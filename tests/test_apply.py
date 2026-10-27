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
    real = applying._stage

    def flaky(path, text):
        if path == paths.lua:
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(applying, "_stage", flaky)
    with pytest.raises(OSError):
        apply(OTHER, paths)
    monkeypatch.setattr(applying, "_stage", real)

    assert json.loads(paths.model.read_text()) == GOOD
    assert (paths.model.read_text(), paths.lua.read_text()) == before
    assert not list(paths.config_dir.glob(".keybinds*."))
    assert sorted(p.name for p in paths.config_dir.iterdir()) == ["keybinds.json", "keybinds.lua"]


def test_a_failed_lua_write_never_renames_the_json_into_place(paths, stubs, monkeypatch):
    apply(GOOD, paths)
    before = (paths.model.read_bytes(), paths.lua.read_bytes())
    real = applying._stage

    def flaky(path, text):
        staged = real(path, text)
        if path == paths.model:
            return staged
        os.unlink(staged)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(applying, "_stage", flaky)
    replaced = []
    real_replace = os.replace
    monkeypatch.setattr(applying.os, "replace", lambda a, b: (replaced.append(b), real_replace(a, b)))
    with pytest.raises(OSError):
        apply(OTHER, paths)

    assert (paths.model.read_bytes(), paths.lua.read_bytes()) == before
    assert not [t for t in replaced if t == paths.model], "json must not move before lua is staged"
    assert [p.name for p in paths.config_dir.iterdir() if p.name.startswith(".keybinds")] == []


def test_write_atomic_removes_its_temp_file_when_the_write_fails(tmp_path, monkeypatch):
    target = tmp_path / "out.json"

    def boom(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(applying.os, "fdopen", boom)
    with pytest.raises(OSError):
        applying.write_atomic(target, "x")

    assert list(tmp_path.iterdir()) == []


def test_writes_go_through_a_symlink_to_the_file_it_points_at(tmp_path):
    # Dotfile managers link keybinds.json in from a repo; the link must stay.
    repo = tmp_path / "dotfiles"
    repo.mkdir()
    (repo / "keybinds.json").write_text("old")
    link = tmp_path / "keybinds.json"
    link.symlink_to(repo / "keybinds.json")

    applying.write_files([(link, "new")])

    assert link.is_symlink()
    assert (repo / "keybinds.json").read_text() == "new"
    assert sorted(p.name for p in repo.iterdir()) == ["keybinds.json"]


def test_apply_takes_and_releases_the_apply_lock(paths, stubs):
    apply(GOOD, paths)

    assert (paths.runtime_dir / "apply.lock").exists()
    # A second apply would block forever if the first had kept the lock.
    assert apply(OTHER, paths)["ok"] is True


def test_non_ascii_descriptions_survive_a_c_locale(home_env, stubs, paths):
    # A systemd service can start with LC_ALL=C; the files must still be UTF-8.
    model = json.loads(json.dumps(GOOD))
    model["binds"][0]["description"] = "ünï"
    env = dict(home_env, PATH=os.environ["PATH"], LC_ALL="C", LANG="C",
               PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply")],
                         input=json.dumps(model), capture_output=True, text=True, env=env)

    assert res.returncode == 0, res.stderr
    assert "ünï" in paths.model.read_bytes().decode("utf-8")
    assert 'description = "ünï"' in paths.lua.read_bytes().decode("utf-8")
    again = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply")],
                           input=json.dumps(model), capture_output=True, text=True, env=env)
    assert again.returncode == 0, again.stderr
    out = paths.config_dir.parent / "cheat.md"
    exported = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm"), "--export", "md",
                               str(out)], capture_output=True, text=True, env=env)
    assert exported.returncode == 0, exported.stderr
    assert "ünï" in out.read_bytes().decode("utf-8")


def test_preview_renders_without_writing_or_calling_hyprctl(paths, stubs):
    from hyprkbm.apply import preview

    result = preview(GOOD, paths)

    assert result["ok"] is True
    assert result["errors"] == []
    assert 'exec_cmd("firefox")' in result["lua"]
    assert result["current"] == ""
    assert not paths.model.exists()
    assert stubs.calls() == []


def test_preview_reports_errors_and_the_current_file(paths, stubs):
    from hyprkbm.apply import preview
    apply(GOOD, paths)
    bad = {"version": 1, "submaps": [], "unbinds": [],
           "binds": [{"id": "b1", "keys": "SUPER + B", "action": {"kind": "nope"}}]}

    result = preview(bad, paths)

    assert result["ok"] is False
    assert result["errors"][0]["id"] == "b1"
    assert result["lua"] == ""
    assert result["current"] == paths.lua.read_text()


def test_the_executable_previews(home_env, stubs, paths):
    env = dict(home_env, PATH=os.environ["PATH"])
    res = subprocess.run([sys.executable, str(ROOT / "bin" / "hyprkbm-apply"), "--preview"],
                         input=json.dumps(GOOD), capture_output=True, text=True, env=env)

    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["ok"] is True
    assert not paths.lua.exists()


def test_preview_handles_missing_lua_interpreter(paths, monkeypatch):
    from hyprkbm.apply import preview
    from hyprkbm import reader

    def raise_no_lua(*_a, **_k):
        raise FileNotFoundError("no lua")

    monkeypatch.setattr(reader, "interpreter", raise_no_lua)

    result = preview(GOOD, paths)

    assert result["ok"] is False
    assert len(result["errors"]) > 0
    assert "could not be read" in result["errors"][0]["message"]
    assert result["lua"] == ""
    assert result["current"] == ""


def test_a_backup_can_be_deleted_and_nothing_else(paths, tmp_path):
    folder = paths.backups / "20260101T000000000000"
    folder.mkdir(parents=True)
    (folder / "keybinds.json").write_text("{}")
    outside = tmp_path / "keep"
    outside.mkdir()

    assert applying.delete_backup(paths, "20260101T000000000000") is True
    assert not folder.exists()
    assert applying.delete_backup(paths, "20260101T000000000000") is False
    assert applying.delete_backup(paths, "../keep") is False
    assert applying.delete_backup(paths, "") is False
    assert outside.exists()
    # A link with a backup's name is not a backup; its target is never touched.
    (paths.backups / "20260202T000000000000").symlink_to(outside)
    assert applying.delete_backup(paths, "20260202T000000000000") is False
    assert outside.exists()
