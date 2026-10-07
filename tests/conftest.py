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
