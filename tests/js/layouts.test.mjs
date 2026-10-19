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
  assert.equal(L.keyName(L.LAYOUTS.ansi, "q"), "Q")
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

// The key size is chosen once from the whole row's width -- keyboard, divider
// and the extra keys -- and never from the keyboard's own width. Deriving it
// from the keyboard's width made the two depend on each other (the extra keys
// are three keys wide), and at some window widths the size flipped between
// two values forever, freezing the panel.
test("unitFor sizes keys from the whole row and fits it", () => {
  assert.equal(L.unitFor(1000), 46)
  assert.equal(L.unitFor(300), 26)
  assert.equal(L.unitFor(5000), 48)
  for (let width = 26 * L.ROW_UNITS; width <= 48 * L.ROW_UNITS; width++) {
    const unit = L.unitFor(width)
    assert.ok(unit * L.ROW_UNITS <= width, `width ${width}: ${unit} keys overflow`)
    assert.equal(L.unitFor(width), unit, "same input, same answer")
  }
})

test("keyName writes letters in upper case, as binds usually are", () => {
  assert.equal(L.keyName(L.LAYOUTS.ansi, "q"), "Q")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "return"), "Return")
  assert.equal(L.keyName(L.LAYOUTS.ansi, "1"), "1")
})

test("unitFor takes a larger cap for the full-screen sheet", () => {
  assert.equal(L.unitFor(10000), 48)
  assert.equal(L.unitFor(10000, 96), 96)
  assert.equal(L.unitFor(21.5 * 70, 96), 70)
})
