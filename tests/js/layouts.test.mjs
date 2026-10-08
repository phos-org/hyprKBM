import { test } from "node:test"
import assert from "node:assert/strict"
import { load } from "./load.mjs"

const L = load("layouts")

function rowWidth(row) { return row.reduce((sum, k) => sum + k.w, 0) }

test("every main row of both layouts is fifteen units wide", () => {
  for (const name of ["ansi", "iso"]) {
    for (const row of L.LAYOUTS[name].main) assert.equal(rowWidth(row), 15, `${name}: ${JSON.stringify(row.map(k => k.id || k.mod || "gap"))}`)
  }
})

test("key ids are lower case and include the keys binds use", () => {
  const ids = L.keyIds(L.LAYOUTS.ansi)
  for (const id of ["q", "1", "0", "tab", "return", "space", "left", "prior", "print", "f12", "grave", "backspace"])
    assert.equal(ids[id], true, id)
  assert.equal(ids["super"], undefined)
  assert.equal(L.keyIds(L.LAYOUTS.iso)["less"], true)
  assert.equal(L.keyIds(L.LAYOUTS.ansi)["less"], undefined)
})

test("keyName gives back the id as the layout writes it", () => {
  assert.equal(L.keyName(L.LAYOUTS.ansi, "return"), "Return")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "q"), "q")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "xf86audiomute"), "xf86audiomute")
})

test("arrow-key navigation moves between neighbouring keys", () => {
  const a = L.LAYOUTS.ansi
  assert.equal(L.neighbour(a, "w", "left"), "q")
  assert.equal(L.neighbour(a, "q", "right"), "w")
  assert.equal(L.neighbour(a, "w", "down"), "s")
  assert.equal(L.neighbour(a, "s", "up"), "w")
  assert.equal(L.neighbour(a, "escape", "left"), "escape")
  assert.equal(L.neighbour(a, "nonsense", "left"), "q")
})
