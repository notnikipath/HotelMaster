from shared.hotelmaster_common import build_rate_breakdown, season_factor


def test_build_rate_breakdown_returns_positive_total() -> None:
    rate = build_rate_breakdown(
        base_price=5000,
        check_in_date=__import__("datetime").date(2026, 7, 10),
        check_out_date=__import__("datetime").date(2026, 7, 13),
        occupancy_ratio=0.82,
    )
    assert rate.nights == 3
    assert rate.nightly_rate > 0
    assert rate.total_amount > rate.base_price


def test_season_factor_for_winter_and_summer() -> None:
    assert season_factor(__import__("datetime").date(2026, 1, 15)) < 1
    assert season_factor(__import__("datetime").date(2026, 7, 15)) > 1
