"""The only code that writes keybinds.json and keybinds.lua, and the only
code that hands them to Hyprland.

An apply reloads Hyprland first, so the new binds always go onto what
hyprland.lua alone produces rather than on top of the previous apply's.
A reload emits configreloaded; the marker counter tells hyprkbm-watch that
this one was ours and already handled.
"""
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from . import marker
from .catalogue import load_catalogue
from .luaval import string
from .model import validate
from .reader import read_config
from .render import render

KEEP_BACKUPS = 30

# Runs the file with hl.bind, hl.unbind and hl.define_submap stubbed out.
# Hyprland checks a dispatcher's arguments when it is constructed, so this
# finds a bad argument or a syntax error without a single bind changing.
DRY_RUN = """\
local stub = {
    bind = function() end,
    unbind = function() end,
    define_submap = function(_, a, b)
        local f = type(a) == "function" and a or b
        if f then f() end
    end,
}
local env = setmetatable({ hl = setmetatable(stub, { __index = hl }) }, { __index = _G })
assert(loadfile(%s, "t", env))()
"""


def hyprctl(*args):
    try:
        res = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    out = (res.stdout + res.stderr).strip()
    # A failed eval exits 7 and prints "error: ..."; check both, in case a
    # future hyprctl changes one of them.
    return res.returncode == 0 and not out.lower().startswith("error"), out


def _failure(*messages):
    return {"ok": False, "errors": [{"id": None, "message": m} for m in messages]}


def notify(message):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "hyprKBM", "hyprKBM", message],
                       capture_output=True)


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.replace(tmp, path)


def backup(paths, now=None):
    present = [p for p in (paths.model, paths.lua) if p.exists()]
    if not present:
        return None
    target = paths.backups / (now or datetime.now()).strftime("%Y%m%dT%H%M%S%f")
    target.mkdir(parents=True)
    for p in present:
        shutil.copy2(p, target / p.name)
    for old in sorted(d for d in paths.backups.iterdir() if d.is_dir())[:-KEEP_BACKUPS]:
        shutil.rmtree(old)
    return target


def _restore(paths, saved):
    for p in (paths.model, paths.lua):
        if saved is not None and (saved / p.name).exists():
            write_atomic(p, (saved / p.name).read_text())
        elif p.exists():
            p.unlink()


def _load(paths):
    marker.expect_reload(paths)
    ok, out = hyprctl("reload")
    if not ok:
        marker.cancel_reload(paths)  # no configreloaded will come
        return False, "hyprctl reload failed: " + out
    if not paths.lua.exists():
        return True, ""
    return hyprctl("eval", "dofile(%s)" % string(str(paths.lua)))


def apply(model, paths, catalogue=None):
    catalogue = catalogue or load_catalogue()
    hand = read_config(paths)
    if hand.error:
        return _failure("%s could not be read, so nothing was changed: %s"
                        % (paths.entry.name, hand.error))
    errors = validate(model, hand, catalogue)
    if errors:
        return {"ok": False, "errors": errors}

    text = render(model, hand, catalogue)
    staged = paths.config_dir / ".keybinds.lua.staged"
    write_atomic(staged, text)
    try:
        ok, out = hyprctl("eval", DRY_RUN % string(str(staged)))
    finally:
        staged.unlink()
    if not ok:
        return _failure("Hyprland rejected the new keybinds, so nothing was changed: " + out)

    saved = backup(paths)
    try:
        write_atomic(paths.model, json.dumps(model, indent=2, ensure_ascii=False) + "\n")
        write_atomic(paths.lua, text)
        ok, out = _load(paths)
    except BaseException:
        # Whatever went wrong, the two files must not be left disagreeing.
        _restore(paths, saved)
        _load(paths)
        raise
    if ok:
        return {"ok": True, "backup": str(saved) if saved else None}

    _restore(paths, saved)
    back, back_out = _load(paths)
    if back:
        message = ("Hyprland refused the new keybinds, and the previous ones were put back: "
                   + out)
    else:
        message = ("Hyprland refused the new keybinds, and the previous ones could not be "
                   "restored either. Refused: %s. Restore failed: %s" % (out, back_out))
    notify(message)
    return _failure(message)


def live(paths):
    """Put keybinds.lua back on top of whatever hyprland.lua just did."""
    if not paths.lua.exists():
        return {"ok": True}
    ok, out = hyprctl("eval", "dofile(%s)" % string(str(paths.lua)))
    if ok:
        return {"ok": True}
    notify("Your hyprKBM keybinds could not be applied: " + out)
    return _failure(out)
