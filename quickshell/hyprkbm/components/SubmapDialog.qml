pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QC
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as KeyNames

// A new submap: its name and the key that leaves it. A bind enters it with
// the "Enter submap" action. Opened with edit(), it changes the leave key of
// one that exists instead.
QC.Popup {
    id: root
    parent: QC.Overlay.overlay
    modal: true
    focus: true
    width: 380
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? Math.round((parent.height - height) / 3) : 0
    padding: Spacing.lg
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutside

    // The submap whose leave key is being changed; "" for a new one.
    property string editing: ""

    function create() {
        editing = ""
        open()
    }

    function edit(submap) {
        editing = submap
        open()
    }

    readonly property string problem: name.text.trim() === "" ? "Give it a name."
        : editing === "" && Store.submaps.indexOf(name.text.trim()) >= 0 ? "There is already a submap called " + name.text.trim() + "."
        : KeyNames.parse(reset.text) === null || KeyNames.isModifierOnly(reset.text) ? "The leave key must be a key, like escape or SUPER + E."
        : ""
    // Not a problem that blocks: Hyprland runs both binds, so the way out
    // still works, but the other bind fires with it.
    readonly property var clash: editing === "" ? null : Store.resetClash(editing, reset.text)

    // Without its own background a TextField draws the style's white box,
    // under the theme's light text.
    component Input: QC.TextField {
        id: input
        width: parent ? parent.width : implicitWidth
        color: Colors.textPrimary
        placeholderTextColor: Colors.textSecondary
        selectionColor: Colors.accentPrimary
        selectedTextColor: Colors.bgVoid
        font.family: Typography.family
        font.pixelSize: Typography.sizeBody
        background: Rectangle {
            color: Colors.bgBase
            radius: Radius.sm
            border.width: input.activeFocus ? 2 : 1
            border.color: input.activeFocus ? Colors.accentPrimary : Colors.borderSubtle
        }
    }

    onOpened: {
        name.text = editing
        reset.text = editing === "" ? "escape" : (Store.submapReset(editing) || "escape")
        if (editing === "") name.forceActiveFocus()
        else { reset.forceActiveFocus(); reset.selectAll() }
    }

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Name"
            Input { id: name; readOnly: root.editing !== ""; opacity: readOnly ? 0.6 : 1 }
        }

        Field {
            label: "Key that leaves it"
            Input { id: reset }
        }

        Text {
            visible: root.problem === "" && root.clash !== null
            Layout.fillWidth: true
            text: root.clash === null ? "" : root.clash.keys + " already does something in " + root.editing + "; pressing it will do that too."
            color: Colors.statusCritical
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
            wrapMode: Text.WordWrap
        }

        Text {
            visible: root.problem !== ""
            text: root.problem
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Action { text: "Cancel"; onClicked: root.close() }
            Action {
                text: root.editing === "" ? "Create" : "Save"
                primary: true
                enabled: root.problem === "" && !Store.readOnly
                onClicked: {
                    if (root.editing === "") Store.addSubmap(name.text.trim(), reset.text.trim())
                    else Store.setSubmapReset(root.editing, reset.text.trim())
                    root.close()
                }
            }
        }
    }
}
