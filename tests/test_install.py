"""install.sh, run for real against a throwaway HOME with a stub systemctl
first on PATH, so nothing reaches the user's own home or systemd."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIT = "hyprkbm-watch.service"

SYSTEMCTL = r'''#!%(python)s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
state = json.load(open(os.path.join(here, "systemd.json")))
with open(os.path.join(here, "calls.log"), "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\n")
args = [a for a in sys.argv[1:] if a not in ("--user", "--quiet", "-q")]
if args[0] == "is-active":
    sys.exit(0 if state["session"] else 3)
if args[0] == "is-enabled":
    print(state["enabled"])
    sys.exit(0 if state["enabled"] == "enabled" else 1)
sys.exit(0)
'''


def links(home):
    return {
        home / ".local/bin/hyprkbm": "bin/hyprkbm",
        home / ".local/bin/hyprkbm-apply": "bin/hyprkbm-apply",
        home / ".local/bin/hyprkbm-watch": "bin/hyprkbm-watch",
        home / ".config/systemd/user" / UNIT: "systemd/" + UNIT,
    }


def run(tmp_path, *args, session=True, enabled="disabled"):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    stubs = tmp_path / "stubs"
    stubs.mkdir(exist_ok=True)
    script = stubs / "systemctl"
    script.write_text(SYSTEMCTL % {"python": sys.executable})
    script.chmod(0o755)
    (stubs / "systemd.json").write_text(json.dumps({"session": session, "enabled": enabled}))
    env = {"PATH": "%s:%s:/usr/bin:/bin" % (stubs, home / ".local/bin"), "HOME": str(home)}
    res = subprocess.run(["bash", str(ROOT / "install.sh"), *args],
                         capture_output=True, text=True, env=env)
    log = stubs / "calls.log"
    calls = [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return home, res, calls


def test_install_links_everything_and_enables_the_watcher(tmp_path):
    home, res, calls = run(tmp_path)

    assert res.returncode == 0, res.stderr
    for dst, src in links(home).items():
        assert dst.is_symlink(), dst
        assert Path(os.readlink(dst)) == ROOT / src
    assert ["--user", "enable", "--now", UNIT] in calls


def test_install_is_idempotent(tmp_path):
    run(tmp_path)
    home, res, _ = run(tmp_path)

    assert res.returncode == 0
    assert "ok" in res.stdout


def test_a_real_file_in_the_way_is_left_alone(tmp_path):
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/hyprkbm").write_text("mine")

    home, res, _ = run(tmp_path)

    assert res.returncode == 1
    assert (home / ".local/bin/hyprkbm").read_text() == "mine"
    assert "skipped" in res.stderr


def test_a_masked_watcher_is_an_error_because_hyprkbm_needs_it(tmp_path):
    home, res, calls = run(tmp_path, enabled="masked")

    assert res.returncode == 1
    assert "masked" in res.stderr
    assert ["--user", "enable", "--now", UNIT] not in calls


def test_without_a_systemd_session_it_explains_the_fallback(tmp_path):
    home, res, calls = run(tmp_path, session=False)

    assert res.returncode == 0
    assert 'hl.exec_cmd("hyprkbm-watch")' in res.stdout


def test_uninstall_removes_only_its_own_links(tmp_path):
    home, _, _ = run(tmp_path)
    keep = home / ".config/hyprkbm/keybinds.json"
    keep.parent.mkdir(parents=True)
    keep.write_text("{}")

    home, res, calls = run(tmp_path, "--uninstall")

    assert res.returncode == 0
    assert not any(dst.exists() or dst.is_symlink() for dst in links(home))
    assert keep.exists()
    assert ["--user", "disable", "--now", UNIT] in calls
