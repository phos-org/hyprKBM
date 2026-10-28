"""The recipes in packaging/: one version everywhere, checksums filled at
release, and the FreeBSD file list matching what make install writes."""
import hashlib
import importlib.util
import re
from pathlib import Path

from hyprkbm import __version__

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "packaging"

spec = importlib.util.spec_from_file_location("checksums", PKG / "checksums.py")
checksums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checksums)


def test_nix32_matches_a_known_value():
    # nix hash convert --to nix32 sha256:<sha256 of the empty string>
    digest = hashlib.sha256(b"").digest()
    assert checksums.nix32(digest) == "0mdqa9w1p6cmli6976v4wi0sw9r4p5prkj7lzfd1877wk11c9c73"


def copy_recipes(tmp_path):
    copies = tmp_path / "copy"
    for name in checksums.RECIPES:
        (copies / name).parent.mkdir(parents=True, exist_ok=True)
        (copies / name).write_text((ROOT / name).read_text())
    return copies


def tarball_of(tmp_path, data):
    tarball = tmp_path / ("hyprkbm-%s.tar.gz" % __version__)
    tarball.write_bytes(data)
    return tarball


def test_checksums_fill_every_recipe(tmp_path):
    tarball = tarball_of(tmp_path, b"not really a tarball")
    sha = hashlib.sha256(b"not really a tarball").hexdigest()
    copies = copy_recipes(tmp_path)

    checksums.fill(tarball, copies)

    for name in checksums.RECIPES:
        out = (copies / name).read_text()
        assert "0" * 64 not in out and "'SKIP'" not in out, name
        if name.endswith(".scm"):
            assert checksums.nix32(bytes.fromhex(sha)) in out
        else:
            assert sha in out, name
    assert "SIZE (hyprkbm-%s.tar.gz) = %d" % (__version__, len(b"not really a tarball")) \
        in (copies / "packaging/freebsd/distinfo").read_text()


def test_checksums_replace_an_older_release_hash(tmp_path):
    # The recipes in the repo hold the last release's hashes, so a second
    # fill must replace them, not leave them for a stale package.
    copies = copy_recipes(tmp_path)
    first = hashlib.sha256(b"first").hexdigest()
    checksums.fill(tarball_of(tmp_path, b"first"), copies)
    sha = hashlib.sha256(b"the second one").hexdigest()

    checksums.fill(tarball_of(tmp_path, b"the second one"), copies)

    for name in checksums.RECIPES:
        out = (copies / name).read_text()
        assert first not in out, name
        assert checksums.nix32(bytes.fromhex(first)) not in out, name
        if name.endswith(".scm"):
            assert checksums.nix32(bytes.fromhex(sha)) in out, name
        else:
            assert sha in out, name
    assert "SIZE (hyprkbm-%s.tar.gz) = %d" % (__version__, len(b"the second one")) \
        in (copies / "packaging/freebsd/distinfo").read_text()


def test_checksums_fail_on_a_recipe_without_one(tmp_path):
    import pytest
    copies = copy_recipes(tmp_path)
    (copies / "packaging/solus/package.yml").write_text("name : hyprkbm\n")
    with pytest.raises(checksums.NoChecksum, match="packaging/solus/package.yml"):
        checksums.fill(tarball_of(tmp_path, b"x"), copies)


def test_the_checksums_cli_exits_non_zero_without_a_checksum(tmp_path):
    import subprocess
    import sys
    copies = copy_recipes(tmp_path)
    (copies / "packaging/arch/PKGBUILD").write_text("pkgname=hyprkbm\n")
    res = subprocess.run([sys.executable, str(PKG / "checksums.py"), str(tarball_of(tmp_path, b"x")),
                          str(copies)], capture_output=True, text=True)
    assert res.returncode != 0
    assert "packaging/arch/PKGBUILD" in res.stderr


def test_versions_agree():
    v = re.escape(__version__)
    expected = {
        "packaging/arch/PKGBUILD": r"^pkgver=%s$" % v,
        "packaging/arch/.SRCINFO": r"^\tpkgver = %s$" % v,
        "packaging/debian/changelog": r"^hyprkbm \(%s\) unstable;" % v,
        "packaging/rpm/hyprkbm.spec": r"^Version:\s+%s$" % v,
        "flake.nix": r'^\s*version = "%s";$' % v,
        "packaging/guix/hyprkbm.scm": r'^\s*\(version "%s"\)' % v,
        "packaging/freebsd/Makefile": r"^DISTVERSION=\s+%s$" % v,
        "packaging/solus/package.yml": r"^version\s*: %s$" % v,
        "packaging/aerynos/stone.yaml": r"^version\s*: %s$" % v,
    }
    for name, pattern in expected.items():
        assert re.search(pattern, (ROOT / name).read_text(), re.M), name


def test_the_freebsd_plist_is_what_make_install_writes(tmp_path):
    import subprocess
    res = subprocess.run(["make", "--no-print-directory", "install", "DESTDIR=%s" % tmp_path,
                          "PREFIX=/usr/local", "SYSTEMD=0"], cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    prefix = tmp_path / "usr/local"
    files = sorted(str(p.relative_to(prefix)) for p in prefix.rglob("*")
                   if p.is_file() or p.is_symlink())
    plist = [l for l in (PKG / "freebsd/pkg-plist").read_text().splitlines() if l and not l.startswith("@")]
    assert plist == files


def test_the_changelog_has_this_version():
    assert re.search(r"^## \[%s\] - \d{4}-\d{2}-\d{2}$" % re.escape(__version__),
                     (ROOT / "CHANGELOG.md").read_text(), re.M)
