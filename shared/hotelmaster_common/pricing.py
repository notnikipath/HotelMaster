from __future__ import annotations

from datetime import UTC, date, datetime

from .schemas import RateBreakdown


def season_factor(day: date) -> float:
    if day.month in {6, 7, 8, 12}:
        return 1.25
    if day.month in {1, 2, 11}:
        return 0.92
    return 1.05


def _occupancy_factor(occupancy_ratio: float) -> float:
    occupancy = min(max(occupancy_ratio, 0.0), 1.0)
    if occupancy >= 0.9:
        return 1.3
    if occupancy >= 0.75:
        return 1.18
    if occupancy >= 0.55:
        return 1.06
    if occupancy <= 0.25:
        return 0.88
    return 1.0


def _lead_time_factor(check_in_date: date) -> float:
    days_left = (check_in_date - datetime.now(UTC).date()).days
    if days_left <= 1:
        return 1.2
    if days_left <= 3:
        return 1.1
    if days_left >= 25:
        return 0.93
    return 1.0


def build_rate_breakdown(
    base_price: float,
    check_in_date: date,
    check_out_date: date,
    occupancy_ratio: float,
) -> RateBreakdown:
    nights = max(1, (check_out_date - check_in_date).days)
    season = season_factor(check_in_date)
    occupancy = _occupancy_factor(occupancy_ratio)
    lead_time = _lead_time_factor(check_in_date)
    nightly = round(base_price * season * occupancy * lead_time, 2)
    total = round(nightly * nights, 2)
    return RateBreakdown(
        base_price=round(base_price, 2),
        season_factor=season,
        occupancy_factor=occupancy,
        lead_time_factor=lead_time,
        nightly_rate=nightly,
        nights=nights,
        total_amount=total,
    )
