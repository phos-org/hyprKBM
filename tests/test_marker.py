import os

from hyprkbm import marker


def test_expect_then_consume_once(paths):
    marker.expect_reload(paths)
    assert marker.consume(paths) is True
    assert marker.consume(paths) is False


def test_two_expects_are_two_consumes(paths):
    marker.expect_reload(paths)
    marker.expect_reload(paths)
    assert [marker.consume(paths) for _ in range(3)] == [True, True, False]


def test_cancel_undoes_an_expect(paths):
    marker.expect_reload(paths)
    marker.cancel_reload(paths)
    assert not paths.marker.exists()
    assert marker.consume(paths) is False


def test_a_stale_marker_is_removed_and_ignored(paths):
    marker.expect_reload(paths)
    old = paths.marker.stat().st_mtime - marker.MAX_AGE - 5
    os.utime(paths.marker, (old, old))
    assert marker.consume(paths) is False
    assert not paths.marker.exists()


def test_garbage_counts_as_zero(paths):
    paths.runtime_dir.mkdir(parents=True)
    paths.marker.write_text("not a number")
    marker.expect_reload(paths)
    assert marker.consume(paths) is True
    assert marker.consume(paths) is False
