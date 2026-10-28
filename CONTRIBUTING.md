# Contributing

## Running the tests

The helpers import nothing outside the Python standard library; `pytest` is
the only development dependency. The reader needs a Lua interpreter, the
panel's logic needs Node, and the packaging tests need GNU make.

```bash
python3 -m pytest tests/ -q
npm test                     # node --test tests/js/*.test.mjs
shellcheck install.sh
```

The suite needs no compositor. It points `HOME` at a temporary directory and
puts stub `hyprctl`, `notify-send` and `systemctl` executables first on
`PATH`. Nothing in it touches your real config or your running session. Keep
it that way: a test that writes to `~/.config` will eventually be run by
someone who is using the machine.

## Working on a live Hyprland session

Most of us develop on the machine whose Hyprland we are using, so a mistake
lands on our own desktop. The rules:

- Install only into a temporary `DESTDIR`, never into `/usr` or your home:
  `make install PREFIX=/usr DESTDIR="$(mktemp -d)"`. `tests/test_make.py`
  does exactly this.
- Build packages only in containers (below) or in CI, and never install a
  built package on your own machine (`pacman -U`, `dpkg -i`, `rpm -i`).
- `install.sh`, `hyprkbm --apply`, bare `hyprkbm`, `hyprkbm --cheatsheet`
  and `hyprctl reload` all change the running session. Run them only when
  that is what you mean to test (see [Testing against
  Hyprland](#testing-against-hyprland)).

## Checking the packaging

A local install, to see what a package would contain:

```bash
D=$(mktemp -d) && make install PREFIX=/usr DESTDIR="$D" && find "$D" | sort
make install PREFIX=/usr/local DESTDIR="$D" SYSTEMD=0   # no systemd, as on FreeBSD
make dist                                                # dist/hyprkbm-X.Y.Z.tar.gz
```

The packages build from the release tarball, in a container. Make the
tarball first with `make dist DISTDIR=/tmp/hyprkbm-dist`, then:

```bash
# Debian
docker run --rm -v /tmp/hyprkbm-dist:/dist debian:testing sh -euc '
  apt-get update -qq && apt-get install -y -qq build-essential debhelper lintian >/dev/null
  cd /tmp && tar xzf /dist/hyprkbm-*.tar.gz && cd hyprkbm-*/
  cp -r packaging/debian debian
  dpkg-buildpackage -us -uc -b
  lintian ../hyprkbm_*_all.deb || true
  apt-get install -y -qq ../hyprkbm_*_all.deb >/dev/null && hyprkbm --version'

# RPM (openSUSE Tumbleweed)
docker run --rm -v /tmp/hyprkbm-dist:/dist -v "$PWD/packaging/rpm":/spec:ro opensuse/tumbleweed sh -euc '
  zypper -q -n in rpm-build make systemd-rpm-macros tar gzip >/dev/null
  mkdir -p ~/rpmbuild/SOURCES && cp /dist/hyprkbm-*.tar.gz ~/rpmbuild/SOURCES/
  rpmbuild -bb --define "_topdir $HOME/rpmbuild" /spec/hyprkbm.spec
  rpm -qlp ~/rpmbuild/RPMS/noarch/hyprkbm-*.noarch.rpm'

# Arch
docker run --rm -v /tmp/hyprkbm-dist:/dist -v "$PWD/packaging/arch":/pkg:ro archlinux:latest sh -euc '
  pacman -Syu --noconfirm --needed base-devel >/dev/null
  useradd -m builder && cp /dist/hyprkbm-*.tar.gz /pkg/PKGBUILD /home/builder/
  chown builder /home/builder/*
  su builder -c "cd ~ && makepkg --nodeps --skipchecksums --noconfirm"
  tar -tf /home/builder/hyprkbm-*.pkg.tar.zst | head -20'

# Nix (reads git-tracked files only, so commit or git add first)
docker run --rm -v "$PWD":/src -w /src nixos/nix sh -euc '
  git config --global --add safe.directory /src
  nix --extra-experimental-features "nix-command flakes" build .#hyprkbm --print-build-logs
  ./result/bin/hyprkbm --version'
```

The Guix, FreeBSD, Solus and aerynOS recipes are reviewed against their
own documentation, not built; `tests/test_packaging.py` checks that every
recipe has the same version, that `checksums.py` fills them all, and that
FreeBSD's `pkg-plist` is what `make install` writes. See
[`packaging/README.md`](packaging/README.md).

## Layout

| Path | Holds |
|---|---|
| `bin/hyprkbm` | the command line, and the launcher for the panel and the cheatsheet |
| `bin/hyprkbm-apply` | the only writer of the keybinds files: validates, backs up, writes and applies, or `--preview` |
| `bin/hyprkbm-watch` | puts hyprKBM's binds back after every Hyprland reload that was not its own |
| `lib/reader.lua` | the sandbox that runs a config against a recording `hl` |
| `lib/hyprkbm/__init__.py` | the version, the one place it is set |
| `lib/hyprkbm/reader.py` | runs `hyprland.lua` through `reader.lua` and turns what it recorded into hand-written binds |
| `lib/hyprkbm/keys.py` | key combos, so two spellings of one combo compare equal |
| `lib/hyprkbm/model.py` | `keybinds.json`: validation, and how it combines with the hand-written binds |
| `lib/hyprkbm/render.py` | writes `keybinds.lua` from the model |
| `lib/hyprkbm/luaval.py` | Python values as Lua source; finds the Lua interpreter |
| `lib/hyprkbm/apply.py` | the only code that writes the keybinds files and hands them to Hyprland; backups |
| `lib/hyprkbm/marker.py` | the counted, lock-protected record of which reloads `hyprkbm-apply` made itself |
| `lib/hyprkbm/catalogue.py` | the action catalogue, and the step from an action to its dispatcher |
| `lib/hyprkbm/export.py` | the Markdown cheatsheet |
| `lib/hyprkbm/state.py` | everything the panel shows, as JSON (`hyprkbm --state`); first-run `keybinds.json`; settings |
| `lib/hyprkbm/paths.py` | where hyprKBM's files live |
| `share/actions.json` | the action catalogue |
| `share/applications/hyprkbm.desktop` | the launcher entry, **Keybinds** |
| `quickshell/hyprkbm/shell.qml` | the panel's window, its key handler, and a submap's leave key line with **Change** |
| `quickshell/hyprkbm/cheatsheet.qml` | the cheatsheet overlay: a second root file, so `qs -p` runs it as its own instance (own `-n`, own IPC target `cheatsheet`) beside the panel |
| `quickshell/hyprkbm/state/Store.qml` | the panel's single source of truth; edits leave it only through `hyprkbm-apply` |
| `quickshell/hyprkbm/components/Header.qml` | submap chips, search, the conflict stepper and the header's actions |
| `quickshell/hyprkbm/components/ModifierBar.qml` | the modifiers the keyboard shows |
| `quickshell/hyprkbm/components/Keyboard.qml`, `KeyBlock.qml`, `KeyCap.qml` | the on-screen keyboard, its blocks of rows, and one key |
| `quickshell/hyprkbm/components/ExtraKeys.qml` | mouse buttons, the wheel and media keys, and "+ any key…" |
| `quickshell/hyprkbm/components/BindPanel.qml`, `BindRow.qml` | the bind list (conflicts, *Stale* with **Drop my edit** and **Keep mine**, *Also bound as*) and one bind |
| `quickshell/hyprkbm/components/Editor.qml` | the bind editor |
| `quickshell/hyprkbm/components/StagedBar.qml` | what is staged, Apply, and the last apply's result |
| `quickshell/hyprkbm/components/Banner.qml` | setup problems: an unreadable config or `keybinds.json`, the watcher not running |
| `quickshell/hyprkbm/components/DiffDialog.qml` | **Review diff**, from `hyprkbm-apply --preview` |
| `quickshell/hyprkbm/components/BackupsDialog.qml` | **Backups**: restore, and the × that deletes one |
| `quickshell/hyprkbm/components/ExportDialog.qml` | **Export** |
| `quickshell/hyprkbm/components/SubmapDialog.qml` | **+ submap**, and changing a submap's leave key |
| `quickshell/hyprkbm/components/RemoveSubmapDialog.qml` | confirms removing a submap, and says which binds go with it |
| `quickshell/hyprkbm/components/SettingsPopup.qml` | the **⋯** menu: layout, cheatsheet key, config file, watcher |
| `quickshell/hyprkbm/components/ThemePopup.qml`, `ColourInput.qml`, `ColourPicker.qml` | **Theme**: preset, accent, dark or light |
| `quickshell/hyprkbm/components/Action.qml`, `Field.qml`, `Select.qml`, `Toggle.qml` | the button, form field, drop-down and switch everything else uses |
| `quickshell/hyprkbm/config/` | the theme: `Colors.qml`, `Theme.qml` (the theme file, and its only writer), `Radius.qml`, `Spacing.qml`, `Typography.qml` |
| `quickshell/hyprkbm/presets/` | the phos theme presets |
| `quickshell/hyprkbm/lib/model.js` | the staged `keybinds.json` and what Hyprland would end up with; stale edits |
| `quickshell/hyprkbm/lib/keys.js`, `qtkeys.js` | key combos (the twin of `keys.py`, both tested against `tests/fixtures/keys.json`), and Qt key codes as keysym names |
| `quickshell/hyprkbm/lib/keymap.js`, `labels.js`, `layouts.js` | which keycap shows which binds, what fits on it, and the ANSI and ISO keyboards |
| `quickshell/hyprkbm/lib/catalogue.js` | the action catalogue's helpers, twins of `catalogue.py` |
| `quickshell/hyprkbm/lib/search.js` | the search words and tags |
| `quickshell/hyprkbm/lib/diff.js` | the line diff for **Review diff** |
| `quickshell/hyprkbm/lib/capture.js` | find mode: the Lua that pauses binds for one press (the `hyprkbm-capture` submap, a 10 s timer) and turns a key event into a combo; `hyprkbm-watch` resets the submap if the panel dies mid-find |
| `quickshell/hyprkbm/lib/focus.js` | the keyboard areas' Tab order, the editor's field walk and the list cursor |
| `quickshell/hyprkbm/lib/quit.js` | what Esc does, and the 3 s window to quit with staged changes |
| `quickshell/hyprkbm/lib/cheatsheet.js` | the cheatsheet's bind, its labels' helpers, and the Lua that pauses binds while it is open (the `hyprkbm-cheatsheet` submap, re-armed every 5 s, reset 15 s after the last re-arm) and runs a bind on Enter |
| `systemd/hyprkbm-watch.service`, `80-hyprkbm.preset` | the watcher's user unit, and the preset that enables it in packages |
| `install.sh` | the per-user install from a clone: symlinks into `~/.local/bin` and `~/.config/systemd/user` |
| `Makefile` | `make install`, `uninstall` and `dist`, for packages and system-wide installs |
| `flake.nix`, `flake.lock` | the Nix package |
| `packaging/arch/` | `PKGBUILD` and `.SRCINFO` for the AUR |
| `packaging/debian/` | the Debian source package |
| `packaging/rpm/hyprkbm.spec` | openSUSE, Mageia and OpenMandriva |
| `packaging/guix/`, `freebsd/`, `solus/`, `aerynos/` | the Guix, FreeBSD port, Solus and aerynOS recipes |
| `packaging/checksums.py` | fills the release tarball's checksum into every recipe |
| `packaging/README.md` | which recipe is for which distro, and how each is checked |
| `.github/workflows/ci.yml` | pytest, node, ShellCheck, qmllint and the packages on every push and PR |
| `.github/workflows/packages.yml` | builds the tarball, `.deb`, `.rpm`, Arch package and Nix flake; run by `ci.yml` and `release.yml` |
| `.github/workflows/release.yml` | on a `v*` tag: checks it matches the version, builds the packages and publishes the release |
| `tests/` | pytest suites; `tests/js/` holds the node tests for `quickshell/hyprkbm/lib/*.js` |
| `docs/superpowers/` | the design spec and implementation plans |

## Running the panel

```bash
HYPRKBM_BIN="$PWD/bin" qs -p quickshell/hyprkbm -d -n
qs ipc -p quickshell/hyprkbm call hyprkbm state     # what it shows, as JSON
qs log -p quickshell/hyprkbm                         # QML warnings and errors
qs kill -p quickshell/hyprkbm
```

The IPC target can select keys, search and edit, but has no way to apply: a
scripted check must never change a real session. Logic belongs in
`quickshell/hyprkbm/lib/*.js` with a test in `tests/js/`; QML only binds and
draws.

Lint the QML. On Arch there is no `qtpaths6`:

```bash
find quickshell -name '*.qml' -print0 | xargs -0 /usr/lib/qt6/bin/qmllint -I /usr/lib/qt6/qml
```

Elsewhere, `qtpaths6 --query QT_INSTALL_QML` gives the import path for `-I`.
CI's qmllint is older and runs with fewer checks, so this is the real gate.

QML pitfalls this project has hit:

- Never compute a size from an item's own width when a sibling's width
  depends on that size. The panel froze from exactly that loop; the key size
  comes from the pane (see `Layouts.unitFor`).
- Import `QtQuick.Controls` as `QC` in files that use our `Action`
  component, which would otherwise clash with the built-in.
- Do not import `lib/keys.js` as `Keys` in a file with key handlers; it
  shadows the `Keys` attached property. `Editor.qml`, `SubmapDialog.qml`
  and `cheatsheet.qml` import it as `KeyNames`.
- `textTertiary` is for inactive states only; `tests/test_theme_presets.py`
  enforces it.

## Testing against Hyprland

This changes your running session, so only when you mean it:
`hyprkbm --status`, then `hyprkbm --apply`, then `hyprctl reload` and check
that `hyprctl binds` still lists the binds. `journalctl --user -u
hyprkbm-watch` shows what the watcher did.

## Conventions

- Commits: `<type>: <description>`, with `feat, fix, refactor, docs, test, chore, perf, style, build, ci`.
- Comments explain *why*, not *what*.

## Releasing

1. Set the version in `lib/hyprkbm/__init__.py` and in every recipe
   (`tests/test_packaging.py` lists them and fails until they agree), and add
   a `CHANGELOG.md` section.
2. Merge that to `main`, then tag it: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`.
3. The release workflow builds the tarball and packages, fills the checksums,
   and publishes the release (a pre-release while the version is below 1.0).
4. Copy the filled recipes from the release's `hyprkbm-X.Y.Z-recipes.tar.gz`
   back into `packaging/` in a PR, and push the PKGBUILD and `.SRCINFO` to the AUR.
