import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/model.js" as Model

// What is staged and not yet applied, and the result of the last apply.
// Nothing reaches Hyprland until Apply.
Rectangle {
    id: root
    signal reviewRequested()

    readonly property var counts: Store.dirty ? Model.summary(Store.saved, Store.model) : null
    readonly property string summaryText: {
        if (counts === null) return ""
        var parts = []
        if (counts.added) parts.push("+" + counts.added + " bind" + (counts.added > 1 ? "s" : ""))
        if (counts.changed) parts.push("~" + counts.changed + " changed")
        if (counts.removed) parts.push("−" + counts.removed + " removed")
        if (counts.unbound) parts.push("−" + counts.unbound + " unbound")
        if (counts.restored) parts.push(counts.restored + " restored")
        if (counts.submaps > 0) parts.push("+" + counts.submaps + " submap" + (counts.submaps > 1 ? "s" : ""))
        return parts.join(" · ")
    }

    visible: Store.dirty || Store.status !== ""
    implicitHeight: row.implicitHeight + Spacing.sm * 2
    radius: Radius.md
    color: Store.dirty
           ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentSecondary.r, Colors.accentSecondary.g, Colors.accentSecondary.b, 0.1))
           : Colors.bgBase
    border.width: 1
    border.color: Store.failed ? Colors.statusCritical : Store.dirty ? Colors.accentSecondary : Colors.borderSubtle

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.margins: Spacing.sm
        spacing: Spacing.md

        Text {
            visible: Store.dirty
            text: "Unapplied changes"
            color: Colors.accentSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
            font.weight: Typography.weightMedium
        }
        Text {
            visible: Store.dirty
            text: root.summaryText
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeBody
        }
        Text {
            Layout.fillWidth: true
            text: Store.status
            color: Store.failed ? Colors.statusCritical : Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            elide: Text.ElideRight
        }

        Text {
            // Same rule as Ctrl+Enter: an open edit is not staged yet, so an
            // apply now would leave it out without saying so.
            visible: Store.dirty && Store.draft !== null
            text: "Save or cancel the open edit to apply."
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
        }

        Action { visible: Store.dirty; text: "Review diff (Ctrl+D)"; onClicked: root.reviewRequested() }
        Action { visible: Store.dirty; text: "Discard (Ctrl+Z)"; enabled: !Store.busy; onClicked: Store.discard() }
        Action {
            visible: Store.dirty
            primary: true
            text: Store.busy ? "Applying…" : "Apply (Ctrl+Enter)"
            enabled: !Store.busy && !Store.readOnly && Store.draft === null
            onClicked: Store.apply()
        }
    }
}
