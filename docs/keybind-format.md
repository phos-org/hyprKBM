# Keybind format

hyprKBM's binds, overrides, and unbinds live in `~/.config/hyprkbm/keybinds.json`. Where that file sits, and the other files next to it, is [Configuration](configuration.md).

Edit the file, then apply it:

```bash
hyprkbm --apply
```

`hyprkbm --apply FILE` reads `FILE` instead. The running panel applies the same file when you press **Apply**. Nothing is written until an apply succeeds. See [How hyprKBM applies binds](how-it-works.md).

The first run creates this file, empty:

```json
{
  "version": 1,
  "submaps": [],
  "binds": [],
  "unbinds": []
}
```

A file you edit by hand has the same four keys. `version` has to be `1`.

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

## Fields

| Field | Meaning |
| --- | --- |
| `binds[].id` | Any unique name. Errors and `hyprkbm --status` refer to binds by it. |
| `binds[].keys` | As in `hyprland.lua`. `"SUPER + SHIFT + F"`, `"XF86AudioMute"`, `"SUPER + mouse:272"`. |
| `binds[].action` | An action from the catalogue, or raw Lua. See [Actions](#actions). |
| `binds[].submap` | Optional. A submap defined in this file or in `hyprland.lua`. The global map when left out. |
| `binds[].description` | Optional. Shown on the cheatsheet. |
| `binds[].flags` | Optional switches. Each value is `true` or `false`. See [Flags](#flags). |
| `binds[].replaces` | Makes the bind an override of one hand-written bind. See [Overrides and unbinds](#overrides-and-unbinds). |
| `binds[].allowConflict` | Optional. `true` keeps a deliberate conflict from blocking the apply. |
| `unbinds[]` | Removes one hand-written bind. Same three fields as `replaces`. |
| `submaps[]` | New submaps. `name` is the submap. `reset` is the key that leaves it. |

`reset` has to be a real key, not a modifier on its own. A modifier alone would leave you with no way out. A submap that `hyprland.lua` already defines is not defined again here. Add binds to it and leave `submaps` alone. Defining it twice is an error.

## Keys

`keys` is the same text you would pass to `hl.bind`. Modifier names are matched without regard to case. These names are the same modifier:

| You can write | hyprKBM stores |
| --- | --- |
| `SUPER`, `WIN`, `LOGO`, `MOD4` | `SUPER` |
| `CTRL`, `CONTROL` | `CTRL` |
| `ALT`, `MOD1` | `ALT` |
| `SHIFT` | `SHIFT` |
| `CAPS` | `CAPS` |
| `MOD2`, `MOD3`, `MOD5` | the same name |

The key itself is matched without regard to case, so `"f"` and `"F"` are one key. `page_up` and `prior` are one key, and so are `page_down` and `next`.

## Actions

An action from the catalogue is an id plus its arguments:

```json
{ "kind": "exec_cmd", "args": { "cmd": "firefox" } }
```

The ids and their fields are [`share/actions.json`](../share/actions.json). That list covers running a command, focus, moving windows, fullscreen, layout messages, submaps, and the rest of the catalogue.

Anything the catalogue does not have is raw Lua, the dispatcher expression included:

```json
{ "kind": "raw", "lua": "hl.dsp.window.resize({ x = 20, y = 0, relative = true })" }
```

A bind that enters a submap (the `submap` action) has to name one defined in this file or in `hyprland.lua`, or the name `reset`. Apply refuses any other name. Hyprland would switch to that submap, and no key in it would do anything.

## Flags

Each flag is an `HL.BindOptions` switch. The value is a boolean. A name outside this list is an error.

`allow_input_capture`, `click`, `dont_inhibit`, `drag`, `ignore_mods`, `locked`, `long_press`, `mouse`, `non_consuming`, `release`, `repeating`, `submap_universal`, `transparent`.

## Overrides and unbinds

An override or an unbind names the bind in `hyprland.lua` it acts on by three fields.

| Field | Meaning |
| --- | --- |
| `keys` | The combo, as `hyprkbm --binds` prints it. |
| `submap` | The submap name, or `""` for the global map. |
| `fingerprint` | What the bind does. The dispatcher, a colon, and its arguments as compact JSON. |

`hyprkbm --binds` prints every hand-written bind as four tab-separated columns. The columns are keys, submap, where, and fingerprint. The submap column is empty for a global bind, which is why the gap before the file name is wider:

```text
SUPER + F		hyprland.lua:116	exec_cmd:["dolphin"]
SUPER + 1		hyprland.lua:156	focus:[{"workspace":1}]
```

`where` is the file and line in `hyprland.lua`. It is there so you can find the bind. An override does not store it. Edits elsewhere in `hyprland.lua` do not break an override, because the override names the keys, the submap, and the fingerprint, not the line.

If the bind it names changes or disappears, `hyprkbm --status` lists the override as stale. It is then applied as an ordinary bind, which conflicts with any new bind on those keys until you drop it or keep it in the panel. See [Deal with a stale edit](usage.md#deal-with-a-stale-edit).

Overriding one bind unbinds its keys in every submap and then puts back the other binds that were on those keys. A bind whose action is a Lua function cannot be re-created, so hyprKBM refuses to override another bind on the same keys.
