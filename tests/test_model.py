import textwrap

import pytest

from hyprkbm.catalogue import load_catalogue
from hyprkbm.model import ModelError, load_model, merge, structure_errors, validate
from hyprkbm.reader import read_config

CAT = load_catalogue()
DOLPHIN = 'exec_cmd:["dolphin"]'


def hand(paths, source):
    paths.entry.write_text(textwrap.dedent(source))
    return read_config(paths)


def model(**parts):
    return {"version": 1, "submaps": [], "binds": [], "unbinds": [], **parts}


def bind(id, keys, cmd="nautilus", **extra):
    return {"id": id, "keys": keys,
            "action": {"kind": "exec_cmd", "args": {"cmd": cmd}}, **extra}


BASE = """\
    hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))
    hl.bind("SUPER + P", hl.dsp.window.pseudo())
"""


def test_a_missing_model_is_empty(paths):
    assert load_model(paths.model) == model()


def test_a_broken_model_says_so(paths):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_text("{oops")
    with pytest.raises(ModelError):
        load_model(paths.model)


def test_a_directory_as_model_raises_error(paths):
    paths.model.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ModelError):
        load_model(paths.model)


def test_invalid_utf8_in_model_raises_error(paths):
    paths.model.parent.mkdir(parents=True)
    paths.model.write_bytes(b"\xff\xfe{")
    with pytest.raises(ModelError):
        load_model(paths.model)


def test_merge_keeps_hand_binds_and_adds_hyprkbms(paths):
    m = merge(model(binds=[bind("b1", "SUPER + B", "firefox")]), hand(paths, BASE), CAT)

    assert [(b.keys, b.source) for b in m.binds] == \
        [("SUPER + F", "hand"), ("SUPER + P", "hand"), ("SUPER + B", "hyprkbm")]
    assert m.binds[0].where == "hyprland.lua:1"
    assert m.binds[2].where == "b1"
    assert m.touched == {}


def test_an_override_replaces_the_hand_bind(paths):
    m = merge(model(binds=[bind("b1", "super + f", description="Files",
                                replaces={"keys": "SUPER + F", "submap": "",
                                          "fingerprint": DOLPHIN})]),
              hand(paths, BASE), CAT)

    assert [(b.keys, b.source) for b in m.binds] == \
        [("SUPER + P", "hand"), ("super + f", "override")]
    assert m.binds[1].opts == {"description": "Files"}
    assert m.touched == {"SUPER+f": "SUPER + F"}
    assert [h.where for h in m.removed] == ["hyprland.lua:1"]


def test_an_unbind_removes_the_hand_bind(paths):
    m = merge(model(unbinds=[{"keys": "SUPER + P", "submap": "",
                              "fingerprint": "window.pseudo:[]"}]),
              hand(paths, BASE), CAT)

    assert [b.keys for b in m.binds] == ["SUPER + F"]
    assert m.touched == {"SUPER+p": "SUPER + P"}


def test_targets_that_no_longer_exist_are_stale(paths):
    m = merge(model(binds=[bind("b1", "SUPER + F", replaces={
                        "keys": "SUPER + F", "submap": "", "fingerprint": 'exec_cmd:["thunar"]'})],
                    unbinds=[{"keys": "SUPER + X", "submap": "", "fingerprint": "exit:[]"}]),
              hand(paths, BASE), CAT)

    assert [(s["kind"], s["id"], s["keys"]) for s in m.stale] == \
        [("unbind", None, "SUPER + X"), ("bind", "b1", "SUPER + F")]
    # A stale override is still applied, as an ordinary bind.
    assert [b.source for b in m.binds] == ["hand", "hand", "hyprkbm"]
    assert m.touched == {}


def test_conflicts_group_by_combo_and_submap(paths):
    m = merge(model(binds=[bind("b1", "WIN + f"),
                           bind("b2", "SUPER + P", allowConflict=True),
                           bind("b3", "SUPER + Z", submap="x")],
                    submaps=[{"name": "x", "reset": "escape"}]),
              hand(paths, BASE + 'hl.bind("SUPER + Z", hl.dsp.exit())\n'), CAT)

    assert [[b.where for b in group] for group in m.conflicts()] == \
        [["hyprland.lua:1", "b1"]]


def test_valid_models_pass(paths):
    assert validate(model(binds=[bind("b1", "SUPER + B")]), hand(paths, BASE), CAT) == []


@pytest.mark.parametrize("broken,problem", [
    ({"version": 2}, "version must be 1"),
    ({"binds": {}}, "binds must be a list"),
    ({"binds": [bind("", "SUPER + B")]}, "needs an id"),
    ({"binds": [bind("b1", "SUPER + B"), bind("b1", "SUPER + N")]}, "used twice"),
    ({"binds": [bind("b1", "SUPER + BOGUS + B")]}, "not a modifier"),
    ({"binds": [bind("b1", "SUPER + B", submap="nowhere")]}, "no submap called 'nowhere'"),
    ({"binds": [bind("b1", "SUPER + B", submap=[])]}, "submap must be text"),
    ({"binds": [{"id": "b1", "keys": "SUPER + B", "action": {"kind": "nope"}}]}, "unknown action"),
    ({"binds": [bind("b1", "SUPER + B", flags={"sticky": True})]}, "flags must map"),
    ({"binds": [bind("b1", "SUPER + B", description=3)]}, "description must be text"),
    ({"binds": [bind("b1", "SUPER + B", replaces={"keys": "SUPER + B"})]}, "replaces needs"),
    ({"unbinds": [{"keys": "SUPER + P"}]}, "unbinds[0] needs"),
    ({"submaps": [{"name": "x"}]}, "needs a reset key"),
    ({"submaps": [{"name": "x", "reset": "FOO + e"}]}, "'FOO' is not a modifier"),
    ({"submaps": [{"name": "x", "reset": "SUPER + "}]}, "needs a key that is not a modifier"),
    ({"submaps": [{"name": "x", "reset": "escape"}, {"name": "x", "reset": "escape"}]},
     "defined twice"),
])
def test_structural_problems_are_reported(paths, broken, problem):
    errors = structure_errors(model(**broken), hand(paths, BASE), CAT)
    assert any(problem in e["message"] for e in errors), errors


def test_a_model_that_is_not_an_object_is_reported(paths):
    errors = structure_errors([], hand(paths, BASE), CAT)
    assert "JSON object" in errors[0]["message"]


def test_a_bind_can_enter_only_a_submap_that_exists(paths):
    def enter(name):
        return {"id": "e1", "keys": "SUPER + R", "action": {"kind": "submap", "args": {"name": name}}}

    h = hand(paths, 'hl.define_submap("resize", function() hl.bind("l", hl.dsp.window.resize()) end)\n')
    own = [{"name": "move", "reset": "escape"}]
    assert validate(model(binds=[enter("resize")], submaps=own), h, CAT) == []
    assert validate(model(binds=[enter("move")], submaps=own), h, CAT) == []
    # "reset" is Hyprland's name for going back to the global binds.
    assert validate(model(binds=[enter("reset")], submaps=own), h, CAT) == []
    errors = validate(model(binds=[enter("mvoe")], submaps=own), h, CAT)
    assert [e["message"] for e in errors] == [
        "SUPER + R: enters the submap 'mvoe', which does not exist, so its keys would do nothing"]


def test_a_submap_from_hyprland_lua_cannot_be_defined_again(paths):
    h = hand(paths, 'hl.define_submap("resize", "escape", function() end)\n')
    errors = structure_errors(model(submaps=[{"name": "resize", "reset": "escape"}]), h, CAT)
    assert "already defined in hyprland.lua" in errors[0]["message"]
    # ...but binds can be added to it.
    assert validate(model(binds=[bind("b1", "right", submap="resize")]), h, CAT) == []


def test_conflicts_involving_hyprkbm_block_and_name_the_bind(paths):
    errors = validate(model(binds=[bind("b1", "SUPER + F")]), hand(paths, BASE), CAT)

    assert errors == [{"id": "b1", "message":
                       "SUPER + F is bound 2 times: hyprland.lua:1, b1"}]


def test_conflicts_only_within_hyprland_lua_do_not_block(paths):
    h = hand(paths, BASE + 'hl.bind("SUPER + F", hl.dsp.exit())\n')
    assert validate(model(), h, CAT) == []


def test_allowing_a_conflict_unblocks_it(paths):
    errors = validate(model(binds=[bind("b1", "SUPER + F", allowConflict=True)]),
                      hand(paths, BASE), CAT)
    assert errors == []


def test_a_function_bind_sharing_a_touched_combo_blocks_the_override(paths):
    h = hand(paths, """\
        hl.bind("SUPER + F", hl.dsp.exec_cmd("dolphin"))
        hl.define_submap("x", "escape", function()
            hl.bind("SUPER + F", function() end)
        end)
    """)
    errors = validate(model(binds=[bind("b1", "SUPER + F", replaces={
        "keys": "SUPER + F", "submap": "", "fingerprint": DOLPHIN})]), h, CAT)

    assert len(errors) == 1
    assert "hyprland.lua:3" in errors[0]["message"]
    assert "cannot re-create (a Lua function or an unusual dispatcher)" in errors[0]["message"]
