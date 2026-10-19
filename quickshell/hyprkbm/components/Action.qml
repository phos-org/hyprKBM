import QtQuick
import QtQuick.Controls
import "../config"

Button {
    id: root
    property bool primary: false

    implicitHeight: 30
    // A click never keeps the keys: in the main window they belong to its
    // FocusScope, whose Tab moves between areas. Dialogs still Tab through us.
    focusPolicy: Qt.TabFocus
    leftPadding: Spacing.lg
    rightPadding: Spacing.lg

    background: Rectangle {
        radius: Radius.sm
        color: !root.enabled ? Colors.bgBase
             : root.primary ? (root.down ? Colors.accentPrimaryDim : Colors.accentPrimary)
             : (root.down || root.hovered ? Colors.bgSurfaceAlt : Colors.bgSurface)
        border.width: root.activeFocus ? 2 : 1
        border.color: !root.enabled ? Colors.borderSubtle
                    : root.activeFocus ? Colors.accentPrimary
                    : root.primary ? Colors.accentPrimary
                    : root.hovered ? Colors.borderStrong : Colors.borderSubtle
        Behavior on color { ColorAnimation { duration: 110 } }
    }

    contentItem: Text {
        text: root.text
        // On the filled primary button the label sits on the primary accent,
        // so it takes the void rather than the usual body colour.
        color: !root.enabled ? Colors.textTertiary
             : root.primary ? Colors.bgVoid : Colors.textPrimary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        font.weight: root.primary ? Typography.weightMedium : Typography.weightRegular
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    // Physical press feedback, matched to the tile lift on the canvas.
    scale: down ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: 80 } }
}
