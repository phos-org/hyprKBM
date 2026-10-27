"""keybinds.json -- hyprKBM's own binds, overrides, unbinds and submaps --
and how it combines with the hand-written binds into what Hyprland ends up
with."""
import copy
import json
from collections import defaultdict
from dataclasses import dataclass, field

from .catalogue import action_errors, to_dispatcher
from .keys import MODIFIERS, KeyParseError, parse
from .reader import reproducible

VERSION = 1
EMPTY = {"version": VERSION, "submaps": [], "binds": [], "unbinds": []}
FLAGS = {"repeating", "locked", "release", "non_consuming", "transparent",
         "ignore_mods", "dont_inhibit", "long_press", "submap_universal", "click",
         "drag", "mouse", "allow_input_capture"}


class ModelError(ValueError):
    pass


def load_model(path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return copy.deepcopy(EMPTY)
    except (OSError, UnicodeDecodeError) as exc:
        raise ModelError("%s could not be read: %s" % (path, exc)) from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ModelError("%s is not valid JSON: %s" % (path, exc)) from exc
    except RecursionError as exc:
        raise ModelError("%s could not be read: %s" % (path, exc)) from exc


@dataclass
class Bind:
    """One bind as Hyprland will have it after an apply."""
    keys: str
    combo: str | None
    submap: str
    dispatcher: dict
    opts: dict
    source: str
    where: str
    id: str | None = None
    allow_conflict: bool = False


@dataclass
class Merged:
    binds: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    touched: dict = field(default_factory=dict)
    stale: list = field(default_factory=list)

    def conflicts(self):
        groups = defaultdict(list)
        for b in self.binds:
            if b.combo is not None and not b.allow_conflict:
                groups[(b.submap, b.combo)].append(b)
        return [group for group in groups.values() if len(group) > 1]


def bind_opts(bind):
    opts = {name: True for name, on in (bind.get("flags") or {}).items() if on is True}
    if bind.get("description"):
        opts["description"] = bind["description"]
    return opts


def _matches(hand_bind, target):
    try:
        combo = parse(target["keys"]).id
    except KeyParseError:
        return False
    return (hand_bind.combo == combo
            and hand_bind.submap == target.get("submap", "")
            and hand_bind.fingerprint == target.get("fingerprint"))


def merge(model, hand, catalogue):
    merged = Merged()
    superseded = set()

    def supersede(target):
        hits = [h for h in hand.binds if _matches(h, target)]
        for h in hits:
            if id(h) not in superseded:
                superseded.add(id(h))
                merged.removed.append(h)
            merged.touched.setdefault(h.combo, h.keys)
        return bool(hits)

    for u in model.get("unbinds", []):
        if not supersede(u):
            merged.stale.append({
                "kind": "unbind", "id": None, "keys": u["keys"],
                "message": "The bind on %s this removes is no longer in %s; "
                           "the unbind does nothing." % (u["keys"], "hyprland.lua")})

    own = []
    for b in model.get("binds", []):
        replaced = False
        if "replaces" in b:
            replaced = supersede(b["replaces"])
            if not replaced:
                merged.stale.append({
                    "kind": "bind", "id": b["id"], "keys": b["keys"],
                    "message": "The hyprland.lua bind this replaced is gone; it is "
                               "now an ordinary bind."})
        own.append(Bind(keys=b["keys"], combo=parse(b["keys"]).id,
                        submap=b.get("submap", ""),
                        dispatcher=to_dispatcher(b["action"], catalogue),
                        opts=bind_opts(b), source="override" if replaced else "hyprkbm",
                        where=b["id"], id=b["id"],
                        allow_conflict=b.get("allowConflict") is True))

    for h in hand.binds:
        if id(h) not in superseded:
            merged.binds.append(Bind(keys=h.keys, combo=h.combo, submap=h.submap,
                                     dispatcher=h.dispatcher, opts=h.opts,
                                     source="hand", where=h.where))
    merged.binds.extend(own)
    return merged


def _valid_target(target):
    if not isinstance(target, dict):
        return False
    if not all(isinstance(target.get(k), str) for k in ("keys", "submap", "fingerprint")):
        return False
    try:
        parse(target["keys"])
    except KeyParseError:
        return False
    return True


def structure_errors(model, hand, catalogue):
    """Everything wrong with the file itself. merge() needs none of these."""
    errors = []

    def err(message, bind_id=None):
        errors.append({"id": bind_id, "message": message})

    if not isinstance(model, dict):
        err("keybinds.json must hold a JSON object")
        return errors
    if model.get("version") != VERSION:
        err("keybinds.json version must be %d" % VERSION)
        return errors
    for name in ("submaps", "binds", "unbinds"):
        if not isinstance(model.get(name, []), list):
            err("%s must be a list" % name)
    if errors:
        return errors

    own_submaps = set()
    for i, s in enumerate(model.get("submaps", [])):
        name = s.get("name") if isinstance(s, dict) else None
        if not isinstance(name, str) or not name:
            err("submaps[%d] needs a name" % i)
            continue
        if name in own_submaps:
            err("submap %r is defined twice" % name)
        if name in hand.submap_names:
            err("submap %r is already defined in hyprland.lua; add binds to it "
                "without defining it again" % name)
        if not isinstance(s.get("reset"), str) or not s["reset"]:
            err("submap %r needs a reset key" % name)
        else:
            # Written as a bind inside the submap: a bad one leaves no way out.
            try:
                if parse(s["reset"]).key.upper() in MODIFIERS:
                    err("submap %r needs a key that is not a modifier to leave it" % name)
            except KeyParseError as exc:
                err("submap %r: %s" % (name, exc))
        own_submaps.add(name)
    known_submaps = own_submaps | hand.submap_names | {""}

    seen = set()
    for i, b in enumerate(model.get("binds", [])):
        if not isinstance(b, dict):
            err("binds[%d] must be an object" % i)
            continue
        bid = b.get("id")
        if not isinstance(bid, str) or not bid:
            err("binds[%d] needs an id" % i)
            bid = None
        elif bid in seen:
            err("id %r is used twice" % bid, bid)
        else:
            seen.add(bid)
        label = b["keys"] if isinstance(b.get("keys"), str) else "binds[%d]" % i
        try:
            parse(b.get("keys"))
        except KeyParseError as exc:
            err("%s: %s" % (label, exc), bid)
        submap = b.get("submap", "")
        if not isinstance(submap, str):
            err("%s: submap must be text" % label, bid)
        elif submap not in known_submaps:
            err("%s: no submap called %r" % (label, submap), bid)
        for problem in action_errors(b.get("action"), catalogue):
            err("%s: %s" % (label, problem), bid)
        if not isinstance(b.get("description", ""), str):
            err("%s: description must be text" % label, bid)
        flags = b.get("flags", {})
        if not isinstance(flags, dict) or any(
                k not in FLAGS or not isinstance(v, bool) for k, v in flags.items()):
            err("%s: flags must map %s to true or false"
                % (label, ", ".join(sorted(FLAGS))), bid)
        if not isinstance(b.get("allowConflict", False), bool):
            err("%s: allowConflict must be true or false" % label, bid)
        if "replaces" in b and not _valid_target(b["replaces"]):
            err("%s: replaces needs keys, submap and fingerprint" % label, bid)

    for i, u in enumerate(model.get("unbinds", [])):
        if not _valid_target(u):
            err("unbinds[%d] needs keys, submap and fingerprint" % i)
    return errors


def validate(model, hand, catalogue):
    """Everything that would stop an apply."""
    errors = structure_errors(model, hand, catalogue)
    if errors:
        return errors

    merged = merge(model, hand, catalogue)
    for group in merged.conflicts():
        own = [b for b in group if b.source != "hand"]
        # Duplicates purely within hyprland.lua are the user's own to sort
        # out; refusing every apply until they do would help nobody.
        if not own:
            continue
        submap = "" if group[0].submap == "" else " in submap %s" % group[0].submap
        errors.append({"id": own[0].id, "message": "%s%s is bound %d times: %s" % (
            group[0].keys, submap, len(group), ", ".join(b.where for b in group))})

    for combo, keys in merged.touched.items():
        for b in merged.binds:
            if b.source == "hand" and b.combo == combo and not reproducible(b.dispatcher, b.opts):
                errors.append({"id": None, "message": (
                    "%s also has a bind at %s whose action hyprKBM cannot "
                    "re-create (a Lua function or an unusual dispatcher). hyprKBM "
                    "replaces a bind by unbinding its keys and re-creating the others "
                    "on them, and it cannot re-create that one; change it in "
                    "hyprland.lua instead." % (keys, b.where))})
    return errors
