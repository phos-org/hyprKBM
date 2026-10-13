.pragma library

// The action catalogue's helpers, twins of lib/hyprkbm/catalogue.py for what
// the panel needs before anything is applied: turning an action into the
// dispatcher it stands for, describing it, checking its fields, and turning a
// hand-written bind's dispatcher back into something the editor can show.
// hyprkbm-apply checks everything again; these give the answer early.

var KEYWORDS = ["and", "break", "do", "else", "elseif", "end", "false", "for",
                "function", "global", "goto", "if", "in", "local", "nil", "not",
                "or", "repeat", "return", "then", "true", "until", "while"]
var IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/

function entryById(catalogue, id) {
    for (var i = 0; i < catalogue.length; i++) if (catalogue[i].id === id) return catalogue[i]
    return null
}

function entryByDsp(catalogue, dsp) {
    for (var i = 0; i < catalogue.length; i++) if (catalogue[i].dsp === dsp) return catalogue[i]
    return null
}

function isObject(v) { return v !== null && typeof v === "object" && !Array.isArray(v) }

function fieldProblem(field, value) {
    var kind = field.type
    if (kind === "string" || kind === "submap")
        return typeof value === "string" && value !== "" ? null : "must be text"
    if (kind === "workspace") {
        var ok = (typeof value === "number" && Math.floor(value) === value)
              || (typeof value === "string" && value !== "")
        return ok ? null : "must be a workspace number or name"
    }
    if (kind === "enum")
        return field.values.indexOf(value) >= 0 ? null : "must be one of " + field.values.join(", ")
    if (kind === "bool") return typeof value === "boolean" ? null : "must be true or false"
    return "has an unknown type " + kind
}

function actionErrors(action, catalogue) {
    if (!isObject(action)) return ["action must be an object"]
    if (action.kind === "raw")
        return typeof action.lua === "string" && action.lua.trim() !== "" ? [] : ["raw action needs some Lua"]
    var entry = typeof action.kind === "string" ? entryById(catalogue, action.kind) : null
    if (entry === null) return ["unknown action " + JSON.stringify(action.kind)]
    var args = action.args === undefined ? {} : action.args
    if (!isObject(args)) return ["args must be an object"]
    var fields = {}
    entry.fields.forEach(function (f) { fields[f.name] = f })
    var errors = []
    Object.keys(args).forEach(function (name) {
        if (!fields.hasOwnProperty(name)) errors.push(entry.label + " has no field " + JSON.stringify(name))
    })
    entry.fields.forEach(function (f) {
        if (!args.hasOwnProperty(f.name)) {
            if (f.required) errors.push(entry.label + " needs " + f.label.toLowerCase())
            return
        }
        var problem = fieldProblem(f, args[f.name])
        if (problem !== null) errors.push(f.label + ": " + problem)
    })
    if (entry.oneOf) {
        var count = entry.oneOf.filter(function (n) { return args.hasOwnProperty(n) }).length
        if (count !== 1) errors.push(entry.label + " needs exactly one of: " + entry.oneOf.join(", "))
    }
    return errors
}

function toDispatcher(action, catalogue) {
    if (action.kind === "raw") return { raw: action.lua }
    var entry = entryById(catalogue, action.kind)
    var args = action.args || {}
    if (entry.call === "none") return { dsp: entry.dsp, args: [] }
    if (entry.call === "positional") {
        var values = []
        for (var i = 0; i < entry.fields.length; i++) {
            if (!args.hasOwnProperty(entry.fields[i].name)) break
            values.push(args[entry.fields[i].name])
        }
        return { dsp: entry.dsp, args: values }
    }
    var table = {}
    var any = false
    entry.fields.forEach(function (f) {
        if (args.hasOwnProperty(f.name)) { table[f.name] = args[f.name]; any = true }
    })
    return { dsp: entry.dsp, args: any ? [table] : [] }
}

// Python's json.dumps(value, ensure_ascii=False): ", " and ": " separators.
function pyJson(v) {
    if (Array.isArray(v)) return "[" + v.map(pyJson).join(", ") + "]"
    if (v !== null && typeof v === "object")
        return "{" + Object.keys(v).map(function (k) {
            return JSON.stringify(k) + ": " + pyJson(v[k])
        }).join(", ") + "}"
    return JSON.stringify(v)
}

function plain(v) {
    if (v === true) return "yes"
    if (v === false) return "no"
    if (v === null || v === undefined) return "None"
    if (typeof v === "object") return pyJson(v)
    return String(v)
}

function luaString(text) {
    var out = ""
    for (var i = 0; i < text.length; i++) {
        var ch = text[i]
        var code = text.charCodeAt(i)
        if (ch === "\"") out += "\\\""
        else if (ch === "\\") out += "\\\\"
        else if (ch === "\n") out += "\\n"
        else if (ch === "\r") out += "\\r"
        else if (ch === "\t") out += "\\t"
        else if (code < 0x20 || code === 0x7f) out += "\\" + ("00" + code).slice(-3)
        else out += ch
    }
    return "\"" + out + "\""
}

function luaLiteral(value) {
    if (value === null || value === undefined) return "nil"
    if (value === true) return "true"
    if (value === false) return "false"
    if (typeof value === "number") return String(value)
    if (typeof value === "string") return luaString(value)
    if (isObject(value) && (value.__function !== undefined || value.__opaque !== undefined))
        throw new Error("not reproducible")
    if (Array.isArray(value))
        return value.length === 0 ? "{}" : "{ " + value.map(luaLiteral).join(", ") + " }"
    var keys = Object.keys(value).sort()
    if (keys.length === 0) return "{}"
    return "{ " + keys.map(function (k) {
        var name = IDENTIFIER.test(k) && KEYWORDS.indexOf(k) < 0 ? k : "[" + luaString(k) + "]"
        return name + " = " + luaLiteral(value[k])
    }).join(", ") + " }"
}

var DSP_PATH = /^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$/

function validDsp(dsp) { return typeof dsp === "string" && DSP_PATH.test(dsp) }

function dispatcherLua(d) {
    if (d.raw !== undefined) return d.raw
    if (d.dsp === undefined || !validDsp(d.dsp)) throw new Error("not reproducible")
    return "hl.dsp." + d.dsp + "(" + (d.args || []).map(luaLiteral).join(", ") + ")"
}

// Workspace text becomes a number only when the number prints back as the same
// text, so "05" and very long digit strings stay as typed.
function workspaceValue(text) {
    if (!/^-?\d+$/.test(text)) return text
    var n = parseInt(text, 10)
    return Number.isSafeInteger(n) && String(n) === text ? n : text
}

function basename(path) { return String(path).split("/").pop() }

function describeDispatcher(d, catalogue) {
    if (!d) return "Unknown action"
    if (d.raw !== undefined) return "Lua: " + d.raw.split(/\s+/).filter(function (w) { return w !== "" }).join(" ")
    if (d.__function !== undefined) return "Lua function (" + basename(d.__function) + ")"
    if (d.dsp === undefined) return "Unknown action"
    var args = d.args || []
    var entry = entryByDsp(catalogue, d.dsp)
    if (entry === null) {
        try { return dispatcherLua(d) } catch (e) { return "hl.dsp." + d.dsp + "(…)" }
    }
    if (entry.call === "table" && args.length === 1 && isObject(args[0]) && Object.keys(args[0]).length > 0) {
        var details = Object.keys(args[0]).sort().map(function (k) { return k + " " + plain(args[0][k]) })
        return entry.label + " (" + details.join(", ") + ")"
    }
    if (args.length > 0) return entry.label + ": " + args.map(plain).join(" ")
    return entry.label
}

function describeAction(action, catalogue) {
    if (actionErrors(action, catalogue).length > 0) return "Incomplete action"
    return describeDispatcher(toDispatcher(action, catalogue), catalogue)
}

function defaultArgs(entry) {
    var out = {}
    if (entry === null) return out
    entry.fields.forEach(function (f) { if (f.default !== undefined) out[f.name] = f.default })
    return out
}

// The editor shows a hand-written bind as a catalogue action when it is one,
// and as raw Lua otherwise; a Lua function cannot be shown as either.
function actionFromDispatcher(d, catalogue) {
    if (!d || d.__function !== undefined || d.__opaque !== undefined) return null
    if (d.raw !== undefined) return { kind: "raw", lua: d.raw }
    if (!validDsp(d.dsp)) return null
    var entry = entryByDsp(catalogue, d.dsp)
    var args = d.args || []
    var candidate = null
    if (entry !== null) {
        if (entry.call === "none" && args.length === 0) candidate = { kind: entry.id, args: {} }
        else if (entry.call === "positional" && args.length <= entry.fields.length) {
            var named = {}
            for (var i = 0; i < args.length; i++) named[entry.fields[i].name] = args[i]
            candidate = { kind: entry.id, args: named }
        } else if (entry.call === "table" && args.length === 0) candidate = { kind: entry.id, args: {} }
        else if (entry.call === "table" && args.length === 1 && isObject(args[0]))
            candidate = { kind: entry.id, args: JSON.parse(JSON.stringify(args[0])) }
    }
    if (candidate !== null && actionErrors(candidate, catalogue).length === 0) return candidate
    try { return { kind: "raw", lua: dispatcherLua(d) } } catch (e) { return null }
}
