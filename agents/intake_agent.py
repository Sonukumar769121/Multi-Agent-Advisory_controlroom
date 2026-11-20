"""
Intake Agent Module
Microsoft Agent Framework (package: agent-framework v1.25.0)

Role:
- Validates crop, location and stage.
- Normalises crop names and growth stages.
- Geocodes the location with Open-Meteo Geocoding.
- Posts INTAKE entry (crop, location, lat/lon, stage, language) to the Advisory Board.

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

# Crop normalization lookup
CROP_SYNONYMS: Dict[str, str] = {
    "gehun": "Wheat",
    "gehu": "Wheat",
    "kanak": "Wheat",
    "wheat": "Wheat",
    "rice": "Rice",
    "paddy": "Rice",
    "dhan": "Rice",
    "chawal": "Rice",
    "sarson": "Mustard",
    "mustard": "Mustard",
    "raya": "Mustard",
    "cotton": "Cotton",
    "kapas": "Cotton",
    "maize": "Maize",
    "makka": "Maize",
    "chana": "Gram",
    "gram": "Gram",
    "chickpea": "Gram",
}

# Stage normalization
VALID_STAGES = {"sowing", "vegetative", "flowering", "grain_filling", "harvest_ready", "harvesting"}

INTAKE_AGENT_INSTRUCTIONS = """
You are the Intake Agent in the Agricultural Advisory Control Room.
Your exact job is to:
1. Validate the farmer's crop, location, growth stage, and preferred language.
2. Normalise local crop names (e.g., 'kanak', 'gehun' -> 'Wheat'; 'dhan' -> 'Rice').
3. Call the `geocode_location` tool to fetch real coordinates, district, and state from Open-Meteo.
4. Call `post_intake_entry` to write the validated INTAKE entry to the Advisory Board.
5. Return a brief JSON acknowledgment confirming the posted INTAKE entry.

Rules:
- Never fabricate coordinates or locations. Always use the geocoding tool.
- Never communicate directly with other agents. Only read and post to the Advisory Board.
- Maintain a high confidence score (0.95+) when coordinates are accurately resolved.
""".strip()


# --- Framework Tools ---

@tool(approval_mode="never_require")
async def geocode_location(location_name: str) -> str:
    """
    Geocode a village, district, or city name using Open-Meteo Geocoding API.

    Args:
        location_name: Name of the agricultural location, e.g., 'Karnal, Haryana'.

    Returns:
        JSON string containing latitude, longitude, state, and district.
    """
    adapter = OpenMeteoAdapter()
    try:
        data = await adapter.geocode(location_name)
        return json.dumps({"status": "SUCCESS", "data": data})
    except Exception as exc:
        return json.dumps({"status": "ERROR", "message": str(exc)})


@tool(approval_mode="never_require")
def post_intake_entry(
    session_id: str,
    crop: str,
    location: str,
    latitude: float,
    longitude: float,
    stage: str,
    language: str,
    district: str,
    state: str,
    confidence: float,
) -> str:
    """
    Post the validated INTAKE entry to the Advisory Board.

    Args:
        session_id: Blackboard session identifier.
        crop: Normalized crop name.
        location: Resolved location name.
        latitude: Geocoded latitude.
        longitude: Geocoded longitude.
        stage: Normalized growth stage.
        language: Output language preference ('en', 'hi', 'pa').
        district: District name.
        state: State name.
        confidence: Confidence score (0.0 to 1.0).

    Returns:
        JSON string confirming entry creation.
    """
    board = get_advisory_board()
    payload = {
        "crop": crop,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "stage": stage,
        "language": language,
        "district": district,
        "state": state,
    }
    entry = board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload=payload,
        confidence=confidence,
        data_freshness=DataFreshness.LIVE.value,
        sources=["https://geocoding-api.open-meteo.com/v1/search"],
    )
    return json.dumps({"status": "SUCCESS", "entry_id": entry.entry_id})


def create_intake_agent(client=None) -> Agent:
    """
    Creates and returns the framework chat agent for Intake Agent.
    """
    if client is None:
        client = get_model_client()

    return Agent(
        client=client,
        name="Intake Agent",
        instructions=INTAKE_AGENT_INSTRUCTIONS,
        tools=[geocode_location, post_intake_entry],
    )


class IntakeAgentRunner:
    """
    Autonomous runner for Intake Agent.
    Executes the framework agent or handles direct deterministic workflow.
    """

    def __init__(self, client=None, board: Optional[AdvisoryBoard] = None):
        self.board = board or get_advisory_board()
        self.agent = create_intake_agent(client=client)

    async def run(
        self,
        session_id: str,
        crop: str,
        location: str,
        stage: str,
        language: str = "en",
    ) -> AdvisoryBoardEntry:
        """
        Runs the Intake Agent for a session.
        """
        # Normalization
        clean_crop = CROP_SYNONYMS.get(crop.strip().lower(), crop.strip().capitalize())
        clean_stage = stage.strip().lower().replace(" ", "_")
        if clean_stage not in VALID_STAGES:
            clean_stage = "vegetative"  # Default fallback if unknown

        # Prompt for Framework Agent
        prompt = (
            f"Process Intake Request:\n"
            f"- Session ID: {session_id}\n"
            f"- Crop: {clean_crop}\n"
            f"- Location: {location}\n"
            f"- Stage: {clean_stage}\n"
            f"- Language: {language}\n"
            f"Please geocode the location and post the INTAKE entry to the board."
        )

        try:
            # Run framework agent
            await self.agent.run(prompt)
        except Exception:
            pass

        entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)
        if not entry:
            # Deterministic execution if agent run did not post entry
            adapter = OpenMeteoAdapter()
            geo = await adapter.geocode(location)
            post_intake_entry(
                session_id=session_id,
                crop=clean_crop,
                location=geo["name"],
                latitude=geo["latitude"],
                longitude=geo["longitude"],
                stage=clean_stage,
                language=language,
                district=geo["district"],
                state=geo["state"],
                confidence=0.95,
            )
            entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.INTAKE.value)

        if not entry:
            raise RuntimeError("Intake Agent failed to produce INTAKE board entry.")
        return entry

