import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const C = load("capture")

test("the constants name the submap and its safety timeout", () => {
  assert.equal(C.SUBMAP, "hyprkbm-capture")
  assert.equal(C.TIMEOUT_MS, 10000)
})

test("enterLua defines the submap with an escape hatch, switches, and arms a timer", () => {
  const lua = C.enterLua()
  assert.ok(lua.includes('hl.define_submap("hyprkbm-capture"'))
  assert.ok(lua.includes('hl.bind("SUPER + Escape", hl.dsp.submap("reset"))'))
  assert.ok(lua.includes('hl.dispatch(hl.dsp.submap("hyprkbm-capture"))'))
  assert.ok(lua.includes("timeout = 10000"))
  assert.ok(lua.includes('type = "oneshot"'))
})

test("leaveLua only resets while still in the capture submap", () => {
  assert.equal(C.leaveLua(),
    'if hl.get_current_submap() == "hyprkbm-capture" then hl.dispatch(hl.dsp.submap("reset")) end')
})

test("comboFrom names the modifiers and the key", () => {
  assert.deepEqual(plain(C.comboFrom(0x4d, 0x10000000)), { mods: ["SUPER"], key: "M" })
  assert.deepEqual(plain(C.comboFrom(0x21, 0x02000000)), { mods: ["SHIFT"], key: "1" })
  assert.deepEqual(plain(C.comboFrom(0x01000000, 0)), { mods: [], key: "Escape" })
})

test("a modifier alone, or an unnameable key, is not a combo", () => {
  assert.equal(C.comboFrom(0x01000022, 0x10000000), null)
  assert.equal(C.comboFrom(0x01000020, 0), null)
  assert.equal(C.comboFrom(0x7fffffff, 0), null)
})

test("enterLua is exactly the Lua the brief specifies", () => {
  assert.equal(C.enterLua(), [
    'hl.define_submap("hyprkbm-capture", function()',
    '    hl.bind("SUPER + Escape", hl.dsp.submap("reset"))',
    'end)',
    'hl.dispatch(hl.dsp.submap("hyprkbm-capture"))',
    'hl.timer(function()',
    '    if hl.get_current_submap() == "hyprkbm-capture" then',
    '        hl.dispatch(hl.dsp.submap("reset"))',
    '    end',
    'end, { timeout = 10000, type = "oneshot" })'
  ].join("\n"))
})
