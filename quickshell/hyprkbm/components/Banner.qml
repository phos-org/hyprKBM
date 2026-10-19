import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"

// Things that are wrong with the setup rather than with a bind: the config
// could not be read completely, keybinds.json cannot be used, or the watcher
// is not running (so binds would vanish at the next reload).
ColumnLayout {
    id: root
    spacing: Spacing.xs
    readonly property var doc: Store.doc

    component Line: Rectangle {
        id: line
        property string message: ""
        property string button: ""
        signal pressed()
        Layout.fillWidth: true
        visible: message !== ""
        implicitHeight: lineRow.implicitHeight + Spacing.sm * 2
        radius: Radius.sm
        color: Qt.tint(Colors.bgBase, Qt.rgba(Colors.statusCritical.r, Colors.statusCritical.g, Colors.statusCritical.b, 0.12))
        border.width: 1
        border.color: Colors.statusCritical
        RowLayout {
            id: lineRow
            anchors.fill: parent
            anchors.margins: Spacing.sm
            Text {
                Layout.fillWidth: true
                text: line.message
                wrapMode: Text.WordWrap
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeSmall
            }
            Action {
                visible: line.button !== ""
                text: line.button
                onClicked: line.pressed()
            }
        }
    }

    Line {
        message: root.doc && root.doc.readerError
                 ? "hyprland.lua could not be read completely, so some binds may be missing and nothing can be applied: " + root.doc.readerError
                 : ""
        button: "Reload"
        onPressed: Store.reload()
    }

    Line {
        message: root.doc && root.doc.modelError
                 ? "keybinds.json cannot be used, so the panel is read-only: " + root.doc.modelError
                   + (root.doc.backups.length > 0 ? " Restoring a backup from Backups replaces it." : "")
                 : ""
    }

    Line {
        message: root.doc && root.doc.watcher !== "active"
                 ? "The hyprkbm-watch service is " + root.doc.watcher + ", so hyprKBM's binds will be gone after the next Hyprland reload."
                 : ""
        button: "Start it"
        onPressed: Store.startWatcher()
    }
}
