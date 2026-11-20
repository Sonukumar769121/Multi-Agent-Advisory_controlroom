"""
Weather Agent Module
Microsoft Agent Framework (package: agent-framework v1.25.0)

Role:
- Reads INTAKE entry from Advisory Board.
- Calls Open-Meteo Forecast API for real forecast data.
- Computes 7-day rainfall, rain probability, min/max temperature, humidity, wind speed, and summary.
- Posts WEATHER entry to Advisory Board with accurate data_freshness and confidence.

Verified API:
- agent_framework.Agent, agent_framework.tool
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/_agent.py
  python/packages/core/agent_framework/_tools.py
"""

import json
from typing import Dict, Any, Optional
from agent_framework import Agent, tool  # [VERIFIED: agent-framework v1.25.0]

from config import get_model_client
from board.advisory_board import get_advisory_board, AdvisoryBoard
from board.models import AdvisoryBoardEntry, EntryType, DataFreshness
from adapters.open_meteo import OpenMeteoAdapter

WEATHER_AGENT_INSTRUCTIONS = """
You are the Weather Agent in the Agricultural Advisory Control Room.
Your task:
1. Read the INTAKE entry from the Advisory Board using `get_board_intake`.
2. Extract the latitude and longitude coordinates.
3. Call `fetch_weather_forecast` to get real 7-day meteorological data from Open-Meteo.
4. Call `post_weather_entry` to write the WEATHER entry to the Advisory Board. Include:
   - 7-day cumulative rainfall in mm
   - rain probability in %
   - min and max temperature in °C
   - humidity in %
   - wind speed in km/h
   - summary
   - data_freshness ('live', 'cached', or 'stale')
5. Return a brief acknowledgment.

Rules:
- Never fabricate temperatures or rainfall amounts. Always use the forecast tool.
- Never contact any other agent directly. Read and write only via board tools.
""".strip()


# --- Framework Tools ---

@tool(approval_mode="never_require")
def get_board_intake(session_id: str) -> str:
    """
    Reads the validated INTAKE entry from the Advisory Board.

    Args:
        session_id: Blackboard session identifier.

    Returns:
        JSON string containing the INTAKE entry payload with coordinates.
    """
    board = get_advisory_board()
    entry = board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)
    if not entry:
        return json.dumps({"error": "INTAKE entry not found on Advisory Board"})
    return entry.model_dump_json()


@tool(approval_mode="never_require")
async def fetch_weather_forecast(latitude: float, longitude: float) -> str:
    """
    Fetch real 7-day weather forecast from Open-Meteo API.

    Args:
        latitude: Geocoded latitude coordinate.
        longitude: Geocoded longitude coordinate.

    Returns:
        JSON string with 7-day rain sum, max rain prob, temp range, humidity, wind, and data_freshness.
    """
    adapter = OpenMeteoAdapter()
    try:
        payload, freshness = await adapter.get_forecast(latitude=latitude, longitude=longitude)
        return json.dumps({"status": "SUCCESS", "payload": payload, "data_freshness": freshness})
    except Exception as exc:
        return json.dumps({"status": "ERROR", "message": str(exc), "data_freshness": "unavailable"})


@tool(approval_mode="never_require")
def post_weather_entry(
    session_id: str,
    seven_day_rain_mm: float,
    rain_probability_pct: float,
    temp_min_c: float,
    temp_max_c: float,
    humidity_pct: float,
    wind_speed_kmh: float,
    summary: str,
    confidence: float,
    data_freshness: str,
) -> str:
    """
    Posts the WEATHER entry to the Advisory Board.

    Args:
        session_id: Blackboard session identifier.
        seven_day_rain_mm: Total 7-day precipitation in mm.
        rain_probability_pct: Peak precipitation probability %.
        temp_min_c: Minimum temp in °C.
        temp_max_c: Maximum temp in °C.
        humidity_pct: Average humidity %.
        wind_speed_kmh: Maximum wind speed in km/h.
        summary: Agronomic summary text.
        confidence: Confidence score 0.0 to 1.0.
        data_freshness: 'live', 'cached', 'stale', or 'unavailable'.

    Returns:
        JSON string confirming entry creation.
    """
    board = get_advisory_board()
    payload = {
        "seven_day_rain_mm": float(seven_day_rain_mm),
        "rain_probability_pct": float(rain_probability_pct),
        "temp_min_c": float(temp_min_c),
        "temp_max_c": float(temp_max_c),
        "humidity_pct": float(humidity_pct),
        "wind_speed_kmh": float(wind_speed_kmh),
        "summary": summary,
    }
    entry = board.post_entry(
        session_id=session_id,
        agent_name="Weather Agent",
        type=EntryType.WEATHER.value,
        payload=payload,
        confidence=confidence,
        data_freshness=data_freshness,
        sources=["https://api.open-meteo.com/v1/forecast"],
    )
    return json.dumps({"status": "SUCCESS", "entry_id": entry.entry_id})


def create_weather_agent(client=None) -> Agent:
    """
    Creates and returns the framework chat agent for Weather Agent.
    """
    if client is None:
        client = get_model_client()

    return Agent(
        client=client,
        name="Weather Agent",
        instructions=WEATHER_AGENT_INSTRUCTIONS,
        tools=[get_board_intake, fetch_weather_forecast, post_weather_entry],
    )


class WeatherAgentRunner:
    """
    Autonomous runner for Weather Agent.
    """

    def __init__(self, client=None, board: Optional[AdvisoryBoard] = None):
        self.board = board or get_advisory_board()
        self.agent = create_weather_agent(client=client)

    async def run(self, session_id: str) -> AdvisoryBoardEntry:
        """
        Executes the Weather Agent workflow for a session.
        """
        prompt = (
            f"Read INTAKE for session '{session_id}' from the board, fetch the 7-day weather forecast, "
            f"and post the WEATHER entry."
        )

        try:
            await self.agent.run(prompt)
        except Exception:
            pass

        entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.WEATHER.value)
        if not entry:
            # Deterministic fallback execution for unit tests or offline environments
            intake_entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)
            if not intake_entry:
                raise RuntimeError(f"Cannot run Weather Agent: INTAKE entry missing for session '{session_id}'")

            lat = float(intake_entry.payload["latitude"])
            lon = float(intake_entry.payload["longitude"])
            adapter = OpenMeteoAdapter()
            forecast_data, freshness = await adapter.get_forecast(latitude=lat, longitude=lon)

            post_weather_entry(
                session_id=session_id,
                seven_day_rain_mm=forecast_data["seven_day_rain_mm"],
                rain_probability_pct=forecast_data["rain_probability_pct"],
                temp_min_c=forecast_data["temp_min_c"],
                temp_max_c=forecast_data["temp_max_c"],
                humidity_pct=forecast_data["humidity_pct"],
                wind_speed_kmh=forecast_data["wind_speed_kmh"],
                summary=forecast_data["summary"],
                confidence=0.92,
                data_freshness=freshness,
            )
            entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.WEATHER.value)

        if not entry:
            raise RuntimeError("Weather Agent failed to produce WEATHER board entry.")
        return entry

