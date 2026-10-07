# hyprKBM: design

A keybind manager for Hyprland's Lua configuration, in the phos family
(Quickshell panel, stdlib-only Python helpers, a watched theme file). Inspired
by [hyprKCS](https://github.com/kosa12/hyprKCS), which targets `hyprland.conf`;
hyprKBM targets `hyprland.lua` and has a keyboard-first interface.

Developed against Hyprland 0.56.2, Quickshell 0.3.1, Lua 5.4/5.5.

## Goals

- See every keybind (hand-written and hyprKBM's own) on an on-screen keyboard.
- Add, edit, delete and override binds without hand-editing Lua.
- Never rewrite `hyprland.lua`; never require a line to be added to it.
- Binds always work: applied at login and after every reload, by a service.
- Look and theme like the other phos projects.

## Non-goals for v1

Tracked as GitHub issues instead: a list view and a palette view
(`--view list|palette`), gesture configuration, input-device settings,
variable refactoring, bulk find-and-replace, and editing `hyprland.lua` in
place.

## Constraints discovered

Measured on Hyprland 0.56.2:

- `hyprctl binds -j` reports every Lua bind as `dispatcher: "__lua"` with an
  opaque `arg`. The live compositor tells which keys are bound, never what
  they do, so actions must come from the Lua source.
- `hl.unbind(combo)` removes **every** bind on that combo, in **every**
  submap. It cannot target one bind among several.
- `hl.define_submap(name, reset, fn)` on an existing submap **appends** to it.
- `hyprctl eval` applies Lua to the running compositor and emits no
  `configreloaded`; `hyprctl reload` re-runs `hyprland.lua` and drops
  everything eval set.

## Architecture

| Path | Language | Job |
|---|---|---|
| `bin/hyprkbm` | Python | Entry point. No args: open the panel. `--cheatsheet`, `--export md [FILE]`, `--apply`, `--status`. |
| `bin/hyprkbm-apply` | Python | The only writer of `keybinds.json` / `keybinds.lua`. Validate, back up, render, write, apply, roll back. |
| `bin/hyprkbm-watch` | Python | Long-running watcher (systemd user service). Re-applies on login and on `configreloaded`. |
| `lib/reader.lua` | Lua | Sandbox harness: runs the user's config against a recording `hl` and prints JSON. |
| `quickshell/hyprkbm/` | QML | The keyboard view and the cheatsheet overlay. QML only binds and draws. |
| `quickshell/hyprkbm/lib/*.js` | JS | All panel logic as `.pragma library`, no I/O: merge, normalisation, conflicts, search, labels. |
| `share/actions.json` | data | Action picker catalogue. |
| `share/layouts/*.json` | data | Physical keyboard layouts (ANSI, ISO). |
| `systemd/hyprkbm-watch.service` | unit | Starts the watcher with `graphical-session.target`. |
| `install.sh` | sh | Symlinks into `$HOME`, enables the service; `--uninstall`. Idempotent. |

Python helpers use the standard library only. The `lua` interpreter is a
dependency (Hyprland already pulls in the `lua` package on Arch).

### Files at runtime

| Path | Owner |
|---|---|
| `~/.config/hyprkbm/keybinds.json` | Source of truth for hyprKBM's binds, overrides, unbinds, submaps. |
| `~/.config/hyprkbm/keybinds.lua` | Rendered from the JSON. Generated; header says not to edit. |
| `~/.config/hyprkbm/theme.json` | Optional theme, same contract as hypr-displays. |
| `~/.config/hyprkbm/settings.json` | Keyboard layout, config entry path. |
| `~/.local/state/hyprkbm/backups/<timestamp>/` | Last 30 copies of the JSON and Lua. |

### Data flow

```
hyprland.lua ──lua reader.lua──▶ hand binds (JSON) ─┐
                                                    ├─▶ panel merges, stages edits
keybinds.json ──────────────────────────────────────┘          │ Apply
                                                               ▼
                                             hyprkbm-apply: validate → backup →
                                             render keybinds.lua → write → reload+eval
                                                               ▲
                              hyprkbm-watch: on login / configreloaded ─┘ (eval only)
```

hyprKBM never parses its own Lua back; it renders from JSON.

## Reading hand-written binds

`lua lib/reader.lua <entry>` runs the user's config (default
`~/.config/hypr/hyprland.lua`) inside a sandbox:

- `hl` is a recorder. `hl.bind(keys, dispatcher, opts)` records keys, the
  dispatcher, options, the current submap and `file:line` from
  `debug.getinfo`. `hl.define_submap` records the submap and runs its function
  with the current submap set. `hl.unbind` records an unbind.
- `hl.dsp.*` (including nested namespaces like `hl.dsp.window.move`) return
  descriptor tables `{ dsp = "window.move", args = {...} }` instead of
  dispatchers.
- A dispatcher that is a Lua function is recorded as
  `{ kind = "function", where = "file:line" }`; such binds are read-only.
- Every other `hl.*` call is a no-op; `hl.get_*` return `nil` or `{}`;
  `hl.on` callbacks are recorded and never run; `hl.config` and friends are
  ignored.
- The environment has no `io`, `package`, `debug` or `loadfile`; `os` is
  limited to `getenv`, `time`, `date` and `clock` (configs commonly build
  paths from `os.getenv("HOME")`). `dofile` and `require` load only files
  under the config directory, and skip hyprKBM's own `keybinds.lua` so a
  config that sources it does not read hyprKBM's binds back as hand-written.
- The run has a 2 second timeout (enforced by the Python caller).
- Output is JSON on stdout: `{ binds, submaps, unbinds, error }`. On a Lua
  error, binds recorded before it are kept and `error` carries the message
  and line.

Known limit: config that branches on live state (`if hl.get_monitor(...)`)
takes its "nothing there" path.

## Data model

`keybinds.json`:

```json
{
  "version": 1,
  "submaps": [{ "name": "resize", "reset": "escape" }],
  "binds": [{
    "id": "b7f3",
    "keys": "SUPER + F",
    "submap": "",
    "action": { "kind": "exec_cmd", "args": { "cmd": "nautilus" } },
    "description": "File manager",
    "flags": { "repeating": false, "locked": false, "release": false,
               "long_press": false, "non_consuming": false,
               "transparent": false, "ignore_mods": false, "mouse": false },
    "replaces": { "keys": "SUPER + F", "submap": "", "fingerprint": "exec_cmd:[\"dolphin\"]" }
  }],
  "unbinds": [{ "keys": "SUPER + P", "submap": "", "fingerprint": "window.pseudo:[]" }]
}
```

- `action.kind` is a catalogue id or `"raw"` with `"lua": "<expression>"`.
- `flags` mirror `HL.BindOptions`; only `true` flags are rendered.
- Optional `"allowConflict": true` marks a deliberate conflict (set by the
  "keep both" choice); it is excluded from the conflict count.
- `replaces` is present on an override and identifies the hand-written bind
  it supersedes. `unbinds` deletes hand-written binds.
- A **fingerprint** is the dispatcher path, a colon, and its arguments as
  compact JSON with sorted keys: `focus:[{"workspace":3}]`. A function
  dispatcher's is `function:<file>:<line>`. Hand
  binds are matched by `keys + submap + fingerprint`, never by line number,
  so overrides survive edits elsewhere in `hyprland.lua`.
- `submap: ""` is the global map.

### Key normalisation

Before comparing, a combo is normalised: modifiers mapped to canonical names
(`WIN`/`MOD4`/`LOGO` → `SUPER`, `CONTROL` → `CTRL`, `ALT`/`MOD1`), upper-cased,
de-duplicated, sorted, whitespace collapsed; keysyms compared
case-insensitively; `mouse:272` etc. kept as is. Normalisation lives in
`lib/keys.js` and a Python twin in `hyprkbm-apply`, both tested against the
same fixture table.

## Rendering keybinds.lua

Order:

1. Header comment: generated by hyprKBM, edit with the panel.
2. `hl.define_submap(name, reset, function() end)` for each hyprKBM submap.
3. For each **touched combo** (a combo with any override or unbind):
   `hl.unbind(combo)` once, then re-emit every hand-written bind on that
   combo (in any submap) that is not overridden or unbound, then the
   overrides. Binds in a submap are emitted inside
   `hl.define_submap(name, reset, function() ... end)`, which appends.
4. Plain hyprKBM binds, grouped by submap.

If an untouched hand-written bind on a touched combo has a function
dispatcher, it cannot be re-emitted. The editor refuses the override or
delete and says why, and `hyprkbm-apply` rejects such a model too.

A **stale** override or unbind (its target is no longer found by the reader)
is flagged in the panel. A stale override still renders as a plain bind; a
stale unbind renders nothing.

## Applying

`hyprkbm-apply` takes the staged model on stdin:

1. Validate: schema, known action kinds and required args, normalised keys,
   no conflicts involving a hyprKBM bind unless it has `"allowConflict": true`
   (duplicates purely within `hyprland.lua` are shown, not blocking).
2. Render to a staged file and **dry-run** it inside Hyprland: `hyprctl eval`
   loads it with `hl.bind`, `hl.unbind` and `hl.define_submap` stubbed, so
   every dispatcher's arguments are checked (Hyprland validates them when a
   dispatcher is constructed) without a bind changing. Syntax errors in raw
   Lua surface here too.
3. Back up the current JSON and Lua to
   `~/.local/state/hyprkbm/backups/<ISO timestamp>/`; prune to 30.
4. Write both files atomically (temp + rename).
5. Create the marker `$XDG_RUNTIME_DIR/hyprkbm/self-reload`, run
   `hyprctl reload` for a clean base, then
   `hyprctl eval 'dofile("<keybinds.lua>")'`.
6. If eval reports an error: restore the backup, reload + eval it, exit
   non-zero with the Lua error. The panel shows it; `notify-send` too.

`hyprkbm-apply --live` does step 5's eval only (no reload, no write); this is
what the watcher calls.

A reload also resets anything other tools applied with eval; hypr-displays
re-applies on `configreloaded`, so the two coexist.

## The watcher

`hyprkbm-watch` (systemd user unit, `WantedBy=graphical-session.target`,
`Restart=on-failure`):

- Waits for Hyprland's `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock`,
  then runs `hyprkbm-apply --live`.
- On every `configreloaded` event, runs `hyprkbm-apply --live`, unless the
  `self-reload` marker exists (it then deletes it and skips; `hyprkbm-apply`
  already evals). A marker older than 10 s is ignored and removed.
- A second instance exits 0.

The service is required. `install.sh` enables it; the panel shows a warning
banner when it is not active, with a button to start it. The docs give an
`hl.on("hyprland.start", ...)` fallback for sessions without
`graphical-session.target`, and no masking opt-out.

## The panel: keyboard view

One window, the only view in v1. Regions (see the approved mockup):

1. **Submap chips**: `global` plus one per submap (hand-written and
   hyprKBM's), with bind counts; `+ submap` creates one (name, reset key).
   Selecting a chip shows that submap on the keyboard.
2. **Search**: free text over keys, actions, descriptions; tags `mod:`,
   `key:`, `exec:`, `desc:`, `submap:`, `src:`. Matching keys stay lit, others
   dim; the bind panel lists all hits across modifier combos.
3. **Conflict button**: count of conflicts; clicking steps through them.
4. **Header actions**: Backups (list, diff, restore), Export (Markdown),
   Theme (presets fuji/iris/paper, accent, dark/light), `⋯` (keyboard layout
   ANSI/ISO, config entry path, service status).
5. **Modifier chips**: SUPER, SHIFT, CTRL, ALT; toggle by click, or hold the
   physical modifiers while the window is focused.
6. **Keyboard**: full layout including F-row, nav cluster and arrows. Each key
   shows a short label for its bind under the current modifiers and submap.
   States: free, bound, conflict, selected, modifier, dimmed.
   **Off-keyboard keys**: mouse buttons, wheel, media/XF86 keys present in
   the config, and `+ any key…` to record or type a keysym.
7. **Selected key panel**: every bind on the selected combo with its source
   (`hyprland.lua:116`, `hyprKBM`, `override`, `stale`); inline conflict
   resolution (keep one, remove one, move one to another key);
   `+ Add a bind`. An **Unplaced** section lists binds whose key could not be
   determined.
8. **Editor**: keys (record or type), action picker with typed fields from
   `actions.json` plus Raw Lua, description, every flag, submap; Save,
   Delete. Editing a hand-written bind creates an override; deleting one
   creates an unbind.
9. **Staged changes bar**: count and summary; Review diff (rendered
   `keybinds.lua` before/after), Discard, Apply. Nothing reaches Hyprland
   before Apply.

Keyboard navigation: arrow keys move the key selection, Enter edits, `/`
focuses search, Esc closes dialogs.

## Cheatsheet

`hyprkbm --cheatsheet` opens the same keyboard component, read-only, on a
full-screen overlay layer surface (namespace `hyprkbm-cheatsheet`). It follows
the physically held modifiers and shows descriptions (falling back to the
action label) instead of short labels. Esc or a click closes it. The user
binds it to a key of their choice; the panel's `⋯` menu offers to add that
bind.

**Export**: `hyprkbm --export md [FILE]` and the Export button write Markdown
grouped by submap, then modifier combo, with key, description and action.

## Action catalogue

`share/actions.json` lists the common dispatchers with typed fields, e.g.
`exec_cmd(cmd: string)`, `focus(direction|workspace)`,
`window.move(workspace)`, `window.close()`, `window.float(action)`,
`window.fullscreen(mode, action)`, `window.pseudo()`, `window.drag()`,
`window.resize()`, `layout(name)`, `submap(name)`, `exit()`. Each entry has
an id, label, `hl.dsp` path, fields (name, type, enum values, default) and a
short-label template for keys. Anything else goes through Raw Lua.

## Theming

Same contract as hypr-displays: `~/.config/hyprkbm/theme.json` (or under
`$XDG_CONFIG_HOME`), sixteen tokens with defaults in `config/Colors.qml`,
presets `fuji` (default), `iris`, `paper`, watched for live reload; the Theme
popup writes the file keeping unknown keys. The theming QML is copied from
hypr-displays since there is no shared phos library yet. Inter, 13/11 px.

## Error handling

| Situation | Behaviour |
|---|---|
| Reader errors or times out | Panel opens with hyprKBM's binds and a banner with the error and line; partial hand binds kept. |
| Apply while the reader errors | Refused: overrides and conflict checks depend on a complete read. |
| Dry run fails | Nothing written; Hyprland's message shown. |
| `keybinds.json` invalid | Panel opens read-only with a banner; offers restoring the latest backup. |
| Apply validation fails | Nothing written; errors shown against the offending binds. |
| Eval fails after write | Automatic rollback to the backup; error shown and sent via `notify-send`. |
| Watcher not running | Panel banner with a Start button. |
| Hyprland not running | `hyprkbm` exits with a message; `--export` still works. |
| Override on a combo shared with a function bind | Refused in the editor with the reason. |

## Testing

- `pytest`: `hyprkbm-apply` (validate, render, backup prune, atomic write,
  rollback), `hyprkbm-watch` (marker logic, events from a fake socket),
  `install.sh`. A throwaway `HOME` and a fake `hyprctl` on `PATH`; never the
  real ones.
- Reader: fixture configs (constants, `..` concatenation, numeric loops,
  helper functions, submaps, function dispatchers, an erroring config, a
  `require`d file, an attempted `os.execute`) run through `lua reader.lua`,
  output compared to expected JSON.
- `node` tests for `lib/*.js`: normalisation (shared fixture table with
  Python), merge, conflicts, search tags, labels.
- Catalogue test: every `hl.dsp` path in `actions.json` exists in
  `/usr/share/hypr/stubs/hl.meta.lua` (skipped when the stub is absent).
- Render round-trip: rendered Lua for fixtures loads in the reader and yields
  the expected binds.
- Manual: real desktop, `qs -p quickshell/hyprkbm`, `quickshell log`; apply,
  `hyprctl reload`, confirm binds survive.

CI runs pytest, node tests, the reader tests, and ShellCheck on `install.sh`.
