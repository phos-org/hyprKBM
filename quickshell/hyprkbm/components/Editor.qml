pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as KeyNames
import "../lib/qtkeys.js" as QtKeys
import "../lib/model.js" as Model
import "../lib/catalogue.js" as Catalogue

// The draft in Store.draft: keys, action, description, flags and submap.
// Saving stages it in the model; nothing reaches Hyprland until Apply.
Rectangle {
    id: root
    color: Colors.bgBase
    radius: Radius.md
    border.width: 1
    border.color: Colors.borderSubtle

    readonly property var draft: Store.draft
    readonly property var entry: draft === null || draft.action.kind === "raw" ? null
                                 : Catalogue.entryById(Store.catalogue, draft.action.kind)
    readonly property var problems: Store.draftProblems()
    readonly property var kinds: Store.catalogue.map(function (e) { return e.id }).concat(["raw"])
    readonly property var kindLabels: Store.catalogue.map(function (e) { return e.label }).concat(["Raw Lua"])
    property bool recording: false
    // Changes when another bind's draft opens, not on every edit of one.
    readonly property string draftIdentity: draft === null ? ""
        : draft.id !== null ? "k:" + draft.id
        : draft.hand !== null ? "h:" + draft.hand.uid : "new"
    onDraftIdentityChanged: recording = false

    component Label: Text {
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
        font.weight: Typography.weightMedium
    }

    component Input: QC.TextField {
        id: input
        Layout.fillWidth: true
        color: Colors.textPrimary
        placeholderTextColor: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: 1
            border.color: input.activeFocus ? Colors.borderStrong : Colors.borderSubtle
        }
    }

    Text {
        visible: root.draft === null
        anchors.centerIn: parent
        width: parent.width - Spacing.xl * 2
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: "Pick a key and press Edit on one of its binds, or add one."
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
    }

    QC.ScrollView {
        visible: root.draft !== null
        anchors.fill: parent
        anchors.margins: Spacing.md
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Spacing.sm

            Text {
                text: root.draft === null ? ""
                    : root.draft.id !== null ? "Edit bind"
                    : root.draft.hand !== null ? "Override " + root.draft.hand.where
                    : "New bind"
                color: Colors.textPrimary
                font.family: Typography.family
                font.pixelSize: Typography.sizeBody
                font.weight: Typography.weightMedium
            }

            Label { text: "Keys" }
            RowLayout {
                Layout.fillWidth: true
                Input {
                    id: keysField
                    text: root.draft === null ? "" : root.draft.keys
                    placeholderText: root.recording ? "Press the keys…" : "SUPER + SHIFT + F"
                    onTextEdited: Store.patchDraft({ keys: text })
                    onActiveFocusChanged: if (!activeFocus) root.recording = false
                    // While recording, the next key pressed with its modifiers
                    // becomes the combo. Hyprland keeps combos it already
                    // binds, so some can only be typed.
                    Keys.onPressed: function (event) {
                        if (!root.recording) return
                        if (event.key === Qt.Key_Escape) {
                            root.recording = false
                            event.accepted = true
                            return
                        }
                        var key = QtKeys.keysymFromQt(event.key, event.modifiers)
                        event.accepted = true
                        if (key === null) return
                        Store.patchDraft({ keys: KeyNames.display(QtKeys.modsFromQt(event.modifiers), key) })
                        root.recording = false
                    }
                }
                Action {
                    text: root.recording ? "Stop" : "⏺ Record"
                    onClicked: {
                        root.recording = !root.recording
                        if (root.recording) keysField.forceActiveFocus()
                    }
                }
            }

            Label { text: "Action" }
            Select {
                Layout.fillWidth: true
                model: root.kindLabels
                currentIndex: root.draft === null ? -1 : root.kinds.indexOf(root.draft.action.kind)
                onActivated: function (index) { Store.setActionKind(root.kinds[index]) }
            }

            Repeater {
                model: root.entry === null ? [] : root.entry.fields
                delegate: ColumnLayout {
                    id: fieldItem
                    required property var modelData
                    readonly property var value: root.draft.action.args === undefined ? undefined
                                                 : root.draft.action.args[modelData.name]
                    Layout.fillWidth: true
                    spacing: Spacing.xs

                    Label { text: fieldItem.modelData.label + (fieldItem.modelData.required ? "" : " (optional)") }

                    Input {
                        visible: ["string", "workspace", "submap"].indexOf(fieldItem.modelData.type) >= 0
                        text: fieldItem.value === undefined ? "" : String(fieldItem.value)
                        onTextEdited: {
                            var v = fieldItem.modelData.type === "workspace" ? Catalogue.workspaceValue(text) : text
                            Store.patchArg(fieldItem.modelData.name, v)
                        }
                    }

                    Select {
                        visible: fieldItem.modelData.type === "enum"
                        Layout.fillWidth: true
                        model: fieldItem.modelData.type === "enum" ? [""].concat(fieldItem.modelData.values) : []
                        currentIndex: fieldItem.modelData.type === "enum"
                                      ? [""].concat(fieldItem.modelData.values).indexOf(fieldItem.value === undefined ? "" : fieldItem.value)
                                      : -1
                        onActivated: function (index) {
                            Store.patchArg(fieldItem.modelData.name, index === 0 ? "" : fieldItem.modelData.values[index - 1])
                        }
                    }

                    Toggle {
                        visible: fieldItem.modelData.type === "bool"
                        text: fieldItem.modelData.label
                        checked: fieldItem.value === undefined ? fieldItem.modelData["default"] === true : fieldItem.value === true
                        onToggled: Store.patchArg(fieldItem.modelData.name, checked)
                    }
                }
            }

            QC.TextArea {
                visible: root.draft !== null && root.draft.action.kind === "raw"
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                placeholderText: "hl.dsp.group.toggle()"
                placeholderTextColor: Colors.textSecondary
                text: root.draft !== null && root.draft.action.kind === "raw" ? root.draft.action.lua : ""
                onTextChanged: if (root.draft !== null && root.draft.action.kind === "raw" && text !== root.draft.action.lua)
                                   Store.patchDraft({ action: { kind: "raw", lua: text } })
                color: Colors.textPrimary
                font.family: "monospace"
                font.pixelSize: Typography.sizeSmall
                wrapMode: TextEdit.Wrap
                background: Rectangle {
                    color: Colors.bgSurface
                    radius: Radius.sm
                    border.width: 1
                    border.color: Colors.borderSubtle
                }
            }

            Label { text: "Description · shown in the cheatsheet" }
            Input {
                text: root.draft === null ? "" : root.draft.description
                onTextEdited: Store.patchDraft({ description: text })
            }

            Label { text: "Flags" }
            Flow {
                Layout.fillWidth: true
                spacing: Spacing.xs
                Repeater {
                    model: Model.FLAG_NAMES
                    delegate: Rectangle {
                        id: flag
                        required property string modelData
                        readonly property bool picked: root.draft !== null && root.draft.flags[modelData] === true
                        implicitWidth: flagText.implicitWidth + Spacing.md
                        implicitHeight: 22
                        radius: 4
                        color: "transparent"
                        border.width: 1
                        border.color: picked ? Colors.accentTertiary : Colors.borderSubtle
                        Text {
                            id: flagText
                            anchors.centerIn: parent
                            text: flag.modelData.replace(/_/g, " ")
                            color: flag.picked ? Colors.accentTertiary : Colors.textTertiary
                            font.family: Typography.family
                            font.pixelSize: Typography.sizeSmall
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                var flags = Model.clone(root.draft.flags)
                                if (flag.picked) delete flags[flag.modelData]
                                else flags[flag.modelData] = true
                                Store.patchDraft({ flags: flags })
                            }
                        }
                    }
                }
            }

            Label { text: "Submap" }
            Select {
                Layout.fillWidth: true
                model: Store.submaps.map(function (s) { return s === "" ? "global" : s })
                currentIndex: root.draft === null ? -1 : Store.submaps.indexOf(root.draft.submap)
                onActivated: function (index) { Store.patchDraft({ submap: Store.submaps[index] }) }
            }

            Repeater {
                model: root.problems
                delegate: Text {
                    required property string modelData
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: modelData
                    color: Colors.statusCritical
                    font.family: Typography.family
                    font.pixelSize: Typography.sizeSmall
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Spacing.sm
                Action {
                    text: "Save"
                    primary: true
                    enabled: root.problems.length === 0 && !Store.readOnly
                    onClicked: Store.saveDraft()
                }
                Action { text: "Cancel"; onClicked: Store.cancelEdit() }
                Item { Layout.fillWidth: true }
                Action {
                    visible: root.draft !== null && (root.draft.id !== null || root.draft.hand !== null)
                    text: "Delete"
                    onClicked: Store.deleteDraft()
                }
            }
        }
    }
}
