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
