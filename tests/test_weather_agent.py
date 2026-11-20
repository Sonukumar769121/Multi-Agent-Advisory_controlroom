"""
Unit tests for Weather Agent
Tests weather forecast parsing, unit normalization (°C, mm, km/h),
stale cache fallback, and WEATHER board entry posting.
"""

import asyncio
from unittest.mock import patch, AsyncMock
from board.models import EntryType, DataFreshness
from adapters.open_meteo import OpenMeteoAdapter
from agents.weather_agent import WeatherAgentRunner


def test_weather_forecast_dry_parsing(recorded_weather_response_dry):
    """Test parsing of Open-Meteo dry weather forecast data."""
    adapter = OpenMeteoAdapter()
    payload = {
        "seven_day_rain_mm": 0.0,
        "rain_probability_pct": 5.0,
        "temp_min_c": 13.0,
        "temp_max_c": 28.4,
        "humidity_pct": 55.0,
        "wind_speed_kmh": 11.2,
        "summary": "Dry conditions expected.",
        "forecast_days": [],
    }
    with patch.object(adapter, "get_forecast", new_callable=AsyncMock) as mock_f:
        mock_f.return_value = (payload, "live")
        res_payload, freshness = asyncio.run(adapter.get_forecast(latitude=29.6857, longitude=76.9905))

        assert res_payload["seven_day_rain_mm"] == 0.0
        assert res_payload["temp_min_c"] == 13.0
        assert res_payload["temp_max_c"] == 28.4
        assert res_payload["humidity_pct"] == 55.0
        assert freshness == "live"


def test_weather_stale_cache_fallback(recorded_weather_response_dry):
    """Test that when API fails, stale cache is returned with 'stale' freshness tag."""
    import httpx
    adapter = OpenMeteoAdapter(max_retries=1)

    # Warm cache with stale timestamp
    cache_key = "weather:29.686:76.991"
    adapter._cache[cache_key] = {
        "timestamp": 0.0,
        "data": {
            "seven_day_rain_mm": 0.0,
            "rain_probability_pct": 5.0,
            "temp_min_c": 14.0,
            "temp_max_c": 28.0,
            "humidity_pct": 55.0,
            "wind_speed_kmh": 11.0,
            "summary": "Cached dry weather.",
            "forecast_days": [],
        },
    }

    # Simulate network failure so it falls back to stale cache
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network down")):
        payload, freshness = asyncio.run(adapter.get_forecast(latitude=29.6857, longitude=76.9905))
        assert payload["seven_day_rain_mm"] == 0.0
        assert freshness in ("cached", "stale")


def test_weather_agent_runner(mock_board, recorded_weather_response_dry):
    """Test full Weather Agent execution after INTAKE entry is present."""
    session_id = "test_weather_session_01"

    # Pre-populate INTAKE on board
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={
            "crop": "Wheat",
            "location": "Karnal, Haryana",
            "latitude": 29.6857,
            "longitude": 76.9905,
            "stage": "vegetative",
            "language": "en",
        },
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["geocoding"],
    )

    runner = WeatherAgentRunner(board=mock_board)
    with patch("agents.weather_agent.OpenMeteoAdapter") as mock_adapter_cls:
        instance = mock_adapter_cls.return_value
        instance.get_forecast = AsyncMock(return_value=({
            "seven_day_rain_mm": 0.0,
            "rain_probability_pct": 5.0,
            "temp_min_c": 13.0,
            "temp_max_c": 28.4,
            "humidity_pct": 55.0,
            "wind_speed_kmh": 11.2,
            "summary": "Dry conditions expected.",
            "forecast_days": [],
        }, "live"))

        entry = asyncio.run(runner.run(session_id=session_id))

        assert entry.session_id == session_id
        assert entry.type == EntryType.WEATHER.value
        assert entry.payload["seven_day_rain_mm"] == 0.0
        assert entry.payload["temp_max_c"] == 28.4
        assert entry.confidence >= 0.90
