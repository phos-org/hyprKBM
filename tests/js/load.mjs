// Loads one of quickshell/hyprkbm/lib/*.js the way QML does: a `.pragma
// library` script whose top-level declarations are its exports, and whose
// `.import "x.js" as X` lines bring other libraries in under a name. node can
// import neither, so each runs in a fresh context and the context is the library.
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import vm from "node:vm"

export function load(name) {
  const path = fileURLToPath(new URL(`../../quickshell/hyprkbm/lib/${name}.js`, import.meta.url))
  let source = readFileSync(path, "utf8").replace(/^\.pragma library\s*$/m, "")
  const context = vm.createContext({})
  source = source.replace(/^\.import "([\w-]+)\.js" as (\w+)\s*$/gm, (_, dep, alias) => {
    context[alias] = load(dep)
    return ""
  })
  vm.runInContext(source, context, { filename: path })
  return context
}

// Values made inside the vm context have that context's prototypes, which
// deepStrictEqual treats as different; comparing through JSON sidesteps it.
export const plain = (v) => JSON.parse(JSON.stringify(v))
