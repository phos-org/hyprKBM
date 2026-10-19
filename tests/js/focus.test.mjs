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

test("walk steps through the editor's controls and leaves at either end", () => {
  assert.equal(F.walk(0, 4, false), 1)
  assert.equal(F.walk(2, 4, false), 3)
  assert.equal(F.walk(3, 4, false), -1)
  assert.equal(F.walk(3, 4, true), 2)
  assert.equal(F.walk(0, 4, true), -1)
})

test("walk from outside the controls enters at the near end", () => {
  // Focus was somewhere the walk does not know (say a flag): Tab goes to the
  // first control, Shift+Tab to the last.
  assert.equal(F.walk(-1, 3, false), 0)
  assert.equal(F.walk(-1, 3, true), 2)
  assert.equal(F.walk(-1, 0, false), -1)
  assert.equal(F.walk(0, 0, true), -1)
})
