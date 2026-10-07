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
