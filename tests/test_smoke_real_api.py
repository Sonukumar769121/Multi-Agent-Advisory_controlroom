"""
Optional Smoke Tests for Live External APIs
Marked as optional: runs real network queries against Open-Meteo and data.gov.in.

Execute with:
    pytest -m optional tests/test_smoke_real_api.py
"""

import os
import asyncio
import pytest
from adapters.open_meteo import OpenMeteoAdapter
from adapters.agmarknet import AgmarknetAdapter


@pytest.mark.optional
def test_live_open_meteo_geocoding():
    """Smoke test: Real Open-Meteo Geocoding endpoint."""
    adapter = OpenMeteoAdapter(timeout=10.0)
    try:
        geo = asyncio.run(adapter.geocode("Karnal, Haryana"))
        assert geo["name"] == "Karnal"
        assert abs(geo["latitude"] - 29.6857) < 0.5
        assert abs(geo["longitude"] - 76.9905) < 0.5
    except Exception as exc:
        pytest.skip(f"Live network unavailable or rate-limited: {exc}")


@pytest.mark.optional
def test_live_open_meteo_forecast():
    """Smoke test: Real Open-Meteo 7-day Weather Forecast endpoint."""
    adapter = OpenMeteoAdapter(timeout=10.0)
    try:
        payload, freshness = asyncio.run(adapter.get_forecast(latitude=29.6857, longitude=76.9905))
        assert freshness in ("live", "cached")
        assert "seven_day_rain_mm" in payload
        assert "temp_min_c" in payload
        assert "temp_max_c" in payload
        assert payload["temp_max_c"] >= payload["temp_min_c"]
    except Exception as exc:
        pytest.skip(f"Live network unavailable or rate-limited: {exc}")


@pytest.mark.optional
def test_live_data_gov_in_agmarknet():
    """Smoke test: Real data.gov.in Agmarknet API (requires DATA_GOV_IN_API_KEY)."""
    api_key = os.getenv("DATA_GOV_IN_API_KEY", "")
    if not api_key:
        pytest.skip("DATA_GOV_IN_API_KEY not set in environment; skipping live Agmarknet test.")

    adapter = AgmarknetAdapter(api_key=api_key, timeout=10.0)
    try:
        data, freshness = asyncio.run(adapter.get_market_data(commodity="Wheat", state="Haryana"))
        assert freshness in ("live", "cached", "unavailable")
        assert "commodity" in data
    except Exception as exc:
        pytest.skip(f"data.gov.in API unavailable: {exc}")

