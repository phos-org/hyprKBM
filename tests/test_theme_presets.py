"""Tests for the theme presets and the defaults they shadow.

The panel's colours are QML, which has no test harness here. The parts that
break quietly are reachable from Python anyway: a preset is JSON, and the
defaults it overrides are literals in Colors.qml.

Three failures are worth catching before a user sees them:
  * a preset naming a token the panel never reads -- `acentPrimary` is not an
    error anywhere, it simply does nothing;
  * the shipped default palette drifting away from the one the panel was
    designed against;
  * a component still asking for a token that no longer exists, which renders
    as transparent black rather than as a failure.
"""
import glob
import json
import os
import re

import pytest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(PROJECT, "quickshell", "hyprkbm")
PRESETS = os.path.join(PANEL, "presets")
COLORS = os.path.join(PANEL, "config", "Colors.qml")

# The palette the panel shipped with, transcribed from Colors.qml as it stood
# before any of it was themeable. Hardcoded on purpose: if the defaults move,
# this file is the thing that has to argue for it.
FUJI = {
    "mode": "dark",
    "bgVoid": "#0b0c16",
    "bgBase": "#12131f",
    "bgSurface": "#1c1826",
    "bgSurfaceAlt": "#241b28",
    "textPrimary": "#f3ece2",
    "textSecondary": "#948da3",
    "textTertiary": "#5f5a6b",
    "accentPrimary": "#c2718c",
    "accentSecondary": "#d9a15c",
    "accentTertiary": "#7c9082",
    "statusCritical": "#b1495a",
}

# What `mode` alone is allowed to move. Everything else is the same colour in
# either mode unless a preset says otherwise.
#
# The three accents are in the ramp, which they were not originally. Not
# because an accent says anything about light level -- it does not -- but
# because the dark accents are mid-tones: on the light ground accentSecondary
# measures 2.0:1, and Field.qml and ActionBar.qml paint it as text. Keeping
# them out of the ramp would have made `{"mode": "light"}` on its own
# unreadable, and that is a supported way to write a theme. Light darkens
# them and keeps their hues. statusCritical stays out: it clears 3:1 in both.
RAMP = ("bgVoid", "bgBase", "bgSurface", "bgSurfaceAlt",
        "textPrimary", "textSecondary", "textTertiary",
        "accentPrimary", "accentSecondary", "accentTertiary")

# Derived from the base tier, and overridable like anything else.
DERIVED = ("borderSubtle", "borderStrong", "accentPrimaryDim", "bgGlass")

TOKENS = set(FUJI) | set(DERIVED)


def preset_paths():
    return sorted(glob.glob(os.path.join(PRESETS, "*.json")))


def preset(name):
    with open(os.path.join(PRESETS, name), encoding="utf-8") as handle:
        return json.load(handle)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


# A colour token declaration, up to the start of the next one. Tolerant of
# wrapping, but it will not run past `property` into its neighbour and
# mis-attribute a literal.
DECLARATION = re.compile(r"property color (?P<name>\w+):(?P<body>(?:(?!\bproperty\b)[\s\S])*)")
RAMP_BRANCH = re.compile(r'"light"\s*\?\s*"(#[0-9a-fA-F]{6})"\s*:\s*"(#[0-9a-fA-F]{6})"')
HEX = re.compile(r'"(#[0-9a-fA-F]{6})"')


def qml_defaults():
    """Every colour token's default in Colors.qml, as {name: (light, dark)}.

    A token whose default is a single literal reads the same in both modes.
    Tokens computed from other tokens carry no literal and are not returned.
    """
    defaults = {}
    for match in DECLARATION.finditer(read(COLORS)):
        body = match.group("body")
        branch = RAMP_BRANCH.search(body)
        if branch:
            defaults[match.group("name")] = (branch.group(1), branch.group(2))
            continue
        literals = HEX.findall(body)
        if len(literals) == 1:
            defaults[match.group("name")] = (literals[0], literals[0])
    return defaults


def qml_accepted_tokens():
    """The keys the theme file's adapter will accept, taken from Colors.qml.

    The adapter's slots are the only `property string <name>: ""` declarations
    in the file -- an unset override.
    """
    return set(re.findall(r'^\s*property string (\w+): ""\s*$', read(COLORS), re.M))


# --------------------------------------------------------------------------
# The presets parse and say only things the panel understands
# --------------------------------------------------------------------------

def test_every_preset_is_valid_json():
    paths = preset_paths()

    assert paths, "no presets found; the panel ships none for a user to copy"
    for path in paths:
        parsed = json.loads(read(path))
        assert isinstance(parsed, dict), f"{os.path.basename(path)} is not an object"


def test_every_preset_key_is_a_token_the_panel_reads():
    """A misspelled token is silent: it is simply never asked for."""
    for path in preset_paths():
        unknown = set(json.loads(read(path))) - TOKENS

        assert not unknown, f"{os.path.basename(path)} sets unknown tokens: {sorted(unknown)}"


def test_every_preset_value_is_a_hex_colour():
    """`mode` aside, a value that is not a colour falls back and confuses."""
    for path in preset_paths():
        for name, value in json.loads(read(path)).items():
            if name == "mode":
                assert value in ("dark", "light"), f"{path}: bad mode {value!r}"
                continue
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)), f"{path}: {name} = {value!r}"


def test_the_theme_file_accepts_exactly_the_documented_tokens():
    """Every token is overridable, and nothing else is offered."""
    assert qml_accepted_tokens() == TOKENS


# --------------------------------------------------------------------------
# The shipped look has not drifted
# --------------------------------------------------------------------------

def test_the_fuji_preset_is_the_palette_the_panel_shipped_with():
    assert preset("fuji.json") == FUJI


def test_the_dark_defaults_are_the_fuji_preset():
    """fuji.json documents the defaults; the defaults are what a user gets.

    Only this test connects the two: with no theme file at all the panel reads
    Colors.qml, so a drift there is invisible to a preset comparison.
    """
    defaults = qml_defaults()

    dark = {name: pair[1] for name, pair in defaults.items()}
    assert dark == {name: value for name, value in FUJI.items() if name != "mode"}


def test_the_light_defaults_are_the_paper_preset():
    """`{"mode": "light"}` on its own has to land on the same ramp paper does."""
    defaults = qml_defaults()
    paper = preset("paper.json")

    light = {name: pair[0] for name, pair in defaults.items() if name in paper}
    assert light == {name: value for name, value in paper.items() if name != "mode"}


def test_mode_moves_the_ramp_and_nothing_else():
    """Exactly the ramp answers to mode; nothing else drifts in behind it."""
    for name, (light, dark) in qml_defaults().items():
        if name in RAMP:
            assert light != dark, f"{name} does not answer to mode"
        else:
            assert light == dark, f"{name} changes with mode but is not part of the ramp"


# --------------------------------------------------------------------------
# What each preset claims to demonstrate
# --------------------------------------------------------------------------

def test_the_paper_preset_moves_only_the_mode_ramp():
    assert set(preset("paper.json")) == {"mode"} | set(RAMP)
    assert preset("paper.json")["mode"] == "light"


def test_the_iris_preset_changes_only_the_primary_accent():
    """Its whole point: borders and the dim shade follow one key."""
    assert set(preset("iris.json")) == {"accentPrimary"}


# --------------------------------------------------------------------------
# The panel only asks for tokens that exist
# --------------------------------------------------------------------------

def test_every_colors_reference_in_the_panel_resolves_to_a_token():
    """An unknown token is not an error in QML; it reads as transparent black."""
    used = set()
    for path in glob.glob(os.path.join(PANEL, "**", "*.qml"), recursive=True):
        if os.path.abspath(path) == os.path.abspath(COLORS):
            continue
        used |= set(re.findall(r"\bColors\.(\w+)", read(path)))

    assert used, "no Colors references found; the search is looking in the wrong place"
    assert used <= TOKENS, f"panel reads tokens that do not exist: {sorted(used - TOKENS)}"


# --------------------------------------------------------------------------
# Contrast: a bundled preset has to be readable, not just parse
# --------------------------------------------------------------------------

def _channel(value):
    value /= 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hexcolour):
    body = hexcolour.lstrip("#")
    red, green, blue = (int(body[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast(foreground, background):
    first, second = luminance(foreground), luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


# WCAG 2.1 puts normal text at 4.5:1 and UI components and graphical objects
# at 3:1 (1.4.11). The split below follows how the panel actually paints each
# token, not the name: accentSecondary is the validation hint in Field.qml and
# the revert countdown in ActionBar.qml, so it is read as text and owes the
# text ratio. accentPrimary, accentTertiary and statusCritical are borders,
# fills and tags.
#
# textTertiary is deliberately absent. It paints disabled and inactive
# controls, which 1.4.3 exempts as incidental -- holding it to 4.5:1 would
# force disabled text to look enabled.
AS_TEXT = ("textPrimary", "textSecondary", "accentSecondary")
AS_COMPONENT = ("accentPrimary", "accentTertiary", "statusCritical")


def resolved(preset_name):
    """A preset's effective palette: its own keys over the mode's defaults."""
    values = preset(preset_name)
    defaults = qml_defaults()
    light = values.get("mode", "dark") == "light"
    palette = {name: pair[0] if light else pair[1]
               for name, pair in defaults.items()}
    palette.update({k: v for k, v in values.items() if k != "mode"})
    return palette


@pytest.mark.parametrize("name", [os.path.basename(p) for p in preset_paths()])
def test_every_bundled_preset_is_readable_on_its_own_background(name):
    """A preset we ship is a recommendation, so it has to clear WCAG itself.

    Caught a real defect: paper's first draft inherited the dark accents, and
    accentSecondary -- which Field.qml paints as hint text -- sat at 2.0:1 on
    a light ground.
    """
    palette = resolved(name)
    background = palette["bgBase"]

    for token in AS_TEXT:
        ratio = contrast(palette[token], background)
        assert ratio >= 4.5, (
            "%s: %s is %s on %s = %.2f:1, below 4.5:1 for text"
            % (name, token, palette[token], background, ratio))

    for token in AS_COMPONENT:
        ratio = contrast(palette[token], background)
        assert ratio >= 3.0, (
            "%s: %s is %s on %s = %.2f:1, below 3:1 for a UI component"
            % (name, token, palette[token], background, ratio))


def test_every_adapter_slot_is_blanked_before_a_live_reload():
    """JsonAdapter only writes the keys a file carries, so a live edit that
    DELETES a key would keep the old value unless the slots are cleared first.
    A token added to the adapter and not to _clearOverrides would silently stop
    reverting -- the same theme.json rendering differently depending only on
    whether the panel had been restarted.
    """
    source = read(COLORS)
    slots = set(re.findall(r'property string (\w+): ""', source))
    cleared = set(re.findall(r'theme\.(\w+) = "";', source))

    assert slots, "no adapter slots found -- has Colors.qml been restructured?"
    assert slots == cleared, (
        "adapter slots not blanked before reload: %s"
        % ", ".join(sorted(slots - cleared)))


def test_tertiary_text_is_only_ever_an_inactive_state():
    """textTertiary is exempt from the contrast bar on the grounds that it
    paints disabled and inactive controls, which WCAG 1.4.3 treats as
    incidental. That exemption is only honest while the token is used that way.

    It was not, once: the empty state ("No displays reported by Hyprland."),
    the keyboard hint, the monitor description and the "n displays connected"
    subtitle all used it, at 2.78:1 in dark mode -- live content rendered as
    the least readable text in the panel. They now use textSecondary.
    """
    offenders = []
    for path in glob.glob(os.path.join(PANEL, "**", "*.qml"), recursive=True):
        for number, line in enumerate(read(path).split("\n"), 1):
            if "Colors.textTertiary" not in line:
                continue
            # A conditional means it is the inactive half of a pair.
            if "?" not in line:
                offenders.append("%s:%d" % (os.path.relpath(path, PANEL), number))

    assert not offenders, (
        "textTertiary used unconditionally -- that is live content, and it does "
        "not clear 3:1 in either mode: %s" % ", ".join(offenders))
