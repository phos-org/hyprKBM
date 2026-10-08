.pragma library

// Physical keyboards, as rows of keys measured in key units (1 = one letter
// key). Ids are xkb keysym names, which is what hl.bind takes; the rest of
// the panel compares them in lower case, as Hyprland does.
//
// Every main row is fifteen units wide. The navigation cluster's rows line up
// with the main rows: function keys, digits, letters, home row, shift, space.

function key(id, label, w) {
    return { id: id, label: label === undefined ? id : label, w: w === undefined ? 1 : w }
}
function mod(name, label, w) { return { mod: name, label: label, w: w } }
function gap(w) { return { gap: true, w: w } }
function letters(text) {
    return text.split("").map(function (c) { return key(c, c.toUpperCase()) })
}
function fkeys(first, last) {
    var out = []
    for (var i = first; i <= last; i++) out.push(key("F" + i))
    return out
}

var FUNCTION_ROW = [key("Escape", "Esc"), gap(1)].concat(
    fkeys(1, 4), [gap(0.5)], fkeys(5, 8), [gap(0.5)], fkeys(9, 12))
var NUMBER_ROW = [key("grave", "`")].concat(
    "1234567890".split("").map(function (d) { return key(d) }),
    [key("minus", "-"), key("equal", "="), key("BackSpace", "⌫", 2)])
var SPACE_ROW = [mod("CTRL", "Ctrl", 1.25), mod("SUPER", "Super", 1.25), mod("ALT", "Alt", 1.25),
                 key("space", "Space", 6.25), mod("ALT", "Alt", 1.25), mod("SUPER", "Super", 1.25),
                 key("Menu", "Menu", 1.25), mod("CTRL", "Ctrl", 1.25)]

var NAV = [
    [key("Print", "PrtSc"), key("Scroll_Lock", "ScrLk"), key("Pause")],
    [key("Insert", "Ins"), key("Home"), key("Prior", "PgUp")],
    [key("Delete", "Del"), key("End"), key("Next", "PgDn")],
    [],
    [gap(1), key("up", "↑")],
    [key("left", "←"), key("down", "↓"), key("right", "→")]
]

var LAYOUTS = {
    ansi: {
        name: "ANSI",
        main: [
            FUNCTION_ROW,
            NUMBER_ROW,
            [key("Tab", "Tab", 1.5)].concat(letters("qwertyuiop"),
                [key("bracketleft", "["), key("bracketright", "]"), key("backslash", "\\", 1.5)]),
            [key("Caps_Lock", "Caps", 1.75)].concat(letters("asdfghjkl"),
                [key("semicolon", ";"), key("apostrophe", "'"), key("Return", "Enter", 2.25)]),
            [mod("SHIFT", "Shift", 2.25)].concat(letters("zxcvbnm"),
                [key("comma", ","), key("period", "."), key("slash", "/"), mod("SHIFT", "Shift", 2.75)]),
            SPACE_ROW
        ],
        nav: NAV
    },
    iso: {
        name: "ISO",
        main: [
            FUNCTION_ROW,
            NUMBER_ROW,
            [key("Tab", "Tab", 1.5)].concat(letters("qwertyuiop"),
                [key("bracketleft", "["), key("bracketright", "]"), key("Return", "Enter", 1.5)]),
            // The tall ISO Enter's lower half: the same key, drawn again.
            [key("Caps_Lock", "Caps", 1.75)].concat(letters("asdfghjkl"),
                [key("semicolon", ";"), key("apostrophe", "'"), key("numbersign", "#"),
                 { id: "Return", label: "", w: 1.25, cont: true }]),
            [mod("SHIFT", "Shift", 1.25), key("less", "<")].concat(letters("zxcvbnm"),
                [key("comma", ","), key("period", "."), key("slash", "/"), mod("SHIFT", "Shift", 2.75)]),
            SPACE_ROW
        ],
        nav: NAV
    }
}

function eachKey(layout, fn) {
    var blocks = [layout.main, layout.nav]
    for (var b = 0; b < blocks.length; b++)
        for (var r = 0; r < blocks[b].length; r++)
            for (var k = 0; k < blocks[b][r].length; k++) fn(blocks[b][r][k], b, r)
}

function keyIds(layout) {
    var out = {}
    eachKey(layout, function (k) { if (k.id !== undefined) out[k.id.toLowerCase()] = true })
    return out
}

function keyName(layout, lowerId) {
    var found = lowerId
    eachKey(layout, function (k) {
        if (k.id !== undefined && k.id.toLowerCase() === lowerId) found = k.id
    })
    return found
}

// Each key's row and horizontal centre, the navigation cluster sitting half a
// unit to the right of the main block.
function positions(layout) {
    var out = []
    var blocks = [{ rows: layout.main, x0: 0 }, { rows: layout.nav, x0: 15.5 }]
    for (var b = 0; b < blocks.length; b++) {
        for (var r = 0; r < blocks[b].rows.length; r++) {
            var x = blocks[b].x0
            var row = blocks[b].rows[r]
            for (var k = 0; k < row.length; k++) {
                if (row[k].id !== undefined && !row[k].cont)
                    out.push({ id: row[k].id.toLowerCase(), row: r, x: x + row[k].w / 2 })
                x += row[k].w
            }
        }
    }
    return out
}

function neighbour(layout, lowerId, dir) {
    var all = positions(layout)
    var here = null
    for (var i = 0; i < all.length; i++) if (all[i].id === lowerId) here = all[i]
    if (here === null) return "q"
    var best = null
    for (var j = 0; j < all.length; j++) {
        var p = all[j]
        var ok = dir === "left" ? (p.row === here.row && p.x < here.x)
               : dir === "right" ? (p.row === here.row && p.x > here.x)
               : dir === "up" ? p.row === here.row - 1
               : p.row === here.row + 1
        if (!ok) continue
        var distance = Math.abs(p.x - here.x)
        if (best === null || distance < best.distance) best = { id: p.id, distance: distance }
    }
    return best === null ? lowerId : best.id
}
