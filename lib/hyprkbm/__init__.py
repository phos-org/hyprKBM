"""hyprKBM's core: reading hyprland.lua, the keybinds model, rendering it to
Lua and applying it to Hyprland."""
from pathlib import Path

__version__ = "0.1.0"

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
SHARE = ROOT / "share"
