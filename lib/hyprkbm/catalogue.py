"""The action picker's catalogue, share/actions.json, and the step from a
catalogue action to the dispatcher it stands for."""
import json
import os
import re

from . import SHARE
from .luaval import NotReproducible, to_lua

CATALOGUE = SHARE / "actions.json"


def load_catalogue(path=CATALOGUE):
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in data["actions"]}


def _field_problem(field, value):
    kind = field["type"]
    if kind in ("string", "submap"):
        return None if isinstance(value, str) and value != "" else "must be text"
    if kind == "workspace":
        number = isinstance(value, int) and not isinstance(value, bool)
        name = isinstance(value, str) and value != ""
        return None if number or name else "must be a workspace number or name"
    if kind == "enum":
        return None if value in field["values"] else \
            "must be one of %s" % ", ".join(field["values"])
    if kind == "bool":
        return None if isinstance(value, bool) else "must be true or false"
    return "has an unknown type %r" % kind


def action_errors(action, catalogue):
    if not isinstance(action, dict):
        return ["action must be an object"]
    kind = action.get("kind")
    if kind == "raw":
        lua = action.get("lua")
        return [] if isinstance(lua, str) and lua.strip() else ["raw action needs some Lua"]
    entry = catalogue.get(kind) if isinstance(kind, str) else None
    if entry is None:
        return ["unknown action %r" % (kind,)]
    args = action.get("args", {})
    if not isinstance(args, dict):
        return ["args must be an object"]

    fields = {f["name"]: f for f in entry["fields"]}
    errors = ["%s has no field %r" % (entry["label"], name) for name in args if name not in fields]
    for name, f in fields.items():
        if name not in args:
            if f.get("required"):
                errors.append("%s needs %s" % (entry["label"], f["label"].lower()))
            continue
        problem = _field_problem(f, args[name])
        if problem:
            errors.append("%s: %s" % (f["label"], problem))
    one_of = entry.get("oneOf")
    if one_of and sum(1 for name in one_of if name in args) != 1:
        errors.append("%s needs exactly one of: %s" % (entry["label"], ", ".join(one_of)))
    return errors


def to_dispatcher(action, catalogue):
    """The dispatcher description a valid action stands for -- the same shape
    the reader gives hand-written binds, so both fingerprint alike."""
    if action["kind"] == "raw":
        return {"raw": action["lua"]}
    entry = catalogue[action["kind"]]
    args = action.get("args", {})
    if entry["call"] == "none":
        return {"dsp": entry["dsp"], "args": []}
    if entry["call"] == "positional":
        values = []
        for f in entry["fields"]:
            if f["name"] not in args:
                break
            values.append(args[f["name"]])
        return {"dsp": entry["dsp"], "args": values}
    table = {f["name"]: args[f["name"]] for f in entry["fields"] if f["name"] in args}
    return {"dsp": entry["dsp"], "args": [table] if table else []}


# A dsp path is pasted into Lua source, so anything but dotted identifiers
# (which the reader can report for a hand-written bind) would be invalid Lua
# or worse.
DSP_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def valid_dsp(dsp):
    return isinstance(dsp, str) and DSP_PATH.match(dsp) is not None


def dispatcher_lua(dispatcher):
    if "raw" in dispatcher:
        # On lines of its own so a trailing `-- comment` in the raw text cannot
        # swallow the closing parenthesis and the options after it.
        return "(\n%s\n)" % dispatcher["raw"]
    if "dsp" not in dispatcher:
        raise NotReproducible(dispatcher.get("__function") or "an hl object")
    if not valid_dsp(dispatcher["dsp"]):
        raise NotReproducible("the action %r" % (dispatcher["dsp"],))
    return "hl.dsp.%s(%s)" % (dispatcher["dsp"],
                              ", ".join(to_lua(a) for a in dispatcher.get("args", [])))


def _plain(value):
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def describe(dispatcher, catalogue):
    """What a bind does, in one line for people."""
    if "raw" in dispatcher:
        return "Lua: " + " ".join(dispatcher["raw"].split())
    if "__function" in dispatcher:
        return "Lua function (%s)" % os.path.basename(dispatcher["__function"])
    if "dsp" not in dispatcher:
        return "Unknown action"
    args = dispatcher.get("args", [])
    entry = next((e for e in catalogue.values() if e["dsp"] == dispatcher["dsp"]), None)
    if entry is None:
        try:
            return dispatcher_lua(dispatcher)
        except NotReproducible:
            return "hl.dsp.%s(…)" % dispatcher["dsp"]
    if entry["call"] == "table" and len(args) == 1 and isinstance(args[0], dict) and args[0]:
        details = ", ".join("%s %s" % (k, _plain(v)) for k, v in sorted(args[0].items()))
        return "%s (%s)" % (entry["label"], details)
    if args:
        return "%s: %s" % (entry["label"], " ".join(_plain(a) for a in args))
    return entry["label"]
