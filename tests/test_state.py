import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from hyprkbm.state import build_state, read_backup, set_layout

HYPRKBM = Path(__file__).resolve().parents[1] / "bin" / "hyprkbm"


def run(home_env, *args):
    env = dict(home_env, PATH=os.environ["PATH"])
    return subprocess.run([sys.executable, str(HYPRKBM), *args],
                          capture_output=True, text=True, env=env)


def write_config(paths, source):
    paths.entry.write_text(textwrap.dedent(source))


def test_state_describes_hand_binds_for_the_panel(paths, stubs):
    write_config(paths, """\
        hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"), { description = "Files" })
        hl.define_submap("resize", "escape", function()
            hl.bind("right", hl.dsp.window.resize())
        end)
    """)

    doc = build_state(paths)

    assert doc["entry"] == str(paths.entry)
    assert doc["readerError"] is None
    first, second = doc["hand"]
    assert first == {
        "uid": "h:0", "keys": "SUPER + F", "combo": "SUPER+f", "submap": "",
        "where": "hyprland.lua:1", "fingerprint": 'exec_cmd:["dolphin"]',
        "reproducible": True, "description": "Files",
        "describe": "Run a command: dolphin",
        "dispatcher": {"dsp": "exec_cmd", "args": ["dolphin"]},
        "opts": {"description": "Files"},
    }
    assert second["uid"] == "h:1"
    assert second["submap"] == "resize"
    assert doc["handSubmaps"] == [{"name": "resize", "reset": "escape"}]
    assert doc["model"] == {"version": 1, "submaps": [], "binds": [], "unbinds": []}
    assert doc["modelError"] is None
    assert [a["id"] for a in doc["catalogue"]][0] == "exec_cmd"
    assert doc["currentLua"] == ""
    assert doc["backups"] == []
    assert doc["settings"] == {}
    assert doc["watcher"] == "unknown"   # the stub systemctl prints nothing


def test_a_broken_model_is_reported_not_raised(paths, stubs):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text("{oops")

    doc = build_state(paths)

    assert doc["model"] is None
    assert "not valid JSON" in doc["modelError"]


def test_a_structurally_invalid_model_is_reported(paths, stubs):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text('{"version": 2}')

    doc = build_state(paths)

    assert doc["model"] == {"version": 2}
    assert "version must be 1" in doc["modelError"]


def test_backups_are_listed_newest_first_and_readable(paths, stubs):
    for name in ("20260101T000000000000", "20260102T000000000000"):
        (paths.backups / name).mkdir(parents=True)
    newest = paths.backups / "20260102T000000000000"
    (newest / "keybinds.json").write_text('{"version": 1, "binds": []}')
    (newest / "keybinds.lua").write_text("-- old\n")

    assert build_state(paths)["backups"] == ["20260102T000000000000",
                                             "20260101T000000000000"]
    assert read_backup(paths, "20260102T000000000000") == {
        "model": {"version": 1, "binds": []}, "lua": "-- old\n", "modelError": None}
    # No keybinds.json in the backup is an empty model, not an error.
    assert read_backup(paths, "20260101T000000000000") == {
        "model": None, "lua": "", "modelError": None}
    assert read_backup(paths, "nope") is None
    assert read_backup(paths, "../etc") is None


def test_set_layout_keeps_other_settings(paths):
    paths.settings.parent.mkdir(parents=True)
    paths.settings.write_text('{"entry": "~/dots/hyprland.lua"}')

    set_layout(paths, "iso")

    assert json.loads(paths.settings.read_text()) == {
        "entry": "~/dots/hyprland.lua", "layout": "iso"}
    with pytest.raises(ValueError):
        set_layout(paths, "dvorak")


def test_cli_state_backup_and_layout(home_env, paths, stubs):
    res = run(home_env, "--state")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["hand"] == []

    assert run(home_env, "--backup", "missing").returncode == 1

    res = run(home_env, "--set-layout", "iso")
    assert res.returncode == 0, res.stderr
    assert json.loads(paths.settings.read_text())["layout"] == "iso"
    assert run(home_env, "--set-layout", "qwertz").returncode == 2


def test_set_layout_refuses_malformed_settings_json(paths):
    paths.settings.parent.mkdir(parents=True)
    paths.settings.write_text("{oops")

    with pytest.raises(ValueError) as exc_info:
        set_layout(paths, "iso")
    assert "could not be read" in str(exc_info.value)
    assert paths.settings.read_text() == "{oops"


def test_set_layout_refuses_non_object_settings_json(paths):
    paths.settings.parent.mkdir(parents=True)
    paths.settings.write_text("[1, 2]")

    with pytest.raises(ValueError) as exc_info:
        set_layout(paths, "iso")
    assert "could not be read" in str(exc_info.value)
    assert paths.settings.read_text() == "[1, 2]"


def test_cli_set_layout_exits_1_on_malformed_settings(home_env, paths):
    paths.settings.parent.mkdir(parents=True)
    paths.settings.write_text("{oops")

    res = run(home_env, "--set-layout", "iso")
    assert res.returncode == 1, res.stderr
    assert "could not be read" in res.stderr
    assert paths.settings.read_text() == "{oops"


def test_a_backup_whose_model_cannot_be_read_says_so(paths, stubs):
    folder = paths.backups / "20260103T000000000000"
    folder.mkdir(parents=True)
    (folder / "keybinds.json").write_text("{not json")
    got = read_backup(paths, "20260103T000000000000")
    assert got["model"] is None
    assert got["modelError"]
    (folder / "keybinds.json").write_text("[1, 2]")
    got = read_backup(paths, "20260103T000000000000")
    assert got["model"] is None and got["modelError"]
