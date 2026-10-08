import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

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
    assert 'bind("SUPER + B", hl.dsp.exec_cmd("firefox"))' in paths.lua.read_text()
    assert stubs.hyprctl_kinds() == ["dry", "reload", "load"]
    load = [c for c in stubs.calls() if c[:2] == ["hyprctl", "eval"]][-1]
    assert load[2] == 'dofile("%s")' % paths.lua
    assert paths.marker.read_text().strip() == "1", "the watcher must be told this reload was ours"
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


def test_a_failing_reload_leaves_no_marker(paths, stubs):
    stubs.respond(reload=["error: no socket", "error: no socket"])

    result = apply(GOOD, paths)

    assert result["ok"] is False
    assert not paths.marker.exists()


def test_a_failed_rollback_says_so_and_shows_both_outputs(paths, stubs):
    apply(GOOD, paths)
    stubs.respond(load=["error: a", "error: b"])

    result = apply(OTHER, paths)

    message = result["errors"][0]["message"]
    assert "could not be restored" in message
    assert "error: a" in message and "error: b" in message
    assert "were put back" not in message
    assert any(c[0] == "notify-send" and "could not be restored" in c[-1]
               for c in stubs.calls())


def test_an_exception_after_the_dry_run_restores_the_previous_files(paths, stubs, monkeypatch):
    apply(GOOD, paths)
    before = (paths.model.read_text(), paths.lua.read_text())
    real = applying.write_atomic

    def flaky(path, text):
        if path == paths.lua:
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(applying, "write_atomic", flaky)
    with pytest.raises(OSError):
        apply(OTHER, paths)
    monkeypatch.setattr(applying, "write_atomic", real)

    assert json.loads(paths.model.read_text()) == GOOD
    assert (paths.model.read_text(), paths.lua.read_text()) == before


def test_the_dry_run_shadows_the_bind_list_so_it_cannot_touch_live_binds():
    # The chunk only runs inside Hyprland, so the text is what can be checked:
    # its env falls back to the real _G, where the preamble would otherwise
    # find (and remove) the live binds' handles.
    assert "__hyprkbm_binds = false" in applying.DRY_RUN
