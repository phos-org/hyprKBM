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
