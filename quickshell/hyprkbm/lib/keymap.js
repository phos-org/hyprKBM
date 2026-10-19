.pragma library
.import "keys.js" as Keys
.import "search.js" as Search
.import "model.js" as Model

// Which keycap shows which binds. A key's id is its keysym in lower case, as
// keys.keyId gives it, so "Return", "return" and an alias all land together.

var MOUSE = [
    { id: "mouse:272", label: "L" }, { id: "mouse:273", label: "R" },
    { id: "mouse:274", label: "M" }, { id: "mouse_up", label: "⇡" },
    { id: "mouse_down", label: "⇣" }
]

function sameMods(a, b) {
    return Keys.sortMods(a).join("+") === Keys.sortMods(b).join("+")
}

function keyStates(binds, submap, mods) {
    var out = {}
    binds.forEach(function (b) {
        if (b.submap !== submap || b.combo === null || !sameMods(b.mods, mods)) return
        var id = Keys.keyId(b.key)
        if (!out.hasOwnProperty(id)) out[id] = { binds: [], state: "bound" }
        out[id].binds.push(b)
    })
    Object.keys(out).forEach(function (id) {
        var live = out[id].binds.filter(function (b) { return !b.allowConflict })
        // Same rule as the header and the bind list: only a group with a
        // hyprKBM bind stops an apply. Two hand binds are an overlap.
        if (live.length > 1) out[id].state = Model.blocks(live) ? "conflict" : "overlap"
    })
    return out
}

function bindsOn(binds, submap, mods, keyId) {
    if (keyId === "") return []
    return binds.filter(function (b) {
        return b.submap === submap && b.combo !== null && sameMods(b.mods, mods) && Keys.keyId(b.key) === keyId
    })
}

// Keys free under the view's modifiers but bound under some other set
// (including none): drawn outlined, so a missing SUPER + D does not hide
// SUPER + SHIFT + D.
function otherKeys(binds, submap, mods) {
    var here = {}
    var other = {}
    binds.forEach(function (b) {
        if (b.submap !== submap || b.combo === null) return
        var id = Keys.keyId(b.key)
        if (sameMods(b.mods, mods)) here[id] = true
        else other[id] = true
    })
    var out = {}
    Object.keys(other).forEach(function (id) { if (!here[id]) out[id] = true })
    return out
}

// The binds on one key under every other modifier set, grouped by modifiers
// so the same combo's binds sit together; ties keep the config's order.
function otherCombos(binds, submap, mods, keyId) {
    if (keyId === "") return []
    var found = []
    binds.forEach(function (b, i) {
        if (b.submap === submap && b.combo !== null && !sameMods(b.mods, mods) && Keys.keyId(b.key) === keyId)
            found.push({ bind: b, order: i, mods: Keys.sortMods(b.mods).join("+") })
    })
    found.sort(function (x, y) {
        return x.mods < y.mods ? -1 : x.mods > y.mods ? 1 : x.order - y.order
    })
    return found.map(function (f) { return f.bind })
}

function matchingKeys(binds, submap, query) {
    if (query.empty) return null
    var out = {}
    binds.forEach(function (b) {
        if (b.submap === submap && b.combo !== null && Search.matches(b, query)) out[Keys.keyId(b.key)] = true
    })
    return out
}

function extraKeys(binds) {
    var seen = {}
    var media = []
    binds.forEach(function (b) {
        if (b.combo === null || !/^xf86/i.test(b.key)) return
        var id = Keys.keyId(b.key)
        if (seen[id]) return
        seen[id] = true
        media.push({ id: b.key, label: b.key.replace(/^XF86(Audio|MonBrightness)?/i, "") })
    })
    media.sort(function (x, y) { return x.id < y.id ? -1 : x.id > y.id ? 1 : 0 })
    return MOUSE.concat(media)
}

function unplaced(binds, submap, known) {
    return binds.filter(function (b) {
        return b.submap === submap && (b.combo === null || !known[Keys.keyId(b.key)])
    })
}

function conflictTargets(conflicts) {
    return conflicts.map(function (group) {
        return { submap: group[0].submap, mods: group[0].mods, key: Keys.keyId(group[0].key) }
    })
}
