"""hyprkbm-watch: what keeps the binds on screen after a reload.

A reload re-runs hyprland.lua and drops everything applied with eval, so the
watcher answers every configreloaded with `hyprkbm-apply --live` -- except
the reload hyprkbm-apply itself made, which it has already handled.
"""
import importlib.machinery
import importlib.util
import os
import socket
import time
from pathlib import Path

from hyprkbm import marker

WATCH = Path(__file__).resolve().parents[1] / "bin" / "hyprkbm-watch"


def load():
    loader = importlib.machinery.SourceFileLoader("hyprkbm_watch", str(WATCH))
    spec = importlib.util.spec_from_loader("hyprkbm_watch", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


watch = load()


def replay(chunks):
    reloads = []
    ours, theirs = socket.socketpair()
    for chunk in chunks:
        theirs.sendall(chunk)
    theirs.shutdown(socket.SHUT_WR)
    with ours:
        watch.read_events(ours, lambda: reloads.append(True))
    theirs.close()
    return len(reloads)


def test_a_reload_triggers_a_reapply():
    assert replay([b"configreloaded>>\n"]) == 1


def test_other_events_do_nothing():
    assert replay([b"activewindow>>kitty,~\n", b"workspace>>2\n"]) == 0


def test_an_event_split_across_reads_still_counts():
    assert replay([b"workspace>>2\nconfigrel", b"oaded>>\n"]) == 1


def test_a_fresh_marker_is_consumed_and_skips_the_reapply(paths):
    marker.expect_reload(paths)

    assert watch.consume_marker(paths) is True
    assert not paths.marker.exists()
    assert watch.consume_marker(paths) is False


def test_an_old_marker_is_removed_but_does_not_skip(paths):
    marker.expect_reload(paths)
    old = time.time() - marker.MAX_AGE - 5
    os.utime(paths.marker, (old, old))

    assert watch.consume_marker(paths) is False
    assert not paths.marker.exists()


def feed(chunks):
    ours, theirs = socket.socketpair()
    for chunk in chunks:
        theirs.sendall(chunk)
    theirs.shutdown(socket.SHUT_WR)
    return ours, theirs


def test_every_connect_runs_the_catch_up(paths, monkeypatch):
    calls = []
    monkeypatch.setattr(watch, "run_live", lambda command: calls.append(command))
    for _ in range(2):
        ours, theirs = feed([])
        with ours:
            watch.serve(ours, "apply", paths)
        theirs.close()

    assert calls == ["apply", "apply"]


def test_a_failing_subprocess_does_not_escape_run_live(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("not executable")

    monkeypatch.setattr(watch.subprocess, "run", boom)

    watch.run_live("apply")


def test_serve_skips_reloads_apply_made_and_answers_the_rest(paths, monkeypatch):
    calls = []
    monkeypatch.setattr(watch, "run_live", lambda command: calls.append(command))
    marker.expect_reload(paths)
    marker.expect_reload(paths)
    ours, theirs = feed([b"configreloaded>>\n" * 3])
    with ours:
        watch.serve(ours, "apply", paths)
    theirs.close()

    assert calls == ["apply", "apply"]  # catch-up, then the third reload
    assert not paths.marker.exists()


def replay_capture(chunks):
    left = []
    ours, theirs = socket.socketpair()
    for chunk in chunks:
        theirs.sendall(chunk)
    theirs.shutdown(socket.SHUT_WR)
    with ours:
        watch.read_events(ours, lambda: None, lambda: left.append(True))
    theirs.close()
    return len(left)


def test_capture_is_left_only_when_another_window_is_active():
    f = watch.should_leave_capture
    assert f("hyprkbm-capture", "kitty", "~") is True
    assert f("hyprkbm-capture", "org.quickshell", "Keybinds") is False
    assert f("hyprkbm-capture", "org.quickshell", "Other") is True
    assert f("", "kitty", "~") is False
    assert f("resize", "kitty", "~") is False


def test_a_stray_window_during_capture_runs_the_reset():
    assert replay_capture([b"submap>>hyprkbm-capture\n", b"activewindow>>kitty,~\n"]) == 1


def test_the_panel_being_active_during_capture_does_not_reset():
    assert replay_capture([
        b"submap>>hyprkbm-capture\n", b"activewindow>>org.quickshell,Keybinds\n"]) == 0


def test_no_reset_after_the_submap_is_left():
    assert replay_capture([
        b"submap>>hyprkbm-capture\n", b"submap>>\n", b"activewindow>>kitty,~\n"]) == 0


def test_a_title_containing_commas_is_kept_whole():
    assert replay_capture([
        b"activewindow>>org.quickshell,Keybinds\n", b"submap>>hyprkbm-capture\n",
        b"activewindow>>org.quickshell,Keybinds, more\n"]) == 1


def test_the_leave_lua_matches_capture_js():
    js = (WATCH.parents[1] / "quickshell/hyprkbm/lib/capture.js").read_text()
    assert watch.LEAVE_CAPTURE_LUA in js.replace("\\\"", '"')


def test_leave_capture_is_bounded_and_survives_failures(monkeypatch, capsys):
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        raise watch.subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(watch.subprocess, "run", fake)
    watch.leave_capture()
    assert seen["timeout"] == 5

    class R:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(watch.subprocess, "run", lambda *a, **k: R())
    watch.leave_capture()
    assert "boom" in capsys.readouterr().err
