"""
Pydantic Models for Agricultural Advisory Control Room
Strict schema definitions for board entries, payloads, and final advisories.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class BoardState(str, Enum):
    CREATED = "CREATED"
    INTAKE_DONE = "INTAKE_DONE"
    WEATHER_DONE = "WEATHER_DONE"
    CROP_DONE = "CROP_DONE"
    MARKET_DONE = "MARKET_DONE"
    SCHEME_DONE = "SCHEME_DONE"
    ADVISORY_READY = "ADVISORY_READY"
    PARTIAL_ADVISORY = "PARTIAL_ADVISORY"
    FAILED = "FAILED"


class DataFreshness(str, Enum):
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class EntryType(str, Enum):
    INTAKE = "INTAKE"
    WEATHER = "WEATHER"
    CROP_ACTION = "CROP_ACTION"
    MARKET = "MARKET"
    SCHEME = "SCHEME"
    ADVISORY = "ADVISORY"
    FAILED = "FAILED"


# --- Payload Models ---

class IntakePayload(BaseModel):
    crop: str = Field(description="Normalized crop name, e.g., 'Wheat', 'Rice'")
    location: str = Field(description="Location name as specified by user, e.g., 'Karnal, Haryana'")
    latitude: float = Field(description="Geocoded latitude coordinate")
    longitude: float = Field(description="Geocoded longitude coordinate")
    stage: str = Field(description="Current crop growth stage, e.g., 'sowing', 'vegetative', 'flowering'")
    language: str = Field(default="en", description="Preferred advisory language: 'en', 'hi' (Hindi), or 'pa' (Punjabi)")
    district: Optional[str] = Field(default=None, description="Administrative district name")
    state: Optional[str] = Field(default=None, description="Administrative state name")


class WeatherPayload(BaseModel):
    seven_day_rain_mm: float = Field(description="Cumulative 7-day expected precipitation in millimeters (mm)")
    rain_probability_pct: float = Field(description="Maximum precipitation probability over the 7 days in percent (%)")
    temp_min_c: float = Field(description="Minimum expected temperature in degrees Celsius (°C)")
    temp_max_c: float = Field(description="Maximum expected temperature in degrees Celsius (°C)")
    humidity_pct: float = Field(description="Average relative humidity in percent (%)")
    wind_speed_kmh: float = Field(description="Maximum wind speed in km/h")
    summary: str = Field(description="Concise agronomic weather outlook summary")
    forecast_days: List[Dict[str, Any]] = Field(default_factory=list, description="Day-by-day weather breakdown")


class CropActionPayload(BaseModel):
    recommended_action: str = Field(description="Specific field action: 'sow', 'wait', 'irrigate', 'hold_irrigation'")
    reasoning: str = Field(description="Agronomic reasoning linking crop stage, moisture, and weather forecast")
    citations: List[str] = Field(description="Document citations from ICAR/KVK/State Agriculture university guides")


class MarketPayload(BaseModel):
    commodity: str = Field(description="Commodity name evaluated")
    mandi_used: str = Field(description="Name of the APMC mandi used for pricing data")
    district: str = Field(description="District of the mandi used")
    state: str = Field(description="State of the mandi used")
    current_modal_price: Optional[float] = Field(default=None, description="Current modal price in Rs per quintal")
    msp: Optional[float] = Field(default=None, description="Official Minimum Support Price (MSP) in Rs per quintal")
    trend_7d_pct: Optional[float] = Field(default=None, description="7-day modal price trend percentage")
    trend_30d_pct: Optional[float] = Field(default=None, description="30-day modal price trend percentage")
    trend_direction: str = Field(description="'UP', 'DOWN', 'FLAT', or 'UNKNOWN'")
    suggestion: str = Field(description="Market recommendation: 'SELL', 'HOLD', or 'DATA_UNAVAILABLE'")
    is_data_available: bool = Field(description="True if real mandi price records were found, False otherwise")


class SchemePayload(BaseModel):
    scheme_name: str = Field(description="Exact official name of the single best government scheme, e.g., 'PM-KISAN'")
    eligibility: str = Field(description="Clear eligibility criteria for the farmer")
    how_to_apply: str = Field(description="Direct, step-by-step application instructions or portal link")
    source_document: str = Field(description="Name of the official source document retrieved from RAG")
    citations: List[str] = Field(description="Specific chunk citations extracted from the scheme corpus")


class AdvisoryBoardEntry(BaseModel):
    entry_id: str = Field(description="Unique entry identifier (UUID)")
    session_id: str = Field(description="Blackboard session ID")
    agent_name: str = Field(description="Originating agent name")
    type: str = Field(description="Entry type: INTAKE, WEATHER, CROP_ACTION, MARKET, SCHEME, FAILED, ADVISORY")
    payload: Dict[str, Any] = Field(description="Structured JSON payload matching the corresponding payload model")
    confidence: float = Field(ge=0.0, le=1.0, description="Agent confidence score between 0.0 and 1.0")
    data_freshness: str = Field(description="Freshness tag: 'live', 'cached', 'stale', or 'unavailable'")
    sources: List[str] = Field(description="List of data sources or endpoint citations used")
    timestamp: str = Field(description="ISO-8601 formatted timestamp of entry creation")
    status: str = Field(default="SUCCESS", description="'SUCCESS' or 'FAILED'")
    version: int = Field(default=1, description="Entry schema version")


class FinalAdvisory(BaseModel):
    session_id: str = Field(description="Blackboard session ID")
    field_action: str = Field(description="Field action recommendation (sowing or irrigation)")
    market_suggestion: str = Field(description="Market timing suggestion (sell or hold)")
    government_scheme: str = Field(description="Selected government scheme with brief eligibility")
    advisory_text: str = Field(description="One unified plain-language advisory (<= 120 words)")
    language: str = Field(default="en", description="Output language code: 'en', 'hi', or 'pa'")
    data_freshness_summary: str = Field(description="Summary of freshness across all upstream agent inputs")
    data_gaps: List[str] = Field(default_factory=list, description="List of gaps or failed inputs if running in partial mode")
    is_partial: bool = Field(default=False, description="True if any upstream agent failed or produced fallback data")
    word_count: int = Field(description="Total word count of advisory_text (must be <= 120 words)")

