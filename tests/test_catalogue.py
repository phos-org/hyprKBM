import re
from pathlib import Path

import pytest

from hyprkbm.catalogue import (action_errors, describe, dispatcher_lua,
                               load_catalogue, to_dispatcher)
from hyprkbm.luaval import NotReproducible

STUB = Path("/usr/share/hypr/stubs/hl.meta.lua")
CAT = load_catalogue()


def stub_dispatchers(text):
    """Every hl.dsp path the installed Hyprland declares."""
    names, prefix = set(), None
    for line in text.splitlines():
        cls = re.match(r"---@class HL\.Dsp(\w*)Namespace\s*$", line)
        if cls:
            prefix = cls.group(1).lower()
            continue
        if prefix is None:
            continue
        fld = re.match(r"---@field (\w+) fun\(", line)
        if fld:
            names.add(fld.group(1) if prefix == "" else prefix + "." + fld.group(1))
        elif not line.startswith("---@field"):
            prefix = None
    return names


@pytest.mark.skipif(not STUB.exists(), reason="Hyprland's Lua stubs are not installed")
def test_every_catalogue_dispatcher_exists_in_hyprland():
    known = stub_dispatchers(STUB.read_text())
    assert known, "the stub parser found nothing; has the stub format changed?"
    assert {a["dsp"] for a in CAT.values()} <= known


def test_catalogue_entries_are_well_formed():
    for entry in CAT.values():
        assert entry["call"] in ("none", "positional", "table"), entry["id"]
        if entry["call"] == "none":
            assert entry["fields"] == [], entry["id"]
        names = {f["name"] for f in entry["fields"]}
        for f in entry["fields"]:
            assert f["type"] in ("string", "workspace", "enum", "bool", "submap")
            if f["type"] == "enum":
                assert f["values"]
        assert set(entry.get("oneOf", [])) <= names, entry["id"]


def test_actions_become_dispatchers():
    assert to_dispatcher({"kind": "exec_cmd", "args": {"cmd": "kitty"}}, CAT) == \
        {"dsp": "exec_cmd", "args": ["kitty"]}
    assert to_dispatcher({"kind": "window.move", "args": {"workspace": 3}}, CAT) == \
        {"dsp": "window.move", "args": [{"workspace": 3}]}
    assert to_dispatcher({"kind": "window.close"}, CAT) == \
        {"dsp": "window.close", "args": []}
    assert to_dispatcher({"kind": "window.cycle_next", "args": {}}, CAT) == \
        {"dsp": "window.cycle_next", "args": []}
    assert to_dispatcher({"kind": "raw", "lua": "hl.dsp.exit()"}, CAT) == \
        {"raw": "hl.dsp.exit()"}


def test_dispatchers_become_lua():
    assert dispatcher_lua({"dsp": "window.move", "args": [{"workspace": 3}]}) == \
        "hl.dsp.window.move({ workspace = 3 })"
    assert dispatcher_lua({"dsp": "exec_cmd", "args": ["kitty"]}) == \
        'hl.dsp.exec_cmd("kitty")'
    assert dispatcher_lua({"raw": "hl.dsp.layout(\"togglesplit\")"}) == \
        'hl.dsp.layout("togglesplit")'
    with pytest.raises(NotReproducible):
        dispatcher_lua({"__function": "hyprland.lua:3"})


@pytest.mark.parametrize("action,problem", [
    ({"kind": "nope"}, "unknown action"),
    ({"kind": "exec_cmd", "args": {}}, "needs command"),
    ({"kind": "exec_cmd", "args": {"cmd": ""}}, "must be text"),
    ({"kind": "exec_cmd", "args": {"cmd": "x", "extra": 1}}, "no field 'extra'"),
    ({"kind": "window.float", "args": {"action": "flip"}}, "must be one of"),
    ({"kind": "window.move", "args": {}}, "exactly one of"),
    ({"kind": "window.move", "args": {"workspace": 1, "direction": "left"}}, "exactly one of"),
    ({"kind": "window.move", "args": {"workspace": True}}, "workspace number or name"),
    ({"kind": "window.cycle_next", "args": {"next": "yes"}}, "true or false"),
    ({"kind": "raw", "lua": "  "}, "needs some Lua"),
    ("exec_cmd", "must be an object"),
])
def test_bad_actions_are_explained(action, problem):
    errors = action_errors(action, CAT)
    assert any(problem in e for e in errors), errors


def test_good_actions_have_no_errors():
    assert action_errors({"kind": "focus", "args": {"workspace": "e+1"}}, CAT) == []
    assert action_errors({"kind": "window.close"}, CAT) == []
    assert action_errors({"kind": "raw", "lua": "hl.dsp.exit()"}, CAT) == []


def test_describe_reads_like_a_sentence():
    assert describe({"dsp": "exec_cmd", "args": ["kitty"]}, CAT) == "Run a command: kitty"
    assert describe({"dsp": "focus", "args": [{"workspace": 3}]}, CAT) == "Focus (workspace 3)"
    assert describe({"dsp": "window.close", "args": []}, CAT) == "Close window"
    assert describe({"dsp": "window.cycle_next", "args": [{"next": False}]}, CAT) == \
        "Cycle windows (next no)"
    assert describe({"dsp": "group.toggle", "args": []}, CAT) == "hl.dsp.group.toggle()"
    assert describe({"__function": "/home/u/.config/hypr/hyprland.lua:150"}, CAT) == \
        "Lua function (hyprland.lua:150)"
    assert describe({"raw": "hl.dsp.layout(\n  'x')"}, CAT) == "Lua: hl.dsp.layout( 'x')"
