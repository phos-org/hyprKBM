#!/usr/bin/env bash
# Install hyprKBM for the current user, as symlinks back into this clone --
# so keep the clone, and `git pull` is the upgrade.
#
#   ./install.sh              link everything and enable the watcher
#   ./install.sh --uninstall  remove what install created
#
# Nothing in hyprland.lua is touched. Keybinds are applied to Hyprland live,
# and hyprkbm-watch, started with the session by a systemd user unit, puts
# them back after every reload and at login. hyprKBM needs it.
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# Fixed rather than configurable: the systemd unit runs the watcher from here.
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
UNIT=hyprkbm-watch.service

# source (in the clone) and destination, one pair per line.
LINKS="
bin/hyprkbm          $BIN_DIR/hyprkbm
bin/hyprkbm-apply    $BIN_DIR/hyprkbm-apply
bin/hyprkbm-watch    $BIN_DIR/hyprkbm-watch
systemd/$UNIT        $CONFIG_DIR/systemd/user/$UNIT
share/applications/hyprkbm.desktop  $DATA_DIR/applications/hyprkbm.desktop
"

failed=0
say() { printf '%s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }

have_systemd_session() {
    command -v systemctl >/dev/null 2>&1 \
        && systemctl --user is-active --quiet graphical-session.target
}

# Compared resolved, not as written: ~/.local/share/../bin is ~/.local/bin, and
# warning about it sends people off to fix a PATH that already works.
bin_on_path() {
    local want dir dirs
    want="$(realpath -m "$BIN_DIR")"
    IFS=: read -ra dirs <<<"$PATH"
    for dir in "${dirs[@]}"; do
        [ -n "$dir" ] && [ "$(realpath -m "$dir")" = "$want" ] && return 0
    done
    return 1
}

have_lua() {
    command -v lua >/dev/null 2>&1 || command -v lua5.5 >/dev/null 2>&1 \
        || command -v lua5.4 >/dev/null 2>&1
}

link() {
    local src="$REPO/$1" dst="$2" err old
    if ! err=$(mkdir -p "$(dirname "$dst")" 2>&1); then
        warn "  failed    $dst: ${err:-could not create the link}"
        failed=1
        return
    fi
    if [ -L "$dst" ]; then
        old="$(readlink "$dst")"
        if [ "$old" = "$src" ]; then
            say "  ok        $dst"
            return
        fi
        # A link is somebody's earlier install of this; a file is not.
        if err=$(ln -sfn "$src" "$dst" 2>&1); then
            say "  replaced  $dst (was -> $old)"
        else
            warn "  failed    $dst: ${err:-could not create the link}"
            failed=1
        fi
    elif [ -e "$dst" ]; then
        warn "  skipped   $dst: a file is already there, not a link; move it and run again"
        failed=1
    elif err=$(ln -s "$src" "$dst" 2>&1); then
        say "  linked    $dst"
    else
        warn "  failed    $dst: ${err:-could not create the link}"
        failed=1
    fi
}

unlink_ours() {
    local src="$REPO/$1" dst="$2"
    if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
        rm "$dst"
        say "  removed   $dst"
    fi
}

enable_watcher() {
    if ! have_systemd_session; then
        say ""
        say "This session does not start graphical-session.target, so systemd cannot"
        say "start the watcher at login. Add this to hyprland.lua instead:"
        say ""
        say '    hl.on("hyprland.start", function()'
        say '        hl.exec_cmd("hyprkbm-watch")'
        say '    end)'
        return
    fi
    systemctl --user daemon-reload
    if [ "$(systemctl --user is-enabled "$UNIT" 2>/dev/null)" = masked ]; then
        warn "$UNIT is masked. hyprKBM needs it: without it, your keybinds are lost"
        warn "at the next reload. Unmask it and run this again:"
        warn "    systemctl --user unmask $UNIT"
        failed=1
        return
    fi
    if systemctl --user enable --now "$UNIT"; then
        say "Enabled $UNIT; it starts with every graphical session."
    else
        warn "Could not enable $UNIT; see: systemctl --user status $UNIT"
        failed=1
    fi
}

install() {
    for tool in hyprctl python3 qs; do
        command -v "$tool" >/dev/null 2>&1 \
            || warn "warning: $tool not found; hyprKBM needs it to run"
    done
    have_lua || warn "warning: no lua interpreter found; hyprKBM needs one to read hyprland.lua"
    say "Linking from $REPO"
    while read -r src dst; do
        [ -n "$src" ] && link "$src" "$dst"
    done <<<"$LINKS"
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database "$DATA_DIR/applications" >/dev/null 2>&1
    if [ -L "$BIN_DIR/hyprkbm-watch" ]; then
        enable_watcher
    else
        warn "The watcher was not enabled: its link $BIN_DIR/hyprkbm-watch is missing."
    fi
    bin_on_path || warn "warning: $BIN_DIR is not on your PATH; add it to run hyprkbm yourself"
    say ""
    say "Done. Try: hyprkbm --status"
}

uninstall() {
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now "$UNIT" >/dev/null 2>&1 || true
    fi
    while read -r src dst; do
        [ -n "$src" ] && unlink_ours "$src" "$dst"
    done <<<"$LINKS"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
    say "Removed. Your keybinds.json, keybinds.lua and backups are kept."
}

case "${1:-}" in
    "") install ;;
    --uninstall) uninstall ;;
    *)
        warn "usage: $0 [--uninstall]"
        exit 2
        ;;
esac
exit "$failed"
