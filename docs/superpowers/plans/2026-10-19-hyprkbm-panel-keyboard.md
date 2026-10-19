# hyprKBM Panel: Keyboard-Driven Use — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the panel be used without the mouse: press a keybind to find it (even one Hyprland has bound), move through the bind list, act with single keys, and Tab between areas.

**Architecture:** Hyprland grabs bound combos before the focused window sees them. "Find mode" switches Hyprland into a submap, `hyprkbm-capture`, whose only bind is SUPER+Escape (an empty submap is not registered); while it is active, every other combo reaches the panel. The panel leaves the submap on the first key it captures, on Escape, focus loss and close; a Hyprland `hl.timer` started together with the switch resets it after 10 s no matter what the panel does, and hyprkbm-watch resets it when the active window is not the panel. Logic that can be pure lives in `lib/*.js` with node tests; the QML binds and draws.

**Tech Stack:** Quickshell 0.3.1 QML, `.pragma library` JS + `node --test`, Python stdlib + pytest, Hyprland 0.56 Lua (`hyprctl eval`).

Builds on `feat/panel` (HEAD afc79f0). Spec: `docs/superpowers/specs/2026-10-07-hyprkbm-design.md` ("The panel: keyboard view", "Panel architecture").

## Global Constraints

Everything in `.superpowers/sdd/panel/constraints.md` (the panel plan's constraints) applies, plus these, learned while building the panel:
- `tests/test_theme_presets.py` rejects `Colors.textTertiary` outside a `?` conditional.
- Files that import `QtQuick.Controls` and use our `Action` import Controls `as QC`.
- Never import `lib/keys.js` as `Keys` in a file with `Keys.on…` handlers (use `KeyNames`).
- Delegates reading outer ids: `pragma ComponentBehavior: Bound` + `required property`.
- No layout size may depend, through any chain, on itself (the panel froze from one such loop). Nested layouts fill spare height by default — set `Layout.fillHeight: false` where they must not.
- QML lint: `find quickshell -name '*.qml' -print0 | xargs -0 /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml`.
- Smoke: `HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d -n`; after each IPC call `timeout 3 qs ipc -p quickshell/hyprkbm call hyprkbm state` must answer within 3 s; `qs log -p quickshell/hyprkbm` must have no error / Binding loop / recursive rearrange lines; always `qs kill -p quickshell/hyprkbm` and confirm `qs list --all` is empty.
- SAFETY: live Hyprland. Never run bare `hyprkbm`, `hyprkbm --apply`, `hyprkbm-apply` without `--preview`, install.sh or `hyprctl reload`; never Save/Apply/Restore in the panel. Implementers must NOT enter find mode on the live session (it turns the user's binds off); the controller tests it with the user.
- Commits `<type>: <description>`, ending with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; never commit `.superpowers/`.

Verified on this machine (Hyprland 0.56.2): `hl.define_submap(name, fn)` with no binds is not registered ("submap doesn't exist"); with one bind it is. `hl.dispatch(hl.dsp.submap(name))` switches; `hl.get_current_submap()` returns `""` for the default; `hl.timer(fn, { timeout = ms, type = "oneshot" })` fires and can reset with `hl.dsp.submap("reset")`.

---

### Task 1: Find mode

**Files:** `quickshell/hyprkbm/lib/capture.js` (new), `tests/js/capture.test.mjs` (new), `quickshell/hyprkbm/state/Store.qml`, `quickshell/hyprkbm/shell.qml`, `quickshell/hyprkbm/components/Header.qml`, `bin/hyprkbm-watch`, `tests/test_watch.py`, `tests/test_panel_qml.py`.

**Interfaces produced:** `Capture.SUBMAP = "hyprkbm-capture"`, `Capture.TIMEOUT_MS = 10000`, `Capture.enterLua() -> string`, `Capture.leaveLua() -> string`, `Capture.comboFrom(key, modifiers) -> {mods, key} | null` (null for a modifier-only press; uses QtKeys.keysymFromQt with modifiers and QtKeys.modsFromQt); Store: `property bool finding`, `function startFind()`, `function stopFind()`, `function found(mods, key)`; IPC: no find entry point (find turns binds off; it must only ever be started by a person in the window).

- [ ] Write `lib/capture.js` and its node tests first. `enterLua()` returns exactly this Lua (one string), which the Store sends with `hyprctl eval`:

```lua
hl.define_submap("hyprkbm-capture", function()
    hl.bind("SUPER + Escape", hl.dsp.submap("reset"))
end)
hl.dispatch(hl.dsp.submap("hyprkbm-capture"))
hl.timer(function()
    if hl.get_current_submap() == "hyprkbm-capture" then
        hl.dispatch(hl.dsp.submap("reset"))
    end
end, { timeout = 10000, type = "oneshot" })
```

  `leaveLua()` returns `if hl.get_current_submap() == "hyprkbm-capture" then hl.dispatch(hl.dsp.submap("reset")) end`. Tests: the strings contain the submap name, the timeout, the SUPER+Escape bind; `comboFrom(0x4d /*M*/, 0x10000000 /*Meta*/)` → `{mods:["SUPER"], key:"M"}`; Shift+1 → `{mods:["SHIFT"], key:"1"}`; a modifier key alone → null; Escape → `{mods:[], key:"Escape"}` (the caller treats bare Escape as "cancel").

- [ ] Store.qml: `finding` flag; `startFind()` (no-op if already finding, busy, or a draft is open) sets `finding = true`, `report("Press the keybind to find… (Esc cancels)", false)` and runs a Process `["hyprctl", "eval", Capture.enterLua()]`; on a non-zero exit it sets `finding = false` and reports the error. `stopFind()` (no-op unless finding) sets `finding = false` and runs `["hyprctl", "eval", Capture.leaveLua()]`. `found(mods, key)`: `stopFind()`, `heldMods = []`, `setMods(mods)`, `selectKey(key)`, `query = ""`, `report("", false)`. Comments explain why each guard exists.

- [ ] shell.qml: in the FocusScope's `Keys.onPressed`, before everything else (including the text-input guard is fine — find can't start from a field), when `Store.finding`: accept the event; bare Escape → `Store.stopFind()`; otherwise `var c = Capture.comboFrom(event.key, event.modifiers)`; if `c !== null` → `Store.found(c.mods, c.key)`; modifier-only presses just update `Store.heldMods` via `QtKeys.heldMods` so the keyboard shows them live. `F` (no modifiers, not in a text field, no draft) → `Store.startFind()`. Leave find mode whenever the scope loses active focus or the window becomes inactive (next to the existing heldMods clearing), and in `onClosed` before `Qt.quit()`.

- [ ] Header.qml: a "Find (F)" Action that calls `Store.startFind()`; while `Store.finding` it reads "Press a keybind…" and clicking it calls `Store.stopFind()`. It must not take focus (`focusPolicy: Qt.NoFocus`), or clicking it would end find mode through focus loss.

- [ ] hyprkbm-watch: a backstop for a panel that died mid-find. Track the current submap from `submap>>NAME` events and the active window from `activewindow>>CLASS,TITLE` events; when the submap is `hyprkbm-capture` and the active window is not class `org.quickshell` with title `Keybinds`, run `hyprctl eval '<leave Lua>'` (same Lua as `Capture.leaveLua()`, as a Python constant with a comment pointing at capture.js). Pure helper `should_leave_capture(submap, active_class, active_title) -> bool` with pytest cases, and a `read_events` replay test (socketpair) showing the reset runs for `submap>>hyprkbm-capture` then `activewindow>>kitty,~` and not when the panel is active. Keep the existing reload handling intact.

- [ ] Source-level tests in tests/test_panel_qml.py: find handling comes first in Keys.onPressed; F starts find; focus loss / window inactive / onClosed call stopFind; the IPC handler has no startFind; Header's Find action has `focusPolicy: Qt.NoFocus`.

- [ ] Run node, pytest, qmllint, smoke (WITHOUT pressing F or calling startFind). Commit: `feat: find a bind by pressing it, even one Hyprland has bound`.

### Task 2: Bind list navigation and action shortcuts

**Files:** `quickshell/hyprkbm/lib/focus.js` (new, pure), `tests/js/focus.test.mjs`, `state/Store.qml`, `shell.qml`, `components/BindPanel.qml`, `components/BindRow.qml`, `components/StagedBar.qml`, `components/Editor.qml`, `tests/test_panel_qml.py`.

**Interfaces produced:** `Focus.AREAS = ["keyboard", "list", "editor"]`, `Focus.next(area, hasEditor) -> area` (skips "editor" when no draft), `Focus.clampIndex(index, length) -> index` (−1 when empty); Store: `property string area: "keyboard"`, `property int listIndex: 0` (reset to 0 when `listed` changes), `function focusedBind() -> bind | null`.

- [ ] lib/focus.js + node tests first (cycle order, skipping editor, wrap-around, clamping, empty list).
- [ ] Keyboard handling in shell.qml's FocusScope (after the text-input and find guards):
  - Tab / Shift+Tab: `Store.area = Focus.next(...)` (Shift+Tab goes backwards — add `Focus.prev` with a test); moving into "editor" focuses the editor's Keys field (expose `function focusFirst()` on Editor); leaving it returns focus to the scope.
  - In area "keyboard": arrows move the key selection (as now).
  - In area "list": Up/Down change `Store.listIndex` (clamped); Enter edits `Store.focusedBind()`; Delete removes it (`Store.deleteBind(uid)`).
  - Shortcuts, valid in keyboard and list areas, never while a text field has focus: `E` edit the focused bind (list) or the first bind on the selected key (keyboard); `A` add a bind on the selected key (`Store.newBindOnSelected()`); `Ctrl+D` open the diff dialog when dirty; `Ctrl+Z` discard when dirty. (`F` is Task 1.)
- [ ] BindPanel/BindRow: the row at `Store.listIndex` is highlighted when `Store.area === "list"`; the list scrolls to keep it visible.
- [ ] A visible focus ring (a 1–2 px `Colors.accentPrimary` border) on the keyboard pane, the bind list and the editor shows which area has the keys.
- [ ] Hints on buttons: "Edit (E)", "+ Add a bind on … (A)", "Review diff (Ctrl+D)", "Discard (Ctrl+Z)", "Apply (Ctrl+Enter)".
- [ ] Source-level tests for the guard ordering (text-input guard before shortcuts; finding before all) and the hints. Run all checks and the smoke test (IPC only; do not press keys in the live panel). Commit: `feat: drive the bind list and the panel's actions from the keyboard`.

### Task 3: Docs

- [ ] README "The panel" section: Find (F) and how it works (your binds pause for that one press, come back on Esc, on focus loss, after 10 s at most, or with SUPER+Escape); the keyboard map (Tab areas, arrows, Enter, Delete, E, A, F, Ctrl+D, Ctrl+Z, Ctrl+Enter, Esc). CONTRIBUTING: lib/capture.js and lib/focus.js in the layout table. Commit: `docs: document finding binds and driving the panel by keyboard`.
