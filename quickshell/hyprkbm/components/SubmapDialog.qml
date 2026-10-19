pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as KeyNames

// A new submap: its name and the key that leaves it. A bind enters it with
// the "Enter submap" action.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: 380
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    readonly property string problem: name.text.trim() === "" ? "Give it a name."
        : Store.submaps.indexOf(name.text.trim()) >= 0 ? "There is already a submap called " + name.text.trim() + "."
        : KeyNames.parse(reset.text) === null ? "The reset key must be a key, like escape."
        : ""

    onOpened: { name.text = ""; reset.text = "escape"; name.forceActiveFocus() }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Name"
            QC.TextField {
                id: name
                width: parent.width
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
        }

        Field {
            label: "Key that leaves it"
            QC.TextField {
                id: reset
                width: parent.width
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
        }

        Text {
            visible: root.problem !== ""
            text: root.problem
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: "Create"
                primary: true
                enabled: root.problem === "" && !Store.readOnly
                onClicked: { Store.addSubmap(name.text.trim(), reset.text.trim()); root.close() }
            }
        }
    }
}
