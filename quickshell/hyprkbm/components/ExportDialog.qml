pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import Quickshell
import "../config"
import "../state"

// Writes the cheatsheet as Markdown with `hyprkbm --export md`. It exports
// what is applied, not what is staged.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: 460
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Text {
            text: "Export a Markdown cheatsheet of the applied binds"
            color: Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }

        QC.TextField {
            id: path
            Layout.fillWidth: true
            text: (Quickshell.env("HOME") || "") + "/keybinds.md"
            color: Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            background: Rectangle {
                color: Colors.bgBase
                radius: Radius.sm
                border.width: 1
                border.color: path.activeFocus ? Colors.borderStrong : Colors.borderSubtle
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: "Export"
                primary: true
                enabled: path.text.trim() !== ""
                onClicked: { Store.exportTo(path.text.trim()); root.close() }
            }
        }
    }
}
