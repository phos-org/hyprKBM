import QtQuick
import QtQuick.Controls
import "../config"

// Compact switch. Keeps Switch's keyboard and focus behaviour, drops its paint.
Switch {
    id: root

    implicitHeight: 26
    spacing: Spacing.md

    indicator: Rectangle {
        id: track
        implicitWidth: 34
        implicitHeight: 18
        x: root.width - width
        y: (root.height - height) / 2
        radius: height / 2
        // A disabled switch reads as off, whatever it is set to. Left accent-
        // filled at half opacity it looks lit but greyed -- a half-drawn
        // control rather than a deliberate lockout, beside a label that has
        // already gone tertiary.
        color: !root.enabled ? Colors.bgSurfaceAlt
             : root.checked ? Colors.accentPrimaryDim : Colors.bgBase
        border.width: root.activeFocus ? 2 : 1
        border.color: !root.enabled ? Colors.borderSubtle
                    : root.activeFocus ? Colors.accentPrimary
                    : root.checked ? Colors.accentPrimary : Colors.borderSubtle
        opacity: root.enabled ? 1 : 0.5

        Behavior on color { ColorAnimation { duration: 140 } }

        Rectangle {
            width: 12
            height: 12
            radius: 6
            y: 3
            x: root.checked ? parent.width - width - 3 : 3
            color: root.checked ? Colors.textPrimary : Colors.textTertiary
            Behavior on x { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: 140 } }
        }
    }

    // The label reserves the track's width, otherwise a long label runs
    // straight underneath the switch.
    contentItem: Text {
        text: root.text
        rightPadding: track.width + root.spacing
        color: root.enabled ? Colors.textPrimary : Colors.textTertiary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
