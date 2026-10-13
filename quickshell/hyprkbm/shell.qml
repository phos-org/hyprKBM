import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import "config"
import "components"
import "state"
import "lib/qtkeys.js" as QtKeys
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
            onActiveFocusChanged: if (!activeFocus) Store.heldMods = []
            Window.onActiveChanged: if (!Window.active) Store.heldMods = []

            Keys.onPressed: function (event) {
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
                if (event.key === Qt.Key_Slash) {
                    header.focusSearch()
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
            Keys.onEscapePressed: {
                if (Store.draft !== null) Store.cancelEdit()
                else Qt.quit()
            }

            ColumnLayout {
                id: body
                anchors.fill: parent
                anchors.margins: Spacing.lg
                spacing: Spacing.md

                Header {
                    id: header
                    Layout.fillWidth: true
                    onLeaveSearch: scope.forceActiveFocus()
                }

                Banner { Layout.fillWidth: true }

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
                            // From the row's own width, which its parent sets;
                            // nothing inside the row feeds back into it.
                            readonly property real unit: Layouts.unitFor(width - spacing * 2 - 1)

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
                }
            }
        }
    }
}
