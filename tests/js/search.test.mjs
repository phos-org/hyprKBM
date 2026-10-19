import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const S = load("search")
const bind = (o) => Object.assign({ keys: "SUPER + F", mods: ["SUPER"], key: "F", submap: "", source: "hand",
  where: "hyprland.lua:1", describe: "Run a command: firefox", description: "",
  dispatcher: { dsp: "exec_cmd", args: ["firefox"] } }, o)

test("queries split into words and known tags", () => {
  assert.deepEqual(plain(S.parseQuery("  mod:Shift exec:fire foo nope:x ")),
    { words: ["foo", "nope:x"], tags: { mod: ["shift"], exec: ["fire"] }, empty: false })
  assert.equal(S.parseQuery("   ").empty, true)
})

test("words match keys, descriptions and actions", () => {
  assert.ok(S.matches(bind({}), S.parseQuery("fire")))
  assert.ok(S.matches(bind({ description: "Browser" }), S.parseQuery("brow")))
  assert.ok(!S.matches(bind({}), S.parseQuery("kitty")))
  assert.ok(S.matches(bind({}), S.parseQuery("")))
})

test("tags narrow", () => {
  assert.ok(S.matches(bind({}), S.parseQuery("mod:win")))
  assert.ok(!S.matches(bind({}), S.parseQuery("mod:shift")))
  assert.ok(S.matches(bind({}), S.parseQuery("key:f exec:fire")))
  assert.ok(!S.matches(bind({ dispatcher: { dsp: "window.close", args: [] } }), S.parseQuery("exec:fire")))
  assert.ok(S.matches(bind({}), S.parseQuery("submap:global")))
  assert.ok(S.matches(bind({ submap: "resize" }), S.parseQuery("submap:res")))
  assert.ok(S.matches(bind({ source: "override" }), S.parseQuery("src:override")))
  assert.ok(S.matches(bind({}), S.parseQuery("src:lua")))
  assert.ok(!S.matches(bind({ source: "hyprkbm" }), S.parseQuery("src:lua")))
  assert.equal(S.filter([bind({}), bind({ key: "Q", keys: "SUPER + Q" })], S.parseQuery("key:q")).length, 1)
})

test("words match the dispatcher's name", () => {
  const close = bind({ describe: "Close the window", dispatcher: { dsp: "window.close", args: [] } })
  assert.ok(S.matches(bind({}), S.parseQuery("exec")))
  assert.ok(!S.matches(close, S.parseQuery("exec")))
  assert.ok(S.matches(close, S.parseQuery("window.close")))
  assert.ok(S.matches(bind({ dispatcher: null, describe: "Lua: foo()" }), S.parseQuery("foo")))
})

test("a tag with no value means has one", () => {
  const close = bind({ dispatcher: { dsp: "window.close", args: [] } })
  assert.deepEqual(plain(S.parseQuery("exec: foo:")), { words: ["foo:"], tags: { exec: [""] }, empty: false })
  assert.ok(S.matches(bind({}), S.parseQuery("exec:")))
  assert.ok(!S.matches(close, S.parseQuery("exec:")))
  assert.ok(S.matches(bind({}), S.parseQuery("exec:fire")))
  assert.ok(!S.matches(bind({}), S.parseQuery("exec:kit")))
  assert.ok(!S.matches(bind({}), S.parseQuery("desc:")))
  assert.ok(S.matches(bind({ description: "Browser" }), S.parseQuery("desc:")))
  assert.ok(S.matches(bind({}), S.parseQuery("mod:")))
  assert.ok(!S.matches(bind({ mods: [], keys: "F" }), S.parseQuery("mod:")))
  for (const q of ["key:", "submap:", "src:"]) assert.ok(S.matches(bind({ submap: "resize" }), S.parseQuery(q)))
})
