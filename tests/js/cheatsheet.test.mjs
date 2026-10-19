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
