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
import "lib/cheatsheet.js" as Cheatsheet

// `hyprkbm --cheatsheet`: the panel's keyboard, read-only and full screen,
// lit by the modifiers you hold. It shares the panel's Store to read binds
// and never stages or applies anything. Esc or a click closes it.
ShellRoot {
    // The interface Quickshell lints against is uncreatable; the Wayland one it
    // loads in its place is not (RevertOverlay in hypr-displays lints the same).
    PanelWindow { // qmllint disable uncreatable-type
        id: sheet

        // The output you are looking at, picked once: a binding would move the
        // sheet to wherever focus went next. Hyprland names its focused monitor
        // only after its first reply, so the sheet waits for that (or, if it
        // never comes, takes the first output) before it is shown at all.
        property ShellScreen output: null
        property bool ready: false

        function pickOutput(force) {
            if (sheet.output !== null) return
            var focused = Hyprland.focusedMonitor
            if (focused === null && !force) return
            sheet.output = Cheatsheet.outputFor(Quickshell.screens, focused === null ? "" : focused.name)
            // No output listed yet: wait for the next try rather than show
            // the sheet unplaced and have it move later.
            if (sheet.output === null) return
            // Shown a turn later, so the surface is made on that output and
            // not made first on the default one, then moved.
            Qt.callLater(function () { sheet.ready = true })
        }

        Component.onCompleted: {
            // Not the panel's SUPER chip: with nothing held, nothing is shown held.
            Store.setMods([])
            sheet.pickOutput(false)
        }

        Connections {
            target: Hyprland
            function onFocusedMonitorChanged() { sheet.pickOutput(false) }
        }

        Timer {
            interval: 500
            running: true
            onTriggered: sheet.pickOutput(true)
        }

        // Quitting inside an IPC call could drop its reply, and the CLI would
        // take the silence for "not running" and open another sheet.
        Timer {
            id: quitSoon
            interval: 150
            onTriggered: Qt.quit()
        }

        screen: sheet.output
        visible: sheet.ready
        anchors { top: true; left: true; right: true; bottom: true }
        exclusionMode: ExclusionMode.Ignore
        color: "transparent"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.namespace: "hyprkbm-cheatsheet"
        // Exclusive, so modifier presses and releases come here.
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        IpcHandler {
            target: "cheatsheet"

            function close(): string {
                sheet.visible = false
                quitSoon.start()
                return "closed"
            }

            function state(): string {
                return JSON.stringify({
                    output: sheet.output === null ? "" : sheet.output.name, shown: sheet.visible,
                    loading: Store.loading, error: Store.loadError,
                    mods: Store.mods, keys: Object.keys(Store.keyStates).length
                })
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Colors.bgVoid
            opacity: 0.9
        }

        // A click anywhere closes: the keys are disabled, so they pass it on.
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
                    text: Cheatsheet.title(Store.mods)
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
                    id: keyRow
                    Layout.alignment: Qt.AlignHCenter
                    visible: !Store.loading && Store.loadError === ""
                    spacing: Spacing.lg
                    // From the output's width only: nothing inside feeds back.
                    // The keyboard and the extra keys are ROW_UNITS keys wide,
                    // with one gap between them.
                    readonly property real unit: Layouts.unitFor(sheet.width * 0.8 - Spacing.lg, 96)

                    Keyboard {
                        // Keyboard sets only its height; its width is in keys.
                        Layout.preferredWidth: Layouts.KEYBOARD_UNITS * keyRow.unit
                        Layout.preferredHeight: implicitHeight
                        unit: keyRow.unit
                        interactive: false
                        detailed: true
                    }

                    ExtraKeys {
                        Layout.alignment: Qt.AlignTop
                        unit: keyRow.unit
                        interactive: false
                        detailed: true
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Hold SUPER, SHIFT, CTRL or ALT to see their binds (pressing a combo still runs it) · Esc or a click closes"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }
            }
        }
    }
}
