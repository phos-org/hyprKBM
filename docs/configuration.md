# Configuration

hyprKBM reads your `hyprland.lua` and one directory of its own. It never edits `hyprland.lua`, and it never asks you to add a line to it. The exception is the one `hl.on` hook in [Without systemd](installation.md#without-systemd), and only when systemd cannot start the watcher.

`$XDG_CONFIG_HOME` and `$XDG_STATE_HOME` are honoured. The paths below are the defaults when those variables are unset. `$XDG_RUNTIME_DIR` holds the watcher's lock and the record of reloads hyprKBM itself triggered. When it is unset, that directory is `/run/user/<uid>/hyprkbm`.

## Files

| Path | What |
| --- | --- |
| `~/.config/hypr/hyprland.lua` | The config hyprKBM reads, unless `settings.json` names another file. |
| `~/.config/hyprkbm/keybinds.json` | hyprKBM's binds, overrides, and unbinds. Yours to edit. The format is [Keybind format](keybind-format.md). |
| `~/.config/hyprkbm/keybinds.lua` | Generated from `keybinds.json`. Overwritten on every apply. Do not edit it. |
| `~/.config/hyprkbm/settings.json` | Optional. Which config file to read, and the panel's keyboard layout. |
| `~/.config/hyprkbm/theme.json` | Optional. The panel's colours, written by **Theme**. |
| `~/.local/state/hyprkbm/backups/` | The last 30 versions of `keybinds.json` and `keybinds.lua`. |

The first time `hyprkbm` runs, it creates `~/.config/hyprkbm/` and an empty `keybinds.json` when that file is absent. A package never does this, because a package does not write into your home. An existing file, including a symlink, is left alone.

`keybinds.json` may be a symlink into your dotfiles. hyprKBM writes through the link and leaves the link in place.

## settings.json

Both keys are optional. A missing file, or a file that is not valid JSON, does not stop hyprKBM from opening. `--set-layout` is the command that refuses a broken `settings.json`, and it leaves the file alone.

```json
{
  "entry": "~/dots/hypr/main.lua",
  "layout": "iso"
}
```

| Key | Meaning |
| --- | --- |
| `entry` | The config to read, instead of `~/.config/hypr/hyprland.lua`. A path that starts with `~/` is expanded from your home directory. |
| `layout` | The on-screen keyboard. `ansi` or `iso`. Anything other than `iso` is shown as ANSI. `hyprkbm --set-layout` accepts only those two names. |

`hyprkbm --set-layout` rewrites `settings.json` and keeps every other key already in the file.

The panel's **⋯** menu shows the config file being read, and it is where you switch between the ANSI and ISO keyboards.

## theme.json

**Theme** in the panel writes this file. With no file at all, the panel uses the defaults in `quickshell/hyprkbm/config/Colors.qml`, which are the `fuji` palette.

The presets, the tokens, and the rule about symlinks are in [Theme presets](../quickshell/hyprkbm/presets/README.md). The short version of that rule is to copy a preset instead of symlinking `theme.json` at a file you want left alone. The panel replaces the file in place, and that follows a symlink.

## Backups

Every apply copies the current `keybinds.json` and `keybinds.lua`, whichever of the two exists, into a new folder under `~/.local/state/hyprkbm/backups/`. The folder name is the time of the apply, `YYYYMMDDTHHMMSS` plus microseconds. The newest 30 folders are kept.

`hyprkbm --backup NAME` prints that folder's `keybinds.json` and `keybinds.lua` as JSON. `hyprkbm --delete-backup NAME` deletes one folder. `NAME` is the folder name, not a path. A name that is not that timestamp shape is refused.

The panel's **Backups** list is the same folders. Restore is covered in [Use hyprKBM](usage.md#backups-export-and-theme).
