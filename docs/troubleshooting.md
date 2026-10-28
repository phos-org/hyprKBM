# Troubleshooting

`hyprkbm --status` is the first check. It prints the config it read, the bind counts, conflicts, stale edits, and whether the watcher is active.

## Binds vanish after a reload

The watcher is not running, or it could not load `keybinds.lua` back.

`hyprkbm --status` shows `watcher:` and then the state of `hyprkbm-watch.service`. `journalctl --user -u hyprkbm-watch` shows what the watcher did.

A reload re-runs `hyprland.lua` and drops whatever `hyprctl eval` had set. The watcher puts `keybinds.lua` back. Without it, hyprKBM's binds are gone until the next apply. Installing and starting the watcher is in [Install hyprKBM](installation.md#the-watcher).

If the unit is enabled but never starts, the session may not be passing `HYPRLAND_INSTANCE_SIGNATURE` to systemd. The unit has `ConditionEnvironment=HYPRLAND_INSTANCE_SIGNATURE`. uwsm does pass that variable. A session that does not start `graphical-session.target` should start the watcher from `hyprland.lua` instead. See [Without systemd](installation.md#without-systemd).

When the watcher connects but Hyprland refuses the load, you get a notification that starts `Your hyprKBM keybinds could not be applied:`. The rest of the text is Hyprland's own error.

## hyprland.lua could not be read

The sandbox hit an error while running your config. hyprKBM refuses to apply until it can read the file completely, because overrides and conflict checks depend on that.

The panel's banner says `hyprland.lua could not be read completely, so some binds may be missing and nothing can be applied:`, and then the error. Apply answers with `<file> could not be read, so nothing was changed:` and the same error. The message names the file and the line when Lua reported them.

`hyprkbm --status` still prints the counts it could get, and a warning on stderr that starts `hyprkbm: warning:`.

A config that loads a file from outside the directory that holds `hyprland.lua` is refused. The reader says `refusing to load` and names the path. Symlinks inside that directory are followed.

## Hyprland rejected the new keybinds

Nothing was written. Apply's message starts `Hyprland rejected the new keybinds, so nothing was changed:`. The rest is Hyprland's own error. This is the check that runs the new file inside Hyprland with binding switched off, before either file is replaced.

`Hyprland refused the new keybinds, and the previous ones were put back:` means the files were written, Hyprland then refused the real load, and the previous `keybinds.json` and `keybinds.lua` were restored and loaded again. You also get a notification.

If that restore also fails, the message starts `Hyprland refused the new keybinds, and the previous ones could not be restored either.` It includes both Hyprland's refusal and the restore error. Your newest backup is the copy taken at the start of that apply.

A misspelled key name is the usual cause of the second message. A bad dispatcher argument is the usual cause of the first.

## Go back to an earlier version

Restore it from the panel's **Backups**, or copy `keybinds.json` out of a backup over `~/.config/hyprkbm/keybinds.json` and run `hyprkbm --apply`.

Backup folders live in `~/.local/state/hyprkbm/backups/`. The newest 30 are kept. `hyprkbm --backup NAME` prints one of them. Restore stays disabled while you have staged changes, unless `keybinds.json` is broken and the panel is read-only.

## The panel does not open

`hyprkbm` with no arguments needs Quickshell 0.3 or later, on your `PATH` as `qs`. The error is `Quickshell (qs) is not installed; the panel needs it.`

If a panel is already open, a second `hyprkbm` focuses that window instead of opening another. The match is class `org.quickshell` and title `Keybinds`.

## Questions

**Does hyprKBM edit hyprland.lua?** No. Binds, overrides, and unbinds go in `keybinds.json`. The one exception is the `hl.on` hook in [Without systemd](installation.md#without-systemd), which you add yourself so the watcher can start.

**Does the command line need Quickshell?** No. `--status`, `--apply`, `--binds`, `--export`, and the backup commands are Python. The panel and the cheatsheet need `qs`.

**Where is the format of keybinds.json?** In [Keybind format](keybind-format.md). The other files are in [Configuration](configuration.md).
