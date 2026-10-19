import QtQuick
import QtQuick.Controls
import "../config"

// Typed colour entry, with a swatch of the colour beside it. The swatch is the
// whole reason this is not a bare text field: a hex string is not a colour
// anyone can read, and the panel's own accent is the one value you want to see
// rather than decode. Pressing it opens the picker -- the swatch is both the
// readout and the way in, because it is the part of the row that is already
// about the colour rather than about its name.
//
// Modelled on NumberInput: commit on Enter or on leaving the field, Escape
// puts the old value back. A colour earns the same treatment as a coordinate
// -- committing per keystroke would drag the panel through "#c", "#c2",
// "#c27" on the way to "#c2718c", repainting every border on each one.
TextField {
    id: root

    // The value in force, as the panel resolved it. Assigned rather than bound
    // to `text` for the reason NumberInput gives: a rebind while you are
    // typing would overwrite what you have half-entered.
    property string value: ""
    // What the swatch paints. Separate from `value` on purpose: `value` is the
    // colour in force, and during a drag on the picker the swatch has to show
    // the candidate instead -- that is what makes the two routes look like one
    // value. It also covers the ordinary case where the theme file says
    // nothing and the panel is still painting the default.
    property color preview: "transparent"

    // The picker is open, so the swatch is a pressed button and should look
    // like one rather than like a readout that happens to be highlighted.
    property bool picking: false

    // The last thing committed was not a colour. Held rather than recomputed
    // from `text`, so the field does not go red halfway through typing one.
    property bool rejected: false

    // `committed` writes the theme; `edited` only says a valid colour is
    // showing, which is what moves the picker as you type without putting a
    // keystroke on disk.
    signal committed(string hex)
    signal edited(string hex)
    signal swatchClicked()

    text: value
    onValueChanged: if (!activeFocus) text = value
    // As soon as it is being edited it is no longer the thing that was
    // refused, and leaving it red would be a complaint about old news.
    onTextChanged: {
        rejected = false;
        const hex = Theme.normalisedColour(text);
        if (hex !== "") edited(hex);
    }

    // Driven by the picker, and unconditional -- deliberately unlike `value`
    // above, which does refuse while the field has focus so that nothing can
    // overwrite half-typed text.
    //
    // What arrives here is not a change from outside. It is the same person's
    // hand, dragging in the picker below, and a gesture says what somebody
    // wants more plainly than whatever is left sitting in the field.
    //
    // It carried `value`'s guard too, which was a bug rather than caution: the
    // field holds focus for as long as the picker is open, so the guard was
    // true on every frame of every drag and not one colour ever got through.
    // Measured in a live session -- a drag across the square logged
    // `show(#3940ba) activeFocus=true` and thirty more like it, while the hex
    // beside the square sat unchanged. Which reads, reasonably, as the accent
    // not applying at all.
    function show(hex: string) {
        text = hex;
    }

    implicitHeight: 30
    color: Colors.textPrimary
    font.family: Typography.family
    font.pixelSize: Typography.sizeBody
    selectByMouse: true
    horizontalAlignment: Text.AlignLeft
    // The swatch sits inside the field rather than beside it, so the colour
    // and the hex that names it are one control.
    leftPadding: swatch.x + swatch.width + Spacing.sm
    rightPadding: Spacing.sm

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.sm
        border.width: 1
        border.color: root.rejected ? Colors.statusCritical
                    : root.activeFocus ? Colors.borderStrong
                    : root.hovered ? Colors.borderStrong : Colors.borderSubtle
        Behavior on border.color { ColorAnimation { duration: 120 } }
    }

    // A direct child rather than part of `background`: the background sits
    // under the text layer, and a press there would be taken by the field's
    // own selection handling before it ever reached the swatch.
    Rectangle {
        id: swatch
        x: Spacing.sm
        y: (root.height - height) / 2
        // A dot rather than a rounded square: at this size any radius short of
        // a circle reads as a rendering artefact.
        width: Typography.sizeBody
        height: width
        radius: width / 2
        color: root.preview
        // A dark accent on a dark surface has no edge of its own, and an unset
        // colour would otherwise be an invisible hole. It brightens on hover
        // and while the picker is open, which is the only affordance saying
        // this dot is pressable.
        border.width: 1
        border.color: (root.picking || swatchMouse.containsMouse)
                    ? Colors.textPrimary : Colors.borderStrong
        scale: swatchMouse.pressed ? 0.9 : 1

        Behavior on border.color { ColorAnimation { duration: 120 } }
        Behavior on scale { NumberAnimation { duration: 80 } }

        MouseArea {
            id: swatchMouse
            anchors.fill: parent
            // Generous: a 13px dot is a small target, and the padding around
            // it is the field's own margin rather than anything clickable.
            anchors.margins: -Spacing.xs
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.swatchClicked()
        }
    }

    function commit() {
        const hex = Theme.normalisedColour(text);
        if (hex === "") {
            // Left as typed on purpose. Snapping the field back to the old
            // value hides what was wrong with what you wrote.
            rejected = true;
            return;
        }
        rejected = false;
        // Focusing out of a field nobody touched is not an edit. Without this,
        // opening the popup and clicking away would write the default accent
        // into a theme file that had deliberately said nothing about it.
        if (hex === value) return;
        committed(hex);
    }

    onEditingFinished: commit()
    Keys.onReturnPressed: commit()
    Keys.onEnterPressed: commit()
    Keys.onEscapePressed: function (event) {
        text = value;
        rejected = false;
        focus = false;
        // Swallowed: the shell's Escape handler closes the panel, and
        // cancelling an edit must not be a way to do that by accident.
        event.accepted = true;
    }
}
