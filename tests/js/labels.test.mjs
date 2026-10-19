import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const L = load("labels")
const b = (dispatcher, description) => ({ dispatcher, description: description || "" })

test("short labels fit on a key", () => {
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["rofi -show drun"] })), "rofi")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["/usr/bin/kitty"] })), "kitty")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["jetbrains-toolbox"] })), "jetbrai…")
  assert.equal(L.shortLabel(b({ dsp: "focus", args: [{ workspace: 3 }] })), "ws 3")
  assert.equal(L.shortLabel(b({ dsp: "window.move", args: [{ workspace: 10 }] })), "→ws 10")
  assert.equal(L.shortLabel(b({ dsp: "focus", args: [{ direction: "left" }] })), "focus")
  assert.equal(L.shortLabel(b({ dsp: "layout", args: ["togglesplit"] })), "split")
  assert.equal(L.shortLabel(b({ dsp: "submap", args: ["resize"] })), "↪resize")
  assert.equal(L.shortLabel(b({ dsp: "window.close", args: [] })), "close")
  assert.equal(L.shortLabel(b({ dsp: "window.cycle_next", args: [] })), "cycle n…")
  assert.equal(L.shortLabel(b({ __function: "h.lua:1" })), "fn")
  assert.equal(L.shortLabel(b({ raw: "hl.dsp.exit()" })), "lua")
  assert.equal(L.shortLabel(b(null)), "?")
})

test("a short description wins", () => {
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["kitty"] }, "Term")), "Term")
  assert.equal(L.shortLabel(b({ dsp: "exec_cmd", args: ["kitty"] }, "A terminal emulator")), "kitty")
})

const sb = (o) => Object.assign({ description: "", describe: "Run a command: kitty",
  dispatcher: { dsp: "exec_cmd", args: ["kitty"] } }, o)

test("the sheet shows the description, else the action", () => {
  assert.equal(L.sheetLabel([sb({ description: "Terminal" })]), "Terminal")
  assert.equal(L.sheetLabel([sb({})]), "Run a command: kitty")
  assert.equal(L.sheetLabel([sb({ describe: "" })]), "kitty")
})

test("several binds on one key show the first and a count", () => {
  assert.equal(L.sheetLabel([sb({ description: "A" }), sb({ description: "B" })]), "A (+1)")
  assert.equal(L.sheetLabel([]), "")
})
