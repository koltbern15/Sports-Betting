import math

import pytest

from engine.ats import BucketMetrics, bucket_spread, compute_bucket_metrics


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


def test_metrics_basic_case():
    # 60 covers, 40 losses, 0 pushes → win_rate = 0.60
    m = compute_bucket_metrics(bucket="home_fav_3.5_7", covers=60, losses=40, pushes=0)
    assert isinstance(m, BucketMetrics)
    assert m.bucket == "home_fav_3.5_7"
    assert m.n == 100
    assert m.wins == 60
    assert m.losses == 40
    assert m.pushes == 0
    assert math.isclose(m.win_rate, 0.6)
    assert math.isclose(m.push_rate, 0.0)
    assert math.isclose(m.roi_neg110, (60 * 10 / 11 - 40) / 100, abs_tol=1e-12)
    assert m.insufficient_sample is False
    # P-value vs 0.5238: 60/100 → significant in the right direction → small p
    assert m.p_value < 0.10


def test_metrics_with_pushes():
    m = compute_bucket_metrics(bucket="pickem", covers=10, losses=10, pushes=5)
    assert m.n == 25
    # win_rate excludes pushes from denominator
    assert math.isclose(m.win_rate, 0.5)
    # push_rate uses total
    assert math.isclose(m.push_rate, 0.2)


def test_metrics_insufficient_sample_flag_below_50():
    m = compute_bucket_metrics(bucket="home_fav_14.5+", covers=20, losses=20, pushes=0)
    assert m.insufficient_sample is True
    m2 = compute_bucket_metrics(bucket="home_fav_14.5+", covers=30, losses=20, pushes=0)
    # 30+20 = 50, threshold is wins+losses < 50 → exactly 50 is NOT insufficient
    assert m2.insufficient_sample is False


def test_metrics_zero_data():
    m = compute_bucket_metrics(bucket="pickem", covers=0, losses=0, pushes=0)
    assert m.n == 0
    assert m.win_rate == 0.0
    assert m.push_rate == 0.0
    assert m.p_value == 1.0
    assert m.ci_low == 0.0
    assert m.ci_high == 1.0
    assert m.insufficient_sample is True
