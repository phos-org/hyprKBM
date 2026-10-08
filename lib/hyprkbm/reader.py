"""Run the user's hyprland.lua through lib/reader.lua and turn what it
recorded into hand-written binds.

hyprctl reports every Lua bind as an opaque "__lua" reference, so the source
is the only place an action can be read from -- and running it, rather than
parsing it, is what gets loops, helper functions and `mainMod ..` right.
"""
import json
import os
import subprocess
from dataclasses import dataclass, field

from . import LIB
from .catalogue import valid_dsp
from .keys import KeyParseError, parse
from .luaval import interpreter

READER = LIB / "reader.lua"
TIMEOUT = 2.0


def fingerprint(dispatcher):
    """What a bind does, as one comparable string. Overrides and unbinds name
    the hand-written bind they act on by keys, submap and this -- never by
    line number, which moves whenever the user edits above it."""
    if "dsp" in dispatcher:
        args = json.dumps(dispatcher.get("args", []), sort_keys=True,
                          separators=(",", ":"), ensure_ascii=False)
        return "%s:%s" % (dispatcher["dsp"], args)
    if "raw" in dispatcher:
        return "raw:" + dispatcher["raw"]
    if "__function" in dispatcher:
        return "function:" + dispatcher["__function"]
    return "opaque"


def _has_marker(value):
    if isinstance(value, dict):
        return ("__function" in value or "__opaque" in value
                or any(_has_marker(v) for v in value.values()))
    if isinstance(value, list):
        return any(_has_marker(v) for v in value)
    return False


def reproducible(dispatcher, opts):
    """Whether hyprKBM could write this bind back out. Overriding one bind
    means unbinding its whole combo and re-creating the rest, so a Lua
    function sharing that combo blocks the override."""
    return (valid_dsp(dispatcher.get("dsp"))
            and not _has_marker(dispatcher) and not _has_marker(opts))


@dataclass
class HandBind:
    keys: str
    combo: str | None
    submap: str
    dispatcher: dict
    opts: dict
    file: str
    line: int
    seq: int

    @property
    def fingerprint(self):
        return fingerprint(self.dispatcher)

    @property
    def reproducible(self):
        return reproducible(self.dispatcher, self.opts)

    @property
    def where(self):
        return "%s:%d" % (os.path.basename(self.file), self.line)


@dataclass
class ReadResult:
    binds: list = field(default_factory=list)
    submaps: list = field(default_factory=list)
    error: str | None = None

    @property
    def submap_names(self):
        return {s["name"] for s in self.submaps}


def read_config(paths):
    entry = paths.entry
    command = [interpreter(), str(READER), str(entry), str(entry.parent), str(paths.lua)]
    try:
        res = subprocess.run(command, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return ReadResult(error="reading %s took longer than %g s; is there an "
                                "endless loop in it?" % (entry, TIMEOUT))
    if res.returncode != 0:
        return ReadResult(error="the reader failed: "
                                + res.stderr.decode("utf-8", "replace").strip())
    text = res.stdout.decode("utf-8", "replace")
    try:
        raw = json.loads(text)
    except ValueError:
        return ReadResult(error="the reader printed something that is not JSON: "
                                + text[:200])
    return _result(raw)


def _combo(keys):
    try:
        return parse(keys).id
    except KeyParseError:
        return None


def _list(value):
    # The reader writes an empty Lua table as {}, whatever it was meant to be.
    return value if isinstance(value, list) else []


def _result(raw):
    unbinds = [(u["seq"], _combo(u.get("keys"))) for u in _list(raw.get("unbinds"))]
    binds = []
    for b in _list(raw.get("binds")):
        combo = _combo(b.get("keys"))
        # hl.unbind drops the combo in every submap, so a later unbind in the
        # config itself means the bind never reaches Hyprland.
        if combo is not None and any(seq > b["seq"] and c == combo for seq, c in unbinds):
            continue
        keys = b.get("keys")
        opts = b.get("opts")
        binds.append(HandBind(
            keys=keys if isinstance(keys, str) else repr(keys),
            combo=combo,
            submap=b.get("submap") or "",
            dispatcher=b.get("dispatcher") or {"__opaque": True},
            opts=opts if isinstance(opts, dict) else {},
            file=b.get("file") or "?",
            line=b.get("line") or 0,
            seq=b["seq"],
        ))

    submaps = {}
    for s in _list(raw.get("submaps")):
        if not isinstance(s.get("name"), str):
            continue
        known = submaps.setdefault(s["name"], {"name": s["name"], "reset": s.get("reset"),
                                               "file": s.get("file"), "line": s.get("line")})
        # Defining a submap again appends to it; the reset key is whichever
        # definition gave one.
        if known["reset"] is None and s.get("reset") is not None:
            known["reset"] = s["reset"]

    error = raw.get("error")
    return ReadResult(binds, list(submaps.values()), error["message"] if error else None)
