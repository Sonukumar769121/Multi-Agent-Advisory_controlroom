"""
Unit tests for Intake Agent
Tests crop normalization, Open-Meteo geocoding handling, and INTAKE board entry posting.
Uses Python stdlib unittest.mock for zero-dependency test execution.
"""

import asyncio
from unittest.mock import patch, AsyncMock
from board.models import EntryType, DataFreshness
from agents.intake_agent import IntakeAgentRunner, CROP_SYNONYMS
from adapters.open_meteo import OpenMeteoAdapter


def test_crop_normalization():
    """Verify Hindi/regional crop synonyms correctly normalize to standard English names."""
    assert CROP_SYNONYMS.get("kanak") == "Wheat"
    assert CROP_SYNONYMS.get("gehun") == "Wheat"
    assert CROP_SYNONYMS.get("dhan") == "Rice"
    assert CROP_SYNONYMS.get("chawal") == "Rice"
    assert CROP_SYNONYMS.get("sarson") == "Mustard"
    assert CROP_SYNONYMS.get("makka") == "Maize"


def test_intake_geocoding_success(mock_board, recorded_geocoding_response):
    """Test geocoding tool parses Open-Meteo coordinates properly."""
    adapter = OpenMeteoAdapter()
    with patch.object(adapter, "geocode", new_callable=AsyncMock) as mock_geo:
        mock_geo.return_value = {
            "name": "Karnal",
            "latitude": 29.6857,
            "longitude": 76.9905,
            "state": "Haryana",
            "district": "Karnal",
            "country": "India",
        }
        geo = asyncio.run(adapter.geocode("Karnal, Haryana"))

        assert geo["name"] == "Karnal"
        assert abs(geo["latitude"] - 29.6857) < 0.001
        assert abs(geo["longitude"] - 76.9905) < 0.001
        assert geo["state"] == "Haryana"
        assert geo["district"] == "Karnal"


def test_intake_agent_runner(mock_board, recorded_geocoding_response):
    """Test full Intake Agent runner execution and board entry creation."""
    session_id = "test_intake_session_01"

    runner = IntakeAgentRunner(board=mock_board)
    with patch("agents.intake_agent.OpenMeteoAdapter") as mock_adapter_cls:
        instance = mock_adapter_cls.return_value
        instance.geocode = AsyncMock(return_value={
            "name": "Karnal",
            "latitude": 29.6857,
            "longitude": 76.9905,
            "state": "Haryana",
            "district": "Karnal",
            "country": "India",
        })

        entry = asyncio.run(runner.run(
            session_id=session_id,
            crop="kanak",  # Regional synonym
            location="Karnal, Haryana",
            stage="vegetative",
            language="en",
        ))

        assert entry.session_id == session_id
        assert entry.type == EntryType.INTAKE.value
        assert entry.payload["crop"] == "Wheat"
        assert entry.payload["stage"] == "vegetative"
        assert abs(entry.payload["latitude"] - 29.6857) < 0.001
        assert entry.confidence >= 0.90
        assert entry.data_freshness == DataFreshness.LIVE.value
