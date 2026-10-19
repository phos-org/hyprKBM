import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "config"
import "components"
import "state"
import "lib/qtkeys.js" as QtKeys
import "lib/capture.js" as Capture
import "lib/layouts.js" as Layouts
import "lib/focus.js" as Focus

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

        // Quickshell keeps running after its last window closes; a panel left
        // running without one would make the next `hyprkbm` (qs -n) do nothing.
        onClosed: {
            // Closing mid-find must not leave Hyprland's binds off.
            Store.stopFind()
            Qt.quit()
        }

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

            // A release is only seen while this scope has focus. If a
            // compositor bind moves focus (or the window deactivates) while a
            // modifier is down, the release goes elsewhere and the keyboard
            // would show that modifier forever, so drop them on either.
            // Find mode ends on either too: its keys only reach this scope
            // while it has focus.
            onActiveFocusChanged: if (!activeFocus) { Store.heldMods = []; Store.stopFind() }
            // Typing into a field (clicking the search) is not a keybind.
            Window.onActiveFocusItemChanged: {
                var f = scope.Window.activeFocusItem
                if (f && (f instanceof TextInput || f instanceof TextEdit)) Store.stopFind()
                // The ring must never claim the editor when focus has left it.
                if (f && Store.area === "editor" && !scope.within(f, editor)) Store.area = "list"
                // Clicking into an editor control puts the keys there, so the
                // ring follows; Tab then walks the editor from where it is.
                else if (f && Store.draft !== null && f !== editor && scope.within(f, editor)) Store.area = "editor"
            }
            Window.onActiveChanged: if (!Window.active) { Store.heldMods = []; Store.stopFind() }

            // Tab / Shift+Tab: the next / previous area. The editor is entered
            // at its near end; every other area is driven from this scope.
            function moveArea(back) {
                let hasEditor = Store.draft !== null
                Store.area = back ? Focus.prev(Store.area, hasEditor) : Focus.next(Store.area, hasEditor)
                if (Store.area === "editor") { if (back) editor.focusLast(); else editor.focusFirst() }
                else scope.takeKeys()
            }

            function within(item, ancestor) {
                for (let p = item; p; p = p.parent) if (p === ancestor) return true
                return false
            }

            // Takes the keys back from whatever inside the scope has them.
            // forceActiveFocus alone is not enough: a FocusScope hands active
            // focus on to the child that last had it, and a closed editor's
            // fields are hidden, not destroyed, so Tab would go on reaching
            // the editor's own walk and never move between areas again.
            function takeKeys() {
                for (let p = scope.Window.activeFocusItem; p && p !== scope; p = p.parent)
                    if (scope.within(p, scope)) p.focus = false
                scope.forceActiveFocus()
            }

            // However the editor closes (Save, Cancel, Esc, Delete), the keys
            // come back here; Store has already moved the area to the list.
            Connections {
                target: Store
                function onDraftChanged() {
                    // Only when focus was in the editor; a click elsewhere keeps its own.
                    if (Store.draft === null && scope.within(scope.Window.activeFocusItem, editor)) scope.takeKeys()
                }
                function onAreaChanged() {
                    if (Store.area !== "editor" && scope.within(scope.Window.activeFocusItem, editor)) scope.takeKeys()
                }
            }

            Keys.onPressed: function (event) {
                // First, before even the text-input guard: while finding, every
                // key is the answer, and find cannot start from a field.
                if (Store.finding) {
                    event.accepted = true
                    let held = QtKeys.modifierFromQtKey(event.key)
                    if (held !== "") {
                        // Show the modifiers live; only a real key ends the wait.
                        if (!event.isAutoRepeat)
                            Store.heldMods = QtKeys.heldMods(event.key, event.modifiers, true)
                        return
                    }
                    // A held key repeats; the first press already answered.
                    if (event.isAutoRepeat) return
                    let c = Capture.comboFrom(event.key, event.modifiers)
                    if (c !== null) Store.found(c.mods, c.key)
                    return
                }
                var mod = QtKeys.modifierFromQtKey(event.key)
                // Auto-repeat would re-assert a modifier that was just
                // released; for every other key it is wanted, so a held arrow
                // keeps moving.
                if (mod !== "") { if (!event.isAutoRepeat) Store.hold(mod); return }
                let m = event.modifiers & ~Qt.KeypadModifier
                // Plain Tab and Shift+Tab only, and before the text-input
                // guard: Tab always moves between areas, from the search field
                // too (it is out of Qt's Tab chain, so its Tab bubbles here).
                // The editor walks its own controls first and only hands Tab
                // on, through tabOut, when the walk runs off an end.
                if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab)
                        && (m === Qt.NoModifier || m === Qt.ShiftModifier)) {
                    // One step per press, like the other one-shot keys.
                    if (!event.isAutoRepeat) scope.moveArea(event.key === Qt.Key_Backtab || m === Qt.ShiftModifier)
                    event.accepted = true
                    return
                }
                // Text fields leave arrows and Return unaccepted, so without
                // this they would move the selection under the user's typing.
                // Everything non-modifier (including "/") sits below it.
                var focused = scope.Window.activeFocusItem
                if (focused && (focused instanceof TextInput || focused instanceof TextEdit)) return
                // One-shot keys fire once per press; only arrows repeat.
                if (event.isAutoRepeat && [Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right].indexOf(event.key) < 0) {
                    event.accepted = true
                    return
                }
                if (event.key === Qt.Key_F && m === Qt.NoModifier && Store.draft === null) {
                    Store.startFind()
                    event.accepted = true
                    return
                }
                if (event.key === Qt.Key_Slash) {
                    header.focusSearch()
                    event.accepted = true
                    return
                }
                // Handled here, past the text-input guard, because this scope
                // only gets keys when no popup has focus: typing in a field or
                // an open dialog (with its own Apply) can never apply by accident.
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                        && (event.modifiers & Qt.ControlModifier)) {
                    if (Store.dirty && !Store.busy && !Store.readOnly && Store.draft === null)
                        Store.apply()
                    event.accepted = true
                    return
                }
                // The editor has the keys: nothing below is for it.
                if (Store.area === "editor") return
                if (event.key === Qt.Key_E && m === Qt.NoModifier) {
                    Store.editBind(Store.area === "list" ? Store.focusedBind()
                                   : (Store.listed.length > 0 ? Store.listed[0] : null))
                    event.accepted = true
                    return
                }
                if (event.key === Qt.Key_A && m === Qt.NoModifier) {
                    Store.newBindOnSelected()
                    event.accepted = true
                    return
                }
                if (event.key === Qt.Key_D && m === Qt.ControlModifier) {
                    if (Store.dirty) diffDialog.open()
                    event.accepted = true
                    return
                }
                if (event.key === Qt.Key_Z && m === Qt.ControlModifier) {
                    if (Store.dirty && !Store.busy) Store.discard()
                    event.accepted = true
                    return
                }
                if (Store.area === "list") {
                    if (event.key === Qt.Key_Up || event.key === Qt.Key_Down) {
                        Store.listIndex = Focus.clampIndex(Store.listIndex + (event.key === Qt.Key_Up ? -1 : 1), Store.listRows.length)
                        event.accepted = true
                    } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        // An "Also bound as" row switches the view; a bind opens.
                        let row = Store.focusedRow()
                        if (row !== null && row.kind === "other") Store.pickOther(row.bind)
                        else Store.editBind(Store.focusedBind())
                        event.accepted = true
                    } else if (event.key === Qt.Key_Delete) {
                        let target = Store.focusedBind()
                        if (target !== null) Store.deleteBind(target.uid)
                        event.accepted = true
                    }
                    return
                }
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
            Keys.onReleased: function (event) {
                if (event.isAutoRepeat) return
                var mod = QtKeys.modifierFromQtKey(event.key)
                if (mod !== "") Store.release(mod)
            }
            // Qt runs this before onPressed and accepts the event, so Escape
            // while finding has to be handled here or it would quit.
            Keys.onEscapePressed: function (event) {
                if (Store.finding) {
                    // Only a bare Escape cancels; with a modifier it is a combo
                    // to find, which onPressed captures once this is unaccepted.
                    if ((event.modifiers & ~Qt.KeypadModifier) !== 0) {
                        event.accepted = false
                        return
                    }
                    event.accepted = true
                    Store.stopFind()
                    return
                }
                if (Store.requestQuit()) {
                    Store.stopFind()
                    Qt.quit()
                }
            }

            ColumnLayout {
                id: body
                anchors.fill: parent
                anchors.margins: Spacing.lg
                spacing: Spacing.md

                Header {
                    id: header
                    Layout.fillWidth: true
                    Layout.fillHeight: false
                    onLeaveSearch: scope.takeKeys()
                    onBackupsRequested: backupsDialog.open()
                    onExportRequested: exportDialog.open()
                    onSubmapRequested: submapDialog.open()
                    onSettingsRequested: settingsPopup.open()
                    onFindRequested: {
                        scope.takeKeys()
                        Store.startFind()
                    }
                }

                // A layout inside a layout fills spare height by default; these
                // two must not, or they open an empty band under the header.
                Banner { Layout.fillWidth: true; Layout.fillHeight: false }

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
                    // Tinted over the pane's own colour, never translucent over it.
                    color: Store.area === "keyboard"
                           ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentPrimary.r, Colors.accentPrimary.g, Colors.accentPrimary.b, 0.05))
                           : Colors.bgBase
                    radius: Radius.md
                    border.width: Store.area === "keyboard" ? 3 : 1
                    border.color: Store.area === "keyboard" ? Colors.accentPrimary : Colors.borderSubtle

                    ColumnLayout {
                        id: keyboardColumn
                        anchors.fill: parent
                        anchors.margins: Spacing.lg
                        spacing: Spacing.sm

                        ModifierBar { Layout.fillWidth: true }

                        RowLayout {
                            id: keyRow
                            Layout.fillWidth: true
                            spacing: Spacing.lg
                            // From the pane's width, which only the window sets.
                            // Not from this row's: a row's width can follow its
                            // contents' minimum widths, and those are in keys.
                            readonly property real unit: Layouts.unitFor(keyboardColumn.width - spacing * 2 - 1)

                            Keyboard {
                                id: keyboard
                                Layout.fillWidth: true
                                Layout.preferredHeight: implicitHeight
                                unit: keyRow.unit
                            }

                            Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: Colors.borderSubtle }

                            ExtraKeys {
                                Layout.alignment: Qt.AlignTop
                                unit: keyRow.unit
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Spacing.md

                    BindPanel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }

                    Editor {
                        id: editor
                        // The editor is already the area; moveArea steps from it.
                        onTabOut: function (back) {
                            Store.area = "editor"
                            scope.moveArea(back)
                        }
                        Layout.preferredWidth: 340
                        Layout.fillHeight: true
                    }
                }

                StagedBar {
                    Layout.fillWidth: true
                    onReviewRequested: diffDialog.open()
                }
            }
        }

        DiffDialog { id: diffDialog }
        BackupsDialog { id: backupsDialog }
        ExportDialog { id: exportDialog }
        SettingsPopup { id: settingsPopup }
        SubmapDialog { id: submapDialog }
    }
}
