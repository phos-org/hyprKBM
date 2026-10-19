import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const K = load("keymap")
const S = load("search")
function bind(uid, keys, mods, key, extra) {
  return Object.assign({ uid, keys, combo: mods.concat([key.toLowerCase()]).join("+"), mods, key,
    submap: "", allowConflict: false, describe: "", description: "", source: "hand", where: "", dispatcher: null }, extra || {})
}
const BINDS = [
  bind("a", "SUPER + F", ["SUPER"], "F"),
  bind("b", "SUPER + F", ["SUPER"], "F"),
  bind("c", "SUPER + Q", ["SUPER"], "Q"),
  bind("d", "SUPER + SHIFT + Q", ["SUPER", "SHIFT"], "Q"),
  bind("e", "XF86AudioMute", [], "XF86AudioMute"),
  bind("f", "SUPER + mouse:272", ["SUPER"], "mouse:272"),
  bind("g", "right", [], "right", { submap: "resize" }),
  bind("h", "SUPER + weird_key", ["SUPER"], "weird_key")
]

test("key states for the held modifiers in the submap", () => {
  const s = plain(K.keyStates(BINDS, "", ["SUPER"]))
  assert.deepEqual(Object.keys(s).sort(), ["f", "mouse:272", "q", "weird_key"])
  // a and b are both hand binds: an overlap, which never stops an apply.
  assert.equal(s.f.state, "overlap")
  assert.equal(s.q.state, "bound")
  assert.deepEqual(s.q.binds.map(b => b.uid), ["c"])
  assert.deepEqual(Object.keys(plain(K.keyStates(BINDS, "resize", []))), ["right"])
})

test("an allowed conflict is just bound", () => {
  const allowed = BINDS.map(b => b.uid === "b" ? Object.assign({}, b, { allowConflict: true }) : b)
  assert.equal(K.keyStates(allowed, "", ["SUPER"]).f.state, "bound")
})

test("binds on one key", () => {
  assert.deepEqual(plain(K.bindsOn(BINDS, "", ["SUPER", "SHIFT"], "q")).map(b => b.uid), ["d"])
  assert.deepEqual(plain(K.bindsOn(BINDS, "", ["SUPER"], "")), [])
})

test("search lights keys under any modifiers", () => {
  assert.equal(K.matchingKeys(BINDS, "", S.parseQuery("")), null)
  assert.deepEqual(plain(K.matchingKeys(BINDS, "", S.parseQuery("key:q"))), { q: true })
})

test("extra keys: the mouse, then media keys the config uses", () => {
  const ids = plain(K.extraKeys(BINDS)).map(k => k.id)
  assert.deepEqual(ids, ["mouse:272", "mouse:273", "mouse:274", "mouse_up", "mouse_down", "XF86AudioMute"])
  assert.equal(plain(K.extraKeys(BINDS))[5].label, "Mute")
})

test("unplaced binds are those no keycap shows", () => {
  const known = { f: true, q: true, xf86audiomute: true, "mouse:272": true }
  assert.deepEqual(plain(K.unplaced(BINDS, "", known)).map(b => b.uid), ["h"])
  const broken = [bind("x", "???", [], "???", { combo: null })]
  assert.deepEqual(plain(K.unplaced(broken, "", known)).map(b => b.uid), ["x"])
})

test("conflict targets say where to look", () => {
  const groups = [[BINDS[0], BINDS[1]]]
  assert.deepEqual(plain(K.conflictTargets(groups)), [{ submap: "", mods: ["SUPER"], key: "f" }])
})

test("a key is a conflict only when its group blocks", () => {
  const binds = [
    bind("a", "SUPER + F", ["SUPER"], "F"),
    bind("b", "SUPER + F", ["SUPER"], "F", { source: "hyprkbm" }),
    bind("c", "SUPER + G", ["SUPER"], "G", { source: "override" }),
    bind("d", "SUPER + G", ["SUPER"], "G", { source: "hyprkbm", allowConflict: true }),
    bind("e", "SUPER + H", ["SUPER"], "H", { source: "hyprkbm" })
  ]
  const s = plain(K.keyStates(binds, "", ["SUPER"]))
  assert.equal(s.f.state, "conflict")
  assert.equal(s.g.state, "bound")
  assert.equal(s.h.state, "bound")
})

test("a key bound only under other modifiers is outlined, not lit", () => {
  const binds = [
    bind("d", "SUPER + SHIFT + D", ["SUPER", "SHIFT"], "D"),
    bind("w1", "SUPER + W", ["SUPER"], "W"),
    bind("w2", "SUPER + SHIFT + W", ["SUPER", "SHIFT"], "W")
  ]
  assert.deepEqual(plain(K.otherKeys(binds, "", ["SUPER"])), { d: true })
  assert.equal(K.keyStates(binds, "", ["SUPER"]).d, undefined)
  // Bound under the view's mods too: lit as usual, never outlined.
  assert.equal(K.keyStates(binds, "", ["SUPER"]).w.state, "bound")
  // Order of the modifiers does not matter.
  assert.deepEqual(plain(K.otherKeys(binds, "", ["SHIFT", "SUPER"])), {})
})

test("other keys: no-modifier view, submaps and unreadable binds", () => {
  const binds = [
    bind("a", "SUPER + A", ["SUPER"], "A"),
    bind("r", "SUPER + R", ["SUPER"], "R", { submap: "resize" }),
    bind("x", "SUPER + X", ["SUPER"], "X", { combo: null })
  ]
  assert.deepEqual(plain(K.otherKeys(binds, "", [])), { a: true })
  assert.deepEqual(plain(K.otherKeys(binds, "resize", [])), { r: true })
  assert.deepEqual(plain(K.otherKeys(binds, "", ["SUPER"])), {})
})

test("other combos on a key, sorted by modifiers then by order", () => {
  const binds = [
    bind("s2", "SUPER + SHIFT + D", ["SUPER", "SHIFT"], "D"),
    bind("c", "CTRL + D", ["CTRL"], "D"),
    bind("here", "SUPER + D", ["SUPER"], "D"),
    bind("bare", "D", [], "D"),
    bind("s1", "SHIFT + SUPER + D", ["SHIFT", "SUPER"], "D"),
    bind("sub", "CTRL + D", ["CTRL"], "D", { submap: "resize" }),
    bind("null", "ALT + D", ["ALT"], "D", { combo: null }),
    bind("e", "CTRL + E", ["CTRL"], "E")
  ]
  const uids = plain(K.otherCombos(binds, "", ["SUPER"], "d")).map(b => b.uid)
  assert.deepEqual(uids, ["bare", "c", "s2", "s1"])
  assert.deepEqual(plain(K.otherCombos(binds, "", [], "d")).map(b => b.uid), ["c", "here", "s2", "s1"])
  assert.deepEqual(plain(K.otherCombos(binds, "", ["SUPER"], "")), [])
})
