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
    ipc = shell.split("IpcHandler", 1)[1].split("FocusScope", 1)[0]
    assert "Store.apply()" not in ipc
    assert "Store.restoreBackup()" not in ipc


def test_the_store_reports_failures_and_keeps_staged_edits():
    store = qml("state", "Store.qml")
    layout = store.split("property Process layoutProc", 1)[1].split("property Process watcherProc", 1)[0]
    assert "StdioCollector" in layout and "root.report(" in layout
    adopt = store.split("function adopt(", 1)[1].split("// ----", 1)[0]
    assert "var hadEdits = root.dirty" in adopt
    assert adopt.index("hadEdits") < adopt.index("saved = ")
    apply_proc = store.split("property Process applyProc", 1)[1].split("property Process previewProc", 1)[0]
    assert "result.errors || []" in apply_proc
    assert "result.errors[0]" not in apply_proc
    for fn in ("newBind", "saveDraft", "edit", "deleteBind", "keepBoth", "addSubmap", "restoreHand"):
        body = store.split("function %s(" % fn, 1)[1].split("\n    }\n", 1)[0]
        assert "model === null" in body, fn
    assert "applied already" in store


def test_no_qml_property_shadows_a_builtin():
    builtins = {"data", "state", "size", "enabled", "visible", "rotation", "palette"}
    for name, source in all_qml().items():
        for prop in re.findall(r"\bproperty\s+\w+\s+(\w+)", source):
            assert prop not in builtins and not prop.startswith("on"), "%s: %s" % (name, prop)


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


def test_a_held_modifier_is_cleared_when_focus_or_the_window_goes_away():
    # A release that lands in another window never reaches the scope.
    shell = qml("shell.qml")
    assert re.search(r"onActiveFocusChanged:\s*if \(!activeFocus\) \{\s*Store\.heldMods = \[\]", shell)
    assert re.search(r"Window\.onActiveChanged:\s*if \(!Window\.active\) \{\s*Store\.heldMods = \[\]", shell)


def test_the_key_handlers_ignore_auto_repeat():
    shell = qml("shell.qml")
    assert shell.count("event.isAutoRepeat") >= 2
    # Only a modifier ignores auto-repeat on press, so a held arrow still repeats.
    handler = shell.split("Keys.onPressed", 1)[1].split("Keys.onReleased", 1)[0]
    assert handler.index("modifierFromQtKey") < handler.index("event.isAutoRepeat")


def test_text_fields_keep_their_arrows_and_enter():
    shell = qml("shell.qml")
    handler = shell.split("Keys.onPressed", 1)[1]
    guard = re.search(r"instanceof TextInput\s*\|\|[^)]*instanceof TextEdit", handler)
    assert guard
    assert guard.start() < handler.index("Store.moveSelection(")
    # Modifier tracking comes before the guard so SUPER still shows while typing.
    assert handler.index("Store.hold(") < guard.start()


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
    handler = shell.split("Keys.onPressed", 1)[1]
    # The text-field guard must come first, or "/" typed in the search re-focuses it.
    assert handler.index("instanceof TextInput") < handler.index("Qt.Key_Slash")


def test_read_only_panel_stages_nothing_and_hand_conflicts_do_not_block():
    store = qml("state", "Store.qml")
    for name in ("restoreHand", "keepBoth"):
        body = store[store.index("function %s(" % name):]
        body = body[:body.index("\n    }")]
        assert "readOnly" in body, name
    for part in (("components", "BindPanel.qml"), ("components", "BindRow.qml")):
        assert "Model.blocks(" in qml(*part), part
    row = qml("components", "BindRow.qml")
    keep = row[row.index('text: "Keep both"'):]
    assert "!Store.readOnly" in keep[:keep.index("}")]
    panel = qml("components", "BindPanel.qml")
    restore = panel[panel.index('text: "Restore"'):]
    assert "!Store.readOnly" in restore[:200]


def test_the_key_size_does_not_depend_on_the_keyboards_own_width():
    """The keyboard used to compute its key size from its own width, which is
    what the extra keys (three keys wide) leave over. Each depended on the
    other, and at some widths the layout never settled: the panel froze."""
    keyboard = qml("components", "Keyboard.qml")
    assert not re.search(r"unit\s*:.*\bwidth\b", keyboard)
    assert re.search(r"property\s+real\s+unit\s*:", keyboard)
    shell = qml("shell.qml")
    assert "Layouts.unitFor(" in shell


def test_the_editor_stages_through_the_store():
    editor = qml("components", "Editor.qml")
    for needle in ("Store.saveDraft()", "Store.cancelEdit()", "Store.deleteDraft()",
                   "Store.patchDraft(", "Store.patchArg(", "Store.setActionKind(",
                   "Store.draftProblems()", "QtKeys.keysymFromQt(", "QtKeys.modsFromQt(",
                   "Model.FLAG_NAMES"):
        assert needle in editor, needle


def test_the_window_has_the_editor():
    assert re.search(r"^\s*Editor\s*\{", qml("shell.qml"), re.M)


def test_the_editor_stops_recording_when_it_should():
    editor = qml("components", "Editor.qml")
    assert "onDraftIdentityChanged: recording = false" in editor
    assert re.search(r"onActiveFocusChanged:[^\n]*recording\s*=\s*false", editor)
    assert "Qt.Key_Escape" in editor
    assert "Catalogue.workspaceValue(" in editor


def test_the_record_button_does_not_steal_focus():
    editor = qml("components", "Editor.qml")
    button = editor[editor.index('text: root.recording ? "Stop"'):]
    assert "focusPolicy: Qt.NoFocus" in button[:300]


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
                               "shell.qml"]


def test_ctrl_enter_applies_only_from_the_keyboard_view():
    shell = qml("shell.qml")
    assert "Shortcut" not in shell
    handler = shell.split("Keys.onPressed", 1)[1].split("Keys.onReleased", 1)[0]
    guard = handler.index("instanceof TextInput")
    ctrl = handler.index("(event.modifiers & Qt.ControlModifier)")
    assert guard < ctrl
    assert handler.index("Store.apply()") > ctrl
    # Before the plain-Enter branch, which would otherwise take Ctrl+Enter.
    assert ctrl < handler.index("Store.edit(")
    cond = handler[ctrl:handler.index("Store.apply()")]
    for term in ("Store.dirty", "Store.busy", "Store.readOnly", "Store.draft"):
        assert term in cond


def test_a_stale_preview_is_never_shown_or_applied():
    store = qml("state", "Store.qml")
    assert re.search(r"onModelChanged:\s*preview = null", store)
    req = store.split("function requestPreview()", 1)[1].split("function ", 1)[0]
    assert req.index("preview = null") < req.index("model === null")
    assert "previewModel = JSON.stringify(model)" in req
    exited = store.split("property Process previewProc", 1)[1]
    assert "root.previewModel" in exited and "JSON.stringify(root.model)" in exited
    diff = qml("components", "DiffDialog.qml")
    assert "onAboutToShow: Store.requestPreview()" in diff
    assert "onOpened" not in diff
    apply_btn = diff.split('text: "Apply"', 1)[1]
    assert "Store.dirty" in apply_btn.split("onClicked", 1)[0]


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


def test_the_dialogs_keep_our_action_button():
    for name in ("BackupsDialog", "ExportDialog", "SettingsPopup", "SubmapDialog"):
        text = qml("components", name + ".qml")
        assert "import QtQuick.Controls as QC" in text, name
        assert not re.search(r"^import QtQuick\.Controls\s*$", text, re.M), name


def test_a_stale_preview_restarts_through_the_event_loop():
    store = qml("state", "Store.qml")
    assert "Qt.callLater(root.requestPreview)" in store


def test_a_backup_load_cannot_land_on_the_wrong_backup():
    store = qml("state", "Store.qml")
    assert "backupWanted" in store
    assert re.search(r"backupWanted\s*!==", store)
    assert "function clearBackup()" in store
    dialog = qml("components", "BackupsDialog.qml")
    assert re.search(r"onOpened:[^\n]*Store\.clearBackup\(\)", dialog)
    assert "Store.backup =" not in dialog
    assert "Store.backup.name === root.chosen" in dialog


def test_restore_never_runs_over_staged_edits_and_is_the_way_out_of_a_broken_model():
    store = qml("state", "Store.qml")
    refusal = store.split("property string restoreRefusal", 1)[1].split("function restoreBackup()", 1)[0]
    for needle in ("backup === null", "busy", "readOnly", "dirty", "doc.modelError", "backup.modelError"):
        assert needle in refusal, needle
    body = store.split("function restoreBackup()", 1)[1].split("function exportTo", 1)[0]
    assert "applyModel(" in body and "apply()" not in body.replace("applyModel(", "")
    am = store.split("function applyModel(m)", 1)[1].split("function runApply", 1)[0]
    assert "busy" in am and "dirty" not in am and "readOnly" not in am
    dialog = qml("components", "BackupsDialog.qml")
    enabled = dialog.split("enabled:")[-1].split("onClicked")[0]
    for needle in ("Store.backup.name", "Store.restoreRefusal"):
        assert needle in enabled, needle


def test_the_payload_is_serialized_when_the_apply_starts():
    store = qml("state", "Store.qml")
    run = store.split("function runApply(m)", 1)[1].split("function requestPreview", 1)[0]
    assert "applyPayload = JSON.stringify(m)" in run
    assert run.index("applyPayload =") < run.index("applyProc.running = true")
    proc = store.split("property Process applyProc", 1)[1].split("property Process previewProc", 1)[0]
    assert "write(root.applyPayload)" in proc
    assert "root.model" not in proc.split("onStarted", 1)[1].split("onExited", 1)[0]


def test_qualified_process_ids_in_the_store():
    store = qml("state", "Store.qml")
    assert "root.backupProc.command" in store and "root.exportProc.command" in store
    assert not re.search(r"(?<![.\w])(backupProc|exportProc)\.command", store)


def test_escape_never_loses_work_or_kills_an_apply():
    shell = qml("shell.qml")
    esc = shell.split("Keys.onEscapePressed", 1)[1].split("ColumnLayout", 1)[0]
    assert "Store.requestQuit()" in esc
    assert "Store.cancelEdit()" not in esc
    store = qml("state", "Store.qml")
    assert "property real quitArmedAt" in store
    body = store.split("function requestQuit()", 1)[1].split("function ", 1)[0]
    assert "Quit.escape(" in body and "busy" in body and "dirty" in body


def test_overriding_a_bind_with_options_hyprkbm_cannot_keep_is_a_problem():
    store = qml("state", "Store.qml")
    body = store.split("function draftProblems()", 1)[1].split("function saveDraft()", 1)[0]
    assert "Model.droppedOpts(draft.hand.opts)" in body
    assert "would drop these options" in body


def test_stale_edits_are_listed_and_can_be_forgotten():
    panel = qml("components", "BindPanel.qml")
    assert "Store.merged.stale" in panel
    forget = panel.split('text: "Forget"', 1)[1].split("}", 1)[0]
    assert "Store.readOnly" in forget and "Store.forget(" in forget
    store = qml("state", "Store.qml")
    body = store.split("function forget(entry)", 1)[1].split("function addSubmap", 1)[0]
    assert "readOnly" in body and "Model.forgetUnbind(" in body and "Model.forgetReplaces(" in body


def test_overlaps_are_drawn_apart_from_conflicts_and_counted_apart():
    cap = qml("components", "KeyCap.qml")
    fill = cap.split("color:", 1)[1].split("border.width", 1)[0]
    # Filled like a bound key; only the conflict state is filled red.
    assert re.search(r'"bound" \|\| kind === "overlap" \? lit\(Colors.accentPrimary', fill)
    border = cap.split("border.color:", 1)[1].split("Behavior", 1)[0]
    assert '"overlap"' in border and "statusCritical" in border
    header = qml("components", "Header.qml")
    action = header.split("Store.nextConflict()", 1)[0].rsplit("Action {", 1)[1]
    assert "Model.blocks(g)" in action and "blocking" in action and "overlap" in action


def test_small_store_and_row_guards():
    store = qml("state", "Store.qml")
    problems = store.split("function draftProblems()", 1)[1].split("function saveDraft()", 1)[0]
    assert "Keys.isModifierOnly(draft.keys)" in problems and "Pick a key, not only modifiers" in problems
    assert "submaps.indexOf(draft.submap)" in problems
    assert "keepSubmapValid()" in store.split("function discard()", 1)[1].split("function ", 1)[0]
    assert "keepSubmapValid()" in store.split("function adopt(", 1)[1].split("\n    }\n", 1)[0]
    row = qml("components", "BindRow.qml")
    assert "untouchable" in row.split('text: "Edit (E)"', 1)[1].split("onClicked", 1)[0]
    assert "untouchable" in row.split('text: "Remove"', 1)[1].split("onClicked", 1)[0]
    assert "QC.ToolTip.text" in row
    bar = qml("components", "StagedBar.qml")
    assert "Store.draft === null" in bar.split('text: Store.busy ? "Applying…"', 1)[1].split("onClicked", 1)[0]
    assert "Store.draft !== null" in bar


def test_forget_is_refused_while_hyprland_lua_is_only_partly_read():
    store = qml("state", "Store.qml")
    body = store.split("function forget(entry)", 1)[1].split("function addSubmap", 1)[0]
    assert "readerError" in body and "report(" in body
    panel = qml("components", "BindPanel.qml")
    forget = panel.split('text: "Forget"', 1)[1].split("}", 1)[0]
    assert "readerError" in forget
    assert "readerError" in panel.split('text: "Stale', 1)[0].rsplit("Text {", 1)[-1] + panel.split('text: "Stale', 1)[1].split("Repeater", 1)[0]
    assert [n for n, s in all_qml().items() if "Store.forget(" in s] == ["components/BindPanel.qml"]


def test_nothing_is_staged_while_an_apply_runs():
    store = qml("state", "Store.qml")
    assert "function stagingBlocked()" in store
    for fn, nxt in (("saveDraft()", "cancelEdit"), ("deleteBind(uid)", "deleteDraft"),
                    ("restoreHand(h)", "keepBoth"), ("keepBoth(uid)", "forget("),
                    ("forget(entry)", "addSubmap"), ("addSubmap(name, reset)", "discard"),
                    ("newBind(keys)", "newBindOnSelected"), ("edit(uid)", "newBind(")):
        body = store.split("function " + fn, 1)[1].split("function " + nxt, 1)[0]
        assert "stagingBlocked()" in body, fn
    assert "Store.busy" in qml("components", "Editor.qml").split('text: "Save (Ctrl+S)"', 1)[1].split("onClicked", 1)[0]


def test_the_legend_has_an_overlap_entry_and_the_readme_warns_about_closing():
    bar = qml("components", "ModifierBar.qml")
    assert '"overlap"' in bar
    readme = (PANEL.parents[1] / "README.md").read_text(encoding="utf-8")
    assert "Applying…" in readme and "mid-apply" in readme


def test_closing_the_window_quits_the_panel():
    """Quickshell keeps running when its last window closes. A panel left
    running without a window blocks the next launch (qs -n), so closing the
    window -- from its own close button or the compositor -- quits."""
    shell = qml("shell.qml")
    assert re.search(r"onClosed:\s*\{[^}]*Qt\.quit\(\)", shell)


def test_the_header_and_banner_do_not_take_spare_height():
    """A layout inside a layout fills spare height by default. The Banner is a
    ColumnLayout, so with no banners showing it still took a third of the
    window as an empty band under the header."""
    shell = qml("shell.qml")
    banner = re.search(r"^\s*Banner\s*\{[^}]*\}", shell, re.M).group(0)
    assert "Layout.fillHeight: false" in banner
    header = shell[shell.index("Header {"):]
    header = header[:header.index("}")]
    assert "Layout.fillHeight: false" in header


def test_recording_shows_held_modifiers_live():
    """The field shows "CTRL + SHIFT + …" while the modifiers are held, so it
    is clear recording works before the final key is pressed."""
    editor = qml("components", "Editor.qml")
    assert "QtKeys.heldMods(" in editor
    assert "QtKeys.recordingText(" in editor
    assert "Keys.onReleased" in editor
    assert re.search(r"text:\s*root\.recording\s*\?", editor)


def test_find_mode_is_handled_first_and_always_left():
    shell = qml("shell.qml")
    handler = shell.split("Keys.onPressed", 1)[1]
    assert handler.index("Store.finding") < handler.index("modifierFromQtKey")
    assert "Store.startFind()" in handler
    assert "Capture.comboFrom(" in handler
    focus = shell.split("onActiveFocusChanged", 1)[1].split("Keys.onPressed", 1)[0]
    assert "Store.stopFind()" in focus
    assert "Window.onActiveChanged" in focus
    closed = shell.split("onClosed", 1)[1].split("IpcHandler", 1)[0]
    assert closed.index("Store.stopFind()") < closed.index("Qt.quit()")


def test_find_cannot_be_started_through_ipc():
    shell = qml("shell.qml")
    ipc = shell.split("IpcHandler", 1)[1].split("FocusScope", 1)[0]
    assert "startFind" not in ipc and "Store.found" not in ipc


def test_the_header_find_action_does_not_take_focus():
    header = qml("components", "Header.qml")
    block = header.split("root.findRequested()", 1)[0].rsplit("Action {", 1)[1]
    assert "focusPolicy: Qt.NoFocus" in block
    assert "Store.stopFind()" in header
    assert "Press a keybind" in header


def test_the_store_enters_and_leaves_through_capture_lua():
    store = qml("state", "Store.qml")
    assert "Capture.enterLua()" in store and "Capture.leaveLua()" in store
    assert "function found(" in store


def test_escape_cancels_find_before_it_can_quit():
    shell = qml("shell.qml")
    esc = shell.split("Keys.onEscapePressed", 1)[1].split("ColumnLayout", 1)[0]
    assert esc.index("Store.finding") < esc.index("Store.requestQuit()")
    assert "Store.stopFind()" in esc.split("Store.requestQuit()", 1)[0]
    # Every quit leaves find mode first.
    for m in re.finditer(r"Qt\.quit\(\)", shell):
        assert "Store.stopFind()" in shell[:m.start()].rsplit("{", 1)[-1] or \
            "Store.stopFind()" in shell[max(0, m.start() - 200):m.start()]


def test_leaving_find_survives_the_panel_and_cannot_be_dropped():
    store = qml("state", "Store.qml")
    assert 'Quickshell.execDetached(["hyprctl", "eval", Capture.leaveLua()])' in store
    assert "findLeave" not in store
    enter = store.split("property Process findEnter", 1)[1].split("property Process", 1)[0]
    assert "!root.finding" in enter and "code !== 0" in enter


def test_find_follows_hyprland_and_ends_with_the_things_that_conflict_with_it():
    store = qml("state", "Store.qml")
    assert "import Quickshell.Hyprland" in store
    assert "onRawEvent" in store and 'event.name === "submap"' in store
    assert "Capture.SUBMAP" in store and "Capture.TIMEOUT_MS" in store
    for fn in ("function runApply(", "function reload(", "function adopt(", "function edit(", "function newBind("):
        body = store.split(fn, 1)[1].split("\n    function ", 1)[0]
        assert "stopFind()" in body, fn
    shell = qml("shell.qml")
    assert "TextInput" in shell.split("onActiveFocusItemChanged", 1)[1][:300]


def test_a_held_key_does_not_find():
    shell = qml("shell.qml")
    finding = shell.split("if (Store.finding)", 1)[1].split("var mod", 1)[0]
    assert "event.isAutoRepeat" in finding.split("Capture.comboFrom", 1)[0]


def test_the_find_button_moves_focus_to_the_window_first():
    header = qml("components", "Header.qml")
    assert "signal findRequested()" in header
    assert "Store.startFind()" not in header
    shell = qml("shell.qml")
    handler = shell.split("onFindRequested:", 1)[1][:200]
    assert handler.index("scope.takeKeys()") < handler.index("Store.startFind()")


def test_a_leave_follows_every_capture_end_seen_in_hyprland():
    store = qml("state", "Store.qml")
    raw = store.split("function onRawEvent", 1)[1].split("property Timer", 1)[0]
    assert "root.leaveNow()" in raw


def test_only_a_bare_escape_cancels_find():
    shell = qml("shell.qml")
    esc = shell.split("Keys.onEscapePressed", 1)[1].split("ColumnLayout", 1)[0]
    finding = esc.split("Store.finding", 1)[1].split("Store.requestQuit()", 1)[0]
    assert "event.modifiers" in finding and "event.accepted = false" in finding
    assert finding.index("event.accepted = false") < finding.index("Store.stopFind()")


def _keys_handler():
    shell = qml("shell.qml")
    return shell.split("Keys.onPressed", 1)[1].split("Keys.onReleased", 1)[0]


def test_navigation_keys_sit_after_find_and_the_text_input_guard():
    h = _keys_handler()
    guard = h.index("instanceof TextInput")
    assert h.index("Store.finding") < guard
    for needle in ("Qt.Key_E", "Qt.Key_A",
                   "Qt.Key_D", "Qt.Key_Z", "Qt.Key_Delete",
                   "Store.listIndex", "Store.focusedBind()", "diffDialog.open()", "Store.discard()"):
        assert needle in h, needle
        assert h.index(needle) > guard, needle


def test_shortcuts_need_no_modifier_or_exactly_control_and_a_dirty_store():
    h = _keys_handler()
    assert "Qt.Key_E && m === Qt.NoModifier" in h
    assert "Qt.Key_A && m === Qt.NoModifier" in h
    z = h.split("Qt.Key_Z &&", 1)[1][:200]
    assert "Store.dirty" in z
    d = h.split("Qt.Key_D &&", 1)[1][:200]
    assert "Store.dirty" in d


def test_the_editor_area_takes_no_list_or_key_shortcuts():
    h = _keys_handler()
    ret = h.index('if (Store.area === "editor") return')
    assert h.index("Qt.Key_Tab") < ret
    for needle in ("Qt.Key_E &&", "Qt.Key_A &&", "Qt.Key_D &&", "Qt.Key_Z &&", "Qt.Key_Delete",
                   "Store.listIndex", "Store.moveSelection"):
        assert h.index(needle) > ret, needle


def test_one_shot_keys_ignore_auto_repeat_but_arrows_repeat():
    h = _keys_handler()
    rep = h.index("event.isAutoRepeat", h.index("instanceof TextInput"))
    assert rep < h.index("Qt.Key_F &&") and rep < h.index("Qt.Key_Slash") and rep < h.index("Qt.Key_Return")
    assert rep < h.index("Qt.Key_Delete") and rep < h.index("Qt.Key_E &&") and rep < h.index("Qt.Key_Z")
    assert "Qt.Key_Up" in h and h.index("Qt.Key_Up") < h.index("Qt.Key_Delete")
    arrows = h.split("Qt.Key_Up", 1)[1].split("Qt.Key_Delete", 1)[0]
    assert "isAutoRepeat" not in arrows


def test_tab_is_plain_and_keypad_is_masked():
    h = _keys_handler()
    assert "~Qt.KeypadModifier" in h
    tab = h.split("Qt.Key_Tab", 1)[1].split("scope.moveArea(", 1)[0]
    assert ("Qt.ShiftModifier" in tab) and ("Qt.NoModifier" in tab)


def test_tab_moves_areas_before_the_text_input_guard_but_after_find():
    h = _keys_handler()
    guard = h.index("instanceof TextInput")
    tab = h.index("Qt.Key_Tab")
    # After find (every key is the answer there) and after modifier tracking,
    # but before the guard, so Tab from the search field moves areas too.
    assert h.index("Store.finding") < tab < guard
    assert h.index("Store.hold(") < tab
    assert h.index("Qt.Key_Backtab") < guard
    assert h.index("scope.moveArea(") < guard
    shell = qml("shell.qml")
    move = shell.split("function moveArea(back)", 1)[1].split("\n            }\n", 1)[0]
    assert "Focus.next" in move and "Focus.prev" in move
    assert "editor.focusFirst()" in move and "editor.focusLast()" in move
    assert "scope.takeKeys()" in move
    # The editor hands Tab back when its walk runs off an end.
    assert "onTabOut:" in shell and "scope.moveArea(back)" in shell


def test_clicks_never_keep_focus_and_only_text_fields_take_it():
    action = qml("components", "Action.qml")
    assert "focusPolicy: Qt.TabFocus" in action
    header = qml("components", "Header.qml")
    search = header.split("id: search", 1)[1].split("Keys.onEscapePressed", 1)[0]
    # Out of Qt's own Tab chain, so its Tab bubbles to the window's handler.
    assert "focusPolicy: Qt.ClickFocus" in search
    # Chips and keycaps are MouseAreas, which never take focus.
    for f in ("ModifierBar.qml", "KeyCap.qml", "Header.qml"):
        assert "focus: true" not in qml("components", f), f


def test_the_editor_walks_its_own_controls():
    editor = qml("components", "Editor.qml")
    assert 'import "../lib/focus.js" as Focus' in editor
    assert "signal tabOut(bool back)" in editor
    assert "function controls()" in editor and "function focusLast()" in editor
    controls = editor.split("function controls()", 1)[1].split("\n    }\n", 1)[0]
    for id_ in ("keysField", "kindSelect", "argFields", "rawLua", "descField", "submapSelect"):
        assert id_ in controls, id_
    assert "c.visible && c.enabled" in controls
    # Buttons are clicked or have shortcuts; Tab never walks them.
    assert "Action" not in controls
    tab = editor.split("function tab(event)", 1)[1].split("\n    }\n", 1)[0]
    assert "Focus.walk(" in tab and "root.tabOut(back)" in tab and "event.accepted = true" in tab
    assert "Keys.onPressed: function (event) { root.tab(event) }" in editor
    # Every walked control is out of Qt's chain, so Tab reaches the walk.
    assert editor.count("focusPolicy: Qt.ClickFocus") >= 6
    # A text area takes Tab as a character: the walk must see it first.
    area = editor.split("QC.TextArea {", 1)[1][:400]
    assert "root.tab(event)" in area


def test_area_is_kept_in_sync_with_real_focus():
    shell = qml("shell.qml")
    focus = shell.split("onActiveFocusItemChanged", 1)[1].split("Window.onActiveChanged", 1)[0]
    assert 'Store.area === "editor"' in focus and 'Store.area = "list"' in focus
    assert "editor" in focus
    conn = shell.split("function onDraftChanged", 1)[1][:300]
    assert "editor" in conn  # only refocus when focus was in the editor
    assert "function onAreaChanged" in shell
    store = qml("state", "Store.qml")
    assert 'area = "keyboard"' in store.split("function selectKey", 1)[1].split("\n    }", 1)[0]


def test_delete_refuses_unreadable_keys_in_the_store():
    store = qml("state", "Store.qml")
    body = store.split("function deleteBind(", 1)[1].split("\n    }\n", 1)[0]
    assert "combo === null" in body and "report(" in body.split("combo === null", 1)[1][:200]
    assert body.index("combo === null") < body.index("unbindHand")


def test_the_cursor_resets_from_what_was_picked_and_the_list_only_clamps():
    store = qml("state", "Store.qml")
    for name in ("onSelectedKeyChanged", "onModsChanged", "onSubmapChanged", "onQueryChanged"):
        assert name + ": listIndex = 0" in store, name
    assert "listContext" not in store and "seenContext" not in store
    h = store.split("onListRowsChanged", 1)[1].split("\n    on", 1)[0][:300]
    assert "Focus.clampIndex(" in h and "listRows.length" in h and "listIndex = 0" not in h


def test_tab_enters_the_editor_by_focusing_its_keys_field_and_leaving_returns_focus():
    shell = qml("shell.qml")
    assert "focusFirst()" in shell and "scope.forceActiveFocus()" in shell
    editor = qml("components", "Editor.qml")
    assert "function focusFirst()" in editor and "keysField.forceActiveFocus()" in editor
    store = qml("state", "Store.qml")
    assert 'property string area: "keyboard"' in store
    assert "property int listIndex: 0" in store
    assert "function focusedBind()" in store
    assert "onListRowsChanged" in store
    assert "onDraftChanged" in store and 'area = "list"' in store
    assert 'import "lib/focus.js" as Focus' in shell
    assert "onDraftChanged" in shell and "Store.draft === null" in shell


def test_the_focus_ring_is_a_thick_accent_border_and_a_faint_tint():
    shell = qml("shell.qml")
    assert 'Store.area === "keyboard"' in shell
    assert 'Store.area === "list"' in qml("components", "BindPanel.qml")
    assert 'Store.area === "editor"' in qml("components", "Editor.qml")
    for f in ("shell.qml", "components/BindPanel.qml", "components/Editor.qml"):
        src = qml(*f.split("/"))
        lines = [l for l in src.splitlines() if l.strip().startswith("border.") and "Store.area ===" in l]
        assert lines and all("border." in l for l in lines), f
        assert all("Colors.accentPrimary" in l for l in lines if "border.color" in l)
        width = [l for l in lines if "border.width" in l]
        assert width and all("? 3 : 1" in l for l in width), f
        # A faint accent tint over the pane's own colour, never translucent.
        fill = src.split("color: Store.area ===", 1)[1][:200]
        assert "Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentPrimary" in fill, f


def test_focused_controls_get_a_2px_accent_border():
    for f in ("Action.qml", "Select.qml", "Toggle.qml"):
        src = qml("components", f)
        assert "border.width: root.activeFocus ? 2 : 1" in src, f
        assert "root.activeFocus ? Colors.accentPrimary" in src, f
    header = qml("components", "Header.qml")
    assert "border.width: search.activeFocus ? 2 : 1" in header
    assert "search.activeFocus ? Colors.accentPrimary" in header
    editor = qml("components", "Editor.qml")
    assert "border.width: input.activeFocus ? 2 : 1" in editor
    assert "input.activeFocus ? Colors.accentPrimary" in editor
    assert "rawLua.activeFocus ? Colors.accentPrimary" in editor


def test_the_focused_row_is_highlighted_and_kept_in_view():
    panel = qml("components", "BindPanel.qml")
    assert "Store.listIndex" in panel and "ensureVisible" in panel and "contentY" in panel
    row = qml("components", "BindRow.qml")
    assert "focused" in row and 'Store.area === "list"' in row


def test_buttons_show_their_shortcuts():
    assert '"Edit (E)"' in qml("components", "BindRow.qml")
    assert '"+ Add a bind on " + root.keyText + " (A)"' in qml("components", "BindPanel.qml")
    bar = qml("components", "StagedBar.qml")
    for hint in ('"Review diff (Ctrl+D)"', '"Discard (Ctrl+Z)"', "(Ctrl+Enter)"):
        assert hint in bar, hint


def test_keys_bound_under_other_modifiers_are_outlined():
    cap = qml("components", "KeyCap.qml")
    fill = cap.split("color:", 1)[1].split("border.width", 1)[0]
    # No fill of its own: it falls through to the free key's surface.
    assert '"other"' not in fill
    assert 'border.width: selected || kind === "other" ? 2 : 1' in cap
    border = cap.split("border.color:", 1)[1].split("Behavior", 1)[0]
    # Selection is checked first, so it still wins the border.
    assert border.index("selected ?") < border.index('"other"')
    assert 'kind === "bound" || kind === "other" ? lit(Colors.accentPrimary, 0.6)' in border
    assert 'root.kind === "other" ? Colors.textSecondary' in cap
    # Only a key that would otherwise be free is outlined.
    for f in ("KeyBlock.qml", "ExtraKeys.qml"):
        kind = qml("components", f).split("function kindOf(", 1)[1].split("\n    }\n", 1)[0]
        assert kind.index("return i.state") < kind.index("Store.otherKeys["), f
    store = qml("state", "Store.qml")
    assert "Keymap.otherKeys(merged.binds, submap, mods)" in store


def test_the_legend_has_an_outline_only_other_mods_entry():
    bar = qml("components", "ModifierBar.qml")
    assert '["other mods", Colors.bgSurface]' in bar
    assert 'legend.modelData[0] === "other mods" ? 2 : 0' in bar
    assert 'legend.modelData[0] === "other mods" ? Colors.accentPrimary' in bar


def test_also_bound_as_is_hidden_while_searching_or_with_no_key():
    store = qml("state", "Store.qml")
    other = store.split("readonly property var otherCombos:", 1)[1].split("readonly property", 1)[0]
    assert "parsedQuery.empty" in other and ": []" in other
    rows = store.split("readonly property var listRows:", 1)[1].split("readonly property", 1)[0]
    assert rows.index("listed.map(") < rows.index("otherCombos.map(")
    assert 'kind: "bind"' in rows and 'kind: "other"' in rows
    panel = qml("components", "BindPanel.qml")
    header = panel.split('text: "Also bound as"', 1)[0].rsplit("Text {", 1)[1]
    assert "!root.searching" in header and 'root.keyText !== ""' in header
    rep = panel.split("id: otherRows", 1)[1].split("\n                }\n", 1)[0]
    assert 'root.searching || root.keyText === "" ? []' in rep and "Store.otherCombos" in rep
    assert "position: Store.listed.length + index" in rep and "other: true" in rep
    # After the removed rows, before the add button.
    assert panel.index("Store.removedHere") < panel.index('"Also bound as"') < panel.index('"+ Add a bind on "')
    assert "otherRows.itemAt(Store.listIndex - n)" in panel
    row = qml("components", "BindRow.qml")
    assert "property bool other: false" in row
    assert "enabled: root.other" in row and "Store.pickOther(root.bind)" in row
    for name in ('"Edit (E)"', '"Remove"'):
        assert "visible: !root.other" in row.split(name, 1)[1][:80], name


def test_enter_dispatches_on_the_row_kind_and_e_and_delete_skip_other_rows():
    h = _keys_handler()
    lst = h.split('if (Store.area === "list") {', 1)[1].split("var dirs", 1)[0]
    assert "Store.listRows.length" in lst
    enter = lst.split("Qt.Key_Return", 1)[1].split("Qt.Key_Delete", 1)[0]
    assert "Store.focusedRow()" in enter
    assert 'row.kind === "other") Store.pickOther(row.bind)' in enter
    assert "else Store.editBind(Store.focusedBind())" in enter
    store = qml("state", "Store.qml")
    fb = store.split("function focusedBind()", 1)[1].split("\n    }\n", 1)[0]
    assert 'row.kind === "bind" ? row.bind : null' in fb
    pick = store.split("function pickOther(", 1)[1].split("\n    }\n", 1)[0]
    assert "setMods(b.mods)" in pick and "listIndex = i" in pick
    assert "selectedKey" not in pick  # the key stays selected


def test_the_scope_takes_the_keys_back_by_clearing_inner_focus():
    # A FocusScope's forceActiveFocus hands focus back to the child that had
    # it, and a closed editor's fields are only hidden; every hand-back must
    # clear that focus first.
    shell = (PANEL / "shell.qml").read_text()
    take = shell[shell.index("function takeKeys()"):]
    take = take[:take.index("\n            }\n")]
    assert "p.focus = false" in take and "scope.forceActiveFocus()" in take
    assert shell.count("scope.forceActiveFocus()") == 1


def test_ctrl_s_saves_the_draft_from_any_field():
    # Before the text-input guard, so it works while typing; Esc cancels.
    shell = (PANEL / "shell.qml").read_text()
    h = shell[shell.index("Keys.onPressed: function (event) {\n                // First"):]
    save = h.index("event.key === Qt.Key_S && m === Qt.ControlModifier")
    assert h.index("Store.finding") < save < h.index("instanceof TextInput")
    assert "Store.saveDraft()" in h[save:save + 300]
    editor = (PANEL / "components" / "Editor.qml").read_text()
    assert 'text: "Save (Ctrl+S)"' in editor and 'text: "Cancel (Esc)"' in editor


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


def test_the_cheatsheet_is_a_read_only_overlay():
    sheet = (PANEL / "cheatsheet.qml").read_text()
    assert 'WlrLayershell.namespace: "hyprkbm-cheatsheet"' in sheet
    assert "WlrLayer.Overlay" in sheet and "WlrKeyboardFocus.Exclusive" in sheet
    assert "interactive: false" in sheet and "detailed: true" in sheet
    assert 'target: "cheatsheet"' in sheet and "function close()" in sheet
    # Never writes: nothing that stages or applies. It evals only the Lua that
    # holds Hyprland's binds, gives them back, or runs the selected combo.
    for forbidden in ("Store.apply", "saveDraft", "newBind", "Store.edit"):
        assert forbidden not in sheet
    evals = re.findall(r'"hyprctl", "eval", ([^\]]+)\]', sheet)
    assert evals and set(evals) <= {"sheet.held ? Cheatsheet.rearmLua(Date.now()) : Cheatsheet.enterLua(Date.now())",
                            "Cheatsheet.leaveLua()", "lua"}, evals
    assert sheet.count("hyprctl") == len(evals)
    # Esc closes; modifiers are followed on press and release.
    assert "Qt.Key_Escape" in sheet and "Keys.onReleased" in sheet
    assert "QtKeys.heldMods(" in sheet


def test_the_cheatsheet_follows_held_modifiers_only():
    sheet = qml("cheatsheet.qml")
    # The panel's default chip (SUPER) would show whenever nothing is held.
    assert "Store.setMods([])" in sheet
    assert "Cheatsheet.title(Store.mods)" in sheet


def test_the_cheatsheet_sizes_its_keys_from_the_output_only():
    sheet = qml("cheatsheet.qml")
    assert re.search(r"Layouts\.unitFor\(sheet\.width \* [\d.]+ - Spacing\.lg, 96\)", sheet)
    assert "Layout.preferredWidth: Layouts.KEYBOARD_UNITS * keyRow.unit" in sheet
    assert "Layout.preferredHeight: implicitHeight" in sheet


def test_the_cheatsheet_answers_close_before_it_quits():
    sheet = qml("cheatsheet.qml")
    close = sheet[sheet.index("function close()"):]
    close = close[:close.index("}")]
    # Quitting inside the call could drop the reply; `hyprkbm --cheatsheet`
    # would then read "not running" and open a second sheet.
    assert "Qt.quit" not in close and "sheet.finish(" in close
    finish = sheet[sheet.index("function finish(lua)"):]
    finish = finish[:finish.index("\n        }\n")]
    assert "sheet.visible = false" in finish
    # The output is picked once, so the sheet never jumps between outputs.
    assert "Cheatsheet.outputFor(" in sheet and "Hyprland.focusedMonitor" in sheet


def test_a_read_only_keyboard_shows_the_selection():
    for name in ("KeyBlock.qml", "ExtraKeys.qml"):
        src = qml("components", name)
        assert "root.interactive &&" not in re.search(r"selected: [^\n]+", src).group(0), name
    sheet = qml("cheatsheet.qml")
    # Store selects Q whenever a load completes; the sheet shows only its own
    # selection, from the start.
    assert "function onSelectedKeyChanged()" in sheet
    assert 'Store.selectedKey = ""' in sheet.split("Component.onCompleted:", 1)[1][:200]


def test_the_cheatsheet_holds_hyprlands_binds_while_open():
    sheet = qml("cheatsheet.qml")
    arm = sheet[sheet.index("id: armTimer"):]
    arm = arm[:arm.index("}")]
    assert "interval: Cheatsheet.ARM_EVERY_MS" in arm and "repeat: true" in arm
    assert "triggeredOnStart: true" in arm and "sheet.arm()" in arm
    # Only the first hold enters the submap; re-arms never put the user back.
    assert '["hyprctl", "eval", sheet.held ? Cheatsheet.rearmLua(Date.now()) : Cheatsheet.enterLua(Date.now())]' in sheet
    done = sheet[sheet.index("id: holdProc"):]
    done = done[:done.index("\n        }\n")]
    # Held only once a hold succeeded.
    assert "sheet.held = true" in done.split("if (code !== 0) {", 1)[1].split("} else {", 1)[1]


def test_the_cheatsheet_closes_when_hyprland_leaves_its_submap():
    sheet = qml("cheatsheet.qml")
    ev = sheet[sheet.index("function onRawEvent(event)"):]
    ev = ev[:ev.index("\n            }\n")]
    # Only after our own entry landed, and not while the sheet itself leaves.
    assert "sheet.held" in ev and "!sheet.closing" in ev
    assert 'event.name === "submap"' in ev and "event.data !== Cheatsheet.SUBMAP" in ev
    # Hyprland already left: nothing to send.
    assert 'sheet.finish("")' in ev and "leaveLua" not in ev
    flush = sheet[sheet.index("function flush()"):]
    flush = flush[:flush.index("\n        }\n")]
    assert 'if (lua !== "") Quickshell.execDetached(' in flush


def test_the_cheatsheet_title_area_never_moves_the_keyboard():
    sheet = qml("cheatsheet.qml")
    area = sheet[sheet.index("id: titleArea"):sheet.index("id: keyRow")]
    # A fixed height from type sizes: room for the combo, two action lines
    # and the status, selected or not.
    assert "Layout.preferredHeight: sheet.titleAreaHeight" in area
    h = sheet[sheet.index("readonly property int titlePx"):]
    h = h[:h.index("\n\n")]
    assert "Math.round(Typography.sizeBody * 1.8)" in h
    assert "Math.ceil(Typography.sizeBody * 1.5)" in h and "Math.ceil(sheet.titlePx * 1.5)" in h
    assert "readonly property real titleAreaHeight" in h and "implicitHeight" not in h
    assert "implicitHeight" not in area and "visible:" not in area
    assert area.count("elide: Text.ElideRight") == 3 and "maximumLineCount: 2" in area


def test_every_way_out_of_the_cheatsheet_gives_the_binds_back():
    sheet = qml("cheatsheet.qml")
    # Qt.quit only from quitSoon, and quitSoon only once the leave or run has
    # gone out, detached so it survives the quit.
    assert sheet.count("Qt.quit") == 1 and "onTriggered: Qt.quit()" in sheet
    assert sheet.count("quitSoon.start()") == 1
    flush = sheet[sheet.index("function flush()"):]
    flush = flush[:flush.index("\n        }\n")]
    assert flush.index('Quickshell.execDetached(["hyprctl", "eval", lua])') < flush.index("quitSoon.start()")
    # Esc, a click and IPC close leave; Enter runs; nothing else finishes.
    assert sheet.count("sheet.finish(Cheatsheet.leaveLua())") == 4  # Esc, click, close(), own key
    assert sheet.count("sheet.finish(") == 6  # and Hyprland leaving
    run = sheet[sheet.index("function runSelection()"):]
    run = run[:run.index("\n        }\n")]
    assert "var lua = Cheatsheet.runLua(sheet.selectedBinds)" in run
    assert "if (lua === null) return" in run and "sheet.finish(lua)" in run
    close = sheet[sheet.index("function close()"):]
    close = close[:close.index("}")]
    assert "sheet.finish(Cheatsheet.leaveLua())" in close


def test_the_cheatsheet_selects_a_pressed_combo():
    sheet = qml("cheatsheet.qml")
    assert "Keymap.bindsOn(Store.merged.binds, \"\", sheet.selection.mods, sheet.selection.keyId)" in sheet
    assert "Cheatsheet.opensSheet(" in sheet
    assert "Qt.Key_Return" in sheet and "Qt.Key_Enter" in sheet
    assert "Cheatsheet.actions(sheet.selectedBinds)" in sheet
    assert "Cheatsheet.status(sheet.selectedBinds)" in sheet
    assert '"Press a combo to see what it does · Enter runs it · Esc closes"' in sheet


def test_the_menu_offers_a_cheatsheet_key():
    store = qml("state", "Store.qml")
    assert "Cheatsheet.keysOf(merged.binds)" in store
    body = store.split("function newCheatsheetBind()", 1)[1].split("\n    }\n", 1)[0]
    assert "newBind(" in body and "Cheatsheet.COMMAND" in body
    popup = qml("components", "SettingsPopup.qml")
    assert "Store.cheatsheetKeys" in popup and "Store.newCheatsheetBind()" in popup
    assert "root.close()" in popup.split("Store.newCheatsheetBind()", 1)[1][:80]
