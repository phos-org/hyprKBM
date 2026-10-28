# Install hyprKBM

Install a package when your distro has one. Use the Nix flake on NixOS. Use `install.sh` when you want to follow `main` from a clone.

The watcher has to be running. It puts hyprKBM's binds back after every Hyprland reload and at login. A package install and `install.sh` both set that up. The sections below say when you still have to start it yourself.

## Requirements

| | |
| --- | --- |
| Hyprland | 0.55 or later, with Lua configuration (`hyprland.lua`). Tested on 0.56.2. |
| Lua | A 5.4 or 5.5 interpreter, found as `lua`, `lua5.5`, `lua5.4`, `lua55`, or `lua54`. `lua` on Arch, where Hyprland already pulls it in. `lua5.4` on Debian and Ubuntu. `lua54` on FreeBSD. |
| Python 3 | The standard library only. Developed against 3.14. CI runs 3.12. |
| Quickshell | Optional. 0.3 or later, for the panel and the cheatsheet (the `qs` command). The command line works without it. |
| systemd | Optional. A user session that starts `graphical-session.target` runs the watcher as a service. [uwsm](https://github.com/Vladimir-csp/uwsm) does that. Without it, see [Without systemd](#without-systemd). |

`install.sh` warns when `hyprctl`, `python3`, `qs`, or a Lua interpreter is missing. The install still finishes.

## Packages

| Distro | |
| --- | --- |
| Arch, Manjaro, Artix, Parabola | `yay -S hyprkbm` (the AUR), or the `.pkg.tar.zst` from the [release](https://github.com/phos-org/hyprKBM/releases) |
| Debian 14, Debian sid, Debian 13 backports, Ubuntu 26.10, Kali, Devuan | the `.deb` from the release: `sudo apt install ./hyprkbm_*_all.deb` |
| openSUSE Tumbleweed, Mageia, OpenMandriva, Rosa | the `.rpm` from the release: `sudo zypper in ./hyprkbm-*.noarch.rpm` (or `dnf`, or `urpmi`). Built and tested on openSUSE Tumbleweed. Mageia, OpenMandriva, and Rosa are untested |
| NixOS and Nix | `nix profile install github:phos-org/hyprKBM`. See [Nix](#nix). |
| Guix, FreeBSD, Solus, aerynOS | recipes in [`packaging/`](../packaging/) |
| anything else | `sudo make install PREFIX=/usr` from the release tarball. GNU make. Add `SYSTEMD=0` when the machine has no systemd |

Which recipe is for which distro, and how each one is checked, is in [Packaging](../packaging/README.md).

Distros whose Hyprland predates the Lua config are not packaged yet. That is Fedora, Alpine, Ubuntu 26.04 LTS, and ALT Linux.

If you installed from a clone with `install.sh`, run `install.sh --uninstall` before installing a package. Otherwise the clone's links in `~/.local/bin` and its unit in `~/.config/systemd/user` come first, and shadow the package.

## The watcher

The Debian and RPM packages enable `hyprkbm-watch` for every user. That takes effect at your next login. To start it now:

```bash
systemctl --user start hyprkbm-watch
```

Elsewhere, including Arch and `make install`, enable and start it once:

```bash
systemctl --user enable --now hyprkbm-watch
```

`make install` writes the unit with `ExecStart` pointing at the installed `hyprkbm-watch`. The unit in the repo, which `install.sh` links, starts `%h/.local/bin/hyprkbm-watch`. The unit is `PartOf=graphical-session.target` and only starts when `HYPRLAND_INSTANCE_SIGNATURE` is set in the user session.

Check it with:

```bash
hyprkbm --status
```

The last line is `watcher:` followed by what `systemctl --user is-active hyprkbm-watch.service` printed. When `systemctl` is missing, that line is `watcher: unknown (no systemctl)`.

## Nix

Nix needs flakes enabled. Add `--extra-experimental-features 'nix-command flakes'` to each command, or set `experimental-features = nix-command flakes` in `nix.conf`. `github:phos-org/hyprKBM` follows `main`. To pin this release, use `github:phos-org/hyprKBM/v0.1.0`.

`nix profile install` puts the unit in `~/.nix-profile/lib/systemd/user`, where systemd does not look, so link it first:

```bash
systemctl --user link ~/.nix-profile/lib/systemd/user/hyprkbm-watch.service
systemctl --user enable --now hyprkbm-watch
```

On NixOS, take the package from the flake's `packages.${system}.hyprkbm` and let NixOS install the unit. With this flake as the input `hyprkbm`:

```nix
{ inputs, pkgs, ... }:
let hyprkbm = inputs.hyprkbm.packages.${pkgs.stdenv.hostPlatform.system}.hyprkbm; in {
  environment.systemPackages = [ hyprkbm ];
  systemd.packages = [ hyprkbm ];
  systemd.user.services.hyprkbm-watch.wantedBy = [ "graphical-session.target" ];
}
```

The flake wraps `hyprkbm`, `hyprkbm-apply`, and `hyprkbm-watch` so Lua 5.4 and `notify-send` are on their `PATH`. `hyprctl` and `qs` still come from your Hyprland and Quickshell.

Guix on another distro is the same idea. Link the unit from your profile, then enable it:

```bash
systemctl --user link ~/.guix-profile/lib/systemd/user/hyprkbm-watch.service
systemctl --user enable --now hyprkbm-watch
```

Without systemd, start the watcher from `hyprland.lua`. See [Without systemd](#without-systemd).

## From a clone

For development, or to follow `main`:

```bash
git clone https://github.com/phos-org/hyprKBM.git ~/src/hyprKBM
~/src/hyprKBM/install.sh
```

`install.sh` links `hyprkbm`, `hyprkbm-apply`, and `hyprkbm-watch` into `~/.local/bin`, links the `hyprkbm-watch` unit into `~/.config/systemd/user`, and links the desktop entry into `~/.local/share/applications`. It then enables and starts the unit. It is safe to run again.

- The install is symlinks back into the clone, so keep the clone. `git pull` is the upgrade. Whatever branch the clone has checked out is what runs.
- An existing symlink at any of those paths is re-pointed to this clone. That is what makes re-installing from a moved clone work. A real file is never touched, and the install fails instead.
- `~/.local/bin` must be on your `PATH` to run `hyprkbm` yourself. The installer warns when it is not.

`XDG_CONFIG_HOME` and `XDG_DATA_HOME` are honoured for the unit and the desktop entry. The binaries always go to `~/.local/bin`.

## Without systemd

If `systemctl --user is-active graphical-session.target` says `inactive`, or there is no systemd at all (FreeBSD, or `make install SYSTEMD=0`), start the watcher from `hyprland.lua` instead:

```lua
hl.on("hyprland.start", function()
	hl.exec_cmd("hyprkbm-watch")
end)
```

`install.sh` prints that snippet and skips the unit when this session does not start `graphical-session.target`. If the unit is masked, it stops and tells you to unmask it:

```bash
systemctl --user unmask hyprkbm-watch.service
```

## Uninstall

A package comes off with the package manager that put it there (`sudo pacman -R hyprkbm`, `sudo apt remove hyprkbm`, `sudo zypper rm hyprkbm`, `nix profile remove hyprkbm`, and the same idea for the others). A `make install` comes off with `sudo make uninstall` and the same `PREFIX`. Run `systemctl --user disable --now hyprkbm-watch` first where you enabled it yourself.

A clone install comes off with:

```bash
~/src/hyprKBM/install.sh --uninstall
```

This disables the watcher and removes the links. Either way, your `keybinds.json`, the generated `keybinds.lua`, and the backups are kept. The binds stay active until the next Hyprland reload.

## A local install, without packaging

To see what a package would contain, without installing onto the machine you are using:

```bash
D=$(mktemp -d) && make install PREFIX=/usr DESTDIR="$D" && find "$D" | sort
make install PREFIX=/usr/local DESTDIR="$D" SYSTEMD=0
make dist
```

`make dist` archives the committed `HEAD`, so commit first or your changes are not in the tarball. Building the distro packages is described in [Contributing](../CONTRIBUTING.md#checking-the-packaging). Do not install a built package onto the machine whose Hyprland you are using.
