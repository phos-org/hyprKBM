import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

// The three theme choices worth making without opening an editor: which
// bundled preset, the accent everything else is derived from, and which ramp.
//
// It stops there deliberately. The other thirteen tokens stay in theme.json,
// documented in ../presets/README.md -- a sixteen-field colour editor is a
// different product, and a file you can read in one screen is a better place
// to design a palette than a dropdown is.
//
// Every control writes theme.json and nothing else. The panel already watches
// that file, so a change here re-themes by exactly the route a hand edit
// takes; there is no second, in-process path that could disagree with what
// ended up on disk.
Popup {
    id: root

    // What the accent field, the swatch and the picker are all showing. The
    // colour in force, until somebody starts expressing a different one --
    // by dragging in the picker or by typing a hex. Holding it here rather
    // than in either control is what makes the two routes one value instead
    // of two that have to be kept in step.
    //
    // Expressing is not committing. Nothing reaches theme.json until a drag
    // ends, a preset swatch is clicked, or Enter is pressed in the field.
    property string candidate: root.accentInForce
    property bool picking: false

    // The accent the theme file names, and only the resolved colour when it
    // names none.
    //
    // Not simply String(Colors.accentPrimary), which passes through the
    // built-in default for an instant on every reload: Colors blanks all
    // sixteen overrides before re-reading the file, and each blanking emits a
    // change, so anything watching the resolved colour sees the default go by.
    // Measured -- a commit of #4f7fa8 over an existing theme reported
    // #7f8fd6, then #c2718c, then #4f7fa8. Adopting that middle value moved
    // the picker's hue to the default's, and for a grey, which carries no hue
    // of its own to restore, it stayed there.
    readonly property string accentInForce: {
        const named = Theme.overrides.accentPrimary;
        return Theme.isColour(named) ? named : String(Colors.accentPrimary);
    }

    // The panel has caught up with what was asked for, so there is no longer a
    // candidate distinct from it. Cleared this way rather than at the moment
    // of committing, so the swatch does not flick back to the old colour for
    // the frame between the write and the file being read again.
    onAccentInForceChanged: if (!accentField.activeFocus) root.candidate = root.accentInForce

    // Hangs from the button that opened it, right edges aligned: that button
    // is at the right end of the header, and a left-aligned popup would run
    // off the window.
    x: parent ? parent.width - width : 0
    y: parent ? parent.height + Spacing.xs : 0
    // Narrower than the inspector column beside it, so it reads as something
    // hanging off a button rather than as a second panel -- but wide enough
    // that the two hints below wrap to two lines rather than four.
    implicitWidth: 240

    padding: Spacing.lg
    // CloseOnPressOutsideParent, not CloseOnPressOutside: the parent is the
    // button, so a click on it is left to the button's own toggle instead of
    // being a close that the click then immediately reopens.
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
    // Escape has to land here rather than on the window, whose handler quits
    // the panel. Closing a popup must never be a way to close the editor.
    focus: true

    background: Rectangle {
        color: Colors.bgSurface
        radius: Radius.md
        border.width: 1
        border.color: Colors.borderStrong
    }

    contentItem: ColumnLayout {
        spacing: Spacing.md

        Field {
            label: "Preset"
            Select {
                width: parent.width
                model: Theme.presets
                currentIndex: Theme.presets.indexOf(Theme.currentPreset)
                // No preset matches the file. That is the normal state of a
                // hand-written theme, and of any preset once the accent below
                // has been changed -- so say so rather than name a preset this
                // file is not.
                displayText: currentIndex < 0 ? "Custom" : currentText
                onActivated: function (index) { Theme.usePreset(Theme.presets[index]) }
            }
        }

        Field {
            label: "Accent"
            // Only ever shown against something the user just typed, so it can
            // afford to be blunt about what happened to it. The example is the
            // value in force rather than a literal: it is the one hex on
            // screen the user can check the shape of, and a literal here would
            // be a palette colour hardcoded into a component.
            hint: accentField.rejected
                  ? "Not a colour. Try " + accentField.value + ". The accent is unchanged."
                  : ""

            ColourInput {
                id: accentField
                width: parent.width
                // The colour in force, which is the mode's default until a
                // theme says otherwise -- so the field opens on a real value to
                // edit rather than on a blank. Deliberately not the candidate:
                // this is what "unchanged" means when the field decides whether
                // leaving it was an edit at all.
                value: root.accentInForce
                preview: root.candidate
                picking: root.picking

                onSwatchClicked: root.picking = !root.picking
                onEdited: function (hex) { root.candidate = hex }
                onCommitted: function (hex) { Theme.setAccent(hex) }
            }
        }

        // Expands the popup rather than opening a second one over it: a nested
        // popup would be dismissed by this one's own close-on-press-outside the
        // moment it was touched, and two stacked surfaces for one value is one
        // more than the value deserves.
        //
        // A sibling of the Accent field rather than part of it, because Field
        // draws its hint underneath its content: with the picker inside, the
        // "not a colour" complaint would appear a hundred pixels below the
        // field it is complaining about.
        ColourPicker {
            id: picker
            Layout.fillWidth: true
            visible: root.picking
            value: root.candidate

            onMoved: function (hex) {
                root.candidate = hex;
                // Straight into the field, so the hex being dragged towards is
                // readable during the drag rather than after it.
                accentField.show(hex);
            }
            onPicked: function (hex) { Theme.setAccent(hex) }
        }

        Field {
            label: "Mode"
            // fuji and paper name every background outright, so once one of
            // them is picked the mode has nothing left to decide and the
            // control looks broken. It is not: the explicit colours win, which
            // is the whole point of them. Worded without naming which colours,
            // because one pinned token reads the same here as all of them.
            hint: Theme.hasExplicitRampColours
                  ? "This theme sets colours explicitly, and the mode will not move those."
                  : ""
            Select {
                width: parent.width
                // A pair of names rather than a Toggle: neither of these is
                // the "on" one, and "Light mode: off" is a worse way to say
                // dark than "Dark" is.
                model: ["Dark", "Light"]
                currentIndex: Theme.mode === "light" ? 1 : 0
                onActivated: function (index) { Theme.setMode(index === 1 ? "light" : "dark") }
            }
        }
    }
}
