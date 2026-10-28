import subprocess

import pytest

from hyprkbm.luaval import NotReproducible, interpreter, to_lua


def lua_prints(expression):
    res = subprocess.run([interpreter(), "-e", "io.write(%s)" % expression],
                         capture_output=True, check=True)
    return res.stdout.decode("utf-8")


@pytest.mark.parametrize("text", [
    "plain",
    'say "hi"',
    "back\\slash",
    "line\nbreak",
    "tab\tand\rcarriage",
    "nul\x00here",
    "bell\x07 then 7",
    "ünïcödé",
    'grim -g "$(slurp)" - | satty --filename -',
])
def test_strings_survive_a_trip_through_lua(text):
    assert lua_prints(to_lua(text)) == text


def test_scalars():
    assert to_lua(None) == "nil"
    assert to_lua(True) == "true"
    assert to_lua(False) == "false"
    assert to_lua(3) == "3"
    assert to_lua(-1.5) == "-1.5"


def test_non_finite_numbers_have_no_literal():
    with pytest.raises(ValueError):
        to_lua(float("nan"))


def test_tables_are_written_with_sorted_keys():
    assert to_lua({"workspace": 3, "action": "toggle"}) == \
        '{ action = "toggle", workspace = 3 }'
    assert to_lua([1, "a", True]) == '{ 1, "a", true }'
    assert to_lua({}) == "{}"
    assert to_lua([]) == "{}"


def test_keys_that_are_not_identifiers_are_bracketed():
    assert to_lua({"end": 1, "a-b": 2}) == '{ ["a-b"] = 2, ["end"] = 1 }'


def test_a_lua_function_cannot_be_written_back():
    with pytest.raises(NotReproducible):
        to_lua([{"cb": {"__function": "hyprland.lua:3"}}])
    with pytest.raises(NotReproducible):
        to_lua({"__opaque": True})


def test_the_interpreter_can_be_overridden(monkeypatch):
    monkeypatch.setenv("HYPRKBM_LUA", "/opt/lua/bin/lua")
    assert interpreter() == "/opt/lua/bin/lua"


def test_the_interpreter_is_also_found_by_freebsd_names(tmp_path, monkeypatch):
    lua = tmp_path / "lua54"
    lua.write_text("#!/bin/sh\n")
    lua.chmod(0o755)
    monkeypatch.delenv("HYPRKBM_LUA", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert interpreter() == str(lua)
