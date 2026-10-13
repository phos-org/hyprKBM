# hyprKBM

<p>
  <a href="https://github.com/phos-org/hyprKBM/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/phos-org/hyprKBM/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://phos.sh"><img alt="A phos project" src="https://img.shields.io/badge/phos-project-eac400"></a>
  <img alt="Hyprland" src="https://img.shields.io/badge/Hyprland-58E1FF?logo=hyprland&logoColor=000">
  <img alt="Python standard library only" src="https://img.shields.io/badge/Python-stdlib%20only-3776AB?logo=python&logoColor=fff">
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-lightgrey"></a>
</p>

**hyprKBM** is a keybind manager for Hyprland's Lua configuration, from the
[phos](https://phos.sh) family. It shows every keybind you have, the ones
you wrote in `hyprland.lua` and its own, and adds, overrides or removes
binds without ever editing your config.

The **keyboard panel** shows every bind on an on-screen keyboard; the
cheatsheet overlay comes next.

## What it does

- **Reads the binds you wrote.** Your `hyprland.lua` is run in a sandbox
  against a stand-in for `hl` that records every bind, which is what gets
  loops, helper functions and `mainMod ..` right. `hyprctl binds` cannot
  help here: it reports every Lua bind as an opaque `__lua` reference.
- **Adds, overrides and removes binds** from
  `~/.config/hyprkbm/keybinds.json`, and never edits `hyprland.lua` or asks
  you to add a line to it.
- **Keeps them applied.** The `hyprkbm-watch` user service puts hyprKBM's
  binds back after every Hyprland reload and at login.
- **Checks before it changes anything.** Conflicts with your other binds
  are refused, every apply is tried inside Hyprland first, and if Hyprland
  still refuses the result, your previous binds are put back.
- **Exports a cheatsheet** as Markdown, grouped by submap and modifiers.

## Requirements

| | |
|---|---|
| Hyprland | with Lua configuration (`hyprland.lua`). Developed against 0.56.2. |
| Lua | a 5.4 or 5.5 interpreter: `lua` on Arch (Hyprland already pulls it in), `lua5.4` on Debian and Ubuntu. |
| Python 3 | standard library only. Developed against 3.14; CI runs 3.12. |
| Quickshell | 0.3 or later, for the panel (the `qs` command). The command line works without it. |
| systemd | a user session that starts `graphical-session.target` ([uwsm](https://github.com/Vladimir-csp/uwsm) does). See [Without systemd](#without-systemd) otherwise. |

## Install

```bash
git clone https://github.com/phos-org/hyprKBM.git ~/src/hyprKBM
~/src/hyprKBM/install.sh
```

`install.sh` links `hyprkbm`, `hyprkbm-apply` and `hyprkbm-watch` into
`~/.local/bin` and the `hyprkbm-watch` unit into `~/.config/systemd/user`,
then enables and starts the unit. It is safe to run again.

- The install is **symlinks back into the clone**, so keep the clone;
  `git pull` is the upgrade. Whatever branch the clone has checked out is
  what runs.
- An existing **symlink** at any of those paths is re-pointed to this clone
  (that is what makes re-installing from a moved clone work); a real file is
  never touched, and the install fails instead.
- `~/.local/bin` must be on your `PATH` to run `hyprkbm` yourself; the
  installer warns if it is not.

Check it with:

```bash
hyprkbm --status
```

### Without systemd

If `systemctl --user is-active graphical-session.target` says `inactive`,
start the watcher from `hyprland.lua` instead:

```lua
hl.on("hyprland.start", function()
    hl.exec_cmd("hyprkbm-watch")
end)
```

### Uninstall

```bash
~/src/hyprKBM/install.sh --uninstall
```

This disables the watcher and removes the links. Your `keybinds.json`, the
generated `keybinds.lua` and the backups are kept; the binds stay active
until the next Hyprland reload.

## The panel

Run `hyprkbm`, or open **Keybinds** from your app launcher. Bind it to a key
if you like:

```lua
hl.bind("SUPER + CTRL + K", hl.dsp.exec_cmd("hyprkbm"))
```

It opens as a floating window, centred, 1180x760. That comes from a window
rule `hyprkbm` adds to the running Hyprland with `hyprctl eval`; the rule
goes at the next reload and comes back at the next launch. Running `hyprkbm`
again focuses the open panel instead of opening a second one.

- **The keyboard** is lit by what each key does under the modifiers you hold
  (or click): accent for bound, red for a conflict. Click a key, or move with
  the arrow keys, to see every bind on it below.
- **Submaps** are the chips in the header; **search** (`/`) narrows to binds
  matching plain words or the tags `mod:`, `key:`, `exec:`, `desc:`,
  `submap:` and `src:` (`src:lua` is your `hyprland.lua`).
- **Conflicts.** Two binds on one key are a *conflict* when at least one is
  hyprKBM's, and that blocks Apply until you resolve it (or set `allowConflict`
  in `keybinds.json`). Overlaps among only your `hyprland.lua` binds are
  shown as *overlaps*; they never block, and the panel says so.
- **Edit, Remove, + Add.** Editing one of your `hyprland.lua` binds makes an
  override; removing one makes an unbind. In the editor, **⏺ Record** takes
  the next key combination (Esc stops recording; Shift+digit records as the
  digit). Pick an action from the list or write raw Lua, add a description,
  flags and a submap.
- **Nothing changes until Apply.** **Review diff** shows the generated
  `keybinds.lua` before and after, and any errors. **Discard** throws the
  staged changes away. Ctrl+Enter applies too, but only from the keyboard
  view: not while you type in a field or have a dialog open, and only when
  there are staged changes and no bind is open in the editor.
- **Backups** lists the last 30 versions with what restoring each would
  change; Restore is disabled while there are staged changes. **Export**
  writes the Markdown cheatsheet to a path you choose. **Theme** offers the
  phos presets, an accent and dark or light, saved in
  `~/.config/hyprkbm/theme.json`. **⋯** switches between ANSI and ISO
  keyboards, names the config file being read, and shows the watcher's state
  with a button to start it.

## Using it

```bash
hyprkbm                      # open the panel
hyprkbm --status              # binds, conflicts, stale overrides, the watcher
hyprkbm --binds               # your hand-written binds, with fingerprints
hyprkbm --apply               # apply ~/.config/hyprkbm/keybinds.json
hyprkbm --export md binds.md  # a Markdown cheatsheet (stdout without a file)
```

### keybinds.json

hyprKBM's binds, overrides and unbinds live in
`~/.config/hyprkbm/keybinds.json`. Edit it, then run `hyprkbm --apply`:

```json
{
  "version": 1,
  "submaps": [
    { "name": "resize", "reset": "escape" }
  ],
  "binds": [
    { "id": "browser", "keys": "SUPER + B", "description": "Browser",
      "action": { "kind": "exec_cmd", "args": { "cmd": "firefox" } } },

    { "id": "files", "keys": "SUPER + F", "description": "Files",
      "action": { "kind": "exec_cmd", "args": { "cmd": "nautilus" } },
      "replaces": { "keys": "SUPER + F", "submap": "",
                    "fingerprint": "exec_cmd:[\"dolphin\"]" } },

    { "id": "grow", "keys": "right", "submap": "resize",
      "action": { "kind": "raw", "lua": "hl.dsp.window.resize({ x = 20, y = 0, relative = true })" },
      "flags": { "repeating": true } }
  ],
  "unbinds": [
    { "keys": "SUPER + P", "submap": "", "fingerprint": "window.pseudo:[]" }
  ]
}
```

| Field | Meaning |
|---|---|
| `binds[].id` | Any unique name. Errors and `--status` refer to binds by it. |
| `binds[].keys` | As in `hyprland.lua`: `"SUPER + SHIFT + F"`, `"XF86AudioMute"`, `"SUPER + mouse:272"`. `WIN`, `MOD4`, `CONTROL` and lower case are all understood. |
| `binds[].action` | `{ "kind": <id>, "args": {…} }` for an action from [`share/actions.json`](share/actions.json) (running a command, focus, moving windows, fullscreen, layout messages, submaps and more), or `{ "kind": "raw", "lua": "<dispatcher>" }` for anything else. |
| `binds[].submap` | Optional. A submap defined here or in `hyprland.lua`; the global map when left out. |
| `binds[].description` | Optional. Shown in the cheatsheet. |
| `binds[].flags` | Optional `HL.BindOptions` switches: `repeating`, `locked`, `release`, `long_press`, `non_consuming`, `transparent`, `ignore_mods` and the rest. |
| `binds[].replaces` | Makes the bind an **override** of one of your hand-written binds. |
| `binds[].allowConflict` | Optional. `true` keeps a deliberate conflict from blocking the apply. |
| `unbinds[]` | Removes one of your hand-written binds. |
| `submaps[]` | New submaps, each with the key that leaves it. Binds can be added to submaps from `hyprland.lua` without defining them again. |

**Overrides and unbinds** name the bind in `hyprland.lua` they act on by
its keys, submap and **fingerprint**: what the bind does, as the dispatcher,
a colon and its arguments as compact JSON. `hyprkbm --binds` prints all
three for every bind you wrote:

```
SUPER + F		hyprland.lua:116	exec_cmd:["dolphin"]
SUPER + 1		hyprland.lua:156	focus:[{"workspace":1}]
```

Line numbers are only for you; edits elsewhere in `hyprland.lua` never
break an override. If the bind it names disappears, `hyprkbm --status`
lists the override as **stale**; it is then applied as an ordinary bind.

## How it works

- **Applying.** `keybinds.lua` is generated from `keybinds.json` and loaded
  into the running Hyprland with `hyprctl eval`. An apply reloads Hyprland
  first, so the new binds always go onto what `hyprland.lua` alone
  produces.
- **The watcher.** A reload re-runs `hyprland.lua` and drops whatever eval
  set, so `hyprkbm-watch` listens on Hyprland's event socket and loads
  `keybinds.lua` again after every reload that was not hyprKBM's own, and
  whenever it (re)connects. `keybinds.lua` removes its own previous binds
  before adding them, so loading it twice never doubles a bind. You do not
  need to source it from `hyprland.lua`.
- **Overriding a bind.** `hl.unbind` removes a key combo in every submap at
  once, so overriding one bind unbinds its keys and re-creates the other
  binds on them. A bind whose action is a Lua function cannot be
  re-created, so hyprKBM refuses to override another bind on the same keys.
- **Checking first.** Before anything is written, the new file is run
  inside Hyprland with binding switched off, which catches a bad dispatcher
  argument. A mistake only the real bind can see, such as a misspelled key
  name, makes Hyprland refuse the load; the previous files are then put
  back and loaded again, and you get a notification.
- **Backups.** Every apply first copies the current `keybinds.json` and
  `keybinds.lua` to `~/.local/state/hyprkbm/backups/<time>/`; the newest 30
  are kept.
- **The sandbox.** Your config runs with no `io`, no `os` beyond reading
  the clock and environment variables, and no loading of files outside the
  directory that holds `hyprland.lua` (symlinks inside it are followed, so
  a config managed by stow or chezmoi works). `hl.on` callbacks are never
  run, and anything that asks about live state, such as `hl.get_monitors()`,
  gets an empty answer, so config that branches on it takes its "nothing
  there" path.

## Files

| Path | What |
|---|---|
| `~/.config/hyprkbm/keybinds.json` | hyprKBM's binds. Yours to edit. |
| `~/.config/hyprkbm/keybinds.lua` | Generated from it. Overwritten on every apply. |
| `~/.config/hyprkbm/settings.json` | Optional. `{"entry": "~/dots/hypr/main.lua"}` reads a config that is not `~/.config/hypr/hyprland.lua`. |
| `~/.local/state/hyprkbm/backups/` | The last 30 versions of the two files above. |

`$XDG_CONFIG_HOME` and `$XDG_STATE_HOME` are honoured.

## Troubleshooting

- **Binds vanish after a reload.** The watcher is not running:
  `hyprkbm --status` shows `watcher:`, and
  `journalctl --user -u hyprkbm-watch` shows what it did. If the unit is
  enabled but never starts, your session may not pass
  `HYPRLAND_INSTANCE_SIGNATURE` to systemd; uwsm does.
- **`hyprland.lua could not be read`.** The sandbox hit an error running your
  config, and hyprKBM refuses to apply until it can read it completely,
  because overrides and conflict checks depend on that. The message names
  the file and line.
- **`Hyprland rejected the new keybinds`** or **`refused the new keybinds`.**
  Nothing changed, or the previous binds were put back; the rest of the
  message is Hyprland's own error.
- **Going back to an earlier version.** Copy `keybinds.json` from a backup
  over `~/.config/hyprkbm/keybinds.json` and run `hyprkbm --apply`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The suite runs without a compositor
and never touches your real config: `python3 -m pytest tests/ -q`.

## Licence

MIT. See [LICENSE](LICENSE).
