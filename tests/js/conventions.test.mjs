import { test } from "node:test"
import assert from "node:assert/strict"
import { readdirSync, readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

const LIB = fileURLToPath(new URL("../../quickshell/hyprkbm/lib/", import.meta.url))

// QML only binds and draws; these files are where the logic lives, and they
// stay testable only while they do no I/O and touch no Qt API.
test("every lib file is a pragma library with no Qt or I/O", () => {
  for (const file of readdirSync(LIB).filter(f => f.endsWith(".js"))) {
    const source = readFileSync(LIB + file, "utf8")
    assert.match(source, /^\.pragma library$/m, file)
    for (const banned of ["Qt.", "Quickshell", "Process", "FileView", "require(", "XMLHttpRequest"])
      assert.ok(!source.includes(banned), `${file} uses ${banned}`)
  }
})
