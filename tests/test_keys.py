import json
from pathlib import Path

import pytest

from hyprkbm.keys import KeyParseError, parse

TABLE = json.loads((Path(__file__).parent / "fixtures" / "keys.json").read_text())


@pytest.mark.parametrize("keys,expected", TABLE["same"])
def test_spellings_of_one_combo_share_an_id(keys, expected):
    assert parse(keys).id == expected


@pytest.mark.parametrize("keys,expected", TABLE["display"])
def test_display_uses_canonical_modifiers_and_the_key_as_written(keys, expected):
    assert parse(keys).display == expected


@pytest.mark.parametrize("keys", TABLE["invalid"])
def test_malformed_combos_are_rejected(keys):
    with pytest.raises(KeyParseError):
        parse(keys)


def test_keys_must_be_text():
    with pytest.raises(KeyParseError):
        parse(42)
