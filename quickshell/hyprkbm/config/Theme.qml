pragma Singleton
import QtQuick
import QtQml
import Quickshell
import Quickshell.Io

// The theme file itself: where it is, what it currently says, and the only
// code in the panel that writes it.
//
// The Colors singleton is the other half, and turns the same file into the
// tokens everything draws with. The split is along what each half does: it
// resolves sixteen named tokens and never looks at anything else, while an
// edit has to keep the whole file. Merging a change through Colors' JsonAdapter
// would drop every key it has no slot for -- a typo, a comment key, a token a
// later version added -- and for a file people hand-edit that is data loss.
//
// Nothing here writes a keybind. A theme is the panel's own
// appearance; it cannot leave you unable to read the screen, which is why it
// is the one file the QML is allowed to write directly rather than staging
// through hyprkbm-apply.
QtObject {
    id: root

    // ------------------------------------------------------------ the file

    // $XDG_CONFIG_HOME/hyprkbm/theme.json, or the same file under
    // ~/.config when XDG_CONFIG_HOME is unset.
    //
    // The Colors singleton reads this rather than working the path out again.
    // Two copies of the derivation would be one edit away from the panel
    // reading one file and writing another, and that failure looks exactly
    // like the popup quietly doing nothing.
    readonly property string path: {
        const configHome = _env("XDG_CONFIG_HOME");
        if (configHome !== "") return configHome + "/hyprkbm/theme.json";

        const home = _env("HOME");
        if (home !== "") return home + "/.config/hyprkbm/theme.json";

        return "";
    }

    // What that file says right now, parsed, or {} when there is no file --
    // which is the ordinary case. Everything the popup shows is derived from
    // this, so a hand edit and a click land in the same state rather than the
    // popup keeping a second opinion about the theme.
    property var overrides: ({})

    // Read back the same way Colors reads it, so the popup shows what the
    // panel is actually using rather than what it last wrote.
    readonly property string mode: root.overrides.mode === "light" ? "light" : "dark"

    // The tokens `mode` decides when a theme leaves them alone. The accents
    // are not here: they move with the mode too, but a theme that sets only an
    // accent -- iris -- still answers to it everywhere else.
    readonly property var _rampTokens: ["bgVoid", "bgBase", "bgSurface", "bgSurfaceAlt",
                                        "textPrimary", "textSecondary", "textTertiary"]

    // This theme names ramp colours outright, so switching mode moves less than
    // it looks like it should -- or, for a preset written out in full, nothing
    // at all. Worth surfacing: the alternative is a control that appears
    // broken, and the honest fix is not for the panel to start deleting
    // colours somebody set on purpose.
    //
    // True for one pinned token as well as for all of them, which is why what
    // the popup says about it does not promise which ones.
    readonly property bool hasExplicitRampColours: {
        for (var i = 0; i < root._rampTokens.length; i++)
            if (typeof root.overrides[root._rampTokens[i]] === "string") return true;
        return false;
    }

    // The preset this file *is*, or "" for one that matches none of them --
    // a hand-written theme, or any of them with an accent changed.
    readonly property string currentPreset: {
        // No theme file is not a nameless theme: the defaults are the shipped
        // palette written out, which is what defaultPreset names and what
        // tests/test_theme_presets.py asserts token for token. Reporting
        // "custom" to somebody who has never touched a theme would be a
        // worse answer than the true one.
        if (Object.keys(root.overrides).length === 0) return root.defaultPreset;

        for (var i = 0; i < root.presets.length; i++) {
            const name = root.presets[i];
            const text = root._presetText[name];
            if (typeof text !== "string") continue;
            if (_sameTheme(root.overrides, _parse(text))) return name;
        }
        return "";
    }

    // --------------------------------------------------------------- edits

    // Each of these writes the file and stops. The panel re-themes because it
    // watches the file, which is the same path a hand edit takes -- there is
    // deliberately no faster in-process route that could disagree with what
    // ended up on disk.

    function usePreset(name: string) {
        const text = root._presetText[name];
        if (typeof text !== "string" || text === "") {
            console.warn("hyprkbm: preset " + name + " is not loaded");
            return;
        }
        // Written byte for byte rather than re-serialised. Picking a preset
        // here is meant to be the `cp paper.json ~/.config/...` the README
        // documents, and the presets are grouped and blank-lined by hand:
        // round-tripping fuji.json through JSON.stringify would flatten
        // twelve grouped keys into one undifferentiated block for no gain.
        _write(text);
    }

    function setAccent(value: string) {
        const hex = normalisedColour(value);
        if (hex === "") return;
        _merge({ accentPrimary: hex });
    }

    function setMode(value: string) {
        _merge({ mode: value === "light" ? "light" : "dark" });
    }

    // ---------------------------------------------------------- the presets

    // The presets that ship in ../presets, by file stem.
    //
    // Written out because there is nothing to enumerate with: neither
    // Quickshell nor Quickshell.Io exposes a directory listing, and
    // Qt.labs.folderlistmodel is not a dependency this panel has -- it is
    // absent from this machine and from the CI runner, so importing it would
    // trade a hardcoded list for a panel that fails to start.
    //
    // Adding a preset is this line plus the file.
    // tests/test_theme_popup.py fails if the two ever disagree.
    readonly property var presets: ["fuji", "paper", "iris"]

    // The one the panel is already showing when there is no theme file at all.
    readonly property string defaultPreset: "fuji"

    // ../presets, beside the QML rather than under the user's config: these
    // are shipped data, not something the user is expected to have.
    readonly property string presetDir: Quickshell.shellDir + "/presets"

    // The accent each bundled preset settles on, as [{name, hex}], for the
    // picker's one-click swatches. "Give me the iris blue" is a common want,
    // and reading it off the presets is the whole cost of answering it --
    // three hexes copied into the picker would be three more literals free to
    // drift away from the files they came from.
    readonly property var presetAccents: {
        const out = [];
        for (var i = 0; i < root.presets.length; i++) {
            const name = root.presets[i];
            const parsed = _parse(root._presetText[name] || "");
            const hex = parsed ? normalisedColour(parsed.accentPrimary || "") : "";
            if (hex !== "") out.push({ name: name, hex: hex });
        }
        return out;
    }

    // {stem: file text}. Reassigned wholesale on every load rather than
    // mutated, so currentPreset re-evaluates -- an in-place write to a var
    // property does not notify.
    property var _presetText: ({})

    // One FileView per preset. A single re-pointed FileView does not work:
    // setting `path` and calling text() in the same turn answers the *previous*
    // file's contents, measured against all three presets in a row.
    readonly property Instantiator _presetReaders: Instantiator {
        model: root.presets

        delegate: FileView {
            required property string modelData

            path: root.presetDir + "/" + modelData + ".json"
            preload: true
            printErrors: false

            onLoaded: {
                const next = {};
                for (var name in root._presetText) next[name] = root._presetText[name];
                next[modelData] = this.text();
                root._presetText = next;
            }
            // A preset named above with no file behind it. Worth saying: the
            // entry is still in the dropdown and will refuse to apply.
            onLoadFailed: function (error) {
                console.warn("hyprkbm: preset " + modelData + " is missing from "
                             + root.presetDir + ": " + FileViewError.toString(error));
            }
        }
    }

    // ------------------------------------------------------------- reading

    readonly property FileView _file: FileView {
        id: themeFile

        path: root.path
        preload: true
        watchChanges: true
        // Tmp-then-rename, like every other file this project writes: a crash
        // mid-write cannot leave half a theme behind. Checked that a separate
        // watching FileView -- which is what the Colors singleton is -- keeps
        // seeing these writes, since replacing the inode under a watch is the
        // usual way to lose one.
        atomicWrites: true
        // Having no theme file is not a failure worth printing on startup.
        printErrors: false

        onFileChanged: themeFile.reload()
        onLoaded: root.overrides = _parse(themeFile.text()) || ({})
        // Deleted, unreadable, or not JSON: the panel is back to its defaults
        // and the popup has to say so rather than keep showing the old file.
        onLoadFailed: root.overrides = ({})

        // _write has already adopted what it wrote. If it did not land, that
        // belief is wrong and the file is the one to believe.
        onSaveFailed: function (error) {
            console.warn("hyprkbm: could not write " + root.path + ": "
                         + FileViewError.toString(error));
            themeFile.reload();
        }
    }

    // ------------------------------------------------------------- helpers

    // The colour shapes the theme file accepts, kept identical to the test in
    // the Colors singleton's _resolve -- a popup that writes a value the panel
    // then refuses would look like the write failing.
    // tests/test_theme_popup.py fails if the two patterns diverge.
    function isColour(value: string): bool {
        return /^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(value);
    }

    // What a typed colour becomes, or "" if it is not one. The leading # is
    // optional going in: it is the character people leave off, and a field
    // that rejects "7f8fd6" reads as broken rather than as strict.
    function normalisedColour(value: string): string {
        var text = String(value).trim();
        if (text !== "" && text.charAt(0) !== "#") text = "#" + text;
        return isColour(text) ? text : "";
    }

    // The current file plus `changes`, so a key the popup knows nothing about
    // survives being next to one it does change.
    //
    // Two spaces and a trailing newline, which is how the bundled presets are
    // written. The file stays something you can open in an editor, and this
    // must not be the change that turns it into machine output.
    //
    // FileView.writeAdapter() was the other way to do this and is not usable:
    // it writes every adapter slot, so a one-key theme comes back as sixteen
    // keys with fifteen empty strings -- measured, not assumed.
    function _merge(changes) {
        const next = {};
        for (var key in root.overrides) next[key] = root.overrides[key];
        for (var name in changes) next[name] = changes[name];
        _write(JSON.stringify(next, null, 2) + "\n");
    }

    // No HOME and no XDG_CONFIG_HOME leaves nowhere to put a theme. The panel
    // still runs on its defaults; silently writing to a relative path would be
    // worse than not writing.
    function _write(text: string) {
        if (root.path === "") {
            console.warn("hyprkbm: no HOME or XDG_CONFIG_HOME, theme not saved");
            return;
        }
        // Nothing goes in the file that cannot be read back out. The one caller
        // that could supply unparseable text is a shipped preset that has been
        // broken, and replacing a working theme with rubbish is worse than
        // refusing the click.
        const parsed = _parse(text);
        if (parsed === null) {
            console.warn("hyprkbm: refusing to write a theme that is not JSON");
            return;
        }

        _file.setText(text);

        // A FileView does not report its own write back to itself, by
        // fileChanged or by a reload -- measured: after a write the Colors
        // singleton had re-themed from the new file while this one still held
        // the old contents, and the next edit would have merged into them and
        // undone the one before it. So adopt what was just written;
        // onSaveFailed below puts it back if the write did not land.
        root.overrides = parsed;
    }

    // null rather than a throw, so every caller has to decide what a
    // malformed theme means to it.
    function _parse(text: string): var {
        try {
            const parsed = JSON.parse(text);
            return (parsed && typeof parsed === "object" && !Array.isArray(parsed))
                 ? parsed : null;
        } catch (error) {
            return null;
        }
    }

    // Same keys, same values. Only used to recognise a preset, where both
    // sides are flat string maps.
    function _sameTheme(a, b): bool {
        if (!a || !b) return false;
        for (var key in a) if (a[key] !== b[key]) return false;
        for (var other in b) if (a[other] !== b[other]) return false;
        return true;
    }

    // Quickshell.env() answers null for a variable that is not set -- measured,
    // not assumed: typeof is "object" and === null, never undefined. The
    // typeof check below rejects it along with every other non-string, so no
    // shape of "not set" can end up pasted into a path.
    function _env(variable: string): string {
        const value = Quickshell.env(variable);
        return typeof value === "string" ? value : "";
    }
}
