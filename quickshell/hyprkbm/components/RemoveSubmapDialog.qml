pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"

// Confirms removing a submap, saying which binds go with it. Staged like any
// other edit, so Apply saves it and Ctrl+Z brings it back.
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

    property string name: ""
    readonly property var use: Store.submapUse(name)

    function ask(submap) {
        name = submap
        open()
    }

    function count(n, what) { return n + " " + what + (n === 1 ? "" : "s") }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Text {
            text: "Remove the submap " + root.name + "?"
            color: Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }

        Text {
            Layout.fillWidth: true
            text: root.use.inside + root.use.entering === 0
                ? "It has no binds."
                : "This also removes " + [root.use.inside > 0 ? root.count(root.use.inside, "bind") + " in it" : "",
                                          root.use.entering > 0 ? root.count(root.use.entering, "bind") + " that enter it" : ""]
                                         .filter(function (s) { return s !== "" }).join(" and ") + "."
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: "Remove"
                primary: true
                enabled: Store.removableSubmap(root.name) && !Store.busy
                onClicked: { Store.removeSubmap(root.name); root.close() }
            }
        }
    }
}
