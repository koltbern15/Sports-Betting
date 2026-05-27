import pytest

from ingestion.divisions import DIVISIONS, division_of, same_division
from ingestion.stadiums import is_dome
from ingestion.team_codes import NFLVERSE_TEAM_CODES, code_to_canonical
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


def test_is_dome_known_dome():
    # State Farm Stadium (Arizona) is a retractable-roof dome
    assert is_dome("State Farm Stadium") is True
    # Mercedes-Benz Superdome (New Orleans) is a fixed dome
    assert is_dome("Mercedes-Benz Superdome") is True
    # Caesars Superdome — same building, post-2021 rename
    assert is_dome("Caesars Superdome") is True


def test_is_dome_known_outdoor():
    assert is_dome("Lambeau Field") is False
    assert is_dome("Heinz Field") is False
    assert is_dome("Arrowhead Stadium") is False


def test_is_dome_unknown_returns_false():
    # Unknown stadium → conservative default = outdoor (False)
    assert is_dome("Some Made-Up Stadium") is False


def test_team_codes_has_all_32_teams():
    assert len(NFLVERSE_TEAM_CODES) == 32


def test_code_to_canonical_modern():
    assert code_to_canonical("KC") == "Kansas City Chiefs"
    assert code_to_canonical("LV") == "Las Vegas Raiders"
    assert code_to_canonical("WAS") == "Washington Commanders"
    assert code_to_canonical("LA") == "Los Angeles Rams"
    assert code_to_canonical("LAC") == "Los Angeles Chargers"


def test_code_to_canonical_unknown_raises():
    with pytest.raises(KeyError):
        code_to_canonical("ZZZ")


def test_all_codes_resolve_to_canonical_set():
    from ingestion.team_names import CANONICAL_TEAMS
    for code in NFLVERSE_TEAM_CODES:
        assert code_to_canonical(code) in CANONICAL_TEAMS
