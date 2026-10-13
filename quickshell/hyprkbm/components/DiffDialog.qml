pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/diff.js" as Diff

// The generated keybinds.lua as it is and as it would be, from
// hyprkbm-apply --preview -- which also validates, so errors show here
// before anyone presses Apply.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: Math.min(900, parent ? parent.width - Spacing.xl * 2 : 900)
    height: Math.min(640, parent ? parent.height - Spacing.xl * 2 : 640)
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    readonly property var lines: Store.preview && Store.preview.ok
                                 ? Diff.lineDiff(Store.preview.current, Store.preview.lua) : []
    readonly property var counts: Diff.counts(lines)

    onOpened: Store.requestPreview()

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Text {
            text: Store.preview === null ? "Checking the new keybinds…"
                : Store.preview.ok ? "keybinds.lua · +" + root.counts.added + " −" + root.counts.removed
                : "These changes cannot be applied"
            color: Store.preview !== null && !Store.preview.ok ? Colors.statusCritical : Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }

        Repeater {
            model: Store.preview !== null && !Store.preview.ok ? Store.preview.errors : []
            delegate: Text {
                required property var modelData
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: (modelData.id ? modelData.id + ": " : "") + modelData.message
                color: Colors.statusCritical
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
        }

        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.lines
            QC.ScrollBar.vertical: QC.ScrollBar {}
            delegate: Text {
                required property var modelData
                width: ListView.view.width
                text: modelData.op + " " + modelData.text
                color: modelData.op === "+" ? Colors.accentTertiary
                     : modelData.op === "-" ? Colors.statusCritical
                     : Colors.textSecondary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                elide: Text.ElideRight
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Close"; onClicked: root.close() }
            Action {
                text: "Apply"
                primary: true
                enabled: Store.preview !== null && Store.preview.ok && !Store.busy && !Store.readOnly
                onClicked: { Store.apply(); root.close() }
            }
        }
    }
}
