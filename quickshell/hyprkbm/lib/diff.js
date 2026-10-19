.pragma library

// A line diff for the review dialog: the generated keybinds.lua before and
// after. The files are a few hundred lines at most, so the plain
// longest-common-subsequence table is fast enough and easy to trust.

function lines(text) {
    if (text === "") return []
    var out = String(text).split("\n")
    if (out[out.length - 1] === "") out.pop()
    return out
}

function lineDiff(before, after) {
    var a = lines(before)
    var b = lines(after)
    var n = a.length
    var m = b.length
    var table = []
    for (var i = 0; i <= n; i++) { table.push(new Array(m + 1).fill(0)) }
    for (var x = n - 1; x >= 0; x--)
        for (var y = m - 1; y >= 0; y--)
            table[x][y] = a[x] === b[y] ? table[x + 1][y + 1] + 1 : Math.max(table[x + 1][y], table[x][y + 1])
    var out = []
    var p = 0
    var q = 0
    while (p < n && q < m) {
        if (a[p] === b[q]) { out.push({ op: " ", text: a[p] }); p++; q++ }
        else if (table[p + 1][q] >= table[p][q + 1]) { out.push({ op: "-", text: a[p] }); p++ }
        else { out.push({ op: "+", text: b[q] }); q++ }
    }
    while (p < n) { out.push({ op: "-", text: a[p] }); p++ }
    while (q < m) { out.push({ op: "+", text: b[q] }); q++ }
    return out
}

function counts(diff) {
    var out = { added: 0, removed: 0 }
    diff.forEach(function (l) {
        if (l.op === "+") out.added++
        else if (l.op === "-") out.removed++
    })
    return out
}
