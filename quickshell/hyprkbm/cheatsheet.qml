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
import "lib/keys.js" as KeyNames
import "lib/keymap.js" as Keymap
import "lib/layouts.js" as Layouts
import "lib/cheatsheet.js" as Cheatsheet

// `hyprkbm --cheatsheet`: the panel's keyboard, read-only and full screen,
// lit by the modifiers you hold. It shares the panel's Store to read binds
// and never stages or applies anything. Press a combo to see what it does,
// Enter to run it; Esc or a click closes.
//
// Hyprland runs a bound combo before any client sees it, so while the sheet
// is shown Hyprland is held in a submap with no binds but SUPER + Escape
// (lib/cheatsheet.js enterLua). The hold is a dead-man switch re-armed every
// few seconds (rearmLua), so the binds come back by themselves if the sheet
// dies; every way out gives them back at once. When Hyprland leaves the
// submap by itself (SUPER + Escape, or the timer), the sheet closes.
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

        // The combo last pressed, { mods, key, keyId }, or null. Its binds are
        // read afresh, so a reload under it shows what is bound now.
        property var selection: null
        readonly property var selectedBinds: sheet.selection === null ? []
            : Keymap.bindsOn(Store.merged.binds, "", sheet.selection.mods, sheet.selection.keyId)

        // Set once the sheet is on its way out: no more holds go out, and the
        // Lua that gives the binds back (or runs the combo) waits for the hold
        // in flight, so it cannot land before it.
        property bool closing: false
        property string finalLua: ""
        property bool flushed: false
        property string holdError: ""
        // Set once the first hold has landed: later ones only re-arm it, and
        // from then on Hyprland leaving the submap closes the sheet.
        property bool held: false

        // Fixed, from type sizes alone, so the keyboard below never moves:
        // the combo, two lines of actions and the status line.
        readonly property int titlePx: Math.round(Typography.sizeBody * 1.8)
        readonly property real titleLineHeight: Math.ceil(sheet.titlePx * 1.5)
        readonly property real bodyLineHeight: Math.ceil(Typography.sizeBody * 1.5)
        readonly property real titleAreaHeight: sheet.titleLineHeight + 3 * sheet.bodyLineHeight + 2 * Spacing.sm

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

        function arm() {
            if (sheet.closing || holdProc.running) return
            holdProc.command = ["hyprctl", "eval", sheet.held ? Cheatsheet.rearmLua(Date.now()) : Cheatsheet.enterLua(Date.now())]
            holdProc.running = true
        }

        // Every way out: hide, then send `lua` (a leave, or a run that leaves
        // first; "" when Hyprland has already left) once no hold is in
        // flight, then quit.
        function finish(lua) {
            if (sheet.closing) return
            sheet.closing = true
            sheet.finalLua = lua
            sheet.visible = false
            if (!holdProc.running) sheet.flush()
            else flushAnyway.start()
        }

        // Detached, so it still goes out as the sheet quits.
        function flush() {
            if (sheet.flushed) return
            sheet.flushed = true
            var lua = sheet.finalLua
            if (lua !== "") Quickshell.execDetached(["hyprctl", "eval", lua])
            quitSoon.start()
        }

        function select(mods, key) {
            if (key === null) return
            var keyId = KeyNames.keyId(key)
            // The sheet's own key toggles it, even while the binds are held.
            if (Cheatsheet.opensSheet(Keymap.bindsOn(Store.merged.binds, "", mods, keyId))) {
                sheet.finish(Cheatsheet.leaveLua())
                return
            }
            sheet.selection = { mods: mods, key: key, keyId: keyId }
            Store.selectedKey = keyId
        }

        function runSelection() {
            if (sheet.selection === null) return
            var lua = Cheatsheet.runLua(sheet.selectedBinds)
            if (lua === null) return
            sheet.finish(lua)
        }

        Component.onCompleted: {
            // Not the panel's SUPER chip: with nothing held, nothing is shown held.
            Store.setMods([])
            Store.selectedKey = ""
            sheet.pickOutput(false)
        }

        Connections {
            target: Hyprland
            function onFocusedMonitorChanged() { sheet.pickOutput(false) }

            // Hyprland left the submap without the sheet: SUPER + Escape, or
            // the dead-man timer. Events before our own entry landed are not
            // about this hold, and the sheet's own leave is already closing.
            function onRawEvent(event) {
                if (sheet.held && !sheet.closing && event.name === "submap"
                        && event.data !== Cheatsheet.SUBMAP)
                    sheet.finish("")
            }
        }

        // Store selects Q whenever a load completes; the sheet outlines only
        // the combo you pressed.
        Connections {
            target: Store
            function onSelectedKeyChanged() {
                var want = sheet.selection === null ? "" : sheet.selection.keyId
                if (Store.selectedKey !== want) Store.selectedKey = want
            }
        }

        Timer {
            interval: 500
            running: true
            onTriggered: sheet.pickOutput(true)
        }

        Timer {
            id: armTimer
            interval: Cheatsheet.ARM_EVERY_MS
            running: sheet.ready && !sheet.closing
            repeat: true
            triggeredOnStart: true
            onTriggered: sheet.arm()
        }

        Process {
            id: holdProc
            stderr: StdioCollector { id: holdErr }
            stdout: StdioCollector { id: holdOut }
            onExited: function (code) {
                if (sheet.closing) { sheet.flush(); return }
                // The Lua may have failed after it switched: give the binds back.
                if (code !== 0) {
                    sheet.holdError = "Binds still run: "
                        + ((holdErr.text || holdOut.text || "Hyprland did not take the hold.").trim())
                    Quickshell.execDetached(["hyprctl", "eval", Cheatsheet.leaveLua()])
                } else {
                    sheet.holdError = ""
                    sheet.held = true
                }
            }
        }

        // A hold that never returns must not keep the sheet alive.
        Timer {
            id: flushAnyway
            interval: 2000
            onTriggered: sheet.flush()
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
                sheet.finish(Cheatsheet.leaveLua())
                return "closed"
            }

            function state(): string {
                return JSON.stringify({
                    output: sheet.output === null ? "" : sheet.output.name, shown: sheet.visible,
                    loading: Store.loading, error: Store.loadError,
                    mods: Store.mods, keys: Object.keys(Store.keyStates).length,
                    selection: sheet.selection === null ? null : KeyNames.display(sheet.selection.mods, sheet.selection.key),
                    binds: sheet.selectedBinds.length, holdError: sheet.holdError
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
            onClicked: sheet.finish(Cheatsheet.leaveLua())
        }

        FocusScope {
            anchors.fill: parent
            focus: true

            // Modifiers already down when the sheet opened show up with the
            // first press or release of any key, through event.modifiers.
            Keys.onPressed: function (event) {
                event.accepted = true
                if (event.key === Qt.Key_Escape) { sheet.finish(Cheatsheet.leaveLua()); return }
                if (event.isAutoRepeat) return
                if (QtKeys.modifierFromQtKey(event.key) !== "") {
                    Store.heldMods = QtKeys.heldMods(event.key, event.modifiers, true)
                    return
                }
                var mods = QtKeys.modsFromQt(event.modifiers)
                Store.heldMods = mods
                // Plain Enter runs; with modifiers it is a combo like any other
                // (SUPER + Return is often the terminal).
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && mods.length === 0) {
                    sheet.runSelection()
                    return
                }
                sheet.select(mods, QtKeys.keysymFromQt(event.key, event.modifiers))
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

                // One fixed height, selected or not, so the keyboard never
                // moves; what does not fit is elided.
                Item {
                    id: titleArea
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: sheet.width * 0.8
                    Layout.preferredHeight: sheet.titleAreaHeight

                    Column {
                        anchors.fill: parent
                        spacing: Spacing.sm

                        Text {
                            width: parent.width
                            height: sheet.titleLineHeight
                            text: sheet.selection === null ? Cheatsheet.title(Store.mods)
                                : KeyNames.display(sheet.selection.mods, Layouts.keyName(Store.layout, sheet.selection.keyId))
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            color: Colors.textPrimary
                            font.family: Typography.family
                            font.pixelSize: sheet.titlePx
                        }

                        // In full, as far as two lines go: the keys clip long actions.
                        Text {
                            width: parent.width
                            height: 2 * sheet.bodyLineHeight
                            text: sheet.selection === null ? "" : Cheatsheet.actions(sheet.selectedBinds)
                            wrapMode: Text.Wrap
                            maximumLineCount: 2
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            color: Colors.textPrimary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeBody
                        }

                        // Errors and loading take the status line, so nothing
                        // is shown or hidden above the keyboard.
                        Text {
                            readonly property bool failed: Store.loadError !== "" || sheet.holdError !== ""
                            width: parent.width
                            height: sheet.bodyLineHeight
                            text: Store.loadError !== "" ? Store.loadError
                                : sheet.holdError !== "" ? sheet.holdError
                                : Store.loading ? "Loading…"
                                : sheet.selection === null ? "" : Cheatsheet.status(sheet.selectedBinds)
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                            color: failed ? Colors.statusCritical : Colors.textSecondary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeBody
                        }
                    }
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
                    text: "Press a combo to see what it does · Enter runs it · Esc closes"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }
            }
        }
    }
}
