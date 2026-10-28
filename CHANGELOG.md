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
- Packages built and published on the release: Arch (AUR), Debian/Ubuntu,
  RPM (openSUSE, Mageia, OpenMandriva). A Nix flake, built in CI. Recipes
  only, not yet built: Guix, FreeBSD, Solus, aerynOS. `make install` for
  anything else.

[0.1.0]: https://github.com/phos-org/hyprKBM/releases/tag/v0.1.0
