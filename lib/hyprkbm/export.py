"""The cheatsheet as Markdown: by submap, then by modifier combo."""
from collections import defaultdict

from .catalogue import describe
from .keys import ORDER, KeyParseError, parse


def _split(keys):
    try:
        combo = parse(keys)
    except KeyParseError:
        return (), keys
    return combo.mods, combo.key


def _cell(value):
    return " ".join(str(value).split()).replace("|", "\\|")


def _description(opts):
    return opts.get("description") or opts.get("desc") or ""


def export_markdown(merged, catalogue):
    lines = ["# Keybinds", ""]
    by_submap = defaultdict(list)
    for b in merged.binds:
        by_submap[b.submap].append(b)

    for submap in sorted(by_submap, key=lambda n: (n != "", n)):
        lines += ["## %s" % (submap or "Global"), ""]
        by_mods = defaultdict(list)
        for b in by_submap[submap]:
            by_mods[_split(b.keys)[0]].append(b)
        for mods in sorted(by_mods, key=lambda m: (len(m), [ORDER.index(x) for x in m])):
            lines += ["### %s" % (" + ".join(mods) or "No modifier"), "",
                      "| Key | Description | Action |", "|---|---|---|"]
            for b in sorted(by_mods[mods], key=lambda b: _split(b.keys)[1].lower()):
                lines.append("| %s | %s | %s |" % (
                    _cell(_split(b.keys)[1]), _cell(_description(b.opts)),
                    _cell(describe(b.dispatcher, catalogue))))
            lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"
