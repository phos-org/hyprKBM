import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { load, plain } from "./load.mjs"

const M = load("model")
const CAT = JSON.parse(readFileSync(new URL("../../share/actions.json", import.meta.url), "utf8")).actions

function hand(i, keys, combo, dsp, args, extra) {
  return Object.assign({
    uid: "h:" + i, keys, combo, submap: "", where: "hyprland.lua:" + (i + 1),
    fingerprint: dsp + ":" + JSON.stringify(args), reproducible: true,
    description: "", describe: dsp, dispatcher: { dsp, args }, opts: {}
  }, extra || {})
}

const HAND = [
  hand(0, "SUPER + F", "SUPER+f", "exec_cmd", ["dolphin"]),
  hand(1, "SUPER + P", "SUPER+p", "window.pseudo", []),
  hand(2, "SUPER + F", "SUPER+f", "window.resize", [], { submap: "resize" })
]
const FILES = { kind: "exec_cmd", args: { cmd: "nautilus" } }

test("merge keeps hand binds and adds hyprKBM's", () => {
  const model = M.addBind(M.emptyModel(), { keys: "SUPER + B", action: { kind: "exec_cmd", args: { cmd: "firefox" } } })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => [b.uid, b.source]), [["h:0", "hand"], ["h:1", "hand"], ["h:2", "hand"], ["k:b1", "hyprkbm"]])
  const own = m.binds[3]
  assert.equal(own.combo, "SUPER+b")
  assert.deepEqual(own.mods, ["SUPER"])
  assert.equal(own.key, "B")
  assert.equal(own.describe, "Run a command: firefox")
  assert.deepEqual(own.dispatcher, { dsp: "exec_cmd", args: ["firefox"] })
  assert.deepEqual(m.conflicts, [])
})

test("an override replaces exactly its hand bind", () => {
  const model = M.overrideHand(M.emptyModel(), HAND[0], { keys: "SUPER + F", action: FILES })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => b.uid), ["h:1", "h:2", "k:b1"])
  assert.equal(m.binds[2].source, "override")
  assert.equal(m.binds[2].hand.where, "hyprland.lua:1")
  assert.deepEqual(plain(model.binds[0].replaces), { keys: "SUPER + F", submap: "", fingerprint: 'exec_cmd:["dolphin"]' })
})

test("an unbind removes its hand bind and can be undone", () => {
  let model = M.unbindHand(M.emptyModel(), HAND[1])
  model = M.unbindHand(model, HAND[1])   // twice is once
  assert.equal(model.unbinds.length, 1)
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.binds.map(b => b.uid), ["h:0", "h:2"])
  assert.deepEqual(m.removed.map(r => r.uid), ["h:1"])
  assert.deepEqual(plain(M.restoreHand(model, HAND[1])).unbinds, [])
})

test("targets that are gone are stale; a stale override is an ordinary bind", () => {
  const model = M.normalise({ version: 1, binds: [{ id: "b1", keys: "SUPER + X", action: FILES,
    replaces: { keys: "SUPER + X", submap: "", fingerprint: "gone" } }],
    unbinds: [{ keys: "SUPER + Y", submap: "", fingerprint: "gone" }] })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.stale.map(s => [s.kind, s.id, s.keys]), [["unbind", null, "SUPER + Y"], ["bind", "b1", "SUPER + X"]])
  assert.equal(m.binds[3].source, "hyprkbm")
})

test("conflicts group by submap and combo, ignoring allowed ones", () => {
  let model = M.addBind(M.emptyModel(), { keys: "WIN + f", action: FILES })
  model = M.addBind(model, { keys: "SUPER + P", action: FILES, allowConflict: true })
  const m = plain(M.merge(HAND, model, CAT))
  assert.deepEqual(m.conflicts.map(g => g.map(b => b.uid)), [["h:0", "k:b1"]])
})

test("edits never mutate their input and tidy empty fields", () => {
  const before = M.addBind(M.emptyModel(), { keys: "SUPER + B", submap: "", action: FILES, description: "", flags: { locked: false }, allowConflict: false })
  const snapshot = JSON.stringify(before)
  assert.deepEqual(plain(before.binds[0]), { id: "b1", keys: "SUPER + B", action: FILES })
  const after = M.updateBind(before, "b1", { description: "Files", flags: { locked: true } })
  assert.equal(JSON.stringify(before), snapshot)
  assert.deepEqual(plain(after.binds[0]), { id: "b1", keys: "SUPER + B", action: FILES, description: "Files", flags: { locked: true } })
  assert.equal(M.removeBind(after, "b1").binds.length, 0)
  assert.equal(M.newId(after), "b2")
})

test("submaps", () => {
  const model = M.addSubmap(M.emptyModel(), "move", "escape")
  assert.deepEqual(plain(model.submaps), [{ name: "move", reset: "escape" }])
  assert.deepEqual(plain(M.submapNames(HAND, [{ name: "resize", reset: "escape" }], model)), ["", "move", "resize"])
})

test("an override is blocked by a Lua function on the same keys", () => {
  const fn = hand(3, "SUPER + F", "SUPER+f", "x", [], { submap: "x", reproducible: false, dispatcher: { __function: "h.lua:9" }, where: "hyprland.lua:9" })
  assert.equal(M.overrideBlocker(HAND.concat([fn]), HAND[0]), "hyprland.lua:9")
  assert.equal(M.overrideBlocker(HAND, HAND[0]), null)
  assert.equal(M.overrideBlocker(HAND.concat([fn]), fn), null)
})

test("summary counts what changed", () => {
  const saved = M.addBind(M.emptyModel(), { keys: "SUPER + B", action: FILES })
  let model = M.updateBind(saved, "b1", { description: "x" })
  model = M.addBind(model, { keys: "SUPER + N", action: FILES })
  model = M.unbindHand(model, HAND[1])
  model = M.addSubmap(model, "move", "escape")
  assert.deepEqual(plain(M.summary(saved, model)), { added: 1, changed: 1, removed: 0, unbound: 1, restored: 0, submaps: 1 })
  assert.deepEqual(plain(M.summary(model, saved)), { added: 0, changed: 1, removed: 1, unbound: 0, restored: 1, submaps: -1 })
})

test("blocks: only a conflict involving a hyprKBM bind stops an apply", () => {
  const hand = { source: "hand" }, own = { source: "hyprkbm" }, over = { source: "override" }
  assert.equal(M.blocks([hand, own]), true)
  assert.equal(M.blocks([hand, hand]), false)
  assert.equal(M.blocks([own, own]), true)
  assert.equal(M.blocks([hand, over]), true)
})

test("FLAG_NAMES is exactly the flags Python's model accepts", () => {
  const py = readFileSync(fileURLToPath(new URL("../../lib/hyprkbm/model.py", import.meta.url)), "utf8")
  const literal = py.match(/^FLAGS\s*=\s*\{([^}]*)\}/m)[1]
  const names = [...literal.matchAll(/"(\w+)"/g)].map(m => m[1])
  assert.equal(names.length, 13)
  assert.deepEqual([...M.FLAG_NAMES].sort(), names.sort())
})

test("droppedOpts names the options of a hand bind hyprKBM cannot keep", () => {
  assert.deepEqual(plain(M.droppedOpts({ repeating: true, description: "x", desc: "y" })), [])
  assert.deepEqual(plain(M.droppedOpts({ locked: true, foo: 1, bar: true })), ["foo", "bar"])
  assert.deepEqual(plain(M.droppedOpts(undefined)), [])
})
