# hyprKBM documentation

hyprKBM shows the keybinds from your `hyprland.lua` and the ones it keeps itself, and applies changes without editing that file.

| | |
| --- | --- |
| [Install hyprKBM](installation.md) | Packages, the Nix flake, `install.sh`, systemd, and uninstalling. |
| [Use hyprKBM](usage.md) | The panel, the cheatsheet, and the commands. |
| [Configuration](configuration.md) | `keybinds.json`, `settings.json`, `theme.json`, and backups. |
| [Keybind format](keybind-format.md) | The fields in `keybinds.json`, actions, flags, overrides, and unbinds. |
| [How hyprKBM applies binds](how-it-works.md) | The sandbox, apply, the watcher, and conflicts. |
| [Troubleshooting](troubleshooting.md) | The watcher, a config that will not read, a refused apply, and restoring a backup. |

Related pages elsewhere in the repo:

| | |
| --- | --- |
| [Packaging](../packaging/README.md) | Which recipe is for which distro, and how each one is checked. |
| [Theme presets](../quickshell/hyprkbm/presets/README.md) | The colours `theme.json` can set. |
| [Contributing](../CONTRIBUTING.md) | Tests, packaging, and the panel's developer loop. |
| [Changelog](../CHANGELOG.md) | What changed. |

## What it does

- It reads the binds you wrote. Your `hyprland.lua` is run in a sandbox against a stand-in for `hl` that records every bind, which is what gets loops, helper functions, and `mainMod ..` right. `hyprctl binds` cannot help here. It reports every Lua bind as an opaque `__lua` reference.
- It adds, overrides, and removes binds from `~/.config/hyprkbm/keybinds.json`, and it does not edit `hyprland.lua`. The one line you add yourself is the watcher hook in [Without systemd](installation.md#without-systemd), and only when systemd cannot start the watcher.
- It keeps them applied. The `hyprkbm-watch` user service puts hyprKBM's binds back after every Hyprland reload and at login.
- It checks before it changes anything. Conflicts with your other binds are refused, every apply is tried inside Hyprland first, and if Hyprland still refuses the result, your previous binds are put back.
- It shows a cheatsheet over the screen. Hold modifiers to see what they do, press a combo to see its action, and press Enter to run it.
- It exports a cheatsheet as Markdown, grouped by submap and modifiers.

## Checking these pages

From the repository root:

```bash
python3 scripts/check-docs.py
npx markdownlint-cli2
```

The first command checks every relative link and every in-repo heading anchor in `README.md` and `docs/`. The second lints `README.md` and the pages in `docs/*.md`.
