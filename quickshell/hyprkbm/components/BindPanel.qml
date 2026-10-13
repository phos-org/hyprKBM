pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/layouts.js" as Layouts

// Every bind on the selected key -- or every match, while searching -- with
// conflicts called out, binds this change removes, and the binds no keycap
// shows.
Rectangle {
    id: root
    color: Colors.bgBase
    radius: Radius.md
    border.width: 1
    border.color: Colors.borderSubtle

    readonly property bool searching: !Store.parsedQuery.empty
    readonly property string keyText: Store.selectedKey === "" ? ""
        : Keys.display(Store.mods, Layouts.keyName(Store.layout, Store.selectedKey))
    readonly property bool conflicted: !searching
        && Store.listed.filter(function (b) { return !b.allowConflict }).length > 1

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
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: parent.width
                spacing: 2

                Repeater {
                    model: Store.listed
                    delegate: BindRow {
                        required property var modelData
                        Layout.fillWidth: true
                        bind: modelData
                        inConflict: root.conflicted && !modelData.allowConflict
                    }
                }

                Text {
                    visible: root.conflicted
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "⚠ These all fire on " + root.keyText + ". Remove one, keep both, or edit one onto other keys."
                    color: Colors.statusCritical
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
                        Action { text: "Restore"; onClicked: Store.restoreHand(removedRow.modelData.hand) }
                    }
                }

                Action {
                    visible: !root.searching && root.keyText !== ""
                    enabled: !Store.readOnly
                    text: "+ Add a bind on " + root.keyText
                    onClicked: Store.newBindOnSelected()
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
