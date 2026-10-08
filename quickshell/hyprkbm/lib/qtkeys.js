.pragma library

// Qt's key codes, as a QML Keys handler reports them, turned into the keysym
// names hl.bind takes. Numbers rather than the named enum, so that this stays
// plain JavaScript the tests can load; the values are Qt 6's Qt::Key enum.

var NAMED = {
    0x01000000: "Escape", 0x01000001: "Tab", 0x01000002: "Tab",
    0x01000003: "BackSpace", 0x01000004: "Return", 0x01000005: "KP_Enter",
    0x01000006: "Insert", 0x01000007: "Delete", 0x01000008: "Pause",
    0x01000009: "Print", 0x01000010: "Home", 0x01000011: "End",
    0x01000012: "left", 0x01000013: "up", 0x01000014: "right", 0x01000015: "down",
    0x01000016: "Prior", 0x01000017: "Next", 0x01000024: "Caps_Lock",
    0x01000026: "Scroll_Lock", 0x01000055: "Menu",
    0x20: "space", 0x2d: "minus", 0x3d: "equal", 0x5b: "bracketleft",
    0x5d: "bracketright", 0x5c: "backslash", 0x3b: "semicolon",
    0x27: "apostrophe", 0x60: "grave", 0x2c: "comma", 0x2e: "period",
    0x2f: "slash", 0x3c: "less", 0x23: "numbersign",
    0x01000070: "XF86AudioLowerVolume", 0x01000071: "XF86AudioMute",
    0x01000072: "XF86AudioRaiseVolume", 0x01000080: "XF86AudioPlay",
    0x01000081: "XF86AudioStop", 0x01000082: "XF86AudioPrev",
    0x01000083: "XF86AudioNext", 0x010000b2: "XF86MonBrightnessUp",
    0x010000b3: "XF86MonBrightnessDown"
}

// Holding these is choosing a combo, not pressing a key of one.
var MODIFIER_KEYS = {
    0x01000020: "SHIFT", 0x01000021: "CTRL", 0x01000022: "SUPER",
    0x01000023: "ALT", 0x01000053: "SUPER", 0x01000054: "SUPER"
}

// Qt::KeyboardModifier flags. Super arrives as Meta on Linux.
var FLAGS = [
    [0x10000000, "SUPER"], [0x04000000, "CTRL"], [0x08000000, "ALT"], [0x02000000, "SHIFT"]
]

function keysymFromQt(key) {
    if (MODIFIER_KEYS.hasOwnProperty(key)) return null
    if (key >= 0x41 && key <= 0x5a) return String.fromCharCode(key)
    if (key >= 0x30 && key <= 0x39) return String.fromCharCode(key)
    if (key >= 0x01000030 && key <= 0x01000047) return "F" + (key - 0x01000030 + 1)
    return NAMED.hasOwnProperty(key) ? NAMED[key] : null
}

function modifierFromQtKey(key) {
    return MODIFIER_KEYS.hasOwnProperty(key) ? MODIFIER_KEYS[key] : ""
}

function modsFromQt(modifiers) {
    var out = []
    for (var i = 0; i < FLAGS.length; i++)
        if ((modifiers & FLAGS[i][0]) !== 0) out.push(FLAGS[i][1])
    return out
}
