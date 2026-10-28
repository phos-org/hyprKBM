# How hyprKBM applies binds

hyprKBM reads the binds you wrote, keeps its own binds beside them, and loads the result into the running Hyprland. Your `hyprland.lua` is not edited.

## Reading hyprland.lua

Your config is run in a sandbox, against a stand-in for `hl` that records every bind. Running it, rather than parsing it, is what gets loops, helper functions, and `mainMod ..` right. `hyprctl binds` cannot help here. It reports every Lua bind as an opaque `__lua` reference.

The sandbox has no `io`, and no `os` beyond reading the clock and environment variables. Files load only from the directory that holds `hyprland.lua`. Symlinks inside that directory are followed, so a config managed by stow or chezmoi works. `hl.on` callbacks are never run. Anything that asks about live state, such as `hl.get_monitors()`, gets an empty answer, so config that branches on it takes its "nothing there" path.

The reader is `lib/reader.lua`. The list of live queries that return an empty table is in that file.

## Applying

`keybinds.lua` is generated from `keybinds.json` and loaded into the running Hyprland with `hyprctl eval`. An apply reloads Hyprland first, so the new binds always go onto what `hyprland.lua` alone produces.

Before anything is written, the new file is run inside Hyprland with binding switched off. That catches a bad dispatcher argument. A mistake only the real bind can see, such as a misspelled key name, makes Hyprland refuse the load. The previous files are then put back and loaded again, and you get a notification.

Two applies at once share one lock, so a panel apply and a `hyprkbm --apply` cannot interleave their backups and their writes.

## The watcher

A reload re-runs `hyprland.lua` and drops whatever `hyprctl eval` set. `hyprkbm-watch` listens on Hyprland's event socket and loads `keybinds.lua` again after every reload that was not hyprKBM's own, and whenever the watcher connects or reconnects.

`keybinds.lua` removes its own previous binds before adding them, so loading it twice never doubles a bind. You do not source it from `hyprland.lua`.

The user unit is `systemd/hyprkbm-watch.service`. It starts with `graphical-session.target`, and only when `HYPRLAND_INSTANCE_SIGNATURE` is set. Installing it is covered in [Install hyprKBM](installation.md#the-watcher).

## Overriding a bind

`hl.unbind` removes a key combo in every submap at once. Overriding one bind unbinds its keys and re-creates the other binds on them. A bind whose action is a Lua function cannot be re-created, so hyprKBM refuses to override another bind on the same keys.

## Conflicts

Two binds on one key are a conflict when at least one of them is hyprKBM's. Apply refuses, and the message names the keys. `allowConflict: true` on the hyprKBM bind keeps that conflict on purpose.

Overlaps among only your `hyprland.lua` binds never block an apply. Refusing every apply until those were sorted out would not help.

## Backups

Every apply first copies the current files into `~/.local/state/hyprkbm/backups/<time>/`. The newest 30 are kept. The folder name and the commands that read or delete one are in [Configuration](configuration.md#backups).
