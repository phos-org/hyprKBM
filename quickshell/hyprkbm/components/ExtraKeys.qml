pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../config"
import "../state"
import "../lib/keys.js" as Keys
import "../lib/labels.js" as Labels

// Keys that are not on a keyboard: mouse buttons, the wheel, and the media
// keys the config uses. "+ any key…" starts a bind on a key typed by hand.
ColumnLayout {
    id: root
    property real unit: 40
    property bool interactive: true
    property bool detailed: false
    spacing: Spacing.xs

    function kindOf(id) {
        var i = Store.keyStates[Keys.keyId(id)]
        if (i !== undefined) return i.state
        return Store.otherKeys[Keys.keyId(id)] === true ? "other" : "free"
    }

    function subOf(id) {
        var i = Store.keyStates[Keys.keyId(id)]
        if (i === undefined) return ""
        return root.detailed ? Labels.sheetLabel(i.binds)
            : (i.binds.length > 1 ? i.binds.length + " binds" : Labels.shortLabel(i.binds[0]))
    }

    Text {
        text: "Mouse & other"
        color: Colors.textSecondary
        font.family: Typography.family
        font.pixelSize: Typography.sizeSmall
    }

    Flow {
        Layout.preferredWidth: root.unit * 3
        spacing: 0
        Repeater {
            model: Store.extras
            delegate: KeyCap {
                required property var modelData
                unit: root.unit
                label: modelData.label
                kind: root.kindOf(modelData.id)
                sub: root.subOf(modelData.id)
                enabled: root.interactive
                subLines: root.detailed ? 3 : 1
                selected: root.interactive && Keys.keyId(modelData.id) === Store.selectedKey
                dimmed: Store.matching !== null && Store.matching[Keys.keyId(modelData.id)] !== true
                onClicked: Store.selectKey(modelData.id)
            }
        }
    }

    Action {
        text: "+ any key…"
        visible: root.interactive
        enabled: !Store.readOnly
        onClicked: Store.newBind(Keys.display(Store.mods, ""))
    }
}
