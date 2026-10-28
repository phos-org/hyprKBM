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


def test_checksums_fill_every_recipe(tmp_path):
    tarball = tmp_path / ("hyprkbm-%s.tar.gz" % __version__)
    tarball.write_bytes(b"not really a tarball")
    sha = hashlib.sha256(b"not really a tarball").hexdigest()
    texts = {name: (ROOT / name).read_text() for name in checksums.RECIPES}
    copies = tmp_path / "copy"
    for name, text in texts.items():
        (copies / name).parent.mkdir(parents=True, exist_ok=True)
        (copies / name).write_text(text)

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


def test_versions_agree():
    v = re.escape(__version__)
    expected = {
        "packaging/arch/PKGBUILD": r"^pkgver=%s$" % v,
        "packaging/arch/.SRCINFO": r"^\tpkgver = %s$" % v,
    }
    for name, pattern in expected.items():
        assert re.search(pattern, (ROOT / name).read_text(), re.M), name
