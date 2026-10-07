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
