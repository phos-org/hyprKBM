.pragma library

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
