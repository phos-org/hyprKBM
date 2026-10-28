# hyprKBM 0.1.0 Release and Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release hyprKBM 0.1.0 as a development pre-release that installs system-wide on every distro shipping Hyprland with the Lua config (0.55+), with built `.deb`, `.rpm`, Arch package and source tarball attached to the GitHub release, and recipes for the AUR, Nix, Guix, FreeBSD, Solus and aerynOS.

**Architecture:** A `Makefile` installs the repo tree into `$(PREFIX)/lib/hyprkbm` and symlinks the three tools into `$(BINDIR)`. The scripts already find their files through `realpath(__file__)`, so the installed tree runs unchanged. Every distro recipe in `packaging/` calls `make install`. A reusable workflow builds the packages; CI runs it on PRs, and a tag runs it again and publishes the release. One version number lives in `lib/hyprkbm/__init__.py`; a test checks that every recipe agrees with it.

**Tech Stack:** GNU make, POSIX sh, Python 3 (stdlib), GitHub Actions, debhelper 13, rpmbuild (openSUSE), makepkg, Nix flakes, Guix, FreeBSD ports, Solus ypkg, aerynOS boulder.

## Global Constraints

- Version for this release: `0.1.0`. Tag: `v0.1.0`. GitHub release marked **pre-release**.
- Minimum Hyprland: **0.55** (first with Lua config). Tested on 0.56.2. Quickshell **0.3+** is optional (panel only).
- Python standard library only; no new runtime dependencies.
- Install root: `$(PREFIX)/lib/hyprkbm` holding `bin/`, `lib/`, `share/actions.json`, `quickshell/hyprkbm/`. Tools symlinked to `$(BINDIR)`. Desktop file in `$(DATADIR)/applications`. systemd user unit in `$(PREFIX)/lib/systemd/user`, preset in `$(PREFIX)/lib/systemd/user-preset`; `SYSTEMD=0` leaves both out.
- Release tarball: `hyprkbm-<version>.tar.gz`, top directory `hyprkbm-<version>/`, git-tracked files only, published as a release asset at `https://github.com/phos-org/hyprKBM/releases/download/v<version>/hyprkbm-<version>.tar.gz`. Every recipe downloads that asset, never GitHub's auto-generated archive.
- Packaging maintainer identity: `knikou01 <166297224+knikou01@users.noreply.github.com>` (the AUR account name may differ; it is free text).
- Live-session safety: never run `hyprctl reload`, `install.sh`, `hyprkbm --apply`, bare `hyprkbm`, `hyprkbm --cheatsheet`, or install a built package on this machine (`pacman -U`, `dpkg -i`, `rpm -i`). Package builds and install tests run in Docker containers or CI only. `make install` only ever into a temporary `DESTDIR`.
- Never commit `.superpowers/`. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Tagging, publishing the release and pushing to the AUR need the user's explicit go-ahead.

## File Structure

| File | Responsibility |
|---|---|
| `lib/hyprkbm/__init__.py` | `__version__`, the single version number |
| `bin/hyprkbm` | `--version`; first-run config creation |
| `bin/hyprkbm-watch` | first-run config creation |
| `lib/hyprkbm/state.py` | `ensure_config(paths)` |
| `lib/hyprkbm/luaval.py` | interpreter lookup also tries FreeBSD's `lua54`/`lua55` |
| `Makefile` | `install`, `uninstall`, `dist` |
| `packaging/README.md` | what each recipe is, how it is built and checked |
| `packaging/arch/PKGBUILD`, `.SRCINFO` | AUR package |
| `packaging/debian/*` | Debian/Ubuntu source package (copied to `debian/` to build) |
| `packaging/rpm/hyprkbm.spec` | openSUSE, Mageia, OpenMandriva |
| `flake.nix`, `flake.lock` | Nix (must sit at the repo root) |
| `packaging/guix/hyprkbm.scm` | Guix |
| `packaging/freebsd/*` | FreeBSD port (`x11/hyprkbm`) |
| `packaging/solus/package.yml` | Solus |
| `packaging/aerynos/stone.yaml` | aerynOS |
| `packaging/checksums.py` | fills the release tarball's checksums into every recipe |
| `.github/workflows/packages.yml` | reusable: builds tarball, deb, rpm, Arch, Nix |
| `.github/workflows/ci.yml` | also calls `packages.yml` on PRs |
| `.github/workflows/release.yml` | on `v*` tags: build, then publish the pre-release |
| `tests/test_make.py` | Makefile install tree, uninstall, dist |
| `tests/test_packaging.py` | recipe versions agree; FreeBSD plist matches the install; checksums script |
| `CHANGELOG.md` | release notes |
| `README.md`, `CONTRIBUTING.md` | install per distro; release procedure |

---

### Task 1: One version, `--version`, and the Lua names FreeBSD uses

**Files:**
- Modify: `lib/hyprkbm/__init__.py`, `bin/hyprkbm`, `lib/hyprkbm/luaval.py`
- Test: `tests/test_cli.py`, `tests/test_luaval.py`

**Interfaces:**
- Produces: `hyprkbm.__version__ == "0.1.0"`; `hyprkbm --version` prints `hyprkbm 0.1.0` and exits 0; `interpreter()` candidates `lua, lua5.5, lua5.4, lua55, lua54`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_version(home_env, stubs):
    from hyprkbm import __version__
    res = run(home_env, "--version")
    assert res.returncode == 0, res.stderr
    assert res.stdout == "hyprkbm %s\n" % __version__
    assert __version__ == "0.1.0"
```

Append to `tests/test_luaval.py` (it already imports from `hyprkbm.luaval`; add `interpreter` to that import if missing):

```python
def test_the_interpreter_is_also_found_by_freebsd_names(tmp_path, monkeypatch):
    lua = tmp_path / "lua54"
    lua.write_text("#!/bin/sh\n")
    lua.chmod(0o755)
    monkeypatch.delenv("HYPRKBM_LUA", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert interpreter() == str(lua)
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_cli.py::test_version tests/test_luaval.py::test_the_interpreter_is_also_found_by_freebsd_names`
Expected: FAIL (`--version` prints the usage and exits 2; `lua54` not found).

- [ ] **Step 3: Implement**

`lib/hyprkbm/__init__.py`, after the docstring:

```python
from pathlib import Path

__version__ = "0.1.0"

ROOT = Path(__file__).resolve().parents[2]
```

(keep `LIB` and `SHARE` as they are).

`bin/hyprkbm`: add `  hyprkbm --version            print the version` to the usage docstring after the `--set-layout` line; import it with the others: `from hyprkbm import __version__  # noqa: E402`; in `main`, before the `-h`/`--help` branch:

```python
    if argv == ["--version"]:
        print("hyprkbm %s" % __version__)
        return 0
```

`lib/hyprkbm/luaval.py`, `interpreter()`:

```python
    # Arch: lua. Debian, Ubuntu, Alpine: lua5.4. FreeBSD: lua54.
    for name in ("lua", "lua5.5", "lua5.4", "lua55", "lua54"):
```

and update its docstring to `Arch ships \`lua\`; Debian and Ubuntu ship versioned names, FreeBSD names without the dot.`

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -q && npm test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/__init__.py bin/hyprkbm lib/hyprkbm/luaval.py tests/test_cli.py tests/test_luaval.py
git commit -m "feat: hyprkbm --version, and find FreeBSD's lua54"
```

---

### Task 2: Create the config folder and an empty keybinds.json on first run

**Files:**
- Modify: `lib/hyprkbm/state.py`, `bin/hyprkbm`, `bin/hyprkbm-watch`, `README.md`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `Paths` (`paths.config_dir`, `paths.model`), `hyprkbm.apply.write_atomic`, `hyprkbm.model.EMPTY`.
- Produces: `ensure_config(paths) -> bool` (True when it created `keybinds.json`). Never raises.

A system package cannot write into a user's home, so hyprKBM creates `$XDG_CONFIG_HOME/hyprkbm/keybinds.json` itself. It never touches an existing file or a symlink (even a dangling one: a dotfiles repo not checked out yet), and never writes `settings.json`, so later defaults still reach the user.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_state.py` (add `ensure_config` to the `from hyprkbm.state import …` line):

```python
def test_first_run_creates_an_empty_keybinds_json(paths):
    assert ensure_config(paths) is True
    assert json.loads(paths.model.read_text()) == {
        "version": 1, "submaps": [], "binds": [], "unbinds": []}
    assert not paths.settings.exists()
    # Second run: nothing to do, and the file is left alone.
    paths.model.write_text('{"version": 1, "binds": []}')
    assert ensure_config(paths) is False
    assert paths.model.read_text() == '{"version": 1, "binds": []}'


def test_first_run_leaves_a_symlink_alone_even_a_dangling_one(paths, tmp_path):
    paths.config_dir.mkdir(parents=True)
    paths.model.symlink_to(tmp_path / "dotfiles" / "keybinds.json")
    assert ensure_config(paths) is False
    assert paths.model.is_symlink() and not (tmp_path / "dotfiles").exists()


def test_first_run_never_fails_a_command(paths):
    paths.config_dir.parent.mkdir(parents=True, exist_ok=True)
    paths.config_dir.write_text("a file where the folder should be")
    assert ensure_config(paths) is False


def test_the_cli_creates_the_config_but_not_for_help(home_env, paths, stubs):
    assert run(home_env, "--help").returncode == 0
    assert not paths.model.exists()
    assert run(home_env, "--status").returncode == 0
    assert paths.model.exists()
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_state.py -k "first_run or creates_the_config"`
Expected: FAIL with `ImportError: cannot import name 'ensure_config'`.

- [ ] **Step 3: Implement**

`lib/hyprkbm/state.py`: change the import to `from .model import EMPTY, ModelError, load_model, structure_errors` and add:

```python
def ensure_config(paths):
    """Creates the config folder and an empty keybinds.json on first run, so
    there is a real file to open and edit. A package cannot do this: it never
    writes into anyone's home. Never touches an existing file or a symlink,
    and never stops the command it runs in."""
    if paths.model.exists() or paths.model.is_symlink():
        return False
    try:
        paths.config_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(paths.model, json.dumps(EMPTY, indent=2) + "\n")
    except OSError:
        return False
    return True
```

`bin/hyprkbm`: import `ensure_config` from `hyprkbm.state` with the others. In `main`, right after the `--version` and `-h`/`--help` branches are checked and before any other command runs, call `ensure_config(paths)`. Concretely, move the `-h`/`--help` and `--version` branches to the top of `main` (just after `paths = Paths.from_env()`), then add the line `ensure_config(paths)` below them.

`bin/hyprkbm-watch`: `from hyprkbm.state import ensure_config  # noqa: E402`, and in `main()` after `paths = Paths.from_env()`: `ensure_config(paths)`.

`README.md`, in the `keybinds.json` section's first paragraph, add the sentence: `hyprKBM creates it, empty, the first time it runs.`

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add lib/hyprkbm/state.py bin/hyprkbm bin/hyprkbm-watch README.md tests/test_state.py
git commit -m "feat: create the config folder and an empty keybinds.json on first run"
```

---

### Task 3: `make install`, `make uninstall`, `make dist`

**Files:**
- Create: `Makefile`, `systemd/80-hyprkbm.preset`
- Modify: `systemd/hyprkbm-watch.service` (comment only), `.gitignore`
- Test: `tests/test_make.py`

**Interfaces:**
- Produces: variables `PREFIX` (default `/usr/local`), `DESTDIR`, `BINDIR`, `LIBDIR`, `DATADIR`, `SYSTEMDUSERDIR`, `SYSTEMDPRESETDIR`, `SYSTEMD` (1/0); targets `all` (no-op), `install`, `uninstall`, `dist` (writes `dist/hyprkbm-$(VERSION).tar.gz`). Needs GNU make (FreeBSD: `gmake`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_make.py`:

```python
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
```

- [ ] **Step 2: Run them to see them fail**

Run: `python -m pytest -q tests/test_make.py`
Expected: FAIL (`make: *** No rule to make target 'install'`).

- [ ] **Step 3: Implement**

Create `systemd/80-hyprkbm.preset`:

```
enable hyprkbm-watch.service
```

In `systemd/hyprkbm-watch.service`, replace the header comment's last sentence `install.sh links and enables it.` with `install.sh links and enables it; make install writes it with ExecStart pointing at the installed hyprkbm-watch.`

Create `Makefile` (recipe lines start with a TAB):

```make
# Installs hyprKBM system-wide or into a package's staging folder:
#
#   make install PREFIX=/usr DESTDIR=$pkgdir
#   make install PREFIX=/usr/local SYSTEMD=0     (no systemd, e.g. FreeBSD)
#   make dist                                     (the release tarball)
#
# GNU make. The tree goes to $(LIBDIR)/hyprkbm as it is in the repo: the tools
# find their files through their own real path, so the links in $(BINDIR)
# are all they need. For a per-user install from a clone, use install.sh.

PREFIX ?= /usr/local
DESTDIR ?=
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib
DATADIR ?= $(PREFIX)/share
SYSTEMDUSERDIR ?= $(PREFIX)/lib/systemd/user
SYSTEMDPRESETDIR ?= $(PREFIX)/lib/systemd/user-preset
SYSTEMD ?= 1
DISTDIR ?= dist

APPDIR = $(LIBDIR)/hyprkbm
TOOLS = hyprkbm hyprkbm-apply hyprkbm-watch
VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"$$/\1/p' lib/hyprkbm/__init__.py)
# Every file the tools need at run time: git's list in a clone, so nothing
# untracked slips in; the unpacked release tarball has no .git, and only
# tracked files to begin with.
TREE = $(shell if [ -d .git ]; then git ls-files lib share/actions.json quickshell; \
	else find lib share/actions.json quickshell -type f ! -path '*/__pycache__/*' ! -name '*.pyc'; fi | sort)

.PHONY: all install uninstall dist

all:

install:
	mkdir -p $(DESTDIR)$(APPDIR)/bin $(DESTDIR)$(BINDIR)
	for t in $(TOOLS); do \
		install -m 755 bin/$$t $(DESTDIR)$(APPDIR)/bin/$$t; \
		ln -sf $(APPDIR)/bin/$$t $(DESTDIR)$(BINDIR)/$$t; \
	done
	for f in $(TREE); do \
		mkdir -p $(DESTDIR)$(APPDIR)/$$(dirname $$f); \
		install -m 644 $$f $(DESTDIR)$(APPDIR)/$$f; \
	done
	mkdir -p $(DESTDIR)$(DATADIR)/applications
	install -m 644 share/applications/hyprkbm.desktop $(DESTDIR)$(DATADIR)/applications/
ifeq ($(SYSTEMD),1)
	mkdir -p $(DESTDIR)$(SYSTEMDUSERDIR) $(DESTDIR)$(SYSTEMDPRESETDIR)
	sed 's|%h/.local/bin|$(BINDIR)|' systemd/hyprkbm-watch.service \
		> $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	chmod 644 $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	install -m 644 systemd/80-hyprkbm.preset $(DESTDIR)$(SYSTEMDPRESETDIR)/
endif

uninstall:
	for t in $(TOOLS); do rm -f $(DESTDIR)$(BINDIR)/$$t; done
	rm -rf $(DESTDIR)$(APPDIR)
	rm -f $(DESTDIR)$(DATADIR)/applications/hyprkbm.desktop
	rm -f $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	rm -f $(DESTDIR)$(SYSTEMDPRESETDIR)/80-hyprkbm.preset

dist:
	mkdir -p $(DISTDIR)
	git archive --format=tar --prefix=hyprkbm-$(VERSION)/ HEAD \
		| gzip -n > $(DISTDIR)/hyprkbm-$(VERSION).tar.gz
	@echo $(DISTDIR)/hyprkbm-$(VERSION).tar.gz
```

Add `dist/` to `.gitignore`.

Note: `make dist` archives `HEAD`, so `test_dist_holds_the_tracked_files_under_one_folder` sees committed files only; it passes once Task 3 is committed. Run it after Step 5 if it fails before.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest -q tests/test_make.py`
Expected: all pass except possibly the `dist` test before the commit (see the note).

- [ ] **Step 5: Commit, then re-run the dist test**

```bash
git add Makefile systemd/80-hyprkbm.preset systemd/hyprkbm-watch.service .gitignore tests/test_make.py
git commit -m "feat: make install, uninstall and dist for system-wide packages"
python -m pytest -q tests/test_make.py
```

Expected: all pass.

---

### Task 4: The release checksums script and the recipe consistency tests

**Files:**
- Create: `packaging/checksums.py`, `packaging/README.md`
- Test: `tests/test_packaging.py`

**Interfaces:**
- Produces: `python3 packaging/checksums.py TARBALL` rewrites, in place, every recipe's checksum for that tarball; `checksums.nix32(digest_bytes) -> str` (Nix/Guix base32). Recipes hold a placeholder until then: the 64-zero hex string `0000…0000` (SHA-256), `SKIP` in the PKGBUILD's `sha256sums`, and 52 zeros (`0`×52) in the Guix `base32`. Tasks 5–8 create the recipes; `checksums.py` must update exactly the files listed in its `RECIPES`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_packaging.py`:

```python
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
```

(Tasks 5–8 append their own tests to this file.)

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest -q tests/test_packaging.py`
Expected: FAIL (`FileNotFoundError` for `packaging/checksums.py`).

- [ ] **Step 3: Implement**

Create `packaging/checksums.py`:

```python
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
```

Create `packaging/README.md`:

```markdown
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
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest -q tests/test_packaging.py::test_nix32_matches_a_known_value`
Expected: PASS. (`test_checksums_fill_every_recipe` passes once Tasks 5–8 have created every recipe; until then it fails on a missing file, which is expected.)

- [ ] **Step 5: Commit**

```bash
git add packaging/checksums.py packaging/README.md tests/test_packaging.py
git commit -m "build: a script that fills release checksums into the recipes"
```

---

### Task 5: Arch (AUR) PKGBUILD

**Files:**
- Create: `packaging/arch/PKGBUILD`, `packaging/arch/.SRCINFO`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_packaging.py`:

```python
def test_versions_agree():
    v = re.escape(__version__)
    expected = {
        "packaging/arch/PKGBUILD": r"^pkgver=%s$" % v,
        "packaging/arch/.SRCINFO": r"^\tpkgver = %s$" % v,
    }
    for name, pattern in expected.items():
        assert re.search(pattern, (ROOT / name).read_text(), re.M), name
```

- [ ] **Step 2: Run it to see it fail**

Run: `python -m pytest -q tests/test_packaging.py::test_versions_agree`
Expected: FAIL (file not found).

- [ ] **Step 3: Write the recipe**

`packaging/arch/PKGBUILD`:

```bash
# Maintainer: knikou01 <166297224+knikou01@users.noreply.github.com>
pkgname=hyprkbm
pkgver=0.1.0
pkgrel=1
pkgdesc="Keyboard-first keybind manager for Hyprland's Lua config"
arch=('any')
url="https://github.com/phos-org/hyprKBM"
license=('MIT')
depends=('hyprland>=0.55' 'python' 'lua')
optdepends=('quickshell: the keybind panel and the cheatsheet'
            'libnotify: notifications when an apply fails')
source=("$url/releases/download/v$pkgver/$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
    cd "$pkgname-$pkgver"
    make install PREFIX=/usr DESTDIR="$pkgdir"
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
```

(No `post_install` that enables the unit: Arch leaves enabling to the user, and the panel's banner offers **Start it**. The `.install` message is not needed because the README's Arch section says `systemctl --user enable --now hyprkbm-watch`.)

`packaging/arch/.SRCINFO` (tabs before the indented keys, exactly as `makepkg --printsrcinfo` writes it):

```
pkgbase = hyprkbm
	pkgdesc = Keyboard-first keybind manager for Hyprland's Lua config
	pkgver = 0.1.0
	pkgrel = 1
	url = https://github.com/phos-org/hyprKBM
	arch = any
	license = MIT
	depends = hyprland>=0.55
	depends = python
	depends = lua
	optdepends = quickshell: the keybind panel and the cheatsheet
	optdepends = libnotify: notifications when an apply fails
	source = https://github.com/phos-org/hyprKBM/releases/download/v0.1.0/hyprkbm-0.1.0.tar.gz
	sha256sums = SKIP

pkgname = hyprkbm
```

- [ ] **Step 4: Check it matches makepkg's own output, and test-build it locally**

```bash
cd packaging/arch && makepkg --printsrcinfo | diff - .SRCINFO && cd ../..
make dist DISTDIR=/tmp/claude-1000/hyprkbm-dist
B=$(mktemp -d) && cp packaging/arch/PKGBUILD $B/ && cp /tmp/claude-1000/hyprkbm-dist/hyprkbm-0.1.0.tar.gz $B/
(cd $B && makepkg --nodeps --skipchecksums --noconfirm) && tar -tf $B/hyprkbm-0.1.0-1-any.pkg.tar.zst | head -20
```

Expected: no diff; a `hyprkbm-0.1.0-1-any.pkg.tar.zst` listing `usr/bin/hyprkbm`, `usr/lib/hyprkbm/…`, `usr/lib/systemd/user/hyprkbm-watch.service`, `usr/share/licenses/hyprkbm/LICENSE`. **Do not install it** (`pacman -U` is forbidden on this machine).

- [ ] **Step 5: Run the tests and commit**

Run: `python -m pytest -q tests/test_packaging.py::test_versions_agree`
Expected: PASS.

```bash
git add packaging/arch tests/test_packaging.py
git commit -m "build: an Arch PKGBUILD for the AUR"
```

---

### Task 6: Debian package

**Files:**
- Create: `packaging/debian/control`, `rules`, `changelog`, `copyright`, `source/format`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Extend the version test**

In `test_versions_agree`, add to `expected`:

```python
        "packaging/debian/changelog": r"^hyprkbm \(%s\) unstable;" % v,
```

Run: `python -m pytest -q tests/test_packaging.py::test_versions_agree` — Expected: FAIL (file not found).

- [ ] **Step 2: Write the package files**

`packaging/debian/control`:

```
Source: hyprkbm
Section: utils
Priority: optional
Maintainer: knikou01 <166297224+knikou01@users.noreply.github.com>
Build-Depends: debhelper-compat (= 13)
Standards-Version: 4.7.0
Homepage: https://github.com/phos-org/hyprKBM
Rules-Requires-Root: no

Package: hyprkbm
Architecture: all
Depends: ${misc:Depends}, hyprland (>= 0.55), python3, lua5.4
Recommends: quickshell (>= 0.3), libnotify-bin
Description: keyboard-first keybind manager for Hyprland's Lua config
 hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
 and adds, overrides or removes binds without editing hyprland.lua. Binds
 are applied to the running Hyprland and kept across reloads by a systemd
 user service.
```

`packaging/debian/rules` (mode 755; recipe lines start with a TAB):

```make
#!/usr/bin/make -f
%:
	dh $@

override_dh_auto_install:
	$(MAKE) install PREFIX=/usr DESTDIR=$(CURDIR)/debian/hyprkbm

# The tests need pytest and Node; CI runs them before any package is built.
override_dh_auto_test:
```

`packaging/debian/changelog` (two spaces before `*`, one space before `--`, two spaces between the address and the date):

```
hyprkbm (0.1.0) unstable; urgency=medium

  * First development release.

 -- knikou01 <166297224+knikou01@users.noreply.github.com>  Tue, 27 Oct 2026 12:00:00 +0200
```

`packaging/debian/copyright`:

```
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: hyprKBM
Source: https://github.com/phos-org/hyprKBM

Files: *
Copyright: 2026 phos
License: Expat
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
```

`packaging/debian/source/format`:

```
3.0 (native)
```

dh_installsystemduser (debhelper 13) finds `usr/lib/systemd/user/hyprkbm-watch.service` in the package and enables it for every user, so no `postinst` is written by hand.

- [ ] **Step 3: Build it in a Debian testing container**

```bash
make dist DISTDIR=/tmp/claude-1000/hyprkbm-dist
docker run --rm -v /tmp/claude-1000/hyprkbm-dist:/dist debian:testing sh -euc '
  apt-get update -qq && apt-get install -y -qq build-essential debhelper lintian >/dev/null
  cd /tmp && tar xzf /dist/hyprkbm-0.1.0.tar.gz && cd hyprkbm-0.1.0
  cp -r packaging/debian debian
  dpkg-buildpackage -us -uc -b
  dpkg-deb -c ../hyprkbm_0.1.0_all.deb | grep -E "usr/bin/hyprkbm|systemd/user/hyprkbm"
  lintian ../hyprkbm_0.1.0_all.deb || true
  apt-get install -y -qq ../hyprkbm_0.1.0_all.deb >/dev/null && hyprkbm --version'
```

Expected: the package builds; the listing shows the links and the unit; the install pulls in Hyprland from testing and prints `hyprkbm 0.1.0`. Lintian warnings are reviewed: fix any **error** (`E:`); warnings may stay but are noted in the PR.

- [ ] **Step 4: Run the tests and commit**

Run: `python -m pytest -q tests/test_packaging.py::test_versions_agree` — Expected: PASS.

```bash
git add packaging/debian tests/test_packaging.py
git commit -m "build: Debian packaging"
```

---

### Task 7: RPM spec (openSUSE, Mageia, OpenMandriva)

**Files:**
- Create: `packaging/rpm/hyprkbm.spec`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Extend the version test**

Add to `expected`: `"packaging/rpm/hyprkbm.spec": r"^Version:\s+%s$" % v,` — run it, Expected: FAIL.

- [ ] **Step 2: Write the spec**

`packaging/rpm/hyprkbm.spec`:

```spec
Name:           hyprkbm
Version:        0.1.0
Release:        0
Summary:        Keyboard-first keybind manager for Hyprland's Lua config
License:        MIT
URL:            https://github.com/phos-org/hyprKBM
Source0:        %{url}/releases/download/v%{version}/%{name}-%{version}.tar.gz
# sha256 of Source0: 0000000000000000000000000000000000000000000000000000000000000000
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       hyprland >= 0.55
Requires:       python3
Requires:       (lua54 or lua55 or lua >= 5.4)
Recommends:     quickshell
Recommends:     /usr/bin/notify-send

%description
hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
and adds, overrides or removes binds without editing hyprland.lua. Binds
are applied to the running Hyprland and kept across reloads by a systemd
user service.

%prep
%autosetup

%build

%install
%make_install PREFIX=%{_prefix}

%post
%systemd_user_post hyprkbm-watch.service

%preun
%systemd_user_preun hyprkbm-watch.service

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/hyprkbm
%{_bindir}/hyprkbm-apply
%{_bindir}/hyprkbm-watch
%{_prefix}/lib/hyprkbm/
%{_datadir}/applications/hyprkbm.desktop
%{_userunitdir}/hyprkbm-watch.service
%{_userpresetdir}/80-hyprkbm.preset

%changelog
* Tue Oct 27 2026 knikou01 <166297224+knikou01@users.noreply.github.com> - 0.1.0-0
- First development release.
```

(`CHANGELOG.md` is created in Task 9; until then the Step 3 build uses a tarball made after Task 9 is committed, or temporarily drop `CHANGELOG.md` from `%doc` for the local check only.)

- [ ] **Step 3: Build it in a Tumbleweed container**

```bash
make dist DISTDIR=/tmp/claude-1000/hyprkbm-dist
docker run --rm -v /tmp/claude-1000/hyprkbm-dist:/dist -v "$PWD/packaging/rpm":/spec:ro opensuse/tumbleweed sh -euc '
  zypper -q -n in rpm-build make systemd-rpm-macros >/dev/null
  mkdir -p ~/rpmbuild/SOURCES && cp /dist/hyprkbm-0.1.0.tar.gz ~/rpmbuild/SOURCES/
  rpmbuild -bb /spec/hyprkbm.spec
  rpm -qlp ~/rpmbuild/RPMS/noarch/hyprkbm-0.1.0-0.noarch.rpm | grep -E "bin/hyprkbm|user/hyprkbm"'
```

Expected: the RPM builds and lists the tools and the unit.

- [ ] **Step 4: Run the tests and commit**

Run: `python -m pytest -q tests/test_packaging.py::test_versions_agree` — Expected: PASS.

```bash
git add packaging/rpm tests/test_packaging.py
git commit -m "build: an RPM spec for openSUSE, Mageia and OpenMandriva"
```

---

### Task 8: Nix flake, Guix, FreeBSD, Solus and aerynOS recipes

**Files:**
- Create: `flake.nix`, `flake.lock`, `packaging/guix/hyprkbm.scm`, `packaging/freebsd/{Makefile,distinfo,pkg-descr,pkg-plist,pkg-message}`, `packaging/solus/package.yml`, `packaging/aerynos/stone.yaml`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Extend the tests**

Add to `expected` in `test_versions_agree`:

```python
        "flake.nix": r'^\s*version = "%s";$' % v,
        "packaging/guix/hyprkbm.scm": r'^\s*\(version "%s"\)' % v,
        "packaging/freebsd/Makefile": r"^DISTVERSION=\s+%s$" % v,
        "packaging/solus/package.yml": r"^version\s*: %s$" % v,
        "packaging/aerynos/stone.yaml": r"^version\s*: %s$" % v,
```

Append:

```python
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
```

Run: `python -m pytest -q tests/test_packaging.py` — Expected: FAIL (files missing).

- [ ] **Step 2: Nix flake**

`flake.nix`:

```nix
{
  description = "hyprKBM: a keyboard-first keybind manager for Hyprland's Lua config";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      packages = forAll (pkgs: rec {
        hyprkbm = pkgs.stdenvNoCC.mkDerivation {
          pname = "hyprkbm";
          version = "0.1.0";
          src = self;

          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = [ pkgs.python3 ];
          dontBuild = true;
          makeFlags = [ "PREFIX=${placeholder "out"}" ];

          # hyprctl and qs come from the user's Hyprland and Quickshell; Lua
          # and notify-send are hyprKBM's own and go on its PATH.
          postFixup = ''
            for tool in hyprkbm hyprkbm-apply hyprkbm-watch; do
              wrapProgram $out/lib/hyprkbm/bin/$tool \
                --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.lua5_4 pkgs.libnotify ]}
            done
          '';

          meta = {
            description = "Keyboard-first keybind manager for Hyprland's Lua config";
            homepage = "https://github.com/phos-org/hyprKBM";
            license = pkgs.lib.licenses.mit;
            platforms = pkgs.lib.platforms.linux;
            mainProgram = "hyprkbm";
          };
        };
        default = hyprkbm;
      });
    };
}
```

Generate the lock and build, in a container (no Nix on this machine):

```bash
docker run --rm -v "$PWD":/src -w /src nixos/nix sh -euc '
  git config --global --add safe.directory /src
  nix --extra-experimental-features "nix-command flakes" flake lock
  nix --extra-experimental-features "nix-command flakes" build .#hyprkbm --print-build-logs
  ./result/bin/hyprkbm --version'
```

Expected: `flake.lock` written; prints `hyprkbm 0.1.0`. The flake reads git-tracked files only, so commit `flake.nix` first (`git add flake.nix` is enough for Nix to see it). Then `sudo chown -R "$USER" flake.lock result 2>/dev/null; rm -f result`.

- [ ] **Step 3: Guix**

`packaging/guix/hyprkbm.scm`:

```scheme
;; guix build -f packaging/guix/hyprkbm.scm   (or add it to a channel)
(define-module (hyprkbm)
  #:use-module (guix packages)
  #:use-module (guix download)
  #:use-module (guix gexp)
  #:use-module (guix build-system gnu)
  #:use-module ((guix licenses) #:prefix license:)
  #:use-module (gnu packages lua)
  #:use-module (gnu packages python))

(define-public hyprkbm
  (package
    (name "hyprkbm")
    (version "0.1.0")
    (source
     (origin
       (method url-fetch)
       (uri (string-append "https://github.com/phos-org/hyprKBM/releases/download/v"
                           version "/hyprkbm-" version ".tar.gz"))
       (sha256 (base32 "0000000000000000000000000000000000000000000000000000"))))
    (build-system gnu-build-system)
    (arguments
     (list
      #:tests? #f
      #:make-flags #~(list (string-append "PREFIX=" #$output))
      #:phases
      #~(modify-phases %standard-phases
          (delete 'configure)
          (delete 'build)
          (add-after 'install 'wrap
            (lambda* (#:key inputs #:allow-other-keys)
              (let ((lua (dirname (search-input-file inputs "bin/lua"))))
                (for-each
                 (lambda (tool)
                   (wrap-program (string-append #$output "/lib/hyprkbm/bin/" tool)
                     `("PATH" prefix (,lua))))
                 '("hyprkbm" "hyprkbm-apply" "hyprkbm-watch"))))))))
    (inputs (list lua python))
    (home-page "https://github.com/phos-org/hyprKBM")
    (synopsis "Keyboard-first keybind manager for Hyprland's Lua config")
    (description
     "hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
and adds, overrides or removes binds without editing hyprland.lua.")
    (license license:expat)))

hyprkbm
```

Verify against the Guix manual's `gnu-build-system` and `wrap-program` sections (https://guix.gnu.org/manual/en/html_node/Build-Systems.html) and fix any argument name that differs; record in the PR that it is review-checked, not built.

- [ ] **Step 4: FreeBSD port**

`packaging/freebsd/Makefile` (tabs after the `=`):

```make
PORTNAME=	hyprkbm
DISTVERSION=	0.1.0
CATEGORIES=	x11
MASTER_SITES=	https://github.com/phos-org/hyprKBM/releases/download/v${DISTVERSION}/

MAINTAINER=	166297224+knikou01@users.noreply.github.com
COMMENT=	Keyboard-first keybind manager for Hyprland's Lua config
WWW=		https://github.com/phos-org/hyprKBM

LICENSE=	MIT
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	hyprctl:x11-wm/hyprland

USES=		gmake lua:54,run python:run shebangfix
SHEBANG_FILES=	bin/hyprkbm bin/hyprkbm-apply bin/hyprkbm-watch
NO_ARCH=	yes
NO_BUILD=	yes
MAKE_ARGS=	PREFIX=${PREFIX} SYSTEMD=0

.include <bsd.port.mk>
```

`packaging/freebsd/distinfo`:

```
TIMESTAMP = 1793095200
SHA256 (hyprkbm-0.1.0.tar.gz) = 0000000000000000000000000000000000000000000000000000000000000000
SIZE (hyprkbm-0.1.0.tar.gz) = 0
```

`packaging/freebsd/pkg-descr`:

```
hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
and adds, overrides or removes binds without editing hyprland.lua. The
panel needs Quickshell (x11/quickshell); the command line works
without it.
```

`packaging/freebsd/pkg-message`:

```
[
{ type: install
  message: <<EOM
FreeBSD has no systemd, so start hyprKBM's watcher from hyprland.lua:

    hl.on("hyprland.start", function()
        hl.exec_cmd("hyprkbm-watch")
    end)

Without it, binds made in hyprKBM are lost at the next Hyprland reload.
EOM
}
]
```

`packaging/freebsd/pkg-plist`: generate it from the real install so it cannot drift:

```bash
D=$(mktemp -d) && make --no-print-directory install DESTDIR=$D PREFIX=/usr/local SYSTEMD=0 >/dev/null
(cd $D/usr/local && find . \( -type f -o -type l \) | sed 's|^\./||' | sort) > packaging/freebsd/pkg-plist
```

(`test_the_freebsd_plist_is_what_make_install_writes` keeps it in sync from now on.)

- [ ] **Step 5: Solus and aerynOS**

`packaging/solus/package.yml`:

```yaml
name       : hyprkbm
version    : 0.1.0
release    : 1
source     :
    - https://github.com/phos-org/hyprKBM/releases/download/v0.1.0/hyprkbm-0.1.0.tar.gz : 0000000000000000000000000000000000000000000000000000000000000000
homepage   : https://github.com/phos-org/hyprKBM
license    : MIT
component  : desktop
summary    : Keyboard-first keybind manager for Hyprland's Lua config
description: |
    hyprKBM shows every keybind from hyprland.lua and its own on a keyboard, and adds, overrides or removes binds without editing hyprland.lua.
rundeps    :
    - hyprland
    - lua
    - python3
    - quickshell
install    : |
    %make_install PREFIX=/usr
```

`packaging/aerynos/stone.yaml`:

```yaml
name        : hyprkbm
version     : 0.1.0
release     : 1
homepage    : https://github.com/phos-org/hyprKBM
upstreams   :
    - https://github.com/phos-org/hyprKBM/releases/download/v0.1.0/hyprkbm-0.1.0.tar.gz : 0000000000000000000000000000000000000000000000000000000000000000
summary     : Keyboard-first keybind manager for Hyprland's Lua config
description : |
    hyprKBM shows every keybind from hyprland.lua and its own on a keyboard, and adds, overrides or removes binds without editing hyprland.lua.
license     : MIT
rundeps     :
    - binary(hyprctl)
    - binary(lua)
    - binary(python3)
install     : |
    %make_install PREFIX=%(prefix)
```

Verify both against their distro docs (Solus: https://help.getsol.us/docs/packaging/package.yml ; aerynOS: the `stone.yaml` reference in https://github.com/AerynOS/os-tools / recipes repo) and fix any key that differs.

- [ ] **Step 6: Run the tests and commit**

Run: `python -m pytest -q tests/test_packaging.py`
Expected: all pass, including `test_checksums_fill_every_recipe`.

```bash
git add flake.nix flake.lock packaging tests/test_packaging.py
git commit -m "build: Nix flake, and Guix, FreeBSD, Solus and aerynOS recipes"
```

---

### Task 9: CHANGELOG, README install section, requirements

**Files:**
- Create: `CHANGELOG.md`
- Modify: `README.md`, `CONTRIBUTING.md`, `tests/test_packaging.py`

- [ ] **Step 1: Test that the changelog names the version**

Append to `tests/test_packaging.py`:

```python
def test_the_changelog_has_this_version():
    assert re.search(r"^## \[%s\] - \d{4}-\d{2}-\d{2}$" % re.escape(__version__),
                     (ROOT / "CHANGELOG.md").read_text(), re.M)
```

Run it — Expected: FAIL.

- [ ] **Step 2: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to hyprKBM. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/): until 1.0, any release may change
how things work.

## [0.1.0] - 2026-10-27

First development release.

### Added
- Reads the binds in `hyprland.lua` by running it in a sandbox, and adds,
  overrides or removes binds through hyprKBM's own `keybinds.json`, never
  editing `hyprland.lua`.
- Applies binds to the running Hyprland, checks them first, keeps a backup
  of every apply, and keeps them across reloads with the `hyprkbm-watch`
  service.
- The keyboard panel (Quickshell): every bind on a keyboard, search, find a
  bind by pressing it, conflicts, submaps with their leave key, stale-edit
  handling, backups with restore and delete, themes, ANSI and ISO layouts.
- The cheatsheet overlay (`hyprkbm --cheatsheet`), and a Markdown export.
- Packages: Arch (AUR), Debian/Ubuntu, openSUSE/Mageia/OpenMandriva, Nix,
  Guix, FreeBSD, Solus, aerynOS; `make install` for anything else.

[0.1.0]: https://github.com/phos-org/hyprKBM/releases/tag/v0.1.0
```

- [ ] **Step 3: README**

In the Requirements table, replace the Hyprland row with:
`| Hyprland | 0.55 or later, with Lua configuration (\`hyprland.lua\`). Tested on 0.56.2. |`

Replace the start of the `## Install` section (up to, not including, `### Without systemd`) with:

````markdown
## Install

| Distro | |
|---|---|
| Arch, Manjaro, Artix | `yay -S hyprkbm` (AUR), or the `.pkg.tar.zst` from the [release](https://github.com/phos-org/hyprKBM/releases) |
| Debian 14 / sid / 13 backports, Ubuntu 26.10, Kali, Devuan | the `.deb` from the release: `sudo apt install ./hyprkbm_*_all.deb` |
| openSUSE Tumbleweed, Mageia, OpenMandriva | the `.rpm` from the release: `sudo zypper in ./hyprkbm-*.noarch.rpm` (or `dnf`/`urpmi`) |
| NixOS, Nix | `nix profile install github:phos-org/hyprKBM` |
| Guix, FreeBSD, Solus, aerynOS | recipes in [`packaging/`](packaging/) |
| anything else | `make install PREFIX=/usr` from the release tarball (GNU make; add `SYSTEMD=0` without systemd) |

Distros whose Hyprland predates the Lua config (Fedora, Alpine, Ubuntu
26.04) are not packaged yet.

The watcher keeps your binds applied across reloads and must run. The
Debian and RPM packages enable it for every user; elsewhere, once:

```bash
systemctl --user enable --now hyprkbm-watch
```

### From a clone

For development, or to follow `main`:

```bash
git clone https://github.com/phos-org/hyprKBM.git ~/src/hyprKBM
~/src/hyprKBM/install.sh
```
````

Keep the existing bullet list about `install.sh` (links, re-pointing, `~/.local/bin` on `PATH`) and the `hyprkbm --status` check under `### From a clone`.

- [ ] **Step 4: CONTRIBUTING release steps**

Append to `CONTRIBUTING.md`:

```markdown
## Releasing

1. Set the version in `lib/hyprkbm/__init__.py` and in every recipe
   (`tests/test_packaging.py` lists them and fails until they agree), and add
   a `CHANGELOG.md` section.
2. Merge that to `main`, then tag it: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`.
3. The release workflow builds the tarball and packages, fills the checksums,
   and publishes the release (a pre-release while the version is below 1.0).
4. Copy the filled recipes from the release's `hyprkbm-X.Y.Z-recipes.tar.gz`
   back into `packaging/` in a PR, and push the PKGBUILD and `.SRCINFO` to the AUR.
```

- [ ] **Step 5: Bring the whole README and CONTRIBUTING up to date**

Not only the sections above: read both files top to bottom against the code as it is on this branch, and fix everything that is stale, missing or wrong. At least check:

- **README**
  - Every feature since v1 is described:
    - submaps: `[`/`]` switching, the × that removes one, the leave key and **Change**;
    - stale edits: **Drop my edit** and **Keep mine**;
    - the panel re-reads `hyprland.lua` on reload;
    - backups: the × that deletes one;
    - `keybinds.json` may be a symlink;
    - first-run creation of `keybinds.json`;
    - apply refuses a bind that enters a missing submap;
    - the cheatsheet.
  - The command list under "Using it" matches `hyprkbm --help` exactly, including `--version` and `--delete-backup`. Compare it with the docstring in `bin/hyprkbm`.
  - The Keys table matches the key handler in `quickshell/hyprkbm/shell.qml` (including `[` / `]`).
  - The Requirements table: Hyprland 0.55+, Lua names (including `lua54` on FreeBSD), Quickshell optional, systemd optional with the fallback.
  - The Uninstall instructions cover packages (the package manager) as well as `install.sh --uninstall`.
  - Every link and anchor resolves. Check `#without-systemd` and every relative file link with `grep -o '](#[^)]*)' README.md` and `grep -o '](\([^h#][^)]*\))' README.md` against the headings and files that exist.
- **CONTRIBUTING**
  - The file-by-file table lists every file in `lib/`, `bin/`, `quickshell/hyprkbm/` (components, lib, state, config), `packaging/`, `Makefile`, `flake.nix` and `.github/workflows/`. Compare with `git ls-files`, and add or remove rows to match. Include:
    - `RemoveSubmapDialog.qml`;
    - `checksums.py`;
    - `packages.yml` and `release.yml`.
  - How to run every test suite:
    - pytest;
    - `npm test`;
    - qmllint with the `-I` form;
    - `make install DESTDIR=…` for a local packaging check;
    - the Docker package builds from this plan.
  - The live-session safety rules for contributors working on a live Hyprland session:
    - test installs only into a temporary `DESTDIR`;
    - build packages only in containers.
  - The QML pitfalls list still matches the code.
  - The release steps from Step 4.

Write down every change in the commit message body.

- [ ] **Step 6: Run everything and commit**

Run: `python -m pytest -q && npm test`
Expected: all pass.

```bash
git add CHANGELOG.md README.md CONTRIBUTING.md tests/test_packaging.py
git commit -m "docs: changelog, per-distro install, release steps, and bring README and CONTRIBUTING up to date"
```

---

### Task 10: Build the packages in CI, and publish on a tag

**Files:**
- Create: `.github/workflows/packages.yml`, `.github/workflows/release.yml`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `packages.yml` (`on: workflow_call`) uploads artifacts `tarball`, `deb`, `rpm`, `arch`; `release.yml` on `v*` tags creates the GitHub release with those files, `SHA256SUMS`, and `hyprkbm-<version>-recipes.tar.gz`.

- [ ] **Step 1: Reusable build workflow**

`.github/workflows/packages.yml`:

```yaml
name: Packages

on:
  workflow_call:

permissions:
  contents: read

jobs:
  tarball:
    name: Tarball
    runs-on: ubuntu-24.04
    outputs:
      version: ${{ steps.v.outputs.version }}
    steps:
      - uses: actions/checkout@v7
      - id: v
        run: echo "version=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' lib/hyprkbm/__init__.py)" >> "$GITHUB_OUTPUT"
      - run: make dist
      - uses: actions/upload-artifact@v4
        with: { name: tarball, path: dist/*.tar.gz }

  deb:
    name: Debian package
    needs: tarball
    runs-on: ubuntu-24.04
    container: debian:testing
    steps:
      - uses: actions/download-artifact@v4
        with: { name: tarball }
      - run: |
          apt-get update -qq && apt-get install -y -qq build-essential debhelper >/dev/null
          tar xzf hyprkbm-*.tar.gz && cd hyprkbm-*/
          cp -r packaging/debian debian
          dpkg-buildpackage -us -uc -b
          apt-get install -y -qq ../hyprkbm_*_all.deb >/dev/null && hyprkbm --version
      - uses: actions/upload-artifact@v4
        with: { name: deb, path: hyprkbm_*_all.deb }

  rpm:
    name: RPM package
    needs: tarball
    runs-on: ubuntu-24.04
    container: opensuse/tumbleweed
    steps:
      - run: zypper -q -n in rpm-build make systemd-rpm-macros tar gzip
      - uses: actions/download-artifact@v4
        with: { name: tarball }
      - run: |
          mkdir -p ~/rpmbuild/SOURCES && cp hyprkbm-*.tar.gz ~/rpmbuild/SOURCES/
          tar xzf hyprkbm-*.tar.gz --wildcards '*/packaging/rpm/hyprkbm.spec' --strip-components=3
          rpmbuild -bb hyprkbm.spec
          cp ~/rpmbuild/RPMS/noarch/*.rpm .
      - uses: actions/upload-artifact@v4
        with: { name: rpm, path: "*.rpm" }

  arch:
    name: Arch package
    needs: tarball
    runs-on: ubuntu-24.04
    container: archlinux:latest
    steps:
      - run: pacman -Syu --noconfirm --needed base-devel
      - uses: actions/download-artifact@v4
        with: { name: tarball }
      - run: |
          useradd -m builder
          tar xzf hyprkbm-*.tar.gz --wildcards '*/packaging/arch/PKGBUILD' --strip-components=3
          cp hyprkbm-*.tar.gz PKGBUILD /home/builder/ && chown builder /home/builder/*
          su builder -c 'cd ~ && makepkg --nodeps --skipchecksums --noconfirm'
          cp /home/builder/*.pkg.tar.zst .
      - uses: actions/upload-artifact@v4
        with: { name: arch, path: "*.pkg.tar.zst" }

  nix:
    name: Nix flake
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
      - uses: DeterminateSystems/nix-installer-action@v16
      - run: nix build .#hyprkbm --print-build-logs && ./result/bin/hyprkbm --version
```

Before committing, check each third-party action's current major version on its GitHub page (`actions/upload-artifact`, `actions/download-artifact`, `DeterminateSystems/nix-installer-action`) and use the latest major that is at least two weeks old; match `actions/checkout@v7` as `ci.yml` already does.

- [ ] **Step 2: Run it from CI**

Append to `.github/workflows/ci.yml` under `jobs:`:

```yaml
  packages:
    uses: ./.github/workflows/packages.yml
```

- [ ] **Step 3: Release workflow**

`.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags: ['v*']

permissions:
  contents: read

jobs:
  check:
    name: Tag matches the version
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
      - run: |
          v=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' lib/hyprkbm/__init__.py)
          test "v$v" = "$GITHUB_REF_NAME" || { echo "tag $GITHUB_REF_NAME but version $v"; exit 1; }

  packages:
    needs: check
    uses: ./.github/workflows/packages.yml

  publish:
    name: Publish
    needs: packages
    runs-on: ubuntu-24.04
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v7
      - uses: actions/download-artifact@v4
        with: { path: out, merge-multiple: true }
      - run: |
          v=${GITHUB_REF_NAME#v}
          python3 packaging/checksums.py out/hyprkbm-$v.tar.gz .
          tar czf out/hyprkbm-$v-recipes.tar.gz packaging flake.nix flake.lock
          (cd out && sha256sum * > SHA256SUMS)
          # The section for this version, without its heading.
          awk -v h="## [$v]" 'index($0, h) == 1 {on=1; next} on && /^## \[/ {exit} on' CHANGELOG.md > notes.md
          pre=""; case "$v" in 0.*) pre="--prerelease" ;; esac
          gh release create "$GITHUB_REF_NAME" out/* --title "hyprKBM $v" --notes-file notes.md $pre
        env:
          GH_TOKEN: ${{ github.token }}
```

- [ ] **Step 4: Validate the workflows**

Run: `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest`
Expected: no errors.

- [ ] **Step 5: Commit, push, open the PR, and watch CI**

```bash
git add .github/workflows
git commit -m "ci: build the packages on every PR, and publish them on a version tag"
git push -u origin release/0.1.0
gh pr create --base main --title "Release 0.1.0: make install, packages, and the release workflow" --body "$(cat <<'EOF'
## Summary
- `hyprkbm --version`; one version number in `lib/hyprkbm/__init__.py`, checked against every recipe.
- First run creates `$XDG_CONFIG_HOME/hyprkbm/keybinds.json` (empty), since a package cannot.
- `make install` / `uninstall` / `dist` for system-wide installs; the systemd user unit and a preset that enables it.
- Recipes in `packaging/`: Arch (AUR), Debian, RPM (openSUSE, Mageia, OpenMandriva), Nix flake, Guix, FreeBSD, Solus, aerynOS.
- CI builds the tarball, `.deb`, `.rpm`, Arch package and Nix flake on every PR; a `v*` tag publishes them as a release.
- CHANGELOG, per-distro install in the README, release steps in CONTRIBUTING.

## Test plan
- [ ] `pytest`, `npm test`, qmllint pass
- [ ] Packages jobs pass (Tarball, Debian, RPM, Arch, Nix)
- [ ] Guix, FreeBSD, Solus and aerynOS recipes reviewed against their docs (not built)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
gh pr checks --watch
```

Expected: Tests, Panel logic, ShellCheck, QML, and the Packages jobs (Tarball, Debian, RPM, Arch, Nix) all pass. Fix and push until they do.

---

### Task 11: Tag and publish 0.1.0 (with the user)

Needs the user's explicit go-ahead at each of steps 2 and 4.

- [ ] **Step 1:** The user merges the Task 10 PR. `git checkout main && git pull`.
- [ ] **Step 2:** With the user's go-ahead: `git tag -a v0.1.0 -m "hyprKBM 0.1.0" && git push origin v0.1.0`.
- [ ] **Step 3:** `gh run watch` on the Release run. Expected: a pre-release `hyprKBM 0.1.0` with the tarball, `.deb`, `.rpm`, `.pkg.tar.zst`, `SHA256SUMS` and the recipes bundle.
- [ ] **Step 4:** Download the recipes bundle, copy the filled `packaging/` and `flake.*` back on a branch `release/0.1.0-checksums`, run `python -m pytest -q tests/test_packaging.py`, and open a PR. After it merges, and once the user's AUR account works, push `packaging/arch/PKGBUILD` and `.SRCINFO` to `ssh://aur@aur.archlinux.org/hyprkbm.git` (user's go-ahead; update the `# Maintainer:` line to their AUR identity first).
- [ ] **Step 5:** Update the roadmap memory: 0.1.0 released; next, issues #1–#7.
