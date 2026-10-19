import QtQuick
import QtQuick.Controls
import "../config"

// ComboBox restyled end to end. The control is kept for its keyboard handling
// (arrows, type-ahead, Escape) which is exactly what a mouse-only settings
// panel is usually missing; none of its default painting survives.
ComboBox {
    id: root
    property bool danger: false

    implicitHeight: 30
    font.family: Typography.family
    font.pixelSize: Typography.sizeBody

    background: Rectangle {
        color: root.enabled ? Colors.bgSurface : Colors.bgBase
        radius: Radius.sm
        border.width: root.activeFocus ? 2 : 1
        border.color: root.danger ? Colors.statusCritical
                    : root.activeFocus ? Colors.accentPrimary
                    : root.hovered ? Colors.borderStrong
                    : Colors.borderSubtle

        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    contentItem: Text {
        leftPadding: Spacing.sm
        rightPadding: Spacing.xl
        text: root.displayText
        color: root.enabled ? Colors.textPrimary : Colors.textTertiary
        font: root.font
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: root.width - width - Spacing.sm
        y: (root.height - height) / 2
        text: "▾"
        color: root.enabled ? Colors.textSecondary : Colors.textTertiary
        font.pixelSize: Typography.sizeBody
    }

    popup: Popup {
        y: root.height + 2
        width: root.width
        implicitHeight: Math.min(contentItem.implicitHeight + 2, 260)
        padding: 1

        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: 1
            border.color: Colors.borderStrong
        }

        contentItem: ListView {
            clip: true
            implicitHeight: contentHeight
            model: root.popup.visible ? root.delegateModel : null
            currentIndex: root.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
    }

    delegate: ItemDelegate {
        width: root.width
        height: 28
        highlighted: root.highlightedIndex === index

        background: Rectangle {
            color: highlighted ? Colors.bgSurfaceAlt : "transparent"
            radius: Radius.sm
        }
        contentItem: Text {
            leftPadding: Spacing.sm
            text: modelData
            color: highlighted ? Colors.textPrimary : Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }
}
