# hyprKBM

A keybind manager for Hyprland's Lua configuration, from the
[phos](https://phos.sh) family. hyprKBM shows every keybind you have, the
ones you wrote in `hyprland.lua` and its own, and adds, overrides or removes
binds without editing your config.

> This version is the core: reading, applying and exporting from the command
> line. The keyboard panel and the cheatsheet overlay come next.

## How it works

- **Your `hyprland.lua` is never edited**, and needs no line added to it.
  hyprKBM keeps its binds in `~/.config/hyprkbm/keybinds.json`, writes
  `keybinds.lua` from it, and applies that to the running Hyprland with
  `hyprctl eval`. `keybinds.lua` is safe to load more than once (it removes
  the binds its previous run made), so sourcing it from `hyprland.lua` is
  harmless, though unnecessary.
- **The binds always work.** A reload re-runs `hyprland.lua` and drops what
  eval set, so the `hyprkbm-watch` user service applies them again after
  every reload and at login. hyprKBM needs it, and `install.sh` enables it.
- **Hand-written binds are read by running your config** in a sandbox,
  against a stand-in for `hl` that records each bind. That is what gets
  loops, helper functions and `mainMod ..` right. The sandbox cannot run
  commands or write files, and it refuses to load files whose path lies
  outside `~/.config/hypr`. Symlinks inside that directory are followed, so
  a config directory managed by stow or chezmoi keeps working.
- **Overriding a bind from `hyprland.lua`** unbinds its keys and re-creates
  the other binds on them, because `hl.unbind` removes a key combo in every
  submap at once. A bind whose action is a Lua function cannot be
  re-created, so hyprKBM refuses to override another bind on its keys.
- **Every apply is checked first.** The new file is run inside Hyprland with
  binding switched off, so a bad dispatcher argument is caught before
  anything changes. If Hyprland still refuses it, the previous binds are put
  back. The last 30 versions are kept in `~/.local/state/hyprkbm/backups/`.

## Requirements

| | |
|---|---|
| Hyprland | with Lua configuration (`hyprland.lua`). Developed against 0.56.2. |
| Lua | 5.4 or 5.5 interpreter (`lua`); Hyprland on Arch already pulls it in. |
| Python 3 | Standard library only. Developed against 3.14; CI runs 3.12. |
| systemd | a user session that starts `graphical-session.target` (uwsm does). |

## Install

```bash
git clone https://github.com/phos-org/hyprKBM.git ~/src/hyprKBM
~/src/hyprKBM/install.sh
```

The install is symlinks back into the clone, so keep it; `git pull` is the
upgrade. An existing symlink at any of the install paths is re-pointed to
this clone (that is what makes re-installing from a moved clone work); a real
file is never touched. `install.sh --uninstall` removes the links and keeps your binds.

Without `graphical-session.target`, start the watcher from `hyprland.lua`:

```lua
hl.on("hyprland.start", function()
    hl.exec_cmd("hyprkbm-watch")
end)
```

## Using it

```bash
hyprkbm --status              # binds, conflicts, stale overrides, the watcher
hyprkbm --export md binds.md  # a Markdown cheatsheet
hyprkbm --apply               # apply ~/.config/hyprkbm/keybinds.json
```

Until the panel arrives, binds are added by editing `keybinds.json`:

```json
{
  "version": 1,
  "submaps": [],
  "binds": [
    { "id": "browser", "keys": "SUPER + B", "description": "Browser",
      "action": { "kind": "exec_cmd", "args": { "cmd": "firefox" } } },
    { "id": "files", "keys": "SUPER + F",
      "action": { "kind": "exec_cmd", "args": { "cmd": "nautilus" } },
      "replaces": { "keys": "SUPER + F", "submap": "",
                    "fingerprint": "exec_cmd:[\"dolphin\"]" } }
  ],
  "unbinds": [
    { "keys": "SUPER + P", "submap": "", "fingerprint": "window.pseudo:[]" }
  ]
}
```

Actions are listed in [`share/actions.json`](share/actions.json); anything
else can be written as `{ "kind": "raw", "lua": "hl.dsp.group.toggle()" }`.
A fingerprint is the dispatcher, a colon, and its arguments as compact JSON.

## Licence

MIT.
