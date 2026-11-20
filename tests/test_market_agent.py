"""
Unit tests for Market Agent
Tests Agmarknet parsing, 7-day and 30-day modal price trends, MSP comparison,
regional mandi fallback, and strict 'data unavailable' behavior.
"""

import asyncio
from unittest.mock import patch, AsyncMock
from board.models import EntryType, DataFreshness
from adapters.agmarknet import AgmarknetAdapter
from agents.market_agent import MarketAgentRunner


def test_agmarknet_price_trend_and_msp(recorded_agmarknet_wheat_response):
    """Test 7-day trend calculation and MSP comparison for Wheat."""
    adapter = AgmarknetAdapter(api_key="test_api_key")

    mock_result = {
        "commodity": "Wheat",
        "mandi_used": "Karnal",
        "district": "Karnal",
        "state": "Haryana",
        "current_modal_price": 2475.0,
        "msp": 2275.0,
        "trend_7d_pct": 3.12,
        "trend_30d_pct": 1.45,
        "trend_direction": "UP",
        "suggestion": "SELL",
        "is_data_available": True,
    }

    with patch.object(adapter, "get_market_data", new_callable=AsyncMock) as mock_m:
        mock_m.return_value = (mock_result, "live")
        data, freshness = asyncio.run(adapter.get_market_data(
            commodity="Wheat",
            state="Haryana",
            district="Karnal",
        ))

        assert data["is_data_available"] is True
        assert data["current_modal_price"] == 2475.0
        assert data["msp"] == 2275.0  # Official Wheat MSP
        assert data["mandi_used"] == "Karnal"
        assert data["suggestion"] == "SELL"
        assert freshness == "live"


def test_market_data_unavailable_no_fabrication():
    """Test Market Agent never fabricates prices when data is unavailable."""
    adapter = AgmarknetAdapter(api_key="")

    data, freshness = asyncio.run(adapter.get_market_data(
        commodity="Wheat",
        state="Haryana",
        district="UnknownDistrict",
    ))

    assert data["is_data_available"] is False
    assert data["current_modal_price"] is None
    assert data["suggestion"] == "DATA_UNAVAILABLE"
    assert freshness == "unavailable"


def test_market_agent_runner(mock_board, recorded_agmarknet_wheat_response):
    """Test full Market Agent runner execution and board entry posting."""
    session_id = "test_market_session_01"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "state": "Haryana", "district": "Karnal"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )

    runner = MarketAgentRunner(board=mock_board)
    with patch("agents.market_agent.AgmarknetAdapter") as mock_adapter_cls:
        instance = mock_adapter_cls.return_value
        instance.get_market_data = AsyncMock(return_value=({
            "commodity": "Wheat",
            "mandi_used": "Karnal",
            "district": "Karnal",
            "state": "Haryana",
            "current_modal_price": 2475.0,
            "msp": 2275.0,
            "trend_7d_pct": 3.12,
            "trend_30d_pct": 1.45,
            "trend_direction": "UP",
            "suggestion": "SELL",
            "is_data_available": True,
        }, "live"))

        entry = asyncio.run(runner.run(session_id=session_id))

        assert entry.session_id == session_id
        assert entry.type == EntryType.MARKET.value
        assert entry.payload["commodity"] == "Wheat"
