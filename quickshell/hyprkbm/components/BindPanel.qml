pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/layouts.js" as Layouts
import "../lib/model.js" as Model

// Every bind on the selected key -- or every match, while searching -- with
// conflicts called out, binds this change removes, and the binds no keycap
// shows.
Rectangle {
    id: root
    // Tinted over the pane's own colour, never translucent over it.
    color: Store.area === "list"
           ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentPrimary.r, Colors.accentPrimary.g, Colors.accentPrimary.b, 0.05))
           : Colors.bgBase
    radius: Radius.md
    border.width: Store.area === "list" ? 3 : 1
    border.color: Store.area === "list" ? Colors.accentPrimary : Colors.borderSubtle

    // Scrolls only; the rows' sizes never depend on it.
    function ensureVisible() {
        let n = Store.listed.length
        let row = Store.listIndex < n ? rows.itemAt(Store.listIndex) : otherRows.itemAt(Store.listIndex - n)
        if (!row) return
        let fl = scroll.contentItem as Flickable
        if (row.y < fl.contentY) fl.contentY = row.y
        else if (row.y + row.height > fl.contentY + fl.height) fl.contentY = row.y + row.height - fl.height
    }
    Connections {
        target: Store
        function onListIndexChanged() { root.ensureVisible() }
        // After the rows of the new view are laid out.
        function onPicked() { Qt.callLater(root.ensureVisible) }
    }

    readonly property bool searching: !Store.parsedQuery.empty
    readonly property string keyText: Store.selectedKey === "" ? ""
        : Keys.display(Store.mods, Layouts.keyName(Store.layout, Store.selectedKey))
    readonly property var conflictGroup: searching ? []
        : Store.listed.filter(function (b) { return !b.allowConflict })
    readonly property bool conflicted: conflictGroup.length > 1
    readonly property bool blocking: conflicted && Model.blocks(conflictGroup)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Spacing.md
        spacing: Spacing.sm

        Text {
            text: root.searching ? "Search · " + Store.listed.length + " matches"
                : root.keyText === "" ? "Pick a key"
                : root.keyText + " · " + (Store.submap === "" ? "global" : Store.submap)
                  + " · " + Store.listed.length + (Store.listed.length === 1 ? " bind" : " binds")
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            font.capitalization: Font.AllUppercase
        }

        QC.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 2

                Repeater {
                    id: rows
                    model: Store.listed
                    delegate: BindRow {
                        required property var modelData
                        required property int index
                        position: index
                        Layout.fillWidth: true
                        bind: modelData
                        group: modelData.allowConflict ? [] : root.conflictGroup
                    }
                }

                Text {
                    visible: root.conflicted
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: root.blocking
                        ? "⚠ These all fire on " + root.keyText + ". Remove one, keep both, or edit one onto other keys."
                        : "These both come from hyprland.lua and both fire on " + root.keyText + ". That does not stop an apply; edit or remove one to change it."
                    color: root.blocking ? Colors.statusCritical : Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }

                Repeater {
                    model: root.searching ? [] : Store.removedHere
                    delegate: RowLayout {
                        id: removedRow
                        required property var modelData
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: "Removed: " + removedRow.modelData.hand.describe + " (" + removedRow.modelData.hand.where + ")"
                            color: Colors.textSecondary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeSmall
                            font.strikeout: true
                            elide: Text.ElideRight
                        }
                        Action { text: "Restore"; enabled: !Store.readOnly; onClicked: Store.restoreHand(removedRow.modelData.hand) }
                    }
                }

                Text {
                    visible: !root.searching && root.keyText !== "" && Store.otherCombos.length > 0
                    Layout.topMargin: Spacing.sm
                    text: "Also bound as"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                    font.capitalization: Font.AllUppercase
                }

                // After the listed binds in the cursor's walk (Store.listRows).
                Repeater {
                    id: otherRows
                    model: root.searching || root.keyText === "" ? [] : Store.otherCombos
                    delegate: BindRow {
                        required property var modelData
                        required property int index
                        position: Store.listed.length + index
                        other: true
                        Layout.fillWidth: true
                        bind: modelData
                    }
                }

                Action {
                    visible: !root.searching && root.keyText !== ""
                    enabled: !Store.readOnly
                    text: "+ Add a bind on " + root.keyText + " (A)"
                    onClicked: Store.newBindOnSelected()
                }

                Text {
                    visible: Store.merged.stale.length > 0
                    Layout.topMargin: Spacing.md
                    text: "Stale · edits whose hyprland.lua bind is gone"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                    font.capitalization: Font.AllUppercase
                }

                Text {
                    visible: Store.merged.stale.length > 0 && !!(Store.doc && Store.doc.readerError)
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "hyprland.lua was not read completely, so these may not be stale at all. Fix it and reload before forgetting anything."
                    color: Colors.statusCritical
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }

                Repeater {
                    model: Store.merged.stale
                    delegate: RowLayout {
                        id: staleRow
                        required property var modelData
                        Layout.fillWidth: true
                        Text {
                            Layout.fillWidth: true
                            text: staleRow.modelData.message
                            wrapMode: Text.WordWrap
                            color: Colors.textSecondary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeSmall
                        }
                        Action { text: "Forget"; enabled: !Store.readOnly && !(Store.doc && Store.doc.readerError); onClicked: Store.forget(staleRow.modelData) }
                    }
                }

                Text {
                    visible: !root.searching && Store.unplaced.length > 0
                    Layout.topMargin: Spacing.md
                    text: "Unplaced · binds no keycap shows"
                    color: Colors.textSecondary
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                    font.capitalization: Font.AllUppercase
                }

                Repeater {
                    model: root.searching ? [] : Store.unplaced
                    delegate: BindRow {
                        required property var modelData
                        Layout.fillWidth: true
                        bind: modelData
                    }
                }
            }
        }
    }
}
