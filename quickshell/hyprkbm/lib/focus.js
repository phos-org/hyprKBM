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
