import textwrap

from hyprkbm.catalogue import load_catalogue
from hyprkbm.export import export_markdown
from hyprkbm.model import merge
from hyprkbm.reader import read_config

CAT = load_catalogue()


def test_export_groups_by_submap_then_modifiers(paths):
    paths.entry.write_text(textwrap.dedent("""\
        hl.bind("SUPER + SHIFT + Q", hl.dsp.exit(), { description = "Leave | quit" })
        hl.bind("SUPER + Q", hl.dsp.exec_cmd("kitty"), { description = "Terminal" })
        hl.bind("Print", hl.dsp.exec_cmd("grim"))
        hl.bind("SUPER + C", hl.dsp.window.close())
        hl.define_submap("resize", "escape", function()
            hl.bind("right", hl.dsp.window.resize())
        end)
    """))
    model = {"version": 1, "submaps": [], "unbinds": [],
             "binds": [{"id": "b1", "keys": "SUPER + B", "description": "Browser",
                        "action": {"kind": "exec_cmd", "args": {"cmd": "firefox"}}}]}

    text = export_markdown(merge(model, read_config(paths), CAT), CAT)

    assert text == textwrap.dedent("""\
        # Keybinds

        ## Global

        ### No modifier

        | Key | Description | Action |
        |---|---|---|
        | Print |  | Run a command: grim |

        ### SUPER

        | Key | Description | Action |
        |---|---|---|
        | B | Browser | Run a command: firefox |
        | C |  | Close window |
        | Q | Terminal | Run a command: kitty |

        ### SUPER + SHIFT

        | Key | Description | Action |
        |---|---|---|
        | Q | Leave \\| quit | Exit Hyprland |

        ## resize

        ### No modifier

        | Key | Description | Action |
        |---|---|---|
        | right |  | Resize window (mouse) |
        """)
