pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/model.js" as Model

// QtQuick.Controls is namespaced because it has its own Action, which would
// otherwise shadow ours.
// Submaps, search, the conflict stepper and the header's actions. The
// dialogs themselves live in shell.qml; the header only asks for them.
RowLayout {
    id: root
    spacing: Spacing.md

    signal backupsRequested()
    signal exportRequested()
    signal submapRequested()
    signal settingsRequested()
    // Escape in the search hands focus back to the window, for the arrow keys.
    signal leaveSearch()

    function focusSearch() { search.forceActiveFocus() }

    function countIn(name) {
        return Store.merged.binds.filter(function (b) { return b.submap === name }).length
    }

    Text {
        text: "Keybinds"
        color: Colors.textPrimary
        font.family: Typography.family
        font.pixelSize: 18
        font.weight: Typography.weightMedium
    }

    Repeater {
        model: Store.submaps
        delegate: Rectangle {
            id: chip
            required property string modelData
            readonly property bool picked: Store.submap === modelData
            implicitWidth: chipText.implicitWidth + Spacing.lg
            implicitHeight: 24
            radius: height / 2
            color: picked ? Colors.accentPrimary : Colors.bgSurfaceAlt
            Text {
                id: chipText
                anchors.centerIn: parent
                text: (chip.modelData === "" ? "global" : chip.modelData) + " · " + root.countIn(chip.modelData)
                color: chip.picked ? Colors.bgVoid : Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: Store.submap = chip.modelData
            }
        }
    }

    Action {
        text: "+ submap"
        enabled: !Store.readOnly
        onClicked: root.submapRequested()
    }

    QC.TextField {
        id: search
        Layout.fillWidth: true
        placeholderText: "/ search · mod: key: exec: desc: submap: src:"
        text: Store.query
        onTextEdited: Store.query = text
        color: Colors.textPrimary
        placeholderTextColor: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: 1
            border.color: search.activeFocus ? Colors.borderStrong : Colors.borderSubtle
        }
        // Escape leaves the search rather than closing the panel.
        Keys.onEscapePressed: function (event) {
            Store.query = ""
            root.leaveSearch()
            event.accepted = true
        }
    }

    Action {
        readonly property int blocking: Store.merged.conflicts.filter(function (g) { return Model.blocks(g) }).length
        readonly property int shown: blocking > 0 ? blocking : Store.merged.conflicts.length
        visible: Store.merged.conflicts.length > 0
        // Hand-only overlaps are real but never stop an apply, so only a
        // blocking group is called a conflict, and only those are counted.
        text: blocking > 0
            ? "⚠ " + shown + (shown === 1 ? " conflict" : " conflicts")
            : shown + (shown === 1 ? " overlap" : " overlaps")
        onClicked: Store.nextConflict()
    }

    Action { text: "Backups"; onClicked: root.backupsRequested() }
    Action { text: "Export"; onClicked: root.exportRequested() }

    Action {
        text: "Theme"
        onClicked: themePopup.opened ? themePopup.close() : themePopup.open()
        // Declared inside the button so it hangs from it.
        ThemePopup { id: themePopup }
    }

    Action { text: "⋯"; onClicked: root.settingsRequested() }
}
