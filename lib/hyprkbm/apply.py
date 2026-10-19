"""The only code that writes keybinds.json and keybinds.lua, and the only
code that hands them to Hyprland.

An apply reloads Hyprland first, so the new binds always go onto what
hyprland.lua alone produces rather than on top of the previous apply's.
A reload emits configreloaded; the marker counter tells hyprkbm-watch that
this one was ours and already handled.
"""
import fcntl
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
-- The env falls back to the real _G, where keybinds.lua's preamble would find
-- the live binds' handles and remove them. Shadowing the list with false makes
-- it read `false or {}`, and its assignment lands here instead of in _G.
local env = setmetatable({
    hl = setmetatable(stub, { __index = hl }),
    __hyprkbm_binds = false,
}, { __index = _G })
assert(loadfile(%s, "t", env))()
"""


def hyprctl(*args):
    try:
        res = subprocess.run(["hyprctl", *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10)
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


def _stage(path, text):
    """Write text to a fresh temp file beside path and return its name. The
    temp file is gone again if the write fails, so ENOSPC leaves no litter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return tmp


def write_files(files):
    """Replace several files together: every temp file is written before any
    is renamed into place, so a write that fails (a full disk) changes none of
    them. Leftover temp files are always removed."""
    staged = []
    try:
        for path, text in files:
            staged.append((_stage(path, text), path))
        while staged:
            tmp, path = staged[0]
            os.replace(tmp, path)
            staged.pop(0)
    finally:
        for tmp, _ in staged:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


def write_atomic(path, text):
    write_files([(path, text)])


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
    files = []
    for p in (paths.model, paths.lua):
        if saved is not None and (saved / p.name).exists():
            files.append((p, (saved / p.name).read_text(encoding="utf-8")))
        elif p.exists():
            p.unlink()
    write_files(files)


def _load(paths):
    marker.expect_reload(paths)
    ok, out = hyprctl("reload")
    if not ok:
        marker.cancel_reload(paths)  # no configreloaded will come
        return False, "hyprctl reload failed: " + out
    if not paths.lua.exists():
        return True, ""
    return hyprctl("eval", "dofile(%s)" % string(str(paths.lua)))


def preview(model, paths, catalogue=None):
    """What an apply would write, without writing it or touching Hyprland:
    the panel's diff, and its errors before anyone presses Apply."""
    catalogue = catalogue or load_catalogue()
    try:
        current = paths.lua.read_text(encoding="utf-8")
    except OSError:
        current = ""
    try:
        hand = read_config(paths)
    except OSError as exc:  # no Lua interpreter to run the reader with
        return dict(_failure("the config could not be read: %s" % exc), lua="", current=current)
    if hand.error:
        result = _failure("%s could not be read: %s" % (paths.entry.name, hand.error))
        return dict(result, lua="", current=current)
    errors = validate(model, hand, catalogue)
    if errors:
        return {"ok": False, "errors": errors, "lua": "", "current": current}
    return {"ok": True, "errors": [], "lua": render(model, hand, catalogue), "current": current}


def apply(model, paths, catalogue=None):
    # Two applies at once (the panel and the CLI, say) would interleave their
    # backups, writes and rollbacks, so only one runs at a time.
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    with open(paths.runtime_dir / "apply.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _apply(model, paths, catalogue or load_catalogue())


def _apply(model, paths, catalogue):
    hand = read_config(paths)
    if hand.error:
        return _failure("%s could not be read, so nothing was changed: %s"
                        % (paths.entry.name, hand.error))
    errors = validate(model, hand, catalogue)
    if errors:
        return {"ok": False, "errors": errors}

    text = render(model, hand, catalogue)
    # A name of its own per call, so nothing else can ever swap or delete it.
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(dir=paths.config_dir, prefix=".keybinds.lua.staged.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        ok, out = hyprctl("eval", DRY_RUN % string(staged))
    finally:
        try:
            os.unlink(staged)
        except FileNotFoundError:
            pass
    if not ok:
        return _failure("Hyprland rejected the new keybinds, so nothing was changed: " + out)

    saved = backup(paths)
    try:
        write_files([(paths.model, json.dumps(model, indent=2, ensure_ascii=False) + "\n"),
                     (paths.lua, text)])
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
