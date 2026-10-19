.pragma library
.import "qtkeys.js" as QtKeys

// Find mode: the user presses a keybind to select it. Hyprland would run a
// bound key instead of handing it to the panel, so for a moment Hyprland is
// switched into a submap that binds nothing but its own way out; every other
// key then reaches the focused panel. bin/hyprkbm-watch carries a copy of
// leaveLua() (LEAVE_CAPTURE_LUA) as a backstop for a panel that died mid-find.

var SUBMAP = "hyprkbm-capture"

// If the panel dies, or the reset never comes, Hyprland resets itself.
var TIMEOUT_MS = 10000

// A submap with no binds is not registered, hence SUPER + Escape: it is also
// the way out that works without the panel.
function enterLua() {
    return 'hl.define_submap("hyprkbm-capture", function()\n'
        + '    hl.bind("SUPER + Escape", hl.dsp.submap("reset"))\n'
        + 'end)\n'
        + 'hl.dispatch(hl.dsp.submap("hyprkbm-capture"))\n'
        + 'hl.timer(function()\n'
        + '    if hl.get_current_submap() == "hyprkbm-capture" then\n'
        + '        hl.dispatch(hl.dsp.submap("reset"))\n'
        + '    end\n'
        + 'end, { timeout = ' + TIMEOUT_MS + ', type = "oneshot" })'
}

// Guarded, so leaving never resets a submap the user entered meanwhile.
function leaveLua() {
    return 'if hl.get_current_submap() == "hyprkbm-capture" then hl.dispatch(hl.dsp.submap("reset")) end'
}

// The combo a key event names, or null for a modifier on its own (the caller
// keeps waiting for the real key) or a key with no bind name.
function comboFrom(key, modifiers) {
    var name = QtKeys.keysymFromQt(key, modifiers)
    if (name === null) return null
    return { mods: QtKeys.modsFromQt(modifiers), key: name }
}
