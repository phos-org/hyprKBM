.pragma library

// The few characters a keycap has room for: what the key does under the held
// modifiers. A description wins when it fits, since the user chose it.

var MAX = 8

function clip(text) {
    text = String(text)
    return text.length > MAX ? text.slice(0, MAX - 1) + "…" : text
}

function shortLabel(bind) {
    if (bind.description && bind.description.length <= MAX) return bind.description
    var d = bind.dispatcher
    if (!d) return "?"
    if (d.__function !== undefined) return "fn"
    if (d.raw !== undefined) return "lua"
    if (d.dsp === undefined) return "?"
    var args = d.args || []
    var first = args[0]
    if (d.dsp === "exec_cmd" && typeof first === "string") {
        var word = first.trim().split(/\s+/)[0] || ""
        return clip(word.split("/").pop())
    }
    if ((d.dsp === "focus" || d.dsp === "window.move") && first !== null
            && typeof first === "object" && first.workspace !== undefined)
        return (d.dsp === "focus" ? "ws " : "→ws ") + first.workspace
    if (d.dsp === "layout" && typeof first === "string") return clip(first.replace(/^toggle/, ""))
    if (d.dsp === "submap" && typeof first === "string") return clip("↪" + first)
    return clip(d.dsp.split(".").pop().replace(/_/g, " "))
}
