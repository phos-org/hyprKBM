import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// The modifiers the keyboard is showing. Click to toggle; holding the real
// ones shows them for as long as they are held.
RowLayout {
    id: root
    spacing: Spacing.sm

    Repeater {
        model: ["SUPER", "CTRL", "ALT", "SHIFT"]
        delegate: Rectangle {
            id: chip
            required property string modelData
            readonly property bool picked: Store.mods.indexOf(modelData) >= 0
            implicitWidth: chipText.implicitWidth + Spacing.lg
            implicitHeight: 24
            radius: height / 2
            color: picked ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentSecondary.r, Colors.accentSecondary.g, Colors.accentSecondary.b, 0.15)) : "transparent"
            border.width: 1
            border.color: picked ? Colors.accentSecondary : Colors.borderSubtle

            Text {
                id: chipText
                anchors.centerIn: parent
                text: chip.modelData
                color: chip.picked ? Colors.accentSecondary : Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: Store.toggleMod(chip.modelData)
            }
        }
    }

    Text {
        Layout.fillWidth: true
        text: "click to toggle, or hold them on your keyboard · " + Store.layout.name
              + (Store.submap === "" ? "" : " · submap " + Store.submap)
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        elide: Text.ElideRight
    }

    Repeater {
        model: [["bound", Colors.accentPrimary], ["overlap", Colors.accentPrimary], ["conflict", Colors.statusCritical], ["free", Colors.textSecondary]]
        delegate: Row {
            id: legend
            required property var modelData
            spacing: Spacing.xs
            Rectangle {
                width: 9; height: 9; radius: 2
                color: legend.modelData[1]
                // Like the keycap: an overlap is a bound key outlined in the conflict colour.
                border.width: legend.modelData[0] === "overlap" ? 1 : 0
                border.color: Colors.statusCritical
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: legend.modelData[0]
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }
    }
}
