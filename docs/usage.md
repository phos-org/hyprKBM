# Use hyprKBM

Open the panel to see every bind, change what you want, and apply. Until you apply, Hyprland is unchanged.

## Open the panel

Run `hyprkbm`, or open **Keybinds** from your app launcher. To put that on a key, add this to `hyprland.lua`:

```lua
hl.bind("SUPER + CTRL + K", hl.dsp.exec_cmd("hyprkbm"))
```

The panel opens as a floating window, centred, 1180 by 760. hyprKBM adds that with a Hyprland window rule through `hyprctl eval`. The rule matches class `org.quickshell` and title `Keybinds`. A reload drops the rule. The next launch adds it again. The window will not shrink below 980 by 620.

Run `hyprkbm` again and the open panel is focused, instead of a second one opening.

Quickshell is required for the panel and the cheatsheet. Without `qs`, `hyprkbm` stops with `Quickshell (qs) is not installed; the panel needs it.` The other commands work without it. `hyprkbm --help` lists them.

## Read the keyboard

The keyboard lights up for the modifiers you hold, or click, in the modifier bar.

- A filled accent key is bound under these modifiers.
- A filled red key is a conflict.
- An accent key with a red outline is an overlap.
- A key with only an accent outline, and no fill, is free under these modifiers and bound under others. In the SUPER view, D is outlined when you have SUPER+SHIFT+D.

Click a key, or move to it with the arrow keys, to list every bind on it.

**Also bound as**, under that list, shows the same key under every other combination of ALT, CTRL, SHIFT, and SUPER, including none. Click one, or press Enter on it, to switch to those modifiers. The key stays selected.

## Find a key

Press F, or click **Find**. Then press any key combination, including one Hyprland has already bound. The panel selects that key under those modifiers.

Your binds pause for that one press, so the combo reaches the panel. They come back as soon as the panel has the combo, when you press Esc, when the panel loses focus, after 10 seconds, or with SUPER+Escape.

Find does nothing while a bind is open in the editor.

## Switch submap

The chips in the header are the submaps. **global** is always first. Click a chip, or step with `[` and `]`.

**+ submap** adds one. The **×** on a submap that hyprKBM created removes it, together with its binds and the binds that enter it.

In a submap hyprKBM created, the line under the modifiers shows the key that leaves it. **Change** edits that key. It has to be a real key, not a modifier on its own.

## Search

Press `/` to search. Words match a bind's keys, its description, and its action, including the action's name, so `exec` finds every bind that runs a command.

These tags narrow the list. A tag is the name, a colon, and an optional value.

| Tag | Matches |
| --- | --- |
| `mod:` | A modifier. `mod:SUPER` is SUPER. `mod:` with nothing after the colon means the bind has a modifier. |
| `key:` | The key name contains the value. An empty value matches every bind. |
| `exec:` | The command contains the value. An empty value means the bind runs a command. |
| `desc:` | The description contains the value. An empty value means the bind has a description. |
| `submap:` | The submap name contains the value. `submap:global` is the global map. An empty value matches every bind. |
| `src:` | Where the bind came from. `src:lua` and `src:hand` are your `hyprland.lua`. `src:hyprkbm` is a bind hyprKBM added. `src:override` is an override. An empty value matches every bind. |

## Deal with a conflict

Two binds on one key are a conflict when at least one of them is hyprKBM's. **Keep both** marks that conflict as deliberate. It sets `allowConflict` on the hyprKBM bind.

Until then, Apply refuses, with a message that names the keys. The Apply button stays enabled. Overlaps that are only among your `hyprland.lua` binds never block, and the panel says so. The header counts conflicts, or overlaps when none of them block.

## Deal with a stale edit

An unbind or an override whose `hyprland.lua` bind has changed or disappeared is listed under **Stale**.

**Drop my edit** deletes it, so `hyprland.lua` wins. **Keep mine** points it at the bind `hyprland.lua` now has on those keys. When none is left, an override stays as an ordinary bind.

`hyprkbm --status` prints the same stale list.

## Edit a bind

**Edit**, **Remove**, and **+ Add** change the staged `keybinds.json`. Editing one of your `hyprland.lua` binds makes an override. Removing one makes an unbind.

In the editor, **Record** takes the next key combination. Esc stops recording. On a US layout, Shift and a digit records as that digit. Qt reports the symbol, and hyprKBM maps it back to the key binds use.

Pick an action from the list, or write raw Lua. Add a description, flags, and a submap. **Save** (Ctrl+S) keeps the edit in the staged file. It does not apply it.

## Apply, review, or discard

Nothing reaches Hyprland until you apply.

**Review diff** (Ctrl+D) shows the generated `keybinds.lua` before and after, and any errors. **Discard** (Ctrl+Z) throws the staged changes away.

Ctrl+Enter applies too. It works from the keyboard view, not while you type in a field and not while a dialog is open. It applies only when there are staged changes and no bind is open in the editor. The Apply button waits for an open edit as well.

Esc cancels an open edit. With staged changes and nothing else open, the first Esc warns instead of quitting, and a second Esc within 3 seconds quits. Esc does nothing while an apply runs. Do not close the panel while it says **Applying…**. Closing it stops the helper in the middle of the apply.

Hyprland reloads when you save `hyprland.lua`. The open panel re-reads it then, and keeps any staged edits.

## Backups, export, and theme

**Backups** lists the last 30 versions, and what restoring each one would change. Restore is disabled while there are staged changes, except when `keybinds.json` is broken. In that case the panel is read-only, and restore is how you get a file it can read. A backup whose `keybinds.json` cannot be read is refused. The **×** on a backup deletes it, after asking once more.

**Export** writes the Markdown cheatsheet to a path you choose. The same text is `hyprkbm --export md`.

**Theme** offers the phos presets, an accent, and dark or light. It saves `~/.config/hyprkbm/theme.json`. The tokens are in [Theme presets](../quickshell/hyprkbm/presets/README.md).

**⋯** switches between ANSI and ISO keyboards, offers a key for the cheatsheet, names the config file being read, and shows the watcher. **Start it** runs `systemctl --user start hyprkbm-watch.service` when the watcher is not active. **Cheatsheet key**, then **Add a key**, opens a new bind whose command is `hyprkbm --cheatsheet` and whose description is "Keybind cheatsheet". Record the keys, then Save and Apply. The hint under that field says the same.

## Drive the panel from the keyboard

The panel has three areas. They are the keyboard, the bind list, and the editor. The one that has the keys shows a thick accent outline. Clicking a button does not take the keys away from that area.

| Key | Does |
| --- | --- |
| Tab / Shift+Tab | Next or previous area. In the editor, next or previous field, leaving the editor at either end. |
| Arrows | Move the selected key, or the cursor in the list. |
| Enter | Edit the bind under the cursor, or switch to an **Also bound as** row. On the keyboard, edit the key's first bind, or add one when it has none. |
| E | Edit the bind under the cursor, or the selected key's first bind. |
| A | Add a bind on the selected key. |
| [ / ] | Previous or next submap. |
| Delete | Remove the bind under the cursor, in the list. |
| F | Find a bind by pressing it. |
| / | Search. |
| Ctrl+S | Save the bind in the editor. |
| Ctrl+D | Review the diff, when something is staged. |
| Ctrl+Z | Discard the staged changes. |
| Ctrl+Enter | Apply. |
| Esc | Cancel find, then the edit. Otherwise quit. With staged changes, press it twice. |

Letters and these shortcuts do nothing while you type in a field, except Tab, Ctrl+S, and Esc.

## Show the cheatsheet

`hyprkbm --cheatsheet` draws your global binds on a full-screen keyboard over the output you are on. Run it again and it hides, so one key toggles it.

Bind that key from **⋯**, as above, or by hand:

```lua
hl.bind("SUPER + F1", hl.dsp.exec_cmd("hyprkbm --cheatsheet"))
```

Hold modifiers to see what they do. Keys light up with your descriptions, or with the action when a bind has none. Modifiers that are already held when it opens show from the next key you press or release.

Press a combo to see it in full at the top, for example SUPER + SHIFT + D, "Run a command: discord". Enter closes the cheatsheet and runs it. A bind whose action is a Lua function, or a mouse bind, cannot be run from here, and the cheatsheet says so.

Your binds are paused while it is open, so pressing a combo shows it instead of running it. They come back the moment it closes. That is Esc, a click, its own key, or Enter. SUPER+Escape closes it at any time and gives the binds back. If the cheatsheet crashes, the binds come back within 15 seconds. The pause is re-armed every 5 seconds, and the 15 seconds are counted from the last re-arm. Closing the cheatsheet returns Hyprland to the default submap.

The cheatsheet shows the global binds only. It never writes a file, and it stages nothing.

Without `qs`, the command stops with `Quickshell (qs) is not installed; the cheatsheet needs it.` and points you at `hyprkbm --export md`.

## Commands

```text
hyprkbm                       open the keyboard panel
hyprkbm --cheatsheet          show the keybind cheatsheet, or hide it if shown
hyprkbm --export md [FILE]    write a Markdown cheatsheet (stdout without FILE)
hyprkbm --apply [FILE]        apply keybinds.json, or FILE, to Hyprland
hyprkbm --status              binds, conflicts, stale edits and the watcher
hyprkbm --binds               hand-written binds: keys, submap, where, fingerprint
hyprkbm --state               everything the panel shows, as JSON
hyprkbm --backup NAME         one backup's keybinds.json and keybinds.lua, as JSON
hyprkbm --delete-backup NAME  delete one backup
hyprkbm --set-layout NAME     the panel's keyboard layout: ansi or iso
hyprkbm --version             print the version
```

`hyprkbm --help` prints the same list. `--set-layout` takes `ansi` or `iso`. Anything else is an error, and the message says so.

`hyprkbm --status` prints the config path, how many hand-written binds it read, how many hyprKBM binds and overrides and unbinds you have, the conflicts, the stale edits, and `watcher:`.

Backup names are the folder names under `~/.local/state/hyprkbm/backups/`. See [Configuration](configuration.md#backups).

The file those commands edit is described in [Keybind format](keybind-format.md).
