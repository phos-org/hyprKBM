import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { load, plain } from "./load.mjs"

const C = load("catalogue")
const CAT = JSON.parse(readFileSync(new URL("../../share/actions.json", import.meta.url), "utf8")).actions

test("actions become the same dispatchers as in Python", () => {
  assert.deepEqual(plain(C.toDispatcher({ kind: "exec_cmd", args: { cmd: "kitty" } }, CAT)),
                   { dsp: "exec_cmd", args: ["kitty"] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "window.move", args: { workspace: 3 } }, CAT)),
                   { dsp: "window.move", args: [{ workspace: 3 }] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "window.close" }, CAT)), { dsp: "window.close", args: [] })
  assert.deepEqual(plain(C.toDispatcher({ kind: "raw", lua: "hl.dsp.exit()" }, CAT)), { raw: "hl.dsp.exit()" })
})

test("bad actions are explained, good ones are not", () => {
  const cases = [
    [{ kind: "nope" }, "unknown action"],
    [{ kind: [] }, "unknown action"],
    [{ kind: "exec_cmd", args: {} }, "needs command"],
    [{ kind: "exec_cmd", args: { cmd: "" } }, "must be text"],
    [{ kind: "exec_cmd", args: { cmd: "x", extra: 1 } }, "no field \"extra\""],
    [{ kind: "window.float", args: { action: "flip" } }, "must be one of"],
    [{ kind: "window.move", args: {} }, "exactly one of"],
    [{ kind: "window.move", args: { workspace: true } }, "workspace number or name"],
    [{ kind: "window.cycle_next", args: { next: "yes" } }, "true or false"],
    [{ kind: "raw", lua: "  " }, "needs some Lua"],
    ["exec_cmd", "must be an object"]
  ]
  for (const [action, problem] of cases) {
    const errors = plain(C.actionErrors(action, CAT))
    assert.ok(errors.some(e => e.includes(problem)), `${JSON.stringify(action)}: ${JSON.stringify(errors)}`)
  }
  assert.deepEqual(plain(C.actionErrors({ kind: "focus", args: { workspace: "e+1" } }, CAT)), [])
  assert.deepEqual(plain(C.actionErrors({ kind: "window.close" }, CAT)), [])
})

test("descriptions match the Python catalogue's", () => {
  assert.equal(C.describeDispatcher({ dsp: "exec_cmd", args: ["kitty"] }, CAT), "Run a command: kitty")
  assert.equal(C.describeDispatcher({ dsp: "focus", args: [{ workspace: 3 }] }, CAT), "Focus (workspace 3)")
  assert.equal(C.describeDispatcher({ dsp: "window.close", args: [] }, CAT), "Close window")
  assert.equal(C.describeDispatcher({ dsp: "window.cycle_next", args: [{ next: false }] }, CAT), "Cycle windows (next no)")
  assert.equal(C.describeDispatcher({ dsp: "group.toggle", args: [] }, CAT), "hl.dsp.group.toggle()")
  assert.equal(C.describeDispatcher({ __function: "/home/u/.config/hypr/hyprland.lua:150" }, CAT), "Lua function (hyprland.lua:150)")
  assert.equal(C.describeDispatcher({ raw: "hl.dsp.layout(\n  'x')" }, CAT), "Lua: hl.dsp.layout( 'x')")
  assert.equal(C.describeAction({ kind: "exec_cmd", args: { cmd: "kitty" } }, CAT), "Run a command: kitty")
})

test("Lua literals match luaval.to_lua", () => {
  assert.equal(C.luaLiteral({ workspace: 3, action: "toggle" }), '{ action = "toggle", workspace = 3 }')
  assert.equal(C.luaLiteral([1, "a", true]), '{ 1, "a", true }')
  assert.equal(C.luaLiteral({ end: 1, "a-b": 2 }), '{ ["a-b"] = 2, ["end"] = 1 }')
  assert.equal(C.luaLiteral('say "hi"\n'), '"say \\"hi\\"\\n"')
  assert.equal(C.dispatcherLua({ dsp: "window.move", args: [{ workspace: 3 }] }), "hl.dsp.window.move({ workspace = 3 })")
})

test("a hand bind's dispatcher becomes an editable action", () => {
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "exec_cmd", args: ["kitty"] }, CAT)),
                   { kind: "exec_cmd", args: { cmd: "kitty" } })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "focus", args: [{ workspace: 2 }] }, CAT)),
                   { kind: "focus", args: { workspace: 2 } })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "window.close", args: [] }, CAT)),
                   { kind: "window.close", args: {} })
  // Not in the catalogue, or not in a shape it knows: kept as raw Lua.
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "group.toggle", args: [] }, CAT)),
                   { kind: "raw", lua: "hl.dsp.group.toggle()" })
  assert.deepEqual(plain(C.actionFromDispatcher({ dsp: "window.resize", args: [{ x: 10, y: 0, relative: true }] }, CAT)),
                   { kind: "raw", lua: "hl.dsp.window.resize({ relative = true, x = 10, y = 0 })" })
  assert.equal(C.actionFromDispatcher({ __function: "f.lua:1" }, CAT), null)
  assert.equal(C.actionFromDispatcher({ __opaque: true }, CAT), null)
})

test("default args come from the fields' defaults", () => {
  assert.deepEqual(plain(C.defaultArgs(C.entryById(CAT, "window.fullscreen"))), { mode: "fullscreen", action: "toggle" })
  assert.deepEqual(plain(C.defaultArgs(C.entryById(CAT, "exec_cmd"))), {})
})
