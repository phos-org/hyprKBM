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
            }
            Window.onActiveChanged: if (!Window.active) { Store.heldMods = []; Store.stopFind() }

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
                // Text fields leave arrows and Return unaccepted, so without
                // this they would move the selection under the user's typing.
                // Everything non-modifier (including "/") sits below it.
                var focused = scope.Window.activeFocusItem
                if (focused && (focused instanceof TextInput || focused instanceof TextEdit)) return
                if (event.key === Qt.Key_F && event.modifiers === Qt.NoModifier && Store.draft === null) {
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
                    onLeaveSearch: scope.forceActiveFocus()
                    onBackupsRequested: backupsDialog.open()
                    onExportRequested: exportDialog.open()
                    onSubmapRequested: submapDialog.open()
                    onSettingsRequested: settingsPopup.open()
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
