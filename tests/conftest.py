import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from hyprkbm.paths import Paths  # noqa: E402


@pytest.fixture(autouse=True)
def no_live_compositor(monkeypatch):
    """hyprctl finds the compositor through this variable, so a test that
    forgets the `stubs` fixture still cannot reach the real session."""
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)


@pytest.fixture
def home_env(tmp_path):
    """An environment whose HOME is a throwaway directory with an empty
    hyprland.lua, so nothing under test can reach the real one."""
    home = tmp_path / "home"
    (home / ".config" / "hypr").mkdir(parents=True)
    (home / ".config" / "hypr" / "hyprland.lua").write_text("")
    return {"HOME": str(home), "XDG_RUNTIME_DIR": str(tmp_path / "run")}


@pytest.fixture
def paths(home_env):
    return Paths.from_env(home_env)


import json  # noqa: E402

HYPRCTL = r'''#!%(python)s
"""Stands in for hyprctl: logs each call, answers from responses.json."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(["hyprctl"] + args) + "\n")
path = os.path.join(here, "responses.json")
responses = json.load(open(path)) if os.path.exists(path) else {}
if args[:1] == ["eval"]:
    kind = "dry" if "loadfile" in args[1] else "load" if "dofile" in args[1] else "eval"
else:
    kind = args[0] if args else ""
queue = responses.get(kind, [])
answer = queue.pop(0) if queue else "ok"
json.dump(responses, open(path, "w"))
print(answer)
sys.exit(7 if answer.startswith("error") else 0)
'''

LOGGER = r'''#!%(python)s
"""Stands in for a command whose only effect matters to the test: being run."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\n")
'''


class Stubs:
    def __init__(self, root):
        self.root = root

    def respond(self, **queues):
        (self.root / "responses.json").write_text(json.dumps(queues))

    def calls(self):
        log = self.root / "calls.log"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    def hyprctl_kinds(self):
        kinds = []
        for call in self.calls():
            if call[0] != "hyprctl":
                continue
            if call[1] == "eval":
                kinds.append("dry" if "loadfile" in call[2] else "load")
            else:
                kinds.append(call[1])
        return kinds


@pytest.fixture
def stubs(tmp_path, monkeypatch):
    root = tmp_path / "stubs"
    root.mkdir()
    for name, body in (("hyprctl", HYPRCTL), ("notify-send", LOGGER), ("systemctl", LOGGER),
                       ("qs", LOGGER)):
        script = root / name
        script.write_text(body % {"python": sys.executable})
        script.chmod(0o755)
    monkeypatch.setenv("PATH", "%s:/usr/bin:/bin" % root)
    return Stubs(root)
