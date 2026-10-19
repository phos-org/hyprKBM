pragma ComponentBehavior: Bound
import QtQuick
import "../state"
import "../lib/keys.js" as Keys
import "../lib/labels.js" as Labels

// One block of keyboard rows -- the main block or the navigation cluster.
// A key is lit by what it does under Store.mods in Store.submap.
Column {
    id: root
    property var rows: []
    property real unit: 40
    property bool interactive: true
    property bool detailed: false

    function info(spec) {
        return spec.id === undefined ? undefined : Store.keyStates[Keys.keyId(spec.id)]
    }

    function kindOf(spec) {
        if (spec.mod !== undefined) return Store.mods.indexOf(spec.mod) >= 0 ? "modOn" : "mod"
        var i = info(spec)
        if (i !== undefined) return i.state
        return spec.id !== undefined && Store.otherKeys[Keys.keyId(spec.id)] === true ? "other" : "free"
    }

    function subOf(spec) {
        var i = info(spec)
        if (i === undefined || spec.cont) return ""
        return root.detailed ? Labels.sheetLabel(i.binds)
            : (i.binds.length > 1 ? i.binds.length + " binds" : Labels.shortLabel(i.binds[0]))
    }

    function press(spec) {
        if (spec.mod !== undefined) Store.toggleMod(spec.mod)
        else Store.selectKey(spec.id)
    }

    Repeater {
        model: root.rows
        delegate: Row {
            id: rowItem
            required property var modelData
            height: root.unit
            Repeater {
                model: rowItem.modelData
                delegate: KeyCap {
                    required property var modelData
                    unit: root.unit
                    units: modelData.w
                    // A gap keeps its width in the row but is neither drawn
                    // nor clickable.
                    enabled: root.interactive && modelData.gap !== true
                    opacity: modelData.gap ? 0 : (dimmed ? 0.35 : 1)
                    label: modelData.label || ""
                    kind: modelData.gap ? "free" : root.kindOf(modelData)
                    sub: root.subOf(modelData)
                    subLines: root.detailed ? 3 : 1
                    selected: modelData.id !== undefined && Keys.keyId(modelData.id) === Store.selectedKey
                    dimmed: Store.matching !== null && modelData.id !== undefined
                            && Store.matching[Keys.keyId(modelData.id)] !== true
                    onClicked: root.press(modelData)
                }
            }
        }
    }
}
