import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/model.js" as Model

// One bind: its keys, what it does, where it comes from, and what can be done
// with it. A bind the last apply refused is outlined in the critical colour.
Rectangle {
    id: root
    property var bind
    // The binds sharing this one's key, when it is listed in a conflict.
    property var group: []
    // Where this row sits in the list, so the list's cursor can mark it.
    property int position: -1
    readonly property bool focused: position >= 0 && Store.area === "list" && position === Store.listIndex
    // Hand-only conflicts are real but never stop an apply, so they are not
    // drawn as errors.
    readonly property bool inConflict: root.group.length > 1 && Model.blocks(root.group)
    readonly property bool refused: root.bind.id !== null && Store.errors.some(function (e) { return e.id === root.bind.id })
    readonly property bool editing: Store.draft !== null
        && ((root.bind.id !== null && Store.draft.id === root.bind.id)
            || (root.bind.source === "hand" && Store.draft.hand !== null && Store.draft.id === null
                && Store.draft.hand.uid === root.bind.uid))

    // A hand bind whose keys hyprKBM could not read cannot be matched by an
    // override or an unbind, so changing it here would do nothing useful.
    readonly property bool untouchable: root.bind.source === "hand" && root.bind.combo === null
    readonly property string untouchableReason:
        "hyprKBM does not understand the keys of this bind, so it cannot be edited or removed here; change it in hyprland.lua."

    implicitHeight: 36
    radius: Radius.sm
    color: editing || focused ? Colors.bgSurfaceAlt : hover.hovered ? Colors.bgSurface : "transparent"
    border.width: refused || focused ? 1 : 0
    border.color: refused ? Colors.statusCritical : Colors.accentPrimary

    HoverHandler { id: hover }
    QC.ToolTip.visible: hover.hovered && root.untouchable
    QC.ToolTip.text: root.untouchableReason

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
            enabled: !Store.readOnly
            onClicked: Store.keepBoth(root.bind.uid)
        }
        Action {
            text: "Edit (E)"
            enabled: !Store.readOnly && !root.untouchable && root.bind.dispatcher !== null && root.bind.dispatcher.__function === undefined
            onClicked: Store.edit(root.bind.uid)
        }
        Action {
            text: "Remove"
            enabled: !Store.readOnly && !root.untouchable
            onClicked: Store.deleteBind(root.bind.uid)
        }
    }
}
