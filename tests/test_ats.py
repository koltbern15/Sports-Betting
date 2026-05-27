import pytest

from engine.ats import bucket_spread


@pytest.mark.parametrize(
    "spread, expected",
    [
        (-20.0, "home_fav_14.5+"),
        (-14.5, "home_fav_14.5+"),
        (-14.0, "home_fav_10.5_14"),
        (-10.5, "home_fav_10.5_14"),
        (-10.0, "home_fav_7.5_10"),
        (-7.5, "home_fav_7.5_10"),
        (-7.0, "home_fav_3.5_7"),
        (-3.5, "home_fav_3.5_7"),
        (-3.0, "home_fav_1_3"),
        (-1.0, "home_fav_1_3"),
        (-0.5, "pickem"),
        (0.0, "pickem"),
        (0.5, "pickem"),
        (1.0, "home_dog_1_3"),
        (3.0, "home_dog_1_3"),
        (3.5, "home_dog_3.5_7"),
        (7.0, "home_dog_3.5_7"),
        (7.5, "home_dog_7.5_10"),
        (10.0, "home_dog_7.5_10"),
        (10.5, "home_dog_10.5_14"),
        (14.0, "home_dog_10.5_14"),
        (14.5, "home_dog_14.5+"),
        (20.0, "home_dog_14.5+"),
    ],
)
def test_bucket_spread_known_values(spread, expected):
    assert bucket_spread(spread) == expected


def test_bucket_spread_none_returns_none():
    assert bucket_spread(None) is None
