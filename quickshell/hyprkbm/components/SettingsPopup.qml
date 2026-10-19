pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"

// The ⋯ menu: keyboard layout, which config is read, and the watcher.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: 420
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    readonly property var layouts: ["ansi", "iso"]

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Keyboard layout"
            Select {
                width: parent.width
                model: ["ANSI", "ISO"]
                currentIndex: root.layouts.indexOf(Store.layoutName)
                onActivated: function (index) { Store.setLayout(root.layouts[index]) }
            }
        }

        Field {
            label: "Config read"
            hint: "Set \"entry\" in ~/.config/hyprkbm/settings.json to read another file."
            Text {
                width: parent.width
                text: Store.doc ? Store.doc.entry : ""
                color: Colors.textPrimary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                elide: Text.ElideMiddle
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "Watcher: " + (Store.doc ? Store.doc.watcher : "unknown")
                color: Store.doc && Store.doc.watcher === "active" ? Colors.textPrimary : Colors.statusCritical
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }
            Action {
                visible: Store.doc !== null && Store.doc.watcher !== "active"
                text: "Start it"
                onClicked: Store.startWatcher()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Action {
                text: "Reload from disk"
                enabled: !Store.dirty
                onClicked: { Store.reload(); root.close() }
            }
            Item { Layout.fillWidth: true }
            Action { text: "Close"; onClicked: root.close() }
        }
    }
}
