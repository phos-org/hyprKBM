import os


def test_tests_never_see_a_live_hyprland_instance():
    assert "HYPRLAND_INSTANCE_SIGNATURE" not in os.environ
