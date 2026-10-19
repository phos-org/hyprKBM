import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const C = load("cheatsheet")
const exec = (cmd, o) => Object.assign({ keys: "SUPER + F1", submap: "", combo: "x",
  dispatcher: { dsp: "exec_cmd", args: [cmd] } }, o)

test("the bind that runs the cheatsheet is recognised", () => {
  assert.equal(C.COMMAND, "hyprkbm --cheatsheet")
  assert.ok(C.isCheatsheetBind(exec("hyprkbm --cheatsheet")))
  assert.ok(C.isCheatsheetBind(exec("/home/u/.local/bin/hyprkbm  --cheatsheet")))
  assert.ok(!C.isCheatsheetBind(exec("hyprkbm")))
  assert.ok(!C.isCheatsheetBind(exec("hyprkbm --cheatsheets")))
  assert.ok(!C.isCheatsheetBind(exec("myhyprkbm --cheatsheet")))
  assert.ok(!C.isCheatsheetBind({ keys: "SUPER + F1", submap: "", dispatcher: null }))
})

test("keysOf lists global binds only", () => {
  assert.deepEqual(C.keysOf([exec("hyprkbm --cheatsheet"), exec("kitty", { keys: "SUPER + Q" }),
    exec("hyprkbm --cheatsheet", { keys: "SUPER + F2", submap: "resize" })]), ["SUPER + F1"])
})

test("outputFor picks the focused output by name, else the first", () => {
  const screens = [{ name: "DP-1" }, { name: "HDMI-A-1" }]
  assert.equal(C.outputFor(screens, "HDMI-A-1").name, "HDMI-A-1")
  assert.equal(C.outputFor(screens, "gone").name, "DP-1")
  assert.equal(C.outputFor(screens, "").name, "DP-1")
  assert.equal(C.outputFor([], "DP-1"), null)
})

test("the title names the held modifiers in order", () => {
  assert.equal(C.title([]), "Keybinds · no modifier")
  assert.equal(C.title(["SHIFT", "SUPER"]), "Keybinds · SUPER + SHIFT")
})

// While the sheet is open Hyprland is held in its own submap, so a pressed
// combo reaches the sheet instead of running.
test("enterLua enters the submap unless already in it, and arms a timer for this token", () => {
  assert.equal(C.SUBMAP, "hyprkbm-cheatsheet")
  assert.equal(C.ARM_EVERY_MS, 5000)
  assert.equal(C.HOLD_MS, 15000)
  const lua = C.enterLua(1760000000123)
  // A hold that lands after the sheet already left does nothing at all.
  assert.ok(lua.startsWith("if 1760000000123 > (__hyprkbm_sheet_closed or 0) then\n"), lua)
  assert.ok(lua.endsWith("\nend"), lua)
  const guard = lua.indexOf('if hl.get_current_submap() ~= "hyprkbm-cheatsheet" then')
  const define = lua.indexOf('hl.define_submap("hyprkbm-cheatsheet", function()')
  const enter = lua.indexOf('hl.dispatch(hl.dsp.submap("hyprkbm-cheatsheet"))')
  const token = lua.indexOf("__hyprkbm_sheet = 1760000000123\n")
  const timer = lua.indexOf("hl.timer(function()")
  assert.ok(guard > 0 && guard < define && define < enter && enter < token && token < timer, lua)
  assert.ok(lua.includes('hl.bind("SUPER + Escape", hl.dsp.submap("reset"))'))
  // The only bind in the submap: nothing else would run.
  assert.equal(lua.split("hl.bind(").length, 2)
  assert.match(lua.slice(enter, token), /\bend\n\s*$/)
  const fire = lua.slice(timer)
  assert.ok(fire.includes('if __hyprkbm_sheet == 1760000000123 and hl.get_current_submap() == "hyprkbm-cheatsheet" then'))
  assert.ok(fire.includes('hl.dispatch(hl.dsp.submap("reset"))'))
  assert.ok(fire.includes('{ timeout = 15000, type = "oneshot" })'))
})

// SUPER + Escape, or the dead-man timer, ends the hold for good: a re-arm
// must never put the user back in.
test("rearmLua fails, touching nothing, when the user has left the submap", () => {
  const lua = C.rearmLua(1760000000456)
  assert.ok(lua.startsWith('if hl.get_current_submap() ~= "hyprkbm-cheatsheet" then\n'
    + '    error("hyprkbm-cheatsheet: no longer held")\nend\n'), lua)
  assert.ok(!lua.includes("define_submap") && !lua.includes("hl.bind("))
  assert.ok(!lua.includes('hl.dsp.submap("hyprkbm-cheatsheet")'))
  // After the check: a new token, and a timer that resets for it only.
  const body = lua.slice(lua.indexOf("\nend\n"))
  assert.ok(body.indexOf("__hyprkbm_sheet = 1760000000456\n") < body.indexOf("hl.timer(function()"))
  assert.ok(body.includes('if __hyprkbm_sheet == 1760000000456 and hl.get_current_submap() == "hyprkbm-cheatsheet" then'))
  assert.ok(body.includes('{ timeout = 15000, type = "oneshot" })'))
})

test("enterLua and rearmLua take integer tokens only", () => {
  for (const f of [C.enterLua, C.rearmLua, C.leaveLua, (t) => C.runLua([], t)]) {
    assert.throws(() => f("1; os.exit()"))
    assert.throws(() => f(1.5))
  }
})

test("leaveLua forgets the token, closes every older hold, and resets only from the sheet's submap", () => {
  assert.equal(C.leaveLua(1760000000999), "__hyprkbm_sheet = nil\n"
    + "__hyprkbm_sheet_closed = 1760000000999\n"
    + 'if hl.get_current_submap() == "hyprkbm-cheatsheet" then hl.dispatch(hl.dsp.submap("reset")) end')
})

const bind = (dispatcher, o) => Object.assign({ keys: "SUPER + D", submap: "", combo: "x",
  source: "hand", flags: {}, dispatcher }, o)

test("runnable says why a bind cannot be run from the sheet", () => {
  assert.equal(C.runnable(bind({ dsp: "exec_cmd", args: ["discord"] })), "")
  assert.equal(C.runnable(bind({ raw: 'hl.dsp.exec_cmd("x")' })), "")
  assert.equal(C.runnable(bind({ __function: "/x/hyprland.lua:12" })), "a Lua function")
  assert.equal(C.runnable(bind({ args: [] })), "a Lua function")
  assert.equal(C.runnable(bind(null)), "not readable")
  assert.equal(C.runnable(bind({ dsp: "exec_cmd", args: ["x"] }, { opts: { mouse: true } })), "a mouse bind")
  assert.equal(C.runnable(bind({ dsp: "exec_cmd", args: ["x"] }, { hand: { opts: { mouse: true } } })), "a mouse bind")
  assert.equal(C.runnable(bind({ dsp: "exec_cmd", args: ["x"] }, { source: "hyprkbm", flags: { mouse: true } })), "a mouse bind")
  assert.equal(C.runnable(bind({ dsp: "no such(thing" })), "not readable")
})

test("runLua leaves first, then dispatches every runnable bind in order", () => {
  const lua = C.runLua([
    bind({ dsp: "exec_cmd", args: ["discord"] }),
    bind({ __function: "f" }),
    bind({ raw: 'hl.dsp.exec_cmd("b") -- note' }),
  ], 42)
  assert.equal(lua, C.leaveLua(42) + "\n"
    + 'hl.dispatch(hl.dsp.exec_cmd("discord"))\n'
    + 'hl.dispatch((\nhl.dsp.exec_cmd("b") -- note\n))')
})

test("runLua is null when nothing can run", () => {
  assert.equal(C.runLua([], 42), null)
  assert.equal(C.runLua([bind({ __function: "f" }), bind(null)], 42), null)
})

test("opensSheet finds the cheatsheet's own bind", () => {
  assert.ok(C.opensSheet([bind({ dsp: "exec_cmd", args: ["kitty"] }), exec("hyprkbm --cheatsheet")]))
  assert.ok(!C.opensSheet([bind({ dsp: "exec_cmd", args: ["kitty"] })]))
  assert.ok(!C.opensSheet([]))
})

test("actions lists each bind's full action, then its description", () => {
  assert.equal(C.actions([
    bind({ dsp: "exec_cmd", args: ["discord"] }, { describe: "Run a command: discord", description: "Chat" }),
    bind({ dsp: "exec_cmd", args: ["x"] }, { describe: "Run a command: x", description: "" }),
  ]), "Run a command: discord  ·  Chat\nRun a command: x")
  assert.equal(C.actions([]), "")
})

test("status says whether Enter runs the combo", () => {
  assert.equal(C.status([]), "Not bound")
  assert.equal(C.status([bind({ dsp: "exec_cmd", args: ["discord"] })]), "Enter runs it")
  assert.equal(C.status([bind({ __function: "f" }), bind({ dsp: "exec_cmd", args: ["x"] })]), "Enter runs it")
  assert.equal(C.status([bind({ __function: "f" }), bind({ __function: "g" }), bind(null)]),
    "Can't run from here: a Lua function, not readable")
})
