import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const Q = load("quit")
const idle = { busy: false, draft: false, dirty: false }

test("Esc is ignored while an apply runs, even with edits open", () => {
  assert.equal(Q.escape({ busy: true, draft: true, dirty: true }, 0, 100).action, "ignore")
})

test("Esc cancels an open edit before anything else", () => {
  assert.equal(Q.escape({ busy: false, draft: true, dirty: true }, 0, 100).action, "cancel")
})

test("Esc quits when nothing is staged", () => {
  assert.equal(Q.escape(idle, 0, 100).action, "quit")
})

test("with staged changes the first Esc warns and arms; a second within 3s quits", () => {
  const dirty = { busy: false, draft: false, dirty: true }
  const first = plain(Q.escape(dirty, 0, 10000))
  assert.equal(first.action, "warn")
  assert.equal(first.armedAt, 10000)
  assert.equal(Q.escape(dirty, 10000, 12999).action, "quit")
  const late = plain(Q.escape(dirty, 10000, 13001))
  assert.equal(late.action, "warn")
  assert.equal(late.armedAt, 13001)
})
