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
            }
        }
    }
}
