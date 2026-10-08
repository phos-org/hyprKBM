import textwrap
from pathlib import Path

from hyprkbm import reader
from hyprkbm.reader import fingerprint, read_config

FIXTURE = Path(__file__).parent / "fixtures" / "hyprland.lua"


def read(paths, source, **files):
    paths.entry.write_text(textwrap.dedent(source))
    for name, text in files.items():
        target = paths.entry.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text))
    return read_config(paths)


def by_keys(result):
    return {(b.submap, b.keys): b for b in result.binds}


def test_constants_and_concatenation_are_evaluated(paths):
    result = read(paths, """\
        local mainMod = "SUPER"
        hl.bind(mainMod .. " + F", hl.dsp.exec_cmd("dolphin"))
    """)

    assert result.error is None
    [bind] = result.binds
    assert bind.keys == "SUPER + F"
    assert bind.combo == "SUPER+f"
    assert bind.dispatcher == {"dsp": "exec_cmd", "args": ["dolphin"]}
    assert bind.fingerprint == 'exec_cmd:["dolphin"]'
    assert bind.line == 2
    assert bind.where == "hyprland.lua:2"
    assert bind.reproducible


def test_a_realistic_config_reads_completely(paths):
    paths.entry.write_text(FIXTURE.read_text())

    result = read_config(paths)

    assert result.error is None
    assert len(result.binds) == 31
    binds = by_keys(result)
    assert binds[("", "SUPER + 0")].dispatcher == \
        {"dsp": "focus", "args": [{"workspace": 10}]}
    assert binds[("", "SUPER + SHIFT + 3")].dispatcher == \
        {"dsp": "window.move", "args": [{"workspace": 3}]}
    assert binds[("", "SUPER + mouse:272")].opts == {"mouse": True}
    assert binds[("", "SUPER + Q")].line == 9
    assert binds[("resize", "right")].opts == {"repeating": True}
    assert binds[("", "SUPER + R")].submap == ""
    assert result.submaps == [{"name": "resize", "reset": "escape",
                               "file": str(paths.entry), "line": 23}]


def test_submap_can_be_appended_to_without_a_reset(paths):
    result = read(paths, """\
        hl.define_submap("move", "escape", function() end)
        hl.define_submap("move", function()
            hl.bind("left", hl.dsp.window.move({ direction = "left" }))
        end)
    """)

    assert [s["reset"] for s in result.submaps] == ["escape"]
    assert result.binds[0].submap == "move"


def test_function_dispatchers_are_recorded_but_not_reproducible(paths):
    result = read(paths, """\
        hl.bind("SUPER + G", function()
            hl.exec_cmd("kitty")
        end)
    """)

    [bind] = result.binds
    assert bind.dispatcher == {"__function": "%s:1" % paths.entry}
    assert bind.fingerprint == "function:%s:1" % paths.entry
    assert not bind.reproducible


def test_a_later_unbind_removes_an_earlier_bind_in_every_submap(paths):
    result = read(paths, """\
        hl.bind("SUPER + P", hl.dsp.window.pseudo())
        hl.define_submap("x", "escape", function()
            hl.bind("SUPER + P", hl.dsp.window.pin())
        end)
        hl.unbind("super + p")
        hl.bind("SUPER + P", hl.dsp.window.close())
    """)

    assert [b.dispatcher["dsp"] for b in result.binds] == ["window.close"]


def test_require_and_dofile_load_from_the_config_dir(paths):
    result = read(paths, """\
        require("binds")
        dofile("extra/more.lua")
    """, **{"binds.lua": 'hl.bind("SUPER + A", hl.dsp.exit())\n',
            "extra/more.lua": 'hl.bind("SUPER + B", hl.dsp.exit())\n'})

    assert result.error is None
    assert [Path(b.file).name for b in result.binds] == ["binds.lua", "more.lua"]


def test_the_sandbox_has_no_os_execute_or_io(paths, tmp_path):
    marker = tmp_path / "pwned"
    result = read(paths, """\
        hl.bind("SUPER + A", hl.dsp.exit())
        os.execute("touch %s")
    """ % marker)

    assert not marker.exists()
    assert "execute" in result.error
    assert len(result.binds) == 1, "binds before the error are kept"

    result = read(paths, 'io.open("/etc/hostname")\n')
    assert "io" in result.error


def test_files_outside_the_config_dir_are_refused(paths):
    result = read(paths, 'dofile("/etc/passwd")\n')

    assert "refusing to load /etc/passwd" in result.error


def test_hyprkbms_own_file_is_never_read_back(paths, monkeypatch):
    monkeypatch.setenv("HOME", str(paths.entry.parents[2]))
    paths.lua.parent.mkdir(parents=True)
    paths.lua.write_text('hl.bind("SUPER + B", hl.dsp.exit())\n')

    result = read(paths, """\
        dofile(os.getenv("HOME") .. "/.config/hyprkbm/keybinds.lua")
    """)

    assert result.error is None
    assert result.binds == []


def test_an_endless_loop_times_out(paths, monkeypatch):
    monkeypatch.setattr(reader, "TIMEOUT", 0.5)

    result = read(paths, "while true do end\n")

    assert "endless loop" in result.error


def test_live_state_and_the_rest_of_hl_do_nothing(paths):
    result = read(paths, """\
        for _, m in ipairs(hl.get_monitors()) do
            hl.bind("SUPER + M", hl.dsp.exit())
        end
        if hl.get_active_window() then hl.bind("SUPER + W", hl.dsp.exit()) end
        hl.config({ general = { gaps_in = 5 } })
        hl.window_rule({ match = { class = "kitty" } }):set_enabled(false)
        hl.on("hyprland.start", function() hl.bind("SUPER + X", hl.dsp.exit()) end)
        local k = hl.bind("SUPER + K", hl.dsp.exit())
        k:set_enabled(false)
    """)

    assert result.error is None
    assert [b.keys for b in result.binds] == ["SUPER + K"]


def test_a_missing_entry_is_an_error(paths):
    paths.entry.unlink()

    assert "cannot open" in read_config(paths).error


def test_fingerprints_sort_table_keys():
    a = fingerprint({"dsp": "window.fullscreen",
                     "args": [{"mode": "fullscreen", "action": "toggle"}]})
    b = fingerprint({"dsp": "window.fullscreen",
                     "args": [{"action": "toggle", "mode": "fullscreen"}]})
    assert a == b == 'window.fullscreen:[{"action":"toggle","mode":"fullscreen"}]'
    assert fingerprint({"raw": "hl.dsp.exit()"}) == "raw:hl.dsp.exit()"


def test_a_config_cannot_swap_string_find_to_escape_the_config_dir(paths):
    outside = paths.entry.parent.parent / "outside.lua"
    outside.write_text('hl.bind("SUPER + X", hl.dsp.exec_cmd("evil"))\n')

    result = read(paths, """\
        string.find = function() return nil end
        dofile("../outside.lua")
    """)

    assert result.binds == []
    assert "refusing to load" in result.error


def test_a_config_cannot_swap_the_shared_string_metatable_to_escape(paths, tmp_path):
    outside = tmp_path / "outside.lua"
    outside.write_text('hl.bind("SUPER + X", hl.dsp.exec_cmd("evil"))\n')
    prefix = str(paths.entry.parent) + "/"

    result = read(paths, """\
        local mt = getmetatable("")
        if type(mt) == "table" then
            mt.__index.sub = function() return "PREFIX" end
        end
        dofile("OUTSIDE")
    """.replace("PREFIX", prefix).replace("OUTSIDE", str(outside)))

    assert result.binds == []
    assert "refusing" in result.error


def test_unbind_can_be_chained_like_bind(paths):
    result = read(paths, 'hl.unbind("SUPER + Q"):whatever()\n')

    assert result.error is None


def test_a_reader_that_prints_garbage_is_an_error(paths, tmp_path, monkeypatch):
    fake = tmp_path / "fake.lua"
    fake.write_text('io.write("}{")\n')
    monkeypatch.setattr(reader, "READER", fake)

    result = read_config(paths)

    assert "not JSON" in result.error


def test_a_dispatcher_with_a_strange_dsp_path_is_not_reproducible():
    from hyprkbm.reader import reproducible
    assert reproducible({"dsp": "window.close", "args": []}, {})
    assert not reproducible({"dsp": "window close", "args": []}, {})
    assert not reproducible({"dsp": "a()", "args": []}, {})
