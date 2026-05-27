import pytest

from ingestion.divisions import DIVISIONS, division_of, same_division
from ingestion.team_names import CANONICAL_TEAMS, canonicalize_team_name


def test_divisions_has_32_teams():
    assert len(DIVISIONS) == 32


def test_divisions_has_8_divisions_with_4_teams_each():
    counts: dict[tuple[str, str], int] = {}
    for _team, (conf, div) in DIVISIONS.items():
        counts[(conf, div)] = counts.get((conf, div), 0) + 1
    assert len(counts) == 8
    assert all(c == 4 for c in counts.values())


def test_division_of_known_teams():
    assert division_of("Kansas City Chiefs") == ("AFC", "West")
    assert division_of("Dallas Cowboys") == ("NFC", "East")
    assert division_of("Green Bay Packers") == ("NFC", "North")


def test_same_division_true():
    assert same_division("Kansas City Chiefs", "Denver Broncos") is True


def test_same_division_false_same_conference():
    assert same_division("Kansas City Chiefs", "Buffalo Bills") is False


def test_same_division_false_different_conference():
    assert same_division("Kansas City Chiefs", "Dallas Cowboys") is False


def test_canonicalize_modern_name_passthrough():
    assert canonicalize_team_name("Kansas City Chiefs") == "Kansas City Chiefs"


def test_canonicalize_st_louis_rams():
    assert canonicalize_team_name("St. Louis Rams") == "Los Angeles Rams"


def test_canonicalize_san_diego_chargers():
    assert canonicalize_team_name("San Diego Chargers") == "Los Angeles Chargers"


def test_canonicalize_oakland_raiders():
    assert canonicalize_team_name("Oakland Raiders") == "Las Vegas Raiders"


def test_canonicalize_washington_redskins():
    assert canonicalize_team_name("Washington Redskins") == "Washington Commanders"


def test_canonicalize_washington_football_team():
    assert canonicalize_team_name("Washington Football Team") == "Washington Commanders"


def test_canonical_teams_match_divisions():
    from ingestion.divisions import DIVISIONS

    assert CANONICAL_TEAMS == set(DIVISIONS.keys())


def test_canonicalize_unknown_team_raises():
    with pytest.raises(KeyError):
        canonicalize_team_name("Cleveland Browns 1971 Edition")
