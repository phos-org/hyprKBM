# hyprKBM Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build hyprKBM's headless core: read hand-written binds out of `hyprland.lua`, keep hyprKBM's own binds in `keybinds.json`, render and apply them to Hyprland live, keep them applied across reloads with a watcher service, and export a Markdown cheatsheet. Everything works from the CLI.

**Architecture:** A Lua sandbox (`lib/reader.lua`) runs the user's config against a recording `hl` and prints JSON. A stdlib-only Python package (`lib/hyprkbm/`) normalises keys, validates and merges the model, renders `keybinds.lua`, and applies it with `hyprctl` (a dry run first, then reload + `dofile`, with rollback). Thin executables in `bin/` wrap the package; a systemd user unit runs `hyprkbm-watch`, which re-applies on every `configreloaded`.

**Tech Stack:** Python 3.12+ (standard library only), Lua 5.4/5.5, pytest, Hyprland 0.56 `hyprctl`, systemd user units, bash + ShellCheck.

This is plan 1 of 3. Plan 2 is the Quickshell keyboard panel; plan 3 is the cheatsheet overlay. Spec: `docs/superpowers/specs/2026-10-07-hyprkbm-design.md`.

## Global Constraints

- Python helpers import nothing outside the standard library; `pytest` is the only development dependency.
- Never write to, or require a line in, the user's `hyprland.lua`.
- `hyprkbm-apply` is the only writer of `keybinds.json` and `keybinds.lua`.
- Tests never touch the real `HOME`, real `hyprctl`, real `notify-send` or real `systemctl`: they use a throwaway `HOME` and stub executables first on `PATH`.
- Lua interpreter: `$HYPRKBM_LUA`, else the first of `lua`, `lua5.5`, `lua5.4` on `PATH`.
- Reader timeout: 2 seconds. Backups kept: 30. Self-reload marker max age: 10 seconds.
- Paths: `~/.config/hyprkbm/{keybinds.json,keybinds.lua,settings.json}` (under `$XDG_CONFIG_HOME` when set), `~/.local/state/hyprkbm/backups/` (under `$XDG_STATE_HOME`), `$XDG_RUNTIME_DIR/hyprkbm/{self-reload,watch.lock}`.
- Commits: `<type>: <description>` with types `feat, fix, refactor, docs, test, chore, perf`. End each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Comments explain *why*, not *what*.

## File Structure

| Path | Responsibility |
|---|---|
| `lib/hyprkbm/__init__.py` | Repo-relative locations (`ROOT`, `LIB`, `SHARE`). |
| `lib/hyprkbm/paths.py` | `Paths`: every runtime file location, built from an env mapping. |
| `lib/hyprkbm/keys.py` | Parse and normalise key combos (`Combo`, `parse`). |
| `lib/hyprkbm/luaval.py` | Python values → Lua literals; finding a Lua interpreter. |
| `lib/reader.lua` | Sandbox that runs a config against a recording `hl`, prints JSON. |
| `lib/hyprkbm/reader.py` | Runs `reader.lua`, turns its output into `HandBind`s; fingerprints. |
| `share/actions.json` | Action catalogue for the picker and the renderer. |
| `lib/hyprkbm/catalogue.py` | Load/validate catalogue actions; action → dispatcher → Lua; describe. |
| `lib/hyprkbm/model.py` | Load `keybinds.json`, validate it, merge it with hand binds. |
| `lib/hyprkbm/render.py` | Merged model → `keybinds.lua` text. |
| `lib/hyprkbm/apply.py` | Dry run, backup, atomic write, reload + load, rollback, `--live`. |
| `lib/hyprkbm/export.py` | Merged binds → Markdown. |
| `bin/hyprkbm` | CLI: `--export md`, `--apply`, `--status`. |
| `bin/hyprkbm-apply` | Apply a model from stdin, or `--live`. Prints JSON. |
| `bin/hyprkbm-watch` | Watcher: applies at startup and after each `configreloaded`. |
| `systemd/hyprkbm-watch.service` | Starts the watcher with the graphical session. |
| `install.sh` | Symlink install, enable the unit; `--uninstall`. |
| `tests/conftest.py` | `sys.path`, throwaway-HOME `paths`, stub executables. |
| `tests/fixtures/keys.json` | Normalisation table, shared with plan 2's JS twin. |
| `tests/fixtures/hyprland.lua` | A realistic config for reader and render tests. |

---

### Task 1: Scaffold, paths and key normalisation

**Files:**
- Create: `lib/hyprkbm/__init__.py`, `lib/hyprkbm/paths.py`, `lib/hyprkbm/keys.py`
- Create: `tests/conftest.py`, `tests/fixtures/keys.json`, `tests/test_keys.py`, `tests/test_paths.py`
- Create: `.github/workflows/ci.yml`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `hyprkbm.ROOT`, `hyprkbm.LIB`, `hyprkbm.SHARE` (`pathlib.Path`).
- Produces: `Paths(config_dir, entry, state_dir, runtime_dir)` with properties `model`, `lua`, `settings`, `backups`, `marker`, `lock`; `Paths.from_env(env=None) -> Paths`.
- Produces: `keys.KeyParseError(ValueError)`, `keys.Combo(mods: tuple[str, ...], key: str)` with `.id` and `.display`, `keys.parse(keys: str) -> Combo`, `keys.ORDER: list[str]`.
- Produces (conftest fixtures): `home_env` (dict with `HOME`, `XDG_RUNTIME_DIR`; creates an empty `~/.config/hypr/hyprland.lua`), `paths` (`Paths` built from `home_env`).

- [ ] **Step 1: Write the shared fixture table and the failing tests**

`tests/fixtures/keys.json`:

```json
{
  "same": [
    ["SUPER + F", "SUPER+f"],
    ["super + f", "SUPER+f"],
    ["WIN + f", "SUPER+f"],
    ["MOD4 + F", "SUPER+f"],
    ["LOGO + F", "SUPER+f"],
    ["SHIFT + SUPER + F", "SUPER+SHIFT+f"],
    ["SUPER + ALT +  SHIFT + P", "SUPER+ALT+SHIFT+p"],
    ["CONTROL + MOD1 + Delete", "CTRL+ALT+delete"],
    ["SUPER + SUPER + F", "SUPER+f"],
    ["XF86AudioMute", "xf86audiomute"],
    ["SUPER + mouse:272", "SUPER+mouse:272"],
    ["Print", "print"],
    ["SHIFT + Print", "SHIFT+print"],
    ["SUPER + 0", "SUPER+0"]
  ],
  "display": [
    ["shift + win + f", "SUPER + SHIFT + f"],
    ["SUPER + ALT +  SHIFT + P", "SUPER + ALT + SHIFT + P"]
  ],
  "invalid": ["", "   ", " + ", "SUPER + BOGUS + F", "F + G"]
}
```

`tests/conftest.py`:

```python
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from hyprkbm.paths import Paths  # noqa: E402


@pytest.fixture
def home_env(tmp_path):
    """An environment whose HOME is a throwaway directory with an empty
    hyprland.lua, so nothing under test can reach the real one."""
    home = tmp_path / "home"
    (home / ".config" / "hypr").mkdir(parents=True)
    (home / ".config" / "hypr" / "hyprland.lua").write_text("")
    return {"HOME": str(home), "XDG_RUNTIME_DIR": str(tmp_path / "run")}


@pytest.fixture
def paths(home_env):
    return Paths.from_env(home_env)
```

`tests/test_keys.py`:

```python
import json
from pathlib import Path

import pytest

from hyprkbm.keys import KeyParseError, parse

TABLE = json.loads((Path(__file__).parent / "fixtures" / "keys.json").read_text())


@pytest.mark.parametrize("keys,expected", TABLE["same"])
def test_spellings_of_one_combo_share_an_id(keys, expected):
    assert parse(keys).id == expected


@pytest.mark.parametrize("keys,expected", TABLE["display"])
def test_display_uses_canonical_modifiers_and_the_key_as_written(keys, expected):
    assert parse(keys).display == expected


@pytest.mark.parametrize("keys", TABLE["invalid"])
def test_malformed_combos_are_rejected(keys):
    with pytest.raises(KeyParseError):
        parse(keys)


def test_keys_must_be_text():
    with pytest.raises(KeyParseError):
        parse(42)
```

`tests/test_paths.py`:

```python
from pathlib import Path

from hyprkbm.paths import Paths


def test_defaults_follow_home(tmp_path):
    p = Paths.from_env({"HOME": str(tmp_path), "XDG_RUNTIME_DIR": "/run/user/1"})

    assert p.model == tmp_path / ".config/hyprkbm/keybinds.json"
    assert p.lua == tmp_path / ".config/hyprkbm/keybinds.lua"
    assert p.entry == tmp_path / ".config/hypr/hyprland.lua"
    assert p.backups == tmp_path / ".local/state/hyprkbm/backups"
    assert p.marker == Path("/run/user/1/hyprkbm/self-reload")
    assert p.lock == Path("/run/user/1/hyprkbm/watch.lock")


def test_xdg_dirs_win_over_home(tmp_path):
    p = Paths.from_env({"HOME": str(tmp_path / "h"),
                        "XDG_CONFIG_HOME": str(tmp_path / "c"),
                        "XDG_STATE_HOME": str(tmp_path / "s"),
                        "XDG_RUNTIME_DIR": str(tmp_path / "r")})

    assert p.model == tmp_path / "c/hyprkbm/keybinds.json"
    assert p.entry == tmp_path / "c/hypr/hyprland.lua"
    assert p.backups == tmp_path / "s/hyprkbm/backups"


def test_settings_can_point_at_another_entry(tmp_path):
    settings = tmp_path / ".config/hyprkbm/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text('{"entry": "~/dots/hypr/main.lua"}')

    p = Paths.from_env({"HOME": str(tmp_path), "XDG_RUNTIME_DIR": "/run/user/1"})

    assert p.entry == tmp_path / "dots/hypr/main.lua"


def test_unreadable_settings_are_ignored(tmp_path):
    settings = tmp_path / ".config/hyprkbm/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text("{not json")

    p = Paths.from_env({"HOME": str(tmp_path), "XDG_RUNTIME_DIR": "/run/user/1"})

    assert p.entry == tmp_path / ".config/hypr/hyprland.lua"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/ -q`
Expected: errors with `ModuleNotFoundError: No module named 'hyprkbm'`.

- [ ] **Step 3: Implement the package, paths and keys**

`lib/hyprkbm/__init__.py`:

```python
"""hyprKBM's core: reading hyprland.lua, the keybinds model, rendering it to
Lua and applying it to Hyprland."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SHARE = ROOT / "share"
```

`lib/hyprkbm/paths.py`:

```python
"""Where hyprKBM's files live.

Built from an environment mapping rather than read from os.environ inside
each helper, so a test can point every path at a throwaway HOME at once.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    entry: Path
    state_dir: Path
    runtime_dir: Path

    @property
    def model(self):
        return self.config_dir / "keybinds.json"

    @property
    def lua(self):
        return self.config_dir / "keybinds.lua"

    @property
    def settings(self):
        return self.config_dir / "settings.json"

    @property
    def backups(self):
        return self.state_dir / "backups"

    @property
    def marker(self):
        return self.runtime_dir / "self-reload"

    @property
    def lock(self):
        return self.runtime_dir / "watch.lock"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        home = Path(env.get("HOME") or os.path.expanduser("~"))
        config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        state_home = Path(env.get("XDG_STATE_HOME") or home / ".local" / "state")
        runtime = Path(env.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid())
        config_dir = config_home / "hyprkbm"

        entry = config_home / "hypr" / "hyprland.lua"
        custom = _settings(config_dir / "settings.json").get("entry")
        if isinstance(custom, str) and custom:
            if custom == "~" or custom.startswith("~/"):
                custom = str(home) + custom[1:]
            entry = Path(custom)

        return cls(config_dir, entry, state_home / "hyprkbm", runtime / "hyprkbm")


def _settings(path):
    # A broken settings file must not stop hyprKBM opening: the defaults are
    # what almost everyone uses anyway.
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
```

`lib/hyprkbm/keys.py`:

```python
"""Key combos as Hyprland's Lua config writes them: "SUPER + SHIFT + F".

Two spellings of one combo must compare equal -- "WIN + f" and "SUPER + F"
are the same bind to Hyprland, and a conflict check that missed that would
wave a real conflict through. The panel has a JavaScript twin of this module;
both are tested against tests/fixtures/keys.json.
"""
from dataclasses import dataclass

# Every modifier name Hyprland accepts, mapped to the one hyprKBM writes.
MODIFIERS = {
    "SUPER": "SUPER", "WIN": "SUPER", "LOGO": "SUPER", "MOD4": "SUPER",
    "CTRL": "CTRL", "CONTROL": "CTRL",
    "ALT": "ALT", "MOD1": "ALT",
    "SHIFT": "SHIFT",
    "CAPS": "CAPS",
    "MOD2": "MOD2", "MOD3": "MOD3", "MOD5": "MOD5",
}
ORDER = ["SUPER", "CTRL", "ALT", "SHIFT", "CAPS", "MOD2", "MOD3", "MOD5"]


class KeyParseError(ValueError):
    pass


@dataclass(frozen=True)
class Combo:
    mods: tuple
    key: str

    @property
    def id(self):
        # Keysyms are matched case-insensitively: "f" and "F" are one key.
        return "+".join(self.mods + (self.key.lower(),))

    @property
    def display(self):
        return " + ".join(self.mods + (self.key,))


def parse(keys):
    if not isinstance(keys, str):
        raise KeyParseError("keys must be text, not %s" % type(keys).__name__)
    tokens = [token for part in keys.split("+") for token in part.split()]
    if not tokens:
        raise KeyParseError("no key in %r" % keys)
    *mod_tokens, key = tokens
    mods = set()
    for token in mod_tokens:
        canonical = MODIFIERS.get(token.upper())
        if canonical is None:
            raise KeyParseError("%r is not a modifier (in %r)" % (token, keys))
        mods.add(canonical)
    return Combo(tuple(m for m in ORDER if m in mods), key)
```

`.gitignore` (replace the file):

```
.superpowers/
__pycache__/
.pytest_cache/
```

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    name: Tests
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: '3.12'

      # The reader runs the user's config in real Lua. Ubuntu only ships
      # versioned names, which hyprkbm.luaval.interpreter() looks for.
      - name: Install Lua
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends lua5.4

      # The helpers import nothing outside the standard library; pytest is the
      # only development dependency there is.
      - name: Install pytest
        run: python3 -m pip install --upgrade pytest

      - name: Run tests
        run: python3 -m pytest tests/ -q
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .github lib tests
git commit -m "feat: add key normalisation and runtime paths

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Lua literals

**Files:**
- Create: `lib/hyprkbm/luaval.py`
- Test: `tests/test_luaval.py`

**Interfaces:**
- Produces: `luaval.to_lua(value) -> str` (None/bool/int/float/str/list/dict), `luaval.string(s: str) -> str`, `luaval.NotReproducible(ValueError)` (raised for `{"__function": ...}` / `{"__opaque": ...}` anywhere in the value), `luaval.interpreter() -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_luaval.py`:

```python
import subprocess

import pytest

from hyprkbm.luaval import NotReproducible, interpreter, to_lua


def lua_prints(expression):
    res = subprocess.run([interpreter(), "-e", "io.write(%s)" % expression],
                         capture_output=True, check=True)
    return res.stdout.decode("utf-8")


@pytest.mark.parametrize("text", [
    "plain",
    'say "hi"',
    "back\\slash",
    "line\nbreak",
    "tab\tand\rcarriage",
    "nul\x00here",
    "bell\x07 then 7",
    "ünïcödé",
    'grim -g "$(slurp)" - | satty --filename -',
])
def test_strings_survive_a_trip_through_lua(text):
    assert lua_prints(to_lua(text)) == text


def test_scalars():
    assert to_lua(None) == "nil"
    assert to_lua(True) == "true"
    assert to_lua(False) == "false"
    assert to_lua(3) == "3"
    assert to_lua(-1.5) == "-1.5"


def test_non_finite_numbers_have_no_literal():
    with pytest.raises(ValueError):
        to_lua(float("nan"))


def test_tables_are_written_with_sorted_keys():
    assert to_lua({"workspace": 3, "action": "toggle"}) == \
        '{ action = "toggle", workspace = 3 }'
    assert to_lua([1, "a", True]) == '{ 1, "a", true }'
    assert to_lua({}) == "{}"
    assert to_lua([]) == "{}"


def test_keys_that_are_not_identifiers_are_bracketed():
    assert to_lua({"end": 1, "a-b": 2}) == '{ ["a-b"] = 2, ["end"] = 1 }'


def test_a_lua_function_cannot_be_written_back():
    with pytest.raises(NotReproducible):
        to_lua([{"cb": {"__function": "hyprland.lua:3"}}])
    with pytest.raises(NotReproducible):
        to_lua({"__opaque": True})


def test_the_interpreter_can_be_overridden(monkeypatch):
    monkeypatch.setenv("HYPRKBM_LUA", "/opt/lua/bin/lua")
    assert interpreter() == "/opt/lua/bin/lua"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_luaval.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.luaval'`.

- [ ] **Step 3: Implement luaval.py**

`lib/hyprkbm/luaval.py`:

```python
"""Python values as Lua source, for writing keybinds.lua."""
import math
import os
import re
import shutil

KEYWORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for",
            "function", "global", "goto", "if", "in", "local", "nil", "not",
            "or", "repeat", "return", "then", "true", "until", "while"}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
ESCAPES = {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


class NotReproducible(ValueError):
    """A value the reader could only describe -- a Lua function, or an object
    from the hl API -- and that therefore cannot be written back out."""


def string(text):
    out = []
    for ch in text:
        if ch in ESCAPES:
            out.append(ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            # Three digits always, so a digit that follows is not swallowed
            # into the escape.
            out.append("\\%03d" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def to_lua(value):
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("%r has no Lua literal" % value)
        return repr(value)
    if isinstance(value, str):
        return string(value)
    if isinstance(value, list):
        if not value:
            return "{}"
        return "{ " + ", ".join(to_lua(v) for v in value) + " }"
    if isinstance(value, dict):
        if "__function" in value or "__opaque" in value:
            raise NotReproducible(value.get("__function") or "an hl object")
        if not value:
            return "{}"
        parts = []
        for key in sorted(value):
            if IDENTIFIER.match(key) and key not in KEYWORDS:
                name = key
            else:
                name = "[%s]" % string(key)
            parts.append("%s = %s" % (name, to_lua(value[key])))
        return "{ " + ", ".join(parts) + " }"
    raise TypeError("cannot write %s as Lua" % type(value).__name__)


def interpreter():
    """The Lua that runs the reader. Arch ships `lua`; Debian and Ubuntu
    ship only versioned names."""
    override = os.environ.get("HYPRKBM_LUA")
    if override:
        return override
    for name in ("lua", "lua5.5", "lua5.4"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("no Lua interpreter found; install the lua package")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_luaval.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/luaval.py tests/test_luaval.py
git commit -m "feat: write Python values as Lua literals

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The config reader

**Files:**
- Create: `lib/reader.lua`, `lib/hyprkbm/reader.py`
- Create: `tests/fixtures/hyprland.lua`
- Test: `tests/test_reader.py`

**Interfaces:**
- Consumes: `keys.parse`, `keys.KeyParseError`, `luaval.interpreter`, `Paths.entry`, `Paths.lua`.
- Produces: `reader.HandBind` (dataclass: `keys: str`, `combo: str | None`, `submap: str`, `dispatcher: dict`, `opts: dict`, `file: str`, `line: int`, `seq: int`; properties `fingerprint: str`, `reproducible: bool`, `where: str` like `"hyprland.lua:116"`).
- Produces: `reader.ReadResult` (`binds: list[HandBind]`, `submaps: list[dict]` each `{"name", "reset", "file", "line"}`, `error: str | None`; property `submap_names: set[str]`).
- Produces: `reader.read_config(paths) -> ReadResult`, `reader.fingerprint(dispatcher: dict) -> str`, `reader.reproducible(dispatcher: dict, opts: dict) -> bool`, `reader.TIMEOUT` (float, seconds).
- Dispatcher dict shapes everywhere downstream: `{"dsp": "window.move", "args": [...]}`, `{"__function": "/path/file.lua:12"}`, `{"__opaque": True}`, and (hyprKBM raw actions, Task 4) `{"raw": "<lua>"}`.

- [ ] **Step 1: Write the fixture config and the failing tests**

`tests/fixtures/hyprland.lua`:

```lua
-- Shaped like a real hyprland.lua: a mod variable, a loop, nested dispatchers.
local mainMod = "SUPER"
local terminal = "kitty"

hl.config({ input = { kb_layout = "us" } })

hl.bind(mainMod .. " + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind(mainMod .. " + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.bind(mainMod .. " + Q", hl.dsp.exec_cmd(terminal))
hl.bind(mainMod .. " + C", hl.dsp.window.close())
hl.bind(mainMod .. " + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind(mainMod .. " + ALT + F", hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
hl.bind("SHIFT + Print", hl.dsp.exec_cmd('grim -g "$(slurp)" - | satty --filename -'))

for i = 1, 10 do
    local key = i % 10
    hl.bind(mainMod .. " + " .. key, hl.dsp.focus({ workspace = i }))
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })

hl.define_submap("resize", "escape", function()
    hl.bind("right", hl.dsp.window.resize({ x = 10, y = 0, relative = true }), { repeating = true })
    hl.bind("left", hl.dsp.window.resize({ x = -10, y = 0, relative = true }), { repeating = true })
end)
hl.bind(mainMod .. " + R", hl.dsp.submap("resize"))
```

`tests/test_reader.py`:

```python
import textwrap
from pathlib import Path

from hyprkbm import reader
from hyprkbm.reader import fingerprint, read_config

FIXTURE = Path(__file__).parent / "fixtures" / "hyprland.lua"


def read(paths, source, **files):
    paths.entry.write_text(textwrap.dedent(source))
    for name, text in files.items():
        target = paths.entry.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text))
    return read_config(paths)


def by_keys(result):
    return {(b.submap, b.keys): b for b in result.binds}


def test_constants_and_concatenation_are_evaluated(paths):
    result = read(paths, """\
        local mainMod = "SUPER"
        hl.bind(mainMod .. " + F", hl.dsp.exec_cmd("dolphin"))
    """)

    assert result.error is None
    [bind] = result.binds
    assert bind.keys == "SUPER + F"
    assert bind.combo == "SUPER+f"
    assert bind.dispatcher == {"dsp": "exec_cmd", "args": ["dolphin"]}
    assert bind.fingerprint == 'exec_cmd:["dolphin"]'
    assert bind.line == 2
    assert bind.where == "hyprland.lua:2"
    assert bind.reproducible


def test_a_realistic_config_reads_completely(paths):
    paths.entry.write_text(FIXTURE.read_text())

    result = read_config(paths)

    assert result.error is None
    assert len(result.binds) == 31
    binds = by_keys(result)
    assert binds[("", "SUPER + 0")].dispatcher == \
        {"dsp": "focus", "args": [{"workspace": 10}]}
    assert binds[("", "SUPER + SHIFT + 3")].dispatcher == \
        {"dsp": "window.move", "args": [{"workspace": 3}]}
    assert binds[("", "SUPER + mouse:272")].opts == {"mouse": True}
    assert binds[("", "SUPER + Q")].line == 9
    assert binds[("resize", "right")].opts == {"repeating": True}
    assert binds[("", "SUPER + R")].submap == ""
    assert result.submaps == [{"name": "resize", "reset": "escape",
                               "file": str(paths.entry), "line": 23}]


def test_submap_can_be_appended_to_without_a_reset(paths):
    result = read(paths, """\
        hl.define_submap("move", "escape", function() end)
        hl.define_submap("move", function()
            hl.bind("left", hl.dsp.window.move({ direction = "left" }))
        end)
    """)

    assert [s["reset"] for s in result.submaps] == ["escape"]
    assert result.binds[0].submap == "move"


def test_function_dispatchers_are_recorded_but_not_reproducible(paths):
    result = read(paths, """\
        hl.bind("SUPER + G", function()
            hl.exec_cmd("kitty")
        end)
    """)

    [bind] = result.binds
    assert bind.dispatcher == {"__function": "%s:1" % paths.entry}
    assert bind.fingerprint == "function:%s:1" % paths.entry
    assert not bind.reproducible


def test_a_later_unbind_removes_an_earlier_bind_in_every_submap(paths):
    result = read(paths, """\
        hl.bind("SUPER + P", hl.dsp.window.pseudo())
        hl.define_submap("x", "escape", function()
            hl.bind("SUPER + P", hl.dsp.window.pin())
        end)
        hl.unbind("super + p")
        hl.bind("SUPER + P", hl.dsp.window.close())
    """)

    assert [b.dispatcher["dsp"] for b in result.binds] == ["window.close"]


def test_require_and_dofile_load_from_the_config_dir(paths):
    result = read(paths, """\
        require("binds")
        dofile("extra/more.lua")
    """, **{"binds.lua": 'hl.bind("SUPER + A", hl.dsp.exit())\n',
            "extra/more.lua": 'hl.bind("SUPER + B", hl.dsp.exit())\n'})

    assert result.error is None
    assert [Path(b.file).name for b in result.binds] == ["binds.lua", "more.lua"]


def test_the_sandbox_has_no_os_execute_or_io(paths, tmp_path):
    marker = tmp_path / "pwned"
    result = read(paths, """\
        hl.bind("SUPER + A", hl.dsp.exit())
        os.execute("touch %s")
    """ % marker)

    assert not marker.exists()
    assert "execute" in result.error
    assert len(result.binds) == 1, "binds before the error are kept"

    result = read(paths, 'io.open("/etc/hostname")\n')
    assert "io" in result.error


def test_files_outside_the_config_dir_are_refused(paths):
    result = read(paths, 'dofile("/etc/passwd")\n')

    assert "refusing to load /etc/passwd" in result.error


def test_hyprkbms_own_file_is_never_read_back(paths, monkeypatch):
    monkeypatch.setenv("HOME", str(paths.entry.parents[2]))
    paths.lua.parent.mkdir(parents=True)
    paths.lua.write_text('hl.bind("SUPER + B", hl.dsp.exit())\n')

    result = read(paths, """\
        dofile(os.getenv("HOME") .. "/.config/hyprkbm/keybinds.lua")
    """)

    assert result.error is None
    assert result.binds == []


def test_an_endless_loop_times_out(paths, monkeypatch):
    monkeypatch.setattr(reader, "TIMEOUT", 0.5)

    result = read(paths, "while true do end\n")

    assert "endless loop" in result.error


def test_live_state_and_the_rest_of_hl_do_nothing(paths):
    result = read(paths, """\
        for _, m in ipairs(hl.get_monitors()) do
            hl.bind("SUPER + M", hl.dsp.exit())
        end
        if hl.get_active_window() then hl.bind("SUPER + W", hl.dsp.exit()) end
        hl.config({ general = { gaps_in = 5 } })
        hl.window_rule({ match = { class = "kitty" } }):set_enabled(false)
        hl.on("hyprland.start", function() hl.bind("SUPER + X", hl.dsp.exit()) end)
        local k = hl.bind("SUPER + K", hl.dsp.exit())
        k:set_enabled(false)
    """)

    assert result.error is None
    assert [b.keys for b in result.binds] == ["SUPER + K"]


def test_a_missing_entry_is_an_error(paths):
    paths.entry.unlink()

    assert "cannot open" in read_config(paths).error


def test_fingerprints_sort_table_keys():
    a = fingerprint({"dsp": "window.fullscreen",
                     "args": [{"mode": "fullscreen", "action": "toggle"}]})
    b = fingerprint({"dsp": "window.fullscreen",
                     "args": [{"action": "toggle", "mode": "fullscreen"}]})
    assert a == b == 'window.fullscreen:[{"action":"toggle","mode":"fullscreen"}]'
    assert fingerprint({"raw": "hl.dsp.exit()"}) == "raw:hl.dsp.exit()"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_reader.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.reader'`.

- [ ] **Step 3: Write the Lua harness**

`lib/reader.lua`:

```lua
-- Runs a Hyprland Lua config against a recording `hl` and prints, as JSON,
-- every bind, unbind and submap it made.
--
--   lua reader.lua <entry> <config dir> <hyprKBM's keybinds.lua>
--
-- hyprctl reports Lua binds as opaque "__lua" references, so the source is the
-- only place an action can be read from. Running it, rather than parsing it,
-- is what gets loops, helper functions and `mainMod ..` right.
--
-- The config runs in a sandbox: no io, no os beyond reading the clock and the
-- environment, and files load only from the config directory. hl.on callbacks
-- are never run, and everything that asks about live state gets "nothing".
local entry, confdir, own = arg[1], arg[2], arg[3] or ""

local getinfo = debug.getinfo
local mtype = math.type

local out = { binds = {}, unbinds = {}, submaps = {} }
local seq = 0
local current_submap = ""

local function next_seq()
    seq = seq + 1
    return seq
end

local function source_of(info)
    if info.source:sub(1, 1) == "@" then return info.source:sub(2) end
    return info.short_src
end

-- The config line that called into hl: 1 is this function, 2 the hl.* function.
local function where()
    local info = getinfo(3, "Sl")
    if not info then return "?", 0 end
    return source_of(info), info.currentline
end

-- Stands in for every hl object the reader does not model (rules, timers,
-- event subscriptions, a bind's handle): any field of it, and any call on it,
-- is itself again, so `hl.bind(...):set_enabled(false)` runs and does nothing.
local INERT = setmetatable({}, {
    __index = function(self) return self end,
    __newindex = function() end,
    __call = function(self) return self end,
})

local is_dispatcher = setmetatable({}, { __mode = "k" })

-- hl.dsp and every namespace under it. Calling a node returns a description
-- of the dispatcher instead of one, which is what lets it be written back out.
local function dsp_node(path)
    return setmetatable({}, {
        __index = function(_, name)
            return dsp_node(path == "" and name or (path .. "." .. name))
        end,
        __call = function(_, ...)
            local d = { dsp = path, args = table.pack(...) }
            is_dispatcher[d] = true
            return d
        end,
    })
end

local hl = { dsp = dsp_node("") }

function hl.bind(keys, dispatcher, opts)
    local file, line = where()
    local record = { seq = next_seq(), keys = keys, submap = current_submap,
                     file = file, line = line, opts = opts }
    if type(dispatcher) == "function" then
        local info = getinfo(dispatcher, "S")
        record.dispatcher = { __function = source_of(info) .. ":" .. info.linedefined }
    elseif is_dispatcher[dispatcher] then
        record.dispatcher = dispatcher
    else
        record.dispatcher = { __opaque = true }
    end
    table.insert(out.binds, record)
    return INERT
end

function hl.unbind(keys)
    local file, line = where()
    table.insert(out.unbinds, { seq = next_seq(), keys = keys, file = file, line = line })
end

function hl.define_submap(name, reset_or_fn, fn)
    local reset = reset_or_fn
    if type(reset_or_fn) == "function" then fn, reset = reset_or_fn, nil end
    local file, line = where()
    table.insert(out.submaps, { name = name, reset = reset, file = file, line = line })
    if fn then
        local saved = current_submap
        current_submap = name
        local ok, err = pcall(fn)
        current_submap = saved
        if not ok then error(err, 0) end
    end
end

function hl.get_current_submap() return current_submap end
function hl.version() return "0.0.0" end
function hl.is_key_down() return false end
for _, name in ipairs({ "get_monitors", "get_windows", "get_workspaces", "get_layers",
                        "get_loaded_plugins", "get_workspace_windows" }) do
    hl[name] = function() return {} end
end

setmetatable(hl, {
    __index = function(_, name)
        if type(name) == "string" and name:sub(1, 4) == "get_" then
            return function() return nil end
        end
        return INERT
    end,
})

-- ------------------------------------------------------------- the sandbox

local env

local function inside_confdir(path)
    return path:sub(1, #confdir + 1) == confdir .. "/"
        and not path:find("/%.%./") and not path:find("/%.%.$")
end

local function resolve(path)
    if path:sub(1, 1) ~= "/" then return confdir .. "/" .. path end
    return path
end

local function load_config_file(path)
    -- A config that loads hyprKBM's own file would otherwise have every one of
    -- hyprKBM's binds read back as hand-written.
    if own ~= "" and path == own then return function() end end
    if not inside_confdir(path) then
        error("hyprkbm reader: refusing to load " .. path .. " (outside " .. confdir .. ")", 0)
    end
    local chunk, err = loadfile(path, "t", env)
    if not chunk then error(err, 0) end
    return chunk
end

local loaded = {}

env = {
    assert = assert, error = error, ipairs = ipairs, pairs = pairs, next = next,
    pcall = pcall, xpcall = xpcall, select = select, tonumber = tonumber,
    tostring = tostring, type = type, rawequal = rawequal, rawget = rawget,
    rawset = rawset, rawlen = rawlen, setmetatable = setmetatable,
    getmetatable = getmetatable, string = string, table = table, math = math,
    utf8 = utf8, _VERSION = _VERSION,
    print = function() end,
    os = { getenv = os.getenv, time = os.time, date = os.date, clock = os.clock },
    hl = hl,
}
env._G = env

env.dofile = function(path)
    return load_config_file(resolve(path))()
end

env.load = function(chunk, name, _, chunk_env)
    return load(chunk, name, "t", chunk_env or env)
end

env.require = function(name)
    if loaded[name] ~= nil then return loaded[name] end
    if type(name) ~= "string" or name:find("%.%.") or name:find("/") then
        error("hyprkbm reader: bad module name " .. tostring(name), 2)
    end
    local base = confdir .. "/" .. (name:gsub("%.", "/"))
    local path
    for _, candidate in ipairs({ base .. ".lua", base .. "/init.lua" }) do
        local handle = io.open(candidate, "r")
        if handle then
            handle:close()
            path = candidate
            break
        end
    end
    if not path then error("module '" .. name .. "' not found under " .. confdir, 2) end
    local result = load_config_file(path)(name)
    loaded[name] = result == nil and true or result
    return loaded[name]
end

-- ------------------------------------------------------------------ JSON

local ESCAPES = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r",
                  ["\t"] = "\\t", ["\b"] = "\\b", ["\f"] = "\\f" }

local function quote(s)
    return '"' .. s:gsub('[%c"\\]', function(c)
        return ESCAPES[c] or string.format("\\u%04x", c:byte())
    end) .. '"'
end

local function array_length(t)
    local n = 0
    for k in pairs(t) do
        if mtype(k) ~= "integer" or k < 1 then return nil end
        n = n + 1
    end
    for i = 1, n do
        if rawget(t, i) == nil then return nil end
    end
    return n
end

local encode

local function encode_list(values, n, depth)
    local parts = {}
    for i = 1, n do parts[i] = encode(values[i], depth + 1) end
    return "[" .. table.concat(parts, ",") .. "]"
end

encode = function(v, depth)
    depth = depth or 0
    local kind = type(v)
    if v == nil then return "null" end
    if depth > 32 then return '{"__opaque":true}' end
    if kind == "boolean" then return tostring(v) end
    if kind == "number" then
        if mtype(v) == "integer" then return string.format("%d", v) end
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        return string.format("%.17g", v)
    end
    if kind == "string" then return quote(v) end
    if kind == "function" then
        local info = getinfo(v, "S")
        return '{"__function":' .. quote(source_of(info) .. ":" .. info.linedefined) .. "}"
    end
    if kind ~= "table" or v == INERT then return '{"__opaque":true}' end
    if is_dispatcher[v] then
        return '{"dsp":' .. quote(v.dsp) .. ',"args":' .. encode_list(v.args, v.args.n, depth) .. "}"
    end
    local n = array_length(v)
    if n and n > 0 then return encode_list(v, n, depth) end
    local keys = {}
    for k in pairs(v) do table.insert(keys, k) end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    local parts = {}
    for _, k in ipairs(keys) do
        table.insert(parts, quote(tostring(k)) .. ":" .. encode(rawget(v, k), depth + 1))
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

-- ------------------------------------------------------------------- run

local ok, err = xpcall(function() load_config_file(entry)() end,
                       function(e) return tostring(e) end)
if not ok then out.error = { message = err } end

io.write(encode(out), "\n")
```

- [ ] **Step 4: Write the Python side**

`lib/hyprkbm/reader.py`:

```python
"""Run the user's hyprland.lua through lib/reader.lua and turn what it
recorded into hand-written binds.

hyprctl reports every Lua bind as an opaque "__lua" reference, so the source
is the only place an action can be read from -- and running it, rather than
parsing it, is what gets loops, helper functions and `mainMod ..` right.
"""
import json
import os
import subprocess
from dataclasses import dataclass, field

from . import LIB
from .keys import KeyParseError, parse
from .luaval import interpreter

READER = LIB / "reader.lua"
TIMEOUT = 2.0


def fingerprint(dispatcher):
    """What a bind does, as one comparable string. Overrides and unbinds name
    the hand-written bind they act on by keys, submap and this -- never by
    line number, which moves whenever the user edits above it."""
    if "dsp" in dispatcher:
        args = json.dumps(dispatcher.get("args", []), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)
        return "%s:%s" % (dispatcher["dsp"], args)
    if "raw" in dispatcher:
        return "raw:" + dispatcher["raw"]
    if "__function" in dispatcher:
        return "function:" + dispatcher["__function"]
    return "opaque"


def _has_marker(value):
    if isinstance(value, dict):
        return ("__function" in value or "__opaque" in value
                or any(_has_marker(v) for v in value.values()))
    if isinstance(value, list):
        return any(_has_marker(v) for v in value)
    return False


def reproducible(dispatcher, opts):
    """Whether hyprKBM could write this bind back out. Overriding one bind
    means unbinding its whole combo and re-creating the rest, so a Lua
    function sharing that combo blocks the override."""
    return "dsp" in dispatcher and not _has_marker(dispatcher) and not _has_marker(opts)


@dataclass
class HandBind:
    keys: str
    combo: str | None
    submap: str
    dispatcher: dict
    opts: dict
    file: str
    line: int
    seq: int

    @property
    def fingerprint(self):
        return fingerprint(self.dispatcher)

    @property
    def reproducible(self):
        return reproducible(self.dispatcher, self.opts)

    @property
    def where(self):
        return "%s:%d" % (os.path.basename(self.file), self.line)


@dataclass
class ReadResult:
    binds: list = field(default_factory=list)
    submaps: list = field(default_factory=list)
    error: str | None = None

    @property
    def submap_names(self):
        return {s["name"] for s in self.submaps}


def read_config(paths):
    entry = paths.entry
    command = [interpreter(), str(READER), str(entry), str(entry.parent), str(paths.lua)]
    try:
        res = subprocess.run(command, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return ReadResult(error="reading %s took longer than %g s; is there an "
                                "endless loop in it?" % (entry, TIMEOUT))
    if res.returncode != 0:
        return ReadResult(error="the reader failed: "
                                + res.stderr.decode("utf-8", "replace").strip())
    return _result(json.loads(res.stdout.decode("utf-8", "replace")))


def _combo(keys):
    try:
        return parse(keys).id
    except KeyParseError:
        return None


def _list(value):
    # The reader writes an empty Lua table as {}, whatever it was meant to be.
    return value if isinstance(value, list) else []


def _result(raw):
    unbinds = [(u["seq"], _combo(u.get("keys"))) for u in _list(raw.get("unbinds"))]
    binds = []
    for b in _list(raw.get("binds")):
        combo = _combo(b.get("keys"))
        # hl.unbind drops the combo in every submap, so a later unbind in the
        # config itself means the bind never reaches Hyprland.
        if combo is not None and any(seq > b["seq"] and c == combo for seq, c in unbinds):
            continue
        keys = b.get("keys")
        opts = b.get("opts")
        binds.append(HandBind(
            keys=keys if isinstance(keys, str) else repr(keys),
            combo=combo,
            submap=b.get("submap") or "",
            dispatcher=b.get("dispatcher") or {"__opaque": True},
            opts=opts if isinstance(opts, dict) else {},
            file=b.get("file") or "?",
            line=b.get("line") or 0,
            seq=b["seq"],
        ))

    submaps = {}
    for s in _list(raw.get("submaps")):
        if not isinstance(s.get("name"), str):
            continue
        known = submaps.setdefault(s["name"], {"name": s["name"], "reset": s.get("reset"),
                                               "file": s.get("file"), "line": s.get("line")})
        # Defining a submap again appends to it; the reset key is whichever
        # definition gave one.
        if known["reset"] is None and s.get("reset") is not None:
            known["reset"] = s["reset"]

    error = raw.get("error")
    return ReadResult(binds, list(submaps.values()), error["message"] if error else None)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_reader.py -q`
Expected: all pass.

Then run the reader against your own config as a smoke test (read-only; the sandbox cannot write):

Run: `python3 -c "import sys; sys.path.insert(0, 'lib'); from hyprkbm.paths import Paths; from hyprkbm.reader import read_config; r = read_config(Paths.from_env()); print(len(r.binds), r.error)"`
Expected: the same number of binds as `hyprctl binds -j | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"`, and `None`.

- [ ] **Step 6: Commit**

```bash
git add lib/reader.lua lib/hyprkbm/reader.py tests/fixtures/hyprland.lua tests/test_reader.py
git commit -m "feat: read hand-written binds by running hyprland.lua in a sandbox

hyprctl binds reports every Lua bind as an opaque __lua reference, so the
actions can only come from the source. Running it against a recording hl
gets loops, helpers and mainMod concatenation right where parsing would not.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The action catalogue

**Files:**
- Create: `share/actions.json`, `lib/hyprkbm/catalogue.py`
- Test: `tests/test_catalogue.py`

**Interfaces:**
- Consumes: `luaval.to_lua`, `luaval.NotReproducible`.
- Produces: `catalogue.load_catalogue(path=CATALOGUE) -> dict[str, dict]` (id → entry), `catalogue.action_errors(action, catalogue) -> list[str]`, `catalogue.to_dispatcher(action, catalogue) -> dict`, `catalogue.dispatcher_lua(dispatcher) -> str`, `catalogue.describe(dispatcher, catalogue) -> str`.
- Model action shapes: `{"kind": "<catalogue id>", "args": {<field>: value}}` or `{"kind": "raw", "lua": "<Lua expression>"}`.
- Catalogue entry shape: `{"id", "label", "dsp", "call": "none"|"positional"|"table", "fields": [{"name", "label", "type": "string"|"workspace"|"enum"|"bool"|"submap", "required"?, "values"?, "default"?}], "oneOf"?: [field names]}`.

- [ ] **Step 1: Write the catalogue data**

`share/actions.json` (every `dsp` path and argument shape was checked against Hyprland 0.56.2 with `hyprctl eval 'local d = hl.dsp....(...)'`, which validates arguments without dispatching):

```json
{
  "version": 1,
  "actions": [
    { "id": "exec_cmd", "label": "Run a command", "dsp": "exec_cmd", "call": "positional",
      "fields": [ { "name": "cmd", "label": "Command", "type": "string", "required": true } ] },
    { "id": "window.close", "label": "Close window", "dsp": "window.close", "call": "none", "fields": [] },
    { "id": "window.kill", "label": "Kill window", "dsp": "window.kill", "call": "none", "fields": [] },
    { "id": "window.float", "label": "Float window", "dsp": "window.float", "call": "table",
      "fields": [ { "name": "action", "label": "Action", "type": "enum",
                    "values": ["toggle", "enable", "disable"], "default": "toggle" } ] },
    { "id": "window.fullscreen", "label": "Fullscreen", "dsp": "window.fullscreen", "call": "table",
      "fields": [ { "name": "mode", "label": "Mode", "type": "enum",
                    "values": ["fullscreen", "maximized"], "default": "fullscreen" },
                  { "name": "action", "label": "Action", "type": "enum",
                    "values": ["toggle", "set", "unset"], "default": "toggle" } ] },
    { "id": "window.pseudo", "label": "Pseudotile", "dsp": "window.pseudo", "call": "none", "fields": [] },
    { "id": "window.pin", "label": "Pin window", "dsp": "window.pin", "call": "none", "fields": [] },
    { "id": "window.move", "label": "Move window", "dsp": "window.move", "call": "table",
      "fields": [ { "name": "workspace", "label": "To workspace", "type": "workspace" },
                  { "name": "direction", "label": "Direction", "type": "enum",
                    "values": ["left", "right", "up", "down"] } ],
      "oneOf": ["workspace", "direction"] },
    { "id": "window.cycle_next", "label": "Cycle windows", "dsp": "window.cycle_next", "call": "table",
      "fields": [ { "name": "next", "label": "Forwards", "type": "bool", "default": true } ] },
    { "id": "window.drag", "label": "Drag window (mouse)", "dsp": "window.drag", "call": "none", "fields": [] },
    { "id": "window.resize", "label": "Resize window (mouse)", "dsp": "window.resize", "call": "none", "fields": [] },
    { "id": "focus", "label": "Focus", "dsp": "focus", "call": "table",
      "fields": [ { "name": "direction", "label": "Direction", "type": "enum",
                    "values": ["left", "right", "up", "down"] },
                  { "name": "workspace", "label": "Workspace", "type": "workspace" },
                  { "name": "monitor", "label": "Monitor", "type": "string" } ],
      "oneOf": ["direction", "workspace", "monitor"] },
    { "id": "workspace.toggle_special", "label": "Toggle special workspace",
      "dsp": "workspace.toggle_special", "call": "positional",
      "fields": [ { "name": "name", "label": "Name", "type": "string" } ] },
    { "id": "layout", "label": "Layout message", "dsp": "layout", "call": "positional",
      "fields": [ { "name": "message", "label": "Message", "type": "string", "required": true } ] },
    { "id": "submap", "label": "Enter submap", "dsp": "submap", "call": "positional",
      "fields": [ { "name": "name", "label": "Submap", "type": "submap", "required": true } ] },
    { "id": "exit", "label": "Exit Hyprland", "dsp": "exit", "call": "none", "fields": [] }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_catalogue.py`:

```python
import re
from pathlib import Path

import pytest

from hyprkbm.catalogue import (action_errors, describe, dispatcher_lua,
                               load_catalogue, to_dispatcher)
from hyprkbm.luaval import NotReproducible

STUB = Path("/usr/share/hypr/stubs/hl.meta.lua")
CAT = load_catalogue()


def stub_dispatchers(text):
    """Every hl.dsp path the installed Hyprland declares."""
    names, prefix = set(), None
    for line in text.splitlines():
        cls = re.match(r"---@class HL\.Dsp(\w*)Namespace\s*$", line)
        if cls:
            prefix = cls.group(1).lower()
            continue
        if prefix is None:
            continue
        fld = re.match(r"---@field (\w+) fun\(", line)
        if fld:
            names.add(fld.group(1) if prefix == "" else prefix + "." + fld.group(1))
        elif not line.startswith("---@field"):
            prefix = None
    return names


@pytest.mark.skipif(not STUB.exists(), reason="Hyprland's Lua stubs are not installed")
def test_every_catalogue_dispatcher_exists_in_hyprland():
    known = stub_dispatchers(STUB.read_text())
    assert known, "the stub parser found nothing; has the stub format changed?"
    assert {a["dsp"] for a in CAT.values()} <= known


def test_catalogue_entries_are_well_formed():
    for entry in CAT.values():
        assert entry["call"] in ("none", "positional", "table"), entry["id"]
        if entry["call"] == "none":
            assert entry["fields"] == [], entry["id"]
        names = {f["name"] for f in entry["fields"]}
        for f in entry["fields"]:
            assert f["type"] in ("string", "workspace", "enum", "bool", "submap")
            if f["type"] == "enum":
                assert f["values"]
        assert set(entry.get("oneOf", [])) <= names, entry["id"]


def test_actions_become_dispatchers():
    assert to_dispatcher({"kind": "exec_cmd", "args": {"cmd": "kitty"}}, CAT) == \
        {"dsp": "exec_cmd", "args": ["kitty"]}
    assert to_dispatcher({"kind": "window.move", "args": {"workspace": 3}}, CAT) == \
        {"dsp": "window.move", "args": [{"workspace": 3}]}
    assert to_dispatcher({"kind": "window.close"}, CAT) == \
        {"dsp": "window.close", "args": []}
    assert to_dispatcher({"kind": "window.cycle_next", "args": {}}, CAT) == \
        {"dsp": "window.cycle_next", "args": []}
    assert to_dispatcher({"kind": "raw", "lua": "hl.dsp.exit()"}, CAT) == \
        {"raw": "hl.dsp.exit()"}


def test_dispatchers_become_lua():
    assert dispatcher_lua({"dsp": "window.move", "args": [{"workspace": 3}]}) == \
        "hl.dsp.window.move({ workspace = 3 })"
    assert dispatcher_lua({"dsp": "exec_cmd", "args": ["kitty"]}) == \
        'hl.dsp.exec_cmd("kitty")'
    assert dispatcher_lua({"raw": "hl.dsp.layout(\"togglesplit\")"}) == \
        'hl.dsp.layout("togglesplit")'
    with pytest.raises(NotReproducible):
        dispatcher_lua({"__function": "hyprland.lua:3"})


@pytest.mark.parametrize("action,problem", [
    ({"kind": "nope"}, "unknown action"),
    ({"kind": "exec_cmd", "args": {}}, "needs command"),
    ({"kind": "exec_cmd", "args": {"cmd": ""}}, "must be text"),
    ({"kind": "exec_cmd", "args": {"cmd": "x", "extra": 1}}, "no field 'extra'"),
    ({"kind": "window.float", "args": {"action": "flip"}}, "must be one of"),
    ({"kind": "window.move", "args": {}}, "exactly one of"),
    ({"kind": "window.move", "args": {"workspace": 1, "direction": "left"}}, "exactly one of"),
    ({"kind": "window.move", "args": {"workspace": True}}, "workspace number or name"),
    ({"kind": "window.cycle_next", "args": {"next": "yes"}}, "true or false"),
    ({"kind": "raw", "lua": "  "}, "needs some Lua"),
    ("exec_cmd", "must be an object"),
])
def test_bad_actions_are_explained(action, problem):
    errors = action_errors(action, CAT)
    assert any(problem in e for e in errors), errors


def test_good_actions_have_no_errors():
    assert action_errors({"kind": "focus", "args": {"workspace": "e+1"}}, CAT) == []
    assert action_errors({"kind": "window.close"}, CAT) == []
    assert action_errors({"kind": "raw", "lua": "hl.dsp.exit()"}, CAT) == []


def test_describe_reads_like_a_sentence():
    assert describe({"dsp": "exec_cmd", "args": ["kitty"]}, CAT) == "Run a command: kitty"
    assert describe({"dsp": "focus", "args": [{"workspace": 3}]}, CAT) == "Focus (workspace 3)"
    assert describe({"dsp": "window.close", "args": []}, CAT) == "Close window"
    assert describe({"dsp": "window.cycle_next", "args": [{"next": False}]}, CAT) == \
        "Cycle windows (next no)"
    assert describe({"dsp": "group.toggle", "args": []}, CAT) == "hl.dsp.group.toggle()"
    assert describe({"__function": "/home/u/.config/hypr/hyprland.lua:150"}, CAT) == \
        "Lua function (hyprland.lua:150)"
    assert describe({"raw": "hl.dsp.layout(\n  'x')"}, CAT) == "Lua: hl.dsp.layout( 'x')"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_catalogue.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.catalogue'`.

- [ ] **Step 4: Implement catalogue.py**

`lib/hyprkbm/catalogue.py`:

```python
"""The action picker's catalogue, share/actions.json, and the step from a
catalogue action to the dispatcher it stands for."""
import json
import os

from . import SHARE
from .luaval import NotReproducible, to_lua

CATALOGUE = SHARE / "actions.json"


def load_catalogue(path=CATALOGUE):
    data = json.loads(path.read_text())
    return {entry["id"]: entry for entry in data["actions"]}


def _field_problem(field, value):
    kind = field["type"]
    if kind in ("string", "submap"):
        return None if isinstance(value, str) and value != "" else "must be text"
    if kind == "workspace":
        number = isinstance(value, int) and not isinstance(value, bool)
        name = isinstance(value, str) and value != ""
        return None if number or name else "must be a workspace number or name"
    if kind == "enum":
        return None if value in field["values"] else \
            "must be one of %s" % ", ".join(field["values"])
    if kind == "bool":
        return None if isinstance(value, bool) else "must be true or false"
    return "has an unknown type %r" % kind


def action_errors(action, catalogue):
    if not isinstance(action, dict):
        return ["action must be an object"]
    kind = action.get("kind")
    if kind == "raw":
        lua = action.get("lua")
        return [] if isinstance(lua, str) and lua.strip() else ["raw action needs some Lua"]
    entry = catalogue.get(kind)
    if entry is None:
        return ["unknown action %r" % (kind,)]
    args = action.get("args", {})
    if not isinstance(args, dict):
        return ["args must be an object"]

    fields = {f["name"]: f for f in entry["fields"]}
    errors = ["%s has no field %r" % (entry["label"], name) for name in args if name not in fields]
    for name, f in fields.items():
        if name not in args:
            if f.get("required"):
                errors.append("%s needs %s" % (entry["label"], f["label"].lower()))
            continue
        problem = _field_problem(f, args[name])
        if problem:
            errors.append("%s: %s" % (f["label"], problem))
    one_of = entry.get("oneOf")
    if one_of and sum(1 for name in one_of if name in args) != 1:
        errors.append("%s needs exactly one of: %s" % (entry["label"], ", ".join(one_of)))
    return errors


def to_dispatcher(action, catalogue):
    """The dispatcher description a valid action stands for -- the same shape
    the reader gives hand-written binds, so both fingerprint alike."""
    if action["kind"] == "raw":
        return {"raw": action["lua"]}
    entry = catalogue[action["kind"]]
    args = action.get("args", {})
    if entry["call"] == "none":
        return {"dsp": entry["dsp"], "args": []}
    if entry["call"] == "positional":
        values = []
        for f in entry["fields"]:
            if f["name"] not in args:
                break
            values.append(args[f["name"]])
        return {"dsp": entry["dsp"], "args": values}
    table = {f["name"]: args[f["name"]] for f in entry["fields"] if f["name"] in args}
    return {"dsp": entry["dsp"], "args": [table] if table else []}


def dispatcher_lua(dispatcher):
    if "raw" in dispatcher:
        return dispatcher["raw"]
    if "dsp" not in dispatcher:
        raise NotReproducible(dispatcher.get("__function") or "an hl object")
    return "hl.dsp.%s(%s)" % (dispatcher["dsp"],
                              ", ".join(to_lua(a) for a in dispatcher["args"]))


def _plain(value):
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def describe(dispatcher, catalogue):
    """What a bind does, in one line for people."""
    if "raw" in dispatcher:
        return "Lua: " + " ".join(dispatcher["raw"].split())
    if "__function" in dispatcher:
        return "Lua function (%s)" % os.path.basename(dispatcher["__function"])
    if "dsp" not in dispatcher:
        return "Unknown action"
    args = dispatcher["args"]
    entry = next((e for e in catalogue.values() if e["dsp"] == dispatcher["dsp"]), None)
    if entry is None:
        try:
            return dispatcher_lua(dispatcher)
        except NotReproducible:
            return "hl.dsp.%s(…)" % dispatcher["dsp"]
    if entry["call"] == "table" and len(args) == 1 and isinstance(args[0], dict) and args[0]:
        details = ", ".join("%s %s" % (k, _plain(v)) for k, v in sorted(args[0].items()))
        return "%s (%s)" % (entry["label"], details)
    if args:
        return "%s: %s" % (entry["label"], " ".join(_plain(a) for a in args))
    return entry["label"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_catalogue.py -q`
Expected: all pass (the stub test runs on a machine with Hyprland installed, and is skipped in CI).

- [ ] **Step 6: Commit**

```bash
git add share/actions.json lib/hyprkbm/catalogue.py tests/test_catalogue.py
git commit -m "feat: add the action catalogue

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The model: load, merge, validate

**Files:**
- Create: `lib/hyprkbm/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: `reader.ReadResult`, `reader.HandBind`, `reader.reproducible`, `catalogue.action_errors`, `catalogue.to_dispatcher`, `keys.parse`.
- Produces: `model.ModelError(ValueError)`, `model.EMPTY`, `model.FLAGS: set[str]`, `model.load_model(path) -> dict`.
- Produces: `model.Bind` (dataclass: `keys`, `combo`, `submap`, `dispatcher`, `opts`, `source` in `{"hand","hyprkbm","override"}`, `where` (`"hyprland.lua:116"` or the hyprKBM id), `id: str | None`, `allow_conflict: bool`).
- Produces: `model.Merged` (`binds: list[Bind]`, `removed: list[HandBind]`, `touched: dict[combo_id, keys_as_written]`, `stale: list[dict]` each `{"kind": "bind"|"unbind", "id": str|None, "keys": str, "message": str}`; method `conflicts() -> list[list[Bind]]`).
- Produces: `model.merge(model, hand, catalogue) -> Merged` (model must be structurally valid), `model.structure_errors(model, hand, catalogue) -> list[dict]`, `model.validate(model, hand, catalogue) -> list[dict]`; error dicts are `{"id": str | None, "message": str}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_model.py`:

```python
import json
import textwrap

import pytest

from hyprkbm.catalogue import load_catalogue
from hyprkbm.model import ModelError, load_model, merge, structure_errors, validate
from hyprkbm.reader import read_config

CAT = load_catalogue()
DOLPHIN = 'exec_cmd:["dolphin"]'


def hand(paths, source):
    paths.entry.write_text(textwrap.dedent(source))
    return read_config(paths)


def model(**parts):
    return {"version": 1, "submaps": [], "binds": [], "unbinds": [], **parts}


def bind(id, keys, cmd="nautilus", **extra):
    return {"id": id, "keys": keys,
            "action": {"kind": "exec_cmd", "args": {"cmd": cmd}}, **extra}


BASE = """\
    hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))
    hl.bind("SUPER + P", hl.dsp.window.pseudo())
"""


def test_a_missing_model_is_empty(paths):
    assert load_model(paths.model) == model()


def test_a_broken_model_says_so(paths):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text("{oops")
    with pytest.raises(ModelError):
        load_model(paths.model)


def test_merge_keeps_hand_binds_and_adds_hyprkbms(paths):
    m = merge(model(binds=[bind("b1", "SUPER + B", "firefox")]), hand(paths, BASE), CAT)

    assert [(b.keys, b.source) for b in m.binds] == \
        [("SUPER + F", "hand"), ("SUPER + P", "hand"), ("SUPER + B", "hyprkbm")]
    assert m.binds[0].where == "hyprland.lua:1"
    assert m.binds[2].where == "b1"
    assert m.touched == {}


def test_an_override_replaces_the_hand_bind(paths):
    m = merge(model(binds=[bind("b1", "super + f", description="Files",
                                replaces={"keys": "SUPER + F", "submap": "",
                                          "fingerprint": DOLPHIN})]),
              hand(paths, BASE), CAT)

    assert [(b.keys, b.source) for b in m.binds] == \
        [("SUPER + P", "hand"), ("super + f", "override")]
    assert m.binds[1].opts == {"description": "Files"}
    assert m.touched == {"SUPER+f": "SUPER + F"}
    assert [h.where for h in m.removed] == ["hyprland.lua:1"]


def test_an_unbind_removes_the_hand_bind(paths):
    m = merge(model(unbinds=[{"keys": "SUPER + P", "submap": "",
                              "fingerprint": "window.pseudo:[]"}]),
              hand(paths, BASE), CAT)

    assert [b.keys for b in m.binds] == ["SUPER + F"]
    assert m.touched == {"SUPER+p": "SUPER + P"}


def test_targets_that_no_longer_exist_are_stale(paths):
    m = merge(model(binds=[bind("b1", "SUPER + F", replaces={
                        "keys": "SUPER + F", "submap": "", "fingerprint": 'exec_cmd:["thunar"]'})],
                    unbinds=[{"keys": "SUPER + X", "submap": "", "fingerprint": "exit:[]"}]),
              hand(paths, BASE), CAT)

    assert [(s["kind"], s["id"], s["keys"]) for s in m.stale] == \
        [("unbind", None, "SUPER + X"), ("bind", "b1", "SUPER + F")]
    # A stale override is still applied, as an ordinary bind.
    assert [b.source for b in m.binds] == ["hand", "hand", "hyprkbm"]
    assert m.touched == {}


def test_conflicts_group_by_combo_and_submap(paths):
    m = merge(model(binds=[bind("b1", "WIN + f"),
                           bind("b2", "SUPER + P", allowConflict=True),
                           bind("b3", "SUPER + Z", submap="x")],
                    submaps=[{"name": "x", "reset": "escape"}]),
              hand(paths, BASE + 'hl.bind("SUPER + Z", hl.dsp.exit())\n'), CAT)

    assert [[b.where for b in group] for group in m.conflicts()] == \
        [["hyprland.lua:1", "b1"]]


def test_valid_models_pass(paths):
    assert validate(model(binds=[bind("b1", "SUPER + B")]), hand(paths, BASE), CAT) == []


@pytest.mark.parametrize("broken,problem", [
    ({"version": 2}, "version must be 1"),
    ({"binds": {}}, "binds must be a list"),
    ({"binds": [bind("", "SUPER + B")]}, "needs an id"),
    ({"binds": [bind("b1", "SUPER + B"), bind("b1", "SUPER + N")]}, "used twice"),
    ({"binds": [bind("b1", "SUPER + BOGUS + B")]}, "not a modifier"),
    ({"binds": [bind("b1", "SUPER + B", submap="nowhere")]}, "no submap called 'nowhere'"),
    ({"binds": [{"id": "b1", "keys": "SUPER + B", "action": {"kind": "nope"}}]}, "unknown action"),
    ({"binds": [bind("b1", "SUPER + B", flags={"sticky": True})]}, "flags must map"),
    ({"binds": [bind("b1", "SUPER + B", description=3)]}, "description must be text"),
    ({"binds": [bind("b1", "SUPER + B", replaces={"keys": "SUPER + B"})]}, "replaces needs"),
    ({"unbinds": [{"keys": "SUPER + P"}]}, "unbinds[0] needs"),
    ({"submaps": [{"name": "x"}]}, "needs a reset key"),
    ({"submaps": [{"name": "x", "reset": "escape"}, {"name": "x", "reset": "escape"}]},
     "defined twice"),
])
def test_structural_problems_are_reported(paths, broken, problem):
    errors = structure_errors(model(**broken), hand(paths, BASE), CAT)
    assert any(problem in e["message"] for e in errors), errors


def test_a_model_that_is_not_an_object_is_reported(paths):
    errors = structure_errors([], hand(paths, BASE), CAT)
    assert "JSON object" in errors[0]["message"]


def test_a_submap_from_hyprland_lua_cannot_be_defined_again(paths):
    h = hand(paths, 'hl.define_submap("resize", "escape", function() end)\n')
    errors = structure_errors(model(submaps=[{"name": "resize", "reset": "escape"}]), h, CAT)
    assert "already defined in hyprland.lua" in errors[0]["message"]
    # ...but binds can be added to it.
    assert validate(model(binds=[bind("b1", "right", submap="resize")]), h, CAT) == []


def test_conflicts_involving_hyprkbm_block_and_name_the_bind(paths):
    errors = validate(model(binds=[bind("b1", "SUPER + F")]), hand(paths, BASE), CAT)

    assert errors == [{"id": "b1", "message":
                       "SUPER + F is bound 2 times: hyprland.lua:1, b1"}]


def test_conflicts_only_within_hyprland_lua_do_not_block(paths):
    h = hand(paths, BASE + 'hl.bind("SUPER + F", hl.dsp.exit())\n')
    assert validate(model(), h, CAT) == []


def test_allowing_a_conflict_unblocks_it(paths):
    errors = validate(model(binds=[bind("b1", "SUPER + F", allowConflict=True)]),
                      hand(paths, BASE), CAT)
    assert errors == []


def test_a_function_bind_sharing_a_touched_combo_blocks_the_override(paths):
    h = hand(paths, """\
        hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))
        hl.define_submap("x", "escape", function()
            hl.bind("SUPER + F", function() end)
        end)
    """)
    errors = validate(model(binds=[bind("b1", "SUPER + F", replaces={
        "keys": "SUPER + F", "submap": "", "fingerprint": DOLPHIN})]), h, CAT)

    assert len(errors) == 1
    assert "hyprland.lua:3" in errors[0]["message"]
    assert "Lua function" in errors[0]["message"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_model.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.model'`.

- [ ] **Step 3: Implement model.py**

`lib/hyprkbm/model.py`:

```python
"""keybinds.json -- hyprKBM's own binds, overrides, unbinds and submaps --
and how it combines with the hand-written binds into what Hyprland ends up
with."""
import copy
import json
from collections import defaultdict
from dataclasses import dataclass, field

from .catalogue import action_errors, to_dispatcher
from .keys import KeyParseError, parse
from .reader import reproducible

VERSION = 1
EMPTY = {"version": VERSION, "submaps": [], "binds": [], "unbinds": []}
FLAGS = {"repeating", "locked", "release", "non_consuming", "transparent",
         "ignore_mods", "dont_inhibit", "long_press", "submap_universal", "click",
         "drag", "mouse", "allow_input_capture"}


class ModelError(ValueError):
    pass


def load_model(path):
    try:
        text = path.read_text()
    except FileNotFoundError:
        return copy.deepcopy(EMPTY)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ModelError("%s is not valid JSON: %s" % (path, exc)) from exc


@dataclass
class Bind:
    """One bind as Hyprland will have it after an apply."""
    keys: str
    combo: str | None
    submap: str
    dispatcher: dict
    opts: dict
    source: str
    where: str
    id: str | None = None
    allow_conflict: bool = False


@dataclass
class Merged:
    binds: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    touched: dict = field(default_factory=dict)
    stale: list = field(default_factory=list)

    def conflicts(self):
        groups = defaultdict(list)
        for b in self.binds:
            if b.combo is not None and not b.allow_conflict:
                groups[(b.submap, b.combo)].append(b)
        return [group for group in groups.values() if len(group) > 1]


def bind_opts(bind):
    opts = {name: True for name, on in (bind.get("flags") or {}).items() if on is True}
    if bind.get("description"):
        opts["description"] = bind["description"]
    return opts


def _matches(hand_bind, target):
    try:
        combo = parse(target["keys"]).id
    except KeyParseError:
        return False
    return (hand_bind.combo == combo
            and hand_bind.submap == target.get("submap", "")
            and hand_bind.fingerprint == target.get("fingerprint"))


def merge(model, hand, catalogue):
    merged = Merged()
    superseded = set()

    def supersede(target):
        hits = [h for h in hand.binds if _matches(h, target)]
        for h in hits:
            if id(h) not in superseded:
                superseded.add(id(h))
                merged.removed.append(h)
            merged.touched.setdefault(h.combo, h.keys)
        return bool(hits)

    for u in model.get("unbinds", []):
        if not supersede(u):
            merged.stale.append({
                "kind": "unbind", "id": None, "keys": u["keys"],
                "message": "The bind on %s this removes is no longer in %s; "
                           "the unbind does nothing." % (u["keys"], "hyprland.lua")})

    own = []
    for b in model.get("binds", []):
        replaced = False
        if "replaces" in b:
            replaced = supersede(b["replaces"])
            if not replaced:
                merged.stale.append({
                    "kind": "bind", "id": b["id"], "keys": b["keys"],
                    "message": "The hyprland.lua bind this replaced is gone; it is "
                               "now an ordinary bind."})
        own.append(Bind(keys=b["keys"], combo=parse(b["keys"]).id,
                        submap=b.get("submap", ""),
                        dispatcher=to_dispatcher(b["action"], catalogue),
                        opts=bind_opts(b), source="override" if replaced else "hyprkbm",
                        where=b["id"], id=b["id"],
                        allow_conflict=b.get("allowConflict") is True))

    for h in hand.binds:
        if id(h) not in superseded:
            merged.binds.append(Bind(keys=h.keys, combo=h.combo, submap=h.submap,
                                     dispatcher=h.dispatcher, opts=h.opts,
                                     source="hand", where=h.where))
    merged.binds.extend(own)
    return merged


def _valid_target(target):
    if not isinstance(target, dict):
        return False
    if not all(isinstance(target.get(k), str) for k in ("keys", "submap", "fingerprint")):
        return False
    try:
        parse(target["keys"])
    except KeyParseError:
        return False
    return True


def structure_errors(model, hand, catalogue):
    """Everything wrong with the file itself. merge() needs none of these."""
    errors = []

    def err(message, bind_id=None):
        errors.append({"id": bind_id, "message": message})

    if not isinstance(model, dict):
        err("keybinds.json must hold a JSON object")
        return errors
    if model.get("version") != VERSION:
        err("keybinds.json version must be %d" % VERSION)
        return errors
    for name in ("submaps", "binds", "unbinds"):
        if not isinstance(model.get(name, []), list):
            err("%s must be a list" % name)
    if errors:
        return errors

    own_submaps = set()
    for i, s in enumerate(model.get("submaps", [])):
        name = s.get("name") if isinstance(s, dict) else None
        if not isinstance(name, str) or not name:
            err("submaps[%d] needs a name" % i)
            continue
        if name in own_submaps:
            err("submap %r is defined twice" % name)
        if name in hand.submap_names:
            err("submap %r is already defined in hyprland.lua; add binds to it "
                "without defining it again" % name)
        if not isinstance(s.get("reset"), str) or not s["reset"]:
            err("submap %r needs a reset key" % name)
        own_submaps.add(name)
    known_submaps = own_submaps | hand.submap_names | {""}

    seen = set()
    for i, b in enumerate(model.get("binds", [])):
        if not isinstance(b, dict):
            err("binds[%d] must be an object" % i)
            continue
        bid = b.get("id")
        if not isinstance(bid, str) or not bid:
            err("binds[%d] needs an id" % i)
            bid = None
        elif bid in seen:
            err("id %r is used twice" % bid, bid)
        else:
            seen.add(bid)
        label = b["keys"] if isinstance(b.get("keys"), str) else "binds[%d]" % i
        try:
            parse(b.get("keys"))
        except KeyParseError as exc:
            err("%s: %s" % (label, exc), bid)
        if b.get("submap", "") not in known_submaps:
            err("%s: no submap called %r" % (label, b.get("submap")), bid)
        for problem in action_errors(b.get("action"), catalogue):
            err("%s: %s" % (label, problem), bid)
        if not isinstance(b.get("description", ""), str):
            err("%s: description must be text" % label, bid)
        flags = b.get("flags", {})
        if not isinstance(flags, dict) or any(
                k not in FLAGS or not isinstance(v, bool) for k, v in flags.items()):
            err("%s: flags must map %s to true or false"
                % (label, ", ".join(sorted(FLAGS))), bid)
        if not isinstance(b.get("allowConflict", False), bool):
            err("%s: allowConflict must be true or false" % label, bid)
        if "replaces" in b and not _valid_target(b["replaces"]):
            err("%s: replaces needs keys, submap and fingerprint" % label, bid)

    for i, u in enumerate(model.get("unbinds", [])):
        if not _valid_target(u):
            err("unbinds[%d] needs keys, submap and fingerprint" % i)
    return errors


def validate(model, hand, catalogue):
    """Everything that would stop an apply."""
    errors = structure_errors(model, hand, catalogue)
    if errors:
        return errors

    merged = merge(model, hand, catalogue)
    for group in merged.conflicts():
        own = [b for b in group if b.source != "hand"]
        # Duplicates purely within hyprland.lua are the user's own to sort
        # out; refusing every apply until they do would help nobody.
        if not own:
            continue
        submap = "" if group[0].submap == "" else " in submap %s" % group[0].submap
        errors.append({"id": own[0].id, "message": "%s%s is bound %d times: %s" % (
            group[0].keys, submap, len(group), ", ".join(b.where for b in group))})

    for combo, keys in merged.touched.items():
        for b in merged.binds:
            if b.source == "hand" and b.combo == combo and not reproducible(b.dispatcher, b.opts):
                errors.append({"id": None, "message": (
                    "%s also has a bind at %s whose action is a Lua function. hyprKBM "
                    "replaces a bind by unbinding its keys and re-creating the others "
                    "on them, and it cannot re-create that one; change it in "
                    "hyprland.lua instead." % (keys, b.where))})
    return errors
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_model.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/model.py tests/test_model.py
git commit -m "feat: merge keybinds.json with hand binds and validate it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Rendering keybinds.lua

**Files:**
- Create: `lib/hyprkbm/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `model.merge`, `model.Bind`, `catalogue.dispatcher_lua`, `luaval.string`, `luaval.to_lua`.
- Produces: `render.render(model, hand, catalogue) -> str`, `render.bind_line(keys, dispatcher, opts) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:

```python
import textwrap

from hyprkbm.catalogue import load_catalogue
from hyprkbm.reader import read_config
from hyprkbm.render import bind_line, render

CAT = load_catalogue()

HAND = """\
    local mainMod = "SUPER"
    hl.bind(mainMod .. " + F", hl.dsp.exec_cmd("dolphin"))
    hl.bind(mainMod .. " + P", hl.dsp.window.pseudo())
    hl.define_submap("resize", "escape", function()
        hl.bind("SUPER + F", hl.dsp.window.resize())
    end)
"""

MODEL = {
    "version": 1,
    "submaps": [{"name": "move", "reset": "escape"}],
    "binds": [
        {"id": "b1", "keys": "SUPER + F", "submap": "",
         "action": {"kind": "exec_cmd", "args": {"cmd": "nautilus"}},
         "description": "File manager",
         "replaces": {"keys": "SUPER + F", "submap": "", "fingerprint": 'exec_cmd:["dolphin"]'}},
        {"id": "b2", "keys": "SUPER + B",
         "action": {"kind": "exec_cmd", "args": {"cmd": "firefox"}},
         "flags": {"repeating": False, "locked": True}},
        {"id": "b3", "keys": "right", "submap": "move",
         "action": {"kind": "window.move", "args": {"direction": "right"}}},
    ],
    "unbinds": [{"keys": "SUPER + P", "submap": "", "fingerprint": "window.pseudo:[]"}],
}

EXPECTED = '''\
-- Generated by hyprKBM from keybinds.json. Edits here are overwritten: change
-- binds in the hyprKBM panel, or edit keybinds.json and run `hyprkbm --apply`.

-- Submaps
hl.define_submap("move", "escape", function() end)

-- SUPER + F: replaces binds from hyprland.lua
hl.unbind("SUPER + F")
hl.define_submap("resize", function()
    hl.bind("SUPER + F", hl.dsp.window.resize())
end)

-- SUPER + P: replaces binds from hyprland.lua
hl.unbind("SUPER + P")

-- hyprKBM's binds
hl.bind("SUPER + F", hl.dsp.exec_cmd("nautilus"), { description = "File manager" })
hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"), { locked = true })
hl.define_submap("move", function()
    hl.bind("right", hl.dsp.window.move({ direction = "right" }))
end)
'''


def hand(paths, source=HAND):
    paths.entry.write_text(textwrap.dedent(source))
    return read_config(paths)


def test_render_writes_submaps_then_replaced_combos_then_own_binds(paths):
    assert render(MODEL, hand(paths), CAT) == EXPECTED


def test_an_empty_model_renders_only_the_header(paths):
    text = render({"version": 1, "submaps": [], "binds": [], "unbinds": []}, hand(paths), CAT)
    assert text.count("\n") == 2
    assert text.startswith("-- Generated by hyprKBM")


def test_bind_line_omits_empty_options():
    assert bind_line("SUPER + C", {"dsp": "window.close", "args": []}, {}) == \
        'hl.bind("SUPER + C", hl.dsp.window.close())'


def test_raw_lua_is_written_verbatim():
    assert bind_line("SUPER + G", {"raw": "function() hl.exec_cmd(\"x\") end"}, {}) == \
        'hl.bind("SUPER + G", function() hl.exec_cmd("x") end)'


def test_what_is_rendered_reads_back_as_intended(paths, tmp_path):
    """Round trip: the rendered file, run through the reader on its own, binds
    exactly hyprKBM's binds plus the re-created hand ones."""
    text = render(MODEL, hand(paths), CAT)
    paths.entry.write_text(text)

    result = read_config(paths)

    assert result.error is None
    assert [(b.submap, b.keys, b.fingerprint, b.opts) for b in result.binds] == [
        ("resize", "SUPER + F", "window.resize:[]", {}),
        ("", "SUPER + F", 'exec_cmd:["nautilus"]', {"description": "File manager"}),
        ("", "SUPER + B", 'exec_cmd:["firefox"]', {"locked": True}),
        ("move", "right", 'window.move:[{"direction":"right"}]', {}),
    ]
    assert result.submaps[0]["name"] == "move"
    assert result.submaps[0]["reset"] == "escape"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_render.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.render'`.

- [ ] **Step 3: Implement render.py**

`lib/hyprkbm/render.py`:

```python
"""keybinds.lua, written from keybinds.json and what hyprland.lua already binds.

hl.unbind drops a combo in every submap at once, so a hand-written bind is
replaced by unbinding its whole combo and re-creating every other hand bind on
it, before hyprKBM's own binds go on top.
"""
from collections import defaultdict

from .catalogue import dispatcher_lua
from .luaval import string, to_lua
from .model import merge

HEADER = """\
-- Generated by hyprKBM from keybinds.json. Edits here are overwritten: change
-- binds in the hyprKBM panel, or edit keybinds.json and run `hyprkbm --apply`.
"""
INDENT = "    "


def bind_line(keys, dispatcher, opts):
    args = [string(keys), dispatcher_lua(dispatcher)]
    if opts:
        args.append(to_lua(opts))
    return "hl.bind(%s)" % ", ".join(args)


def _by_submap(binds):
    groups = defaultdict(list)
    for b in binds:
        groups[b.submap].append(b)
    # The global map first, then submaps by name.
    return [(name, groups[name]) for name in sorted(groups, key=lambda n: (n != "", n))]


def _emit(lines, binds):
    for submap, group in _by_submap(binds):
        if submap == "":
            lines.extend(bind_line(b.keys, b.dispatcher, b.opts) for b in group)
            continue
        # The two-argument form appends to a submap without touching its reset.
        lines.append("hl.define_submap(%s, function()" % string(submap))
        lines.extend(INDENT + bind_line(b.keys, b.dispatcher, b.opts) for b in group)
        lines.append("end)")


def render(model, hand, catalogue):
    merged = merge(model, hand, catalogue)
    lines = [HEADER]

    submaps = model.get("submaps", [])
    if submaps:
        lines.append("-- Submaps")
        for s in submaps:
            lines.append("hl.define_submap(%s, %s, function() end)"
                         % (string(s["name"]), string(s["reset"])))
        lines.append("")

    for combo in sorted(merged.touched):
        keys = merged.touched[combo]
        lines.append("-- %s: replaces binds from hyprland.lua" % " ".join(keys.split()))
        lines.append("hl.unbind(%s)" % string(keys))
        _emit(lines, [b for b in merged.binds if b.source == "hand" and b.combo == combo])
        lines.append("")

    own = [b for b in merged.binds if b.source != "hand"]
    if own:
        lines.append("-- hyprKBM's binds")
        _emit(lines, own)

    return "\n".join(lines).rstrip("\n") + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_render.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/render.py tests/test_render.py
git commit -m "feat: render keybinds.lua from the merged model

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Applying, with a dry run and rollback

**Files:**
- Create: `lib/hyprkbm/apply.py`, `bin/hyprkbm-apply`
- Modify: `tests/conftest.py` (add the `stubs` fixture)
- Test: `tests/test_apply.py`

**Interfaces:**
- Consumes: `read_config`, `validate`, `render`, `load_catalogue`, `luaval.string`, `Paths`.
- Produces: `apply.apply(model, paths, catalogue=None) -> dict`, `apply.live(paths) -> dict`, `apply.hyprctl(*args) -> tuple[bool, str]`, `apply.backup(paths, now=None) -> Path | None`, `apply.KEEP_BACKUPS = 30`, `apply.DRY_RUN` (Lua template with one `%s` for the quoted path). Results: `{"ok": True, "backup": str | None}` or `{"ok": False, "errors": [{"id", "message"}]}`.
- Produces: `bin/hyprkbm-apply` (stdin model → JSON on stdout; `--live`); exit 0 on ok, 1 on failure, 2 on usage error.
- Produces (conftest): `stubs` fixture → `Stubs` with `respond(**queues)` (queues keyed `dry`, `load`, `reload`, `eval`; each a list of answers consumed in order, default `"ok"`; an answer starting with `error` exits 7), `calls() -> list[list[str]]` (each `[program, *args]`), `hyprctl_kinds() -> list[str]`, and `root` (the stub directory, first on `PATH`). Stubs exist for `hyprctl`, `notify-send` and `systemctl`.

- [ ] **Step 1: Add the stub executables to conftest**

Append to `tests/conftest.py`:

```python
import json  # noqa: E402

HYPRCTL = r'''#!%(python)s
"""Stands in for hyprctl: logs each call, answers from responses.json."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(["hyprctl"] + args) + "\n")
path = os.path.join(here, "responses.json")
responses = json.load(open(path)) if os.path.exists(path) else {}
if args[:1] == ["eval"]:
    kind = "dry" if "loadfile" in args[1] else "load" if "dofile" in args[1] else "eval"
else:
    kind = args[0] if args else ""
queue = responses.get(kind, [])
answer = queue.pop(0) if queue else "ok"
json.dump(responses, open(path, "w"))
print(answer)
sys.exit(7 if answer.startswith("error") else 0)
'''

LOGGER = r'''#!%(python)s
"""Stands in for a command whose only effect matters to the test: being run."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\n")
'''


class Stubs:
    def __init__(self, root):
        self.root = root

    def respond(self, **queues):
        (self.root / "responses.json").write_text(json.dumps(queues))

    def calls(self):
        log = self.root / "calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def hyprctl_kinds(self):
        kinds = []
        for call in self.calls():
            if call[0] != "hyprctl":
                continue
            if call[1] == "eval":
                kinds.append("dry" if "loadfile" in call[2] else "load")
            else:
                kinds.append(call[1])
        return kinds


@pytest.fixture
def stubs(tmp_path, monkeypatch):
    root = tmp_path / "stubs"
    root.mkdir()
    for name, body in (("hyprctl", HYPRCTL), ("notify-send", LOGGER), ("systemctl", LOGGER)):
        script = root / name
        script.write_text(body % {"python": sys.executable})
        script.chmod(0o755)
    monkeypatch.setenv("PATH", "%s:/usr/bin:/bin" % root)
    return Stubs(root)
```

- [ ] **Step 2: Write the failing tests**

`tests/test_apply.py`:

```python
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from hyprkbm import apply as applying
from hyprkbm.apply import apply, backup, live

ROOT = Path(__file__).resolve().parents[1]
GOOD = {"version": 1, "submaps": [], "unbinds": [],
        "binds": [{"id": "b1", "keys": "SUPER + B",
                   "action": {"kind": "exec_cmd", "args": {"cmd": "firefox"}}}]}
OTHER = {"version": 1, "submaps": [], "unbinds": [],
         "binds": [{"id": "b2", "keys": "SUPER + N",
                    "action": {"kind": "exec_cmd", "args": {"cmd": "foot"}}}]}


def test_first_apply_dry_runs_writes_reloads_and_loads(paths, stubs):
    result = apply(GOOD, paths)

    assert result == {"ok": True, "backup": None}
    assert json.loads(paths.model.read_text()) == GOOD
    assert 'hl.bind("SUPER + B", hl.dsp.exec_cmd("firefox"))' in paths.lua.read_text()
    assert stubs.hyprctl_kinds() == ["dry", "reload", "load"]
    load = [c for c in stubs.calls() if c[:2] == ["hyprctl", "eval"]][-1]
    assert load[2] == 'dofile("%s")' % paths.lua
    assert paths.marker.exists(), "the watcher must be told this reload was ours"
    assert not list(paths.config_dir.glob(".keybinds.lua.staged*"))


def test_a_second_apply_backs_up_the_first(paths, stubs):
    apply(GOOD, paths)
    first_lua = paths.lua.read_text()

    result = apply(OTHER, paths)

    saved = Path(result["backup"])
    assert json.loads((saved / "keybinds.json").read_text()) == GOOD
    assert (saved / "keybinds.lua").read_text() == first_lua
    assert json.loads(paths.model.read_text()) == OTHER


def test_an_invalid_model_changes_nothing(paths, stubs):
    bad = {"version": 1, "submaps": [], "unbinds": [],
           "binds": [{"id": "b1", "keys": "SUPER + B", "action": {"kind": "nope"}}]}

    result = apply(bad, paths)

    assert result["ok"] is False
    assert result["errors"][0]["id"] == "b1"
    assert not paths.model.exists()
    assert stubs.calls() == []


def test_a_failed_dry_run_changes_nothing(paths, stubs):
    stubs.respond(dry=["error: hl.window.move: unrecognized arguments"])

    result = apply(GOOD, paths)

    assert result["ok"] is False
    assert "unrecognized arguments" in result["errors"][0]["message"]
    assert not paths.model.exists()
    assert stubs.hyprctl_kinds() == ["dry"]


def test_a_refused_load_puts_the_previous_binds_back(paths, stubs):
    apply(GOOD, paths)
    before = (paths.model.read_text(), paths.lua.read_text())
    stubs.respond(load=["error: boom"])

    result = apply(OTHER, paths)

    assert result["ok"] is False
    assert "boom" in result["errors"][0]["message"]
    assert (paths.model.read_text(), paths.lua.read_text()) == before
    assert stubs.hyprctl_kinds()[-5:] == ["dry", "reload", "load", "reload", "load"]
    assert any(c[0] == "notify-send" for c in stubs.calls())


def test_a_refused_first_load_leaves_no_files(paths, stubs):
    stubs.respond(load=["error: boom"])

    apply(GOOD, paths)

    assert not paths.model.exists()
    assert not paths.lua.exists()
    assert stubs.hyprctl_kinds() == ["dry", "reload", "load", "reload"]


def test_a_broken_hyprland_lua_blocks_applying(paths, stubs):
    paths.entry.write_text("this is not lua\n")

    result = apply(GOOD, paths)

    assert result["ok"] is False
    assert "could not be read" in result["errors"][0]["message"]
    assert stubs.calls() == []


def test_backups_are_pruned_to_the_newest_thirty(paths):
    paths.config_dir.mkdir(parents=True)
    paths.model.write_text("{}")
    start = datetime(2026, 1, 1)
    for i in range(32):
        backup(paths, now=start + timedelta(minutes=i))

    kept = sorted(p.name for p in paths.backups.iterdir())
    assert len(kept) == applying.KEEP_BACKUPS
    assert kept[0] == (start + timedelta(minutes=2)).strftime("%Y%m%dT%H%M%S%f")


def test_live_loads_the_file_without_reloading(paths, stubs):
    apply(GOOD, paths)
    before = len(stubs.hyprctl_kinds())

    assert live(paths) == {"ok": True}
    assert stubs.hyprctl_kinds()[before:] == ["load"]


def test_live_with_nothing_applied_does_nothing(paths, stubs):
    assert live(paths) == {"ok": True}
    assert stubs.calls() == []


def test_live_failures_are_reported_and_notified(paths, stubs):
    apply(GOOD, paths)
    stubs.respond(load=["error: boom"])

    result = live(paths)

    assert result["ok"] is False
    assert any(c[0] == "notify-send" for c in stubs.calls())


def test_the_executable_applies_a_model_from_stdin(home_env, stubs, paths):
    env = dict(home_env, PATH=os.environ["PATH"])
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply")],
                         input=json.dumps(GOOD), capture_output=True, text=True, env=env)

    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["ok"] is True
    assert paths.lua.exists()


def test_the_executable_rejects_garbage(home_env, stubs):
    env = dict(home_env, PATH=os.environ["PATH"])
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply")],
                         input="{nope", capture_output=True, text=True, env=env)

    assert res.returncode == 1
    assert "not JSON" in json.loads(res.stdout)["errors"][0]["message"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_apply.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'hyprkbm.apply'`.

- [ ] **Step 4: Implement apply.py and the executable**

`lib/hyprkbm/apply.py`:

```python
"""The only code that writes keybinds.json and keybinds.lua, and the only
code that hands them to Hyprland.

An apply reloads Hyprland first, so the new binds always go onto what
hyprland.lua alone produces rather than on top of the previous apply's.
A reload emits configreloaded; the marker file tells hyprkbm-watch that this
one was ours and already handled.
"""
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime

from .catalogue import load_catalogue
from .luaval import string
from .model import validate
from .reader import read_config
from .render import render

KEEP_BACKUPS = 30

# Runs the file with hl.bind, hl.unbind and hl.define_submap stubbed out.
# Hyprland checks a dispatcher's arguments when it is constructed, so this
# finds a bad argument or a syntax error without a single bind changing.
DRY_RUN = """\
local stub = {
    bind = function() end,
    unbind = function() end,
    define_submap = function(_, a, b)
        local f = type(a) == "function" and a or b
        if f then f() end
    end,
}
local env = setmetatable({ hl = setmetatable(stub, { __index = hl }) }, { __index = _G })
assert(loadfile(%s, "t", env))()
"""


def hyprctl(*args):
    try:
        res = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    out = (res.stdout + res.stderr).strip()
    # A failed eval exits 7 and prints "error: ..."; check both, in case a
    # future hyprctl changes one of them.
    return res.returncode == 0 and not out.lower().startswith("error"), out


def _failure(*messages):
    return {"ok": False, "errors": [{"id": None, "message": m} for m in messages]}


def notify(message):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "hyprKBM", "hyprKBM", message],
                       capture_output=True)


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.replace(tmp, path)


def backup(paths, now=None):
    present = [p for p in (paths.model, paths.lua) if p.exists()]
    if not present:
        return None
    target = paths.backups / (now or datetime.now()).strftime("%Y%m%dT%H%M%S%f")
    target.mkdir(parents=True)
    for p in present:
        shutil.copy2(p, target / p.name)
    for old in sorted(d for d in paths.backups.iterdir() if d.is_dir())[:-KEEP_BACKUPS]:
        shutil.rmtree(old)
    return target


def _restore(paths, saved):
    for p in (paths.model, paths.lua):
        if saved is not None and (saved / p.name).exists():
            shutil.copy2(saved / p.name, p)
        elif p.exists():
            p.unlink()


def _mark_self_reload(paths):
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    paths.marker.touch()


def _load(paths):
    _mark_self_reload(paths)
    ok, out = hyprctl("reload")
    if not ok:
        return False, "hyprctl reload failed: " + out
    if not paths.lua.exists():
        return True, ""
    return hyprctl("eval", "dofile(%s)" % string(str(paths.lua)))


def apply(model, paths, catalogue=None):
    catalogue = catalogue or load_catalogue()
    hand = read_config(paths)
    if hand.error:
        return _failure("%s could not be read, so nothing was changed: %s"
                        % (paths.entry.name, hand.error))
    errors = validate(model, hand, catalogue)
    if errors:
        return {"ok": False, "errors": errors}

    text = render(model, hand, catalogue)
    staged = paths.config_dir / ".keybinds.lua.staged"
    write_atomic(staged, text)
    try:
        ok, out = hyprctl("eval", DRY_RUN % string(str(staged)))
    finally:
        staged.unlink()
    if not ok:
        return _failure("Hyprland rejected the new keybinds, so nothing was changed: " + out)

    saved = backup(paths)
    write_atomic(paths.model, json.dumps(model, indent=2, ensure_ascii=False) + "\n")
    write_atomic(paths.lua, text)
    ok, out = _load(paths)
    if ok:
        return {"ok": True, "backup": str(saved) if saved else None}

    _restore(paths, saved)
    _load(paths)
    message = "Hyprland refused the new keybinds, and the previous ones were put back: " + out
    notify(message)
    return _failure(message)


def live(paths):
    """Put keybinds.lua back on top of whatever hyprland.lua just did."""
    if not paths.lua.exists():
        return {"ok": True}
    ok, out = hyprctl("eval", "dofile(%s)" % string(str(paths.lua)))
    if ok:
        return {"ok": True}
    notify("Your hyprKBM keybinds could not be applied: " + out)
    return _failure(out)
```

`bin/hyprkbm-apply`:

```python
#!/usr/bin/env python3
"""Apply hyprKBM's keybinds to Hyprland.

  hyprkbm-apply          validate the model on stdin, back up, write, apply
  hyprkbm-apply --live   re-apply keybinds.lua to the running Hyprland as it is

Prints a JSON result. Exits 1 when nothing was applied.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from hyprkbm.apply import apply, live  # noqa: E402
from hyprkbm.paths import Paths  # noqa: E402


def main(argv):
    paths = Paths.from_env()
    if argv == ["--live"]:
        result = live(paths)
    elif not argv:
        try:
            model = json.load(sys.stdin)
        except ValueError as exc:
            result = {"ok": False, "errors": [{
                "id": None, "message": "the model on stdin is not JSON: %s" % exc}]}
        else:
            result = apply(model, paths)
    else:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Run: `chmod +x bin/hyprkbm-apply`

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add lib/hyprkbm/apply.py bin/hyprkbm-apply tests/conftest.py tests/test_apply.py
git commit -m "feat: apply keybinds with a dry run, backups and rollback

The rendered file is first run inside Hyprland with hl.bind stubbed out,
which checks every dispatcher's arguments without changing a bind. Only
then are the files written, Hyprland reloaded and the file loaded; if
Hyprland still refuses, the previous files go back on disk and on screen.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The watcher service

**Files:**
- Create: `bin/hyprkbm-watch`, `systemd/hyprkbm-watch.service`
- Test: `tests/test_watch.py`

**Interfaces:**
- Consumes: `Paths.marker`, `Paths.lock`, `Paths.runtime_dir`; `bin/hyprkbm-apply --live`.
- Consumes: `hyprkbm.marker` (`expect_reload(paths)`, `consume(paths, now=None) -> bool`, `MAX_AGE = 10.0`), added as a fix to Task 7.
- Produces: module functions (loaded in tests via importlib): `consume_marker(paths, now=None) -> bool` (delegates to `marker.consume`), `read_events(sock, on_reload) -> None` (returns when the socket closes).

- [ ] **Step 1: Write the failing tests**

`tests/test_watch.py`:

```python
"""hyprkbm-watch: what keeps the binds on screen after a reload.

A reload re-runs hyprland.lua and drops everything applied with eval, so the
watcher answers every configreloaded with `hyprkbm-apply --live` -- except
the reload hyprkbm-apply itself made, which it has already handled.
"""
import importlib.machinery
import importlib.util
import os
import socket
import time
from pathlib import Path

from hyprkbm import marker

WATCH = Path(__file__).resolve().parents[1] / "bin" / "hyprkbm-watch"


def load():
    loader = importlib.machinery.SourceFileLoader("hyprkbm_watch", str(WATCH))
    spec = importlib.util.spec_from_loader("hyprkbm_watch", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


watch = load()


def replay(chunks):
    reloads = []
    ours, theirs = socket.socketpair()
    for chunk in chunks:
        theirs.sendall(chunk)
    theirs.shutdown(socket.SHUT_WR)
    with ours:
        watch.read_events(ours, lambda: reloads.append(True))
    theirs.close()
    return len(reloads)


def test_a_reload_triggers_a_reapply():
    assert replay([b"configreloaded>>\n"]) == 1


def test_other_events_do_nothing():
    assert replay([b"activewindow>>kitty,~\n", b"workspace>>2\n"]) == 0


def test_an_event_split_across_reads_still_counts():
    assert replay([b"workspace>>2\nconfigrel", b"oaded>>\n"]) == 1


def test_a_fresh_marker_is_consumed_and_skips_the_reapply(paths):
    marker.expect_reload(paths)

    assert watch.consume_marker(paths) is True
    assert not paths.marker.exists()
    assert watch.consume_marker(paths) is False


def test_an_old_marker_is_removed_but_does_not_skip(paths):
    marker.expect_reload(paths)
    old = time.time() - marker.MAX_AGE - 5
    os.utime(paths.marker, (old, old))

    assert watch.consume_marker(paths) is False
    assert not paths.marker.exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_watch.py -q`
Expected: FAIL with `FileNotFoundError` for `bin/hyprkbm-watch`.

- [ ] **Step 3: Implement the watcher and its unit**

`bin/hyprkbm-watch`:

```python
#!/usr/bin/env python3
"""Keep hyprKBM's keybinds applied to Hyprland.

hyprKBM applies keybinds.lua to the running compositor with `hyprctl eval`,
so hyprland.lua needs no line loading it -- but a reload re-runs hyprland.lua
and drops everything eval set, and a new login starts from hyprland.lua alone.
This listens on Hyprland's event socket and answers every `configreloaded`
with `hyprkbm-apply --live`, and applies once when it starts, which the
systemd user unit makes happen at login.

hyprkbm-apply reloads Hyprland itself before applying; it leaves a marker so
the reload it caused is not answered twice.
"""
import errno
import fcntl
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from hyprkbm import marker  # noqa: E402
from hyprkbm.paths import Paths  # noqa: E402

RELOADED = "configreloaded"
RECONNECT_SECONDS = 2.0
SELF_DIR = os.path.dirname(os.path.realpath(__file__))


def claim_single_instance(paths):
    """Two watchers would both answer every reload. The handle is never
    closed: the lock lasts as long as this process does."""
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    handle = open(paths.lock, "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            # Status 0: the job is being done, and a failure here would have
            # systemd restart this one in a loop.
            print("another hyprkbm-watch already holds %s" % paths.lock, file=sys.stderr)
            sys.exit(0)
        raise
    return handle


def apply_command():
    sibling = os.path.join(SELF_DIR, "hyprkbm-apply")
    if os.access(sibling, os.X_OK):
        return sibling
    from shutil import which
    found = which("hyprkbm-apply")
    if not found:
        sys.exit("hyprkbm-apply not found next to %s or on PATH" % SELF_DIR)
    return found


def socket_path():
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not signature:
        sys.exit("HYPRLAND_INSTANCE_SIGNATURE unset -- not inside a Hyprland session")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid())
    return os.path.join(runtime, "hypr", signature, ".socket2.sock")


def run_live(command):
    res = subprocess.run([command, "--live"], capture_output=True, text=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print("%s apply --live rc=%d %s" % (stamp, res.returncode,
                                        (res.stdout + res.stderr).strip()), flush=True)


def consume_marker(paths, now=None):
    """True when the reload was hyprkbm-apply's own, which applies the binds
    itself. The marker is a count, kept by hyprkbm.marker, because an apply
    that rolls back reloads twice."""
    return marker.consume(paths, now)


def read_events(sock, on_reload):
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return
        buffer += chunk
        *lines, buffer = buffer.split(b"\n")
        for line in lines:
            if line.decode("utf-8", "replace").split(">>", 1)[0] == RELOADED:
                on_reload()


def main():
    paths = Paths.from_env()
    _lock = claim_single_instance(paths)
    command = apply_command()
    path = socket_path()

    def on_reload():
        if consume_marker(paths):
            print("reload made by hyprkbm-apply; it applied the binds itself", flush=True)
        else:
            run_live(command)

    started = False
    while True:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(path)
                print("watching %s" % path, flush=True)
                if not started:
                    # At login hyprland.lua has run, and hyprKBM's binds are
                    # not in it.
                    run_live(command)
                    started = True
                read_events(sock, on_reload)
        except OSError as exc:
            print("socket error: %s" % exc, file=sys.stderr, flush=True)
        time.sleep(RECONNECT_SECONDS)


if __name__ == "__main__":
    main()
```

Run: `chmod +x bin/hyprkbm-watch`

`systemd/hyprkbm-watch.service`:

```ini
# Starts hyprkbm-watch with the graphical session, so hyprKBM's keybinds are
# applied at login and after every Hyprland reload without a line in
# hyprland.lua. hyprKBM needs it: without it, binds made in hyprKBM vanish at
# the next reload. install.sh links and enables it.
[Unit]
Description=Keep hyprKBM's keybinds applied to Hyprland
Documentation=https://github.com/phos-org/hyprKBM
PartOf=graphical-session.target
After=graphical-session.target
ConditionEnvironment=HYPRLAND_INSTANCE_SIGNATURE

[Service]
ExecStart=%h/.local/bin/hyprkbm-watch
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_watch.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add bin/hyprkbm-watch systemd/hyprkbm-watch.service tests/test_watch.py
git commit -m "feat: re-apply keybinds after every reload with a watcher service

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Markdown export and the hyprkbm CLI

**Files:**
- Create: `lib/hyprkbm/export.py`, `bin/hyprkbm`
- Test: `tests/test_export.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `model.merge`, `model.load_model`, `model.structure_errors`, `model.ModelError`, `catalogue.describe`, `keys.parse`, `keys.ORDER`, `apply.apply`, `read_config`.
- Produces: `export.export_markdown(merged, catalogue) -> str`.
- Produces: `bin/hyprkbm` with `--export md [FILE]`, `--apply [FILE]`, `--status`. Without arguments (or with `--cheatsheet`) it exits 2 and says the panel is not installed yet; plan 2 replaces that branch.

- [ ] **Step 1: Write the failing tests**

`tests/test_export.py`:

```python
import textwrap

from hyprkbm.catalogue import load_catalogue
from hyprkbm.export import export_markdown
from hyprkbm.model import merge
from hyprkbm.reader import read_config

CAT = load_catalogue()


def test_export_groups_by_submap_then_modifiers(paths):
    paths.entry.write_text(textwrap.dedent("""\
        hl.bind("SUPER + SHIFT + Q", hl.dsp.exit(), { description = "Leave | quit" })
        hl.bind("SUPER + Q", hl.dsp.exec_cmd("kitty"), { description = "Terminal" })
        hl.bind("Print", hl.dsp.exec_cmd("grim"))
        hl.bind("SUPER + C", hl.dsp.window.close())
        hl.define_submap("resize", "escape", function()
            hl.bind("right", hl.dsp.window.resize())
        end)
    """))
    model = {"version": 1, "submaps": [], "unbinds": [],
             "binds": [{"id": "b1", "keys": "SUPER + B", "description": "Browser",
                        "action": {"kind": "exec_cmd", "args": {"cmd": "firefox"}}}]}

    text = export_markdown(merge(model, read_config(paths), CAT), CAT)

    assert text == textwrap.dedent("""\
        # Keybinds

        ## Global

        ### No modifier

        | Key | Description | Action |
        |---|---|---|
        | Print |  | Run a command: grim |

        ### SUPER

        | Key | Description | Action |
        |---|---|---|
        | B | Browser | Run a command: firefox |
        | C |  | Close window |
        | Q | Terminal | Run a command: kitty |

        ### SUPER + SHIFT

        | Key | Description | Action |
        |---|---|---|
        | Q | Leave \\| quit | Exit Hyprland |

        ## resize

        ### No modifier

        | Key | Description | Action |
        |---|---|---|
        | right |  | Resize window (mouse) |
        """)
```

`tests/test_cli.py`:

```python
import json
import os
import subprocess
import sys
from pathlib import Path

HYPRKBM = Path(__file__).resolve().parents[1] / "bin" / "hyprkbm"


def run(home_env, *args):
    env = dict(home_env, PATH=os.environ["PATH"])
    return subprocess.run([sys.executable, str(HYPRKBM), *args],
                          capture_output=True, text=True, env=env)


def test_export_to_stdout(home_env, paths, stubs):
    paths.entry.write_text('hl.bind("SUPER + Q", hl.dsp.exec_cmd("kitty"))\n')

    res = run(home_env, "--export", "md")

    assert res.returncode == 0, res.stderr
    assert "| Q |  | Run a command: kitty |" in res.stdout


def test_export_to_a_file(home_env, paths, stubs, tmp_path):
    out = tmp_path / "binds.md"

    res = run(home_env, "--export", "md", str(out))

    assert res.returncode == 0, res.stderr
    assert out.read_text().startswith("# Keybinds")


def test_apply_a_file(home_env, paths, stubs, tmp_path):
    staged = tmp_path / "model.json"
    staged.write_text(json.dumps({
        "version": 1, "submaps": [], "unbinds": [],
        "binds": [{"id": "b1", "keys": "SUPER + B",
                   "action": {"kind": "exec_cmd", "args": {"cmd": "firefox"}}}]}))

    res = run(home_env, "--apply", str(staged))

    assert res.returncode == 0, res.stderr
    assert "Applied" in res.stdout
    assert paths.lua.exists()


def test_apply_reports_errors(home_env, paths, stubs, tmp_path):
    staged = tmp_path / "model.json"
    staged.write_text('{"version": 1, "binds": [{"id": "b1", "keys": "SUPER + B", '
                      '"action": {"kind": "nope"}}]}')

    res = run(home_env, "--apply", str(staged))

    assert res.returncode == 1
    assert "unknown action" in res.stderr


def test_status_summarises(home_env, paths, stubs):
    paths.entry.write_text('hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))\n'
                           'hl.bind("SUPER + F", hl.dsp.exit())\n')

    res = run(home_env, "--status")

    assert res.returncode == 0, res.stderr
    assert "hand-written binds: 2" in res.stdout
    assert "SUPER + F: hyprland.lua:1, hyprland.lua:2" in res.stdout
    assert ["systemctl", "--user", "is-active", "hyprkbm-watch.service"] in stubs.calls()


def test_no_arguments_explains_the_panel_is_missing(home_env, stubs):
    res = run(home_env)

    assert res.returncode == 2
    assert "panel" in res.stderr
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_export.py tests/test_cli.py -q`
Expected: FAIL (`No module named 'hyprkbm.export'`, and `bin/hyprkbm` missing).

- [ ] **Step 3: Implement export.py and the CLI**

`lib/hyprkbm/export.py`:

```python
"""The cheatsheet as Markdown: by submap, then by modifier combo."""
from collections import defaultdict

from .catalogue import describe
from .keys import ORDER, KeyParseError, parse


def _split(keys):
    try:
        combo = parse(keys)
    except KeyParseError:
        return (), keys
    return combo.mods, combo.key


def _cell(value):
    return " ".join(str(value).split()).replace("|", "\\|")


def _description(opts):
    return opts.get("description") or opts.get("desc") or ""


def export_markdown(merged, catalogue):
    lines = ["# Keybinds", ""]
    by_submap = defaultdict(list)
    for b in merged.binds:
        by_submap[b.submap].append(b)

    for submap in sorted(by_submap, key=lambda n: (n != "", n)):
        lines += ["## %s" % (submap or "Global"), ""]
        by_mods = defaultdict(list)
        for b in by_submap[submap]:
            by_mods[_split(b.keys)[0]].append(b)
        for mods in sorted(by_mods, key=lambda m: (len(m), [ORDER.index(x) for x in m])):
            lines += ["### %s" % (" + ".join(mods) or "No modifier"), "",
                      "| Key | Description | Action |", "|---|---|---|"]
            for b in sorted(by_mods[mods], key=lambda b: _split(b.keys)[1].lower()):
                lines.append("| %s | %s | %s |" % (
                    _cell(_split(b.keys)[1]), _cell(_description(b.opts)),
                    _cell(describe(b.dispatcher, catalogue))))
            lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"
```

`bin/hyprkbm`:

```python
#!/usr/bin/env python3
"""hyprKBM: a keyboard-first keybind manager for Hyprland's Lua config.

  hyprkbm --export md [FILE]   write a Markdown cheatsheet (stdout without FILE)
  hyprkbm --apply [FILE]       apply keybinds.json, or FILE, to Hyprland
  hyprkbm --status             binds, conflicts, stale edits and the watcher
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from hyprkbm.apply import apply  # noqa: E402
from hyprkbm.catalogue import load_catalogue  # noqa: E402
from hyprkbm.export import export_markdown  # noqa: E402
from hyprkbm.model import ModelError, load_model, merge, structure_errors  # noqa: E402
from hyprkbm.paths import Paths  # noqa: E402
from hyprkbm.reader import read_config  # noqa: E402

UNIT = "hyprkbm-watch.service"


def fail(*messages, code=1):
    for m in messages:
        print("hyprkbm: %s" % m, file=sys.stderr)
    return code


def load_state(paths):
    """Hand binds, the model and the catalogue, or a list of reasons not."""
    hand = read_config(paths)
    if hand.error:
        print("hyprkbm: warning: %s: %s" % (paths.entry, hand.error), file=sys.stderr)
    try:
        model = load_model(paths.model)
    except ModelError as exc:
        return None, [str(exc)]
    catalogue = load_catalogue()
    errors = structure_errors(model, hand, catalogue)
    if errors:
        return None, ["%s: %s" % (paths.model, e["message"]) for e in errors]
    return (hand, model, catalogue), []


def cmd_export(paths, args):
    if not args or args[0] != "md" or len(args) > 2:
        return fail("usage: hyprkbm --export md [FILE]", code=2)
    state, errors = load_state(paths)
    if errors:
        return fail(*errors)
    hand, model, catalogue = state
    text = export_markdown(merge(model, hand, catalogue), catalogue)
    if len(args) == 2:
        Path(args[1]).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def cmd_apply(paths, args):
    if len(args) > 1:
        return fail("usage: hyprkbm --apply [FILE]", code=2)
    try:
        model = load_model(Path(args[0]) if args else paths.model)
    except ModelError as exc:
        return fail(str(exc))
    result = apply(model, paths)
    if not result["ok"]:
        return fail(*(e["message"] for e in result["errors"]))
    print("Applied." + (" Previous keybinds saved in %s." % result["backup"]
                        if result["backup"] else ""))
    return 0


def cmd_status(paths):
    state, errors = load_state(paths)
    if errors:
        return fail(*errors)
    hand, model, catalogue = state
    merged = merge(model, hand, catalogue)
    print("config: %s%s" % (paths.entry, " (could not be read completely)" if hand.error else ""))
    print("hand-written binds: %d" % len(hand.binds))
    print("hyprKBM binds: %d (%d overrides), %d unbinds" % (
        len(model.get("binds", [])),
        sum(1 for b in merged.binds if b.source == "override"),
        len(model.get("unbinds", []))))
    conflicts = merged.conflicts()
    print("conflicts: %d" % len(conflicts))
    for group in conflicts:
        print("  %s: %s" % (group[0].keys, ", ".join(b.where for b in group)))
    print("stale: %d" % len(merged.stale))
    for s in merged.stale:
        print("  %s: %s" % (s["keys"], s["message"]))
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", UNIT],
                             capture_output=True, text=True)
        watcher = res.stdout.strip() or "unknown"
    except OSError:
        watcher = "unknown (no systemctl)"
    print("watcher: %s" % watcher)
    return 0


def main(argv):
    paths = Paths.from_env()
    if argv[:1] == ["--export"]:
        return cmd_export(paths, argv[1:])
    if argv[:1] == ["--apply"]:
        return cmd_apply(paths, argv[1:])
    if argv == ["--status"]:
        return cmd_status(paths)
    if argv in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    if argv in ([], ["--cheatsheet"]):
        return fail("the hyprKBM panel is not installed in this version yet; "
                    "see hyprkbm --help", code=2)
    return fail(__doc__.strip(), code=2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Run: `chmod +x bin/hyprkbm`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/export.py bin/hyprkbm tests/test_export.py tests/test_cli.py
git commit -m "feat: add the hyprkbm CLI with Markdown export and status

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: install.sh, docs and CI linting

**Files:**
- Create: `install.sh`, `README.md`, `CONTRIBUTING.md`
- Modify: `.github/workflows/ci.yml` (add ShellCheck job)
- Test: `tests/test_install.py`

**Interfaces:**
- Consumes: `bin/hyprkbm`, `bin/hyprkbm-apply`, `bin/hyprkbm-watch`, `systemd/hyprkbm-watch.service`.
- Produces: `install.sh` (`./install.sh`, `./install.sh --uninstall`), exit 0 on success, 1 if anything was skipped or failed, 2 on usage error.

- [ ] **Step 1: Write the failing tests**

`tests/test_install.py`:

```python
"""install.sh, run for real against a throwaway HOME with a stub systemctl
first on PATH, so nothing reaches the user's own home or systemd."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = "hyprkbm-watch.service"

SYSTEMCTL = r'''#!%(python)s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
state = json.load(open(os.path.join(here, "systemd.json")))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
args = [a for a in sys.argv[1:] if a not in ("--user", "--quiet", "-q")]
if args[0] == "is-active":
    sys.exit(0 if state["session"] else 3)
if args[0] == "is-enabled":
    print(state["enabled"])
    sys.exit(0 if state["enabled"] == "enabled" else 1)
sys.exit(0)
'''


def links(home):
    return {
        home / ".local/bin/hyprkbm": "bin/hyprkbm",
        home / ".local/bin/hyprkbm-apply": "bin/hyprkbm-apply",
        home / ".local/bin/hyprkbm-watch": "bin/hyprkbm-watch",
        home / ".config/systemd/user" / UNIT: "systemd/" + UNIT,
    }


def run(tmp_path, *args, session=True, enabled="disabled"):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    script = stubs / "systemctl"
    script.write_text(SYSTEMCTL % {"python": sys.executable})
    script.chmod(0o755)
    (stubs / "systemd.json").write_text(json.dumps({"session": session, "enabled": enabled}))
    env = {"PATH": "%s:%s:/usr/bin:/bin" % (stubs, home / ".local/bin"), "HOME": str(home)}
    res = subprocess.run(["bash", str(ROOT / "install.sh"), *args],
                         capture_output=True, text=True, env=env)
    log = stubs / "calls.log"
    calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return home, res, calls


def test_install_links_everything_and_enables_the_watcher(tmp_path):
    home, res, calls = run(tmp_path)

    assert res.returncode == 0, res.stderr
    for dst, src in links(home).items():
        assert dst.is_symlink(), dst
        assert Path(os.readlink(dst)) == ROOT / src
    assert ["--user", "enable", "--now", UNIT] in calls


def test_install_is_idempotent(tmp_path):
    run(tmp_path)
    home, res, _ = run(tmp_path)

    assert res.returncode == 0
    assert "ok" in res.stdout


def test_a_real_file_in_the_way_is_left_alone(tmp_path):
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/hyprkbm").write_text("mine")

    home, res, _ = run(tmp_path)

    assert res.returncode == 1
    assert (home / ".local/bin/hyprkbm").read_text() == "mine"
    assert "skipped" in res.stderr


def test_a_masked_watcher_is_an_error_because_hyprkbm_needs_it(tmp_path):
    home, res, calls = run(tmp_path, enabled="masked")

    assert res.returncode == 1
    assert "masked" in res.stderr
    assert ["--user", "enable", "--now", UNIT] not in calls


def test_without_a_systemd_session_it_explains_the_fallback(tmp_path):
    home, res, calls = run(tmp_path, session=False)

    assert res.returncode == 0
    assert 'hl.exec_cmd("hyprkbm-watch")' in res.stdout


def test_uninstall_removes_only_its_own_links(tmp_path):
    home, _, _ = run(tmp_path)
    keep = home / ".config/hyprkbm/keybinds.json"
    keep.parent.mkdir(parents=True)
    keep.write_text("{}")

    home, res, calls = run(tmp_path, "--uninstall")

    assert res.returncode == 0
    assert not any(dst.exists() or dst.is_symlink() for dst in links(home))
    assert keep.exists()
    assert ["--user", "disable", "--now", UNIT] in calls
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_install.py -q`
Expected: FAIL (`install.sh` does not exist; bash exits 127).

- [ ] **Step 3: Write install.sh**

`install.sh`:

```bash
#!/usr/bin/env bash
# Install hyprKBM for the current user, as symlinks back into this clone --
# so keep the clone, and `git pull` is the upgrade.
#
#   ./install.sh              link everything and enable the watcher
#   ./install.sh --uninstall  remove what install created
#
# Nothing in hyprland.lua is touched. Keybinds are applied to Hyprland live,
# and hyprkbm-watch, started with the session by a systemd user unit, puts
# them back after every reload and at login. hyprKBM needs it.
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# Fixed rather than configurable: the systemd unit runs the watcher from here.
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
UNIT=hyprkbm-watch.service

# source (in the clone) and destination, one pair per line.
LINKS="
bin/hyprkbm          $BIN_DIR/hyprkbm
bin/hyprkbm-apply    $BIN_DIR/hyprkbm-apply
bin/hyprkbm-watch    $BIN_DIR/hyprkbm-watch
systemd/$UNIT        $CONFIG_DIR/systemd/user/$UNIT
"

failed=0
say() { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }

have_systemd_session() {
    command -v systemctl >/dev/null 2>&1 \
        && systemctl --user is-active --quiet graphical-session.target
}

have_lua() {
    command -v lua >/dev/null 2>&1 || command -v lua5.5 >/dev/null 2>&1 \
        || command -v lua5.4 >/dev/null 2>&1
}

link() {
    local src="$REPO/$1" dst="$2"
    mkdir -p "$(dirname "$dst")"
    if [ -L "$dst" ]; then
        if [ "$(readlink "$dst")" = "$src" ]; then
            say "  ok        $dst"
            return
        fi
        # A link is somebody's earlier install of this; a file is not.
        ln -sfn "$src" "$dst"
        say "  replaced  $dst"
    elif [ -e "$dst" ]; then
        warn "  skipped   $dst: a file is already there, not a link; move it and run again"
        failed=1
    else
        ln -s "$src" "$dst"
        say "  linked    $dst"
    fi
}

unlink_ours() {
    local src="$REPO/$1" dst="$2"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        rm "$dst"
        say "  removed   $dst"
    fi
}

enable_watcher() {
    if ! have_systemd_session; then
        say ""
        say "This session does not start graphical-session.target, so systemd cannot"
        say "start the watcher at login. Add this to hyprland.lua instead:"
        say ""
        say '    hl.on("hyprland.start", function()'
        say '        hl.exec_cmd("hyprkbm-watch")'
        say '    end)'
        return
    fi
    systemctl --user daemon-reload
    if [ "$(systemctl --user is-enabled "$UNIT" 2>/dev/null)" = masked ]; then
        warn "$UNIT is masked. hyprKBM needs it: without it, your keybinds are lost"
        warn "at the next reload. Unmask it and run this again:"
        warn "    systemctl --user unmask $UNIT"
        failed=1
        return
    fi
    if systemctl --user enable --now "$UNIT"; then
        say "Enabled $UNIT; it starts with every graphical session."
    else
        warn "Could not enable $UNIT; see: systemctl --user status $UNIT"
        failed=1
    fi
}

install() {
    for tool in hyprctl python3; do
        command -v "$tool" >/dev/null 2>&1 \
            || warn "warning: $tool not found; hyprKBM needs it to run"
    done
    have_lua || warn "warning: no lua interpreter found; hyprKBM needs one to read hyprland.lua"
    say "Linking from $REPO"
    while read -r src dst; do
        [ -n "$src" ] && link "$src" "$dst"
    done <<<"$LINKS"
    enable_watcher
    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "warning: $BIN_DIR is not on your PATH; add it to run hyprkbm yourself" ;;
    esac
    say ""
    say "Done. Try: hyprkbm --status"
}

uninstall() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now "$UNIT" >/dev/null 2>&1 || true
    fi
    while read -r src dst; do
        [ -n "$src" ] && unlink_ours "$src" "$dst"
    done <<<"$LINKS"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
    say "Removed. Your keybinds.json, keybinds.lua and backups are kept."
}

case "${1:-}" in
    "") install ;;
    --uninstall) uninstall ;;
    *)
        warn "usage: $0 [--uninstall]"
        exit 2
        ;;
esac
exit "$failed"
```

Run: `chmod +x install.sh && shellcheck install.sh`
Expected: no ShellCheck output.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_install.py -q`
Expected: all pass.

- [ ] **Step 5: Add the ShellCheck job to CI**

Append to `.github/workflows/ci.yml` under `jobs:`:

```yaml
  shell:
    name: ShellCheck
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7

      # shellcheck ships with the GitHub runner image.
      - name: Lint the installer
        run: shellcheck install.sh
```

- [ ] **Step 6: Write the README and contributor guide**

`README.md`:

````markdown
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
  `hyprctl eval`.
- **The binds always work.** A reload re-runs `hyprland.lua` and drops what
  eval set, so the `hyprkbm-watch` user service applies them again after
  every reload and at login. hyprKBM needs it, and `install.sh` enables it.
- **Hand-written binds are read by running your config** in a sandbox,
  against a stand-in for `hl` that records each bind. That is what gets
  loops, helper functions and `mainMod ..` right. The sandbox cannot run
  commands, write files or load anything outside `~/.config/hypr`.
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
upgrade. `install.sh --uninstall` removes the links and keeps your binds.

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
````

`CONTRIBUTING.md`:

````markdown
# Contributing

## Running the tests

The helpers import nothing outside the Python standard library; `pytest` is
the only development dependency. The reader needs a Lua interpreter.

```bash
python3 -m pytest tests/ -q
shellcheck install.sh
```

The suite needs no compositor. It points `HOME` at a temporary directory and
puts stub `hyprctl`, `notify-send` and `systemctl` executables first on
`PATH`. Nothing in it touches your real config or your running session. Keep
it that way: a test that writes to `~/.config` will eventually be run by
someone who is using the machine.

## Layout

| Path | Holds |
|---|---|
| `lib/reader.lua` | the sandbox that runs a config against a recording `hl` |
| `lib/hyprkbm/` | the Python core: keys, model, render, apply, export |
| `share/actions.json` | the action catalogue |
| `bin/` | `hyprkbm`, `hyprkbm-apply` (the only writer of keybinds files), `hyprkbm-watch` |

## Testing against Hyprland

`hyprkbm --status`, then `hyprkbm --apply`, then `hyprctl reload` and check
that `hyprctl binds` still lists the binds. `journalctl --user -u
hyprkbm-watch` shows what the watcher did.

## Conventions

- Commits: `<type>: <description>`, with `feat, fix, refactor, docs, test, chore, perf`.
- Comments explain *why*, not *what*.
````

- [ ] **Step 7: Run everything and commit**

Run: `python3 -m pytest tests/ -q && shellcheck install.sh`
Expected: all tests pass, no ShellCheck output.

```bash
git add install.sh README.md CONTRIBUTING.md .github/workflows/ci.yml tests/test_install.py
git commit -m "feat: install with one command, and document the core

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Verify on a real Hyprland session

No new files; this checks the whole core against the running compositor. It changes live binds temporarily and restores them at the end.

- [ ] **Step 1: Install and check status**

Run: `./install.sh && hyprkbm --status`
Expected: links created, `Enabled hyprkbm-watch.service`, a hand-written bind count equal to `hyprctl binds -j | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"`, `watcher: active`.

- [ ] **Step 2: Apply a bind, an override and an unbind**

Write `~/.config/hyprkbm/keybinds.json` (if one already exists, copy it aside first):

```json
{
  "version": 1,
  "submaps": [{ "name": "hyprkbm-test", "reset": "escape" }],
  "binds": [
    { "id": "t1", "keys": "SUPER + CTRL + ALT + F12", "description": "hyprKBM test",
      "action": { "kind": "exec_cmd", "args": { "cmd": "notify-send hyprKBM works" } } },
    { "id": "t2", "keys": "SUPER + J", "description": "Toggle split (via hyprKBM)",
      "action": { "kind": "layout", "args": { "message": "togglesplit" } },
      "replaces": { "keys": "SUPER + J", "submap": "", "fingerprint": "layout:[\"togglesplit\"]" } },
    { "id": "t3", "keys": "F10", "submap": "hyprkbm-test",
      "action": { "kind": "window.move", "args": { "direction": "left" } } }
  ],
  "unbinds": []
}
```

If your `hyprland.lua` has no `SUPER + J` togglesplit bind, point `t2` at any simple bind of yours. List your binds with their fingerprints:

Run: `python3 -c "import sys; sys.path.insert(0, 'lib'); from hyprkbm.paths import Paths; from hyprkbm.reader import read_config; [print(b.keys, '|', b.fingerprint) for b in read_config(Paths.from_env()).binds]"`

Run: `hyprkbm --apply`
Expected: `Applied.`

Run: `hyprctl binds -j | python3 -c "import json,sys; [print(b['key'], b['submap'], b['description']) for b in json.load(sys.stdin) if b['description'] or b['submap']]"`
Expected: `F12  hyprKBM test`, `J  Toggle split (via hyprKBM)` and `F10 hyprkbm-test`, with only one SUPER+J bind.

Press SUPER+CTRL+ALT+F12: a "hyprKBM works" notification appears.

- [ ] **Step 3: Check the binds survive a reload**

Run: `hyprctl reload && sleep 1 && hyprctl binds -j | python3 -c "import json,sys; print(sum(1 for b in json.load(sys.stdin) if b['description'].startswith(('hyprKBM','Toggle split'))))"`
Expected: `2`.

Run: `journalctl --user -u hyprkbm-watch -n 5 --no-pager`
Expected: an `apply --live rc=0` line after the reload, and `reload made by hyprkbm-apply` for the reload `hyprkbm --apply` itself made.

- [ ] **Step 4: Check rollback**

Add a raw bind whose dispatcher Hyprland refuses. Validation cannot see inside raw Lua, so this exercises the dry run. Add to `binds`:

```json
{ "id": "t4", "keys": "SUPER + CTRL + ALT + F11",
  "action": { "kind": "raw", "lua": "hl.dsp.window.move({ bogus = 1 })" } }
```

Run: `hyprkbm --apply`
Expected: exit 1, `Hyprland rejected the new keybinds, so nothing was changed: ... unrecognized arguments ...`; `keybinds.json` unchanged.

- [ ] **Step 5: Export, then restore**

Run: `hyprkbm --export md | head -20`
Expected: a Markdown table including the test binds.

Restore: put back your previous `keybinds.json` (or write `{"version": 1, "submaps": [], "binds": [], "unbinds": []}`), then `hyprkbm --apply`.
Expected: `Applied.`, and `hyprctl binds -j` no longer lists the test binds.

- [ ] **Step 6: Record the result**

If anything differed from the expectations above, fix it under superpowers:systematic-debugging before continuing, with a regression test. Otherwise there is nothing to commit; note the Hyprland version verified against in the PR description.
