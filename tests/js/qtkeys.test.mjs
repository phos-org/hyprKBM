import { test } from "node:test"
import assert from "node:assert/strict"
import { load, plain } from "./load.mjs"

const Q = load("qtkeys")

test("letters, digits and named keys become keysyms", () => {
  assert.equal(Q.keysymFromQt(0x41), "A")
  assert.equal(Q.keysymFromQt(0x30), "0")
  assert.equal(Q.keysymFromQt(0x01000004), "Return")
  assert.equal(Q.keysymFromQt(0x01000012), "left")
  assert.equal(Q.keysymFromQt(0x01000016), "Prior")
  assert.equal(Q.keysymFromQt(0x01000030), "F1")
  assert.equal(Q.keysymFromQt(0x0100003b), "F12")
  assert.equal(Q.keysymFromQt(0x20), "space")
  assert.equal(Q.keysymFromQt(0x2f), "slash")
  assert.equal(Q.keysymFromQt(0x01000072), "XF86AudioRaiseVolume")
})

test("modifier keys are not keysyms but are modifiers", () => {
  assert.equal(Q.keysymFromQt(0x01000020), null)
  assert.equal(Q.modifierFromQtKey(0x01000020), "SHIFT")
  assert.equal(Q.modifierFromQtKey(0x01000021), "CTRL")
  assert.equal(Q.modifierFromQtKey(0x01000023), "ALT")
  assert.equal(Q.modifierFromQtKey(0x01000022), "SUPER")
  assert.equal(Q.modifierFromQtKey(0x01000053), "SUPER")
  assert.equal(Q.modifierFromQtKey(0x41), "")
})

test("unknown keys are null", () => {
  assert.equal(Q.keysymFromQt(0x01ffffff), null)
})

test("modifier flags become canonical modifiers in order", () => {
  assert.deepEqual(plain(Q.modsFromQt(0x02000000 | 0x10000000)), ["SUPER", "SHIFT"])
  assert.deepEqual(plain(Q.modsFromQt(0x04000000 | 0x08000000)), ["CTRL", "ALT"])
  assert.deepEqual(plain(Q.modsFromQt(0)), [])
})

test("Shift+symbol maps to base key on US layout", () => {
  assert.equal(Q.keysymFromQt(0x21, 0x02000000), "1")
  assert.equal(Q.keysymFromQt(0x3a, 0x02000000), "semicolon")
  assert.equal(Q.keysymFromQt(0x23, 0), "numbersign")
  assert.equal(Q.keysymFromQt(0x23, 0x02000000), "3")
  assert.equal(Q.keysymFromQt(0x3c, 0), "less")
  assert.equal(Q.keysymFromQt(0x41, 0x02000000), "A")
  assert.equal(Q.keysymFromQt(0x21), null)
})

// While recording, the field shows what is held as it changes. Qt does not
// always include a modifier in the flags of its own press (or drop it from
// the flags of its own release), so the key itself is folded in.
test("held modifiers follow presses and releases of modifier keys", () => {
  const SHIFT = 0x01000020, CTRL = 0x01000021
  assert.deepEqual(plain(Q.heldMods(CTRL, 0, true)), ["CTRL"])
  assert.deepEqual(plain(Q.heldMods(SHIFT, 0x04000000, true)), ["CTRL", "SHIFT"])
  assert.deepEqual(plain(Q.heldMods(SHIFT, 0x04000000 | 0x02000000, false)), ["CTRL"])
  assert.deepEqual(plain(Q.heldMods(CTRL, 0x04000000, false)), [])
  assert.deepEqual(plain(Q.heldMods(0x41, 0x04000000, true)), ["CTRL"])
})

test("the live recording text", () => {
  assert.equal(Q.recordingText([]), "Press the keys…")
  assert.equal(Q.recordingText(["CTRL", "SHIFT"]), "CTRL + SHIFT + …")
})
