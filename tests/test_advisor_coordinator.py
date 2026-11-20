"""
Unit tests for Advisor Coordinator
Tests unified 120-word plain-language synthesis, 3-component advisory structure,
multilingual output (Hindi/Punjabi), and data gaps/partial advisory handling.
"""

import asyncio
import pytest
from board.models import EntryType, DataFreshness
from agents.advisor_coordinator import AdvisorCoordinatorRunner


def test_coordinator_full_advisory_synthesis(mock_board):
    """Test synthesis of full advisory adhering to <= 120 words and 3 components."""
    session_id = "test_coord_full_session"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "location": "Karnal", "language": "en"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Weather Agent",
        type=EntryType.WEATHER.value,
        payload={"seven_day_rain_mm": 0.0, "summary": "Dry weather."},
        confidence=0.92,
        data_freshness=DataFreshness.LIVE.value,
        sources=["open_meteo"],
    )
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Crop Agent",
        type=EntryType.CROP_ACTION.value,
        payload={"recommended_action": "irrigate", "reasoning": "Crown root stage needs moisture."},
        confidence=0.90,
        data_freshness=DataFreshness.LIVE.value,
        sources=["ICAR"],
    )
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Market Agent",
        type=EntryType.MARKET.value,
        payload={"suggestion": "SELL", "current_modal_price": 2475.0, "msp": 2275.0, "mandi_used": "Karnal", "is_data_available": True},
        confidence=0.90,
        data_freshness=DataFreshness.LIVE.value,
        sources=["agmarknet"],
    )
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Scheme Agent",
        type=EntryType.SCHEME.value,
        payload={"scheme_name": "PMFBY", "eligibility": "All farmers growing notified crops."},
        confidence=0.92,
        data_freshness=DataFreshness.LIVE.value,
        sources=["pmfby.gov.in"],
    )

    runner = AdvisorCoordinatorRunner(board=mock_board)
    final_advisory = asyncio.run(runner.run(session_id=session_id))

    # Word count constraint: <= 120 words
    assert final_advisory.word_count <= 120
    assert "irrigate" in final_advisory.field_action.lower()
    assert "SELL" in final_advisory.market_suggestion
    assert "PMFBY" in final_advisory.government_scheme
    assert final_advisory.is_partial is False


def test_coordinator_partial_advisory_when_agent_fails(mock_board):
    """Test coordinator handles agent failure by marking partial advisory and logging data gaps."""
    session_id = "test_coord_partial_session"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "location": "Karnal", "language": "en"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )
    # Simulate failed Market Agent
    mock_board.post_entry(
        session_id=session_id,
        agent_name="Market Agent",
        type=EntryType.FAILED.value,
        payload={"error": "Agmarknet API timeout"},
        confidence=0.0,
        data_freshness=DataFreshness.UNAVAILABLE.value,
        sources=["market"],
        status="FAILED",
    )

    runner = AdvisorCoordinatorRunner(board=mock_board)
    final_advisory = asyncio.run(runner.run(session_id=session_id))

    assert final_advisory.word_count <= 120
    assert final_advisory.is_partial is True
    assert len(final_advisory.data_gaps) > 0

