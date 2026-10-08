.pragma library
.import "keys.js" as Keys
.import "catalogue.js" as Catalogue

// The panel's staged keybinds.json, and what Hyprland would end up with if it
// were applied: hand-written binds, minus the ones overridden or unbound,
// plus hyprKBM's own. A twin of model.merge in Python, which stays the
// authority -- hyprkbm-apply validates everything again.
//
// Nothing here mutates its input. The store assigns each result to a
// `property var`, and an object changed in place would never repaint.

var FLAG_NAMES = ["repeating", "locked", "release", "long_press", "non_consuming",
                  "transparent", "ignore_mods"]

function emptyModel() { return { version: 1, submaps: [], binds: [], unbinds: [] } }

function clone(v) { return JSON.parse(JSON.stringify(v)) }

function normalise(model) {
    var m = clone(model || emptyModel())
    m.version = m.version === undefined ? 1 : m.version
    m.submaps = Array.isArray(m.submaps) ? m.submaps : []
    m.binds = Array.isArray(m.binds) ? m.binds : []
    m.unbinds = Array.isArray(m.unbinds) ? m.unbinds : []
    return m
}

function matches(h, target) {
    return h.combo !== null && h.combo === Keys.idOf(target.keys)
        && h.submap === (target.submap || "") && h.fingerprint === target.fingerprint
}

function handBind(h) {
    var c = Keys.parse(h.keys)
    return {
        uid: h.uid, source: "hand", keys: h.keys, combo: h.combo,
        mods: c === null ? [] : c.mods, key: c === null ? h.keys : c.key,
        submap: h.submap, where: h.where, id: null, hand: h,
        description: h.description || "", describe: h.describe, dispatcher: h.dispatcher,
        reproducible: h.reproducible, allowConflict: false, action: null, flags: {}
    }
}

function ownBind(b, catalogue, replaced) {
    var c = Keys.parse(b.keys)
    var valid = Catalogue.actionErrors(b.action, catalogue).length === 0
    return {
        uid: "k:" + b.id, source: replaced === null ? "hyprkbm" : "override",
        keys: b.keys, combo: c === null ? null : Keys.comboId(c.mods, c.key),
        mods: c === null ? [] : c.mods, key: c === null ? b.keys : c.key,
        submap: b.submap || "", where: b.id, id: b.id, hand: replaced,
        description: b.description || "", describe: Catalogue.describeAction(b.action, catalogue),
        dispatcher: valid ? Catalogue.toDispatcher(b.action, catalogue) : null,
        reproducible: true, allowConflict: b.allowConflict === true,
        action: b.action, flags: b.flags || {}
    }
}

function conflicts(binds) {
    var groups = {}
    var order = []
    binds.forEach(function (b) {
        if (b.combo === null || b.allowConflict) return
        var k = b.submap + "\u0000" + b.combo
        if (!groups.hasOwnProperty(k)) { groups[k] = []; order.push(k) }
        groups[k].push(b)
    })
    return order.map(function (k) { return groups[k] }).filter(function (g) { return g.length > 1 })
}

function merge(hand, model, catalogue) {
    model = normalise(model)
    var superseded = {}
    var removed = []
    var stale = []

    function supersede(target) {
        var hits = []
        hand.forEach(function (h, i) { if (matches(h, target)) { hits.push(i); superseded[i] = true } })
        return hits
    }

    model.unbinds.forEach(function (u) {
        var hits = supersede(u)
        if (hits.length === 0)
            stale.push({ kind: "unbind", id: null, keys: u.keys,
                         message: "The bind on " + u.keys + " this removes is no longer in hyprland.lua; the unbind does nothing." })
        hits.forEach(function (i) { removed.push({ uid: hand[i].uid, hand: hand[i] }) })
    })

    var own = model.binds.map(function (b) {
        var replaced = null
        if (b.replaces) {
            var hits = supersede(b.replaces)
            if (hits.length > 0) replaced = hand[hits[0]]
            else stale.push({ kind: "bind", id: b.id, keys: b.keys,
                              message: "The hyprland.lua bind this replaced is gone; it is now an ordinary bind." })
        }
        return ownBind(b, catalogue, replaced)
    })

    var binds = []
    hand.forEach(function (h, i) { if (!superseded[i]) binds.push(handBind(h)) })
    binds = binds.concat(own)
    return { binds: binds, removed: removed, stale: stale, conflicts: conflicts(binds) }
}

function newId(model) {
    var used = {}
    normalise(model).binds.forEach(function (b) { used[b.id] = true })
    var n = 1
    while (used["b" + n]) n++
    return "b" + n
}

// Optional fields are left out rather than written empty, so keybinds.json
// stays the file a person would have written.
function tidy(b) {
    var out = { id: b.id, keys: b.keys }
    if (b.submap) out.submap = b.submap
    out.action = b.action
    if (b.description) out.description = b.description
    var flags = {}
    var any = false
    Object.keys(b.flags || {}).forEach(function (f) { if (b.flags[f] === true) { flags[f] = true; any = true } })
    if (any) out.flags = flags
    if (b.allowConflict === true) out.allowConflict = true
    if (b.replaces) out.replaces = b.replaces
    return out
}

function addBind(model, fields) {
    var m = normalise(model)
    var b = clone(fields)
    b.id = newId(m)
    m.binds.push(tidy(b))
    return m
}

function updateBind(model, id, fields) {
    var m = normalise(model)
    m.binds = m.binds.map(function (b) {
        if (b.id !== id) return b
        var next = clone(b)
        Object.keys(fields).forEach(function (k) { next[k] = clone(fields[k]) })
        return tidy(next)
    })
    return m
}

function removeBind(model, id) {
    var m = normalise(model)
    m.binds = m.binds.filter(function (b) { return b.id !== id })
    return m
}

function targetOf(h) { return { keys: h.keys, submap: h.submap, fingerprint: h.fingerprint } }

function unbindHand(model, h) {
    var m = normalise(model)
    var present = m.unbinds.some(function (u) { return matches(h, u) })
    if (!present) m.unbinds.push(targetOf(h))
    return m
}

function restoreHand(model, h) {
    var m = normalise(model)
    m.unbinds = m.unbinds.filter(function (u) { return !matches(h, u) })
    return m
}

function overrideHand(model, h, fields) {
    var f = clone(fields)
    f.replaces = targetOf(h)
    return addBind(model, f)
}

function addSubmap(model, name, reset) {
    var m = normalise(model)
    m.submaps.push({ name: name, reset: reset })
    return m
}

function submapNames(hand, handSubmaps, model) {
    var seen = {}
    var m = normalise(model)
    ;(handSubmaps || []).forEach(function (s) { seen[s.name] = true })
    m.submaps.forEach(function (s) { seen[s.name] = true })
    hand.forEach(function (h) { if (h.submap) seen[h.submap] = true })
    m.binds.forEach(function (b) { if (b.submap) seen[b.submap] = true })
    return [""].concat(Object.keys(seen).sort())
}

// hl.unbind drops a combo in every submap, so replacing one hand bind means
// re-creating every other hand bind on its keys -- and a Lua function cannot
// be re-created. The same rule hyprkbm-apply enforces, given early.
function overrideBlocker(hand, target) {
    for (var i = 0; i < hand.length; i++) {
        var h = hand[i]
        if (h === target || h.uid === target.uid) continue
        if (h.combo !== null && h.combo === target.combo && !h.reproducible) return h.where
    }
    return null
}

function summary(saved, model) {
    var a = normalise(saved)
    var b = normalise(model)
    var before = {}
    a.binds.forEach(function (x) { before[x.id] = JSON.stringify(x) })
    var after = {}
    b.binds.forEach(function (x) { after[x.id] = JSON.stringify(x) })
    var out = { added: 0, changed: 0, removed: 0, unbound: 0, restored: 0,
                submaps: b.submaps.length - a.submaps.length }
    Object.keys(after).forEach(function (id) {
        if (!before.hasOwnProperty(id)) out.added++
        else if (before[id] !== after[id]) out.changed++
    })
    Object.keys(before).forEach(function (id) { if (!after.hasOwnProperty(id)) out.removed++ })
    var ua = a.unbinds.map(function (u) { return JSON.stringify(u) })
    var ub = b.unbinds.map(function (u) { return JSON.stringify(u) })
    out.unbound = ub.filter(function (u) { return ua.indexOf(u) < 0 }).length
    out.restored = ua.filter(function (u) { return ub.indexOf(u) < 0 }).length
    return out
}
