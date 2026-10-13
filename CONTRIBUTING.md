# Contributing

## Running the tests

The helpers import nothing outside the Python standard library; `pytest` is
the only development dependency. The reader needs a Lua interpreter.

```bash
python3 -m pytest tests/ -q
node --test tests/js/        # or: npm test
shellcheck install.sh
```

The suite needs no compositor. It points `HOME` at a temporary directory and
puts stub `hyprctl`, `notify-send` and `systemctl` executables first on
`PATH`. Nothing in it touches your real config or your running session. Keep
it that way: a test that writes to `~/.config` will eventually be run by
someone who is using the machine.

## Layout

| Path | Holds |
|---|---|
| `lib/reader.lua` | the sandbox that runs a config against a recording `hl` |
| `lib/hyprkbm/` | the Python core: keys, model, render, apply, export, and `marker.py`, the counted lock-protected record of which reloads hyprkbm-apply made itself |
| `share/actions.json` | the action catalogue |
| `bin/` | `hyprkbm`, `hyprkbm-apply` (the only writer of keybinds files), `hyprkbm-watch` |
| `quickshell/hyprkbm/` | the panel: QML in `components/`, logic in `lib/*.js`, theme in `config/`, presets in `presets/` |
| `tests/js/` | node tests for `quickshell/hyprkbm/lib/*.js` |
| `systemd/` | the `hyprkbm-watch` user unit |
| `docs/superpowers/` | the design spec and implementation plans |

## Running the panel

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d -n
qs ipc -p quickshell/hyprkbm call hyprkbm state     # what it shows, as JSON
qs log -p quickshell/hyprkbm                         # QML warnings and errors
qs kill -p quickshell/hyprkbm
```

The IPC target can select keys, search and edit, but has no way to apply: a
scripted check must never change a real session. Logic belongs in
`quickshell/hyprkbm/lib/*.js` with a test in `tests/js/`; QML only binds and
draws.

Lint the QML. On Arch there is no `qtpaths6`:

```bash
find quickshell -name '*.qml' -print0 | xargs -0 /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml
```

Elsewhere, `qtpaths6 --query QT_INSTALL_QML` gives the import path for `-I`.

QML pitfalls this project has hit:

- Never compute a size from an item's own width when a sibling's width
  depends on that size. The panel froze from exactly that loop; the key size
  comes from the pane (see `Layouts.unitFor`).
- Import `QtQuick.Controls` as `QC` in files that use our `Action`
  component, which would otherwise clash with the built-in.
- Do not import `lib/keys.js` as `Keys` in a file with key handlers; it
  shadows the `Keys` attached property.
- `textTertiary` is for inactive states only; `tests/test_theme_presets.py`
  enforces it.

## Testing against Hyprland

`hyprkbm --status`, then `hyprkbm --apply`, then `hyprctl reload` and check
that `hyprctl binds` still lists the binds. `journalctl --user -u
hyprkbm-watch` shows what the watcher did.

## Conventions

- Commits: `<type>: <description>`, with `feat, fix, refactor, docs, test, chore, perf`.
- Comments explain *why*, not *what*.
