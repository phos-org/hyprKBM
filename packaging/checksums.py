#!/usr/bin/env python3
"""Fills the release tarball's checksum into every recipe.

  python3 packaging/checksums.py dist/hyprkbm-X.Y.Z.tar.gz [ROOT]

The recipes start with placeholders (zeros, or SKIP in the PKGBUILD), and
after a release they hold that release's hashes, copied back from the
release. So this replaces whatever hash is there. It fails, naming the
recipe, when a recipe has no checksum field, so a release can never ship an
unfilled or stale checksum. The release workflow runs it after building the
tarball and attaches the filled recipes to the release.
"""
import hashlib
import re
import sys
from pathlib import Path

HEX = r"(?:[0-9a-f]{64})"
# Where each recipe keeps its checksum, matched by the text around it rather
# than any 64-hex string: (pattern, value). The pattern's group is the text
# before the hash; the match after it is the hash, replaced by the value.
FIELDS = {
    "packaging/arch/PKGBUILD": [(r"(sha256sums=\(')(?:%s|SKIP)(?='\))" % HEX, "sha")],
    "packaging/arch/.SRCINFO": [(r"(^\tsha256sums = )(?:%s|SKIP)$" % HEX, "sha")],
    "packaging/rpm/hyprkbm.spec": [(r"(^# sha256 of Source0: )%s$" % HEX, "sha")],
    "packaging/guix/hyprkbm.scm": [(r'(\(base32 ")[0-9a-z]{52}(?="\))', "nix32")],
    "packaging/freebsd/distinfo": [(r"(^SHA256 \(.*\) = )%s$" % HEX, "sha"),
                                   (r"(^SIZE \(.*\) = )\d+$", "size")],
    "packaging/solus/package.yml": [(r"(\.tar\.gz : )%s$" % HEX, "sha")],
    "packaging/aerynos/stone.yaml": [(r"(\.tar\.gz : )%s$" % HEX, "sha")],
}
RECIPES = tuple(FIELDS)


class NoChecksum(Exception):
    pass


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
    values = {"sha": sha, "nix32": nix32(bytes.fromhex(sha)), "size": str(len(data))}
    texts = {}
    for name, fields in FIELDS.items():
        text = (Path(root) / name).read_text(encoding="utf-8")
        for pattern, value in fields:
            text, n = re.subn(pattern, lambda m: m.group(1) + values[value], text, flags=re.M)
            if n == 0:
                raise NoChecksum("%s: no checksum field found (%s)" % (name, pattern))
        texts[name] = text
    # Write only once every recipe matched, so a failure leaves none half-done.
    for name, text in texts.items():
        (Path(root) / name).write_text(text, encoding="utf-8")
    return sha


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.strip())
    try:
        print(fill(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else Path(__file__).resolve().parents[1]))
    except NoChecksum as e:
        sys.exit("checksums.py: %s" % e)
