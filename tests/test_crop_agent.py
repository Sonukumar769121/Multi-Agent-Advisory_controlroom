"""
Unit tests for Crop Agent
Tests crop guidance RAG retrieval, agronomic decision logic under wet vs dry forecasts,
and CROP_ACTION board entry posting.
"""

import asyncio
from board.models import EntryType, DataFreshness
from agents.crop_agent import CropAgentRunner


def test_crop_agent_hold_irrigation_on_rain(mock_board, mock_chroma_client):
    """Test Crop Agent recommends 'hold_irrigation' when weather forecast indicates heavy rain."""
    session_id = "test_crop_wet_session"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "stage": "vegetative", "location": "Karnal"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )

    # Rainy forecast (32mm)
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Weather Agent",
        type=EntryType.WEATHER.value,
        payload={"seven_day_rain_mm": 32.0, "temp_max_c": 24.0, "temp_min_c": 14.0},
        confidence=0.92,
        data_freshness=DataFreshness.LIVE.value,
        sources=["open_meteo"],
    )

    runner = CropAgentRunner(board=mock_board)
    entry = asyncio.run(runner.run(session_id=session_id))

    assert entry.type == EntryType.CROP_ACTION.value
    assert entry.payload["recommended_action"] == "hold_irrigation"
    assert "32.0 mm" in entry.payload["reasoning"] or "rain" in entry.payload["reasoning"].lower()
    assert len(entry.payload["citations"]) > 0


def test_crop_agent_irrigate_on_dry(mock_board, mock_chroma_client):
    """Test Crop Agent recommends 'irrigate' at CRI/vegetative stage when dry weather is expected."""
    session_id = "test_crop_dry_session"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "stage": "vegetative", "location": "Karnal"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )

    # Dry forecast (0.0mm)
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Weather Agent",
        type=EntryType.WEATHER.value,
        payload={"seven_day_rain_mm": 0.0, "temp_max_c": 28.0, "temp_min_c": 13.0},
        confidence=0.92,
        data_freshness=DataFreshness.LIVE.value,
        sources=["open_meteo"],
    )

    runner = CropAgentRunner(board=mock_board)
    entry = asyncio.run(runner.run(session_id=session_id))

    assert entry.type == EntryType.CROP_ACTION.value
    assert entry.payload["recommended_action"] == "irrigate"
    assert "vegetative" in entry.payload["reasoning"].lower() or "irrigate" in entry.payload["reasoning"].lower()
