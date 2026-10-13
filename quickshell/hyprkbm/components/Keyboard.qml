import QtQuick
import "../state"

// The main block and the navigation cluster of Store.layout, sized to the
// width it is given.
Item {
    id: root
    // Fifteen units of main block, half a unit of gap, three of cluster.
    readonly property real unit: Math.max(26, Math.min(48, Math.floor(width / 18.5)))
    implicitHeight: unit * 6

    Row {
        spacing: root.unit * 0.5
        KeyBlock { rows: Store.layout.main; unit: root.unit }
        KeyBlock { rows: Store.layout.nav; unit: root.unit }
    }
}
