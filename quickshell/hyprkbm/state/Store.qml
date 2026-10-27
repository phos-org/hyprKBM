pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import "../lib/keys.js" as Keys
import "../lib/model.js" as Model
import "../lib/keymap.js" as Keymap
import "../lib/search.js" as Search
import "../lib/layouts.js" as Layouts
import "../lib/catalogue.js" as Catalogue
import "../lib/quit.js" as Quit
import "../lib/capture.js" as Capture
import "../lib/focus.js" as Focus
import "../lib/cheatsheet.js" as Cheatsheet

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
    readonly property var cheatsheetKeys: Cheatsheet.keysOf(merged.binds)
    readonly property var keyStates: Keymap.keyStates(merged.binds, submap, mods)
    readonly property var matching: Keymap.matchingKeys(merged.binds, submap, parsedQuery)
    readonly property var extras: Keymap.extraKeys(merged.binds)
    readonly property var listed: parsedQuery.empty
                                  ? Keymap.bindsOn(merged.binds, submap, mods, selectedKey)
                                  : Search.filter(merged.binds, parsedQuery)
    // Keys bound only under other modifiers, and the selected key's binds
    // under them: what a view that hides them would otherwise lose.
    readonly property var otherKeys: Keymap.otherKeys(merged.binds, submap, mods)
    readonly property var otherCombos: parsedQuery.empty
                                       ? Keymap.otherCombos(merged.binds, submap, mods, selectedKey)
                                       : []
    // What the list cursor walks: the listed binds, then "Also bound as".
    readonly property var listRows: listed.map(function (b) { return { kind: "bind", bind: b } })
        .concat(otherCombos.map(function (b) { return { kind: "other", bind: b } }))
    readonly property var removedHere: merged.removed.filter(function (r) {
        return r.hand.submap === root.submap && root.selectedKey !== ""
            && r.hand.combo === Keys.comboId(root.mods, root.selectedKey)
    })
    readonly property var unplaced: Keymap.unplaced(merged.binds, submap, knownKeys())

    // Which part of the panel has the keys, and which bind the list points at.
    property string area: "keyboard"
    property int listIndex: 0
    // Back to the top when what was picked changes; the list itself only
    // clamps, so the order the two signals arrive in does not matter.
    onSelectedKeyChanged: listIndex = 0
    onModsChanged: listIndex = 0
    onSubmapChanged: listIndex = 0
    onQueryChanged: listIndex = 0
    onListRowsChanged: listIndex = Math.max(0, Focus.clampIndex(listIndex, listRows.length))
    // The editor closing hands the keys back to the list.
    onDraftChanged: if (draft === null && area === "editor") area = "list"

    property var draft: null
    property string status: ""
    property bool failed: false
    property var errors: []
    property bool busy: false
    property string applyPayload: ""
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
    // When the first Esc over staged edits was pressed; a second one soon
    // after quits. 0 means not armed.
    property real quitArmedAt: 0

    // Find mode: Hyprland is in the capture submap and the next key pressed
    // is a combo to select, not a command. Its binds are off meanwhile.
    property bool finding: false

    signal applied()
    // A pick switches views; the list scrolls to the bind even when the
    // cursor lands on the row it was already on, so listIndex never changes.
    signal picked()

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
        stopFind()
        loading = true
        stateProc.running = true
    }

    function adopt(parsed) {
        // A reload (after a layout change, the watcher or IPC) must not throw
        // away edits that are staged but not applied; only a clean model is
        // refreshed from disk. Dirtiness is read before `saved` is overwritten.
        stopFind()
        var hadEdits = root.dirty
        doc = parsed
        saved = parsed.model
        if (model === null || !hadEdits)
            model = parsed.model === null ? null : Model.clone(parsed.model)
        loadError = ""
        if (selectedKey === "") selectedKey = "q"
        keepSubmapValid()
    }

    // A submap that only existed in staged edits is gone once they are
    // discarded or reloaded away; leaving it selected would show an empty,
    // unreachable page.
    function keepSubmapValid() {
        if (submap !== "" && submaps.indexOf(submap) < 0) submap = ""
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
        area = "keyboard"
    }

    // Fire-and-forget, so it still goes out when the panel is quitting and
    // cannot be dropped by an earlier leave that is still running.
    function leaveNow() {
        Quickshell.execDetached(["hyprctl", "eval", Capture.leaveLua()])
    }

    function startFind() {
        // Not while an apply runs or a draft is open: the pressed keys are
        // the draft's, and an apply reloads Hyprland, which ends the submap.
        // Not twice: the second would define the submap again.
        if (finding || busy || draft !== null) return
        finding = true
        report("Press the keybind to find… (Esc cancels)", false)
        findEnter.running = true
    }

    function stopFind() {
        // A no-op unless finding, so a stray call can never reset a submap
        // the user entered themselves (the Lua is guarded too).
        if (!finding) return
        finding = false
        leaveNow()
    }

    function found(mods, key) {
        stopFind()
        // Held modifiers belong to the pressed combo, not to the display.
        heldMods = []
        setMods(mods)
        selectKey(key)
        report("", false)
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

    // While an apply runs the model is still the pre-apply one; an edit made
    // now would survive the reload as "had edits" and could undo the apply.
    function stagingBlocked() {
        if (!busy) return false
        report("Wait for the current apply to finish.", true)
        return true
    }

    function edit(uid) {
        var b = findBind(uid)
        if (b === null || readOnly || model === null || stagingBlocked()) return
        if (b.source === "hand") {
            var action = Catalogue.actionFromDispatcher(b.dispatcher, catalogue)
            if (action === null) {
                report("The bind at " + b.where + " runs a Lua function; change it in hyprland.lua.", true)
                return
            }
            stopFind()
            draft = { id: null, hand: b.hand, keys: b.keys, submap: b.submap, action: action,
                      description: b.description, flags: flagsFromOpts(b.hand.opts), allowConflict: false }
        } else {
            stopFind()
            draft = { id: b.id, hand: b.hand, keys: b.keys, submap: b.submap,
                      action: Model.clone(b.action), description: b.description,
                      flags: Model.clone(b.flags), allowConflict: b.allowConflict }
        }
    }

    function focusedRow() {
        var i = Focus.clampIndex(listIndex, listRows.length)
        return i < 0 ? null : listRows[i]
    }

    // Only a listed bind: E and Delete never reach an "Also bound as" row.
    function focusedBind() {
        var row = focusedRow()
        return row !== null && row.kind === "bind" ? row.bind : null
    }

    // An "Also bound as" row: show the key under that bind's modifiers, with
    // the cursor on the bind itself.
    function pickOther(b) {
        if (b === null || b === undefined) return
        heldMods = []
        setMods(b.mods)
        for (var i = 0; i < listed.length; i++)
            if (listed[i].uid === b.uid) { listIndex = i; break }
        picked()
    }

    // The keys' Edit: the Edit button's own limits apply, so a bind hyprKBM
    // cannot read is refused rather than turned into a useless override.
    function editBind(b) {
        if (b === null || b === undefined) return
        if (b.source === "hand" && b.combo === null) {
            report("hyprKBM does not understand the keys of this bind; change it in hyprland.lua.", true)
            return
        }
        edit(b.uid)
    }

    function newBind(keys) {
        if (readOnly || model === null || stagingBlocked()) return
        stopFind()
        draft = { id: null, hand: null, keys: keys, submap: submap,
                  action: { kind: "exec_cmd", args: {} }, description: "", flags: {}, allowConflict: false }
    }

    // The ⋯ menu's offer: a bind that opens the cheatsheet, keys left for the
    // user to record. It goes through the editor like any other new bind.
    function newCheatsheetBind() {
        newBind("")
        if (draft === null) return
        patchDraft({ submap: "", action: { kind: "exec_cmd", args: { cmd: Cheatsheet.COMMAND } },
                     description: "Keybind cheatsheet" })
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
        else if (Keys.isModifierOnly(draft.keys)) out.push("Pick a key, not only modifiers")
        if (draft.submap !== "" && submaps.indexOf(draft.submap) < 0)
            out.push("The submap \"" + draft.submap + "\" does not exist; pick another or add it first.")
        Catalogue.actionErrors(draft.action, catalogue).forEach(function (e) { out.push(e) })
        if (draft.hand !== null && draft.id === null) {
            var dropped = Model.droppedOpts(draft.hand.opts)
            if (dropped.length > 0)
                out.push("hyprKBM would drop these options of the original bind: " + dropped.join(", ") + ".")
            var blocker = Model.overrideBlocker(hand, draft.hand)
            if (blocker !== null)
                out.push("The bind at " + blocker + " shares these keys and runs a Lua function, which hyprKBM cannot re-create; change it in hyprland.lua instead.")
        }
        return out
    }

    function saveDraft() {
        if (model === null || draft === null || draftProblems().length > 0 || stagingBlocked()) return
        var fields = { keys: draft.keys.trim(), submap: draft.submap, action: draft.action,
                       description: draft.description, flags: draft.flags, allowConflict: draft.allowConflict }
        if (draft.id !== null) model = Model.updateBind(model, draft.id, fields)
        else if (draft.hand !== null) model = Model.overrideHand(model, draft.hand, fields)
        else model = Model.addBind(model, fields)
        draft = null
        report("Staged. Apply when ready.", false)
    }

    function cancelEdit() { draft = null }

    // Whether the window should close for this Esc. Reports why it did not.
    function requestQuit() {
        var r = Quit.escape({ busy: busy, draft: draft !== null, dirty: dirty }, quitArmedAt, Date.now())
        quitArmedAt = r.action === "warn" ? r.armedAt : 0
        if (r.action === "cancel") cancelEdit()
        else if (r.action === "warn")
            report("You have changes that are not applied. Apply or Discard them, or press Esc again to quit.", true)
        return r.action === "quit"
    }

    function deleteBind(uid) {
        var b = findBind(uid)
        if (b === null || readOnly || model === null || stagingBlocked()) return
        if (b.source === "hand" && b.combo === null) {
            report("hyprKBM does not understand the keys of this bind, so it cannot be removed here; change it in hyprland.lua.", true)
            return
        }
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
        if (model === null || readOnly || stagingBlocked()) return
        model = Model.restoreHand(model, h)
    }

    function keepBoth(uid) {
        var b = findBind(uid)
        if (model === null || readOnly || b === null || b.id === null || stagingBlocked()) return
        model = Model.updateBind(model, b.id, { allowConflict: true })
    }

    // A stale edit is one whose hyprland.lua bind has changed or gone. Drop
    // lets hyprland.lua win; Keep moves the edit onto what is there now.
    function staleBlocked() {
        if (model === null || readOnly || stagingBlocked()) return true
        // With hyprland.lua only partly read, a valid edit looks stale; acting
        // on it would survive the reload and lose it for good.
        if (doc && doc.readerError) {
            report("hyprland.lua was not read completely, so stale edits cannot be trusted. Fix it and reload first.", true)
            return true
        }
        return false
    }

    function dropStale(entry) {
        if (staleBlocked()) return
        if (draft !== null && entry.id !== null && draft.id === entry.id) draft = null
        model = Model.dropStale(model, entry)
        report("Edit dropped; hyprland.lua's bind on " + entry.keys + " stays. Apply to save it.", false)
    }

    function keepStale(entry) {
        if (staleBlocked()) return
        if (entry.successor !== null) {
            var blocker = Model.overrideBlocker(hand, entry.successor)
            if (blocker !== null) {
                report("Keeping this would re-create the bind at " + blocker + ", which runs a Lua function; change it in hyprland.lua.", true)
                return
            }
        }
        model = Model.keepStale(model, entry)
        report("Edit kept. Apply to save it.", false)
    }

    function addSubmap(name, reset) {
        if (model === null || stagingBlocked()) return
        model = Model.addSubmap(model, name, reset)
        submap = name
    }

    function removableSubmap(name) {
        return model !== null && !readOnly
            && Model.removableSubmap(hand, doc ? doc.handSubmaps : [], model, name)
    }

    // The leave key of a submap hyprKBM defines; null for global and for one
    // only hyprland.lua defines.
    function submapReset(name) {
        return name === "" ? null : Model.submapReset(model || Model.emptyModel(), name)
    }

    function resetClash(name, reset) {
        return Model.resetClash(merged.binds, name, reset)
    }

    function setSubmapReset(name, reset) {
        if (model === null || readOnly || submapReset(name) === null || stagingBlocked()) return
        model = Model.setSubmapReset(model, name, reset)
    }

    function submapUse(name) {
        return Model.submapUse(model || Model.emptyModel(), name)
    }

    function removeSubmap(name) {
        if (!removableSubmap(name) || stagingBlocked()) return
        // A bind open in the editor that goes with it would save it back.
        if (draft !== null && (draft.submap === name
                || (draft.action && draft.action.kind === "submap" && draft.action.args && draft.action.args.name === name)))
            draft = null
        model = Model.removeSubmap(model, name)
        keepSubmapValid()
        report("Submap " + name + " removed. Apply to save it.", false)
    }

    // The header's chips in order, wrapping at either end.
    function cycleSubmap(step) {
        var i = submaps.indexOf(submap)
        submap = submaps[(i + step + submaps.length) % submaps.length]
    }

    function discard() {
        model = Model.clone(saved)
        keepSubmapValid()
        draft = null
        errors = []
        report("Changes discarded.", false)
    }

    // ----------------------------------------------------------- helpers

    function apply() {
        if (!dirty || busy || readOnly) return
        runApply(model)
    }

    // Applies a model that is not the staged one -- a restored backup. Python
    // validates it exactly as it does any other; only the busy guard is here.
    function applyModel(m) {
        if (busy) return
        runApply(m)
    }

    function runApply(m) {
        stopFind()
        busy = true
        report("Applying…", false)
        // Captured now: the process starts later, and a model edited in
        // between must not be what gets written.
        applyPayload = JSON.stringify(m)
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
        if (root.backupProc.running) return
        root.backupProc.command = [helper("hyprkbm"), "--backup", name]
        root.backupProc.running = true
    }

    function clearBackup() {
        backupWanted = ""
        backup = null
    }

    // Why the loaded backup cannot be restored right now, or "". A broken
    // keybinds.json makes the panel read-only, and restoring is the way out of
    // that; over staged edits it would silently replace them.
    readonly property string restoreRefusal: {
        if (backup === null) return "Pick a backup to restore first."
        if (busy) return "Wait for the current apply to finish."
        if (backup.modelError) return backup.modelError + " It cannot be restored."
        if (readOnly && !(doc && doc.modelError)) return "The keybinds cannot be edited, so a backup cannot be restored."
        if (dirty && !readOnly) return "Apply or discard your staged changes before restoring a backup."
        return ""
    }

    function restoreBackup() {
        if (restoreRefusal !== "") { report(restoreRefusal, true); return }
        var m = backup.model === null ? Model.emptyModel() : Model.clone(backup.model)
        if (!readOnly && JSON.stringify(m) === JSON.stringify(saved)) {
            report("That backup is what is applied already.", false)
            return
        }
        applyModel(m)
    }

    function exportTo(path) {
        root.exportProc.command = [helper("hyprkbm"), "--export", "md", path]
        root.exportProc.running = true
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
            other: otherCombos.map(function (b) { return b.uid }),
            otherKeys: Object.keys(otherKeys).length,
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
            write(root.applyPayload)
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
            var got = root.backupProc.command[2]
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
            if (code === 0) root.report("Exported to " + root.exportProc.command[3] + ".", false)
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

    property Process findEnter: Process {
        command: ["hyprctl", "eval", Capture.enterLua()]
        stderr: StdioCollector { id: findErr }
        onExited: function (code) {
            // Cancelled while the enter was in flight, or the Lua failed after
            // it had already switched: either way Hyprland may be in capture.
            if (!root.finding || code !== 0) root.leaveNow()
            if (root.finding && code !== 0) {
                root.finding = false
                root.report((findErr.text || "Hyprland could not enter find mode.").trim(), true)
            }
        }
    }

    // Hyprland leaves the submap by itself (its own timer, SUPER + Escape);
    // it has already left, so nothing is sent.
    property Connections hyprland: Connections {
        target: Hyprland
        function onRawEvent(event) {
            // Hyprland reloads when hyprland.lua is saved, so the panel follows
            // it. adopt() keeps staged edits; an apply re-reads by itself.
            if (event.name === "configreloaded" && !root.busy) {
                root.configReload.restart()
                return
            }
            if (root.finding && event.name === "submap" && event.data !== Capture.SUBMAP) {
                root.finding = false
                // Guarded Lua: harmless when Hyprland really left, and it ends
                // a capture that a stale event from an earlier find reported over.
                root.leaveNow()
            }
        }
    }

    // One read for a burst of reloads (an editor saving twice, the watcher's
    // own eval following Hyprland's).
    property Timer configReload: Timer {
        interval: 300
        onTriggered: root.reload()
    }

    // Backstop for a leave event that never arrives.
    property Timer findTimeout: Timer {
        interval: Capture.TIMEOUT_MS
        running: root.finding
        onTriggered: root.stopFind()
    }

    property Process watcherProc: Process {
        command: ["systemctl", "--user", "start", "hyprkbm-watch.service"]
        onExited: function (code) {
            if (code !== 0) root.report("The watcher could not be started; see systemctl --user status hyprkbm-watch.", true)
            root.reload()
        }
    }
}
