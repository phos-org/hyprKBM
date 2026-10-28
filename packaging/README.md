# Packaging

Every recipe here installs hyprKBM with the top-level `Makefile`
(`make install PREFIX=… DESTDIR=…`) from the release tarball
`hyprkbm-<version>.tar.gz`, a release asset, never GitHub's own archive.

| Recipe | For | Built and checked by |
|---|---|---|
| `arch/PKGBUILD` | Arch, Manjaro, Artix, Parabola (AUR) | CI (Arch container) |
| `debian/` | Debian 13 backports, 14, sid; Ubuntu 26.10; Kali; Devuan | CI (Debian testing container); `.deb` on the release |
| `rpm/hyprkbm.spec` | openSUSE Tumbleweed, Mageia, OpenMandriva, Rosa | CI (Tumbleweed container); `.rpm` on the release |
| `../flake.nix` | NixOS, Nix | CI (`nix build`) |
| `guix/hyprkbm.scm` | Guix | review only |
| `freebsd/` | FreeBSD ports (`x11/hyprkbm`) | review only; `pkg-plist` is checked against `make install` by the tests |
| `solus/package.yml` | Solus | review only |
| `aerynos/stone.yaml` | aerynOS | review only |

Checksums are placeholders (zeros, or `SKIP`) until a release exists. The
release workflow runs `checksums.py` on the tarball and attaches the filled
recipes to the release; copy them back here in a follow-up PR.

Not yet packaged, because their Hyprland predates the Lua config (0.55):
Fedora, Alpine, Ubuntu 26.04 LTS, ALT Linux. Add them once they catch up.
