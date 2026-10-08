.pragma library

// Key combos as Hyprland's Lua config writes them: "SUPER + SHIFT + F".
// The twin of lib/hyprkbm/keys.py. Both are tested against
// tests/fixtures/keys.json, so what the panel calls one key is what
// hyprkbm-apply calls one key.

var MODIFIERS = {
    SUPER: "SUPER", WIN: "SUPER", LOGO: "SUPER", MOD4: "SUPER",
    CTRL: "CTRL", CONTROL: "CTRL",
    ALT: "ALT", MOD1: "ALT",
    SHIFT: "SHIFT",
    CAPS: "CAPS",
    MOD2: "MOD2", MOD3: "MOD3", MOD5: "MOD5"
}
var ORDER = ["SUPER", "CTRL", "ALT", "SHIFT", "CAPS", "MOD2", "MOD3", "MOD5"]
// Two names xkb accepts for one keysym.
var KEY_ALIASES = { page_up: "prior", page_down: "next" }

function sortMods(mods) {
    var seen = {}
    for (var i = 0; i < mods.length; i++) {
        var canonical = MODIFIERS[String(mods[i]).toUpperCase()]
        if (canonical !== undefined) seen[canonical] = true
    }
    return ORDER.filter(function (m) { return seen[m] === true })
}

function parse(keys) {
    if (typeof keys !== "string") return null
    var tokens = []
    var parts = keys.split("+")
    for (var i = 0; i < parts.length; i++) {
        var words = parts[i].split(/\s+/)
        for (var j = 0; j < words.length; j++)
            if (words[j] !== "") tokens.push(words[j])
    }
    if (tokens.length === 0) return null
    var key = tokens.pop()
    for (var k = 0; k < tokens.length; k++)
        if (MODIFIERS[tokens[k].toUpperCase()] === undefined) return null
    return { mods: sortMods(tokens), key: key }
}

function keyId(key) {
    var lower = String(key).toLowerCase()
    return KEY_ALIASES.hasOwnProperty(lower) ? KEY_ALIASES[lower] : lower
}

function comboId(mods, key) {
    return sortMods(mods).concat([keyId(key)]).join("+")
}

function idOf(keys) {
    var c = parse(keys)
    return c === null ? null : comboId(c.mods, c.key)
}

function display(mods, key) {
    return sortMods(mods).concat([key]).join(" + ")
}
