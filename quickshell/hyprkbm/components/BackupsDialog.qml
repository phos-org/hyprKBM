pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/diff.js" as Diff

// The last thirty versions of keybinds.json, each with what restoring it
// would change. Restoring applies the backup through the same checks as any other
// apply, and is also the way out when keybinds.json is broken.
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
    // The backup whose × was pressed: deleting cannot be undone, so the row
    // asks once more in place.
    property string confirming: ""
    readonly property var names: Store.doc ? Store.doc.backups : []
    // Store.backup can still be an earlier pick while the chosen one loads.
    readonly property bool loaded: Store.backup !== null && Store.backup.name === chosen
    readonly property var lines: loaded ? Diff.lineDiff(Store.doc.currentLua, Store.backup.lua) : []

    // A word that acts like a button, for the backup rows.
    component RowButton: Text {
        id: button
        signal clicked()
        property color tint: Colors.textSecondary
        property color hoverTint: Colors.statusCritical
        color: area.containsMouse ? hoverTint : tint
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        font.weight: Typography.weightMedium
        MouseArea {
            id: area
            anchors.fill: parent
            anchors.margins: -Spacing.xs
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: button.clicked()
        }
    }

    function when(name) {
        // 20261008T173647613251 -> 2026-10-08 17:36:47
        return name.slice(0, 4) + "-" + name.slice(4, 6) + "-" + name.slice(6, 8)
             + " " + name.slice(9, 11) + ":" + name.slice(11, 13) + ":" + name.slice(13, 15)
    }

    onOpened: { chosen = ""; confirming = ""; Store.clearBackup() }

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
                readonly property bool asking: root.confirming === row.modelData
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: Spacing.sm
                    text: row.asking ? "Delete this backup?" : root.when(row.modelData)
                    color: row.asking ? Colors.statusCritical : Colors.textPrimary
                    font.family: Typography.family
                    font.pixelSize: row.asking ? Typography.sizeSmall : Typography.sizeBody
                }
                // Under the buttons, so they keep their own clicks.
                MouseArea {
                    anchors.fill: parent
                    enabled: !row.asking
                    onClicked: { root.confirming = ""; root.chosen = row.modelData; Store.loadBackup(row.modelData) }
                }
                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: Spacing.sm
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Spacing.sm

                    RowButton {
                        visible: !row.asking
                        text: "×"
                        onClicked: root.confirming = row.modelData
                    }
                    RowButton {
                        visible: row.asking
                        text: "Delete"
                        tint: Colors.statusCritical
                        onClicked: {
                            if (root.chosen === row.modelData) root.chosen = ""
                            root.confirming = ""
                            Store.deleteBackup(row.modelData)
                        }
                    }
                    RowButton {
                        visible: row.asking
                        text: "Keep"
                        hoverTint: Colors.textPrimary
                        onClicked: root.confirming = ""
                    }
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
                    : !root.loaded ? "Reading…"
                    : "Restoring " + root.when(root.chosen) + " · +" + Diff.counts(root.lines).added
                      + " −" + Diff.counts(root.lines).removed + " lines of keybinds.lua"
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
            }

            Text {
                visible: root.loaded && Store.restoreRefusal !== ""
                text: Store.restoreRefusal
                color: Colors.textSecondary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
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
                    enabled: Store.backup !== null && Store.backup.name === root.chosen
                             && Store.restoreRefusal === ""
                    onClicked: { Store.restoreBackup(); root.close() }
                }
            }
        }
    }
}
