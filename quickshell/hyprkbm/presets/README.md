# Theme presets

The panel reads one optional file:

```
$XDG_CONFIG_HOME/hyprkbm/theme.json      # or ~/.config/hyprkbm/theme.json
```

It is not required. With no file at all the panel uses the defaults in
`../config/Colors.qml`, which are the `fuji` palette below.

Pick a preset from **Theme** in the panel's header, or by putting one at that
path yourself:

```sh
mkdir -p ~/.config/hyprkbm
cp      paper.json       ~/.config/hyprkbm/theme.json   # start from it
ln -sf "$PWD/paper.json" ~/.config/hyprkbm/theme.json   # or follow it -- but read below
```

The file is watched. Save an edit and the panel re-themes without a restart.

## The Theme popup

**Theme**, beside Identify, offers the presets below, the primary accent and
dark-or-light. It writes this same file and nothing else, through the same
watch a hand edit goes through, so there is one way the panel re-themes rather
than two that can disagree about what your theme is.

The accent has two ways in, and they are two views of one value rather than two
settings. Type a hex into the field, or press the swatch beside it to open a
picker — a saturation/value square, a hue strip, and the accents of the presets
below as one-click swatches. Dragging in the picker moves the hex as you go;
typing a hex moves the picker. Neither writes anything until the gesture ends:
a drag writes once, when you let go.

What it writes is what you would have written. Picking a preset copies that
preset's own bytes, blank lines and all. Changing the accent or the mode
rewrites the file keeping every key already in it — including the thirteen
tokens the popup does not offer, and any key it has never heard of.

And it stays minimal. The popup never adds a key you did not ask for: with no
theme file at all, picking an accent leaves you the same one line `iris.json`
is. An absent key is not missing or broken — it means "use the default", which
is what makes a one-line theme a complete one. `fuji` and `paper` are the
exception, and only because being written out in full is the point of them.

Two things worth knowing:

- **Do not symlink `theme.json` to a file you want left alone.** The panel
  replaces the file in place and that follows a symlink, so an accent changed
  in the popup lands on whatever the link points at — including `paper.json` in
  a checkout of this repository, if that is what you linked to. Copy the preset
  instead. Following a preset by symlink is still fine if you never use the
  popup.
- **`mode` only moves the tokens a theme has left alone.** `fuji` and `paper`
  name every background outright, so once you have picked one of them the Mode
  control has nothing left to move and the panel will not change. That is the
  explicit colours winning, which is the point of them; the popup says so
  rather than appearing to do nothing. Start from `iris`, or from no file at
  all, if you want `mode` to carry the whole look.

## The presets

| File | What it is |
|------|------------|
| `fuji.json` | The shipped palette, written out in full. Dark, warm, rose and amber over a blue-black. |
| `paper.json` | The light ramp, written out in full. Warm paper rather than white, with the same accents. |
| `iris.json` | One key. Nothing but a new primary accent, and the borders and pressed shades follow it. |

`iris.json` is the one to read first: a theme only has to name what it
disagrees with. Everything it does not mention keeps its default.

## Tokens

Set any of these. A value is a `#rrggbb` hex string; anything that is not a
colour is ignored and the default stands. `#aarrggbb` works too, which is the
form to use for `bgGlass` or a border, where the alpha is the point.

**Base**

| Token | Default (dark) | Default (light) |
|-------|----------------|-----------------|
| `mode` | `"dark"` | — set to `"light"` to move the ramp below |
| `bgVoid` | `#0b0c16` | `#faf7f2` |
| `bgBase` | `#12131f` | `#f4efe8` |
| `bgSurface` | `#1c1826` | `#ece4da` |
| `bgSurfaceAlt` | `#241b28` | `#e3d8cd` |
| `textPrimary` | `#f3ece2` | `#2a2430` |
| `textSecondary` | `#948da3` | `#5f5a6b` |
| `textTertiary` | `#5f5a6b` | `#8d8797` |
| `accentPrimary` | `#c2718c` | `#b04b6d` |
| `accentSecondary` | `#d9a15c` | `#966223` |
| `accentTertiary` | `#7c9082` | `#607165` |
| `statusCritical` | `#b1495a` | same |

`{"mode": "light"}` on its own is enough — it lands on exactly the ramp
`paper.json` spells out.

**Derived**

Computed from the base tier, so a one-line theme still hangs together. Set one
explicitly and the arithmetic steps aside for it.

| Token | How it is built |
|-------|-----------------|
| `borderSubtle` | `accentPrimary` at 16% alpha |
| `borderStrong` | `accentPrimary` at 35% alpha |
| `accentPrimaryDim` | `accentPrimary` darkened — the pressed state of a primary button |
| `bgGlass` | `bgBase` at 72% alpha |

## Notes

Light mode darkens the three accents and keeps their hues. An accent says
nothing about light level, so this is not where they belong in principle -- but
the dark accents are mid-tones, and on the light ramp `accentSecondary` falls
to 2.0:1 while `Field.qml` and `ActionBar.qml` both paint it as text. Leaving
them alone would have made `{"mode": "light"}` unreadable on its own, and that
is a supported way to write a theme. Darkened, all three clear 4.5:1.

`statusCritical` is the exception and does not move: it clears 3:1 against
either ground, which is the bar for something drawn as a border or a fill.

If you write your own light theme, set accents that clear 4.5:1 against your
own `bgBase`. `tests/test_theme_presets.py` enforces exactly that for every
preset shipped here, so a new one cannot land with text nobody can read.

A theme is data. There is deliberately no way to supply QML — it would run
inside the shell's own process, and a file in a config directory should not be
able to do that.
