import QtQuick
import "../config"

// One key on the on-screen keyboard. It draws a state and reports clicks;
// what the state means is decided in lib/keymap.js.
Rectangle {
    id: root
    property string label: ""
    property string sub: ""
    property string kind: "free"
    property bool selected: false
    property bool dimmed: false
    property real unit: 40
    property real units: 1
    signal clicked()

    // The accent laid over the key's own surface rather than the accent at
    // reduced opacity: the pane behind is darker than a key, so translucency
    // reads as a hole rather than a lit key.
    function lit(accent, amount) {
        return Qt.tint(Colors.bgSurface, Qt.rgba(accent.r, accent.g, accent.b, amount))
    }

    width: unit * units - 4
    height: unit - 4
    radius: Radius.sm
    opacity: dimmed ? 0.35 : 1
    color: kind === "conflict" ? lit(Colors.statusCritical, 0.45)
         : kind === "bound" || kind === "overlap" ? lit(Colors.accentPrimary, 0.3)
         : kind === "modOn" ? lit(Colors.accentSecondary, 0.18)
         : kind === "mod" ? Colors.bgSurfaceAlt
         : Colors.bgSurface
    border.width: selected ? 2 : 1
    border.color: selected ? Colors.textPrimary
                : kind === "conflict" || kind === "overlap" ? Colors.statusCritical
                : kind === "bound" ? lit(Colors.accentPrimary, 0.6)
                : kind === "mod" || kind === "modOn" ? Colors.accentSecondary
                : Colors.borderSubtle

    Behavior on color { ColorAnimation { duration: 110 } }

    Column {
        anchors.centerIn: parent
        width: parent.width - 4
        spacing: 0

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.label
            color: root.kind === "free" ? Colors.textTertiary
                 : root.kind === "mod" || root.kind === "modOn" ? Colors.accentSecondary
                 : Colors.textPrimary
            font.family: Typography.family
            font.pixelSize: Math.max(9, Math.round(root.unit * 0.27))
            elide: Text.ElideRight
        }

        Text {
            visible: root.sub !== ""
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: root.sub
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Math.max(7, Math.round(root.unit * 0.19))
            elide: Text.ElideRight
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
