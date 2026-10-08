import QtQuick
import QtQuick.Layouts
import "../config"

// Label above control, per the shell's existing form rhythm. The label is a
// sibling rather than a placeholder so it stays readable once a value is set.
ColumnLayout {
    id: root
    property string label: ""
    property string hint: ""
    default property alias content: holder.data

    spacing: Spacing.xs
    Layout.fillWidth: true

    Text {
        text: root.label
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        font.weight: Typography.weightMedium
    }

    Item {
        id: holder
        Layout.fillWidth: true
        implicitHeight: childrenRect.height
    }

    Text {
        visible: root.hint !== ""
        text: root.hint
        color: Colors.accentSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
}
