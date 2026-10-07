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
