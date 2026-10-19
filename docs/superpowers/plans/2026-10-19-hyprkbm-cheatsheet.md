# hyprKBM Cheatsheet Overlay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `hyprkbm --cheatsheet` shows (and, run again, hides) a full-screen, read-only keyboard of your binds that follows the modifiers you hold, with descriptions on the keys; the panel's `⋯` menu offers to bind it to a key.

**Architecture:** A second Quickshell root file, `quickshell/hyprkbm/cheatsheet.qml`, next to the panel's `shell.qml`. `qs -p <file>` makes it a separate instance (its own `-n` and its own IPC) that still imports the panel's `components/`, `state/`, `config/` and `lib/`. It reuses `Store` (read-only use: it never stages) and the keyboard components, given two new inputs: `interactive` (off: keys ignore clicks, so a click falls through and closes the sheet) and `detailed` (on: keys show the description, else the action text). The window is a layer-shell surface on the overlay layer with exclusive keyboard focus, so it sees modifier presses. The CLI toggles: it asks a running sheet to close over IPC and launches one only when none answered.

**Tech Stack:** Quickshell 0.3.1 QML (`Quickshell.Wayland` layer shell, `Quickshell.Hyprland`), `.pragma library` JS + `node --test`, Python stdlib + pytest.

Builds on `main` at e475316 (panel merged, PR #9). Spec: `docs/superpowers/specs/2026-10-07-hyprkbm-design.md`, section "Cheatsheet":

> `hyprkbm --cheatsheet` opens the same keyboard component, read-only, on a full-screen overlay layer surface (namespace `hyprkbm-cheatsheet`). It follows the physically held modifiers and shows descriptions (falling back to the action label) instead of short labels. Esc or a click closes it. The user binds it to a key of their choice; the panel's `⋯` menu offers to add that bind.

## Global Constraints

- Layer namespace exactly `hyprkbm-cheatsheet`; the bind command exactly `hyprkbm --cheatsheet`.
- The cheatsheet never writes anything: no `Store.apply`, no staging, no `hyprctl eval`.
- QML only binds and draws; logic that can be pure goes in `quickshell/hyprkbm/lib/*.js` with a node test in `tests/js/` (loaded with `tests/js/load.mjs`: `const X = load("name")`, `plain()` for deep-equal).
- `tests/test_theme_presets.py` rejects `Colors.textTertiary` outside a `?` conditional.
- Files that import `QtQuick.Controls` and use our `Action` import Controls `as QC`.
- Never import `lib/keys.js` as `Keys` in a file with `Keys.on…` handlers (use `KeyNames`).
- Delegates reading outer ids: `pragma ComponentBehavior: Bound` + `required property`.
- No layout size may depend, through any chain, on itself (the panel once froze from such a loop): the key unit comes from the window's width only.
- QML lint: `find quickshell -name '*.qml' -print0 | xargs -0 /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml` — no new warnings in touched files.
- Tests: `python3 -m pytest -q` and `node --test tests/js/` must pass.
- SAFETY (live Hyprland session): never run bare `hyprkbm`, `hyprkbm --cheatsheet`, `hyprkbm --apply`, `hyprkbm-apply` without `--preview`, `install.sh`, or `hyprctl reload`. Implementers must NOT launch `cheatsheet.qml` (it takes the whole screen and the keyboard); the controller smoke-tests it with the user. The panel smoke test (`HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d -n`, IPC only, then `qs kill -p quickshell/hyprkbm`) is allowed.
- Commits `<type>: <description>`, a blank line, `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; never commit `.superpowers/`.

Measured on this machine: `qs ipc -p <path> call <target> <fn>` exits 255 when no instance of that config runs; `qs -p dir/file.qml` runs a single QML file as its own config.

---

### Task 1: `hyprkbm --cheatsheet` shows or hides the overlay

**Files:**
- Modify: `bin/hyprkbm` (docstring, new `CHEATSHEET` constant, `cmd_cheatsheet`, `main`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `CHEATSHEET = PANEL / "cheatsheet.qml"`; the overlay must answer `qs ipc -p <CHEATSHEET> call cheatsheet close` with exit 0 (Task 4 provides that handler).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_cli.py`):

```python
QS_IPC_NOBODY = r'''#!%(python)s
"""qs where no cheatsheet runs: ipc fails as the real one does (255)."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(["qs"] + sys.argv[1:]) + "\n")
sys.exit(255 if sys.argv[1:2] == ["ipc"] else 0)
'''


def nobody_running(stubs):
    qs = stubs.root / "qs"
    qs.write_text(QS_IPC_NOBODY % {"python": sys.executable})
    qs.chmod(0o755)


def test_cheatsheet_opens_when_none_is_running(home_env, stubs):
    nobody_running(stubs)

    res = run(home_env, "--cheatsheet")

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    calls = [c for c in stubs.calls() if c[0] == "qs"]
    assert calls[0][:2] == ["qs", "ipc"] and calls[0][-2:] == ["cheatsheet", "close"]
    launch = next(c for c in calls if is_launch(c))
    assert launch[2].endswith("quickshell/hyprkbm/cheatsheet.qml") and launch[3:] == ["-d", "-n"]


def test_cheatsheet_closes_the_one_that_is_running(home_env, stubs):
    # The default qs stub exits 0: a running sheet answered and closed.
    res = run(home_env, "--cheatsheet")

    assert res.returncode == 0, res.stderr
    calls = [c for c in stubs.calls() if c[0] == "qs"]
    assert len(calls) == 1 and calls[0][1] == "ipc"
    assert calls[0][2:4] == ["-p", calls[0][3]] and calls[0][3].endswith("cheatsheet.qml")


def test_cheatsheet_needs_quickshell(home_env, stubs):
    (stubs.root / "qs").unlink()

    res = run(home_env, "--cheatsheet")

    assert res.returncode == 1
    assert "Quickshell" in res.stderr
```

  Also delete any existing test asserting that `--cheatsheet` says "not in this version yet" (search `tests/` for `not in this version`).

- [ ] **Step 2: Run them to see them fail**

Run: `python3 -m pytest tests/test_cli.py -q -k cheatsheet`
Expected: FAIL (the command still prints "the cheatsheet overlay is not in this version yet").

- [ ] **Step 3: Implement.** In `bin/hyprkbm`:
  - Docstring: after the `hyprkbm` line add `  hyprkbm --cheatsheet         show the keybind cheatsheet, or hide it if shown`.
  - After `PANEL = ...`: `CHEATSHEET = PANEL / "cheatsheet.qml"`.
  - Add, after `cmd_panel`:

```python
def cmd_cheatsheet():
    """Toggles: a running sheet is asked to close; only when none answers is
    one started. Bound to one key, the same press shows and hides it."""
    if shutil.which("qs") is None:
        return fail("Quickshell (qs) is not installed; the cheatsheet needs it. "
                    "hyprkbm --export md writes a cheatsheet as Markdown")
    try:
        res = subprocess.run(["qs", "ipc", "-p", str(CHEATSHEET), "call", "cheatsheet", "close"],
                             capture_output=True, timeout=3)
        if res.returncode == 0:
            return 0
    except (OSError, subprocess.TimeoutExpired):
        pass  # treat as not running; -n below still stops a second sheet
    env = dict(os.environ, HYPRKBM_BIN=str(ROOT / "bin"))
    subprocess.Popen(["qs", "-p", str(CHEATSHEET), "-d", "-n"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return 0
```

  - In `main`, replace the `--cheatsheet` branch with `if argv == ["--cheatsheet"]: return cmd_cheatsheet()`.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit** — `feat: hyprkbm --cheatsheet shows the cheatsheet, or hides it`

---

### Task 2: Labels for the sheet, and recognising the cheatsheet bind

**Files:**
- Modify: `quickshell/hyprkbm/lib/labels.js`, `quickshell/hyprkbm/lib/layouts.js`
- Create: `quickshell/hyprkbm/lib/cheatsheet.js`
- Test: `tests/js/labels.test.mjs` (create if missing, else append), `tests/js/cheatsheet.test.mjs`, `tests/js/layouts.test.mjs` (append)

**Interfaces:**
- Produces: `Labels.sheetLabel(binds) -> string`; `Layouts.unitFor(width, max)` (max defaults to 48, so existing callers are unchanged); `Cheatsheet.COMMAND = "hyprkbm --cheatsheet"`, `Cheatsheet.isCheatsheetBind(bind) -> bool`, `Cheatsheet.keysOf(binds) -> [string]` (the `keys` of every global-submap bind that runs the cheatsheet, in order).

- [ ] **Step 1: Write the failing tests**

`tests/js/labels.test.mjs` (append these tests; create the file with the imports if it does not exist):

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const L = load("labels")
const b = (o) => Object.assign({ description: "", describe: "Run a command: kitty",
  dispatcher: { dsp: "exec_cmd", args: ["kitty"] } }, o)

test("the sheet shows the description, else the action", () => {
  assert.equal(L.sheetLabel([b({ description: "Terminal" })]), "Terminal")
  assert.equal(L.sheetLabel([b({})]), "Run a command: kitty")
  assert.equal(L.sheetLabel([b({ describe: "" })]), "kitty")
})

test("several binds on one key show the first and a count", () => {
  assert.equal(L.sheetLabel([b({ description: "A" }), b({ description: "B" })]), "A (+1)")
  assert.equal(L.sheetLabel([]), "")
})
```

`tests/js/cheatsheet.test.mjs`:

```js
import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const C = load("cheatsheet")
const exec = (cmd, o) => Object.assign({ keys: "SUPER + F1", submap: "", combo: "x",
  dispatcher: { dsp: "exec_cmd", args: [cmd] } }, o)

test("the bind that runs the cheatsheet is recognised", () => {
  assert.equal(C.COMMAND, "hyprkbm --cheatsheet")
  assert.ok(C.isCheatsheetBind(exec("hyprkbm --cheatsheet")))
  assert.ok(C.isCheatsheetBind(exec("/home/u/.local/bin/hyprkbm  --cheatsheet")))
  assert.ok(!C.isCheatsheetBind(exec("hyprkbm")))
  assert.ok(!C.isCheatsheetBind(exec("hyprkbm --cheatsheets")))
  assert.ok(!C.isCheatsheetBind(exec("myhyprkbm --cheatsheet")))
  assert.ok(!C.isCheatsheetBind({ keys: "SUPER + F1", submap: "", dispatcher: null }))
})

test("keysOf lists global binds only", () => {
  assert.deepEqual(C.keysOf([exec("hyprkbm --cheatsheet"), exec("kitty", { keys: "SUPER + Q" }),
    exec("hyprkbm --cheatsheet", { keys: "SUPER + F2", submap: "resize" })]), ["SUPER + F1"])
})
```

`tests/js/layouts.test.mjs` (append):

```js
test("unitFor takes a larger cap for the full-screen sheet", () => {
  assert.equal(L.unitFor(10000), 48)
  assert.equal(L.unitFor(10000, 96), 96)
  assert.equal(L.unitFor(21.5 * 70, 96), 70)
})
```
(use whatever name the file already binds `load("layouts")` to.)

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/js/`
Expected: FAIL (`sheetLabel`/`cheatsheet` missing, `unitFor` ignores the cap).

- [ ] **Step 3: Implement**

`labels.js`, append:

```js
// The full-screen cheatsheet has room for words: the user's description, or
// the action as the bind list writes it.
function sheetLabel(binds) {
    if (binds.length === 0) return ""
    var first = binds[0]
    var text = first.description || first.describe || shortLabel(first)
    return binds.length > 1 ? text + " (+" + (binds.length - 1) + ")" : text
}
```

  Note: `shortLabel(b({describe: ""}))` gives `"kitty"`, which the test expects.

`layouts.js`: change `unitFor` to

```js
function unitFor(width, max) {
    return Math.max(26, Math.min(max === undefined ? 48 : max, Math.floor(width / ROW_UNITS)))
}
```

`cheatsheet.js`:

```js
.pragma library

// The bind that opens the cheatsheet, so the ⋯ menu can say which key it is
// on, or offer to add one.

var COMMAND = "hyprkbm --cheatsheet"

function isCheatsheetBind(bind) {
    var d = bind.dispatcher
    if (!d || d.dsp !== "exec_cmd" || typeof (d.args || [])[0] !== "string") return false
    return /^(\S*\/)?hyprkbm\s+--cheatsheet(\s|$)/.test(d.args[0].trim())
}

function keysOf(binds) {
    return binds.filter(function (b) { return b.submap === "" && isCheatsheetBind(b) })
                .map(function (b) { return b.keys })
}
```

- [ ] **Step 4: Run tests** — `node --test tests/js/` passes.
- [ ] **Step 5: Commit** — `feat: labels for the cheatsheet, and a way to find its bind`

---

### Task 3: The keyboard can be read-only and detailed

**Files:**
- Modify: `quickshell/hyprkbm/components/Keyboard.qml`, `KeyBlock.qml`, `ExtraKeys.qml`, `KeyCap.qml`
- Test: `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Labels.sheetLabel(binds)` (Task 2).
- Produces: on `Keyboard`, `KeyBlock` and `ExtraKeys`: `property bool interactive: true`, `property bool detailed: false` (Keyboard passes both to its KeyBlocks); on `KeyCap`: `property int subLines: 1`. The panel's look and behaviour must not change (defaults).

- [ ] **Step 1: Write the failing source tests** (append to `tests/test_panel_qml.py`, which defines `qml(*parts)` returning a file's text):

```python
def test_the_keyboard_can_be_read_only_and_detailed():
    kb = qml("components", "Keyboard.qml")
    assert "property bool interactive: true" in kb and "property bool detailed: false" in kb
    assert kb.count("interactive: root.interactive") == 2 and kb.count("detailed: root.detailed") == 2
    for name in ("KeyBlock.qml", "ExtraKeys.qml"):
        src = qml("components", name)
        assert "property bool interactive: true" in src and "property bool detailed: false" in src
        assert "Labels.sheetLabel(" in src
        assert "root.interactive" in src
    block = qml("components", "KeyBlock.qml")
    assert "enabled: root.interactive && modelData.gap !== true" in block
    extra = qml("components", "ExtraKeys.qml")
    assert "visible: root.interactive" in extra  # the "+ any key…" button
    cap = qml("components", "KeyCap.qml")
    assert "property int subLines: 1" in cap and "maximumLineCount: root.subLines" in cap
```

- [ ] **Step 2: Run** `python3 -m pytest tests/test_panel_qml.py -q -k read_only` — FAIL.

- [ ] **Step 3: Implement**
  - `Keyboard.qml`: add `property bool interactive: true` and `property bool detailed: false`; on both `KeyBlock`s add `interactive: root.interactive; detailed: root.detailed`.
  - `KeyBlock.qml`: add both properties. In `subOf`: `return root.detailed ? Labels.sheetLabel(i.binds) : (i.binds.length > 1 ? i.binds.length + " binds" : Labels.shortLabel(i.binds[0]))`. In the KeyCap delegate: `enabled: root.interactive && modelData.gap !== true` (a disabled KeyCap's MouseArea takes no clicks, so they reach whatever is underneath) and `subLines: root.detailed ? 3 : 1`.
  - `ExtraKeys.qml`: same two properties; `subOf` uses `Labels.sheetLabel(i.binds)` when `root.detailed`; KeyCap delegate `enabled: root.interactive`, `subLines: root.detailed ? 3 : 1`; the `+ any key…` Action gets `visible: root.interactive`.
  - `KeyCap.qml`: add `property int subLines: 1`; the `sub` Text gets `wrapMode: root.subLines > 1 ? Text.Wrap : Text.NoWrap`, `maximumLineCount: root.subLines` (keep `elide: Text.ElideRight`). Keep the cap's own `height: unit - 4`; the text must not size the cap.
- [ ] **Step 4: Run** `python3 -m pytest -q`, `node --test tests/js/`, qmllint, and the panel smoke test (IPC `state`, `select q SUPER`; the log must have no errors / binding loops). Then `qs kill -p quickshell/hyprkbm`.
- [ ] **Step 5: Commit** — `feat: let the keyboard be shown read-only, with descriptions`

---

### Task 4: The overlay

**Files:**
- Create: `quickshell/hyprkbm/cheatsheet.qml`
- Test: `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: Task 3's `interactive`/`detailed`; `Layouts.unitFor(width, 96)`; `QtKeys.heldMods(key, modifiers, pressed)`, `QtKeys.modifierFromQtKey(key)`, `QtKeys.modsFromQt(modifiers)`; `Store.heldMods`, `Store.mods`, `Store.loading`, `Store.loadError`, `Store.keyStates`.
- Produces: IPC target `cheatsheet` with `close()` (Task 1 relies on its exit 0) and `state()`.

- [ ] **Step 1: Write the failing source tests**

```python
def test_the_cheatsheet_is_a_read_only_overlay():
    sheet = (PANEL / "cheatsheet.qml").read_text()
    assert 'WlrLayershell.namespace: "hyprkbm-cheatsheet"' in sheet
    assert "WlrLayer.Overlay" in sheet and "WlrKeyboardFocus.Exclusive" in sheet
    assert "interactive: false" in sheet and "detailed: true" in sheet
    assert 'target: "cheatsheet"' in sheet and "function close()" in sheet
    # Never writes: nothing that stages, applies or evals.
    for forbidden in ("Store.apply", "saveDraft", "newBind", "hyprctl", "Store.edit"):
        assert forbidden not in sheet
    # Esc closes; modifiers are followed on press and release.
    assert "Qt.Key_Escape" in sheet and "Keys.onReleased" in sheet
    assert "QtKeys.heldMods(" in sheet
```

- [ ] **Step 2: Run** — FAIL (file missing).

- [ ] **Step 3: Write `quickshell/hyprkbm/cheatsheet.qml`:**

```qml
import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import "config"
import "components"
import "state"
import "lib/qtkeys.js" as QtKeys
import "lib/layouts.js" as Layouts
import "lib/keys.js" as KeyNames

// `hyprkbm --cheatsheet`: the panel's keyboard, read-only and full screen,
// lit by the modifiers you hold. It shares the panel's Store to read binds
// and never stages or applies anything. Esc or a click closes it.
ShellRoot {
    PanelWindow {
        id: sheet
        // The output you are looking at.
        screen: Quickshell.screens.find(function (s) {
            return Hyprland.focusedMonitor !== null && s.name === Hyprland.focusedMonitor.name
        }) || Quickshell.screens[0]
        anchors { top: true; left: true; right: true; bottom: true }
        exclusionMode: ExclusionMode.Ignore
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "hyprkbm-cheatsheet"
        // Exclusive, so modifier presses and releases come here.
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        IpcHandler {
            target: "cheatsheet"
            function close(): string { Qt.callLater(Qt.quit); return "closed" }
            function state(): string {
                return JSON.stringify({ loading: Store.loading, error: Store.loadError,
                                        mods: Store.mods, keys: Object.keys(Store.keyStates).length })
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Colors.bgVoid
            opacity: 0.9
        }

        // Anywhere a key does not take it (and keys take none here).
        MouseArea {
            anchors.fill: parent
            onClicked: Qt.quit()
        }

        FocusScope {
            anchors.fill: parent
            focus: true

            // Modifiers already down when the sheet opened show up with the
            // first press or release of any key, through event.modifiers.
            Keys.onPressed: function (event) {
                event.accepted = true
                if (event.key === Qt.Key_Escape) { Qt.quit(); return }
                if (event.isAutoRepeat) return
                Store.heldMods = QtKeys.modifierFromQtKey(event.key) !== ""
                    ? QtKeys.heldMods(event.key, event.modifiers, true)
                    : QtKeys.modsFromQt(event.modifiers)
            }
            Keys.onReleased: function (event) {
                event.accepted = true
                if (event.isAutoRepeat) return
                if (QtKeys.modifierFromQtKey(event.key) !== "")
                    Store.heldMods = QtKeys.heldMods(event.key, event.modifiers, false)
            }

            ColumnLayout {
                anchors.centerIn: parent
                spacing: Spacing.lg

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: Store.mods.length === 0 ? "Keybinds · no modifier"
                        : "Keybinds · " + KeyNames.display(Store.mods, "").replace(/ \+ $/, "")
                    color: Colors.textPrimary
                    font.family: Typography.family
                    font.pixelSize: Math.round(Typography.sizeBody * 1.8)
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    visible: Store.loading || Store.loadError !== ""
                    text: Store.loadError !== "" ? Store.loadError : "Loading…"
                    color: Store.loadError !== "" ? Colors.statusCritical : Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeBody
                }

                RowLayout {
                    visible: !Store.loading && Store.loadError === ""
                    spacing: Spacing.lg
                    // From the output's width only: nothing inside feeds back.
                    readonly property real unit: Layouts.unitFor(sheet.width * 0.8, 96)
                    Keyboard { unit: parent.unit; interactive: false; detailed: true }
                    ExtraKeys { unit: parent.unit; interactive: false; detailed: true; Layout.alignment: Qt.AlignTop }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Hold SUPER, SHIFT, CTRL or ALT · Esc or a click closes"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }
            }
        }
    }
}
```

  Verified while planning: `Typography` has only `sizeBody` (13) and `sizeSmall` (11); `KeyNames.display(["SUPER","SHIFT"], "")` is `"SUPER + SHIFT + "` (hence the `replace`); `Store.loading` / `Store.loadError` exist; `ExtraKeys` reads `Store.extras`. `Keyboard` sets only `implicitHeight`, so inside the RowLayout give it `Layout.preferredWidth` computed the way `shell.qml` sizes its keyboard row (read how `ROW_UNITS` in `lib/layouts.js` is defined and what `shell.qml` subtracts), never from its own children.
  qmllint must be clean for this file. Do NOT run it (see Global Constraints): the controller will.

- [ ] **Step 4: Run** `python3 -m pytest -q`, `node --test tests/js/`, qmllint.
- [ ] **Step 5: Commit** — `feat: the cheatsheet overlay`

---

### Task 5: The ⋯ menu offers a key for the cheatsheet

**Files:**
- Modify: `quickshell/hyprkbm/state/Store.qml`, `quickshell/hyprkbm/components/SettingsPopup.qml`
- Test: `tests/test_panel_qml.py`

**Interfaces:**
- Consumes: `Cheatsheet.COMMAND`, `Cheatsheet.keysOf(binds)` (Task 2).
- Produces: Store `readonly property var cheatsheetKeys: Cheatsheet.keysOf(merged.binds)`; `function newCheatsheetBind()`.

- [ ] **Step 1: Write the failing source tests**

```python
def test_the_menu_offers_a_cheatsheet_key():
    store = qml("state", "Store.qml")
    assert "Cheatsheet.keysOf(merged.binds)" in store
    body = store.split("function newCheatsheetBind()", 1)[1].split("\n    }\n", 1)[0]
    assert "newBind(" in body and "Cheatsheet.COMMAND" in body
    popup = qml("components", "SettingsPopup.qml")
    assert "Store.cheatsheetKeys" in popup and "Store.newCheatsheetBind()" in popup
    assert "root.close()" in popup.split("Store.newCheatsheetBind()", 1)[1][:80]
```

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**
  - Store.qml: `.import`-style QML import `import "../lib/cheatsheet.js" as Cheatsheet`; the property above; and

```qml
    // The ⋯ menu's offer: a bind that opens the cheatsheet, keys left for the
    // user to record. It goes through the editor like any other new bind.
    function newCheatsheetBind() {
        newBind("")
        if (draft === null) return
        patchDraft({ submap: "", action: { kind: "exec_cmd", args: { cmd: Cheatsheet.COMMAND } },
                     description: "Keybind cheatsheet" })
    }
```

  - SettingsPopup.qml: a `Field` labelled `Cheatsheet key`, placed after "Keyboard layout", containing a RowLayout: a Text showing `Store.cheatsheetKeys.length > 0 ? Store.cheatsheetKeys.join(", ") : "None yet"` (`Colors.textPrimary`, `Typography.sizeBody`, `Layout.fillWidth: true`) and an `Action` with `text: Store.cheatsheetKeys.length > 0 ? "Add another" : "Add a key"`, `enabled: !Store.readOnly && Store.draft === null && !Store.busy`, `onClicked: { Store.newCheatsheetBind(); root.close() }`. Field's `hint`: `"Runs hyprkbm --cheatsheet. Record the keys in the editor, then Save and Apply."`
- [ ] **Step 4: Run** pytest, node, qmllint, the panel smoke test (IPC only; do not click the new button).
- [ ] **Step 5: Commit** — `feat: offer a key for the cheatsheet in the ⋯ menu`

---

### Task 7: Press a combo to see it; Enter runs it

The user's request after seeing the overlay (2026-10-19): "Let's say I select super+shift+d, which is discord. When I'm in cheatsheet, can we give the thing that will be ran (discord in the example) where the mods are now selected, and only let it run if I press enter?" Long labels stay clipped on the keys (the user likes how it looks); the full action is shown in the title area instead.

Hyprland runs a bound combo before any client sees it, so while the sheet is open Hyprland is held in a submap, `hyprkbm-cheatsheet`, whose only bind is SUPER+Escape → reset (as find mode does with `hyprkbm-capture`). A dead-man switch, not the watcher, guarantees the binds come back if the sheet dies: the sheet re-arms a 15 s `hl.timer` every 5 s, and each timer resets only if no newer one was armed since.

**Files:** `quickshell/hyprkbm/lib/cheatsheet.js`, `tests/js/cheatsheet.test.mjs`, `quickshell/hyprkbm/cheatsheet.qml`, `quickshell/hyprkbm/components/KeyBlock.qml`, `ExtraKeys.qml`, `tests/test_panel_qml.py`.

**Interfaces (lib/cheatsheet.js, all pure):**
- `SUBMAP = "hyprkbm-cheatsheet"`, `ARM_EVERY_MS = 5000`, `HOLD_MS = 15000`.
- `holdLua(token) -> string`: defines the submap (one bind, `SUPER + Escape` → `hl.dsp.submap("reset")`) only if `hl.get_current_submap() ~= SUBMAP` is about to be entered (define + dispatch when not already in it; just re-arm when in it), sets the global `__hyprkbm_sheet = token`, and starts `hl.timer(function() if __hyprkbm_sheet == <token> and hl.get_current_submap() == SUBMAP then hl.dispatch(hl.dsp.submap("reset")) end end, { timeout = HOLD_MS, type = "oneshot" })`. `token` is an integer (the sheet passes `Date.now()`), written as a Lua number.
- `leaveLua() -> string`: `__hyprkbm_sheet = nil` and the guarded reset (only if the current submap is SUBMAP).
- `runnable(bind) -> string`: `""` when Enter can run it, else the reason shown to the user: `"a Lua function"` when the dispatcher has `__function` or no `dsp`/`raw`; `"a mouse bind"` when `bind.opts && bind.opts.mouse`; `"not readable"` for a null dispatcher.
- `runLua(binds) -> string | null`: `leaveLua()` followed by one `hl.dispatch(<Catalogue.dispatcherLua(d)>)` per runnable bind (raw Lua wrapped as `hl.dispatch((\n<raw>\n))`, as catalogue.py does), in order; `null` when none is runnable. Leaving first means the action runs with the binds already back.
- `opensSheet(binds) -> bool`: some bind in the list `isCheatsheetBind`.

**Behaviour (cheatsheet.qml):**
- [ ] On show, eval `holdLua(Date.now())` (Quickshell `Process` running `["hyprctl", "eval", lua]`; for the final leave/run use `Quickshell.execDetached` so it survives the quit), and re-eval it from a `Timer` every `ARM_EVERY_MS`. Every way the sheet closes (Esc, click, IPC `close()`, Enter) runs `leaveLua()` (or `runLua`) through `execDetached` before quitting.
- [ ] A press of a non-modifier key (no auto-repeat, not Esc, not Enter/Return) selects a combo: `mods = QtKeys.modsFromQt(event.modifiers)`, `key = QtKeys.keysymFromQt(event.key, event.modifiers)` (see `Capture.comboFrom`), and the binds are `Keymap.bindsOn(Store.merged.binds, "", mods, Keys.keyId(key))`. If they include the cheatsheet's own bind (`opensSheet`), close the sheet instead (its key toggles it, even while binds are paused). Otherwise keep `{ mods, key, binds }` as the selection and select the key on the keyboard (`Store.selectedKey`), so it is outlined.
- [ ] The title area shows, with a selection: the combo (`KeyNames.display(mods, Layouts.keyName(Store.layout, keyId))`) as the title, and below it the full action of each bind (`description` and `describe`, e.g. "Run a command: discord", not clipped) and the line "Enter runs it" — or "Not bound" when `binds` is empty, or "Can't run from here: <reason>" when `runLua(binds)` is null. Without a selection it shows the current title.
- [ ] Enter/Return with a runnable selection: hide the sheet, `execDetached(["hyprctl", "eval", runLua(binds)])`, quit (via the same delayed quit as `close()`). Enter without one does nothing.
- [ ] Holding modifiers still changes the keyboard as now; a new selection replaces the old one; Esc and a click still close.
- [ ] The read-only keyboard shows the selection again: drop Task 4's "selection only when interactive" gating in KeyBlock/ExtraKeys, and instead have the sheet clear `Store.selectedKey` whenever a load completes (Store selects Q on load) and when it starts.
- [ ] Footer: "Press a combo to see what it does · Enter runs it · Esc closes".
- [ ] Node tests first for every lib function (token in the Lua, the guard, `runLua` order and leave-first, raw wrapping, mouse/function reasons, null when nothing runs, `opensSheet`). Source tests: the sheet arms on a Timer, every quit path leaves (grep each `Qt.quit`/`quitSoon` caller is preceded by a leave or run), Enter only runs `runLua` output, the footer text.
- [ ] Commit: `feat: press a combo in the cheatsheet to see it, and Enter to run it`.

### Task 6: Docs

**Files:** `README.md`, `CONTRIBUTING.md`, `docs/superpowers/specs/2026-10-07-hyprkbm-design.md` (only if the build differs from the spec).

- [ ] (After Task 7.) README: a "### The cheatsheet" subsection under "The panel": `hyprkbm --cheatsheet` shows it and running it again hides it (so one key toggles); bind it from the ⋯ menu or by hand (`hl.bind("SUPER + F1", hl.dsp.exec_cmd("hyprkbm --cheatsheet"))`); it covers the focused output, follows the modifiers you hold (ones already held when it opens show from the next key press or release), shows descriptions or the action, global submap only; pressing a combo shows what it does and Enter runs it; your binds are paused while it is open (SUPER+Escape or 15 s after a crash brings them back); Esc or a click closes; it changes nothing on disk. Add `--cheatsheet` to the command list wherever the README lists commands; remove any "not in this version yet" text.
- [ ] CONTRIBUTING layout table: `quickshell/hyprkbm/cheatsheet.qml` (the overlay, its own qs instance) and `lib/cheatsheet.js`.
- [ ] Run `python3 -m pytest -q` (README assertions exist in tests). Commit — `docs: document the cheatsheet`.
