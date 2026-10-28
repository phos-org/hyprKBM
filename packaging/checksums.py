#!/usr/bin/env python3
"""Fills the release tarball's checksum into every recipe.

  python3 packaging/checksums.py dist/hyprkbm-X.Y.Z.tar.gz [ROOT]

The recipes carry placeholders until a release exists: zeros, or SKIP in the
PKGBUILD. The release workflow runs this after building the tarball and
attaches the filled recipes to the release.
"""
import hashlib
import re
import sys
from pathlib import Path

RECIPES = (
    "packaging/arch/PKGBUILD",
    "packaging/arch/.SRCINFO",
    "packaging/rpm/hyprkbm.spec",
    "packaging/guix/hyprkbm.scm",
    "packaging/freebsd/distinfo",
    "packaging/solus/package.yml",
    "packaging/aerynos/stone.yaml",
)
ZEROS = "0" * 64
NIX32_ZEROS = "0" * 52
# Nix's base32: its own alphabet, read from the last byte backwards.
NIX32 = "0123456789abcdfghijklmnpqrsvwxyz"


def nix32(digest):
    length = (len(digest) * 8 - 1) // 5 + 1
    out = []
    for n in range(length - 1, -1, -1):
        b = n * 5
        i, j = divmod(b, 8)
        c = digest[i] >> j
        if i + 1 < len(digest):
            c |= digest[i + 1] << (8 - j)
        out.append(NIX32[c & 0x1F])
    return "".join(out)


def fill(tarball, root):
    data = Path(tarball).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    for name in RECIPES:
        path = Path(root) / name
        text = path.read_text(encoding="utf-8")
        if name.endswith(".scm"):
            text = text.replace(NIX32_ZEROS, nix32(bytes.fromhex(sha)))
        elif name.endswith("PKGBUILD"):
            text = re.sub(r"sha256sums=\('SKIP'\)", "sha256sums=('%s')" % sha, text)
        elif name.endswith(".SRCINFO"):
            text = text.replace("sha256sums = SKIP", "sha256sums = %s" % sha)
        elif name.endswith("distinfo"):
            text = text.replace(ZEROS, sha)
            text = re.sub(r"SIZE \((.*)\) = \d+", r"SIZE (\1) = %d" % len(data), text)
        else:
            text = text.replace(ZEROS, sha)
        path.write_text(text, encoding="utf-8")
    return sha


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.strip())
    print(fill(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else Path(__file__).resolve().parents[1]))
