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
