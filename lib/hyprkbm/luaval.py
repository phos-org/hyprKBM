"""Python values as Lua source, for writing keybinds.lua."""
import math
import os
import re
import shutil

KEYWORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for",
            "function", "global", "goto", "if", "in", "local", "nil", "not",
            "or", "repeat", "return", "then", "true", "until", "while"}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


class NotReproducible(ValueError):
    """A value the reader could only describe -- a Lua function, or an object
    from the hl API -- and that therefore cannot be written back out."""


def string(text):
    out = []
    for ch in text:
        if ch in ESCAPES:
            out.append(ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            # Three digits always, so a digit that follows is not swallowed
            # into the escape.
            out.append("\\%03d" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def to_lua(value):
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("%r has no Lua literal" % value)
        return repr(value)
    if isinstance(value, str):
        return string(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        return "{ " + ", ".join(to_lua(v) for v in value) + " }"
    if isinstance(value, dict):
        if "__function" in value or "__opaque" in value:
            raise NotReproducible(value.get("__function") or "an hl object")
        if not value:
            return "{}"
        parts = []
        for key in sorted(value):
            if IDENTIFIER.match(key) and key not in KEYWORDS:
                name = key
            else:
                name = "[%s]" % string(key)
            parts.append("%s = %s" % (name, to_lua(value[key])))
        return "{ " + ", ".join(parts) + " }"
    raise TypeError("cannot write %s as Lua" % type(value).__name__)


def interpreter():
    """The Lua that runs the reader. Arch ships `lua`; Debian and Ubuntu ship
    versioned names, FreeBSD names without the dot."""
    override = os.environ.get("HYPRKBM_LUA")
    if override:
        return override
    for name in ("lua", "lua5.5", "lua5.4", "lua55", "lua54"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("no Lua interpreter found; install the lua package")
