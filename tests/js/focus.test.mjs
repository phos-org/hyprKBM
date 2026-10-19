import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const F = load("focus")

test("areas cycle keyboard, list, editor", () => {
  assert.deepEqual(plain(F.AREAS), ["keyboard", "list", "editor"])
  assert.equal(F.next("keyboard", true), "list")
  assert.equal(F.next("list", true), "editor")
  assert.equal(F.next("editor", true), "keyboard")
})

test("next skips the editor when there is no draft", () => {
  assert.equal(F.next("list", false), "keyboard")
  assert.equal(F.next("keyboard", false), "list")
  assert.equal(F.next("editor", false), "keyboard")
})

test("prev goes backwards and skips the editor", () => {
  assert.equal(F.prev("keyboard", true), "editor")
  assert.equal(F.prev("keyboard", false), "list")
  assert.equal(F.prev("list", true), "keyboard")
  assert.equal(F.prev("editor", true), "list")
  assert.equal(F.prev("editor", false), "list")
})

test("an unknown area starts from the keyboard", () => {
  assert.equal(F.next("nope", true), "list")
})

test("clampIndex keeps the index in range and is -1 when empty", () => {
  assert.equal(F.clampIndex(0, 0), -1)
  assert.equal(F.clampIndex(5, 0), -1)
  assert.equal(F.clampIndex(-3, 4), 0)
  assert.equal(F.clampIndex(9, 4), 3)
  assert.equal(F.clampIndex(2, 4), 2)
})
