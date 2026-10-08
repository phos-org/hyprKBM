import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const D = load("diff")

test("a line diff keeps, adds and removes", () => {
  const lines = plain(D.lineDiff("a\nb\nc\n", "a\nc\nd\n"))
  assert.deepEqual(lines, [
    { op: " ", text: "a" }, { op: "-", text: "b" }, { op: " ", text: "c" }, { op: "+", text: "d" }
  ])
  assert.deepEqual(plain(D.counts(lines)), { added: 1, removed: 1 })
})

test("from nothing, everything is added", () => {
  assert.deepEqual(plain(D.lineDiff("", "x\ny")), [{ op: "+", text: "x" }, { op: "+", text: "y" }])
  assert.deepEqual(plain(D.lineDiff("x", "x")), [{ op: " ", text: "x" }])
})
