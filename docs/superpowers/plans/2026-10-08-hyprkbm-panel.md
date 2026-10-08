# hyprKBM Keyboard Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build hyprKBM's keyboard panel: a Quickshell window that shows every keybind on an on-screen keyboard and stages adds, edits, overrides, removals and submaps, applying them through the core's `hyprkbm-apply`.

**Architecture:** The panel reads one JSON document from `hyprkbm --state` and keeps its edits as a staged copy of `keybinds.json`. All logic lives in `quickshell/hyprkbm/lib/*.js` (`.pragma library`, no I/O, tested with `node --test`); QML only binds and draws. Every write goes through a Python helper: `hyprkbm-apply` (apply), `hyprkbm-apply --preview` (validate and render, for the diff), `hyprkbm --set-layout`, `hyprkbm --backup`. The theme layer is copied from hypr-displays.

**Tech Stack:** Quickshell 0.3.1 (QtQuick, QtQuick.Controls, QtQuick.Layouts, Quickshell.Io), JavaScript (QML `.pragma library`, node ≥ 20 for tests), Python 3.12+ stdlib, pytest.

Not in this plan: the cheatsheet overlay and the ⋯ menu's offer to bind it (plan 3).

This is plan 2 of 3 and builds on the core (branch `feat/core`, PR #8); work on branch `feat/panel`, which starts from `feat/core`. Plan 3 is the cheatsheet overlay. Spec: `docs/superpowers/specs/2026-10-07-hyprkbm-design.md`, sections "The panel: keyboard view" and "Panel architecture".

## Global Constraints

- QML only binds and draws. Logic goes in `quickshell/hyprkbm/lib/*.js`, each file starting with `.pragma library`, with no I/O and no Qt APIs, and a test in `tests/js/`.
- The panel never writes `keybinds.json` or `keybinds.lua`. Keybinds leave only through `hyprkbm-apply`; `settings.json` only through `hyprkbm --set-layout`; `theme.json` only through the copied theme layer.
- Python helpers import nothing outside the standard library; `pytest` and `node` are the only development dependencies.
- Tests never touch the real `HOME`, `hyprctl`, `notify-send`, `systemctl` or `qs`: Python tests use the `stubs` fixture and a throwaway `HOME`; JS tests are pure.
- This machine runs a LIVE Hyprland session. Implementers may launch the panel for smoke checks only with `qs -p quickshell/hyprkbm -d` and must kill it afterwards (`qs kill -p quickshell/hyprkbm`). They must never press Apply, never call an apply through IPC, and never run `hyprkbm --apply`, `hyprkbm-apply` (without `--preview`), `install.sh` or `hyprctl reload`.
- Window title `Keybinds`; IPC target `hyprkbm`; theme file `$XDG_CONFIG_HOME/hyprkbm/theme.json` (or `~/.config/hyprkbm/theme.json`).
- Fonts and sizes from `config/Typography.qml` (Inter, 13/11); colours only from `Colors.*` tokens.
- Never name a QML property after a built-in one (`data`, `state`, `size`, `enabled`, `visible`, anything starting with `on`). The store's state document is therefore `doc`, not `state`.
- Commits: `<type>: <description>` with types `feat, fix, refactor, docs, test, chore, perf`; end each commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Comments explain *why*, not *what*.

## File Structure

| Path | Responsibility |
|---|---|
| `lib/hyprkbm/keys.py` | (modify) `Page_Up`/`Page_Down` aliases in combo ids. |
| `lib/hyprkbm/state.py` | Builds the `hyprkbm --state` document. |
| `lib/hyprkbm/apply.py` | (modify) `preview(model, paths)`: validate + render, no writes. |
| `bin/hyprkbm` | (modify) `--state`, `--backup NAME`, `--set-layout ansi|iso`, and no arguments opens the panel. |
| `bin/hyprkbm-apply` | (modify) `--preview`. |
| `package.json`, `tests/js/load.mjs` | node test runner and a loader for `.pragma library` files. |
| `quickshell/hyprkbm/lib/keys.js` | Twin of `keys.py`. |
| `quickshell/hyprkbm/lib/qtkeys.js` | Qt key codes → keysyms and modifiers. |
| `quickshell/hyprkbm/lib/layouts.js` | ANSI and ISO keyboards, key ids, arrow-key navigation. |
| `quickshell/hyprkbm/lib/catalogue.js` | Twin of the catalogue's action helpers; Lua literals for raw edits. |
| `quickshell/hyprkbm/lib/model.js` | Merge staged model + hand binds; conflicts; stale; immutable edit operations. |
| `quickshell/hyprkbm/lib/labels.js` | Short keycap labels. |
| `quickshell/hyprkbm/lib/search.js` | Query parsing and matching. |
| `quickshell/hyprkbm/lib/keymap.js` | Key states, binds on a key, matches, unplaced, extra keys, conflict stepping. |
| `quickshell/hyprkbm/lib/diff.js` | Line diff. |
| `quickshell/hyprkbm/config/*`, `presets/*` | Theme layer, copied from hypr-displays. |
| `quickshell/hyprkbm/components/{Action,Select,Toggle,Field,ThemePopup,ColourPicker,ColourInput}.qml` | Controls, copied from hypr-displays. |
| `quickshell/hyprkbm/state/Store.qml` | The panel's single source of truth; runs the helpers. |
| `quickshell/hyprkbm/shell.qml` | Window, keyboard shortcuts, IPC, layout of the view. |
| `quickshell/hyprkbm/components/KeyCap.qml`, `KeyBlock.qml`, `Keyboard.qml`, `ModifierBar.qml`, `ExtraKeys.qml` | The keyboard. |
| `quickshell/hyprkbm/components/Header.qml`, `BindPanel.qml`, `BindRow.qml`, `Banner.qml` | Header, the selected key's binds, banners. |
| `quickshell/hyprkbm/components/Editor.qml` | The bind editor. |
| `quickshell/hyprkbm/components/StagedBar.qml`, `DiffDialog.qml` | Staged changes and the diff. |
| `quickshell/hyprkbm/components/BackupsDialog.qml`, `ExportDialog.qml`, `SettingsPopup.qml`, `SubmapDialog.qml` | The header's dialogs. |
| `share/applications/hyprkbm.desktop` | Launcher entry. |
| `tests/test_state.py`, `tests/test_panel_qml.py`, `tests/test_theme_presets.py` | Python-side tests for the panel. |

## Shared shapes

The `hyprkbm --state` document (Task 1) — every later task reads it:

```json
{
  "entry": "/home/u/.config/hypr/hyprland.lua",
  "readerError": null,
  "hand": [
    { "uid": "h:0", "keys": "SUPER + F", "combo": "SUPER+f", "submap": "",
      "where": "hyprland.lua:116", "fingerprint": "exec_cmd:[\"dolphin\"]",
      "reproducible": true, "description": "", "describe": "Run a command: dolphin",
      "dispatcher": { "dsp": "exec_cmd", "args": ["dolphin"] }, "opts": {} }
  ],
  "handSubmaps": [ { "name": "resize", "reset": "escape" } ],
  "model": { "version": 1, "submaps": [], "binds": [], "unbinds": [] },
  "modelError": null,
  "catalogue": [ { "id": "exec_cmd", "label": "Run a command", "dsp": "exec_cmd", "call": "positional", "fields": [ … ] } ],
  "currentLua": "",
  "backups": [ "20261008T173647613251" ],
  "settings": {},
  "watcher": "active"
}
```

A **merged bind** (`lib/model.js`, Task 4) — what every view draws:

```js
{ uid: "h:0" | "k:<id>", source: "hand" | "hyprkbm" | "override",
  keys: "SUPER + F", combo: "SUPER+f" | null, mods: ["SUPER"], key: "F",
  submap: "", where: "hyprland.lua:116" | "<id>", id: null | "<id>",
  hand: <hand entry> | null,          // the hand bind itself, or the one an override replaces
  description: "", describe: "Run a command: dolphin",
  dispatcher: {dsp, args} | {raw} | {__function} | null,
  reproducible: true, allowConflict: false,
  action: null | {kind, args} | {kind: "raw", lua}, flags: {} }
```

---

### Task 1: Core support for the panel

**Files:**
- Modify: `lib/hyprkbm/keys.py`, `tests/fixtures/keys.json`
- Create: `lib/hyprkbm/state.py`
- Modify: `lib/hyprkbm/apply.py` (add `preview`), `bin/hyprkbm-apply`, `bin/hyprkbm`
- Test: `tests/test_state.py`, `tests/test_apply.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Consumes (from the core): `read_config(paths) -> ReadResult` (`.binds` of `HandBind` with `keys, combo, submap, dispatcher, opts, file, line, seq`, properties `fingerprint, reproducible, where`; `.submaps`; `.error`); `load_model(path)` / `ModelError`; `structure_errors(model, hand, catalogue)`; `validate`; `render(model, hand, catalogue)`; `describe(dispatcher, catalogue)`; `load_catalogue()`, `CATALOGUE` (path of `share/actions.json`); `apply.write_atomic(path, text)`; `Paths` (`.entry .model .lua .settings .backups`).
- Produces: `keys.KEY_ALIASES`; `state.build_state(paths) -> dict` (the document above); `state.read_backup(paths, name) -> dict | None` (`{"model": dict | None, "lua": str}`); `state.set_layout(paths, name) -> None` (raises `ValueError` for anything but `"ansi"`/`"iso"`); `apply.preview(model, paths, catalogue=None) -> {"ok", "errors", "lua", "current"}`; CLI `hyprkbm --state`, `hyprkbm --backup NAME`, `hyprkbm --set-layout NAME`, `hyprkbm-apply --preview`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/fixtures/keys.json`'s `"same"` array (keep the existing entries):

```json
    ["SUPER + Page_Up", "SUPER+prior"],
    ["SUPER + Prior", "SUPER+prior"],
    ["Page_Down", "next"]
```

`tests/test_state.py`:

```python
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from hyprkbm.state import build_state, read_backup, set_layout

HYPRKBM = Path(__file__).resolve().parents[1] / "bin" / "hyprkbm"


def run(home_env, *args):
    env = dict(home_env, PATH=os.environ["PATH"])
    return subprocess.run([sys.executable, str(HYPRKBM), *args],
                          capture_output=True, text=True, env=env)


def write_config(paths, source):
    paths.entry.write_text(textwrap.dedent(source))


def test_state_describes_hand_binds_for_the_panel(paths, stubs):
    write_config(paths, """\
        hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"), { description = "Files" })
        hl.define_submap("resize", "escape", function()
            hl.bind("right", hl.dsp.window.resize())
        end)
    """)

    doc = build_state(paths)

    assert doc["entry"] == str(paths.entry)
    assert doc["readerError"] is None
    first, second = doc["hand"]
    assert first == {
        "uid": "h:0", "keys": "SUPER + F", "combo": "SUPER+f", "submap": "",
        "where": "hyprland.lua:1", "fingerprint": 'exec_cmd:["dolphin"]',
        "reproducible": True, "description": "Files",
        "describe": "Run a command: dolphin",
        "dispatcher": {"dsp": "exec_cmd", "args": ["dolphin"]},
        "opts": {"description": "Files"},
    }
    assert second["uid"] == "h:1"
    assert second["submap"] == "resize"
    assert doc["handSubmaps"] == [{"name": "resize", "reset": "escape"}]
    assert doc["model"] == {"version": 1, "submaps": [], "binds": [], "unbinds": []}
    assert doc["modelError"] is None
    assert [a["id"] for a in doc["catalogue"]][0] == "exec_cmd"
    assert doc["currentLua"] == ""
    assert doc["backups"] == []
    assert doc["settings"] == {}
    assert doc["watcher"] == "unknown"   # the stub systemctl prints nothing


def test_a_broken_model_is_reported_not_raised(paths, stubs):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text("{oops")

    doc = build_state(paths)

    assert doc["model"] is None
    assert "not valid JSON" in doc["modelError"]


def test_a_structurally_invalid_model_is_reported(paths, stubs):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text('{"version": 2}')

    doc = build_state(paths)

    assert doc["model"] == {"version": 2}
    assert "version must be 1" in doc["modelError"]


def test_backups_are_listed_newest_first_and_readable(paths, stubs):
    for name in ("20260101T000000000000", "20260102T000000000000"):
        (paths.backups / name).mkdir(parents=True)
    newest = paths.backups / "20260102T000000000000"
    (newest / "keybinds.json").write_text('{"version": 1, "binds": []}')
    (newest / "keybinds.lua").write_text("-- old\n")

    assert build_state(paths)["backups"] == ["20260102T000000000000",
                                             "20260101T000000000000"]
    assert read_backup(paths, "20260102T000000000000") == {
        "model": {"version": 1, "binds": []}, "lua": "-- old\n"}
    assert read_backup(paths, "20260101T000000000000") == {"model": None, "lua": ""}
    assert read_backup(paths, "nope") is None
    assert read_backup(paths, "../etc") is None


def test_set_layout_keeps_other_settings(paths):
    paths.settings.parent.mkdir(parents=True)
    paths.settings.write_text('{"entry": "~/dots/hyprland.lua"}')

    set_layout(paths, "iso")

    assert json.loads(paths.settings.read_text()) == {
        "entry": "~/dots/hyprland.lua", "layout": "iso"}
    with pytest.raises(ValueError):
        set_layout(paths, "dvorak")


def test_cli_state_backup_and_layout(home_env, paths, stubs):
    res = run(home_env, "--state")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["hand"] == []

    assert run(home_env, "--backup", "missing").returncode == 1

    res = run(home_env, "--set-layout", "iso")
    assert res.returncode == 0, res.stderr
    assert json.loads(paths.settings.read_text())["layout"] == "iso"
    assert run(home_env, "--set-layout", "qwertz").returncode == 2
```

Append to `tests/test_apply.py`:

```python
def test_preview_renders_without_writing_or_calling_hyprctl(paths, stubs):
    from hyprkbm.apply import preview

    result = preview(GOOD, paths)

    assert result["ok"] is True
    assert result["errors"] == []
    assert 'exec_cmd("firefox")' in result["lua"]
    assert result["current"] == ""
    assert not paths.model.exists()
    assert stubs.calls() == []


def test_preview_reports_errors_and_the_current_file(paths, stubs):
    from hyprkbm.apply import preview
    apply(GOOD, paths)
    bad = {"version": 1, "submaps": [], "unbinds": [],
           "binds": [{"id": "b1", "keys": "SUPER + B", "action": {"kind": "nope"}}]}

    result = preview(bad, paths)

    assert result["ok"] is False
    assert result["errors"][0]["id"] == "b1"
    assert result["lua"] == ""
    assert result["current"] == paths.lua.read_text()


def test_the_executable_previews(home_env, stubs, paths):
    env = dict(home_env, PATH=os.environ["PATH"])
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply"), "--preview"],
                         input=json.dumps(GOOD), capture_output=True, text=True, env=env)

    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["ok"] is True
    assert not paths.lua.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/ -q`
Expected: failures in `test_keys.py` (the three alias cases), `ModuleNotFoundError: No module named 'hyprkbm.state'`, and `ImportError: cannot import name 'preview'`.

- [ ] **Step 3: Implement**

In `lib/hyprkbm/keys.py`, add below `ORDER`:

```python
# Two names xkb accepts for one keysym. A bind written with either spelling
# must land on the same key, in conflict checks and on the panel's keyboard.
KEY_ALIASES = {"page_up": "prior", "page_down": "next"}
```

and replace `Combo.id` with:

```python
    @property
    def id(self):
        # Keysyms are matched case-insensitively: "f" and "F" are one key.
        key = self.key.lower()
        return "+".join(self.mods + (KEY_ALIASES.get(key, key),))
```

Create `lib/hyprkbm/state.py`:

```python
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


def _read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


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
    """A backup's two files, or None when there is no such backup."""
    if not BACKUP_NAME.match(name):
        return None
    folder = paths.backups / name
    if not folder.is_dir():
        return None
    try:
        model = json.loads((folder / "keybinds.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        model = None
    try:
        lua = (folder / "keybinds.lua").read_text(encoding="utf-8")
    except OSError:
        lua = ""
    return {"model": model, "lua": lua}


def set_layout(paths, name):
    """Record the keyboard layout, keeping every other key in settings.json --
    including ones this version has never heard of."""
    if name not in LAYOUTS:
        raise ValueError("layout must be one of %s" % ", ".join(LAYOUTS))
    settings = _read_json(paths.settings)
    settings["layout"] = name
    write_atomic(paths.settings, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
```

In `lib/hyprkbm/apply.py`, add after `live`:

```python
def preview(model, paths, catalogue=None):
    """What an apply would write, without writing it or touching Hyprland:
    the panel's diff, and its errors before anyone presses Apply."""
    catalogue = catalogue or load_catalogue()
    try:
        current = paths.lua.read_text(encoding="utf-8")
    except OSError:
        current = ""
    hand = read_config(paths)
    if hand.error:
        result = _failure("%s could not be read: %s" % (paths.entry.name, hand.error))
        return dict(result, lua="", current=current)
    errors = validate(model, hand, catalogue)
    if errors:
        return {"ok": False, "errors": errors, "lua": "", "current": current}
    return {"ok": True, "errors": [], "lua": render(model, hand, catalogue), "current": current}
```

In `bin/hyprkbm-apply`, change the import to `from hyprkbm.apply import apply, live, preview  # noqa: E402`, add a usage line to the docstring:

```
  hyprkbm-apply --preview  validate and render the model on stdin; write nothing
```

and replace `run` with:

```python
def run(argv, paths):
    if argv == ["--live"]:
        return live(paths)
    if argv in ([], ["--preview"]):
        try:
            model = json.load(sys.stdin)
        except ValueError as exc:
            return {"ok": False, "errors": [{
                "id": None, "message": "the model on stdin is not JSON: %s" % exc}]}
        return preview(model, paths) if argv else apply(model, paths)
    return None
```

In `bin/hyprkbm`, add `import json` to the imports, add `from hyprkbm.state import build_state, read_backup, set_layout  # noqa: E402`, add to the docstring:

```
  hyprkbm --state              everything the panel shows, as JSON
  hyprkbm --backup NAME        one backup's keybinds.json and keybinds.lua, as JSON
  hyprkbm --set-layout NAME    the panel's keyboard layout: ansi or iso
```

add these functions above `main`:

```python
def cmd_state(paths):
    print(json.dumps(build_state(paths), ensure_ascii=False))
    return 0


def cmd_backup(paths, args):
    if len(args) != 1:
        return fail("usage: hyprkbm --backup NAME", code=2)
    found = read_backup(paths, args[0])
    if found is None:
        return fail("no backup called %s" % args[0])
    print(json.dumps(found, ensure_ascii=False))
    return 0


def cmd_set_layout(paths, args):
    if len(args) != 1:
        return fail("usage: hyprkbm --set-layout ansi|iso", code=2)
    try:
        set_layout(paths, args[0])
    except ValueError as exc:
        return fail(str(exc), code=2)
    except OSError as exc:
        return fail("settings could not be written: %s" % exc)
    return 0
```

and add to `main`, before the `--help` check:

```python
    if argv == ["--state"]:
        return cmd_state(paths)
    if argv[:1] == ["--backup"]:
        return cmd_backup(paths, argv[1:])
    if argv[:1] == ["--set-layout"]:
        return cmd_set_layout(paths, argv[1:])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/keys.py lib/hyprkbm/state.py lib/hyprkbm/apply.py bin/hyprkbm bin/hyprkbm-apply tests/fixtures/keys.json tests/test_state.py tests/test_apply.py
git commit -m "feat: give the panel its state, a preview, backups and the layout setting

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: JS foundation: test runner, keys, Qt keys and layouts

**Files:**
- Create: `package.json`, `tests/js/load.mjs`
- Create: `quickshell/hyprkbm/lib/keys.js`, `quickshell/hyprkbm/lib/qtkeys.js`, `quickshell/hyprkbm/lib/layouts.js`
- Test: `tests/js/keys.test.mjs`, `tests/js/qtkeys.test.mjs`, `tests/js/layouts.test.mjs`, `tests/js/conventions.test.mjs`
- Modify: `.github/workflows/ci.yml` (node job)

**Interfaces:**
- Produces (`keys.js`): `MODIFIERS`, `ORDER`, `KEY_ALIASES`, `parse(keys) -> {mods: string[], key: string} | null`, `sortMods(mods) -> string[]` (canonical, de-duplicated, in `ORDER`), `keyId(key) -> string` (lower case, aliases applied), `comboId(mods, key) -> string`, `idOf(keys) -> string | null`, `display(mods, key) -> string`.
- Produces (`qtkeys.js`): `keysymFromQt(key, modifiers?) -> string | null` (with Shift held, a shifted US symbol maps back to its base key), `modifierFromQtKey(key) -> string` (`""` when not a modifier key), `modsFromQt(modifiers) -> string[]`.
- Produces (`layouts.js`): `LAYOUTS` (`{ansi, iso}`, each `{name, main: row[], nav: row[]}`; a row is an array of `{id, label, w}` keys, `{mod, label, w}` modifier keys and `{gap: true, w}` gaps; ISO's `Return` continuation has `cont: true`), `keyIds(layout) -> {[lowerId]: true}`, `keyName(layout, lowerId) -> string` (the id as written in the layout, or `lowerId`), `neighbour(layout, lowerId, dir) -> lowerId` (`dir` is `"left" | "right" | "up" | "down"`).
- Produces (`tests/js/load.mjs`): `load(name)` returns the library's context; `plain(v)`.

- [ ] **Step 1: Write the loader, runner and failing tests**

`package.json`:

```json
{
  "name": "hyprkbm-panel",
  "private": true,
  "description": "hyprKBM's panel is QML and needs no build; this runs the tests of its JavaScript logic.",
  "scripts": {
    "test": "node --test tests/js/"
  }
}
```

`tests/js/load.mjs`:

```js
// Loads one of quickshell/hyprkbm/lib/*.js the way QML does: a `.pragma
// library` script whose top-level declarations are its exports, and whose
// `.import "x.js" as X` lines bring other libraries in under a name. node can
// import neither, so each runs in a fresh context and the context is the library.
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import vm from "node:vm"

export function load(name) {
  const path = fileURLToPath(new URL(`../../quickshell/hyprkbm/lib/${name}.js`, import.meta.url))
  let source = readFileSync(path, "utf8").replace(/^\.pragma library\s*$/m, "")
  const context = vm.createContext({})
  source = source.replace(/^\.import "([\w-]+)\.js" as (\w+)\s*$/gm, (_, dep, alias) => {
    context[alias] = load(dep)
    return ""
  })
  vm.runInContext(source, context, { filename: path })
  return context
}

// Values made inside the vm context have that context's prototypes, which
// deepStrictEqual treats as different; comparing through JSON sidesteps it.
export const plain = (v) => JSON.parse(JSON.stringify(v))
```

`tests/js/keys.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { load, plain } from "./load.mjs"

const K = load("keys")
// The table keys.py is tested against: the two parsers must agree.
const TABLE = JSON.parse(readFileSync(new URL("../fixtures/keys.json", import.meta.url), "utf8"))

test("spellings of one combo share an id", () => {
  for (const [keys, expected] of TABLE.same) assert.equal(K.idOf(keys), expected, keys)
})

test("display uses canonical modifiers and the key as written", () => {
  for (const [keys, expected] of TABLE.display) {
    const c = K.parse(keys)
    assert.equal(K.display(c.mods, c.key), expected, keys)
  }
})

test("malformed combos do not parse", () => {
  for (const keys of TABLE.invalid) assert.equal(K.parse(keys), null, JSON.stringify(keys))
  assert.equal(K.parse(42), null)
})

test("comboId sorts and de-duplicates modifiers", () => {
  assert.equal(K.comboId(["SHIFT", "SUPER", "SUPER"], "Q"), "SUPER+SHIFT+q")
  assert.deepEqual(plain(K.sortMods(["shift", "win"])), ["SUPER", "SHIFT"])
  assert.equal(K.keyId("Page_Up"), "prior")
})
```

`tests/js/qtkeys.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const Q = load("qtkeys")

test("letters, digits and named keys become keysyms", () => {
  assert.equal(Q.keysymFromQt(0x41), "A")
  assert.equal(Q.keysymFromQt(0x30), "0")
  assert.equal(Q.keysymFromQt(0x01000004), "Return")
  assert.equal(Q.keysymFromQt(0x01000012), "left")
  assert.equal(Q.keysymFromQt(0x01000016), "Prior")
  assert.equal(Q.keysymFromQt(0x01000030), "F1")
  assert.equal(Q.keysymFromQt(0x0100003b), "F12")
  assert.equal(Q.keysymFromQt(0x20), "space")
  assert.equal(Q.keysymFromQt(0x2f), "slash")
  assert.equal(Q.keysymFromQt(0x01000072), "XF86AudioRaiseVolume")
})

test("modifier keys are not keysyms but are modifiers", () => {
  assert.equal(Q.keysymFromQt(0x01000020), null)
  assert.equal(Q.modifierFromQtKey(0x01000020), "SHIFT")
  assert.equal(Q.modifierFromQtKey(0x01000021), "CTRL")
  assert.equal(Q.modifierFromQtKey(0x01000023), "ALT")
  assert.equal(Q.modifierFromQtKey(0x01000022), "SUPER")
  assert.equal(Q.modifierFromQtKey(0x01000053), "SUPER")
  assert.equal(Q.modifierFromQtKey(0x41), "")
})

test("unknown keys are null", () => {
  assert.equal(Q.keysymFromQt(0x01ffffff), null)
})

test("modifier flags become canonical modifiers in order", () => {
  assert.deepEqual(plain(Q.modsFromQt(0x02000000 | 0x10000000)), ["SUPER", "SHIFT"])
  assert.deepEqual(plain(Q.modsFromQt(0x04000000 | 0x08000000)), ["CTRL", "ALT"])
  assert.deepEqual(plain(Q.modsFromQt(0)), [])
})
```

`tests/js/layouts.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const L = load("layouts")

function rowWidth(row) { return row.reduce((sum, k) => sum + k.w, 0) }

test("every main row of both layouts is fifteen units wide", () => {
  for (const name of ["ansi", "iso"]) {
    for (const row of L.LAYOUTS[name].main) assert.equal(rowWidth(row), 15, `${name}: ${JSON.stringify(row.map(k => k.id || k.mod || "gap"))}`)
  }
})

test("key ids are lower case and include the keys binds use", () => {
  const ids = L.keyIds(L.LAYOUTS.ansi)
  for (const id of ["q", "1", "0", "tab", "return", "space", "left", "prior", "print", "f12", "grave", "backspace"])
    assert.equal(ids[id], true, id)
  assert.equal(ids["super"], undefined)
  assert.equal(L.keyIds(L.LAYOUTS.iso)["less"], true)
  assert.equal(L.keyIds(L.LAYOUTS.ansi)["less"], undefined)
})

test("keyName gives back the id as the layout writes it", () => {
  assert.equal(L.keyName(L.LAYOUTS.ansi, "return"), "Return")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "q"), "q")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "xf86audiomute"), "xf86audiomute")
})

test("arrow-key navigation moves between neighbouring keys", () => {
  const a = L.LAYOUTS.ansi
  assert.equal(L.neighbour(a, "w", "left"), "q")
  assert.equal(L.neighbour(a, "q", "right"), "w")
  assert.equal(L.neighbour(a, "w", "down"), "s")
  assert.equal(L.neighbour(a, "s", "up"), "w")
  assert.equal(L.neighbour(a, "escape", "left"), "escape")
  assert.equal(L.neighbour(a, "nonsense", "left"), "q")
})
```

`tests/js/conventions.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { readdirSync, readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

const LIB = fileURLToPath(new URL("../../quickshell/hyprkbm/lib/", import.meta.url))

// QML only binds and draws; these files are where the logic lives, and they
// stay testable only while they do no I/O and touch no Qt API.
test("every lib file is a pragma library with no Qt or I/O", () => {
  for (const file of readdirSync(LIB).filter(f => f.endsWith(".js"))) {
    const source = readFileSync(LIB + file, "utf8")
    assert.match(source, /^\.pragma library$/m, file)
    for (const banned of ["Qt.", "Quickshell", "Process", "FileView", "require(", "XMLHttpRequest"])
      assert.ok(!source.includes(banned), `${file} uses ${banned}`)
  }
})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test tests/js/`
Expected: FAIL — `ENOENT` for `quickshell/hyprkbm/lib/keys.js` (and the others).

- [ ] **Step 3: Implement the three libraries**

`quickshell/hyprkbm/lib/keys.js`:

```js
.pragma library

// Key combos as Hyprland's Lua config writes them: "SUPER + SHIFT + F".
// The twin of lib/hyprkbm/keys.py. Both are tested against
// tests/fixtures/keys.json, so what the panel calls one key is what
// hyprkbm-apply calls one key.

var MODIFIERS = {
    SUPER: "SUPER", WIN: "SUPER", LOGO: "SUPER", MOD4: "SUPER",
    CTRL: "CTRL", CONTROL: "CTRL",
    ALT: "ALT", MOD1: "ALT",
    SHIFT: "SHIFT",
    CAPS: "CAPS",
    MOD2: "MOD2", MOD3: "MOD3", MOD5: "MOD5"
}
var ORDER = ["SUPER", "CTRL", "ALT", "SHIFT", "CAPS", "MOD2", "MOD3", "MOD5"]
// Two names xkb accepts for one keysym.
var KEY_ALIASES = { page_up: "prior", page_down: "next" }

function sortMods(mods) {
    var seen = {}
    for (var i = 0; i < mods.length; i++) {
        var canonical = MODIFIERS[String(mods[i]).toUpperCase()]
        if (canonical !== undefined) seen[canonical] = true
    }
    return ORDER.filter(function (m) { return seen[m] === true })
}

function parse(keys) {
    if (typeof keys !== "string") return null
    var tokens = []
    var parts = keys.split("+")
    for (var i = 0; i < parts.length; i++) {
        var words = parts[i].split(/\s+/)
        for (var j = 0; j < words.length; j++)
            if (words[j] !== "") tokens.push(words[j])
    }
    if (tokens.length === 0) return null
    var key = tokens.pop()
    for (var k = 0; k < tokens.length; k++)
        if (MODIFIERS[tokens[k].toUpperCase()] === undefined) return null
    return { mods: sortMods(tokens), key: key }
}

function keyId(key) {
    var lower = String(key).toLowerCase()
    return KEY_ALIASES.hasOwnProperty(lower) ? KEY_ALIASES[lower] : lower
}

function comboId(mods, key) {
    return sortMods(mods).concat([keyId(key)]).join("+")
}

function idOf(keys) {
    var c = parse(keys)
    return c === null ? null : comboId(c.mods, c.key)
}

function display(mods, key) {
    return sortMods(mods).concat([key]).join(" + ")
}
```

`quickshell/hyprkbm/lib/qtkeys.js`:

```js
.pragma library

// Qt's key codes, as a QML Keys handler reports them, turned into the keysym
// names hl.bind takes. Numbers rather than the named enum, so that this stays
// plain JavaScript the tests can load; the values are Qt 6's Qt::Key enum.

var NAMED = {
    0x01000000: "Escape", 0x01000001: "Tab", 0x01000002: "Tab",
    0x01000003: "BackSpace", 0x01000004: "Return", 0x01000005: "KP_Enter",
    0x01000006: "Insert", 0x01000007: "Delete", 0x01000008: "Pause",
    0x01000009: "Print", 0x01000010: "Home", 0x01000011: "End",
    0x01000012: "left", 0x01000013: "up", 0x01000014: "right", 0x01000015: "down",
    0x01000016: "Prior", 0x01000017: "Next", 0x01000024: "Caps_Lock",
    0x01000026: "Scroll_Lock", 0x01000055: "Menu",
    0x20: "space", 0x2d: "minus", 0x3d: "equal", 0x5b: "bracketleft",
    0x5d: "bracketright", 0x5c: "backslash", 0x3b: "semicolon",
    0x27: "apostrophe", 0x60: "grave", 0x2c: "comma", 0x2e: "period",
    0x2f: "slash", 0x3c: "less", 0x23: "numbersign",
    0x01000070: "XF86AudioLowerVolume", 0x01000071: "XF86AudioMute",
    0x01000072: "XF86AudioRaiseVolume", 0x01000080: "XF86AudioPlay",
    0x01000081: "XF86AudioStop", 0x01000082: "XF86AudioPrev",
    0x01000083: "XF86AudioNext", 0x010000b2: "XF86MonBrightnessUp",
    0x010000b3: "XF86MonBrightnessDown"
}

// Holding these is choosing a combo, not pressing a key of one.
var MODIFIER_KEYS = {
    0x01000020: "SHIFT", 0x01000021: "CTRL", 0x01000022: "SUPER",
    0x01000023: "ALT", 0x01000053: "SUPER", 0x01000054: "SUPER"
}

// Qt::KeyboardModifier flags. Super arrives as Meta on Linux.
var FLAGS = [
    [0x10000000, "SUPER"], [0x04000000, "CTRL"], [0x08000000, "ALT"], [0x02000000, "SHIFT"]
]

function keysymFromQt(key) {
    if (MODIFIER_KEYS.hasOwnProperty(key)) return null
    if (key >= 0x41 && key <= 0x5a) return String.fromCharCode(key)
    if (key >= 0x30 && key <= 0x39) return String.fromCharCode(key)
    if (key >= 0x01000030 && key <= 0x01000047) return "F" + (key - 0x01000030 + 1)
    return NAMED.hasOwnProperty(key) ? NAMED[key] : null
}

function modifierFromQtKey(key) {
    return MODIFIER_KEYS.hasOwnProperty(key) ? MODIFIER_KEYS[key] : ""
}

function modsFromQt(modifiers) {
    var out = []
    for (var i = 0; i < FLAGS.length; i++)
        if ((modifiers & FLAGS[i][0]) !== 0) out.push(FLAGS[i][1])
    return out
}
```

`quickshell/hyprkbm/lib/layouts.js`:

```js
.pragma library

// Physical keyboards, as rows of keys measured in key units (1 = one letter
// key). Ids are xkb keysym names, which is what hl.bind takes; the rest of
// the panel compares them in lower case, as Hyprland does.
//
// Every main row is fifteen units wide. The navigation cluster's rows line up
// with the main rows: function keys, digits, letters, home row, shift, space.

function key(id, label, w) {
    return { id: id, label: label === undefined ? id : label, w: w === undefined ? 1 : w }
}
function mod(name, label, w) { return { mod: name, label: label, w: w } }
function gap(w) { return { gap: true, w: w } }
function letters(text) {
    return text.split("").map(function (c) { return key(c, c.toUpperCase()) })
}
function fkeys(first, last) {
    var out = []
    for (var i = first; i <= last; i++) out.push(key("F" + i))
    return out
}

var FUNCTION_ROW = [key("Escape", "Esc"), gap(1)].concat(
    fkeys(1, 4), [gap(0.5)], fkeys(5, 8), [gap(0.5)], fkeys(9, 12))
var NUMBER_ROW = [key("grave", "`")].concat(
    "1234567890".split("").map(function (d) { return key(d) }),
    [key("minus", "-"), key("equal", "="), key("BackSpace", "⌫", 2)])
var SPACE_ROW = [mod("CTRL", "Ctrl", 1.25), mod("SUPER", "Super", 1.25), mod("ALT", "Alt", 1.25),
                 key("space", "Space", 6.25), mod("ALT", "Alt", 1.25), mod("SUPER", "Super", 1.25),
                 key("Menu", "Menu", 1.25), mod("CTRL", "Ctrl", 1.25)]

var NAV = [
    [key("Print", "PrtSc"), key("Scroll_Lock", "ScrLk"), key("Pause")],
    [key("Insert", "Ins"), key("Home"), key("Prior", "PgUp")],
    [key("Delete", "Del"), key("End"), key("Next", "PgDn")],
    [],
    [gap(1), key("up", "↑")],
    [key("left", "←"), key("down", "↓"), key("right", "→")]
]

var LAYOUTS = {
    ansi: {
        name: "ANSI",
        main: [
            FUNCTION_ROW,
            NUMBER_ROW,
            [key("Tab", "Tab", 1.5)].concat(letters("qwertyuiop"),
                [key("bracketleft", "["), key("bracketright", "]"), key("backslash", "\\", 1.5)]),
            [key("Caps_Lock", "Caps", 1.75)].concat(letters("asdfghjkl"),
                [key("semicolon", ";"), key("apostrophe", "'"), key("Return", "Enter", 2.25)]),
            [mod("SHIFT", "Shift", 2.25)].concat(letters("zxcvbnm"),
                [key("comma", ","), key("period", "."), key("slash", "/"), mod("SHIFT", "Shift", 2.75)]),
            SPACE_ROW
        ],
        nav: NAV
    },
    iso: {
        name: "ISO",
        main: [
            FUNCTION_ROW,
            NUMBER_ROW,
            [key("Tab", "Tab", 1.5)].concat(letters("qwertyuiop"),
                [key("bracketleft", "["), key("bracketright", "]"), key("Return", "Enter", 1.5)]),
            // The tall ISO Enter's lower half: the same key, drawn again.
            [key("Caps_Lock", "Caps", 1.75)].concat(letters("asdfghjkl"),
                [key("semicolon", ";"), key("apostrophe", "'"), key("numbersign", "#"),
                 { id: "Return", label: "", w: 1.25, cont: true }]),
            [mod("SHIFT", "Shift", 1.25), key("less", "<")].concat(letters("zxcvbnm"),
                [key("comma", ","), key("period", "."), key("slash", "/"), mod("SHIFT", "Shift", 2.75)]),
            SPACE_ROW
        ],
        nav: NAV
    }
}

function eachKey(layout, fn) {
    var blocks = [layout.main, layout.nav]
    for (var b = 0; b < blocks.length; b++)
        for (var r = 0; r < blocks[b].length; r++)
            for (var k = 0; k < blocks[b][r].length; k++) fn(blocks[b][r][k], b, r)
}

function keyIds(layout) {
    var out = {}
    eachKey(layout, function (k) { if (k.id !== undefined) out[k.id.toLowerCase()] = true })
    return out
}

function keyName(layout, lowerId) {
    var found = lowerId
    eachKey(layout, function (k) {
        if (k.id !== undefined && k.id.toLowerCase() === lowerId) found = k.id
    })
    return found
}

// Each key's row and horizontal centre, the navigation cluster sitting half a
// unit to the right of the main block.
function positions(layout) {
    var out = []
    var blocks = [{ rows: layout.main, x0: 0 }, { rows: layout.nav, x0: 15.5 }]
    for (var b = 0; b < blocks.length; b++) {
        for (var r = 0; r < blocks[b].rows.length; r++) {
            var x = blocks[b].x0
            var row = blocks[b].rows[r]
            for (var k = 0; k < row.length; k++) {
                if (row[k].id !== undefined && !row[k].cont)
                    out.push({ id: row[k].id.toLowerCase(), row: r, x: x + row[k].w / 2 })
                x += row[k].w
            }
        }
    }
    return out
}

function neighbour(layout, lowerId, dir) {
    var all = positions(layout)
    var here = null
    for (var i = 0; i < all.length; i++) if (all[i].id === lowerId) here = all[i]
    if (here === null) return "q"
    var best = null
    for (var j = 0; j < all.length; j++) {
        var p = all[j]
        var ok = dir === "left" ? (p.row === here.row && p.x < here.x)
               : dir === "right" ? (p.row === here.row && p.x > here.x)
               : dir === "up" ? p.row === here.row - 1
               : p.row === here.row + 1
        if (!ok) continue
        var distance = Math.abs(p.x - here.x)
        if (best === null || distance < best.distance) best = { id: p.id, distance: distance }
    }
    return best === null ? lowerId : best.id
}
```

Append to `.github/workflows/ci.yml` under `jobs:`:

```yaml
  js:
    name: Panel logic (node)
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-node@v4
        with:
          node-version: '22'

      # Plain node, no packages: the panel's logic is .pragma library
      # JavaScript that tests/js/load.mjs runs in a fresh context.
      - name: Run tests
        run: npm test
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/js/ && python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add package.json tests/js quickshell/hyprkbm/lib .github/workflows/ci.yml
git commit -m "feat: add the panel's key parsing, Qt key codes and keyboard layouts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: JS catalogue helpers

**Files:**
- Create: `quickshell/hyprkbm/lib/catalogue.js`
- Test: `tests/js/catalogue.test.mjs`

**Interfaces:**
- Consumes: the catalogue array from `doc.catalogue` (entries `{id, label, dsp, call, fields: [{name, label, type, required?, values?, default?}], oneOf?}`), dispatcher shapes from the Shared shapes section.
- Produces: `entryById(catalogue, id)`, `entryByDsp(catalogue, dsp)`, `toDispatcher(action, catalogue)`, `actionErrors(action, catalogue) -> string[]`, `describeDispatcher(d, catalogue) -> string`, `describeAction(action, catalogue) -> string`, `luaLiteral(value) -> string`, `dispatcherLua(d) -> string`, `actionFromDispatcher(d, catalogue) -> action | null` (null for a Lua function or an opaque value), `defaultArgs(entry) -> object`.

- [ ] **Step 1: Write the failing test**

`tests/js/catalogue.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { load, plain } from "./load.mjs"

const C = load("catalogue")
const CAT = JSON.parse(readFileSync(new URL("../../share/actions.json", import.meta.url), "utf8")).actions

test("actions become the same dispatchers as in Python", () => {
  assert.deepEqual(plain(C.toDispatcher({ kind: "exec_cmd", args: { cmd: "kitty" } }, CAT)),
                   { dsp: "exec_cmd", args: ["kitty"] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "window.move", args: { workspace: 3 } }, CAT)),
                   { dsp: "window.move", args: [{ workspace: 3 }] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "window.close" }, CAT)), { dsp: "window.close", args: [] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "raw", lua: "hl.dsp.exit()" }, CAT)), { raw: "hl.dsp.exit()" })
})

test("bad actions are explained, good ones are not", () => {
  const cases = [
    [{ kind: "nope" }, "unknown action"],
    [{ kind: [] }, "unknown action"],
    [{ kind: "exec_cmd", args: {} }, "needs command"],
    [{ kind: "exec_cmd", args: { cmd: "" } }, "must be text"],
    [{ kind: "exec_cmd", args: { cmd: "x", extra: 1 } }, "no field \"extra\""],
    [{ kind: "window.float", args: { action: "flip" } }, "must be one of"],
    [{ kind: "window.move", args: {} }, "exactly one of"],
    [{ kind: "window.move", args: { workspace: true } }, "workspace number or name"],
    [{ kind: "window.cycle_next", args: { next: "yes" } }, "true or false"],
    [{ kind: "raw", lua: "  " }, "needs some Lua"],
    ["exec_cmd", "must be an object"]
  ]
  for (const [action, problem] of cases) {
    const errors = plain(C.actionErrors(action, CAT))
    assert.ok(errors.some(e => e.includes(problem)), `${JSON.stringify(action)}: ${JSON.stringify(errors)}`)
  }
  assert.deepEqual(plain(C.actionErrors({ kind: "focus", args: { workspace: "e+1" } }, CAT)), [])
  assert.deepEqual(plain(C.actionErrors({ kind: "window.close" }, CAT)), [])
})

test("descriptions match the Python catalogue's", () => {
  assert.equal(C.describeDispatcher({ dsp: "exec_cmd", args: ["kitty"] }, CAT), "Run a command: kitty")
  assert.equal(C.describeDispatcher({ dsp: "focus", args: [{ workspace: 3 }] }, CAT), "Focus (workspace 3)")
  assert.equal(C.describeDispatcher({ dsp: "window.close", args: [] }, CAT), "Close window")
  assert.equal(C.describeDispatcher({ dsp: "window.cycle_next", args: [{ next: false }] }, CAT), "Cycle windows (next no)")
  assert.equal(C.describeDispatcher({ dsp: "group.toggle", args: [] }, CAT), "hl.dsp.group.toggle()")
  assert.equal(C.describeDispatcher({ __function: "/home/u/.config/hypr/hyprland.lua:150" }, CAT), "Lua function (hyprland.lua:150)")
  assert.equal(C.describeDispatcher({ raw: "hl.dsp.layout(\n  'x')" }, CAT), "Lua: hl.dsp.layout( 'x')")
  assert.equal(C.describeAction({ kind: "exec_cmd", args: { cmd: "kitty" } }, CAT), "Run a command: kitty")
})

test("Lua literals match luaval.to_lua", () => {
  assert.equal(C.luaLiteral({ workspace: 3, action: "toggle" }), '{ action = "toggle", workspace = 3 }')
  assert.equal(C.luaLiteral([1, "a", true]), '{ 1, "a", true }')
  assert.equal(C.luaLiteral({ end: 1, "a-b": 2 }), '{ ["a-b"] = 2, ["end"] = 1 }')
  assert.equal(C.luaLiteral('say "hi"\n'), '"say \\"hi\\"\\n"')
  assert.equal(C.dispatcherLua({ dsp: "window.move", args: [{ workspace: 3 }] }), "hl.dsp.window.move({ workspace = 3 })")
})

test("a hand bind's dispatcher becomes an editable action", () => {
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "exec_cmd", args: ["kitty"] }, CAT)),
                   { kind: "exec_cmd", args: { cmd: "kitty" } })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "focus", args: [{ workspace: 2 }] }, CAT)),
                   { kind: "focus", args: { workspace: 2 } })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "window.close", args: [] }, CAT)),
                   { kind: "window.close", args: {} })
  // Not in the catalogue, or not in a shape it knows: kept as raw Lua.
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "group.toggle", args: [] }, CAT)),
                   { kind: "raw", lua: "hl.dsp.group.toggle()" })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "window.resize", args: [{ x: 10, y: 0, relative: true }] }, CAT)),
                   { kind: "raw", lua: "hl.dsp.window.resize({ relative = true, x = 10, y = 0 })" })
  assert.equal(C.actionFromDispatcher({ __function: "f.lua:1" }, CAT), null)
  assert.equal(C.actionFromDispatcher({ __opaque: true }, CAT), null)
})

test("default args come from the fields' defaults", () => {
  assert.deepEqual(plain(C.defaultArgs(C.entryById(CAT, "window.fullscreen"))), { mode: "fullscreen", action: "toggle" })
  assert.deepEqual(plain(C.defaultArgs(C.entryById(CAT, "exec_cmd"))), {})
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test tests/js/catalogue.test.mjs`
Expected: FAIL — `ENOENT` for `catalogue.js`.

- [ ] **Step 3: Implement**

`quickshell/hyprkbm/lib/catalogue.js`:

```js
.pragma library

// The action catalogue's helpers, twins of lib/hyprkbm/catalogue.py for what
// the panel needs before anything is applied: turning an action into the
// dispatcher it stands for, describing it, checking its fields, and turning a
// hand-written bind's dispatcher back into something the editor can show.
// hyprkbm-apply checks everything again; these give the answer early.

var KEYWORDS = ["and", "break", "do", "else", "elseif", "end", "false", "for",
                "function", "global", "goto", "if", "in", "local", "nil", "not",
                "or", "repeat", "return", "then", "true", "until", "while"]
var IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/

function entryById(catalogue, id) {
    for (var i = 0; i < catalogue.length; i++) if (catalogue[i].id === id) return catalogue[i]
    return null
}

function entryByDsp(catalogue, dsp) {
    for (var i = 0; i < catalogue.length; i++) if (catalogue[i].dsp === dsp) return catalogue[i]
    return null
}

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

function fieldProblem(field, value) {
    var kind = field.type
    if (kind === "string" || kind === "submap")
        return typeof value === "string" && value !== "" ? null : "must be text"
    if (kind === "workspace") {
        var ok = (typeof value === "number" && Math.floor(value) === value)
              || (typeof value === "string" && value !== "")
        return ok ? null : "must be a workspace number or name"
    }
    if (kind === "enum")
        return field.values.indexOf(value) >= 0 ? null : "must be one of " + field.values.join(", ")
    if (kind === "bool") return typeof value === "boolean" ? null : "must be true or false"
    return "has an unknown type " + kind
}

function actionErrors(action, catalogue) {
    if (!isObject(action)) return ["action must be an object"]
    if (action.kind === "raw")
        return typeof action.lua === "string" && action.lua.trim() !== "" ? [] : ["raw action needs some Lua"]
    var entry = typeof action.kind === "string" ? entryById(catalogue, action.kind) : null
    if (entry === null) return ["unknown action " + JSON.stringify(action.kind)]
    var args = action.args === undefined ? {} : action.args
    if (!isObject(args)) return ["args must be an object"]
    var fields = {}
    entry.fields.forEach(function (f) { fields[f.name] = f })
    var errors = []
    Object.keys(args).forEach(function (name) {
        if (!fields.hasOwnProperty(name)) errors.push(entry.label + " has no field " + JSON.stringify(name))
    })
    entry.fields.forEach(function (f) {
        if (!args.hasOwnProperty(f.name)) {
            if (f.required) errors.push(entry.label + " needs " + f.label.toLowerCase())
            return
        }
        var problem = fieldProblem(f, args[f.name])
        if (problem !== null) errors.push(f.label + ": " + problem)
    })
    if (entry.oneOf) {
        var count = entry.oneOf.filter(function (n) { return args.hasOwnProperty(n) }).length
        if (count !== 1) errors.push(entry.label + " needs exactly one of: " + entry.oneOf.join(", "))
    }
    return errors
}

function toDispatcher(action, catalogue) {
    if (action.kind === "raw") return { raw: action.lua }
    var entry = entryById(catalogue, action.kind)
    var args = action.args || {}
    if (entry.call === "none") return { dsp: entry.dsp, args: [] }
    if (entry.call === "positional") {
        var values = []
        for (var i = 0; i < entry.fields.length; i++) {
            if (!args.hasOwnProperty(entry.fields[i].name)) break
            values.push(args[entry.fields[i].name])
        }
        return { dsp: entry.dsp, args: values }
    }
    var table = {}
    var any = false
    entry.fields.forEach(function (f) {
        if (args.hasOwnProperty(f.name)) { table[f.name] = args[f.name]; any = true }
    })
    return { dsp: entry.dsp, args: any ? [table] : [] }
}

function plain(v) {
    if (v === true) return "yes"
    if (v === false) return "no"
    if (v !== null && typeof v === "object") return JSON.stringify(v)
    return String(v)
}

function luaString(text) {
    var out = ""
    for (var i = 0; i < text.length; i++) {
        var ch = text[i]
        var code = text.charCodeAt(i)
        if (ch === "\"") out += "\\\""
        else if (ch === "\\") out += "\\\\"
        else if (ch === "\n") out += "\\n"
        else if (ch === "\r") out += "\\r"
        else if (ch === "\t") out += "\\t"
        else if (code < 0x20 || code === 0x7f) out += "\\" + ("00" + code).slice(-3)
        else out += ch
    }
    return "\"" + out + "\""
}

function luaLiteral(value) {
    if (value === null || value === undefined) return "nil"
    if (value === true) return "true"
    if (value === false) return "false"
    if (typeof value === "number") return String(value)
    if (typeof value === "string") return luaString(value)
    if (Array.isArray(value))
        return value.length === 0 ? "{}" : "{ " + value.map(luaLiteral).join(", ") + " }"
    var keys = Object.keys(value).sort()
    if (keys.length === 0) return "{}"
    return "{ " + keys.map(function (k) {
        var name = IDENTIFIER.test(k) && KEYWORDS.indexOf(k) < 0 ? k : "[" + luaString(k) + "]"
        return name + " = " + luaLiteral(value[k])
    }).join(", ") + " }"
}

function dispatcherLua(d) {
    if (d.raw !== undefined) return d.raw
    return "hl.dsp." + d.dsp + "(" + (d.args || []).map(luaLiteral).join(", ") + ")"
}

function basename(path) { return String(path).split("/").pop() }

function describeDispatcher(d, catalogue) {
    if (!d) return "Unknown action"
    if (d.raw !== undefined) return "Lua: " + d.raw.split(/\s+/).filter(function (w) { return w !== "" }).join(" ")
    if (d.__function !== undefined) return "Lua function (" + basename(d.__function) + ")"
    if (d.dsp === undefined) return "Unknown action"
    var args = d.args || []
    var entry = entryByDsp(catalogue, d.dsp)
    if (entry === null) return dispatcherLua(d)
    if (entry.call === "table" && args.length === 1 && isObject(args[0]) && Object.keys(args[0]).length > 0) {
        var details = Object.keys(args[0]).sort().map(function (k) { return k + " " + plain(args[0][k]) })
        return entry.label + " (" + details.join(", ") + ")"
    }
    if (args.length > 0) return entry.label + ": " + args.map(plain).join(" ")
    return entry.label
}

function describeAction(action, catalogue) {
    if (actionErrors(action, catalogue).length > 0) return "Incomplete action"
    return describeDispatcher(toDispatcher(action, catalogue), catalogue)
}

function defaultArgs(entry) {
    var out = {}
    if (entry === null) return out
    entry.fields.forEach(function (f) { if (f.default !== undefined) out[f.name] = f.default })
    return out
}

// The editor shows a hand-written bind as a catalogue action when it is one,
// and as raw Lua otherwise; a Lua function cannot be shown as either.
function actionFromDispatcher(d, catalogue) {
    if (!d || d.__function !== undefined || d.__opaque !== undefined) return null
    if (d.raw !== undefined) return { kind: "raw", lua: d.raw }
    var entry = entryByDsp(catalogue, d.dsp)
    var args = d.args || []
    var candidate = null
    if (entry !== null) {
        if (entry.call === "none" && args.length === 0) candidate = { kind: entry.id, args: {} }
        else if (entry.call === "positional" && args.length <= entry.fields.length) {
            var named = {}
            for (var i = 0; i < args.length; i++) named[entry.fields[i].name] = args[i]
            candidate = { kind: entry.id, args: named }
        } else if (entry.call === "table" && args.length === 0) candidate = { kind: entry.id, args: {} }
        else if (entry.call === "table" && args.length === 1 && isObject(args[0]))
            candidate = { kind: entry.id, args: JSON.parse(JSON.stringify(args[0])) }
    }
    if (candidate !== null && actionErrors(candidate, catalogue).length === 0) return candidate
    return { kind: "raw", lua: dispatcherLua(d) }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add quickshell/hyprkbm/lib/catalogue.js tests/js/catalogue.test.mjs
git commit -m "feat: add the panel's catalogue helpers, twins of the Python ones

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: JS model: merge, conflicts and edits

**Files:**
- Create: `quickshell/hyprkbm/lib/model.js`, `quickshell/hyprkbm/lib/labels.js`
- Test: `tests/js/model.test.mjs`, `tests/js/labels.test.mjs`

**Interfaces:**
- Consumes: `keys.js` (`parse`, `idOf`, `keyId`), `catalogue.js` (`toDispatcher`, `actionErrors`, `describeAction`); hand entries from `doc.hand`.
- Produces (`model.js`): `emptyModel()`, `clone(v)`, `normalise(model)`, `merge(hand, model, catalogue) -> {binds, removed, stale, conflicts}` (binds: merged binds; removed: `[{uid, hand}]` hand binds an unbind removes; stale: `[{kind, id, keys, message}]`; conflicts: arrays of merged binds), `newId(model)`, `addBind(model, fields)`, `updateBind(model, id, fields)`, `removeBind(model, id)`, `unbindHand(model, hand)`, `restoreHand(model, hand)`, `overrideHand(model, hand, fields)`, `addSubmap(model, name, reset)`, `submapNames(hand, handSubmaps, model) -> string[]` (`""` first), `overrideBlocker(hand, target) -> string | null` (the `where` of a hand bind that blocks replacing `target`), `summary(saved, model) -> {added, changed, removed, unbound, restored, submaps}`, `FLAG_NAMES`. `fields` is `{keys, submap, action, description, flags, allowConflict}`.
- Produces (`labels.js`): `MAX = 8`, `shortLabel(bind) -> string`.

- [ ] **Step 1: Write the failing tests**

`tests/js/model.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { load, plain } from "./load.mjs"

const M = load("model")
const CAT = JSON.parse(readFileSync(new URL("../../share/actions.json", import.meta.url), "utf8")).actions

function hand(i, keys, combo, dsp, args, extra) {
  return Object.assign({
    uid: "h:" + i, keys, combo, submap: "", where: "hyprland.lua:" + (i + 1),
    fingerprint: dsp + ":" + JSON.stringify(args), reproducible: true,
    description: "", describe: dsp, dispatcher: { dsp, args }, opts: {}
  }, extra || {})
}

const HAND = [
  hand(0, "SUPER + F", "SUPER+f", "exec_cmd", ["dolphin"]),
  hand(1, "SUPER + P", "SUPER+p", "window.pseudo", []),
  hand(2, "SUPER + F", "SUPER+f", "window.resize", [], { submap: "resize" })
]
const FILES = { kind: "exec_cmd", args: { cmd: "nautilus" } }

test("merge keeps hand binds and adds hyprKBM's", () => {
  const model = M.addBind(M.emptyModel(), { keys: "SUPER + B", action: { kind: "exec_cmd", args: { cmd: "firefox" } } })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => [b.uid, b.source]), [["h:0", "hand"], ["h:1", "hand"], ["h:2", "hand"], ["k:b1", "hyprkbm"]])
  const own = m.binds[3]
  assert.equal(own.combo, "SUPER+b")
  assert.deepEqual(own.mods, ["SUPER"])
  assert.equal(own.key, "B")
  assert.equal(own.describe, "Run a command: firefox")
  assert.deepEqual(own.dispatcher, { dsp: "exec_cmd", args: ["firefox"] })
  assert.deepEqual(m.conflicts, [])
})

test("an override replaces exactly its hand bind", () => {
  const model = M.overrideHand(M.emptyModel(), HAND[0], { keys: "SUPER + F", action: FILES })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => b.uid), ["h:1", "h:2", "k:b1"])
  assert.equal(m.binds[2].source, "override")
  assert.equal(m.binds[2].hand.where, "hyprland.lua:1")
  assert.deepEqual(model.binds[0].replaces, { keys: "SUPER + F", submap: "", fingerprint: 'exec_cmd:["dolphin"]' })
})

test("an unbind removes its hand bind and can be undone", () => {
  let model = M.unbindHand(M.emptyModel(), HAND[1])
  model = M.unbindHand(model, HAND[1])   // twice is once
  assert.equal(model.unbinds.length, 1)
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => b.uid), ["h:0", "h:2"])
  assert.deepEqual(m.removed.map(r => r.uid), ["h:1"])
  assert.deepEqual(plain(M.restoreHand(model, HAND[1])).unbinds, [])
})

test("targets that are gone are stale; a stale override is an ordinary bind", () => {
  const model = M.normalise({ version: 1, binds: [{ id: "b1", keys: "SUPER + X", action: FILES,
    replaces: { keys: "SUPER + X", submap: "", fingerprint: "gone" } }],
    unbinds: [{ keys: "SUPER + Y", submap: "", fingerprint: "gone" }] })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.stale.map(s => [s.kind, s.id, s.keys]), [["unbind", null, "SUPER + Y"], ["bind", "b1", "SUPER + X"]])
  assert.equal(m.binds[3].source, "hyprkbm")
})

test("conflicts group by submap and combo, ignoring allowed ones", () => {
  let model = M.addBind(M.emptyModel(), { keys: "WIN + f", action: FILES })
  model = M.addBind(model, { keys: "SUPER + P", action: FILES, allowConflict: true })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.conflicts.map(g => g.map(b => b.uid)), [["h:0", "k:b1"]])
})

test("edits never mutate their input and tidy empty fields", () => {
  const before = M.addBind(M.emptyModel(), { keys: "SUPER + B", submap: "", action: FILES, description: "", flags: { locked: false }, allowConflict: false })
  const snapshot = JSON.stringify(before)
  assert.deepEqual(plain(before.binds[0]), { id: "b1", keys: "SUPER + B", action: FILES })
  const after = M.updateBind(before, "b1", { description: "Files", flags: { locked: true } })
  assert.equal(JSON.stringify(before), snapshot)
  assert.deepEqual(plain(after.binds[0]), { id: "b1", keys: "SUPER + B", action: FILES, description: "Files", flags: { locked: true } })
  assert.equal(M.removeBind(after, "b1").binds.length, 0)
  assert.equal(M.newId(after), "b2")
})

test("submaps", () => {
  const model = M.addSubmap(M.emptyModel(), "move", "escape")
  assert.deepEqual(plain(model.submaps), [{ name: "move", reset: "escape" }])
  assert.deepEqual(plain(M.submapNames(HAND, [{ name: "resize", reset: "escape" }], model)), ["", "move", "resize"])
})

test("an override is blocked by a Lua function on the same keys", () => {
  const fn = hand(3, "SUPER + F", "SUPER+f", "x", [], { submap: "x", reproducible: false, dispatcher: { __function: "h.lua:9" }, where: "hyprland.lua:9" })
  assert.equal(M.overrideBlocker(HAND.concat([fn]), HAND[0]), "hyprland.lua:9")
  assert.equal(M.overrideBlocker(HAND, HAND[0]), null)
  assert.equal(M.overrideBlocker(HAND.concat([fn]), fn), null)
})

test("summary counts what changed", () => {
  const saved = M.addBind(M.emptyModel(), { keys: "SUPER + B", action: FILES })
  let model = M.updateBind(saved, "b1", { description: "x" })
  model = M.addBind(model, { keys: "SUPER + N", action: FILES })
  model = M.unbindHand(model, HAND[1])
  model = M.addSubmap(model, "move", "escape")
  assert.deepEqual(plain(M.summary(saved, model)), { added: 1, changed: 1, removed: 0, unbound: 1, restored: 0, submaps: 1 })
  assert.deepEqual(plain(M.summary(model, saved)), { added: 0, changed: 1, removed: 1, unbound: 0, restored: 1, submaps: -1 })
})
```

`tests/js/labels.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const L = load("labels")
const b = (dispatcher, description) => ({ dispatcher, description: description || "" })

test("short labels fit on a key", () => {
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["rofi -show drun"] })), "rofi")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["/usr/bin/kitty"] })), "kitty")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["jetbrains-toolbox"] })), "jetbrai…")
  assert.equal(L.shortLabel(b({ dsp: "focus", args: [{ workspace: 3 }] })), "ws 3")
  assert.equal(L.shortLabel(b({ dsp: "window.move", args: [{ workspace: 10 }] })), "→ws 10")
  assert.equal(L.shortLabel(b({ dsp: "focus", args: [{ direction: "left" }] })), "focus")
  assert.equal(L.shortLabel(b({ dsp: "layout", args: ["togglesplit"] })), "split")
  assert.equal(L.shortLabel(b({ dsp: "submap", args: ["resize"] })), "↪resize")
  assert.equal(L.shortLabel(b({ dsp: "window.close", args: [] })), "close")
  assert.equal(L.shortLabel(b({ dsp: "window.cycle_next", args: [] })), "cycle n…")
  assert.equal(L.shortLabel(b({ __function: "h.lua:1" })), "fn")
  assert.equal(L.shortLabel(b({ raw: "hl.dsp.exit()" })), "lua")
  assert.equal(L.shortLabel(b(null)), "?")
})

test("a short description wins", () => {
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["kitty"] }, "Term")), "Term")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["kitty"] }, "A terminal emulator")), "kitty")
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test tests/js/`
Expected: FAIL — `ENOENT` for `model.js` and `labels.js`.

- [ ] **Step 3: Implement**

`quickshell/hyprkbm/lib/model.js`:

```js
.pragma library
.import "keys.js" as Keys
.import "catalogue.js" as Catalogue

// The panel's staged keybinds.json, and what Hyprland would end up with if it
// were applied: hand-written binds, minus the ones overridden or unbound,
// plus hyprKBM's own. A twin of model.merge in Python, which stays the
// authority -- hyprkbm-apply validates everything again.
//
// Nothing here mutates its input. The store assigns each result to a
// `property var`, and an object changed in place would never repaint.

var FLAG_NAMES = ["repeating", "locked", "release", "long_press", "non_consuming",
                  "transparent", "ignore_mods"]

function emptyModel() { return { version: 1, submaps: [], binds: [], unbinds: [] } }

function clone(v) { return JSON.parse(JSON.stringify(v)) }

function normalise(model) {
    var m = clone(model || emptyModel())
    m.version = m.version === undefined ? 1 : m.version
    m.submaps = Array.isArray(m.submaps) ? m.submaps : []
    m.binds = Array.isArray(m.binds) ? m.binds : []
    m.unbinds = Array.isArray(m.unbinds) ? m.unbinds : []
    return m
}

function matches(h, target) {
    return h.combo !== null && h.combo === Keys.idOf(target.keys)
        && h.submap === (target.submap || "") && h.fingerprint === target.fingerprint
}

function handBind(h) {
    var c = Keys.parse(h.keys)
    return {
        uid: h.uid, source: "hand", keys: h.keys, combo: h.combo,
        mods: c === null ? [] : c.mods, key: c === null ? h.keys : c.key,
        submap: h.submap, where: h.where, id: null, hand: h,
        description: h.description || "", describe: h.describe, dispatcher: h.dispatcher,
        reproducible: h.reproducible, allowConflict: false, action: null, flags: {}
    }
}

function ownBind(b, catalogue, replaced) {
    var c = Keys.parse(b.keys)
    var valid = Catalogue.actionErrors(b.action, catalogue).length === 0
    return {
        uid: "k:" + b.id, source: replaced === null ? "hyprkbm" : "override",
        keys: b.keys, combo: c === null ? null : Keys.comboId(c.mods, c.key),
        mods: c === null ? [] : c.mods, key: c === null ? b.keys : c.key,
        submap: b.submap || "", where: b.id, id: b.id, hand: replaced,
        description: b.description || "", describe: Catalogue.describeAction(b.action, catalogue),
        dispatcher: valid ? Catalogue.toDispatcher(b.action, catalogue) : null,
        reproducible: true, allowConflict: b.allowConflict === true,
        action: b.action, flags: b.flags || {}
    }
}

function conflicts(binds) {
    var groups = {}
    var order = []
    binds.forEach(function (b) {
        if (b.combo === null || b.allowConflict) return
        var k = b.submap + "\u0000" + b.combo
        if (!groups.hasOwnProperty(k)) { groups[k] = []; order.push(k) }
        groups[k].push(b)
    })
    return order.map(function (k) { return groups[k] }).filter(function (g) { return g.length > 1 })
}

function merge(hand, model, catalogue) {
    model = normalise(model)
    var superseded = {}
    var removed = []
    var stale = []

    function supersede(target) {
        var hits = []
        hand.forEach(function (h, i) { if (matches(h, target)) { hits.push(i); superseded[i] = true } })
        return hits
    }

    model.unbinds.forEach(function (u) {
        var hits = supersede(u)
        if (hits.length === 0)
            stale.push({ kind: "unbind", id: null, keys: u.keys,
                         message: "The bind on " + u.keys + " this removes is no longer in hyprland.lua; the unbind does nothing." })
        hits.forEach(function (i) { removed.push({ uid: hand[i].uid, hand: hand[i] }) })
    })

    var own = model.binds.map(function (b) {
        var replaced = null
        if (b.replaces) {
            var hits = supersede(b.replaces)
            if (hits.length > 0) replaced = hand[hits[0]]
            else stale.push({ kind: "bind", id: b.id, keys: b.keys,
                              message: "The hyprland.lua bind this replaced is gone; it is now an ordinary bind." })
        }
        return ownBind(b, catalogue, replaced)
    })

    var binds = []
    hand.forEach(function (h, i) { if (!superseded[i]) binds.push(handBind(h)) })
    binds = binds.concat(own)
    return { binds: binds, removed: removed, stale: stale, conflicts: conflicts(binds) }
}

function newId(model) {
    var used = {}
    normalise(model).binds.forEach(function (b) { used[b.id] = true })
    var n = 1
    while (used["b" + n]) n++
    return "b" + n
}

// Optional fields are left out rather than written empty, so keybinds.json
// stays the file a person would have written.
function tidy(b) {
    var out = { id: b.id, keys: b.keys }
    if (b.submap) out.submap = b.submap
    out.action = b.action
    if (b.description) out.description = b.description
    var flags = {}
    var any = false
    Object.keys(b.flags || {}).forEach(function (f) { if (b.flags[f] === true) { flags[f] = true; any = true } })
    if (any) out.flags = flags
    if (b.allowConflict === true) out.allowConflict = true
    if (b.replaces) out.replaces = b.replaces
    return out
}

function addBind(model, fields) {
    var m = normalise(model)
    var b = clone(fields)
    b.id = newId(m)
    m.binds.push(tidy(b))
    return m
}

function updateBind(model, id, fields) {
    var m = normalise(model)
    m.binds = m.binds.map(function (b) {
        if (b.id !== id) return b
        var next = clone(b)
        Object.keys(fields).forEach(function (k) { next[k] = clone(fields[k]) })
        return tidy(next)
    })
    return m
}

function removeBind(model, id) {
    var m = normalise(model)
    m.binds = m.binds.filter(function (b) { return b.id !== id })
    return m
}

function targetOf(h) { return { keys: h.keys, submap: h.submap, fingerprint: h.fingerprint } }

function unbindHand(model, h) {
    var m = normalise(model)
    var present = m.unbinds.some(function (u) { return matches(h, u) })
    if (!present) m.unbinds.push(targetOf(h))
    return m
}

function restoreHand(model, h) {
    var m = normalise(model)
    m.unbinds = m.unbinds.filter(function (u) { return !matches(h, u) })
    return m
}

function overrideHand(model, h, fields) {
    var f = clone(fields)
    f.replaces = targetOf(h)
    return addBind(model, f)
}

function addSubmap(model, name, reset) {
    var m = normalise(model)
    m.submaps.push({ name: name, reset: reset })
    return m
}

function submapNames(hand, handSubmaps, model) {
    var seen = {}
    var m = normalise(model)
    ;(handSubmaps || []).forEach(function (s) { seen[s.name] = true })
    m.submaps.forEach(function (s) { seen[s.name] = true })
    hand.forEach(function (h) { if (h.submap) seen[h.submap] = true })
    m.binds.forEach(function (b) { if (b.submap) seen[b.submap] = true })
    return [""].concat(Object.keys(seen).sort())
}

// hl.unbind drops a combo in every submap, so replacing one hand bind means
// re-creating every other hand bind on its keys -- and a Lua function cannot
// be re-created. The same rule hyprkbm-apply enforces, given early.
function overrideBlocker(hand, target) {
    for (var i = 0; i < hand.length; i++) {
        var h = hand[i]
        if (h === target || h.uid === target.uid) continue
        if (h.combo !== null && h.combo === target.combo && !h.reproducible) return h.where
    }
    return null
}

function summary(saved, model) {
    var a = normalise(saved)
    var b = normalise(model)
    var before = {}
    a.binds.forEach(function (x) { before[x.id] = JSON.stringify(x) })
    var after = {}
    b.binds.forEach(function (x) { after[x.id] = JSON.stringify(x) })
    var out = { added: 0, changed: 0, removed: 0, unbound: 0, restored: 0,
                submaps: b.submaps.length - a.submaps.length }
    Object.keys(after).forEach(function (id) {
        if (!before.hasOwnProperty(id)) out.added++
        else if (before[id] !== after[id]) out.changed++
    })
    Object.keys(before).forEach(function (id) { if (!after.hasOwnProperty(id)) out.removed++ })
    var ua = a.unbinds.map(function (u) { return JSON.stringify(u) })
    var ub = b.unbinds.map(function (u) { return JSON.stringify(u) })
    out.unbound = ub.filter(function (u) { return ua.indexOf(u) < 0 }).length
    out.restored = ua.filter(function (u) { return ub.indexOf(u) < 0 }).length
    return out
}
```

`quickshell/hyprkbm/lib/labels.js`:

```js
.pragma library

// The few characters a keycap has room for: what the key does under the held
// modifiers. A description wins when it fits, since the user chose it.

var MAX = 8

function clip(text) {
    text = String(text)
    return text.length > MAX ? text.slice(0, MAX - 1) + "…" : text
}

function shortLabel(bind) {
    if (bind.description && bind.description.length <= MAX) return bind.description
    var d = bind.dispatcher
    if (!d) return "?"
    if (d.__function !== undefined) return "fn"
    if (d.raw !== undefined) return "lua"
    if (d.dsp === undefined) return "?"
    var args = d.args || []
    var first = args[0]
    if (d.dsp === "exec_cmd" && typeof first === "string") {
        var word = first.trim().split(/\s+/)[0] || ""
        return clip(word.split("/").pop())
    }
    if ((d.dsp === "focus" || d.dsp === "window.move") && first !== null
            && typeof first === "object" && first.workspace !== undefined)
        return (d.dsp === "focus" ? "ws " : "→ws ") + first.workspace
    if (d.dsp === "layout" && typeof first === "string") return clip(first.replace(/^toggle/, ""))
    if (d.dsp === "submap" && typeof first === "string") return clip("↪" + first)
    return clip(d.dsp.split(".").pop().replace(/_/g, " "))
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add quickshell/hyprkbm/lib/model.js quickshell/hyprkbm/lib/labels.js tests/js/model.test.mjs tests/js/labels.test.mjs
git commit -m "feat: add the panel's model: merge, conflicts, edits and keycap labels

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: JS search, keymap and diff

**Files:**
- Create: `quickshell/hyprkbm/lib/search.js`, `quickshell/hyprkbm/lib/keymap.js`, `quickshell/hyprkbm/lib/diff.js`
- Test: `tests/js/search.test.mjs`, `tests/js/keymap.test.mjs`, `tests/js/diff.test.mjs`

**Interfaces:**
- Consumes: `keys.js`; merged binds from `model.merge`.
- Produces (`search.js`): `TAGS`, `parseQuery(text) -> {words, tags, empty}`, `matches(bind, query) -> bool`, `filter(binds, query) -> bind[]`.
- Produces (`keymap.js`): `MOUSE` (fixed extra keys), `keyStates(binds, submap, mods) -> {[keyId]: {binds, state: "bound"|"conflict"}}`, `bindsOn(binds, submap, mods, keyId) -> bind[]`, `matchingKeys(binds, submap, query) -> {[keyId]: true} | null` (null when the query is empty), `extraKeys(binds) -> [{id, label}]`, `unplaced(binds, submap, known) -> bind[]` (`known` is a `{[keyId]: true}` set), `conflictTargets(conflicts) -> [{submap, mods, key}]`.
- Produces (`diff.js`): `lineDiff(a, b) -> [{op: " " | "+" | "-", text}]`, `counts(lines) -> {added, removed}`.

- [ ] **Step 1: Write the failing tests**

`tests/js/search.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const S = load("search")
const bind = (o) => Object.assign({ keys: "SUPER + F", mods: ["SUPER"], key: "F", submap: "", source: "hand",
  where: "hyprland.lua:1", describe: "Run a command: firefox", description: "",
  dispatcher: { dsp: "exec_cmd", args: ["firefox"] } }, o)

test("queries split into words and known tags", () => {
  assert.deepEqual(plain(S.parseQuery("  mod:Shift exec:fire foo nope:x ")),
    { words: ["foo", "nope:x"], tags: { mod: ["shift"], exec: ["fire"] }, empty: false })
  assert.equal(S.parseQuery("   ").empty, true)
})

test("words match keys, descriptions and actions", () => {
  assert.ok(S.matches(bind({}), S.parseQuery("fire")))
  assert.ok(S.matches(bind({ description: "Browser" }), S.parseQuery("brow")))
  assert.ok(!S.matches(bind({}), S.parseQuery("kitty")))
  assert.ok(S.matches(bind({}), S.parseQuery("")))
})

test("tags narrow", () => {
  assert.ok(S.matches(bind({}), S.parseQuery("mod:win")))
  assert.ok(!S.matches(bind({}), S.parseQuery("mod:shift")))
  assert.ok(S.matches(bind({}), S.parseQuery("key:f exec:fire")))
  assert.ok(!S.matches(bind({ dispatcher: { dsp: "window.close", args: [] } }), S.parseQuery("exec:fire")))
  assert.ok(S.matches(bind({}), S.parseQuery("submap:global")))
  assert.ok(S.matches(bind({ submap: "resize" }), S.parseQuery("submap:res")))
  assert.ok(S.matches(bind({ source: "override" }), S.parseQuery("src:override")))
  assert.ok(S.matches(bind({}), S.parseQuery("src:lua")))
  assert.ok(!S.matches(bind({ source: "hyprkbm" }), S.parseQuery("src:lua")))
  assert.equal(S.filter([bind({}), bind({ key: "Q", keys: "SUPER + Q" })], S.parseQuery("key:q")).length, 1)
})
```

`tests/js/keymap.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const K = load("keymap")
const S = load("search")
function bind(uid, keys, mods, key, extra) {
  return Object.assign({ uid, keys, combo: mods.concat([key.toLowerCase()]).join("+"), mods, key,
    submap: "", allowConflict: false, describe: "", description: "", source: "hand", where: "", dispatcher: null }, extra || {})
}
const BINDS = [
  bind("a", "SUPER + F", ["SUPER"], "F"),
  bind("b", "SUPER + F", ["SUPER"], "F"),
  bind("c", "SUPER + Q", ["SUPER"], "Q"),
  bind("d", "SUPER + SHIFT + Q", ["SUPER", "SHIFT"], "Q"),
  bind("e", "XF86AudioMute", [], "XF86AudioMute"),
  bind("f", "SUPER + mouse:272", ["SUPER"], "mouse:272"),
  bind("g", "right", [], "right", { submap: "resize" }),
  bind("h", "SUPER + weird_key", ["SUPER"], "weird_key")
]

test("key states for the held modifiers in the submap", () => {
  const s = plain(K.keyStates(BINDS, "", ["SUPER"]))
  assert.deepEqual(Object.keys(s).sort(), ["f", "mouse:272", "q", "weird_key"])
  assert.equal(s.f.state, "conflict")
  assert.equal(s.q.state, "bound")
  assert.deepEqual(s.q.binds.map(b => b.uid), ["c"])
  assert.deepEqual(Object.keys(plain(K.keyStates(BINDS, "resize", []))), ["right"])
})

test("an allowed conflict is just bound", () => {
  const allowed = BINDS.map(b => b.uid === "b" ? Object.assign({}, b, { allowConflict: true }) : b)
  assert.equal(K.keyStates(allowed, "", ["SUPER"]).f.state, "bound")
})

test("binds on one key", () => {
  assert.deepEqual(plain(K.bindsOn(BINDS, "", ["SUPER", "SHIFT"], "q")).map(b => b.uid), ["d"])
  assert.deepEqual(plain(K.bindsOn(BINDS, "", ["SUPER"], "")), [])
})

test("search lights keys under any modifiers", () => {
  assert.equal(K.matchingKeys(BINDS, "", S.parseQuery("")), null)
  assert.deepEqual(plain(K.matchingKeys(BINDS, "", S.parseQuery("key:q"))), { q: true })
})

test("extra keys: the mouse, then media keys the config uses", () => {
  const ids = plain(K.extraKeys(BINDS)).map(k => k.id)
  assert.deepEqual(ids, ["mouse:272", "mouse:273", "mouse:274", "mouse_up", "mouse_down", "XF86AudioMute"])
  assert.equal(plain(K.extraKeys(BINDS))[5].label, "Mute")
})

test("unplaced binds are those no keycap shows", () => {
  const known = { f: true, q: true, xf86audiomute: true, "mouse:272": true }
  assert.deepEqual(plain(K.unplaced(BINDS, "", known)).map(b => b.uid), ["h"])
  const broken = [bind("x", "???", [], "???", { combo: null })]
  assert.deepEqual(plain(K.unplaced(broken, "", known)).map(b => b.uid), ["x"])
})

test("conflict targets say where to look", () => {
  const groups = [[BINDS[0], BINDS[1]]]
  assert.deepEqual(plain(K.conflictTargets(groups)), [{ submap: "", mods: ["SUPER"], key: "f" }])
})
```

`tests/js/diff.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const D = load("diff")

test("a line diff keeps, adds and removes", () => {
  const lines = plain(D.lineDiff("a\nb\nc\n", "a\nc\nd\n"))
  assert.deepEqual(lines, [
    { op: " ", text: "a" }, { op: "-", text: "b" }, { op: " ", text: "c" }, { op: "+", text: "d" }
  ])
  assert.deepEqual(plain(D.counts(lines)), { added: 1, removed: 1 })
})

test("from nothing, everything is added", () => {
  assert.deepEqual(plain(D.lineDiff("", "x\ny")), [{ op: "+", text: "x" }, { op: "+", text: "y" }])
  assert.deepEqual(plain(D.lineDiff("x", "x")), [{ op: " ", text: "x" }])
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test tests/js/`
Expected: FAIL — `ENOENT` for the three libraries.

- [ ] **Step 3: Implement**

`quickshell/hyprkbm/lib/search.js`:

```js
.pragma library
.import "keys.js" as Keys

// The header's search: plain words match a bind's keys, action and
// description; tags narrow. `src:lua` means binds from hyprland.lua.

var TAGS = ["mod", "key", "exec", "desc", "submap", "src"]

function parseQuery(text) {
    var words = []
    var tags = {}
    String(text).split(/\s+/).forEach(function (token) {
        if (token === "") return
        var m = /^(\w+):(.+)$/.exec(token)
        if (m !== null && TAGS.indexOf(m[1].toLowerCase()) >= 0) {
            var tag = m[1].toLowerCase()
            if (!tags.hasOwnProperty(tag)) tags[tag] = []
            tags[tag].push(m[2].toLowerCase())
        } else words.push(token.toLowerCase())
    })
    return { words: words, tags: tags, empty: words.length === 0 && Object.keys(tags).length === 0 }
}

function command(bind) {
    var d = bind.dispatcher
    return d && d.dsp === "exec_cmd" && typeof (d.args || [])[0] === "string" ? d.args[0].toLowerCase() : null
}

function every(list, fn) {
    for (var i = 0; i < list.length; i++) if (!fn(list[i])) return false
    return true
}

function matches(bind, query) {
    if (query.empty) return true
    var hay = [bind.keys, bind.describe, bind.description, bind.where].join(" ").toLowerCase()
    if (!every(query.words, function (w) { return hay.indexOf(w) >= 0 })) return false
    var t = query.tags
    if (t.mod && !every(t.mod, function (m) {
        var canonical = Keys.MODIFIERS[m.toUpperCase()] || m.toUpperCase()
        return bind.mods.indexOf(canonical) >= 0
    })) return false
    if (t.key && !every(t.key, function (k) { return String(bind.key).toLowerCase().indexOf(k) >= 0 })) return false
    if (t.exec && !every(t.exec, function (e) { var c = command(bind); return c !== null && c.indexOf(e) >= 0 })) return false
    if (t.desc && !every(t.desc, function (d) { return bind.description.toLowerCase().indexOf(d) >= 0 })) return false
    if (t.submap && !every(t.submap, function (s) {
        return s === "global" ? bind.submap === "" : bind.submap.toLowerCase().indexOf(s) >= 0
    })) return false
    if (t.src && !every(t.src, function (s) {
        return s === "lua" || s === "hand" ? bind.source === "hand" : bind.source === s
    })) return false
    return true
}

function filter(binds, query) {
    return binds.filter(function (b) { return matches(b, query) })
}
```

`quickshell/hyprkbm/lib/keymap.js`:

```js
.pragma library
.import "keys.js" as Keys
.import "search.js" as Search

// Which keycap shows which binds. A key's id is its keysym in lower case, as
// keys.keyId gives it, so "Return", "return" and an alias all land together.

var MOUSE = [
    { id: "mouse:272", label: "L" }, { id: "mouse:273", label: "R" },
    { id: "mouse:274", label: "M" }, { id: "mouse_up", label: "⇡" },
    { id: "mouse_down", label: "⇣" }
]

function sameMods(a, b) {
    return Keys.sortMods(a).join("+") === Keys.sortMods(b).join("+")
}

function keyStates(binds, submap, mods) {
    var out = {}
    binds.forEach(function (b) {
        if (b.submap !== submap || b.combo === null || !sameMods(b.mods, mods)) return
        var id = Keys.keyId(b.key)
        if (!out.hasOwnProperty(id)) out[id] = { binds: [], state: "bound" }
        out[id].binds.push(b)
    })
    Object.keys(out).forEach(function (id) {
        var live = out[id].binds.filter(function (b) { return !b.allowConflict })
        if (live.length > 1) out[id].state = "conflict"
    })
    return out
}

function bindsOn(binds, submap, mods, keyId) {
    if (keyId === "") return []
    return binds.filter(function (b) {
        return b.submap === submap && b.combo !== null && sameMods(b.mods, mods) && Keys.keyId(b.key) === keyId
    })
}

function matchingKeys(binds, submap, query) {
    if (query.empty) return null
    var out = {}
    binds.forEach(function (b) {
        if (b.submap === submap && b.combo !== null && Search.matches(b, query)) out[Keys.keyId(b.key)] = true
    })
    return out
}

function extraKeys(binds) {
    var seen = {}
    var media = []
    binds.forEach(function (b) {
        if (b.combo === null || !/^xf86/i.test(b.key)) return
        var id = Keys.keyId(b.key)
        if (seen[id]) return
        seen[id] = true
        media.push({ id: b.key, label: b.key.replace(/^XF86(Audio|MonBrightness)?/i, "") })
    })
    media.sort(function (x, y) { return x.id < y.id ? -1 : x.id > y.id ? 1 : 0 })
    return MOUSE.concat(media)
}

function unplaced(binds, submap, known) {
    return binds.filter(function (b) {
        return b.submap === submap && (b.combo === null || !known[Keys.keyId(b.key)])
    })
}

function conflictTargets(conflicts) {
    return conflicts.map(function (group) {
        return { submap: group[0].submap, mods: group[0].mods, key: Keys.keyId(group[0].key) }
    })
}
```

`quickshell/hyprkbm/lib/diff.js`:

```js
.pragma library

// A line diff for the review dialog: the generated keybinds.lua before and
// after. The files are a few hundred lines at most, so the plain
// longest-common-subsequence table is fast enough and easy to trust.

function lines(text) {
    if (text === "") return []
    var out = String(text).split("\n")
    if (out[out.length - 1] === "") out.pop()
    return out
}

function lineDiff(before, after) {
    var a = lines(before)
    var b = lines(after)
    var n = a.length
    var m = b.length
    var table = []
    for (var i = 0; i <= n; i++) { table.push(new Array(m + 1).fill(0)) }
    for (var x = n - 1; x >= 0; x--)
        for (var y = m - 1; y >= 0; y--)
            table[x][y] = a[x] === b[y] ? table[x + 1][y + 1] + 1 : Math.max(table[x + 1][y], table[x][y + 1])
    var out = []
    var p = 0
    var q = 0
    while (p < n && q < m) {
        if (a[p] === b[q]) { out.push({ op: " ", text: a[p] }); p++; q++ }
        else if (table[p + 1][q] >= table[p][q + 1]) { out.push({ op: "-", text: a[p] }); p++ }
        else { out.push({ op: "+", text: b[q] }); q++ }
    }
    while (p < n) { out.push({ op: "-", text: a[p] }); p++ }
    while (q < m) { out.push({ op: "+", text: b[q] }); q++ }
    return out
}

function counts(diff) {
    var out = { added: 0, removed: 0 }
    diff.forEach(function (l) {
        if (l.op === "+") out.added++
        else if (l.op === "-") out.removed++
    })
    return out
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test tests/js/`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add quickshell/hyprkbm/lib/search.js quickshell/hyprkbm/lib/keymap.js quickshell/hyprkbm/lib/diff.js tests/js/search.test.mjs tests/js/keymap.test.mjs tests/js/diff.test.mjs
git commit -m "feat: add the panel's search, key map and line diff

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Panel scaffold: theme, store, window and launcher

**Files:**
- Create (copied): `quickshell/hyprkbm/config/{Colors,Theme,Radius,Spacing,Typography}.qml`, `quickshell/hyprkbm/config/qmldir`, `quickshell/hyprkbm/presets/{fuji,iris,paper}.json`, `quickshell/hyprkbm/presets/README.md`, `quickshell/hyprkbm/components/{Action,Select,Toggle,Field,ThemePopup,ColourPicker,ColourInput}.qml`, `tests/test_theme_presets.py`
- Create: `quickshell/hyprkbm/state/Store.qml`, `quickshell/hyprkbm/state/qmldir`, `quickshell/hyprkbm/shell.qml`, `share/applications/hyprkbm.desktop`, `tests/test_panel_qml.py`
- Modify: `bin/hyprkbm` (no arguments opens the panel), `install.sh` (desktop entry), `tests/conftest.py` (a `qs` stub), `tests/test_cli.py`, `tests/test_install.py`, `.github/workflows/ci.yml` (QML job)

**Interfaces:**
- Consumes: `hyprkbm --state`, `hyprkbm-apply` and `--preview`, `hyprkbm --backup`, `hyprkbm --export md`, `hyprkbm --set-layout`; every `lib/*.js`.
- Produces (`Store`, a singleton): properties `binDir, loading, loadError, doc, saved, model, readOnly, dirty, catalogue, hand, merged, submaps, submap, toggledMods, heldMods, mods, selectedKey, query, parsedQuery, layoutName, layout, keyStates, matching, listed, removedHere, unplaced, extras, draft, status, failed, errors, busy, preview, backup`; functions `reload(), hold(mod), release(mod), toggleMod(mod), setMods(list), selectKey(id), moveSelection(dir), findBind(uid), edit(uid), newBind(keys), newBindOnSelected(), patchDraft(fields), patchArg(name, value), setActionKind(kind), draftProblems(), saveDraft(), cancelEdit(), deleteBind(uid), deleteDraft(), restoreHand(hand), keepBoth(uid), addSubmap(name, reset), nextConflict(), discard(), apply(), requestPreview(), loadBackup(name), restoreBackup(), exportTo(path), setLayout(name), startWatcher(), snapshot()`; signal `applied()`.
- Produces (`bin/hyprkbm`): no arguments → `cmd_panel(paths)`.

- [ ] **Step 1: Copy the theme layer and controls from hypr-displays**

```bash
SRC=/home/kakaouskias/Projects/phos/hypr-displays
[ -d "$SRC/.git" ] || { git clone -q https://github.com/phos-org/hypr-displays.git /tmp/hypr-displays-src && SRC=/tmp/hypr-displays-src; }
mkdir -p quickshell/hyprkbm/config quickshell/hyprkbm/presets quickshell/hyprkbm/components quickshell/hyprkbm/state
for f in config/Colors.qml config/Theme.qml config/Radius.qml config/Spacing.qml config/Typography.qml config/qmldir \
         presets/fuji.json presets/iris.json presets/paper.json presets/README.md \
         components/Action.qml components/Select.qml components/Toggle.qml components/Field.qml \
         components/ThemePopup.qml components/ColourPicker.qml components/ColourInput.qml; do
    git -C "$SRC" show d5c49e3:quickshell/displays/$f > quickshell/hyprkbm/$f
done
git -C "$SRC" show d5c49e3:tests/test_theme_presets.py > tests/test_theme_presets.py
sed -i 's/hypr-displays/hyprkbm/g' quickshell/hyprkbm/config/*.qml quickshell/hyprkbm/presets/README.md
sed -i 's/Nothing here writes a display setting/Nothing here writes a keybind/' quickshell/hyprkbm/config/Theme.qml
sed -i 's#"quickshell", "displays"#"quickshell", "hyprkbm"#; s#quickshell/displays#quickshell/hyprkbm#g' tests/test_theme_presets.py
grep -rn "hypr-displays\|Displays\|displays" quickshell/hyprkbm tests/test_theme_presets.py
```

Expected: the final `grep` prints nothing, or only lines that mention displays in prose you then reword (for example a comment in `Theme.qml` about "a display setting" or the presets README describing "the panel"). Reword those by hand so they describe hyprKBM. Then:

Run: `python3 -m pytest tests/test_theme_presets.py -q`
Expected: pass. If a test there names a hypr-displays component that does not exist here (for example `Inspector.qml`), delete only that test function and note it in your report.

- [ ] **Step 2: Write the failing tests**

Add a `qs` stub to `tests/conftest.py`'s `stubs` fixture by changing its loop to:

```python
    for name, body in (("hyprctl", HYPRCTL), ("notify-send", LOGGER), ("systemctl", LOGGER),
                       ("qs", LOGGER)):
```

Replace `test_no_arguments_explains_the_panel_is_missing` in `tests/test_cli.py` with:

```python
def wait_for(stubs, program):
    import time
    for _ in range(50):
        if any(c[0] == program for c in stubs.calls()):
            return
        time.sleep(0.05)


def test_no_arguments_opens_the_panel(home_env, stubs):
    res = run(home_env)

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    qs = [c for c in stubs.calls() if c[0] == "qs"][0]
    assert qs[1] == "-p" and qs[2].endswith("quickshell/hyprkbm") and qs[3] == "-d"


def test_an_open_panel_is_focused_not_opened_again(home_env, stubs):
    stubs.respond(**{"-j": ['[{"class": "org.quickshell", "title": "Keybinds"}]']})

    res = run(home_env)

    assert res.returncode == 0, res.stderr
    assert ["hyprctl", "dispatch", "focuswindow", "title:^Keybinds$"] in stubs.calls()
    assert not any(c[0] == "qs" for c in stubs.calls())


def test_no_quickshell_is_explained(home_env, stubs):
    (stubs.root / "qs").unlink()
    env = dict(home_env, PATH="%s:/usr/bin:/bin" % stubs.root)
    if any(os.access(os.path.join(d, "qs"), os.X_OK) for d in ("/usr/bin", "/bin")):
        import pytest
        pytest.skip("a real qs is installed in /usr/bin; cannot hide it")
    res = subprocess.run([sys.executable, str(HYPRKBM)], capture_output=True, text=True, env=env)

    assert res.returncode == 1
    assert "Quickshell" in res.stderr
```

Append to `tests/test_install.py`'s `links()` dictionary:

```python
        home / ".local/share/applications/hyprkbm.desktop": "share/applications/hyprkbm.desktop",
```

`tests/test_panel_qml.py`:

```python
"""Source-level checks on the panel's QML.

There is no QML test harness, so these read the source narrowly, for the
rules that keep the panel honest. The logic itself is tested in tests/js/;
qmllint in CI checks the QML parses and resolves.
"""
import re
from pathlib import Path

PANEL = Path(__file__).resolve().parents[1] / "quickshell" / "hyprkbm"


def code_only(text):
    return "\n".join(line.split("//")[0] for line in text.split("\n"))


def qml(*parts):
    return code_only((PANEL.joinpath(*parts)).read_text(encoding="utf-8"))


def all_qml():
    return {p.relative_to(PANEL).as_posix(): code_only(p.read_text(encoding="utf-8"))
            for p in PANEL.rglob("*.qml")}


def test_the_panel_writes_keybinds_only_through_hyprkbm_apply():
    # The theme layer in config/ is the one place that writes a file itself
    # (theme.json); everything else goes through a helper.
    for name, source in all_qml().items():
        if name.startswith("config/"):
            continue
        assert "FileView" not in source, name
        assert "setText(" not in source, name
    store = qml("state", "Store.qml")
    assert 'helper("hyprkbm-apply")' in store
    assert '"--preview"' in store


def test_the_store_runs_the_helpers_by_name_or_from_hyprkbm_bin():
    store = qml("state", "Store.qml")
    assert 'envValue("HYPRKBM_BIN")' in store
    assert 'helper("hyprkbm"), "--state"' in store


def test_the_window_is_titled_and_scriptable():
    shell = qml("shell.qml")
    assert re.search(r'title:\s*"Keybinds"', shell)
    assert re.search(r'target:\s*"hyprkbm"', shell)
    # Applying from a script would let a smoke test change a real session.
    assert "Store.apply()" not in shell.split("IpcHandler", 1)[1].split("FocusScope", 1)[0]


def test_no_qml_property_shadows_a_builtin():
    builtins = {"data", "state", "size", "enabled", "visible", "rotation", "palette"}
    for name, source in all_qml().items():
        for prop in re.findall(r"\bproperty\s+\w+\s+(\w+)", source):
            assert prop not in builtins and not prop.startswith("on"), "%s: %s" % (name, prop)
```

Add a QML job to `.github/workflows/ci.yml` under `jobs:` — copy the `qml` job from hypr-displays exactly (`git -C "$SRC" show d5c49e3:.github/workflows/ci.yml`, the job named `qml:` with `container: debian:trixie`), it already lints every `*.qml` under `quickshell/`.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py tests/test_install.py tests/test_panel_qml.py -q`
Expected: failures — the CLI still prints the "panel is not installed" message, the desktop entry is not linked, and `Store.qml` / `shell.qml` do not exist.

- [ ] **Step 4: Implement the launcher, desktop entry and install link**

In `bin/hyprkbm`, add `import shutil` to the imports, then add above `main`:

```python
ROOT = Path(os.path.realpath(__file__)).parents[1]
PANEL = ROOT / "quickshell" / "hyprkbm"
PANEL_CLASS = "org.quickshell"
TITLE = "Keybinds"


def panel_open():
    """Whether the panel already has a window: class as well as title, so a
    terminal that happens to be called Keybinds is not mistaken for it."""
    try:
        res = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True, timeout=5)
        clients = json.loads(res.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False
    return isinstance(clients, list) and any(
        isinstance(c, dict) and c.get("class") == PANEL_CLASS and c.get("title") == TITLE
        for c in clients)


def cmd_panel(paths):
    if shutil.which("qs") is None:
        return fail("Quickshell (qs) is not installed; the panel needs it. "
                    "The command line works without it: see hyprkbm --help")
    if panel_open():
        subprocess.run(["hyprctl", "dispatch", "focuswindow", "title:^%s$" % TITLE],
                       capture_output=True, timeout=5)
        return 0
    # A keybind's PATH does not include ~/.local/bin, so the panel is told
    # where its helpers are rather than left to find them.
    env = dict(os.environ, HYPRKBM_BIN=str(ROOT / "bin"))
    subprocess.Popen(["qs", "-p", str(PANEL), "-d"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return 0
```

In `main`, replace

```python
    if argv in ([], ["--cheatsheet"]):
        return fail("the hyprKBM panel is not installed in this version yet; "
                    "see hyprkbm --help", code=2)
```

with

```python
    if argv == []:
        return cmd_panel(paths)
    if argv == ["--cheatsheet"]:
        return fail("the cheatsheet overlay is not in this version yet; "
                    "hyprkbm --export md writes a cheatsheet as Markdown", code=2)
```

and add to the docstring's first line block: `  hyprkbm                      open the keyboard panel`.

`share/applications/hyprkbm.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Keybinds
GenericName=Keybind manager
Comment=See and change your Hyprland keybinds
Exec=hyprkbm
Icon=input-keyboard
Categories=Settings;
Keywords=hyprland;keybinds;shortcuts;hotkeys;
```

In `install.sh`, add `DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"` under `CONFIG_DIR=`, and add this line to `LINKS`:

```
share/applications/hyprkbm.desktop  $DATA_DIR/applications/hyprkbm.desktop
```

and, in `install()` after the link loop, refresh the launcher cache when the tool exists:

```bash
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database "$DATA_DIR/applications" >/dev/null 2>&1
```

Also add `qs` to the tool check in `install()`: `for tool in hyprctl python3 qs; do`.

- [ ] **Step 5: Write the store, its qmldir and the window**

`quickshell/hyprkbm/state/qmldir`:

```
singleton Store 1.0 Store.qml
```

`quickshell/hyprkbm/state/Store.qml`:

```qml
pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../lib/keys.js" as Keys
import "../lib/model.js" as Model
import "../lib/keymap.js" as Keymap
import "../lib/search.js" as Search
import "../lib/layouts.js" as Layouts
import "../lib/catalogue.js" as Catalogue

// The panel's single source of truth. It never writes keybinds.json or
// keybinds.lua: edits are staged in `model` and leave only through
// hyprkbm-apply, which validates, dry-runs, backs up and can roll back.
//
// Every list here is computed by lib/*.js and reassigned wholesale; nothing is
// mutated in place, because a mutated object never repaints.
QtObject {
    id: root

    // Where the helpers are. Empty means "wherever PATH says"; `hyprkbm`
    // sets HYPRKBM_BIN when it opens the panel, because a keybind's PATH
    // does not include ~/.local/bin.
    readonly property string binDir: envValue("HYPRKBM_BIN")

    property bool loading: true
    property string loadError: ""
    property var doc: null
    property var saved: null
    property var model: null
    readonly property bool readOnly: doc !== null && (doc.model === null || doc.modelError !== null)
    readonly property bool dirty: model !== null && saved !== null
                                  && JSON.stringify(model) !== JSON.stringify(saved)

    readonly property var catalogue: doc ? doc.catalogue : []
    readonly property var hand: doc ? doc.hand : []
    readonly property var merged: Model.merge(hand, model || Model.emptyModel(), catalogue)
    readonly property var submaps: Model.submapNames(hand, doc ? doc.handSubmaps : [], model || Model.emptyModel())

    property string submap: ""
    property var toggledMods: ["SUPER"]
    property var heldMods: []
    // Holding real modifiers shows what they do; letting go shows the chips again.
    readonly property var mods: heldMods.length > 0 ? heldMods : toggledMods
    property string selectedKey: ""
    property string query: ""
    readonly property var parsedQuery: Search.parseQuery(query)
    readonly property string layoutName: doc && doc.settings && doc.settings.layout === "iso" ? "iso" : "ansi"
    readonly property var layout: Layouts.LAYOUTS[layoutName]
    readonly property var keyStates: Keymap.keyStates(merged.binds, submap, mods)
    readonly property var matching: Keymap.matchingKeys(merged.binds, submap, parsedQuery)
    readonly property var extras: Keymap.extraKeys(merged.binds)
    readonly property var listed: parsedQuery.empty
                                  ? Keymap.bindsOn(merged.binds, submap, mods, selectedKey)
                                  : Search.filter(merged.binds, parsedQuery)
    readonly property var removedHere: merged.removed.filter(function (r) {
        return r.hand.submap === root.submap && root.selectedKey !== ""
            && r.hand.combo === Keys.comboId(root.mods, root.selectedKey)
    })
    readonly property var unplaced: Keymap.unplaced(merged.binds, submap, knownKeys())

    property var draft: null
    property string status: ""
    property bool failed: false
    property var errors: []
    property bool busy: false
    property var preview: null
    property var backup: null
    property int conflictIndex: -1

    signal applied()

    Component.onCompleted: reload()

    function envValue(name) {
        var value = Quickshell.env(name)
        return value ? String(value).trim() : ""
    }

    function helper(name) { return binDir ? binDir + "/" + name : name }

    function knownKeys() {
        var known = Layouts.keyIds(layout)
        extras.forEach(function (k) { known[Keys.keyId(k.id)] = true })
        return known
    }

    function report(text, isError) {
        status = text
        failed = isError === true
    }

    // ------------------------------------------------------------ reading

    function reload() {
        loading = true
        stateProc.running = true
    }

    function adopt(parsed) {
        doc = parsed
        saved = parsed.model
        model = parsed.model === null ? null : Model.clone(parsed.model)
        loadError = ""
        if (selectedKey === "") selectedKey = "q"
    }

    // ------------------------------------------------------- the keyboard

    function hold(mod) {
        if (heldMods.indexOf(mod) < 0) heldMods = Keys.sortMods(heldMods.concat([mod]))
    }

    function release(mod) {
        heldMods = heldMods.filter(function (m) { return m !== mod })
    }

    function toggleMod(mod) {
        toggledMods = toggledMods.indexOf(mod) >= 0
                      ? toggledMods.filter(function (m) { return m !== mod })
                      : Keys.sortMods(toggledMods.concat([mod]))
    }

    function setMods(list) { toggledMods = Keys.sortMods(list) }

    function selectKey(id) {
        selectedKey = Keys.keyId(id)
        query = ""
    }

    function moveSelection(dir) {
        selectedKey = Layouts.neighbour(layout, selectedKey === "" ? "q" : selectedKey, dir)
    }

    function nextConflict() {
        var targets = Keymap.conflictTargets(merged.conflicts)
        if (targets.length === 0) return
        conflictIndex = (conflictIndex + 1) % targets.length
        var t = targets[conflictIndex]
        submap = t.submap
        toggledMods = t.mods
        heldMods = []
        selectedKey = t.key
        query = ""
    }

    // ------------------------------------------------------------ editing

    function findBind(uid) {
        for (var i = 0; i < merged.binds.length; i++)
            if (merged.binds[i].uid === uid) return merged.binds[i]
        return null
    }

    function flagsFromOpts(opts) {
        var flags = {}
        Model.FLAG_NAMES.forEach(function (f) { if (opts && opts[f] === true) flags[f] = true })
        return flags
    }

    function edit(uid) {
        var b = findBind(uid)
        if (b === null || readOnly) return
        if (b.source === "hand") {
            var action = Catalogue.actionFromDispatcher(b.dispatcher, catalogue)
            if (action === null) {
                report("The bind at " + b.where + " runs a Lua function; change it in hyprland.lua.", true)
                return
            }
            draft = { id: null, hand: b.hand, keys: b.keys, submap: b.submap, action: action,
                      description: b.description, flags: flagsFromOpts(b.hand.opts), allowConflict: false }
        } else {
            draft = { id: b.id, hand: b.hand, keys: b.keys, submap: b.submap,
                      action: Model.clone(b.action), description: b.description,
                      flags: Model.clone(b.flags), allowConflict: b.allowConflict }
        }
    }

    function newBind(keys) {
        if (readOnly) return
        draft = { id: null, hand: null, keys: keys, submap: submap,
                  action: { kind: "exec_cmd", args: {} }, description: "", flags: {}, allowConflict: false }
    }

    function newBindOnSelected() {
        newBind(selectedKey === "" ? Keys.display(mods, "") : Keys.display(mods, Layouts.keyName(layout, selectedKey)))
    }

    function patchDraft(fields) {
        var next = Model.clone(draft)
        Object.keys(fields).forEach(function (k) { next[k] = fields[k] })
        draft = next
    }

    function patchArg(name, value) {
        var action = Model.clone(draft.action)
        if (!action.args) action.args = {}
        if (value === "" || value === null || value === undefined) delete action.args[name]
        else action.args[name] = value
        patchDraft({ action: action })
    }

    function setActionKind(kind) {
        if (kind === "raw") patchDraft({ action: { kind: "raw", lua: "" } })
        else patchDraft({ action: { kind: kind, args: Catalogue.defaultArgs(Catalogue.entryById(catalogue, kind)) } })
    }

    function draftProblems() {
        if (draft === null) return []
        var out = []
        if (Keys.parse(draft.keys) === null) out.push("Keys: write them like SUPER + SHIFT + F")
        Catalogue.actionErrors(draft.action, catalogue).forEach(function (e) { out.push(e) })
        if (draft.hand !== null && draft.id === null) {
            var blocker = Model.overrideBlocker(hand, draft.hand)
            if (blocker !== null)
                out.push("The bind at " + blocker + " shares these keys and runs a Lua function, which hyprKBM cannot re-create; change it in hyprland.lua instead.")
        }
        return out
    }

    function saveDraft() {
        if (draft === null || draftProblems().length > 0) return
        var fields = { keys: draft.keys.trim(), submap: draft.submap, action: draft.action,
                       description: draft.description, flags: draft.flags, allowConflict: draft.allowConflict }
        if (draft.id !== null) model = Model.updateBind(model, draft.id, fields)
        else if (draft.hand !== null) model = Model.overrideHand(model, draft.hand, fields)
        else model = Model.addBind(model, fields)
        draft = null
        report("Staged. Apply when ready.", false)
    }

    function cancelEdit() { draft = null }

    function deleteBind(uid) {
        var b = findBind(uid)
        if (b === null || readOnly) return
        if (b.source === "hand") {
            var blocker = Model.overrideBlocker(hand, b.hand)
            if (blocker !== null) {
                report("Removing this would re-create the bind at " + blocker + ", which runs a Lua function; change it in hyprland.lua.", true)
                return
            }
            model = Model.unbindHand(model, b.hand)
        } else model = Model.removeBind(model, b.id)
        if (draft !== null && (draft.id === b.id || (draft.hand !== null && b.hand !== null && draft.hand.uid === b.hand.uid)))
            draft = null
    }

    function deleteDraft() {
        if (draft === null) return
        if (draft.id !== null) deleteBind("k:" + draft.id)
        else if (draft.hand !== null) deleteBind(draft.hand.uid)
        draft = null
    }

    function restoreHand(h) { model = Model.restoreHand(model, h) }

    function keepBoth(uid) {
        var b = findBind(uid)
        if (b !== null && b.id !== null) model = Model.updateBind(model, b.id, { allowConflict: true })
    }

    function addSubmap(name, reset) {
        model = Model.addSubmap(model, name, reset)
        submap = name
    }

    function discard() {
        model = Model.clone(saved)
        draft = null
        errors = []
        report("Changes discarded.", false)
    }

    // ----------------------------------------------------------- helpers

    function apply() {
        if (!dirty || busy || readOnly) return
        busy = true
        report("Applying…", false)
        applyProc.stdinEnabled = true
        applyProc.running = true
    }

    function requestPreview() {
        if (model === null) return
        preview = null
        previewProc.stdinEnabled = true
        previewProc.running = true
    }

    function loadBackup(name) {
        backup = null
        backupProc.command = [helper("hyprkbm"), "--backup", name]
        backupProc.running = true
    }

    function restoreBackup() {
        if (backup === null) return
        model = backup.model === null ? Model.emptyModel() : Model.clone(backup.model)
        apply()
    }

    function exportTo(path) {
        exportProc.command = [helper("hyprkbm"), "--export", "md", path]
        exportProc.running = true
    }

    function setLayout(name) {
        layoutProc.command = [helper("hyprkbm"), "--set-layout", name]
        layoutProc.running = true
    }

    function startWatcher() { watcherProc.running = true }

    function parsed(text) {
        try { return JSON.parse(text) } catch (e) { return null }
    }

    function snapshot() {
        return {
            loading: loading, loadError: loadError, readOnly: readOnly, dirty: dirty,
            submap: submap, mods: mods, selectedKey: selectedKey, query: query,
            binds: merged.binds.length, conflicts: merged.conflicts.length, stale: merged.stale.length,
            listed: listed.map(function (b) { return b.uid }),
            draft: draft === null ? null : { id: draft.id, keys: draft.keys, kind: draft.action.kind },
            status: status, errors: errors
        }
    }

    property Process stateProc: Process {
        command: [root.helper("hyprkbm"), "--state"]
        stdout: StdioCollector { id: stateOut }
        stderr: StdioCollector { id: stateErr }
        onExited: function (code) {
            root.loading = false
            var parsedDoc = code === 0 ? root.parsed(stateOut.text) : null
            if (parsedDoc === null) {
                root.loadError = "hyprKBM's state could not be read: "
                    + ((stateErr.text || stateOut.text || "is hyprkbm installed?").trim())
                return
            }
            root.adopt(parsedDoc)
        }
    }

    property Process applyProc: Process {
        command: [root.helper("hyprkbm-apply")]
        stdinEnabled: true
        onStarted: {
            write(JSON.stringify(root.model))
            stdinEnabled = false   // EOF, so the helper's read of stdin returns
        }
        stdout: StdioCollector { id: applyOut }
        stderr: StdioCollector { id: applyErr }
        onExited: function (code) {
            root.busy = false
            var result = root.parsed(applyOut.text)
            if (result === null) {
                root.errors = []
                root.report("hyprkbm-apply failed: " + (applyErr.text || applyOut.text).trim(), true)
                return
            }
            if (result.ok) {
                root.errors = []
                root.report("Applied.", false)
                root.reload()
                root.applied()
                return
            }
            root.errors = result.errors
            var more = result.errors.length > 1 ? " (and " + (result.errors.length - 1) + " more)" : ""
            root.report(result.errors[0].message + more, true)
        }
    }

    property Process previewProc: Process {
        command: [root.helper("hyprkbm-apply"), "--preview"]
        stdinEnabled: true
        onStarted: {
            write(JSON.stringify(root.model))
            stdinEnabled = false
        }
        stdout: StdioCollector { id: previewOut }
        onExited: function (code) {
            root.preview = root.parsed(previewOut.text)
                           || { ok: false, errors: [{ id: null, message: "The preview could not be made." }], lua: "", current: "" }
        }
    }

    property Process backupProc: Process {
        stdout: StdioCollector { id: backupOut }
        onExited: function (code) {
            root.backup = code === 0 ? root.parsed(backupOut.text) : null
            if (root.backup === null) root.report("That backup could not be read.", true)
        }
    }

    property Process exportProc: Process {
        stderr: StdioCollector { id: exportErr }
        onExited: function (code) {
            if (code === 0) root.report("Exported to " + exportProc.command[3] + ".", false)
            else root.report((exportErr.text || "Export failed.").trim(), true)
        }
    }

    property Process layoutProc: Process {
        onExited: function (code) { if (code === 0) root.reload() }
    }

    property Process watcherProc: Process {
        command: ["systemctl", "--user", "start", "hyprkbm-watch.service"]
        onExited: function (code) {
            if (code !== 0) root.report("The watcher could not be started; see systemctl --user status hyprkbm-watch.", true)
            root.reload()
        }
    }
}
```

`quickshell/hyprkbm/shell.qml` (the components it lays out are added in later tasks; this task's version shows the loading state and the raw counts so it runs on its own):

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "config"
import "components"
import "state"
import "lib/qtkeys.js" as QtKeys

ShellRoot {
    // An ordinary window rather than a layer-shell panel: it is a thing you
    // open, move and close, not part of the desktop.
    FloatingWindow {
        id: win
        title: "Keybinds"
        implicitWidth: 1180
        implicitHeight: 760
        minimumSize.width: 980
        minimumSize.height: 620
        color: Colors.bgVoid

        // Scripted inspection, over `qs ipc -p <panel> call hyprkbm <fn>`. It
        // drives the same store the pointer does, and deliberately offers no
        // way to apply: a smoke test must never change a real session.
        IpcHandler {
            target: "hyprkbm"

            function state(): string { return JSON.stringify(Store.snapshot()) }

            function select(key: string, mods: string): string {
                Store.heldMods = []
                Store.setMods(mods === "" ? [] : mods.split("+"))
                Store.selectKey(key)
                return JSON.stringify(Store.snapshot())
            }

            function search(text: string): string {
                Store.query = text
                return JSON.stringify(Store.snapshot())
            }

            function submap(name: string): string {
                Store.submap = name
                return JSON.stringify(Store.snapshot())
            }

            function edit(uid: string): string {
                Store.edit(uid)
                return JSON.stringify(Store.snapshot())
            }

            function reload(): string {
                Store.reload()
                return "reloading"
            }
        }

        FocusScope {
            id: scope
            anchors.fill: parent
            focus: true

            Keys.onPressed: function (event) {
                var mod = QtKeys.modifierFromQtKey(event.key)
                if (mod !== "") { Store.hold(mod); return }
            }
            Keys.onReleased: function (event) {
                var mod = QtKeys.modifierFromQtKey(event.key)
                if (mod !== "") Store.release(mod)
            }
            Keys.onEscapePressed: {
                if (Store.draft !== null) Store.cancelEdit()
                else Qt.quit()
            }

            ColumnLayout {
                id: body
                anchors.fill: parent
                anchors.margins: Spacing.lg
                spacing: Spacing.md

                Text {
                    text: Store.loading ? "Reading your keybinds…"
                        : Store.loadError !== "" ? Store.loadError
                        : Store.merged.binds.length + " binds, " + Store.merged.conflicts.length + " conflicts"
                    color: Store.loadError !== "" ? Colors.statusCritical : Colors.textPrimary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeBody
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors (warnings are reported; read them, and fix any about this task's files that are not the known `id`-in-property-value blind spot described in hypr-displays' CONTRIBUTING).

- [ ] **Step 7: Smoke-test the window on the real desktop**

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d
sleep 2
qs ipc -p quickshell/hyprkbm call hyprkbm state
qs log -p quickshell/hyprkbm | tail -20
qs kill -p quickshell/hyprkbm
```

Expected: `state` prints JSON with `"loading":false`, `"loadError":""` and a `"binds"` count equal to `hyprkbm --status`'s hand-written binds plus hyprKBM binds; the log shows no `ReferenceError`, `TypeError` or `Cannot assign` lines.

- [ ] **Step 8: Commit**

```bash
git add quickshell/hyprkbm tests/test_theme_presets.py tests/test_panel_qml.py tests/test_cli.py tests/test_install.py tests/conftest.py bin/hyprkbm install.sh share/applications .github/workflows/ci.yml
git commit -m "feat: scaffold the panel: theme, store, window and launcher

The theme layer and its controls come from hypr-displays unchanged apart from
names, so the two panels look and theme alike. The store reads everything
from hyprkbm --state and stages edits as a copy of keybinds.json.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The keyboard

**Files:**
- Create: `quickshell/hyprkbm/components/KeyCap.qml`, `KeyBlock.qml`, `Keyboard.qml`, `ModifierBar.qml`, `ExtraKeys.qml`
- Modify: `quickshell/hyprkbm/shell.qml` (lay the keyboard out; arrow keys, Enter), `tests/test_panel_qml.py` (append)

**Interfaces:**
- Consumes: `Store.layout, mods, toggledMods, keyStates, matching, selectedKey, extras, merged`, `Store.toggleMod, selectKey, moveSelection, newBind, newBindOnSelected, edit, listed`; `Keys.keyId, display`; `Labels.shortLabel`.
- Produces: `KeyCap { label, sub, kind ("free"|"bound"|"conflict"|"mod"|"modOn"), selected, dimmed, unit, units; signal clicked() }`; `KeyBlock { rows, unit }`; `Keyboard { readonly unit }`, `ModifierBar`, `ExtraKeys { unit }`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_panel_qml.py`:

```python
def test_the_keyboard_draws_from_the_store_and_lib():
    keyboard = qml("components", "Keyboard.qml")
    assert "Store.layout.main" in keyboard
    assert "Store.layout.nav" in keyboard
    block = qml("components", "KeyBlock.qml")
    assert "Store.keyStates" in block
    assert "Labels.shortLabel" in block
    cap = qml("components", "KeyCap.qml")
    assert "signal clicked()" in cap
    # Lit keys are tinted over the key's surface, never drawn translucent.
    assert "Qt.tint(" in cap


def test_the_window_lays_out_the_keyboard():
    shell = qml("shell.qml")
    for part in ("ModifierBar", "Keyboard", "ExtraKeys"):
        assert re.search(r"^\s*%s\s*\{" % part, shell, re.M), part
    assert "Store.moveSelection(" in shell
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_panel_qml.py -q`
Expected: FAIL — `FileNotFoundError` for `Keyboard.qml`.

- [ ] **Step 3: Implement the four components**

`quickshell/hyprkbm/components/KeyCap.qml`:

```qml
import QtQuick
import "../config"

// One key on the on-screen keyboard. It draws a state and reports clicks;
// what the state means is decided in lib/keymap.js.
Rectangle {
    id: root
    property string label: ""
    property string sub: ""
    property string kind: "free"
    property bool selected: false
    property bool dimmed: false
    property real unit: 40
    property real units: 1
    signal clicked()

    // The accent laid over the key's own surface rather than the accent at
    // reduced opacity: the pane behind is darker than a key, so translucency
    // reads as a hole rather than a lit key.
    function lit(accent, amount) {
        return Qt.tint(Colors.bgSurface, Qt.rgba(accent.r, accent.g, accent.b, amount))
    }

    width: unit * units - 4
    height: unit - 4
    radius: Radius.sm
    opacity: dimmed ? 0.35 : 1
    color: kind === "conflict" ? lit(Colors.statusCritical, 0.45)
         : kind === "bound" ? lit(Colors.accentPrimary, 0.3)
         : kind === "modOn" ? lit(Colors.accentSecondary, 0.18)
         : kind === "mod" ? Colors.bgSurfaceAlt
         : Colors.bgSurface
    border.width: selected ? 2 : 1
    border.color: selected ? Colors.textPrimary
                : kind === "conflict" ? Colors.statusCritical
                : kind === "bound" ? lit(Colors.accentPrimary, 0.6)
                : kind === "mod" || kind === "modOn" ? Colors.accentSecondary
                : Colors.borderSubtle

    Behavior on color { ColorAnimation { duration: 110 } }

    Column {
        anchors.centerIn: parent
        width: parent.width - 4
        spacing: 0

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.label
            color: root.kind === "free" ? Colors.textTertiary
                 : root.kind === "mod" || root.kind === "modOn" ? Colors.accentSecondary
                 : Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Math.max(9, Math.round(root.unit * 0.27))
            elide: Text.ElideRight
        }

        Text {
            visible: root.sub !== ""
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.sub
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Math.max(7, Math.round(root.unit * 0.19))
            elide: Text.ElideRight
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
```

`quickshell/hyprkbm/components/KeyBlock.qml` (its own file rather than an inline component: an inline component cannot see the ids of the file around it):

```qml
import QtQuick
import "../state"
import "../lib/keys.js" as Keys
import "../lib/labels.js" as Labels

// One block of keyboard rows -- the main block or the navigation cluster.
// A key is lit by what it does under Store.mods in Store.submap.
Column {
    id: root
    property var rows: []
    property real unit: 40

    function info(spec) {
        return spec.id === undefined ? undefined : Store.keyStates[Keys.keyId(spec.id)]
    }

    function kindOf(spec) {
        if (spec.mod !== undefined) return Store.mods.indexOf(spec.mod) >= 0 ? "modOn" : "mod"
        var i = info(spec)
        return i === undefined ? "free" : i.state
    }

    function subOf(spec) {
        var i = info(spec)
        if (i === undefined || spec.cont) return ""
        return i.binds.length > 1 ? i.binds.length + " binds" : Labels.shortLabel(i.binds[0])
    }

    function press(spec) {
        if (spec.mod !== undefined) Store.toggleMod(spec.mod)
        else Store.selectKey(spec.id)
    }

    Repeater {
        model: root.rows
        delegate: Row {
            id: rowItem
            required property var modelData
            height: root.unit
            Repeater {
                model: rowItem.modelData
                delegate: KeyCap {
                    required property var modelData
                    unit: root.unit
                    units: modelData.w
                    // A gap keeps its width in the row but is neither drawn
                    // nor clickable.
                    enabled: modelData.gap !== true
                    opacity: modelData.gap ? 0 : (dimmed ? 0.35 : 1)
                    label: modelData.label || ""
                    kind: modelData.gap ? "free" : root.kindOf(modelData)
                    sub: root.subOf(modelData)
                    selected: modelData.id !== undefined && Keys.keyId(modelData.id) === Store.selectedKey
                    dimmed: Store.matching !== null && modelData.id !== undefined
                            && Store.matching[Keys.keyId(modelData.id)] !== true
                    onClicked: root.press(modelData)
                }
            }
        }
    }
}
```

`quickshell/hyprkbm/components/Keyboard.qml`:

```qml
import QtQuick
import "../state"

// The main block and the navigation cluster of Store.layout, sized to the
// width it is given.
Item {
    id: root
    // Fifteen units of main block, half a unit of gap, three of cluster.
    readonly property real unit: Math.max(26, Math.min(48, Math.floor(width / 18.5)))
    implicitHeight: unit * 6

    Row {
        spacing: root.unit * 0.5
        KeyBlock { rows: Store.layout.main; unit: root.unit }
        KeyBlock { rows: Store.layout.nav; unit: root.unit }
    }
}
```

`quickshell/hyprkbm/components/ModifierBar.qml`:

```qml
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// The modifiers the keyboard is showing. Click to toggle; holding the real
// ones shows them for as long as they are held.
RowLayout {
    id: root
    spacing: Spacing.sm

    Repeater {
        model: ["SUPER", "CTRL", "ALT", "SHIFT"]
        delegate: Rectangle {
            id: chip
            required property string modelData
            readonly property bool picked: Store.mods.indexOf(modelData) >= 0
            implicitWidth: chipText.implicitWidth + Spacing.lg
            implicitHeight: 24
            radius: height / 2
            color: picked ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentSecondary.r, Colors.accentSecondary.g, Colors.accentSecondary.b, 0.15)) : "transparent"
            border.width: 1
            border.color: picked ? Colors.accentSecondary : Colors.borderSubtle

            Text {
                id: chipText
                anchors.centerIn: parent
                text: chip.modelData
                color: chip.picked ? Colors.accentSecondary : Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: Store.toggleMod(chip.modelData)
            }
        }
    }

    Text {
        Layout.fillWidth: true
        text: "click to toggle, or hold them on your keyboard · " + Store.layout.name
              + (Store.submap === "" ? "" : " · submap " + Store.submap)
        color: Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        elide: Text.ElideRight
    }

    Repeater {
        model: [["bound", Colors.accentPrimary], ["conflict", Colors.statusCritical], ["free", Colors.textTertiary]]
        delegate: Row {
            required property var modelData
            spacing: Spacing.xs
            Rectangle { width: 9; height: 9; radius: 2; color: modelData[1]; anchors.verticalCenter: parent.verticalCenter }
            Text {
                text: modelData[0]
                color: Colors.textTertiary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }
    }
}
```

`quickshell/hyprkbm/components/ExtraKeys.qml`:

```qml
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/labels.js" as Labels

// Keys that are not on a keyboard: mouse buttons, the wheel, and the media
// keys the config uses. "+ any key…" starts a bind on a key typed by hand.
ColumnLayout {
    id: root
    property real unit: 40
    spacing: Spacing.xs

    function kindOf(id) {
        var i = Store.keyStates[Keys.keyId(id)]
        return i === undefined ? "free" : i.state
    }

    function subOf(id) {
        var i = Store.keyStates[Keys.keyId(id)]
        if (i === undefined) return ""
        return i.binds.length > 1 ? i.binds.length + " binds" : Labels.shortLabel(i.binds[0])
    }

    Text {
        text: "Mouse & other"
        color: Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
    }

    Flow {
        Layout.preferredWidth: root.unit * 3
        spacing: 0
        Repeater {
            model: Store.extras
            delegate: KeyCap {
                required property var modelData
                unit: root.unit
                label: modelData.label
                kind: root.kindOf(modelData.id)
                sub: root.subOf(modelData.id)
                selected: Keys.keyId(modelData.id) === Store.selectedKey
                dimmed: Store.matching !== null && Store.matching[Keys.keyId(modelData.id)] !== true
                onClicked: Store.selectKey(modelData.id)
            }
        }
    }

    Action {
        text: "+ any key…"
        enabled: !Store.readOnly
        onClicked: Store.newBind(Keys.display(Store.mods, ""))
    }
}
```

- [ ] **Step 4: Lay the keyboard out in the window**

In `quickshell/hyprkbm/shell.qml`, replace the `Keys.onPressed` handler with:

```qml
            Keys.onPressed: function (event) {
                var mod = QtKeys.modifierFromQtKey(event.key)
                if (mod !== "") { Store.hold(mod); return }
                var dirs = {}
                dirs[Qt.Key_Left] = "left"
                dirs[Qt.Key_Right] = "right"
                dirs[Qt.Key_Up] = "up"
                dirs[Qt.Key_Down] = "down"
                if (dirs[event.key] !== undefined) {
                    Store.moveSelection(dirs[event.key])
                    event.accepted = true
                } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    if (Store.listed.length > 0) Store.edit(Store.listed[0].uid)
                    else Store.newBindOnSelected()
                    event.accepted = true
                }
            }
```

and replace the placeholder `Text { … }` and `Item { Layout.fillHeight: true }` inside `ColumnLayout { id: body … }` with:

```qml
                Text {
                    visible: Store.loading || Store.loadError !== ""
                    text: Store.loading ? "Reading your keybinds…" : Store.loadError
                    color: Store.loadError !== "" ? Colors.statusCritical : Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeBody
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: keyboardColumn.implicitHeight + Spacing.lg * 2
                    color: Colors.bgBase
                    radius: Radius.md
                    border.width: 1
                    border.color: Colors.borderSubtle

                    ColumnLayout {
                        id: keyboardColumn
                        anchors.fill: parent
                        anchors.margins: Spacing.lg
                        spacing: Spacing.sm

                        ModifierBar { Layout.fillWidth: true }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Spacing.lg

                            Keyboard {
                                id: keyboard
                                Layout.fillWidth: true
                                Layout.preferredHeight: implicitHeight
                            }

                            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Colors.borderSubtle }

                            ExtraKeys {
                                Layout.alignment: Qt.AlignTop
                                unit: keyboard.unit
                            }
                        }
                    }
                }

                Item { Layout.fillWidth: true; Layout.fillHeight: true }
```

- [ ] **Step 5: Run the tests, lint, and smoke-test**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors.

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d
sleep 2
qs ipc -p quickshell/hyprkbm call hyprkbm select q SUPER
qs ipc -p quickshell/hyprkbm call hyprkbm search "exec:kitty"
qs log -p quickshell/hyprkbm | tail -20
qs kill -p quickshell/hyprkbm
```

Expected: `select` returns `"selectedKey":"q"` and a `listed` array with the uid of your SUPER+Q bind (`h:<n>`); `search` returns a non-empty `listed`; the log shows no `ReferenceError`, `TypeError` or `Unable to assign` lines. Look at the window while it is open: keys bound under SUPER are tinted with the accent, the selected key has a light outline, and the extra keys sit to the right of the arrows.

- [ ] **Step 6: Commit**

```bash
git add quickshell/hyprkbm/components/KeyCap.qml quickshell/hyprkbm/components/KeyBlock.qml quickshell/hyprkbm/components/Keyboard.qml quickshell/hyprkbm/components/ModifierBar.qml quickshell/hyprkbm/components/ExtraKeys.qml quickshell/hyprkbm/shell.qml tests/test_panel_qml.py
git commit -m "feat: draw the keyboard, lit by what each key does

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Header, bind list and banners

**Files:**
- Create: `quickshell/hyprkbm/components/Header.qml`, `BindPanel.qml`, `BindRow.qml`, `Banner.qml`
- Modify: `quickshell/hyprkbm/shell.qml`, `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Store.submaps, submap, merged (binds, conflicts, stale), query, listed, removedHere, unplaced, selectedKey, mods, layout, errors, readOnly, doc, loadError, draft`; `Store.nextConflict, edit, deleteBind, keepBoth, restoreHand, newBindOnSelected, startWatcher, reload`; `ThemePopup` (copied).
- Produces: `Header { function focusSearch(); signal backupsRequested(); signal exportRequested(); signal submapRequested(); signal settingsRequested(); signal leaveSearch() }`; `BindRow { property var bind; property bool inConflict }`; `BindPanel`; `Banner`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_panel_qml.py`:

```python
def test_the_header_and_bind_panel_are_wired():
    header = qml("components", "Header.qml")
    for needle in ("Store.submaps", "Store.query", "Store.nextConflict()", "ThemePopup",
                   "signal backupsRequested()", "signal exportRequested()",
                   "signal submapRequested()", "signal settingsRequested()",
                   "function focusSearch()"):
        assert needle in header, needle
    panel = qml("components", "BindPanel.qml")
    for needle in ("Store.listed", "Store.removedHere", "Store.unplaced",
                   "Store.restoreHand(", "Store.newBindOnSelected()"):
        assert needle in panel, needle
    row = qml("components", "BindRow.qml")
    for needle in ("Store.edit(", "Store.deleteBind(", "Store.keepBoth("):
        assert needle in row, needle
    banner = qml("components", "Banner.qml")
    for needle in ("readerError", "modelError", "Store.startWatcher()"):
        assert needle in banner, needle


def test_slash_focuses_search():
    shell = qml("shell.qml")
    assert "Qt.Key_Slash" in shell
    assert "header.focusSearch()" in shell
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_panel_qml.py -q`
Expected: FAIL — `FileNotFoundError` for `Header.qml`.

- [ ] **Step 3: Implement the four components**

`quickshell/hyprkbm/components/Header.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"

// Submaps, search, the conflict stepper and the header's actions. The
// dialogs themselves live in shell.qml; the header only asks for them.
RowLayout {
    id: root
    spacing: Spacing.md

    signal backupsRequested()
    signal exportRequested()
    signal submapRequested()
    signal settingsRequested()
    // Escape in the search hands focus back to the window, for the arrow keys.
    signal leaveSearch()

    function focusSearch() { search.forceActiveFocus() }

    function countIn(name) {
        return Store.merged.binds.filter(function (b) { return b.submap === name }).length
    }

    Text {
        text: "Keybinds"
        color: Colors.textPrimary
        font.family: Typography.family
        font.pixelSize: 18
        font.weight: Typography.weightMedium
    }

    Repeater {
        model: Store.submaps
        delegate: Rectangle {
            id: chip
            required property string modelData
            readonly property bool picked: Store.submap === modelData
            implicitWidth: chipText.implicitWidth + Spacing.lg
            implicitHeight: 24
            radius: height / 2
            color: picked ? Colors.accentPrimary : Colors.bgSurfaceAlt
            Text {
                id: chipText
                anchors.centerIn: parent
                text: (chip.modelData === "" ? "global" : chip.modelData) + " · " + root.countIn(chip.modelData)
                color: chip.picked ? Colors.bgVoid : Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: Store.submap = chip.modelData
            }
        }
    }

    Action {
        text: "+ submap"
        enabled: !Store.readOnly
        onClicked: root.submapRequested()
    }

    TextField {
        id: search
        Layout.fillWidth: true
        placeholderText: "/ search · mod: key: exec: desc: submap: src:"
        text: Store.query
        onTextEdited: Store.query = text
        color: Colors.textPrimary
        placeholderTextColor: Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: 1
            border.color: search.activeFocus ? Colors.borderStrong : Colors.borderSubtle
        }
        // Escape leaves the search rather than closing the panel.
        Keys.onEscapePressed: function (event) {
            Store.query = ""
            root.leaveSearch()
            event.accepted = true
        }
    }

    Action {
        visible: Store.merged.conflicts.length > 0
        text: "⚠ " + Store.merged.conflicts.length + (Store.merged.conflicts.length === 1 ? " conflict" : " conflicts")
        onClicked: Store.nextConflict()
    }

    Action { text: "Backups"; onClicked: root.backupsRequested() }
    Action { text: "Export"; onClicked: root.exportRequested() }

    Action {
        text: "Theme"
        onClicked: themePopup.opened ? themePopup.close() : themePopup.open()
        // Declared inside the button so it hangs from it.
        ThemePopup { id: themePopup }
    }

    Action { text: "⋯"; onClicked: root.settingsRequested() }
}
```

`quickshell/hyprkbm/components/BindRow.qml`:

```qml
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// One bind: its keys, what it does, where it comes from, and what can be done
// with it. A bind the last apply refused is outlined in the critical colour.
Rectangle {
    id: root
    property var bind
    property bool inConflict: false
    readonly property bool refused: root.bind.id !== null && Store.errors.some(function (e) { return e.id === root.bind.id })
    readonly property bool editing: Store.draft !== null
        && ((root.bind.id !== null && Store.draft.id === root.bind.id)
            || (root.bind.source === "hand" && Store.draft.hand !== null && Store.draft.id === null
                && Store.draft.hand.uid === root.bind.uid))

    implicitHeight: 36
    radius: Radius.sm
    color: editing ? Colors.bgSurfaceAlt : hover.hovered ? Colors.bgSurface : "transparent"
    border.width: refused ? 1 : 0
    border.color: Colors.statusCritical

    HoverHandler { id: hover }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.sm
        anchors.rightMargin: Spacing.sm
        spacing: Spacing.sm

        Repeater {
            model: root.bind.mods.concat([root.bind.key])
            delegate: Rectangle {
                required property string modelData
                implicitWidth: keyText.implicitWidth + Spacing.sm
                implicitHeight: 20
                radius: 4
                color: Colors.bgSurfaceAlt
                border.width: 1
                border.color: Colors.borderSubtle
                Text {
                    id: keyText
                    anchors.centerIn: parent
                    text: modelData
                    color: Colors.textPrimary
                    font.family: "monospace"
                    font.pixelSize: Typography.sizeSmall
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.bind.describe + (root.bind.description !== "" ? "  ·  " + root.bind.description : "")
            color: root.inConflict ? Colors.statusCritical : Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            elide: Text.ElideRight
        }

        Rectangle {
            implicitWidth: sourceText.implicitWidth + Spacing.md
            implicitHeight: 18
            radius: 9
            color: "transparent"
            border.width: 1
            border.color: root.bind.source === "hyprkbm" ? Colors.accentTertiary
                        : root.bind.source === "override" ? Colors.accentSecondary
                        : Colors.textTertiary
            Text {
                id: sourceText
                anchors.centerIn: parent
                text: root.bind.source === "hand" ? root.bind.where
                    : root.bind.source === "override" ? "overrides " + root.bind.hand.where
                    : "hyprKBM"
                color: parent.border.color
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }

        Action {
            text: "Keep both"
            visible: root.inConflict && root.bind.id !== null
            onClicked: Store.keepBoth(root.bind.uid)
        }
        Action {
            text: "Edit"
            enabled: !Store.readOnly && root.bind.dispatcher !== null && root.bind.dispatcher.__function === undefined
            onClicked: Store.edit(root.bind.uid)
        }
        Action {
            text: "Remove"
            enabled: !Store.readOnly
            onClicked: Store.deleteBind(root.bind.uid)
        }
    }
}
```

`quickshell/hyprkbm/components/BindPanel.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/layouts.js" as Layouts

// Every bind on the selected key -- or every match, while searching -- with
// conflicts called out, binds this change removes, and the binds no keycap
// shows.
Rectangle {
    id: root
    color: Colors.bgBase
    radius: Radius.md
    border.width: 1
    border.color: Colors.borderSubtle

    readonly property bool searching: !Store.parsedQuery.empty
    readonly property string keyText: Store.selectedKey === "" ? ""
        : Keys.display(Store.mods, Layouts.keyName(Store.layout, Store.selectedKey))
    readonly property bool conflicted: !searching
        && Store.listed.filter(function (b) { return !b.allowConflict }).length > 1

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.md
        spacing: Spacing.sm

        Text {
            text: root.searching ? "Search · " + Store.listed.length + " matches"
                : root.keyText === "" ? "Pick a key"
                : root.keyText + " · " + (Store.submap === "" ? "global" : Store.submap)
                  + " · " + Store.listed.length + (Store.listed.length === 1 ? " bind" : " binds")
            color: Colors.textTertiary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            font.capitalization: Font.AllUppercase
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 2

                Repeater {
                    model: Store.listed
                    delegate: BindRow {
                        required property var modelData
                        Layout.fillWidth: true
                        bind: modelData
                        inConflict: root.conflicted && !modelData.allowConflict
                    }
                }

                Text {
                    visible: root.conflicted
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "⚠ These all fire on " + root.keyText + ". Remove one, keep both, or edit one onto other keys."
                    color: Colors.statusCritical
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }

                Repeater {
                    model: root.searching ? [] : Store.removedHere
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: "Removed: " + modelData.hand.describe + " (" + modelData.hand.where + ")"
                            color: Colors.textTertiary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeSmall
                            font.strikeout: true
                            elide: Text.ElideRight
                        }
                        Action { text: "Restore"; onClicked: Store.restoreHand(modelData.hand) }
                    }
                }

                Action {
                    visible: !root.searching && root.keyText !== ""
                    enabled: !Store.readOnly
                    text: "+ Add a bind on " + root.keyText
                    onClicked: Store.newBindOnSelected()
                }

                Text {
                    visible: !root.searching && Store.unplaced.length > 0
                    Layout.topMargin: Spacing.md
                    text: "Unplaced · binds no keycap shows"
                    color: Colors.textTertiary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                    font.capitalization: Font.AllUppercase
                }

                Repeater {
                    model: root.searching ? [] : Store.unplaced
                    delegate: BindRow {
                        required property var modelData
                        Layout.fillWidth: true
                        bind: modelData
                    }
                }
            }
        }
    }
}
```

`quickshell/hyprkbm/components/Banner.qml`:

```qml
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// Things that are wrong with the setup rather than with a bind: the config
// could not be read completely, keybinds.json cannot be used, or the watcher
// is not running (so binds would vanish at the next reload).
ColumnLayout {
    id: root
    spacing: Spacing.xs
    readonly property var doc: Store.doc

    component Line: Rectangle {
        id: line
        property string message: ""
        property string button: ""
        signal pressed()
        Layout.fillWidth: true
        visible: message !== ""
        implicitHeight: lineRow.implicitHeight + Spacing.sm * 2
        radius: Radius.sm
        color: Qt.tint(Colors.bgBase, Qt.rgba(Colors.statusCritical.r, Colors.statusCritical.g, Colors.statusCritical.b, 0.12))
        border.width: 1
        border.color: Colors.statusCritical
        RowLayout {
            id: lineRow
            anchors.fill: parent
            anchors.margins: Spacing.sm
            Text {
                Layout.fillWidth: true
                text: line.message
                wrapMode: Text.WordWrap
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
            Action {
                visible: line.button !== ""
                text: line.button
                onClicked: line.pressed()
            }
        }
    }

    Line {
        message: root.doc && root.doc.readerError
                 ? "hyprland.lua could not be read completely, so some binds may be missing and nothing can be applied: " + root.doc.readerError
                 : ""
        button: "Reload"
        onPressed: Store.reload()
    }

    Line {
        message: root.doc && root.doc.modelError
                 ? "keybinds.json cannot be used, so the panel is read-only: " + root.doc.modelError
                   + (root.doc.backups.length > 0 ? " Restore a backup from Backups." : "")
                 : ""
    }

    Line {
        message: root.doc && root.doc.watcher !== "active"
                 ? "The hyprkbm-watch service is " + root.doc.watcher + ", so hyprKBM's binds will be gone after the next Hyprland reload."
                 : ""
        button: "Start it"
        onPressed: Store.startWatcher()
    }
}
```

- [ ] **Step 4: Lay them out in the window**

In `quickshell/hyprkbm/shell.qml`, add `/` to `Keys.onPressed` — insert before the `var dirs = {}` line:

```qml
                if (event.key === Qt.Key_Slash) {
                    header.focusSearch()
                    event.accepted = true
                    return
                }
```

In `ColumnLayout { id: body … }`, insert as the first two children:

```qml
                Header {
                    id: header
                    Layout.fillWidth: true
                    onLeaveSearch: scope.forceActiveFocus()
                }

                Banner { Layout.fillWidth: true }
```

and replace the trailing `Item { Layout.fillWidth: true; Layout.fillHeight: true }` with:

```qml
                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Spacing.md

                    BindPanel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
                }
```

- [ ] **Step 5: Run the tests, lint, and smoke-test**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors.

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d
sleep 2
qs ipc -p quickshell/hyprkbm call hyprkbm select f SUPER
qs ipc -p quickshell/hyprkbm call hyprkbm search "src:hyprkbm"
qs log -p quickshell/hyprkbm | tail -20
qs kill -p quickshell/hyprkbm
```

Expected: the `select` call lists the SUPER+F bind(s); the log shows no QML errors. While the window is open, check by eye: the header shows `global · N` and any submaps, typing in the search dims non-matching keys, and the bind list shows each bind's keys, action and source.

- [ ] **Step 6: Commit**

```bash
git add quickshell/hyprkbm/components/Header.qml quickshell/hyprkbm/components/BindPanel.qml quickshell/hyprkbm/components/BindRow.qml quickshell/hyprkbm/components/Banner.qml quickshell/hyprkbm/shell.qml tests/test_panel_qml.py
git commit -m "feat: list the selected key's binds, with search, submaps and banners

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The bind editor

**Files:**
- Create: `quickshell/hyprkbm/components/Editor.qml`
- Modify: `quickshell/hyprkbm/shell.qml`, `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Store.draft, catalogue, submaps, readOnly`; `Store.patchDraft, patchArg, setActionKind, draftProblems, saveDraft, cancelEdit, deleteDraft`; `Catalogue.entryById`; `Model.FLAG_NAMES`; `QtKeys.keysymFromQt(key, modifiers), modsFromQt`; `Keys.display`.
- Produces: `Editor` (no public API).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_panel_qml.py`:

```python
def test_the_editor_stages_through_the_store():
    editor = qml("components", "Editor.qml")
    for needle in ("Store.saveDraft()", "Store.cancelEdit()", "Store.deleteDraft()",
                   "Store.patchDraft(", "Store.patchArg(", "Store.setActionKind(",
                   "Store.draftProblems()", "QtKeys.keysymFromQt(", "QtKeys.modsFromQt(",
                   "Model.FLAG_NAMES"):
        assert needle in editor, needle


def test_the_window_has_the_editor():
    assert re.search(r"^\s*Editor\s*\{", qml("shell.qml"), re.M)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_panel_qml.py -q`
Expected: FAIL — `FileNotFoundError` for `Editor.qml`.

- [ ] **Step 3: Implement the editor**

`quickshell/hyprkbm/components/Editor.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/qtkeys.js" as QtKeys
import "../lib/model.js" as Model
import "../lib/catalogue.js" as Catalogue

// The draft in Store.draft: keys, action, description, flags and submap.
// Saving stages it in the model; nothing reaches Hyprland until Apply.
Rectangle {
    id: root
    color: Colors.bgBase
    radius: Radius.md
    border.width: 1
    border.color: Colors.borderSubtle

    readonly property var draft: Store.draft
    readonly property var entry: draft === null || draft.action.kind === "raw" ? null
                                 : Catalogue.entryById(Store.catalogue, draft.action.kind)
    readonly property var problems: Store.draftProblems()
    readonly property var kinds: Store.catalogue.map(function (e) { return e.id }).concat(["raw"])
    readonly property var kindLabels: Store.catalogue.map(function (e) { return e.label }).concat(["Raw Lua"])
    property bool recording: false

    component Label: Text {
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        font.weight: Typography.weightMedium
    }

    component Input: TextField {
        id: input
        Layout.fillWidth: true
        color: Colors.textPrimary
        placeholderTextColor: Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: 1
            border.color: input.activeFocus ? Colors.borderStrong : Colors.borderSubtle
        }
    }

    Text {
        visible: root.draft === null
        anchors.centerIn: parent
        width: parent.width - Spacing.xl * 2
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: "Pick a key and press Edit on one of its binds, or add one."
        color: Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
    }

    ScrollView {
        visible: root.draft !== null
        anchors.fill: parent
        anchors.margins: Spacing.md
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Spacing.sm

            Text {
                text: root.draft === null ? ""
                    : root.draft.id !== null ? "Edit bind"
                    : root.draft.hand !== null ? "Override " + root.draft.hand.where
                    : "New bind"
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
                font.weight: Typography.weightMedium
            }

            Label { text: "Keys" }
            RowLayout {
                Layout.fillWidth: true
                Input {
                    id: keysField
                    text: root.draft === null ? "" : root.draft.keys
                    placeholderText: root.recording ? "Press the keys…" : "SUPER + SHIFT + F"
                    onTextEdited: Store.patchDraft({ keys: text })
                    // While recording, the next key pressed with its modifiers
                    // becomes the combo. Hyprland keeps combos it already
                    // binds, so some can only be typed.
                    Keys.onPressed: function (event) {
                        if (!root.recording) return
                        var key = QtKeys.keysymFromQt(event.key, event.modifiers)
                        event.accepted = true
                        if (key === null) return
                        Store.patchDraft({ keys: Keys.display(QtKeys.modsFromQt(event.modifiers), key) })
                        root.recording = false
                    }
                }
                Action {
                    text: root.recording ? "Stop" : "⏺ Record"
                    onClicked: {
                        root.recording = !root.recording
                        if (root.recording) keysField.forceActiveFocus()
                    }
                }
            }

            Label { text: "Action" }
            Select {
                Layout.fillWidth: true
                model: root.kindLabels
                currentIndex: root.draft === null ? -1 : root.kinds.indexOf(root.draft.action.kind)
                onActivated: function (index) { Store.setActionKind(root.kinds[index]) }
            }

            Repeater {
                model: root.entry === null ? [] : root.entry.fields
                delegate: ColumnLayout {
                    id: fieldItem
                    required property var modelData
                    readonly property var value: root.draft.action.args === undefined ? undefined
                                                 : root.draft.action.args[modelData.name]
                    Layout.fillWidth: true
                    spacing: Spacing.xs

                    Label { text: fieldItem.modelData.label + (fieldItem.modelData.required ? "" : " (optional)") }

                    Input {
                        visible: ["string", "workspace", "submap"].indexOf(fieldItem.modelData.type) >= 0
                        text: fieldItem.value === undefined ? "" : String(fieldItem.value)
                        onTextEdited: {
                            var v = text
                            if (fieldItem.modelData.type === "workspace" && /^-?\d+$/.test(v)) v = parseInt(v, 10)
                            Store.patchArg(fieldItem.modelData.name, v)
                        }
                    }

                    Select {
                        visible: fieldItem.modelData.type === "enum"
                        Layout.fillWidth: true
                        model: fieldItem.modelData.type === "enum" ? [""].concat(fieldItem.modelData.values) : []
                        currentIndex: fieldItem.modelData.type === "enum"
                                      ? [""].concat(fieldItem.modelData.values).indexOf(fieldItem.value === undefined ? "" : fieldItem.value)
                                      : -1
                        onActivated: function (index) {
                            Store.patchArg(fieldItem.modelData.name, index === 0 ? "" : fieldItem.modelData.values[index - 1])
                        }
                    }

                    Toggle {
                        visible: fieldItem.modelData.type === "bool"
                        text: fieldItem.modelData.label
                        checked: fieldItem.value === undefined ? fieldItem.modelData["default"] === true : fieldItem.value === true
                        onToggled: Store.patchArg(fieldItem.modelData.name, checked)
                    }
                }
            }

            TextArea {
                visible: root.draft !== null && root.draft.action.kind === "raw"
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                placeholderText: "hl.dsp.group.toggle()"
                text: root.draft !== null && root.draft.action.kind === "raw" ? root.draft.action.lua : ""
                onTextChanged: if (root.draft !== null && root.draft.action.kind === "raw" && text !== root.draft.action.lua)
                                   Store.patchDraft({ action: { kind: "raw", lua: text } })
                color: Colors.textPrimary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                wrapMode: TextEdit.Wrap
                background: Rectangle {
                    color: Colors.bgSurface
                    radius: Radius.sm
                    border.width: 1
                    border.color: Colors.borderSubtle
                }
            }

            Label { text: "Description · shown in the cheatsheet" }
            Input {
                text: root.draft === null ? "" : root.draft.description
                onTextEdited: Store.patchDraft({ description: text })
            }

            Label { text: "Flags" }
            Flow {
                Layout.fillWidth: true
                spacing: Spacing.xs
                Repeater {
                    model: Model.FLAG_NAMES
                    delegate: Rectangle {
                        id: flag
                        required property string modelData
                        readonly property bool picked: root.draft !== null && root.draft.flags[modelData] === true
                        implicitWidth: flagText.implicitWidth + Spacing.md
                        implicitHeight: 22
                        radius: 4
                        color: "transparent"
                        border.width: 1
                        border.color: picked ? Colors.accentTertiary : Colors.borderSubtle
                        Text {
                            id: flagText
                            anchors.centerIn: parent
                            text: flag.modelData.replace(/_/g, " ")
                            color: flag.picked ? Colors.accentTertiary : Colors.textTertiary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeSmall
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var flags = Model.clone(root.draft.flags)
                                if (flag.picked) delete flags[flag.modelData]
                                else flags[flag.modelData] = true
                                Store.patchDraft({ flags: flags })
                            }
                        }
                    }
                }
            }

            Label { text: "Submap" }
            Select {
                Layout.fillWidth: true
                model: Store.submaps.map(function (s) { return s === "" ? "global" : s })
                currentIndex: root.draft === null ? -1 : Store.submaps.indexOf(root.draft.submap)
                onActivated: function (index) { Store.patchDraft({ submap: Store.submaps[index] }) }
            }

            Repeater {
                model: root.problems
                delegate: Text {
                    required property string modelData
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: modelData
                    color: Colors.statusCritical
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Spacing.sm
                Action {
                    text: "Save"
                    primary: true
                    enabled: root.problems.length === 0 && !Store.readOnly
                    onClicked: Store.saveDraft()
                }
                Action { text: "Cancel"; onClicked: Store.cancelEdit() }
                Item { Layout.fillWidth: true }
                Action {
                    visible: root.draft !== null && (root.draft.id !== null || root.draft.hand !== null)
                    text: "Delete"
                    onClicked: Store.deleteDraft()
                }
            }
        }
    }
}
```

- [ ] **Step 4: Add the editor to the window**

In `quickshell/hyprkbm/shell.qml`, add to the `RowLayout` that holds `BindPanel`, after it:

```qml
                    Editor {
                        Layout.preferredWidth: 340
                        Layout.fillHeight: true
                    }
```

- [ ] **Step 5: Run the tests, lint, and smoke-test**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors.

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d
sleep 2
qs ipc -p quickshell/hyprkbm call hyprkbm select q SUPER
UID_Q=$(qs ipc -p quickshell/hyprkbm call hyprkbm state | python3 -c "import json,sys; print(json.load(sys.stdin)['listed'][0])")
qs ipc -p quickshell/hyprkbm call hyprkbm edit "$UID_Q"
qs log -p quickshell/hyprkbm | tail -20
qs kill -p quickshell/hyprkbm
```

Expected: after `edit`, `state` shows a `draft` with `"keys":"SUPER + Q"` and `"kind":"exec_cmd"`; the log shows no QML errors. While the window is open (before the kill), look at the editor: it shows the bind's keys, "Run a command" with your terminal's command, no problems listed. Do not press Save or Apply.

- [ ] **Step 6: Commit**

```bash
git add quickshell/hyprkbm/components/Editor.qml quickshell/hyprkbm/shell.qml tests/test_panel_qml.py
git commit -m "feat: edit binds: keys, actions, raw Lua, flags and submaps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Staged changes, the diff and applying

**Files:**
- Create: `quickshell/hyprkbm/components/StagedBar.qml`, `DiffDialog.qml`
- Modify: `quickshell/hyprkbm/shell.qml`, `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Store.dirty, saved, model, busy, status, failed, errors, preview, readOnly`; `Store.discard, apply, requestPreview`; `Model.summary`; `Diff.lineDiff, counts`.
- Produces: `StagedBar { signal reviewRequested() }`; `DiffDialog` (a `Popup`; `open()`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_panel_qml.py`:

```python
def test_staged_changes_apply_only_from_the_bar_and_the_diff():
    bar = qml("components", "StagedBar.qml")
    assert "Model.summary(" in bar
    assert "Store.discard()" in bar
    assert "Store.apply()" in bar
    assert "signal reviewRequested()" in bar
    diff = qml("components", "DiffDialog.qml")
    assert "Store.requestPreview()" in diff
    assert "Diff.lineDiff(" in diff
    assert "Store.apply()" in diff
    # The bar, the diff and the window's Ctrl+Enter -- and nothing else.
    applies = [n for n, s in all_qml().items() if "Store.apply()" in s]
    assert sorted(applies) == ["components/DiffDialog.qml", "components/StagedBar.qml",
                               "shell.qml", "state/Store.qml"]


def test_ctrl_enter_applies_from_the_window():
    shell = qml("shell.qml")
    assert re.search(r'sequences:\s*\["Ctrl\+Return",\s*"Ctrl\+Enter"\]', shell)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_panel_qml.py -q`
Expected: FAIL — `FileNotFoundError` for `StagedBar.qml`.

- [ ] **Step 3: Implement**

`quickshell/hyprkbm/components/StagedBar.qml`:

```qml
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/model.js" as Model

// What is staged and not yet applied, and the result of the last apply.
// Nothing reaches Hyprland until Apply.
Rectangle {
    id: root
    signal reviewRequested()

    readonly property var counts: Store.dirty ? Model.summary(Store.saved, Store.model) : null
    readonly property string summaryText: {
        if (counts === null) return ""
        var parts = []
        if (counts.added) parts.push("+" + counts.added + " bind" + (counts.added > 1 ? "s" : ""))
        if (counts.changed) parts.push("~" + counts.changed + " changed")
        if (counts.removed) parts.push("−" + counts.removed + " removed")
        if (counts.unbound) parts.push("−" + counts.unbound + " unbound")
        if (counts.restored) parts.push(counts.restored + " restored")
        if (counts.submaps > 0) parts.push("+" + counts.submaps + " submap" + (counts.submaps > 1 ? "s" : ""))
        return parts.join(" · ")
    }

    visible: Store.dirty || Store.status !== ""
    implicitHeight: row.implicitHeight + Spacing.sm * 2
    radius: Radius.md
    color: Store.dirty
           ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentSecondary.r, Colors.accentSecondary.g, Colors.accentSecondary.b, 0.1))
           : Colors.bgBase
    border.width: 1
    border.color: Store.failed ? Colors.statusCritical : Store.dirty ? Colors.accentSecondary : Colors.borderSubtle

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: Spacing.sm
        spacing: Spacing.md

        Text {
            visible: Store.dirty
            text: "Unapplied changes"
            color: Colors.accentSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }
        Text {
            visible: Store.dirty
            text: root.summaryText
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
        }
        Text {
            Layout.fillWidth: true
            text: Store.status
            color: Store.failed ? Colors.statusCritical : Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            elide: Text.ElideRight
        }

        Action { visible: Store.dirty; text: "Review diff"; onClicked: root.reviewRequested() }
        Action { visible: Store.dirty; text: "Discard"; enabled: !Store.busy; onClicked: Store.discard() }
        Action {
            visible: Store.dirty
            primary: true
            text: Store.busy ? "Applying…" : "Apply"
            enabled: !Store.busy && !Store.readOnly
            onClicked: Store.apply()
        }
    }
}
```

`quickshell/hyprkbm/components/DiffDialog.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/diff.js" as Diff

// The generated keybinds.lua as it is and as it would be, from
// hyprkbm-apply --preview -- which also validates, so errors show here
// before anyone presses Apply.
Popup {
    id: root
    parent: Overlay.overlay
    modal: true
    focus: true
    width: Math.min(900, parent ? parent.width - Spacing.xl * 2 : 900)
    height: Math.min(640, parent ? parent.height - Spacing.xl * 2 : 640)
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var lines: Store.preview && Store.preview.ok
                                 ? Diff.lineDiff(Store.preview.current, Store.preview.lua) : []
    readonly property var counts: Diff.counts(lines)

    onOpened: Store.requestPreview()

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Text {
            text: Store.preview === null ? "Checking the new keybinds…"
                : Store.preview.ok ? "keybinds.lua · +" + root.counts.added + " −" + root.counts.removed
                : "These changes cannot be applied"
            color: Store.preview !== null && !Store.preview.ok ? Colors.statusCritical : Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }

        Repeater {
            model: Store.preview !== null && !Store.preview.ok ? Store.preview.errors : []
            delegate: Text {
                required property var modelData
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: (modelData.id ? modelData.id + ": " : "") + modelData.message
                color: Colors.statusCritical
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.lines
            ScrollBar.vertical: ScrollBar {}
            delegate: Text {
                required property var modelData
                width: ListView.view.width
                text: modelData.op + " " + modelData.text
                color: modelData.op === "+" ? Colors.accentTertiary
                     : modelData.op === "-" ? Colors.statusCritical
                     : Colors.textTertiary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                elide: Text.ElideRight
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Close"; onClicked: root.close() }
            Action {
                text: "Apply"
                primary: true
                enabled: Store.preview !== null && Store.preview.ok && !Store.busy && !Store.readOnly
                onClicked: { Store.apply(); root.close() }
            }
        }
    }
}
```

- [ ] **Step 4: Add them to the window**

In `quickshell/hyprkbm/shell.qml`, add as the last child of `ColumnLayout { id: body … }`:

```qml
                StagedBar {
                    Layout.fillWidth: true
                    onReviewRequested: diffDialog.open()
                }
```

add inside `FloatingWindow`, after the `FocusScope`:

```qml
        DiffDialog { id: diffDialog }
```

and add inside `FloatingWindow`, after `DiffDialog { id: diffDialog }` (after the `FocusScope`, so that it is not between `IpcHandler` and `FocusScope`, where `test_the_window_is_titled_and_scriptable` checks no apply can be reached):

```qml
        // Ctrl+Enter is safe as a Shortcut: nothing else in the panel wants it.
        Shortcut {
            sequences: ["Ctrl+Return", "Ctrl+Enter"]
            enabled: Store.dirty && !Store.busy && !Store.readOnly && Store.draft === null
            onActivated: Store.apply()
        }
```

- [ ] **Step 5: Run the tests, lint, and smoke-test**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors.

Smoke test (no apply): open the panel as before, open the diff with no changes staged is impossible (the bar is hidden), so stage nothing and only check the log is clean; then kill it. The full apply round trip is Task 12's live check.

- [ ] **Step 6: Commit**

```bash
git add quickshell/hyprkbm/components/StagedBar.qml quickshell/hyprkbm/components/DiffDialog.qml quickshell/hyprkbm/shell.qml tests/test_panel_qml.py
git commit -m "feat: review staged changes as a diff and apply them

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Backups, export, settings and submaps

**Files:**
- Create: `quickshell/hyprkbm/components/BackupsDialog.qml`, `ExportDialog.qml`, `SettingsPopup.qml`, `SubmapDialog.qml`
- Modify: `quickshell/hyprkbm/shell.qml`, `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Store.doc (backups, currentLua, entry, watcher, settings), backup, layoutName, submaps, readOnly, busy`; `Store.loadBackup, restoreBackup, exportTo, setLayout, startWatcher, reload, addSubmap`; `Diff.lineDiff, counts`; `Keys.parse`; `Quickshell.env("HOME")`.
- Produces: four `Popup`s with `open()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_panel_qml.py`:

```python
def test_the_header_dialogs_are_wired():
    backups = qml("components", "BackupsDialog.qml")
    for needle in ("Store.loadBackup(", "Store.restoreBackup()", "Diff.lineDiff("):
        assert needle in backups, needle
    assert "Store.exportTo(" in qml("components", "ExportDialog.qml")
    settings = qml("components", "SettingsPopup.qml")
    for needle in ("Store.setLayout(", "Store.startWatcher()", "Store.reload()"):
        assert needle in settings, needle
    assert "Store.addSubmap(" in qml("components", "SubmapDialog.qml")
    shell = qml("shell.qml")
    for handler in ("onBackupsRequested", "onExportRequested", "onSubmapRequested",
                    "onSettingsRequested"):
        assert handler in shell, handler
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_panel_qml.py -q`
Expected: FAIL — `FileNotFoundError` for `BackupsDialog.qml`.

- [ ] **Step 3: Implement the four dialogs**

Each is a centred modal `Popup` styled like `DiffDialog`.

`quickshell/hyprkbm/components/BackupsDialog.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/diff.js" as Diff

// The last thirty versions of keybinds.json, each with what restoring it
// would change. Restoring stages the backup and applies it, through the same
// checks as any other apply.
Popup {
    id: root
    parent: Overlay.overlay
    modal: true
    focus: true
    width: Math.min(900, parent ? parent.width - Spacing.xl * 2 : 900)
    height: Math.min(600, parent ? parent.height - Spacing.xl * 2 : 600)
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    property string chosen: ""
    readonly property var names: Store.doc ? Store.doc.backups : []
    readonly property var lines: Store.backup ? Diff.lineDiff(Store.doc.currentLua, Store.backup.lua) : []

    function when(name) {
        // 20261008T173647613251 -> 2026-10-08 17:36:47
        return name.slice(0, 4) + "-" + name.slice(4, 6) + "-" + name.slice(6, 8)
             + " " + name.slice(9, 11) + ":" + name.slice(11, 13) + ":" + name.slice(13, 15)
    }

    onOpened: { chosen = ""; Store.backup = null }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: RowLayout {
        spacing: Spacing.lg

        ListView {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            clip: true
            model: root.names
            delegate: Rectangle {
                required property string modelData
                width: ListView.view.width
                height: 30
                radius: Radius.sm
                color: root.chosen === modelData ? Colors.bgSurfaceAlt : "transparent"
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Spacing.sm
                    text: root.when(modelData)
                    color: Colors.textPrimary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeBody
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: { root.chosen = modelData; Store.loadBackup(modelData) }
                }
            }
            Text {
                visible: root.names.length === 0
                text: "No backups yet. One is made before every apply."
                color: Colors.textTertiary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
                wrapMode: Text.WordWrap
                width: parent.width
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
                text: root.chosen === "" ? "Pick a backup to see what restoring it would change."
                    : Store.backup === null ? "Reading…"
                    : "Restoring " + root.when(root.chosen) + " · +" + Diff.counts(root.lines).added
                      + " −" + Diff.counts(root.lines).removed + " lines of keybinds.lua"
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.lines
                ScrollBar.vertical: ScrollBar {}
                delegate: Text {
                    required property var modelData
                    width: ListView.view.width
                    text: modelData.op + " " + modelData.text
                    color: modelData.op === "+" ? Colors.accentTertiary
                         : modelData.op === "-" ? Colors.statusCritical
                         : Colors.textTertiary
                    font.family: "monospace"
                    font.pixelSize: Typography.sizeSmall
                    elide: Text.ElideRight
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Action { text: "Close"; onClicked: root.close() }
                Action {
                    text: "Restore"
                    primary: true
                    enabled: Store.backup !== null && !Store.busy
                    onClicked: { Store.restoreBackup(); root.close() }
                }
            }
        }
    }
}
```

`quickshell/hyprkbm/components/ExportDialog.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import "../config"
import "../state"

// Writes the cheatsheet as Markdown with `hyprkbm --export md`. It exports
// what is applied, not what is staged.
Popup {
    id: root
    parent: Overlay.overlay
    modal: true
    focus: true
    width: 460
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Text {
            text: "Export a Markdown cheatsheet of the applied binds"
            color: Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }

        TextField {
            id: path
            Layout.fillWidth: true
            text: (Quickshell.env("HOME") || "") + "/keybinds.md"
            color: Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            background: Rectangle {
                color: Colors.bgBase
                radius: Radius.sm
                border.width: 1
                border.color: path.activeFocus ? Colors.borderStrong : Colors.borderSubtle
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: "Export"
                primary: true
                enabled: path.text.trim() !== ""
                onClicked: { Store.exportTo(path.text.trim()); root.close() }
            }
        }
    }
}
```

`quickshell/hyprkbm/components/SettingsPopup.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"

// The ⋯ menu: keyboard layout, which config is read, and the watcher.
Popup {
    id: root
    parent: Overlay.overlay
    modal: true
    focus: true
    width: 420
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property var layouts: ["ansi", "iso"]

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Keyboard layout"
            Select {
                width: parent.width
                model: ["ANSI", "ISO"]
                currentIndex: root.layouts.indexOf(Store.layoutName)
                onActivated: function (index) { Store.setLayout(root.layouts[index]) }
            }
        }

        Field {
            label: "Config read"
            hint: "Set \"entry\" in ~/.config/hyprkbm/settings.json to read another file."
            Text {
                width: parent.width
                text: Store.doc ? Store.doc.entry : ""
                color: Colors.textPrimary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                elide: Text.ElideMiddle
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "Watcher: " + (Store.doc ? Store.doc.watcher : "unknown")
                color: Store.doc && Store.doc.watcher === "active" ? Colors.textPrimary : Colors.statusCritical
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
            Action {
                visible: Store.doc !== null && Store.doc.watcher !== "active"
                text: "Start it"
                onClicked: Store.startWatcher()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Action {
                text: "Reload from disk"
                enabled: !Store.dirty
                onClicked: { Store.reload(); root.close() }
            }
            Item { Layout.fillWidth: true }
            Action { text: "Close"; onClicked: root.close() }
        }
    }
}
```

`quickshell/hyprkbm/components/SubmapDialog.qml`:

```qml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys

// A new submap: its name and the key that leaves it. A bind enters it with
// the "Enter submap" action.
Popup {
    id: root
    parent: Overlay.overlay
    modal: true
    focus: true
    width: 380
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property string problem: name.text.trim() === "" ? "Give it a name."
        : Store.submaps.indexOf(name.text.trim()) >= 0 ? "There is already a submap called " + name.text.trim() + "."
        : Keys.parse(reset.text) === null ? "The reset key must be a key, like escape."
        : ""

    onOpened: { name.text = ""; reset.text = "escape"; name.forceActiveFocus() }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Name"
            TextField {
                id: name
                width: parent.width
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
        }

        Field {
            label: "Key that leaves it"
            TextField {
                id: reset
                width: parent.width
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
        }

        Text {
            visible: root.problem !== ""
            text: root.problem
            color: Colors.textTertiary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: "Create"
                primary: true
                enabled: root.problem === "" && !Store.readOnly
                onClicked: { Store.addSubmap(name.text.trim(), reset.text.trim()); root.close() }
            }
        }
    }
}
```

- [ ] **Step 4: Wire them to the header**

In `quickshell/hyprkbm/shell.qml`, give `Header` its handlers:

```qml
                Header {
                    id: header
                    Layout.fillWidth: true
                    onLeaveSearch: scope.forceActiveFocus()
                    onBackupsRequested: backupsDialog.open()
                    onExportRequested: exportDialog.open()
                    onSubmapRequested: submapDialog.open()
                    onSettingsRequested: settingsPopup.open()
                }
```

and add next to `DiffDialog { id: diffDialog }`:

```qml
        BackupsDialog { id: backupsDialog }
        ExportDialog { id: exportDialog }
        SettingsPopup { id: settingsPopup }
        SubmapDialog { id: submapDialog }
```

- [ ] **Step 5: Run the tests, lint, and smoke-test**

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

Run: `find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`
Expected: no errors.

Smoke test as before; while the window is open, open each header dialog by clicking Backups, Export, ⋯ and + submap, check each opens centred and closes with Escape, and that the Backups list shows dates. Do not press Restore, Export or Create. Kill the panel; the log must show no QML errors.

- [ ] **Step 6: Commit**

```bash
git add quickshell/hyprkbm/components/BackupsDialog.qml quickshell/hyprkbm/components/ExportDialog.qml quickshell/hyprkbm/components/SettingsPopup.qml quickshell/hyprkbm/components/SubmapDialog.qml quickshell/hyprkbm/shell.qml tests/test_panel_qml.py
git commit -m "feat: add backups, export, settings and new submaps to the panel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Docs, then verify on the live session

**Files:**
- Modify: `README.md`, `CONTRIBUTING.md`

This task's Steps 3–5 change the live session and are run by the controller with the user's consent, not by an implementer subagent.

- [ ] **Step 1: Document the panel**

In `README.md`:
- In the intro, replace the "This release is the core…" note with: "The **keyboard panel** shows every bind on an on-screen keyboard; the cheatsheet overlay comes next."
- Add `| Quickshell | 0.3 or later, for the panel (the `qs` command). The command line works without it. |` to the Requirements table.
- Add a `## The panel` section after `## Install`:

```markdown
## The panel

Run `hyprkbm`, or open **Keybinds** from your app launcher. Bind it to a key
if you like:

```lua
hl.bind("SUPER + CTRL + K", hl.dsp.exec_cmd("hyprkbm"))
```

- **The keyboard** is lit by what each key does under the modifiers you hold
  (or click): accent for bound, red for a conflict. Click a key, or move with
  the arrow keys, to see every bind on it below.
- **Submaps** are the chips in the header; **search** (`/`) narrows to binds
  matching plain words or `mod:`, `key:`, `exec:`, `desc:`, `submap:` and
  `src:` (`src:lua` is your `hyprland.lua`).
- **Edit, Remove, + Add.** Editing one of your `hyprland.lua` binds makes an
  override; removing one makes an unbind. Record keys with ⏺, pick an action
  from the list or write raw Lua, add a description, flags and a submap.
- **Nothing changes until Apply** (or Ctrl+Enter). **Review diff** shows the
  generated `keybinds.lua` before and after, and any errors. **Discard**
  throws the staged changes away.
- **Backups** shows the last 30 versions with what restoring each would
  change. **Export** writes the Markdown cheatsheet. **Theme** offers the
  phos presets, an accent and dark or light, saved in
  `~/.config/hyprkbm/theme.json`. **⋯** switches between ANSI and ISO
  keyboards and shows the watcher's state.
```

- Add `hyprkbm` (no arguments) to the `## Using it` command block: `hyprkbm                       # open the panel`.

In `CONTRIBUTING.md`, add to "Running the tests": `node --test tests/js/` (or `npm test`), and add a "Running the panel" section:

```markdown
## Running the panel

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d
qs ipc -p quickshell/hyprkbm call hyprkbm state     # what it shows, as JSON
qs log -p quickshell/hyprkbm                         # QML warnings and errors
qs kill -p quickshell/hyprkbm
```

The IPC target can select keys, search and open the editor, but has no way to
apply: a scripted check must never change a real session. Logic belongs in
`quickshell/hyprkbm/lib/*.js` with a test in `tests/js/`; QML only binds and
draws. Lint with
`find quickshell -name '*.qml' -print0 | xargs -0 qmllint -I "$(qtpaths6 --query QT_INSTALL_QML)"`.
```

and add rows for `quickshell/hyprkbm/` and `tests/js/` to its layout table.

Run: `python3 -m pytest tests/ -q && node --test tests/js/`
Expected: all pass.

```bash
git add README.md CONTRIBUTING.md
git commit -m "docs: document the keyboard panel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Re-install so the desktop entry is linked**

Run: `./install.sh && hyprkbm --status`
Expected: `linked … hyprkbm.desktop`, the watcher `active`.

- [ ] **Step 3: Live round trip through the panel** (controller, with the user's consent)

Open the panel with `hyprkbm`. Then, by hand in the window:
1. Select SUPER and the key F12 with CTRL and ALT also on; **+ Add a bind** → action "Run a command", command `notify-send "hyprKBM panel works"`, description `panel test`; Save. The staged bar shows `+1 bind`.
2. **Review diff**: the new `hl.bind` line is added; no errors. Apply. The status says "Applied."; the bar clears.
3. Press SUPER+CTRL+ALT+F12: the notification appears.
4. `hyprctl reload`; the panel still lists the bind; pressing it still works (the watcher).
5. Open **Backups**, pick the newest entry: its diff removes the test bind. Restore it. The test bind disappears from the panel and from `hyprctl binds`.

Expected: each step as described; `qs log -p quickshell/hyprkbm` shows no QML errors.

- [ ] **Step 4: Check the theme and layout**

In ⋯ switch to ISO: the keyboard redraws with the ISO Enter and the `<` key; switch back to ANSI. In Theme, pick `paper`: the panel turns light; pick `fuji` again.

- [ ] **Step 5: Record the result**

If anything differs, fix it under superpowers:systematic-debugging with a regression test (JS or source-level) before continuing. Note the Hyprland and Quickshell versions verified against in the PR description.
