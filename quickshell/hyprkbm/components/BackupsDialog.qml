pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/diff.js" as Diff

// The last thirty versions of keybinds.json, each with what restoring it
// would change. Restoring stages the backup and applies it, through the same
// checks as any other apply.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: Math.min(900, parent ? parent.width - Spacing.xl * 2 : 900)
    height: Math.min(600, parent ? parent.height - Spacing.xl * 2 : 600)
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 2) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    property string chosen: ""
    readonly property var names: Store.doc ? Store.doc.backups : []
    readonly property var lines: Store.backup ? Diff.lineDiff(Store.doc.currentLua, Store.backup.lua) : []

    function when(name) {
        // 20261008T173647613251 -> 2026-10-08 17:36:47
        return name.slice(0, 4) + "-" + name.slice(4, 6) + "-" + name.slice(6, 8)
             + " " + name.slice(9, 11) + ":" + name.slice(11, 13) + ":" + name.slice(13, 15)
    }

    onOpened: { chosen = ""; Store.backup = null }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: RowLayout {
        spacing: Spacing.lg

        ListView {
            Layout.preferredWidth: 220
            Layout.fillHeight: true
            clip: true
            model: root.names
            delegate: Rectangle {
                id: row
                required property string modelData
                width: ListView.view.width
                height: 30
                radius: Radius.sm
                color: root.chosen === row.modelData ? Colors.bgSurfaceAlt : "transparent"
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Spacing.sm
                    text: root.when(row.modelData)
                    color: Colors.textPrimary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeBody
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: { root.chosen = row.modelData; Store.loadBackup(row.modelData) }
                }
            }
            Text {
                visible: root.names.length === 0
                text: "No backups yet. One is made before every apply."
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
                wrapMode: Text.WordWrap
                width: parent.width
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
                text: root.chosen === "" ? "Pick a backup to see what restoring it would change."
                    : Store.backup === null ? "Reading…"
                    : "Restoring " + root.when(root.chosen) + " · +" + Diff.counts(root.lines).added
                      + " −" + Diff.counts(root.lines).removed + " lines of keybinds.lua"
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
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
                    text: "Restore"
                    primary: true
                    enabled: Store.backup !== null && !Store.busy
                    onClicked: { Store.restoreBackup(); root.close() }
                }
            }
        }
    }
}
