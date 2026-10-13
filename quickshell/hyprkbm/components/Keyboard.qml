import QtQuick
import "../state"

// The main block and the navigation cluster of Store.layout. The key size is
// handed in (see Layouts.unitFor) rather than worked out from this item's own
// width, which the extra keys beside it would otherwise feed back into.
Item {
    id: root
    property real unit: 40
    // Fifteen units of main block, half a unit of gap, three of cluster.
    implicitWidth: unit * 18.5
    implicitHeight: unit * 6

    Row {
        spacing: root.unit * 0.5
        KeyBlock { rows: Store.layout.main; unit: root.unit }
        KeyBlock { rows: Store.layout.nav; unit: root.unit }
    }
}
