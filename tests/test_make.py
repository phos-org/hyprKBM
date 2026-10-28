"""The Makefile, run for real into a throwaway DESTDIR."""
import os
import subprocess
import sys
import tarfile
from pathlib import Path

from hyprkbm import __version__

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("hyprkbm", "hyprkbm-apply", "hyprkbm-watch")


def make(*args, cwd=ROOT):
    return subprocess.run(["make", "--no-print-directory", *args], cwd=cwd,
                          capture_output=True, text=True)


def installed(dest):
    return sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if not p.is_dir())


def test_install_lays_out_the_tree_and_links_the_tools(tmp_path):
    res = make("install", "DESTDIR=%s" % tmp_path, "PREFIX=/usr")
    assert res.returncode == 0, res.stderr
    app = tmp_path / "usr/lib/hyprkbm"
    for tool in TOOLS:
        link = tmp_path / "usr/bin" / tool
        assert link.is_symlink() and os.readlink(link) == "/usr/lib/hyprkbm/bin/" + tool
        assert os.access(app / "bin" / tool, os.X_OK)
    for f in ("lib/hyprkbm/__init__.py", "lib/reader.lua", "share/actions.json",
              "quickshell/hyprkbm/shell.qml", "quickshell/hyprkbm/cheatsheet.qml"):
        assert (app / f).is_file(), f
    assert (tmp_path / "usr/share/applications/hyprkbm.desktop").is_file()
    unit = (tmp_path / "usr/lib/systemd/user/hyprkbm-watch.service").read_text()
    assert "ExecStart=/usr/bin/hyprkbm-watch\n" in unit
    assert (tmp_path / "usr/lib/systemd/user-preset/80-hyprkbm.preset").read_text() \
        == "enable hyprkbm-watch.service\n"
    files = installed(tmp_path)
    assert not [f for f in files if "__pycache__" in f or "/tests/" in f or "/docs/" in f]


def test_the_installed_tree_runs(tmp_path):
    assert make("install", "DESTDIR=%s" % tmp_path, "PREFIX=/usr").returncode == 0
    res = subprocess.run([sys.executable, str(tmp_path / "usr/lib/hyprkbm/bin/hyprkbm"), "--version"],
                         capture_output=True, text=True)
    assert res.stdout == "hyprkbm %s\n" % __version__


def test_without_systemd_there_is_no_unit(tmp_path):
    assert make("install", "DESTDIR=%s" % tmp_path, "PREFIX=/usr/local", "SYSTEMD=0").returncode == 0
    assert not [f for f in installed(tmp_path) if "systemd" in f]
    assert (tmp_path / "usr/local/bin/hyprkbm").is_symlink()


def test_uninstall_removes_everything_it_installed(tmp_path):
    assert make("install", "DESTDIR=%s" % tmp_path, "PREFIX=/usr").returncode == 0
    res = make("uninstall", "DESTDIR=%s" % tmp_path, "PREFIX=/usr")
    assert res.returncode == 0, res.stderr
    assert installed(tmp_path) == []


def test_dist_holds_the_tracked_files_under_one_folder(tmp_path):
    res = make("dist", "DISTDIR=%s" % tmp_path)
    assert res.returncode == 0, res.stderr
    tarball = tmp_path / ("hyprkbm-%s.tar.gz" % __version__)
    with tarfile.open(tarball) as tar:
        names = tar.getnames()
    top = "hyprkbm-%s/" % __version__
    assert all(n.startswith(top) or n == top.rstrip("/") for n in names)
    assert top + "Makefile" in names and top + "bin/hyprkbm" in names
    assert not [n for n in names if ".superpowers" in n]
