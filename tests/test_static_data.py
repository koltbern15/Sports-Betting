from ingestion.divisions import DIVISIONS, division_of, same_division


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
