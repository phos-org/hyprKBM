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

## Live-check feedback (2026-10-19)

The user's findings from the live test of Tasks 1–2, with their choices: "exec" finds nothing; after a click, Tab walks the buttons instead of the areas (decided: Tab/Shift+Tab always move between areas, buttons never take focus from a click); the focus highlight is too subtle; and a new indicator for keys bound under other modifier combinations (decided: picking one in the list switches the modifier view to it).

### Task 3: Search finds binds by what they do

**Files:** `quickshell/hyprkbm/lib/search.js`, `tests/js/search.test.mjs`, `quickshell/hyprkbm/components/Header.qml` (placeholder/tooltip text only, if it lists the tags).

- [ ] Plain words also match the bind's dispatcher name (`bind.dispatcher.dsp`, e.g. `exec_cmd`), so `exec` lists every bind that runs a command, `workspace` every workspace bind, and so on. A bind with no dispatcher (raw Lua) still matches on its other text.
- [ ] A tag with nothing after the colon is no longer a word; it means "has one": `exec:` runs a command, `desc:` has a description, `mod:` has at least one modifier; `key:`, `submap:` and `src:` with no value match everything. (Change the token regex to accept an empty value; keep unknown `foo:` a word.)
- [ ] Node tests first: `exec` and `exec:` match an exec bind and not a `killactive` bind; `exec:kit` still narrows; `desc:` / `mod:` empty cases; `foo:` stays a word; `matchingKeys` follows (it already uses `matches`).
- [ ] Commit: `fix: find binds by their action's name, and let an empty tag mean "has one"`.

### Task 4: Tab always moves between areas, and focus is easy to see

**Files:** `quickshell/hyprkbm/components/Action.qml`, `shell.qml`, `components/Editor.qml`, `components/BindPanel.qml`, `components/Header.qml`, `components/ModifierBar.qml` (any clickable that can take focus), `lib/focus.js` + tests if logic is added, `tests/test_panel_qml.py`.

Behaviour to reach (the mechanism is the implementer's call; check it with qmllint and the smoke test):
- [ ] Clicking a button, a modifier toggle, a keycap or any other non-text control never leaves keyboard focus on that control: the panel's FocusScope keeps the keys, so the next Tab moves to the next area. `Action` gets `focusPolicy: Qt.TabFocus` (not focused by a click; still reachable by Tab inside dialogs and popups, which have their own focus chains). Text fields (search, editor fields) still take focus on click, as they must.
- [ ] Tab / Shift+Tab from the search field go to the next / previous area (leaving the field), as from anywhere else in the main window.
- [ ] Inside the editor, Tab / Shift+Tab move between the editor's own controls (fields, selects, toggles; not its buttons, which have shortcuts or are clicked); Tab from its last control goes to the next area and Shift+Tab from its first goes to the previous one. Esc still cancels the draft.
- [ ] Dialogs and popups (diff, backups, export, submap, settings, theme) are untouched by this: Tab inside them walks their own buttons and fields.
- [ ] Stronger focus: the focused area gets a 3 px `Colors.accentPrimary` border and a faint accent tint on its background (use `Qt.tint` with a low amount, as KeyCap's `lit()` does; never translucent over the pane). A focused `Action` (in dialogs) gets a 2 px `Colors.accentPrimary` border instead of `borderStrong`. A focused editor field / search field gets a 2 px `Colors.accentPrimary` border.
- [ ] Source-level tests: Action has `focusPolicy: Qt.TabFocus`; the Tab handling runs before the text-input guard (so it works from the search field) but after the find branch; the editor exposes how it walks its controls; the area border width is 3.
- [ ] Smoke test (IPC only; no key presses in the live panel). Commit: `fix: keep Tab for moving between areas, and make focus easy to see`.

### Task 5: Show where a key is bound under other modifiers

**Files:** `quickshell/hyprkbm/lib/keymap.js`, `tests/js/keymap.test.mjs`, `state/Store.qml`, `components/KeyCap.qml`, `components/KeyBlock.qml` / `ExtraKeys.qml` (wherever the kind is chosen), `components/ModifierBar.qml` (legend), `components/BindPanel.qml`, `components/BindRow.qml` if a variant is needed, `shell.qml` (list keys), `tests/test_panel_qml.py`.

**Interfaces produced:** `Keymap.otherKeys(binds, submap, mods) -> {keyId: true}` — keys with at least one placeable bind (`combo !== null`) in `submap` whose mods differ from `mods`, and none under `mods` exactly; `Keymap.otherCombos(binds, submap, mods, keyId) -> [bind]` — the binds on `keyId` in `submap` under any other modifier set (including none), sorted by `Keys.sortMods(mods).join("+")` then by their original order; Store: `property var otherCombos` (empty while searching or with no key selected), `property var listRows` (= `listed` then `otherCombos`, the rows the list cursor walks), `function focusedRow() -> {kind: "bind"|"other", bind} | null`.

- [ ] Node tests first: SUPER view, only SUPER+SHIFT+D bound → D in `otherKeys`, not in `keyStates`; a key bound under SUPER and SUPER+SHIFT → in `keyStates` only; no-modifier view and a SUPER bind → in `otherKeys`; other submaps ignored; `combo === null` ignored; `otherCombos` excludes the current mods, includes the no-modifier bind, ordering.
- [ ] Keyboard: a new KeyCap kind `"other"`: no fill (the free key's `Colors.bgSurface`), a 2 px `lit(Colors.accentPrimary, 0.6)`-strength accent border, label in `Colors.textSecondary`. A key in `keyStates` keeps its current kind; `other` only applies to keys that are otherwise `free`. Selection still wins the border. The legend gets "other mods" with an outline-only swatch.
- [ ] List: under the selected key's binds (after the conflict note and removed rows, before "+ Add a bind…"), a section headed "Also bound as" (same small-caps style as "Stale"/"Unplaced"), one row per `otherCombos` bind showing its full keys (e.g. `SUPER + SHIFT + D`) and its action, styled like a BindRow but without Edit/Delete buttons. Clicking a row, or Enter on it with the list cursor there, calls `Store.setMods(bind.mods)` (the key stays selected; the list now shows that bind in context). E and Delete do nothing on these rows. Hidden while searching and when there is no selected key.
- [ ] The list cursor walks `listRows`: `Store.listIndex` is clamped against `listRows.length`; `focusedBind()` returns a bind only when the cursor is on a `listed` row (so E/Delete keep their meaning); Enter on an "other" row switches view; the focused row is highlighted and scrolled into view as BindRows are now.
- [ ] Source-level tests for the new kind, the legend entry, the section's visibility rules and Enter's dispatch on row kind. Smoke test with IPC `select`/`submap` (IPC only). Commit: `feat: show where a key is bound under other modifiers`.

### Task 6: Docs

- [ ] README "The panel" section: Find (F) and how it works (your binds pause for that one press, come back on Esc, on focus loss, after 10 s at most, or with SUPER+Escape); the keyboard map (Tab / Shift+Tab areas, arrows, Enter, Delete, E, A, F, /, Ctrl+D, Ctrl+Z, Ctrl+Enter, Esc); search words and tags (including empty tags); the outline for keys bound under other modifiers and the "Also bound as" section. CONTRIBUTING: lib/capture.js and lib/focus.js in the layout table. Commit: `docs: document finding binds and driving the panel by keyboard`.
