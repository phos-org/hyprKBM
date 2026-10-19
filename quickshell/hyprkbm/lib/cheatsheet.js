.pragma library
.import "keys.js" as Keys
.import "catalogue.js" as Catalogue

// The bind that opens the cheatsheet, so the ⋯ menu can say which key it is
// on, or offer to add one.

var COMMAND = "hyprkbm --cheatsheet"

function isCheatsheetBind(bind) {
    var d = bind.dispatcher
    if (!d || d.dsp !== "exec_cmd" || typeof (d.args || [])[0] !== "string") return false
    return /^(\S*\/)?hyprkbm\s+--cheatsheet(\s|$)/.test(d.args[0].trim())
}

function keysOf(binds) {
    return binds.filter(function (b) { return b.submap === "" && isCheatsheetBind(b) })
                .map(function (b) { return b.keys })
}

// The output to cover: the focused one by name, else the first there is.
function outputFor(screens, name) {
    for (var i = 0; i < screens.length; i++)
        if (screens[i].name === name) return screens[i]
    return screens.length > 0 ? screens[0] : null
}

function title(mods) {
    return mods.length === 0 ? "Keybinds · no modifier" : "Keybinds · " + Keys.sortMods(mods).join(" + ")
}

// ------------------------------------------------- holding Hyprland's binds
//
// Hyprland runs a bound combo before any client sees it, so while the sheet
// is open Hyprland is held in a submap whose one bind is its own way out
// (find mode's trick, lib/capture.js). The binds must come back if the sheet
// dies, so the sheet re-arms a dead-man timer every ARM_EVERY_MS: each timer
// resets only if no newer one was armed since, and the submap is still ours.

var SUBMAP = "hyprkbm-cheatsheet"
var ARM_EVERY_MS = 5000
var HOLD_MS = 15000

// A submap with no binds is not registered, hence SUPER + Escape: it is also
// the way out that works without the sheet.
function holdLua(token) {
    if (typeof token !== "number" || !Number.isSafeInteger(token)) throw new Error("bad token")
    return 'if hl.get_current_submap() ~= "' + SUBMAP + '" then\n'
        + '    hl.define_submap("' + SUBMAP + '", function()\n'
        + '        hl.bind("SUPER + Escape", hl.dsp.submap("reset"))\n'
        + '    end)\n'
        + '    hl.dispatch(hl.dsp.submap("' + SUBMAP + '"))\n'
        + 'end\n'
        + '__hyprkbm_sheet = ' + String(token) + '\n'
        + 'hl.timer(function()\n'
        + '    if __hyprkbm_sheet == ' + String(token) + ' and hl.get_current_submap() == "' + SUBMAP + '" then\n'
        + '        hl.dispatch(hl.dsp.submap("reset"))\n'
        + '    end\n'
        + 'end, { timeout = ' + HOLD_MS + ', type = "oneshot" })'
}

// Guarded, so leaving never resets a submap the user entered meanwhile.
function leaveLua() {
    return '__hyprkbm_sheet = nil\n'
        + 'if hl.get_current_submap() == "' + SUBMAP + '" then hl.dispatch(hl.dsp.submap("reset")) end'
}

function isMouse(bind) {
    if (bind.opts && bind.opts.mouse) return true
    if (bind.source === "hand") return !!(bind.hand && bind.hand.opts && bind.hand.opts.mouse)
    return !!(bind.flags && bind.flags.mouse)
}

// The dispatch a bind stands for, or null when it has none the sheet can send.
function dispatchOf(d) {
    if (!d || d.__function !== undefined || (d.dsp === undefined && d.raw === undefined)) return null
    if (d.raw !== undefined) return "hl.dispatch((\n" + d.raw + "\n))"
    try { return "hl.dispatch(" + Catalogue.dispatcherLua(d) + ")" } catch (e) { return null }
}

// "" when Enter can run the bind, else why not, in words for the title area.
function runnable(bind) {
    var d = bind.dispatcher
    if (!d) return "not readable"
    if (isMouse(bind)) return "a mouse bind"
    if (d.__function !== undefined || (d.dsp === undefined && d.raw === undefined)) return "a Lua function"
    return dispatchOf(d) === null ? "not readable" : ""
}

// Leaving first, so the action runs with the binds already back.
function runLua(binds) {
    var calls = binds.filter(function (b) { return runnable(b) === "" })
                     .map(function (b) { return dispatchOf(b.dispatcher) })
    return calls.length === 0 ? null : leaveLua() + "\n" + calls.join("\n")
}

// The sheet's own key toggles it, even while the binds are held.
function opensSheet(binds) {
    return binds.some(isCheatsheetBind)
}

// A pressed combo's binds, in full (the keys clip them), one per line.
function actions(binds) {
    return binds.map(function (b) {
        return b.describe + (b.description ? "  ·  " + b.description : "")
    }).join("\n")
}

function status(binds) {
    if (binds.length === 0) return "Not bound"
    if (runLua(binds) !== null) return "Enter runs it"
    var reasons = []
    binds.forEach(function (b) {
        var r = runnable(b)
        if (reasons.indexOf(r) < 0) reasons.push(r)
    })
    return "Can't run from here: " + reasons.join(", ")
}
