pragma Singleton
import QtQuick
import Quickshell.Io

// Every colour the panel draws with, and the one place that decides them.
//
// Each token has a default here, so the panel runs with no theme file at all.
// A theme file only names what it disagrees with: set `accentPrimary` and the
// borders and the pressed shade follow it, set `mode` and the backgrounds and
// text follow that. Anything derived can still be overridden outright.
//
// A theme is data, deliberately not QML. A .qml theme would run inside the
// shell's own process, and nothing dropped into a config directory should be
// able to do that.
QtObject {
    id: root

    // ------------------------------------------------------------------ base

    readonly property string mode: theme.mode === "light" ? "light" : "dark"

    readonly property color bgVoid: _resolve("bgVoid", theme.bgVoid,
        root.mode === "light" ? "#faf7f2" : "#0b0c16")
    readonly property color bgBase: _resolve("bgBase", theme.bgBase,
        root.mode === "light" ? "#f4efe8" : "#12131f")
    readonly property color bgSurface: _resolve("bgSurface", theme.bgSurface,
        root.mode === "light" ? "#ece4da" : "#1c1826")
    readonly property color bgSurfaceAlt: _resolve("bgSurfaceAlt", theme.bgSurfaceAlt,
        root.mode === "light" ? "#e3d8cd" : "#241b28")

    readonly property color textPrimary: _resolve("textPrimary", theme.textPrimary,
        root.mode === "light" ? "#2a2430" : "#f3ece2")
    readonly property color textSecondary: _resolve("textSecondary", theme.textSecondary,
        root.mode === "light" ? "#5f5a6b" : "#948da3")
    readonly property color textTertiary: _resolve("textTertiary", theme.textTertiary,
        root.mode === "light" ? "#8d8797" : "#5f5a6b")

    // The accents carry the product's voice, so light mode keeps their hues and
    // only darkens them. It has to: the dark accents are mid-tones, and on the
    // light ramp accentSecondary falls to 2.0:1 -- unreadable, and Field.qml
    // and ActionBar.qml both paint it as text. Darkening here rather than in
    // paper.json means `{"mode": "light"}` on its own is legible too.
    // Ratios against each mode's bgBase: primary 5.3/4.5, secondary 8.1/4.5,
    // tertiary 5.4/4.5. statusCritical clears 3:1 in both and is unchanged.
    readonly property color accentPrimary: _resolve("accentPrimary", theme.accentPrimary,
        root.mode === "light" ? "#b04b6d" : "#c2718c")
    readonly property color accentSecondary: _resolve("accentSecondary", theme.accentSecondary,
        root.mode === "light" ? "#966223" : "#d9a15c")
    readonly property color accentTertiary: _resolve("accentTertiary", theme.accentTertiary,
        root.mode === "light" ? "#607165" : "#7c9082")
    readonly property color statusCritical: _resolve("statusCritical", theme.statusCritical, "#b1495a")

    // --------------------------------------------------------------- derived

    // Built from the base tier so a one-line theme still hangs together, and
    // overridable anyway for a theme that disagrees with the arithmetic.
    readonly property color borderSubtle: _resolve("borderSubtle", theme.borderSubtle,
        Qt.rgba(root.accentPrimary.r, root.accentPrimary.g, root.accentPrimary.b, 0.16))
    readonly property color borderStrong: _resolve("borderStrong", theme.borderStrong,
        Qt.rgba(root.accentPrimary.r, root.accentPrimary.g, root.accentPrimary.b, 0.35))
    readonly property color accentPrimaryDim: _resolve("accentPrimaryDim", theme.accentPrimaryDim,
        Qt.darker(root.accentPrimary, 1.35))
    readonly property color bgGlass: _resolve("bgGlass", theme.bgGlass,
        Qt.rgba(root.bgBase.r, root.bgBase.g, root.bgBase.b, 0.72))

    // --------------------------------------------------------------- loading

    // Where the theme file is, and what the Theme popup writes to, come from
    // Theme.qml. One derivation, deliberately: two would be one edit away from
    // the panel reading one file and writing another.

    // A theme value counts only if it is a hex colour. QML renders anything it
    // cannot parse as transparent black, which looks like the panel breaking
    // rather than like a typo, so a value that is not one is dropped here.
    //
    // A typo is the likeliest mistake in a hand-written theme and the default
    // that replaces it looks deliberate, so say which token was dropped and
    // what was wrong with it. Empty is not a mistake -- it is every token the
    // file did not mention.
    function _resolve(token: string, value: string, fallback: color): color {
        if (/^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value))
            return value;
        if (value !== "")
            console.warn("hyprkbm: " + token + ': "' + value
                         + '" is not a hex colour, using the default');
        return fallback;
    }

    // Every adapter slot, blanked. Kept beside the JsonAdapter block below:
    // a token added there and not added here silently stops reverting on a
    // live edit, which is the quietest bug this file can have.
    function _clearOverrides() {
        theme.mode = "";
        theme.bgVoid = "";
        theme.bgBase = "";
        theme.bgSurface = "";
        theme.bgSurfaceAlt = "";
        theme.textPrimary = "";
        theme.textSecondary = "";
        theme.textTertiary = "";
        theme.accentPrimary = "";
        theme.accentSecondary = "";
        theme.accentTertiary = "";
        theme.statusCritical = "";
        theme.borderSubtle = "";
        theme.borderStrong = "";
        theme.accentPrimaryDim = "";
        theme.bgGlass = "";
    }

    // Every override a theme file may carry. The empty string means the user
    // said nothing about that token, which is how the defaults above survive a
    // partial file -- or a missing one.
    readonly property FileView _themeFile: FileView {
        id: themeFile

        path: Theme.path
        preload: true
        watchChanges: true
        // FileView warns on every failed read of its own accord, including the
        // one that is not a failure -- having no theme file at all. Silence it
        // and let onLoadFailed below decide what is worth saying.
        printErrors: false
        // watchChanges reports the edit; asking for the reread is ours to do.
        // Clear first: JsonAdapter only writes the keys a file actually
        // carries, so a key DELETED between edits would otherwise keep the
        // value it had, and the same theme.json would render differently
        // depending only on whether you had restarted. Blanking the slots puts
        // every token back to "user said nothing" before the file speaks.
        onFileChanged: {
            root._clearOverrides();
            themeFile.reload();
        }

        onLoadFailed: function (error) {
            // Having no theme file is the ordinary case, not news.
            if (error === FileViewError.FileNotFound || Theme.path === "") return;
            console.warn("hyprkbm: ignoring " + Theme.path + ": "
                         + FileViewError.toString(error));
        }

        JsonAdapter {
            id: theme

            property string mode: ""

            property string bgVoid: ""
            property string bgBase: ""
            property string bgSurface: ""
            property string bgSurfaceAlt: ""

            property string textPrimary: ""
            property string textSecondary: ""
            property string textTertiary: ""

            property string accentPrimary: ""
            property string accentSecondary: ""
            property string accentTertiary: ""
            property string statusCritical: ""

            property string borderSubtle: ""
            property string borderStrong: ""
            property string accentPrimaryDim: ""
            property string bgGlass: ""
        }
    }
}
