# hyprKBM

<p>
  <a href="https://github.com/phos-org/hyprKBM/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/phos-org/hyprKBM/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/phos-org/hyprKBM/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/phos-org/hyprKBM?include_prereleases&sort=semver"></a>
  <a href="https://phos.sh"><img alt="A phos project" src="https://img.shields.io/badge/phos-project-eac400"></a>
  <img alt="Hyprland" src="https://img.shields.io/badge/Hyprland-58E1FF?logo=hyprland&logoColor=000">
  <img alt="Python standard library only" src="https://img.shields.io/badge/Python-stdlib%20only-3776AB?logo=python&logoColor=fff">
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-lightgrey"></a>
</p>

**hyprKBM** is a keybind manager for Hyprland's Lua configuration, from the
[phos](https://phos.sh) family. It shows every keybind you have, the ones
you wrote in `hyprland.lua` and its own, and adds, overrides or removes
binds without ever editing your config.

The **keyboard panel** shows every bind on an on-screen keyboard, and the
**cheatsheet** puts the same keyboard over your screen at a keypress.

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
- **Shows a cheatsheet** over the screen: hold modifiers to see what they
  do, press a combo to see its action, Enter to run it.
- **Exports a cheatsheet** as Markdown, grouped by submap and modifiers.

## Requirements

| | |
|---|---|
| Hyprland | 0.55 or later, with Lua configuration (`hyprland.lua`). Tested on 0.56.2. |
| Lua | a 5.4 or 5.5 interpreter, found as `lua`, `lua5.5`, `lua5.4`, `lua55` or `lua54`: `lua` on Arch (Hyprland already pulls it in), `lua5.4` on Debian and Ubuntu, `lua54` on FreeBSD. |
| Python 3 | standard library only. Developed against 3.14; CI runs 3.12. |
| Quickshell | optional: 0.3 or later, for the panel and the cheatsheet (the `qs` command). The command line works without it. |
| systemd | optional: a user session that starts `graphical-session.target` ([uwsm](https://github.com/Vladimir-csp/uwsm) does) runs the watcher as a service. Without it, see [Without systemd](#without-systemd). |

## Install

| Distro | |
|---|---|
| Arch, Manjaro, Artix, Parabola | `yay -S hyprkbm` (AUR), or the `.pkg.tar.zst` from the [release](https://github.com/phos-org/hyprKBM/releases) |
| Debian 14 / sid / 13 backports, Ubuntu 26.10, Kali, Devuan | the `.deb` from the release: `sudo apt install ./hyprkbm_*_all.deb` |
| openSUSE Tumbleweed, Mageia, OpenMandriva, Rosa | the `.rpm` from the release: `sudo zypper in ./hyprkbm-*.noarch.rpm` (or `dnf`/`urpmi`). Built and tested on openSUSE Tumbleweed; Mageia, OpenMandriva and Rosa are untested |
| NixOS, Nix | `nix profile install github:phos-org/hyprKBM` ([below](#nix)) |
| Guix, FreeBSD, Solus, aerynOS | recipes in [`packaging/`](packaging/) |
| anything else | `sudo make install PREFIX=/usr` from the release tarball (GNU make; add `SYSTEMD=0` without systemd) |

Distros whose Hyprland predates the Lua config (Fedora, Alpine, Ubuntu
26.04 LTS, ALT Linux) are not packaged yet.

If you installed from a clone with `install.sh`, run `install.sh
--uninstall` before installing a package. Otherwise the clone's links in
`~/.local/bin` and its unit in `~/.config/systemd/user` come first, and
shadow the package's.

The watcher keeps your binds applied across reloads and must run. The
Debian and RPM packages enable it for every user, which takes effect at your
next login; to start it now:

```bash
systemctl --user start hyprkbm-watch
```

Elsewhere (Arch, `make install`), enable and start it once:

```bash
systemctl --user enable --now hyprkbm-watch
```

### Nix

Nix needs flakes enabled: add `--extra-experimental-features 'nix-command
flakes'` to each command, or set `experimental-features = nix-command
flakes` in `nix.conf`. `github:phos-org/hyprKBM` follows `main`; to pin
this release, use `github:phos-org/hyprKBM/v0.1.0`.

`nix profile install` puts the unit in `~/.nix-profile/lib/systemd/user`,
where systemd does not look, so link it first:

```bash
systemctl --user link ~/.nix-profile/lib/systemd/user/hyprkbm-watch.service
systemctl --user enable --now hyprkbm-watch
```

On NixOS, take the package from the flake's `packages.${system}.hyprkbm`
and let NixOS install the unit. With this flake as the input `hyprkbm`:

```nix
{ inputs, pkgs, ... }:
let hyprkbm = inputs.hyprkbm.packages.${pkgs.stdenv.hostPlatform.system}.hyprkbm; in {
  environment.systemPackages = [ hyprkbm ];
  systemd.packages = [ hyprkbm ];
  systemd.user.services.hyprkbm-watch.wantedBy = [ "graphical-session.target" ];
}
```

Guix on another distro is the same: link the unit from your profile with
`systemctl --user link ~/.guix-profile/lib/systemd/user/hyprkbm-watch.service`,
then enable it. Without systemd, start the watcher from `hyprland.lua`
([below](#without-systemd)).

### From a clone

For development, or to follow `main`:

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
or there is no systemd at all (FreeBSD, or `make install SYSTEMD=0`),
start the watcher from `hyprland.lua` instead:

```lua
hl.on("hyprland.start", function()
    hl.exec_cmd("hyprkbm-watch")
end)
```

### Uninstall

A package comes off with the package manager that put it there
(`sudo pacman -R hyprkbm`, `sudo apt remove hyprkbm`, `sudo zypper rm
hyprkbm`, `nix profile remove hyprkbm`, …), and a `make install` with
`sudo make uninstall` and the same `PREFIX`. Run `systemctl --user disable
--now hyprkbm-watch` first where you enabled it yourself. A clone install
comes off with:

```bash
~/src/hyprKBM/install.sh --uninstall
```

This disables the watcher and removes the links. Either way, your
`keybinds.json`, the generated `keybinds.lua` and the backups are kept; the
binds stay active until the next Hyprland reload.

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
  (or click): accent for bound, filled red for a conflict, and an accent key
  with a red outline for an overlap (see below). A key with only an accent
  outline and no fill is free under these modifiers but bound under others:
  in the SUPER view, D is outlined if you have SUPER+SHIFT+D. Click a key, or
  move with the arrow keys, to see every bind on it below.
- **Also bound as.** Under the selected key's binds, the list shows its binds
  under every other combination of ALT, CTRL, SHIFT and SUPER, or none. Click
  one (or press Enter on it) to switch to those modifiers with the key still
  selected.
- **Find (F).** Press F (or click **Find**), then press any key combination,
  even one Hyprland has bound: the panel selects that key under those
  modifiers. To let a bound combination through, your binds pause for that
  one press. They come back as soon as the panel has it, on Esc, when the
  panel loses focus, after 10 seconds at most, or with SUPER+Escape.
- **Submaps** are the chips in the header: click one, or step through them
  with `[` and `]`; **global** is always the first. **+ submap** adds one,
  and the **×** on a submap hyprKBM made removes it, with its binds and the
  binds that enter it. In a submap hyprKBM made, the line under the
  modifiers shows the key that leaves it, and **Change** edits it (a real
  key, not a modifier alone).
- **Search** (`/`) narrows to binds matching plain words or the tags
  `mod:`, `key:`, `exec:`, `desc:`, `submap:` and `src:` (`src:lua` is your `hyprland.lua`). Words also match
  the action's name, so `exec` finds every bind that runs a command. A tag
  with nothing after the colon means "has one": `exec:` runs a command,
  `desc:` has a description, `mod:` has a modifier.
- **Conflicts.** Two binds on one key are a *conflict* when at least one is
  hyprKBM's. The bind list's **Keep both** marks that conflict as deliberate
  (it sets `allowConflict` on the hyprKBM bind). Until then Apply refuses with
  a message naming the keys; the button itself stays enabled. Overlaps among
  only your `hyprland.lua` binds are *overlaps*: they never block, and the
  panel says so. The header counts conflicts, or overlaps when none block.
- **Stale edits.** An unbind or override whose `hyprland.lua` bind has
  changed or disappeared is listed under *Stale* in the bind list.
  **Drop my edit** deletes it, so `hyprland.lua` wins. **Keep mine** moves
  it onto the bind `hyprland.lua` now has on those keys; with none left, an
  override stays as an ordinary bind.
- **Edit, Remove, + Add.** Editing one of your `hyprland.lua` binds makes an
  override; removing one makes an unbind. In the editor, **⏺ Record** takes
  the next key combination (Esc stops recording; Shift+digit records as the
  digit). Pick an action from the list or write raw Lua, add a description,
  flags and a submap.
- **Nothing changes until Apply.** **Review diff** shows the generated
  `keybinds.lua` before and after, and any errors. **Discard** throws the
  staged changes away. Ctrl+Enter applies too, but only from the keyboard
  view: not while you type in a field or have a dialog open, and only when
  there are staged changes and no bind is open in the editor. The Apply button
  waits for an open edit too. **Esc** cancels an open edit; with staged
  changes it warns instead of quitting, and quits only if pressed again
  within 3 seconds; it does nothing while an apply runs. Do not close the
  panel while it says "Applying…": closing it stops the helper mid-apply.
- **Backups** lists the last 30 versions with what restoring each would
  change. Restore is disabled while there are staged changes, except that it
  is the way out when `keybinds.json` is broken (the panel is then read-only),
  and a backup whose `keybinds.json` cannot be read is refused. The **×** on
  a backup deletes it, after asking once more. **Export**
  writes the Markdown cheatsheet to a path you choose. **Theme** offers the
  phos presets, an accent and dark or light, saved in
  `~/.config/hyprkbm/theme.json`. **⋯** switches between ANSI and ISO
  keyboards, offers a key for the cheatsheet, names the config file being
  read, and shows the watcher's state with a button to start it.
- **Follows `hyprland.lua`.** Hyprland reloads when you save it, and the
  open panel re-reads it then, keeping any staged edits.

### Keys

The panel can be driven without the mouse. It has three areas, the keyboard,
the bind list and the editor, and the one with the keys has a thick accent
outline. Clicking a button does not take the keys away from them.

| Key | Does |
|---|---|
| Tab / Shift+Tab | next / previous area; in the editor, next / previous field, leaving it at either end |
| Arrows | move the selected key (keyboard) or the cursor (list) |
| Enter | edit the bind under the cursor, or switch to an *Also bound as* row; on the keyboard, edit the key's first bind or add one |
| E | edit the bind under the cursor, or the selected key's first bind |
| A | add a bind on the selected key |
| [ / ] | previous / next submap |
| Delete | remove the bind under the cursor (list) |
| F | find a bind by pressing it |
| / | search |
| Ctrl+S | save the bind in the editor |
| Ctrl+D | review the diff |
| Ctrl+Z | discard the staged changes |
| Ctrl+Enter | apply |
| Esc | cancel find, then the edit; otherwise quit (twice with staged changes) |

Letters and shortcuts do nothing while you type in a field, except Tab,
Ctrl+S and Esc.

## The cheatsheet

`hyprkbm --cheatsheet` shows your binds on a full-screen keyboard over the
output you are on, and running it again hides it, so one key toggles it. Bind
that key from the panel's **⋯** menu (**Cheatsheet key → Add a key**), or by
hand:

```lua
hl.bind("SUPER + F1", hl.dsp.exec_cmd("hyprkbm --cheatsheet"))
```

- **Hold modifiers** to see what they do: keys light up with your
  descriptions, or the action when a bind has none. Modifiers already held
  when it opens show from the next key you press or release.
- **Press a combo** to see it in full at the top, e.g. SUPER + SHIFT + D:
  "Run a command: discord". **Enter** closes the cheatsheet and runs it. A
  bind whose action is a Lua function, or a mouse bind, cannot be run from
  here, and the cheatsheet says so.
- **Your binds are paused while it is open**, so pressing a combo shows it
  instead of running it. They come back the moment it closes (Esc, a click,
  its own key, Enter), with **SUPER+Escape** at any time (which also closes
  it), and within 15 seconds on their own if the cheatsheet crashes. Closing
  it returns Hyprland to the default submap.
- It shows the global binds, never changes anything on disk, and stages
  nothing.

## Using it

```bash
hyprkbm                       # open the keyboard panel
hyprkbm --cheatsheet          # show the keybind cheatsheet, or hide it if shown
hyprkbm --export md [FILE]    # write a Markdown cheatsheet (stdout without FILE)
hyprkbm --apply [FILE]        # apply keybinds.json, or FILE, to Hyprland
hyprkbm --status              # binds, conflicts, stale edits and the watcher
hyprkbm --binds               # hand-written binds: keys, submap, where, fingerprint
hyprkbm --state               # everything the panel shows, as JSON
hyprkbm --backup NAME         # one backup's keybinds.json and keybinds.lua, as JSON
hyprkbm --delete-backup NAME  # delete one backup
hyprkbm --set-layout NAME     # the panel's keyboard layout: ansi or iso
hyprkbm --version             # print the version
```

`hyprkbm --help` prints the same list. Backup names are the folder names
under `~/.local/state/hyprkbm/backups/`.

### keybinds.json

hyprKBM's binds, overrides and unbinds live in
`~/.config/hyprkbm/keybinds.json`. It may be a symlink into your dotfiles;
hyprKBM writes through the link and leaves it in place. hyprKBM creates it,
empty, the first time it runs (a package cannot: it never writes into
anyone's home). Edit it, then run
`hyprkbm --apply`:

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
| `binds[].flags` | Optional `HL.BindOptions` switches: `repeating`, `locked`, `release`, `long_press`, `non_consuming`, `transparent`, `ignore_mods`, `dont_inhibit`, `submap_universal`, `click`, `drag`, `mouse` and `allow_input_capture`. |
| `binds[].replaces` | Makes the bind an **override** of one of your hand-written binds. |
| `binds[].allowConflict` | Optional. `true` keeps a deliberate conflict from blocking the apply. |
| `unbinds[]` | Removes one of your hand-written binds. |
| `submaps[]` | New submaps, each with the key that leaves it (`reset`). That key must be a real key, not a modifier alone, or nothing would get you out. Binds can be added to submaps from `hyprland.lua` without defining them again. |

**Overrides and unbinds** name the bind in `hyprland.lua` they act on by
its keys, submap and **fingerprint**: what the bind does, as the dispatcher,
a colon and its arguments as compact JSON. `hyprkbm --binds` prints all
three for every bind you wrote:

```
SUPER + F		hyprland.lua:116	exec_cmd:["dolphin"]
SUPER + 1		hyprland.lua:156	focus:[{"workspace":1}]
```

A bind that enters a submap (the `submap` action) must name one defined
here or in `hyprland.lua`, or `reset`; apply refuses any other, because
Hyprland would switch to it and no key in it would do anything.

Line numbers are only for you; edits elsewhere in `hyprland.lua` never
break an override. If the bind it names changes or disappears,
`hyprkbm --status` lists the override as **stale**; it is then applied as an
ordinary bind, which conflicts with any new bind on those keys until you
drop or keep it in the panel.

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
| `~/.config/hyprkbm/settings.json` | Optional. `{"entry": "~/dots/hypr/main.lua"}` reads a config that is not `~/.config/hypr/hyprland.lua`; `layout` is the panel's keyboard, `ansi` or `iso`. |
| `~/.config/hyprkbm/theme.json` | Optional. The panel's theme, written by **Theme**; see [`presets/`](quickshell/hyprkbm/presets/README.md). |
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
- **Going back to an earlier version.** Restore it from the panel's
  **Backups**, or copy `keybinds.json` from a backup over
  `~/.config/hyprkbm/keybinds.json` and run `hyprkbm --apply`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The suites run without a compositor
and never touch your real config: `python3 -m pytest tests/ -q` and
`npm test`. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Licence

MIT. See [LICENSE](LICENSE).
