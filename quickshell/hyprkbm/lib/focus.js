.pragma library

// Which part of the panel has the keys. Pure, so the Tab order is testable.
var AREAS = ["keyboard", "list", "editor"]

function usable(hasEditor) {
    return AREAS.filter(function (a) { return a !== "editor" || hasEditor })
}

function step(area, hasEditor, by) {
    var order = usable(hasEditor)
    var i = order.indexOf(area)
    if (i < 0) {
        // An editor that just closed sits after the list: Tab wraps, Shift+Tab
        // lands on the list. Anything unknown starts from the keyboard.
        if (area === "editor") return by > 0 ? order[0] : order[order.length - 1]
        i = 0
    }
    return order[(i + by + order.length) % order.length]
}

// Tab. The editor is skipped while no draft is open.
function next(area, hasEditor) { return step(area, hasEditor, 1) }

// Shift+Tab.
function prev(area, hasEditor) { return step(area, hasEditor, -1) }

// -1 when there is nothing to point at.
function clampIndex(index, length) {
    if (length <= 0) return -1
    return Math.max(0, Math.min(index, length - 1))
}

// The list's cursor belongs to its context (key, modifiers, submap, query).
function contextChanged(before, after) { return before !== after }

// Where the cursor goes when the list changes: back to the top for a new
// context, otherwise stay on the same row, or the last one if it shrank.
function reconcile(index, length, changed) {
    if (changed) return 0
    return Math.max(0, clampIndex(index, length))
}

// Tab inside the editor: the next of its `count` controls from `index`, or -1
// when the walk runs off either end and the keys go on to the next area. An
// index of -1 (focus on something the walk does not list) enters at the near end.
function walk(index, count, back) {
    if (count <= 0) return -1
    if (index < 0) return back ? count - 1 : 0
    var to = index + (back ? -1 : 1)
    return to < 0 || to >= count ? -1 : to
}
