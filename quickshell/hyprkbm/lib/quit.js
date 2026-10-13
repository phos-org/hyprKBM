.pragma library

// What Esc does in the window. Pure so the 3 s window is testable: the store
// keeps the arming timestamp and passes the clock in.
var WINDOW_MS = 3000

// Returns {action: "ignore"|"cancel"|"warn"|"quit", armedAt}. Quitting over
// staged edits needs a second Esc, because one stray press must not lose work.
function escape(s, armedAt, now) {
    if (s.busy) return { action: "ignore", armedAt: armedAt }
    if (s.draft) return { action: "cancel", armedAt: armedAt }
    if (!s.dirty) return { action: "quit", armedAt: armedAt }
    if (armedAt > 0 && now - armedAt <= WINDOW_MS) return { action: "quit", armedAt: armedAt }
    return { action: "warn", armedAt: now }
}
