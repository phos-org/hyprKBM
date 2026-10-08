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


def wait_for(stubs, program):
    import time
    for _ in range(50):
        if any(c[0] == program for c in stubs.calls()):
            return
        time.sleep(0.05)


def test_no_arguments_opens_the_panel(home_env, stubs):
    res = run(home_env)

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    qs = [c for c in stubs.calls() if c[0] == "qs"][0]
    assert qs[1] == "-p" and qs[2].endswith("quickshell/hyprkbm") and qs[3] == "-d"


def test_an_open_panel_is_focused_not_opened_again(home_env, stubs):
    stubs.respond(**{"-j": ['[{"class": "org.quickshell", "title": "Keybinds"}]']})

    res = run(home_env)

    assert res.returncode == 0, res.stderr
    assert ["hyprctl", "dispatch", "focuswindow", "title:^Keybinds$"] in stubs.calls()
    assert not any(c[0] == "qs" for c in stubs.calls())


def test_no_quickshell_is_explained(home_env, stubs):
    (stubs.root / "qs").unlink()
    env = dict(home_env, PATH="%s:/usr/bin:/bin" % stubs.root)
    if any(os.access(os.path.join(d, "qs"), os.X_OK) for d in ("/usr/bin", "/bin")):
        import pytest
        pytest.skip("a real qs is installed in /usr/bin; cannot hide it")
    res = subprocess.run([sys.executable, str(HYPRKBM)], capture_output=True, text=True, env=env)

    assert res.returncode == 1
    assert "Quickshell" in res.stderr


def test_export_to_an_unwritable_path_fails_cleanly(home_env, paths, stubs, tmp_path):
    res = run(home_env, "--export", "md", str(tmp_path / "missing" / "binds.md"))

    assert res.returncode == 1
    assert res.stderr.startswith("hyprkbm:")
    assert "Traceback" not in res.stderr


def test_export_without_a_lua_interpreter_fails_cleanly(home_env, paths, stubs):
    res = run(dict(home_env, HYPRKBM_LUA="/nonexistent/lua"), "--export", "md")

    assert res.returncode == 1
    assert res.stderr.startswith("hyprkbm:")
    assert "Traceback" not in res.stderr


def test_binds_lists_what_an_override_needs(home_env, paths, stubs):
    paths.entry.write_text('hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))\n'
                           'hl.define_submap("resize", "escape", function()\n'
                           '    hl.bind("right", hl.dsp.window.resize())\n'
                           'end)\n')

    res = run(home_env, "--binds")

    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert 'SUPER + F\t\thyprland.lua:1\texec_cmd:["dolphin"]' in lines
    assert "right\tresize\thyprland.lua:3\twindow.resize:[]" in lines
