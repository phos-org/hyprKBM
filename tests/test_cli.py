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


def is_launch(call):
    return call[0] == "qs" and call[1:2] == ["-p"] and "-d" in call


def wait_for(stubs, program):
    """The launch is detached, so its stub logs a moment after hyprkbm exits."""
    import time
    for _ in range(50):
        if any(is_launch(c) if program == "qs" else c[0] == program for c in stubs.calls()):
            return
        time.sleep(0.05)


def test_no_arguments_opens_the_panel(home_env, stubs):
    res = run(home_env)

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    qs = [c for c in stubs.calls() if c[0] == "qs" and c[1] == "-p"][0]
    assert qs[1] == "-p" and qs[2].endswith("quickshell/hyprkbm") and qs[3:] == ["-d", "-n"]


def test_an_open_panel_is_focused_not_opened_again(home_env, stubs):
    """Focused through the Lua API -- Lua-config Hyprland rejects the old
    `dispatch focuswindow` syntax -- and by the window's own address, so a
    different window that happens to be titled Keybinds is never raised."""
    stubs.respond(**{"-j": ['[{"class": "org.quickshell", "title": "Keybinds", '
                            '"address": "0x5a1b2c3d"}]']})

    res = run(home_env)

    assert res.returncode == 0, res.stderr
    evals = [c[2] for c in stubs.calls() if c[:2] == ["hyprctl", "eval"]]
    assert evals == ['hl.dispatch(hl.dsp.focus({ window = "address:0x5a1b2c3d" }))']
    assert not any(c[0] == "qs" for c in stubs.calls())
    assert not any(c[:2] == ["hyprctl", "dispatch"] for c in stubs.calls())


def test_a_panel_left_running_without_a_window_is_cleared_first(home_env, stubs):
    """With no panel window, any panel instance still running is an orphan --
    and qs -n would refuse to start a new one beside it, so `hyprkbm` would
    silently do nothing. It is killed before the new one starts."""
    res = run(home_env)

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    qs = [c for c in stubs.calls() if c[0] == "qs"]
    launch = next(c for c in qs if is_launch(c))
    assert qs[0] == ["qs", "kill", "-p", launch[2]]
    assert qs.index(qs[0]) < qs.index(launch)
    assert launch[3:] == ["-d", "-n"]


def test_no_quickshell_is_explained(home_env, stubs):
    (stubs.root / "qs").unlink()
    # sys.executable is absolute, so python runs while PATH holds only the stubs
    # and no real qs can be found.
    env = dict(home_env, PATH=str(stubs.root))
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


def test_the_panel_is_made_to_float_before_it_opens(home_env, stubs):
    """Tiled, the panel gets whatever share of the workspace is left -- often
    far below its minimum size. A window rule added just before it opens makes
    it float, centred, at its own size; the rule lives until the next reload,
    like everything else hyprKBM applies, and a guard keeps launches from
    stacking copies of it."""
    res = run(home_env)

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    calls = stubs.calls()
    evals = [c for c in calls if c[:2] == ["hyprctl", "eval"]]
    assert len(evals) == 1
    rule = evals[0][2]
    for needle in ("hl.window_rule(", "float = true", "center = true",
                   'size = "1180 760"', "Keybinds", "org", "__hyprkbm_panel_rule"):
        assert needle in rule, needle
    assert calls.index(evals[0]) < next(i for i, c in enumerate(calls) if is_launch(c))


QS_IPC_NOBODY = r'''#!%(python)s
"""qs where no cheatsheet runs: ipc fails as the real one does (255)."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(["qs"] + sys.argv[1:]) + "\n")
sys.exit(255 if sys.argv[1:2] == ["ipc"] else 0)
'''


def nobody_running(stubs):
    qs = stubs.root / "qs"
    qs.write_text(QS_IPC_NOBODY % {"python": sys.executable})
    qs.chmod(0o755)


def test_cheatsheet_opens_when_none_is_running(home_env, stubs):
    nobody_running(stubs)

    res = run(home_env, "--cheatsheet")

    assert res.returncode == 0, res.stderr
    wait_for(stubs, "qs")
    calls = [c for c in stubs.calls() if c[0] == "qs"]
    assert calls[0][:2] == ["qs", "ipc"] and calls[0][-2:] == ["cheatsheet", "close"]
    launch = next(c for c in calls if is_launch(c))
    assert launch[2].endswith("quickshell/hyprkbm/cheatsheet.qml") and launch[3:] == ["-d", "-n"]


def test_cheatsheet_closes_the_one_that_is_running(home_env, stubs):
    # The default qs stub exits 0: a running sheet answered and closed.
    res = run(home_env, "--cheatsheet")

    assert res.returncode == 0, res.stderr
    calls = [c for c in stubs.calls() if c[0] == "qs"]
    assert len(calls) == 1 and calls[0][1] == "ipc"
    assert calls[0][2] == "-p" and calls[0][3].endswith("quickshell/hyprkbm/cheatsheet.qml")


def test_cheatsheet_needs_quickshell(home_env, stubs):
    (stubs.root / "qs").unlink()

    # sys.executable is absolute, so python runs while PATH holds only the stubs
    env = dict(home_env, PATH=str(stubs.root))
    res = subprocess.run([sys.executable, str(HYPRKBM), "--cheatsheet"],
                         capture_output=True, text=True, env=env)

    assert res.returncode == 1
    assert "Quickshell" in res.stderr


def test_version(home_env, stubs):
    from hyprkbm import __version__
    res = run(home_env, "--version")
    assert res.returncode == 0, res.stderr
    assert res.stdout == "hyprkbm %s\n" % __version__
    assert __version__ == "0.1.0"
