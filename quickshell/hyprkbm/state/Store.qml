pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import "../lib/keys.js" as Keys
import "../lib/model.js" as Model
import "../lib/keymap.js" as Keymap
import "../lib/search.js" as Search
import "../lib/layouts.js" as Layouts
import "../lib/catalogue.js" as Catalogue

// The panel's single source of truth. It never writes keybinds.json or
// keybinds.lua: edits are staged in `model` and leave only through
// hyprkbm-apply, which validates, dry-runs, backs up and can roll back.
//
// Every list here is computed by lib/*.js and reassigned wholesale; nothing is
// mutated in place, because a mutated object never repaints.
QtObject {
    id: root

    // Where the helpers are. Empty means "wherever PATH says"; `hyprkbm`
    // sets HYPRKBM_BIN when it opens the panel, because a keybind's PATH
    // does not include ~/.local/bin.
    readonly property string binDir: envValue("HYPRKBM_BIN")

    property bool loading: true
    property string loadError: ""
    property var doc: null
    property var saved: null
    property var model: null
    readonly property bool readOnly: doc !== null && (doc.model === null || doc.modelError !== null)
    readonly property bool dirty: model !== null && saved !== null
                                  && JSON.stringify(model) !== JSON.stringify(saved)

    readonly property var catalogue: doc ? doc.catalogue : []
    readonly property var hand: doc ? doc.hand : []
    readonly property var merged: Model.merge(hand, model || Model.emptyModel(), catalogue)
    readonly property var submaps: Model.submapNames(hand, doc ? doc.handSubmaps : [], model || Model.emptyModel())

    property string submap: ""
    property var toggledMods: ["SUPER"]
    property var heldMods: []
    // Holding real modifiers shows what they do; letting go shows the chips again.
    readonly property var mods: heldMods.length > 0 ? heldMods : toggledMods
    property string selectedKey: ""
    property string query: ""
    readonly property var parsedQuery: Search.parseQuery(query)
    readonly property string layoutName: doc && doc.settings && doc.settings.layout === "iso" ? "iso" : "ansi"
    readonly property var layout: Layouts.LAYOUTS[layoutName]
    readonly property var keyStates: Keymap.keyStates(merged.binds, submap, mods)
    readonly property var matching: Keymap.matchingKeys(merged.binds, submap, parsedQuery)
    readonly property var extras: Keymap.extraKeys(merged.binds)
    readonly property var listed: parsedQuery.empty
                                  ? Keymap.bindsOn(merged.binds, submap, mods, selectedKey)
                                  : Search.filter(merged.binds, parsedQuery)
    readonly property var removedHere: merged.removed.filter(function (r) {
        return r.hand.submap === root.submap && root.selectedKey !== ""
            && r.hand.combo === Keys.comboId(root.mods, root.selectedKey)
    })
    readonly property var unplaced: Keymap.unplaced(merged.binds, submap, knownKeys())

    property var draft: null
    property string status: ""
    property bool failed: false
    property var errors: []
    property bool busy: false
    property var preview: null
    // The model the current preview run was started for. A model edited while
    // the helper ran would otherwise leave a preview of an older model on show.
    property string previewModel: ""
    property bool previewAgain: false
    onModelChanged: preview = null
    property var backup: null
    // The backup the dialog last asked for. Loads finish in their own time, so
    // a result is kept only when it is for the name still wanted.
    property string backupWanted: ""
    property int conflictIndex: -1

    signal applied()

    Component.onCompleted: reload()

    function envValue(name) {
        var value = Quickshell.env(name)
        return value ? String(value).trim() : ""
    }

    function helper(name) { return binDir ? binDir + "/" + name : name }

    function knownKeys() {
        var known = Layouts.keyIds(layout)
        extras.forEach(function (k) { known[Keys.keyId(k.id)] = true })
        return known
    }

    function report(text, isError) {
        status = text
        failed = isError === true
    }

    // ------------------------------------------------------------ reading

    function reload() {
        loading = true
        stateProc.running = true
    }

    function adopt(parsed) {
        // A reload (after a layout change, the watcher or IPC) must not throw
        // away edits that are staged but not applied; only a clean model is
        // refreshed from disk. Dirtiness is read before `saved` is overwritten.
        var hadEdits = root.dirty
        doc = parsed
        saved = parsed.model
        if (model === null || !hadEdits)
            model = parsed.model === null ? null : Model.clone(parsed.model)
        loadError = ""
        if (selectedKey === "") selectedKey = "q"
    }

    // ------------------------------------------------------- the keyboard

    function hold(mod) {
        if (heldMods.indexOf(mod) < 0) heldMods = Keys.sortMods(heldMods.concat([mod]))
    }

    function release(mod) {
        heldMods = heldMods.filter(function (m) { return m !== mod })
    }

    function toggleMod(mod) {
        toggledMods = toggledMods.indexOf(mod) >= 0
                      ? toggledMods.filter(function (m) { return m !== mod })
                      : Keys.sortMods(toggledMods.concat([mod]))
    }

    function setMods(list) { toggledMods = Keys.sortMods(list) }

    function selectKey(id) {
        selectedKey = Keys.keyId(id)
        query = ""
    }

    function moveSelection(dir) {
        selectedKey = Layouts.neighbour(layout, selectedKey === "" ? "q" : selectedKey, dir)
    }

    function nextConflict() {
        var targets = Keymap.conflictTargets(merged.conflicts)
        if (targets.length === 0) return
        conflictIndex = (conflictIndex + 1) % targets.length
        var t = targets[conflictIndex]
        submap = t.submap
        toggledMods = t.mods
        heldMods = []
        selectedKey = t.key
        query = ""
    }

    // ------------------------------------------------------------ editing

    function findBind(uid) {
        for (var i = 0; i < merged.binds.length; i++)
            if (merged.binds[i].uid === uid) return merged.binds[i]
        return null
    }

    function flagsFromOpts(opts) {
        var flags = {}
        Model.FLAG_NAMES.forEach(function (f) { if (opts && opts[f] === true) flags[f] = true })
        return flags
    }

    function edit(uid) {
        var b = findBind(uid)
        if (b === null || readOnly || model === null) return
        if (b.source === "hand") {
            var action = Catalogue.actionFromDispatcher(b.dispatcher, catalogue)
            if (action === null) {
                report("The bind at " + b.where + " runs a Lua function; change it in hyprland.lua.", true)
                return
            }
            draft = { id: null, hand: b.hand, keys: b.keys, submap: b.submap, action: action,
                      description: b.description, flags: flagsFromOpts(b.hand.opts), allowConflict: false }
        } else {
            draft = { id: b.id, hand: b.hand, keys: b.keys, submap: b.submap,
                      action: Model.clone(b.action), description: b.description,
                      flags: Model.clone(b.flags), allowConflict: b.allowConflict }
        }
    }

    function newBind(keys) {
        if (readOnly || model === null) return
        draft = { id: null, hand: null, keys: keys, submap: submap,
                  action: { kind: "exec_cmd", args: {} }, description: "", flags: {}, allowConflict: false }
    }

    function newBindOnSelected() {
        newBind(selectedKey === "" ? Keys.display(mods, "") : Keys.display(mods, Layouts.keyName(layout, selectedKey)))
    }

    function patchDraft(fields) {
        var next = Model.clone(draft)
        Object.keys(fields).forEach(function (k) { next[k] = fields[k] })
        draft = next
    }

    function patchArg(name, value) {
        var action = Model.clone(draft.action)
        if (!action.args) action.args = {}
        if (value === "" || value === null || value === undefined) delete action.args[name]
        else action.args[name] = value
        patchDraft({ action: action })
    }

    function setActionKind(kind) {
        if (kind === "raw") patchDraft({ action: { kind: "raw", lua: "" } })
        else patchDraft({ action: { kind: kind, args: Catalogue.defaultArgs(Catalogue.entryById(catalogue, kind)) } })
    }

    function draftProblems() {
        if (draft === null) return []
        var out = []
        if (Keys.parse(draft.keys) === null) out.push("Keys: write them like SUPER + SHIFT + F")
        Catalogue.actionErrors(draft.action, catalogue).forEach(function (e) { out.push(e) })
        if (draft.hand !== null && draft.id === null) {
            var blocker = Model.overrideBlocker(hand, draft.hand)
            if (blocker !== null)
                out.push("The bind at " + blocker + " shares these keys and runs a Lua function, which hyprKBM cannot re-create; change it in hyprland.lua instead.")
        }
        return out
    }

    function saveDraft() {
        if (model === null || draft === null || draftProblems().length > 0) return
        var fields = { keys: draft.keys.trim(), submap: draft.submap, action: draft.action,
                       description: draft.description, flags: draft.flags, allowConflict: draft.allowConflict }
        if (draft.id !== null) model = Model.updateBind(model, draft.id, fields)
        else if (draft.hand !== null) model = Model.overrideHand(model, draft.hand, fields)
        else model = Model.addBind(model, fields)
        draft = null
        report("Staged. Apply when ready.", false)
    }

    function cancelEdit() { draft = null }

    function deleteBind(uid) {
        var b = findBind(uid)
        if (b === null || readOnly || model === null) return
        if (b.source === "hand") {
            var blocker = Model.overrideBlocker(hand, b.hand)
            if (blocker !== null) {
                report("Removing this would re-create the bind at " + blocker + ", which runs a Lua function; change it in hyprland.lua.", true)
                return
            }
            model = Model.unbindHand(model, b.hand)
        } else model = Model.removeBind(model, b.id)
        if (draft !== null && (draft.id === b.id || (draft.hand !== null && b.hand !== null && draft.hand.uid === b.hand.uid)))
            draft = null
    }

    function deleteDraft() {
        if (draft === null) return
        if (draft.id !== null) deleteBind("k:" + draft.id)
        else if (draft.hand !== null) deleteBind(draft.hand.uid)
        draft = null
    }

    function restoreHand(h) {
        if (model === null || readOnly) return
        model = Model.restoreHand(model, h)
    }

    function keepBoth(uid) {
        var b = findBind(uid)
        if (model === null || readOnly || b === null || b.id === null) return
        model = Model.updateBind(model, b.id, { allowConflict: true })
    }

    function addSubmap(name, reset) {
        if (model === null) return
        model = Model.addSubmap(model, name, reset)
        submap = name
    }

    function discard() {
        model = Model.clone(saved)
        draft = null
        errors = []
        report("Changes discarded.", false)
    }

    // ----------------------------------------------------------- helpers

    function apply() {
        if (!dirty || busy || readOnly) return
        busy = true
        report("Applying…", false)
        applyProc.stdinEnabled = true
        applyProc.running = true
    }

    function requestPreview() {
        preview = null
        if (model === null) return
        // The running helper was fed an older model; run again when it exits.
        if (previewProc.running) { previewAgain = true; return }
        previewAgain = false
        previewModel = JSON.stringify(model)
        previewProc.stdinEnabled = true
        previewProc.running = true
    }

    function loadBackup(name) {
        backupWanted = name
        backup = null
        // A load already running cannot be retargeted; its exit starts this one.
        if (backupProc.running) return
        backupProc.command = [helper("hyprkbm"), "--backup", name]
        backupProc.running = true
    }

    function clearBackup() {
        backupWanted = ""
        backup = null
    }

    function restoreBackup() {
        // Restoring replaces the staged model and applies it, so it must not
        // run over staged edits or a model the panel cannot edit.
        if (backup === null) { report("Pick a backup to restore first.", true); return }
        if (busy) { report("Wait for the current apply to finish.", true); return }
        if (readOnly) { report("The keybinds cannot be edited, so a backup cannot be restored.", true); return }
        if (dirty) { report("Apply or discard your staged changes before restoring a backup.", true); return }
        model = backup.model === null ? Model.emptyModel() : Model.clone(backup.model)
        if (!dirty) {
            report("That backup is what is applied already.", false)
            return
        }
        apply()
    }

    function exportTo(path) {
        exportProc.command = [helper("hyprkbm"), "--export", "md", path]
        exportProc.running = true
    }

    function setLayout(name) {
        layoutProc.command = [helper("hyprkbm"), "--set-layout", name]
        layoutProc.running = true
    }

    function startWatcher() { watcherProc.running = true }

    function parsed(text) {
        try { return JSON.parse(text) } catch (e) { return null }
    }

    function snapshot() {
        return {
            loading: loading, loadError: loadError, readOnly: readOnly, dirty: dirty,
            submap: submap, mods: mods, selectedKey: selectedKey, query: query,
            binds: merged.binds.length, conflicts: merged.conflicts.length, stale: merged.stale.length,
            listed: listed.map(function (b) { return b.uid }),
            draft: draft === null ? null : { id: draft.id, keys: draft.keys, kind: draft.action.kind },
            status: status, errors: errors
        }
    }

    property Process stateProc: Process {
        command: [root.helper("hyprkbm"), "--state"]
        stdout: StdioCollector { id: stateOut }
        stderr: StdioCollector { id: stateErr }
        onExited: function (code) {
            root.loading = false
            var parsedDoc = code === 0 ? root.parsed(stateOut.text) : null
            if (parsedDoc === null) {
                root.loadError = "hyprKBM's state could not be read: "
                    + ((stateErr.text || stateOut.text || "is hyprkbm installed?").trim())
                return
            }
            root.adopt(parsedDoc)
        }
    }

    property Process applyProc: Process {
        command: [root.helper("hyprkbm-apply")]
        stdinEnabled: true
        onStarted: {
            write(JSON.stringify(root.model))
            stdinEnabled = false   // EOF, so the helper's read of stdin returns
        }
        stdout: StdioCollector { id: applyOut }
        stderr: StdioCollector { id: applyErr }
        onExited: function (code) {
            root.busy = false
            var result = root.parsed(applyOut.text)
            if (result === null) {
                root.errors = []
                root.report("hyprkbm-apply failed: " + (applyErr.text || applyOut.text).trim(), true)
                return
            }
            if (result.ok) {
                root.errors = []
                root.report("Applied.", false)
                root.reload()
                root.applied()
                return
            }
            var errs = result.errors || []
            root.errors = errs
            var more = errs.length > 1 ? " (and " + (errs.length - 1) + " more)" : ""
            root.report(errs.length ? errs[0].message + more : "hyprkbm-apply refused the change.", true)
        }
    }

    property Process previewProc: Process {
        command: [root.helper("hyprkbm-apply"), "--preview"]
        stdinEnabled: true
        onStarted: {
            write(JSON.stringify(root.model))
            stdinEnabled = false
        }
        stdout: StdioCollector { id: previewOut }
        onExited: function (code) {
            if (root.previewAgain || root.previewModel !== JSON.stringify(root.model)) {
                Qt.callLater(root.requestPreview)
                return
            }
            root.preview = root.parsed(previewOut.text)
                           || { ok: false, errors: [{ id: null, message: "The preview could not be made." }], lua: "", current: "" }
        }
    }

    property Process backupProc: Process {
        stdout: StdioCollector { id: backupOut }
        onExited: function (code) {
            var got = backupProc.command[2]
            if (got !== root.backupWanted) {
                // Stale: the dialog moved on while this ran. Start the wanted
                // one once the process has really stopped.
                if (root.backupWanted !== "") Qt.callLater(function () { root.loadBackup(root.backupWanted) })
                return
            }
            var parsed = code === 0 ? root.parsed(backupOut.text) : null
            if (parsed === null) {
                root.backup = null
                root.report("That backup could not be read.", true)
                return
            }
            parsed.name = got
            root.backup = parsed
        }
    }

    property Process exportProc: Process {
        stderr: StdioCollector { id: exportErr }
        onExited: function (code) {
            if (code === 0) root.report("Exported to " + exportProc.command[3] + ".", false)
            else root.report((exportErr.text || "Export failed.").trim(), true)
        }
    }

    property Process layoutProc: Process {
        stderr: StdioCollector { id: layoutErr }
        onExited: function (code) {
            if (code === 0) root.reload()
            else root.report((layoutErr.text || "The layout could not be saved.").trim(), true)
        }
    }

    property Process watcherProc: Process {
        command: ["systemctl", "--user", "start", "hyprkbm-watch.service"]
        onExited: function (code) {
            if (code !== 0) root.report("The watcher could not be started; see systemctl --user status hyprkbm-watch.", true)
            root.reload()
        }
    }
}
