# Contributing

## Running the tests

The helpers import nothing outside the Python standard library; `pytest` is
the only development dependency. The reader needs a Lua interpreter.

```bash
python3 -m pytest tests/ -q
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
| `systemd/` | the `hyprkbm-watch` user unit |
| `docs/superpowers/` | the design spec and implementation plans |

## Testing against Hyprland

`hyprkbm --status`, then `hyprkbm --apply`, then `hyprctl reload` and check
that `hyprctl binds` still lists the binds. `journalctl --user -u
hyprkbm-watch` shows what the watcher did.

## Conventions

- Commits: `<type>: <description>`, with `feat, fix, refactor, docs, test, chore, perf`.
- Comments explain *why*, not *what*.
