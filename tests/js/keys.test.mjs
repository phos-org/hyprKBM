import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { load, plain } from "./load.mjs"

const K = load("keys")
// The table keys.py is tested against: the two parsers must agree.
const TABLE = JSON.parse(readFileSync(new URL("../fixtures/keys.json", import.meta.url), "utf8"))

test("spellings of one combo share an id", () => {
  for (const [keys, expected] of TABLE.same) assert.equal(K.idOf(keys), expected, keys)
})

test("display uses canonical modifiers and the key as written", () => {
  for (const [keys, expected] of TABLE.display) {
    const c = K.parse(keys)
    assert.equal(K.display(c.mods, c.key), expected, keys)
  }
})

test("malformed combos do not parse", () => {
  for (const keys of TABLE.invalid) assert.equal(K.parse(keys), null, JSON.stringify(keys))
  assert.equal(K.parse(42), null)
})

test("comboId sorts and de-duplicates modifiers", () => {
  assert.equal(K.comboId(["SHIFT", "SUPER", "SUPER"], "Q"), "SUPER+SHIFT+q")
  assert.deepEqual(plain(K.sortMods(["shift", "win"])), ["SUPER", "SHIFT"])
  assert.equal(K.keyId("Page_Up"), "prior")
})
