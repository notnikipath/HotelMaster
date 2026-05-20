from shared.hotelmaster_common import forecast_occupancy, mape


def test_forecast_occupancy_has_expected_horizon() -> None:
    forecast = forecast_occupancy([0.6, 0.62, 0.65, 0.68], horizon_days=5)
    assert len(forecast) == 5
    assert all(0 <= item <= 1 for item in forecast)


def test_mape_computes_value() -> None:
    value = mape([0.7, 0.74], [0.69, 0.73])
    assert value > 0
    assert value < 10
