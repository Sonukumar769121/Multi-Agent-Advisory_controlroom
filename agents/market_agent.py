"""
Market Agent Module
Microsoft Agent Framework (package: agent-framework v1.25.0)

Role:
- Reads INTAKE entry from Advisory Board.
- Queries Agmarknet dataset via data.gov.in API (Resource 9ef84268-d588-465a-a308-a864a43d0070).
- Computes 7-day and 30-day modal price trends in Rs per quintal and compares with MSP.
- Falls back to nearest mandi in the state if none found for the district.
- Posts MARKET entry with price, mandi used, trend, SELL/HOLD suggestion, and data_freshness.
- DATA INTEGRITY RULE: If no data, post 'data unavailable' and NEVER invent prices.

Verified API:
- agent_framework.Agent, agent_framework.tool
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/_agent.py
  python/packages/core/agent_framework/_tools.py
"""

import json
from typing import Dict, Any, Optional
from agent_framework import Agent, tool  # [VERIFIED: agent-framework v1.25.0]

from config import get_model_client, DATA_GOV_IN_API_KEY
from board.advisory_board import get_advisory_board, AdvisoryBoard
from board.models import AdvisoryBoardEntry, EntryType, DataFreshness
from adapters.agmarknet import AgmarknetAdapter

MARKET_AGENT_INSTRUCTIONS = """
You are the Market Agent in the Agricultural Advisory Control Room.
Your role:
1. Read the INTAKE entry from the Advisory Board using `get_board_intake`.
2. Extract the crop (commodity), state, and district.
3. Call `fetch_agmarknet_data` to get official mandi prices and trends from data.gov.in.
4. If records are found:
   - Note the modal price (Rs/quintal), MSP comparison, 7-day trend, and mandi used.
   - Formulate a clear SELL or HOLD recommendation.
5. If records are unavailable:
   - State 'data unavailable' explicitly.
   - Set suggestion to 'DATA_UNAVAILABLE'.
   - NEVER fabricate or guess prices under any circumstances!
6. Call `post_market_entry` to write the MARKET entry to the Advisory Board.
7. Return a brief acknowledgment.
""".strip()


# --- Framework Tools ---

@tool(approval_mode="never_require")
def get_intake_for_market(session_id: str) -> str:
    """
    Reads the INTAKE entry from the Advisory Board.

    Args:
        session_id: Blackboard session identifier.

    Returns:
        JSON string of INTAKE entry.
    """
    board = get_advisory_board()
    entry = board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)
    if not entry:
        return json.dumps({"error": "INTAKE entry not found on Advisory Board"})
    return entry.model_dump_json()


@tool(approval_mode="never_require")
async def fetch_agmarknet_data(commodity: str, state: str = "", district: str = "") -> str:
    """
    Queries real Agmarknet wholesale mandi prices via data.gov.in API.

    Args:
        commodity: Crop commodity name (e.g., 'Wheat', 'Rice').
        state: State name for regional filtering.
        district: District name for APMC mandi selection.

    Returns:
        JSON string containing modal price, trends, MSP, suggestion, and data_freshness.
    """
    adapter = AgmarknetAdapter(api_key=DATA_GOV_IN_API_KEY)
    try:
        data, freshness = await adapter.get_market_data(
            commodity=commodity,
            state=state if state else None,
            district=district if district else None,
        )
        return json.dumps({"status": "SUCCESS", "payload": data, "data_freshness": freshness})
    except Exception as exc:
        return json.dumps({
            "status": "ERROR",
            "message": str(exc),
            "payload": {
                "commodity": commodity,
                "mandi_used": "N/A",
                "district": district or "Unknown",
                "state": state or "Unknown",
                "current_modal_price": None,
                "msp": None,
                "trend_7d_pct": None,
                "trend_30d_pct": None,
                "trend_direction": "UNKNOWN",
                "suggestion": "DATA_UNAVAILABLE",
                "is_data_available": False,
            },
            "data_freshness": "unavailable",
        })


@tool(approval_mode="never_require")
def post_market_entry(
    session_id: str,
    commodity: str,
    mandi_used: str,
    district: str,
    state: str,
    current_modal_price: Optional[float],
    msp: Optional[float],
    trend_7d_pct: Optional[float],
    trend_30d_pct: Optional[float],
    trend_direction: str,
    suggestion: str,
    is_data_available: bool,
    confidence: float,
    data_freshness: str,
) -> str:
    """
    Posts the MARKET entry to the Advisory Board.

    Args:
        session_id: Blackboard session identifier.
        commodity: Commodity evaluated.
        mandi_used: APMC market used.
        district: Mandi district.
        state: Mandi state.
        current_modal_price: Current modal price in Rs/quintal.
        msp: Minimum Support Price in Rs/quintal.
        trend_7d_pct: 7-day price trend percentage.
        trend_30d_pct: 30-day price trend percentage.
        trend_direction: 'UP', 'DOWN', 'FLAT', or 'UNKNOWN'.
        suggestion: Recommendation ('SELL', 'HOLD', 'DATA_UNAVAILABLE').
        is_data_available: True if real prices were available.
        confidence: Confidence score 0.0 to 1.0.
        data_freshness: 'live', 'cached', 'stale', or 'unavailable'.

    Returns:
        JSON string confirming entry creation.
    """
    board = get_advisory_board()
    payload = {
        "commodity": commodity,
        "mandi_used": mandi_used,
        "district": district,
        "state": state,
        "current_modal_price": current_modal_price,
        "msp": msp,
        "trend_7d_pct": trend_7d_pct,
        "trend_30d_pct": trend_30d_pct,
        "trend_direction": trend_direction,
        "suggestion": suggestion,
        "is_data_available": is_data_available,
    }
    entry = board.post_entry(
        session_id=session_id,
        agent_name="Market Agent",
        type=EntryType.MARKET.value,
        payload=payload,
        confidence=confidence,
        data_freshness=data_freshness,
        sources=[
            "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
            if is_data_available
            else "Agmarknet (data unavailable)"
        ],
    )
    return json.dumps({"status": "SUCCESS", "entry_id": entry.entry_id})


def create_market_agent(client=None) -> Agent:
    """
    Creates and returns the framework chat agent for Market Agent.
    """
    if client is None:
        client = get_model_client()

    return Agent(
        client=client,
        name="Market Agent",
        instructions=MARKET_AGENT_INSTRUCTIONS,
        tools=[get_intake_for_market, fetch_agmarknet_data, post_market_entry],
    )


class MarketAgentRunner:
    """
    Autonomous runner for Market Agent.
    """

    def __init__(self, client=None, board: Optional[AdvisoryBoard] = None):
        self.board = board or get_advisory_board()
        self.agent = create_market_agent(client=client)

    async def run(self, session_id: str) -> AdvisoryBoardEntry:
        """
        Executes Market Agent workflow for a session.
        """
        prompt = (
            f"Read INTAKE for session '{session_id}' from the Advisory Board. "
            f"Fetch Agmarknet mandi data and post the MARKET entry."
        )

        try:
            await self.agent.run(prompt)
        except Exception:
            pass

        entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.MARKET.value)
        if not entry:
            # Deterministic execution for offline testing or unit test suite
            intake_entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)
            if not intake_entry:
                raise RuntimeError(f"Cannot run Market Agent: INTAKE entry missing for session '{session_id}'")

            crop = intake_entry.payload.get("crop", "Wheat")
            state = intake_entry.payload.get("state", "")
            district = intake_entry.payload.get("district", "")

            adapter = AgmarknetAdapter(api_key=DATA_GOV_IN_API_KEY)
            market_data, freshness = await adapter.get_market_data(commodity=crop, state=state, district=district)

            confidence = 0.90 if market_data["is_data_available"] else 0.40
            post_market_entry(
                session_id=session_id,
                commodity=market_data["commodity"],
                mandi_used=market_data["mandi_used"],
                district=market_data["district"],
                state=market_data["state"],
                current_modal_price=market_data["current_modal_price"],
                msp=market_data["msp"],
                trend_7d_pct=market_data["trend_7d_pct"],
                trend_30d_pct=market_data["trend_30d_pct"],
                trend_direction=market_data["trend_direction"],
                suggestion=market_data["suggestion"],
                is_data_available=market_data["is_data_available"],
                confidence=confidence,
                data_freshness=freshness,
            )
            entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.MARKET.value)

        if not entry:
            raise RuntimeError("Market Agent failed to produce MARKET board entry.")
        return entry

