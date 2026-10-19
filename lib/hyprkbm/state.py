"""Everything the panel shows, as one JSON document: `hyprkbm --state`.

The panel is QML and does no I/O of its own beyond running hyprKBM's helpers,
so this is its only view of hyprland.lua, keybinds.json, the catalogue, the
backups, the settings and the watcher. Errors are reported in the document
rather than raised: a panel that cannot open is no help in fixing a broken
keybinds.json.
"""
import json
import re
import subprocess

from .apply import write_atomic
from .catalogue import CATALOGUE, describe, load_catalogue
from .model import ModelError, load_model, structure_errors
from .reader import ReadResult, read_config

UNIT = "hyprkbm-watch.service"
LAYOUTS = ("ansi", "iso")
# Backup directories are timestamps; anything else is not one of ours.
BACKUP_NAME = re.compile(r"[0-9T]+\Z")


class SettingsError(ValueError):
    """Raised when settings.json cannot be read or is malformed."""
    pass


def _read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_settings(path):
    """Read settings.json, or raise SettingsError if it exists but is malformed.

    Returns {} if the file does not exist (safe to write).
    Raises SettingsError if the file exists but cannot be parsed as a JSON object.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise SettingsError("settings.json could not be read, so it was left alone: %s" % exc)

    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SettingsError("settings.json could not be read, so it was left alone: %s" % exc)

    if not isinstance(data, dict):
        raise SettingsError("settings.json could not be read, so it was left alone: not a JSON object")

    return data


def watcher_status():
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", UNIT],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return res.stdout.strip() or "unknown"


def backups(paths):
    try:
        names = [d.name for d in paths.backups.iterdir()
                 if d.is_dir() and BACKUP_NAME.match(d.name)]
    except OSError:
        return []
    return sorted(names, reverse=True)


def _hand_entry(index, bind, catalogue):
    opts = bind.opts
    description = opts.get("description") or opts.get("desc") or ""
    return {
        "uid": "h:%d" % index,
        "keys": bind.keys,
        "combo": bind.combo,
        "submap": bind.submap,
        "where": bind.where,
        "fingerprint": bind.fingerprint,
        "reproducible": bind.reproducible,
        "description": description if isinstance(description, str) else str(description),
        "describe": describe(bind.dispatcher, catalogue),
        "dispatcher": bind.dispatcher,
        "opts": opts,
    }


def build_state(paths):
    catalogue = load_catalogue()
    try:
        hand = read_config(paths)
    except OSError as exc:  # no Lua interpreter to run the reader with
        hand = ReadResult(error="the config could not be read: %s" % exc)

    model, model_error = None, None
    try:
        model = load_model(paths.model)
    except ModelError as exc:
        model_error = str(exc)
    if model is not None:
        errors = structure_errors(model, hand, catalogue)
        if errors:
            model_error = "; ".join(e["message"] for e in errors)

    try:
        current = paths.lua.read_text(encoding="utf-8")
    except OSError:
        current = ""

    return {
        "entry": str(paths.entry),
        "readerError": hand.error,
        "hand": [_hand_entry(i, b, catalogue) for i, b in enumerate(hand.binds)],
        "handSubmaps": [{"name": s["name"], "reset": s["reset"]} for s in hand.submaps],
        "model": model,
        "modelError": model_error,
        "catalogue": json.loads(CATALOGUE.read_text(encoding="utf-8"))["actions"],
        "currentLua": current,
        "backups": backups(paths),
        "settings": _read_json(paths.settings),
        "watcher": watcher_status(),
    }


def read_backup(paths, name):
    """A backup's two files, or None when there is no such backup.

    A keybinds.json that exists but cannot be read is reported in modelError
    rather than as a missing model: restoring "nothing" would wipe every
    hyprKBM bind, which is not what an unreadable file means."""
    if not BACKUP_NAME.match(name):
        return None
    folder = paths.backups / name
    if not folder.is_dir():
        return None
    model, model_error = None, None
    path = folder / "keybinds.json"
    if path.exists():
        try:
            model = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(model, dict):
                model, model_error = None, "keybinds.json in this backup is not an object"
        except (OSError, ValueError) as e:
            model, model_error = None, "keybinds.json in this backup cannot be read: %s" % e
    try:
        lua = (folder / "keybinds.lua").read_text(encoding="utf-8")
    except OSError:
        lua = ""
    return {"model": model, "lua": lua, "modelError": model_error}


def set_layout(paths, name):
    """Record the keyboard layout, keeping every other key in settings.json --
    including ones this version has never heard of."""
    if name not in LAYOUTS:
        raise ValueError("layout must be one of %s" % ", ".join(LAYOUTS))
    settings = _read_settings(paths.settings)
    settings["layout"] = name
    write_atomic(paths.settings, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
