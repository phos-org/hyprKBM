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
    assert re.search(r"onActiveFocusChanged:\s*if \(!activeFocus\) Store\.heldMods = \[\]", shell)
    assert re.search(r"Window\.onActiveChanged:\s*if \(!Window\.active\) Store\.heldMods = \[\]", shell)


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
    ctrl = handler.index("Qt.ControlModifier")
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
    assert "untouchable" in row.split('text: "Edit"', 1)[1].split("onClicked", 1)[0]
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
    assert "Store.busy" in qml("components", "Editor.qml").split('text: "Save"', 1)[1].split("onClicked", 1)[0]


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
    assert re.search(r"onClosed:\s*Qt\.quit\(\)", shell)
