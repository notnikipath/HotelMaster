from __future__ import annotations


def forecast_occupancy(history: list[float], horizon_days: int = 7) -> list[float]:
    if not history:
        return [0.5 for _ in range(horizon_days)]
    normalized = [min(max(value, 0.0), 1.0) for value in history]
    window = normalized[-7:] if len(normalized) >= 7 else normalized
    base = sum(window) / len(window)
    trend = 0.0
    if len(window) >= 2:
        trend = (window[-1] - window[0]) / max(len(window) - 1, 1)
    forecast: list[float] = []
    for day in range(1, horizon_days + 1):
        projected = base + trend * day * 0.45
        forecast.append(round(min(max(projected, 0.0), 1.0), 3))
    return forecast


def mape(predicted: list[float], actual: list[float]) -> float:
    if not predicted or not actual or len(predicted) != len(actual):
        return 0.0
    errors = []
    for p, a in zip(predicted, actual, strict=True):
        if a <= 0:
            continue
        errors.append(abs((a - p) / a))
    if not errors:
        return 0.0
    return round(sum(errors) / len(errors) * 100, 2)
