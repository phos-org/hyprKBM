"""Tells hyprkbm-watch which configreloaded events apply caused itself.

The marker file holds a count of reloads apply has triggered and the watcher
has not yet seen. A bare touch-file cannot do this: apply's rollback reloads
twice, and the watcher may process the events late or together, so one flag
would let the second event trigger a pointless (and bind-duplicating) re-apply.
A counter makes each event consume exactly one expectation.

The file's mtime is the time of the latest expectation; anything older than
MAX_AGE is stale (the event never came) and is ignored, so it cannot swallow
the user's next real reload.

Apply and the watcher are separate processes, so every read-modify-write runs
under an exclusive flock on a lock file beside the marker.
"""
import fcntl
import os
import time
from contextlib import contextmanager

MAX_AGE = 10.0


@contextmanager
def _locked(paths):
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    with open(paths.runtime_dir / "self-reload.lock", "a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _count(paths, now):
    """The pending count; 0 when missing, unreadable, garbage or stale."""
    try:
        if now - paths.marker.stat().st_mtime > MAX_AGE:
            return 0
        return max(0, int(paths.marker.read_text(encoding="utf-8").strip()))
    except (OSError, ValueError):
        return 0


def _store(paths, count):
    if count <= 0:
        try:
            paths.marker.unlink()
        except FileNotFoundError:
            pass
    else:
        paths.marker.write_text("%d\n" % count, encoding="utf-8")  # also refreshes the mtime


def expect_reload(paths):
    with _locked(paths):
        _store(paths, _count(paths, time.time()) + 1)


def cancel_reload(paths):
    """Undo expect_reload when the reload failed and no event will come."""
    with _locked(paths):
        _store(paths, _count(paths, time.time()) - 1)


def consume(paths, now=None):
    """True if this configreloaded was apply's own (and uses up one expectation)."""
    now = time.time() if now is None else now
    with _locked(paths):
        count = _count(paths, now)
        _store(paths, count - 1)
        return count > 0
