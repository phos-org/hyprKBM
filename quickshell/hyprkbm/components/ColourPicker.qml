import QtQuick
import QtQuick.Layouts
import "../config"

// Choosing the accent by eye. The other half of the accent row: the hex field
// is for a value you already have, this is for one you are still looking for.
// Neither is the real control -- they are two views of one value, and each
// follows the other as it moves.
//
// Built here rather than taken from QtQuick.Dialogs' ColorDialog. That module
// is not installed on this machine and is not among the three QtQuick modules
// CI installs, so importing it would turn a colour picker into a panel that
// will not start; and a platform dialog would arrive with its own margins and
// corners in the middle of a panel where every one of those is deliberate.
//
// A saturation/value square under a hue strip, because that is the arrangement
// people already know. Nothing here is a new idea on purpose.
//
// A ColumnLayout root, and Layout.preferredHeight rather than height on the
// two bars below: this is dropped straight into the popup's own layout, and
// the project's CI notes that plain `height:` on a layout-managed item is what
// used to block the strict qmllint run.
ColumnLayout {
    id: root

    // The colour to show. Set from outside; the picker never writes it.
    property color value: "transparent"

    // `moved` fires all the way through a drag, `picked` once at the end of
    // one. The split is the whole reason this feels like a picker rather than
    // a series of clicks: the swatch and the hex follow your finger, but the
    // theme file is written once, when you let go. Writing per frame would be
    // a hundred atomic replacements of a file the whole panel is watching.
    signal moved(string hex)
    signal picked(string hex)

    spacing: Spacing.sm

    // Held as HSV rather than recomputed from `value` each time, because the
    // conversion back is lossy in the two places it matters: every colour
    // along the top edge of the square is value 1 whatever its saturation, and
    // every grey has no hue at all. Recomputing would drag the cursor out from
    // under the pointer at exactly the moments somebody is using it.
    property real hue: 0
    property real saturation: 0
    property real brightness: 0
    property bool dragging: false

    function hex(): string {
        return String(Qt.hsva(root.hue, root.saturation, root.brightness, 1));
    }

    // Take a colour from outside -- unless it is the one already showing, or a
    // gesture is in progress. Without that guard a drag fights its own echo:
    // the value comes back through the field and the cursor jumps to wherever
    // the rounded hex landed.
    function adopt() {
        if (root.dragging) return;
        if (root.hex() === String(root.value)) return;

        // Qt answers -1 for the hue of a grey, having none to report. Keeping
        // the hue we had means the strip does not snap to red every time
        // somebody drags the saturation down to nothing.
        if (root.value.hsvHue >= 0) root.hue = root.value.hsvHue;
        root.saturation = root.value.hsvSaturation;
        root.brightness = root.value.hsvValue;
    }

    onValueChanged: adopt()
    Component.onCompleted: adopt()

    // A preset swatch is a choice, not a gesture: it lands on a named colour
    // and there is nothing to drag, so it goes straight through to picked.
    function choose(chosen: string) {
        const colour = Qt.color(chosen);
        if (colour.hsvHue >= 0) root.hue = colour.hsvHue;
        root.saturation = colour.hsvSaturation;
        root.brightness = colour.hsvValue;
        root.moved(root.hex());
        root.picked(root.hex());
    }

    function clamped(fraction: real): real {
        return fraction < 0 ? 0 : fraction > 1 ? 1 : fraction;
    }

    // The gesture, in the picker's own coordinates. On the root rather than
    // inside the MouseAreas because the root owns the HSV state -- and because
    // a handler only a pointer can reach is a handler that cannot be driven
    // from the panel's IPC surface the way everything else here can.
    function trackSquare(pointX: real, pointY: real) {
        root.saturation = root.clamped(pointX / square.width);
        root.brightness = 1 - root.clamped(pointY / square.height);
        root.moved(root.hex());
    }

    function trackHue(pointX: real) {
        root.hue = root.clamped(pointX / hues.width);
        root.moved(root.hex());
    }

    function endGesture() {
        root.dragging = false;
        root.picked(root.hex());
    }

    // ---------------------------------------------------- saturation / value

    Rectangle {
        id: square
        Layout.fillWidth: true
        // Tall enough to aim in, short enough that the popup still reads as
        // something hanging off a button. Much under 90 and the bottom of the
        // range is a few pixels of near-black, which is not a range at all.
        Layout.preferredHeight: 108
        radius: Radius.sm
        clip: true
        color: Qt.hsva(root.hue, 1, 1, 1)

        // White across, black down. These are not theme colours and must not
        // become them: they are the colour space itself, and a square whose
        // white came from a palette would not be showing you the colour you
        // are choosing.
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 1) }
                GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
            }
        }
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0) }
                GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 1) }
            }
        }

        // Two rings rather than one. The cursor sits on top of every colour in
        // the square by definition, so it cannot be any single one of them and
        // stay visible; dark outside and light inside is legible on all of
        // them, which is the one thing it has to be.
        Item {
            x: root.saturation * square.width
            y: (1 - root.brightness) * square.height

            Rectangle {
                anchors.centerIn: parent
                width: 12
                height: width
                radius: width / 2
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(0, 0, 0, 0.65)
            }
            Rectangle {
                anchors.centerIn: parent
                width: 10
                height: width
                radius: width / 2
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.9)
            }
        }

        MouseArea {
            anchors.fill: parent
            // The gesture belongs to whichever area it started in. Without
            // this the popup can take it mid-drag and the cursor stops dead
            // somewhere the user did not leave it.
            preventStealing: true
            cursorShape: Qt.CrossCursor

            onPressed: function (event) {
                root.dragging = true;
                root.trackSquare(event.x, event.y);
            }
            // Positions are reported past the edges once the grab is held,
            // which is what the clamping is for: dragging off the top keeps
            // the value at 1 rather than losing the gesture at the boundary.
            onPositionChanged: function (event) {
                if (pressed) root.trackSquare(event.x, event.y);
            }
            onReleased: root.endGesture()
        }
    }

    // ------------------------------------------------------------------ hue

    Rectangle {
        id: hues
        Layout.fillWidth: true
        Layout.preferredHeight: 14
        radius: Radius.sm
        clip: true

        // Six steps and the wrap back to red. Written as Qt.hsva of the same
        // fraction as the position, so the strip is the hue axis itself rather
        // than a rainbow somebody typed out and can mistype.
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0 / 6; color: Qt.hsva(0 / 6, 1, 1, 1) }
            GradientStop { position: 1 / 6; color: Qt.hsva(1 / 6, 1, 1, 1) }
            GradientStop { position: 2 / 6; color: Qt.hsva(2 / 6, 1, 1, 1) }
            GradientStop { position: 3 / 6; color: Qt.hsva(3 / 6, 1, 1, 1) }
            GradientStop { position: 4 / 6; color: Qt.hsva(4 / 6, 1, 1, 1) }
            GradientStop { position: 5 / 6; color: Qt.hsva(5 / 6, 1, 1, 1) }
            GradientStop { position: 6 / 6; color: Qt.hsva(6 / 6, 1, 1, 1) }
        }

        Rectangle {
            x: root.hue * hues.width - width / 2
            width: 5
            height: hues.height
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.9)

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                color: "transparent"
                border.width: 1
                border.color: Qt.rgba(0, 0, 0, 0.55)
            }
        }

        MouseArea {
            anchors.fill: parent
            preventStealing: true
            cursorShape: Qt.CrossCursor

            onPressed: function (event) {
                root.dragging = true;
                root.trackHue(event.x);
            }
            onPositionChanged: function (event) {
                if (pressed) root.trackHue(event.x);
            }
            onReleased: root.endGesture()
        }
    }

    // ------------------------------------------------------- preset accents

    RowLayout {
        Layout.fillWidth: true
        spacing: Spacing.sm
        visible: Theme.presetAccents.length > 0

        Text {
            text: "From a preset"
            color: Colors.textSecondary
            font.family: Typography.family
            font.pixelSize: Typography.sizeSmall
        }

        Repeater {
            model: Theme.presetAccents

            delegate: Rectangle {
                id: chip
                required property var modelData

                Layout.preferredWidth: Typography.sizeBody
                Layout.preferredHeight: Typography.sizeBody
                radius: width / 2
                color: chip.modelData.hex
                // The colour is already drawn in the field above, so the ring
                // here says "this is the one you are on" rather than repeating
                // it a second time.
                border.width: 1
                border.color: root.hex() === chip.modelData.hex
                            ? Colors.textPrimary : Colors.borderStrong

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.choose(chip.modelData.hex)
                }
            }
        }

        // Keeps the chips packed against the label rather than spread across
        // the row when there are only three of them.
        Item { Layout.fillWidth: true }
    }
}
