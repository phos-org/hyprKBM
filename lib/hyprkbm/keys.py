"""Key combos as Hyprland's Lua config writes them: "SUPER + SHIFT + F".

Two spellings of one combo must compare equal -- "WIN + f" and "SUPER + F"
are the same bind to Hyprland, and a conflict check that missed that would
wave a real conflict through. The panel has a JavaScript twin of this module;
both are tested against tests/fixtures/keys.json.
"""
from dataclasses import dataclass

# Every modifier name Hyprland accepts, mapped to the one hyprKBM writes.
MODIFIERS = {
    "SUPER": "SUPER", "WIN": "SUPER", "LOGO": "SUPER", "MOD4": "SUPER",
    "CTRL": "CTRL", "CONTROL": "CTRL",
    "ALT": "ALT", "MOD1": "ALT",
    "SHIFT": "SHIFT",
    "CAPS": "CAPS",
    "MOD2": "MOD2", "MOD3": "MOD3", "MOD5": "MOD5",
}
ORDER = ["SUPER", "CTRL", "ALT", "SHIFT", "CAPS", "MOD2", "MOD3", "MOD5"]

# Two names xkb accepts for one keysym. A bind written with either spelling
# must land on the same key, in conflict checks and on the panel's keyboard.
KEY_ALIASES = {"page_up": "prior", "page_down": "next"}


class KeyParseError(ValueError):
    pass


@dataclass(frozen=True)
class Combo:
    mods: tuple
    key: str

    @property
    def id(self):
        # Keysyms are matched case-insensitively: "f" and "F" are one key.
        key = self.key.lower()
        return "+".join(self.mods + (KEY_ALIASES.get(key, key),))

    @property
    def display(self):
        return " + ".join(self.mods + (self.key,))


def parse(keys):
    if not isinstance(keys, str):
        raise KeyParseError("keys must be text, not %s" % type(keys).__name__)
    tokens = [token for part in keys.split("+") for token in part.split()]
    if not tokens:
        raise KeyParseError("no key in %r" % keys)
    *mod_tokens, key = tokens
    mods = set()
    for token in mod_tokens:
        canonical = MODIFIERS.get(token.upper())
        if canonical is None:
            raise KeyParseError("%r is not a modifier (in %r)" % (token, keys))
        mods.add(canonical)
    return Combo(tuple(m for m in ORDER if m in mods), key)
