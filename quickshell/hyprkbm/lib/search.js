.pragma library
.import "keys.js" as Keys

// The header's search: plain words match a bind's keys, action (its text and
// its dispatcher's name, so "exec" finds every command) and description; tags
// narrow. `src:lua` means binds from hyprland.lua. A tag with nothing after
// the colon means "has one": `exec:` runs a command, `desc:` has a
// description, `mod:` has a modifier; the others match everything.

var TAGS = ["mod", "key", "exec", "desc", "submap", "src"]

function parseQuery(text) {
    var words = []
    var tags = {}
    String(text).split(/\s+/).forEach(function (token) {
        if (token === "") return
        var m = /^(\w+):(.*)$/.exec(token)
        if (m !== null && TAGS.indexOf(m[1].toLowerCase()) >= 0) {
            var tag = m[1].toLowerCase()
            if (!tags.hasOwnProperty(tag)) tags[tag] = []
            tags[tag].push(m[2].toLowerCase())
        } else words.push(token.toLowerCase())
    })
    return { words: words, tags: tags, empty: words.length === 0 && Object.keys(tags).length === 0 }
}

function command(bind) {
    var d = bind.dispatcher
    return d && d.dsp === "exec_cmd" && typeof (d.args || [])[0] === "string" ? d.args[0].toLowerCase() : null
}

function every(list, fn) {
    for (var i = 0; i < list.length; i++) if (!fn(list[i])) return false
    return true
}

function matches(bind, query) {
    if (query.empty) return true
    var dsp = bind.dispatcher ? bind.dispatcher.dsp : ""
    var hay = [bind.keys, bind.describe, bind.description, bind.where, dsp].join(" ").toLowerCase()
    if (!every(query.words, function (w) { return hay.indexOf(w) >= 0 })) return false
    var t = query.tags
    if (t.mod && !every(t.mod, function (m) {
        if (m === "") return bind.mods.length > 0
        var canonical = Keys.MODIFIERS[m.toUpperCase()] || m.toUpperCase()
        return bind.mods.indexOf(canonical) >= 0
    })) return false
    if (t.key && !every(t.key, function (k) { return String(bind.key).toLowerCase().indexOf(k) >= 0 })) return false
    if (t.exec && !every(t.exec, function (e) { var c = command(bind); return c !== null && c.indexOf(e) >= 0 })) return false
    if (t.desc && !every(t.desc, function (d) {
        return d === "" ? bind.description !== "" : bind.description.toLowerCase().indexOf(d) >= 0
    })) return false
    if (t.submap && !every(t.submap, function (s) {
        return s === "global" ? bind.submap === "" : bind.submap.toLowerCase().indexOf(s) >= 0
    })) return false
    if (t.src && !every(t.src, function (s) {
        if (s === "") return true
        return s === "lua" || s === "hand" ? bind.source === "hand" : bind.source === s
    })) return false
    return true
}

function filter(binds, query) {
    return binds.filter(function (b) { return matches(b, query) })
}
