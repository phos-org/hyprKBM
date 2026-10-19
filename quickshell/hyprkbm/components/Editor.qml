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
import "../lib/focus.js" as Focus

// The draft in Store.draft: keys, action, description, flags and submap.
// Saving stages it in the model; nothing reaches Hyprland until Apply.
Rectangle {
    id: root
    // Tinted over the pane's own colour, never translucent over it.
    color: Store.area === "editor"
           ? Qt.tint(Colors.bgBase, Qt.rgba(Colors.accentPrimary.r, Colors.accentPrimary.g, Colors.accentPrimary.b, 0.05))
           : Colors.bgBase
    radius: Radius.md
    border.width: Store.area === "editor" ? 3 : 1
    border.color: Store.area === "editor" ? Colors.accentPrimary : Colors.borderSubtle

    // Tab ran off the last control (Shift+Tab off the first): the window
    // moves on to the next (previous) area.
    signal tabOut(bool back)

    // Tab into the editor lands on its first field; Shift+Tab, on its last.
    function focusFirst() { keysField.forceActiveFocus() }
    function focusLast() {
        let list = controls()
        if (list.length > 0) list[list.length - 1].forceActiveFocus()
        else focusFirst()
    }

    // What Tab walks, in reading order: the fields, selects and toggles that
    // are showing. Not the buttons (they are clicked or have shortcuts) and
    // not the flags (plain chips, toggled by clicking).
    function controls() {
        let list = [keysField, kindSelect]
        for (let i = 0; i < argFields.count; i++) {
            let row = argFields.itemAt(i)
            if (row) list = list.concat(row.controls)
        }
        list = list.concat([rawLua, descField, submapSelect])
        return list.filter(function (c) { return c.visible && c.enabled })
    }

    // Every control here is out of Qt's own Tab chain (Qt.ClickFocus), so
    // Tab reaches this handler and the walk is ours alone.
    function tab(event) {
        let m = event.modifiers & ~Qt.KeypadModifier
        if ((event.key !== Qt.Key_Tab && event.key !== Qt.Key_Backtab)
                || (m !== Qt.NoModifier && m !== Qt.ShiftModifier)) return
        event.accepted = true
        // One step per press, as Tab between areas.
        if (event.isAutoRepeat) return
        let back = event.key === Qt.Key_Backtab || m === Qt.ShiftModifier
        let list = controls()
        let at = -1
        for (let i = 0; i < list.length; i++) if (list[i].activeFocus) at = i
        let to = Focus.walk(at, list.length, back)
        if (to < 0) root.tabOut(back)
        else list[to].forceActiveFocus()
    }
    Keys.onPressed: function (event) { root.tab(event) }

    readonly property var draft: Store.draft
    readonly property var entry: draft === null || draft.action.kind === "raw" ? null
                                 : Catalogue.entryById(Store.catalogue, draft.action.kind)
    readonly property var problems: Store.draftProblems()
    readonly property var kinds: Store.catalogue.map(function (e) { return e.id }).concat(["raw"])
    readonly property var kindLabels: Store.catalogue.map(function (e) { return e.label }).concat(["Raw Lua"])
    property bool recording: false
    // What the keys field shows while recording: the modifiers held so far.
    property var recordingMods: []
    onRecordingChanged: recordingMods = []
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
        focusPolicy: Qt.ClickFocus
        color: Colors.textPrimary
        placeholderTextColor: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgSurface
            radius: Radius.sm
            border.width: input.activeFocus ? 2 : 1
            border.color: input.activeFocus ? Colors.accentPrimary : Colors.borderSubtle
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
                    // While recording, the held modifiers show as they change,
                    // so it is clear the field is listening before the last key.
                    text: root.recording ? QtKeys.recordingText(root.recordingMods)
                        : root.draft === null ? "" : root.draft.keys
                    placeholderText: "SUPER + SHIFT + F"
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
                        if (key === null) {
                            root.recordingMods = QtKeys.heldMods(event.key, event.modifiers, true)
                            return
                        }
                        Store.patchDraft({ keys: KeyNames.display(QtKeys.modsFromQt(event.modifiers), key) })
                        root.recording = false
                    }
                    Keys.onReleased: function (event) {
                        if (!root.recording) return
                        root.recordingMods = QtKeys.heldMods(event.key, event.modifiers, false)
                        event.accepted = true
                    }
                }
                Action {
                    text: root.recording ? "Stop" : "⏺ Record"
                    focusPolicy: Qt.NoFocus
                    onClicked: {
                        root.recording = !root.recording
                        if (root.recording) keysField.forceActiveFocus()
                    }
                }
            }

            Label { text: "Action" }
            Select {
                id: kindSelect
                Layout.fillWidth: true
                focusPolicy: Qt.ClickFocus
                model: root.kindLabels
                currentIndex: root.draft === null ? -1 : root.kinds.indexOf(root.draft.action.kind)
                onActivated: function (index) { Store.setActionKind(root.kinds[index]) }
            }

            Repeater {
                id: argFields
                model: root.entry === null ? [] : root.entry.fields
                delegate: ColumnLayout {
                    id: fieldItem
                    required property var modelData
                    readonly property var value: root.draft.action.args === undefined ? undefined
                                                 : root.draft.action.args[modelData.name]
                    // Only one of the three shows; controls() drops the rest.
                    readonly property var controls: [argInput, argSelect, argToggle]
                    Layout.fillWidth: true
                    spacing: Spacing.xs

                    Label { text: fieldItem.modelData.label + (fieldItem.modelData.required ? "" : " (optional)") }

                    Input {
                        id: argInput
                        visible: ["string", "workspace", "submap"].indexOf(fieldItem.modelData.type) >= 0
                        text: fieldItem.value === undefined ? "" : String(fieldItem.value)
                        onTextEdited: {
                            var v = fieldItem.modelData.type === "workspace" ? Catalogue.workspaceValue(text) : text
                            Store.patchArg(fieldItem.modelData.name, v)
                        }
                    }

                    Select {
                        id: argSelect
                        visible: fieldItem.modelData.type === "enum"
                        Layout.fillWidth: true
                        focusPolicy: Qt.ClickFocus
                        model: fieldItem.modelData.type === "enum" ? [""].concat(fieldItem.modelData.values) : []
                        currentIndex: fieldItem.modelData.type === "enum"
                                      ? [""].concat(fieldItem.modelData.values).indexOf(fieldItem.value === undefined ? "" : fieldItem.value)
                                      : -1
                        onActivated: function (index) {
                            Store.patchArg(fieldItem.modelData.name, index === 0 ? "" : fieldItem.modelData.values[index - 1])
                        }
                    }

                    Toggle {
                        id: argToggle
                        focusPolicy: Qt.ClickFocus
                        visible: fieldItem.modelData.type === "bool"
                        text: fieldItem.modelData.label
                        checked: fieldItem.value === undefined ? fieldItem.modelData["default"] === true : fieldItem.value === true
                        onToggled: Store.patchArg(fieldItem.modelData.name, checked)
                    }
                }
            }

            QC.TextArea {
                id: rawLua
                focusPolicy: Qt.ClickFocus
                // A text area takes Tab as a character, so the walk has to
                // see it first.
                Keys.onPressed: function (event) { root.tab(event) }
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
                    border.width: rawLua.activeFocus ? 2 : 1
                    border.color: rawLua.activeFocus ? Colors.accentPrimary : Colors.borderSubtle
                }
            }

            Label { text: "Description · shown in the cheatsheet" }
            Input {
                id: descField
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
                id: submapSelect
                Layout.fillWidth: true
                focusPolicy: Qt.ClickFocus
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
                    text: "Save (Ctrl+S)"
                    primary: true
                    enabled: root.problems.length === 0 && !Store.readOnly && !Store.busy
                    onClicked: Store.saveDraft()
                }
                Action { text: "Cancel (Esc)"; onClicked: Store.cancelEdit() }
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
