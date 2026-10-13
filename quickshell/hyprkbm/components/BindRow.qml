import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// One bind: its keys, what it does, where it comes from, and what can be done
// with it. A bind the last apply refused is outlined in the critical colour.
Rectangle {
    id: root
    property var bind
    property bool inConflict: false
    readonly property bool refused: root.bind.id !== null && Store.errors.some(function (e) { return e.id === root.bind.id })
    readonly property bool editing: Store.draft !== null
        && ((root.bind.id !== null && Store.draft.id === root.bind.id)
            || (root.bind.source === "hand" && Store.draft.hand !== null && Store.draft.id === null
                && Store.draft.hand.uid === root.bind.uid))

    implicitHeight: 36
    radius: Radius.sm
    color: editing ? Colors.bgSurfaceAlt : hover.hovered ? Colors.bgSurface : "transparent"
    border.width: refused ? 1 : 0
    border.color: Colors.statusCritical

    HoverHandler { id: hover }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Spacing.sm
        anchors.rightMargin: Spacing.sm
        spacing: Spacing.sm

        Repeater {
            model: root.bind.mods.concat([root.bind.key])
            delegate: Rectangle {
                required property string modelData
                implicitWidth: keyText.implicitWidth + Spacing.sm
                implicitHeight: 20
                radius: 4
                color: Colors.bgSurfaceAlt
                border.width: 1
                border.color: Colors.borderSubtle
                Text {
                    id: keyText
                    anchors.centerIn: parent
                    text: parent.modelData
                    color: Colors.textPrimary
                    font.family: "monospace"
                    font.pixelSize: Typography.sizeSmall
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.bind.describe + (root.bind.description !== "" ? "  ·  " + root.bind.description : "")
            color: root.inConflict ? Colors.statusCritical : Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            elide: Text.ElideRight
        }

        Rectangle {
            implicitWidth: sourceText.implicitWidth + Spacing.md
            implicitHeight: 18
            radius: 9
            color: "transparent"
            border.width: 1
            border.color: root.bind.source === "hyprkbm" ? Colors.accentTertiary
                        : root.bind.source === "override" ? Colors.accentSecondary
                        : Colors.textSecondary
            Text {
                id: sourceText
                anchors.centerIn: parent
                text: root.bind.source === "hand" ? root.bind.where
                    : root.bind.source === "override" ? "overrides " + root.bind.hand.where
                    : "hyprKBM"
                color: parent.border.color
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }

        Action {
            text: "Keep both"
            visible: root.inConflict && root.bind.id !== null
            onClicked: Store.keepBoth(root.bind.uid)
        }
        Action {
            text: "Edit"
            enabled: !Store.readOnly && root.bind.dispatcher !== null && root.bind.dispatcher.__function === undefined
            onClicked: Store.edit(root.bind.uid)
        }
        Action {
            text: "Remove"
            enabled: !Store.readOnly
            onClicked: Store.deleteBind(root.bind.uid)
        }
    }
}
