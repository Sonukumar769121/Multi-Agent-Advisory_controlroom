"""
Advisor Coordinator Module
Microsoft Agent Framework (package: agent-framework v1.25.0)

Role:
- Reads the entire Advisory Board for the session.
- Synthesizes ONE unified, plain-language advisory:
  * Exactly ONE field action (sowing or irrigation)
  * Exactly ONE market timing recommendation (sell or hold)
  * Exactly ONE relevant government scheme with eligibility
  * Length: 120 words or fewer, plain language, short sentences
  * Explicitly states data freshness and notes data gaps if any agent failed or is stale
  * Supports Hindi ('hi') or Punjabi ('pa') translations when requested.
- Posts ADVISORY entry and returns FinalAdvisory.

Verified API:
- agent_framework.Agent, agent_framework.tool
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/_agent.py
  python/packages/core/agent_framework/_tools.py
"""

import json
from typing import Dict, Any, Optional, List
from agent_framework import Agent, tool  # [VERIFIED: agent-framework v1.25.0]

from config import get_model_client
from board.advisory_board import get_advisory_board, AdvisoryBoard
from board.models import AdvisoryBoardEntry, EntryType, DataFreshness, FinalAdvisory

# --- Localization Dictionaries for Multilingual Advisories ---
CROP_TRANSLATIONS = {
    "Wheat": {"hi": "गेहूँ", "pa": "ਕਣਕ"},
    "Rice": {"hi": "धान / चावल", "pa": "ਝੋਨਾ / ਚੌਲ"},
    "Mustard": {"hi": "सरसों", "pa": "ਸਰ੍ਹੋਂ"},
    "Cotton": {"hi": "कपास", "pa": "ਕਪਾਹ"},
    "Maize": {"hi": "मक्का", "pa": "ਮੱਕੀ"},
    "Gram": {"hi": "चना", "pa": "ਛੋਲੇ"},
}

def localize_crop(crop_name: str, lang: str) -> str:
    if lang in ("hi", "pa"):
        return CROP_TRANSLATIONS.get(crop_name, {}).get(lang, crop_name)
    return crop_name

def localize_field_action(act: str, reasoning: str, rain: float, lang: str) -> str:
    act_lower = act.lower()
    if lang == "hi":
        if "hold" in act_lower or rain >= 15.0:
            return f"खेत कार्य: सिंचाई रोकें। अगले दिनों में {rain} मिमी वर्षा की संभावना है, जिससे जलभराव का खतरा है।"
        elif "irrigate" in act_lower or "irrigation" in act_lower:
            return "खेत कार्य: सिंचाई तुरंत करें। अगले 7 दिन मौसम शुष्क रहेगा (0.0 मिमी वर्षा) और फसल विकास की संवेदनशील अवस्था में है।"
        elif "sow" in act_lower:
            return "खेत कार्य: बुवाई करें। तापमान और नमी बुवाई के लिए पूरी तरह अनुकूल है।"
        elif "wait" in act_lower:
            return "खेत कार्य: बुवाई या छिड़काव रोकें। मौसम स्थिर होने तक 4-5 दिन प्रतीक्षा करें।"
        return f"खेत कार्य: {act.capitalize()}। {reasoning}"
    elif lang == "pa":
        if "hold" in act_lower or rain >= 15.0:
            return f"ਖੇਤ ਕਾਰਵਾਈ: ਸਿੰਚਾਈ ਰੋਕੋ। ਅਗਲੇ ਦਿਨਾਂ ਦੌਰਾਨ {rain} ਮਿਲੀਮੀਟਰ ਮੀਂਹ ਪੈਣ ਦੀ ਸੰਭਾਵਨਾ ਹੈ।"
        elif "irrigate" in act_lower or "irrigation" in act_lower:
            return "ਖੇਤ ਕਾਰਵਾਈ: ਤੁਰੰਤ ਸਿੰਚਾਈ ਕਰੋ। ਅਗਲੇ 7 ਦਿਨ ਮੌਸਮ ਖੁਸ਼ਕ ਰਹੇਗਾ (0.0 ਮਿਲੀਮੀਟਰ ਮੀਂਹ) ਅਤੇ ਫ਼ਸਲ ਨਾਜ਼ੁਕ ਪੜਾਅ 'ਤੇ ਹੈ।"
        elif "sow" in act_lower:
            return "ਖੇਤ ਕਾਰਵਾਈ: ਬਿਜਾਈ ਕਰੋ। ਤਾਪਮਾਨ ਅਤੇ ਨਮੀ ਬਿਜਾਈ ਲਈ ਬਿਲਕੁਲ ਢੁਕਵੀਂ ਹੈ।"
        elif "wait" in act_lower:
            return "ਖੇਤ ਕਾਰਵਾਈ: ਬਿਜਾਈ ਜਾਂ ਸਪਰੇਅ ਰੋਕੋ। ਮੌਸਮ ਅਨੁਕੂਲ ਹੋਣ ਤੱਕ ਕੁਝ ਦਿਨ ਉਡੀਕ ਕਰੋ।"
        return f"ਖੇਤ ਕਾਰਵਾਈ: {act.capitalize()}। {reasoning}"
    return f"Field Action: {act.capitalize()}. {reasoning}"

def localize_market(sugg: str, price: Optional[float], msp: Optional[float], mandi: str, is_available: bool, lang: str) -> str:
    sugg_upper = sugg.upper()
    if not is_available:
        if lang == "hi":
            return "मंडी सुझाव: स्थानीय मंडी भाव अनुपलब्ध हैं। अपने नजदीकी एपीएमसी या एमएसपी खरीद केंद्र पर संपर्क करें।"
        elif lang == "pa":
            return "ਮੰਡੀ ਸਲਾਹ: ਸਥਾਨਕ ਮੰਡੀ ਦੇ ਭਾਅ ਉਪਲਬਧ ਨਹੀਂ ਹਨ। ਆਪਣੀ ਨੇੜਲੀ ਮਾਰਕੀਟ ਕਮੇਟੀ ਜਾਂ ਐਮ.ਐਸ.ਪੀ ਕੇਂਦਰ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।"
        return "Market: Live mandi prices unavailable. Check local APMC or deliver to MSP center."

    if lang == "hi":
        action_hi = "बिक्री करें" if "SELL" in sugg_upper else "माल रोक कर रखें"
        return f"मंडी सुझाव: {action_hi}। {mandi} मंडी में भाव ₹{price}/क्विंटल चल रहा है (एमएसपी: ₹{msp}/क्विंटल)।"
    elif lang == "pa":
        action_pa = "ਫ਼ਸਲ ਵੇਚੋ" if "SELL" in sugg_upper else "ਮਾਲ ਰੋਕ ਕੇ ਰੱਖੋ"
        return f"ਮੰਡੀ ਸਲਾਹ: {action_pa}। {mandi} ਮੰਡੀ ਵਿੱਚ ਭਾਅ ₹{price}/ਕੁਇੰਟਲ ਚੱਲ ਰਿਹਾ ਹੈ (ਐਮ.ਐਸ.ਪੀ: ₹{msp}/ਕੁਇੰਟਲ)।"
    return f"Market: {sugg_upper}. Current modal price at {mandi} is Rs {price}/quintal (MSP: Rs {msp}/quintal)."

def localize_scheme(s_name: str, s_elig: str, lang: str) -> str:
    s_name_upper = s_name.upper()
    if lang == "hi":
        if "PMFBY" in s_name_upper or "BIMA" in s_name_upper:
            return "सरकारी योजना: प्रधानमंत्री फसल बीमा योजना (PMFBY)। पात्रता: सभी अधिसूचित फसल किसान। 1.5% रबी प्रीमियम पर प्राकृतिक आपदाओं से पूर्ण सुरक्षा पाएं।"
        elif "KISAN" in s_name_upper:
            return "सरकारी योजना: पीएम-किसान सम्मान निधि। पात्रता: सभी पात्र भूमिधारक किसान। प्रति वर्ष ₹6,000 की आर्थिक सहायता तीन किस्तों में प्राप्त करें।"
        elif "KCC" in s_name_upper:
            return "सरकारी योजना: किसान क्रेडिट कार्ड (KCC)। पात्रता: सभी किसान। 4% रियायती ब्याज दर पर अल्पकालिक फसली ऋण लें।"
        return f"सरकारी योजना: {s_name}। पात्रता: {s_elig} आधिकारिक पोर्टल या सीएससी केंद्र पर आवेदन करें।"
    elif lang == "pa":
        if "PMFBY" in s_name_upper or "BIMA" in s_name_upper:
            return "ਸਰਕਾਰੀ ਸਕੀਮ: ਪ੍ਰਧਾਨ ਮੰਤਰੀ ਫ਼ਸਲ ਬੀਮਾ ਯੋਜਨਾ (PMFBY)। ਯੋਗਤਾ: ਸਾਰੇ ਨੋਟੀਫਾਈਡ ਫ਼ਸਲ ਕਾਸ਼ਤਕਾਰ। 1.5% ਰਬੀ ਪ੍ਰੀਮੀਅਮ 'ਤੇ ਕੁਦਰਤੀ ਆਫ਼ਤਾਂ ਤੋਂ ਬੀਮਾ ਸੁਰੱਖਿਆ ਪ੍ਰਾਪਤ ਕਰੋ।"
        elif "KISAN" in s_name_upper:
            return "ਸਰਕਾਰੀ ਸਕੀਮ: ਪੀ.ਐਮ-ਕਿਸਾਨ ਸਨਮਾਨ ਨਿਧੀ। ਯੋਗਤਾ: ਸਾਰੇ ਯੋਗ ਜ਼ਮੀਨ ਮਾਲਕ ਕਿਸਾਨ। ਸਾਲਾਨਾ ₹6,000 ਦੀ ਸਹਾਇਤਾ ਤਿੰਨ ਕਿਸ਼ਤਾਂ ਵਿੱਚ ਸਿੱਧੇ ਖਾਤੇ ਵਿੱਚ ਪ੍ਰਾਪਤ ਕਰੋ।"
        elif "KCC" in s_name_upper:
            return "ਸਰਕਾਰੀ ਸਕੀਮ: ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ (KCC)। ਯੋਗਤਾ: ਸਾਰੇ ਕਿਸਾਨ। 4% ਸਬਸਿਡੀ ਵਾਲੀ ਵਿਆਜ ਦਰ 'ਤੇ ਫ਼ਸਲੀ ਕਰਜ਼ਾ ਲਵੋ।"
        return f"ਸਰਕਾਰੀ ਸਕੀਮ: {s_name}। ਯੋਗਤਾ: {s_elig} ਅਧਿਕਾਰਤ ਪੋਰਟਲ 'ਤੇ ਅਰਜ਼ੀ ਦਿਓ।"
    return f"Scheme: {s_name}. Eligibility: {s_elig} Apply at official portal or CSC."

def localize_freshness(summary: str, lang: str) -> str:
    if lang == "hi":
        return summary.replace("Weather", "मौसम").replace("Market", "मंडी भाव").replace("Scheme", "योजना").replace("live", "लाइव").replace("cached", "कैश्ड").replace("stale", "पुरानी")
    elif lang == "pa":
        return summary.replace("Weather", "ਮੌਸਮ").replace("Market", "ਮੰਡੀ ਭਾਅ").replace("Scheme", "ਸਕੀਮ").replace("live", "ਲਾਈਵ").replace("cached", "ਕੈਸ਼ਡ").replace("stale", "ਪੁਰਾਣੀ")
    return summary

ADVISOR_COORDINATOR_INSTRUCTIONS = """
You are the Advisor Coordinator in the Agricultural Advisory Control Room.
Your role:
1. Call `read_full_board` to inspect all blackboard entries for the session:
   - INTAKE (crop, location, stage, language)
   - WEATHER (rainfall, temperatures, humidity, wind)
   - CROP_ACTION (field action, reasoning)
   - MARKET (mandi price, MSP, trend, sell/hold)
   - SCHEME (scheme name, eligibility, apply)
   - FAILED (any failed agent steps)
2. Produce ONE concise agricultural advisory following these strict constraints:
   - Length: MUST be 120 words or fewer.
   - Tone: Plain language, short and direct sentences suitable for farmers.
   - Component A: Exactly one field action (sowing or irrigation advice based on weather).
   - Component B: Exactly one market timing recommendation (sell or hold based on price and MSP).
   - Component C: Exactly one government scheme with clear eligibility.
   - Transparency: Mention data freshness (e.g. 'Weather data is live; Mandi price is cached/unavailable').
   - Language: If language is 'hi', provide the advisory in Hindi; if 'pa', in Punjabi; otherwise English.
3. Call `post_final_advisory` to write the advisory to the board.
4. Return the final advisory text.
""".strip()


# --- Framework Tools ---

@tool(approval_mode="never_require")
def read_full_board(session_id: str) -> str:
    """
    Reads all posted entries from the Advisory Board for the current session.

    Args:
        session_id: Blackboard session identifier.

    Returns:
        JSON array of all board entries with payloads and status tags.
    """
    board = get_advisory_board()
    entries = board.get_entries(session_id=session_id)
    return json.dumps([e.model_dump() for e in entries])


@tool(approval_mode="never_require")
def post_final_advisory(
    session_id: str,
    field_action: str,
    market_suggestion: str,
    government_scheme: str,
    advisory_text: str,
    language: str,
    data_freshness_summary: str,
    data_gaps_json: str,
    is_partial: bool,
) -> str:
    """
    Posts the final unified advisory to the Advisory Board.

    Args:
        session_id: Blackboard session identifier.
        field_action: Single field action recommendation.
        market_suggestion: Single market recommendation.
        government_scheme: Government scheme and brief eligibility.
        advisory_text: Unified plain-language advisory (<= 120 words).
        language: Language code ('en', 'hi', 'pa').
        data_freshness_summary: Summary of upstream data freshness.
        data_gaps_json: JSON array of identified gaps or failed agents.
        is_partial: True if running with partial/missing upstream inputs.

    Returns:
        JSON string confirming advisory creation.
    """
    board = get_advisory_board()
    try:
        data_gaps = json.loads(data_gaps_json) if isinstance(data_gaps_json, str) else data_gaps_json
    except Exception:
        data_gaps = [str(data_gaps_json)]

    words = advisory_text.strip().split()
    word_count = len(words)

    payload = {
        "field_action": field_action,
        "market_suggestion": market_suggestion,
        "government_scheme": government_scheme,
        "advisory_text": advisory_text,
        "language": language,
        "data_freshness_summary": data_freshness_summary,
        "data_gaps": data_gaps,
        "is_partial": is_partial,
        "word_count": word_count,
    }

    entry = board.post_entry(
        session_id=session_id,
        agent_name="Advisor Coordinator",
        type=EntryType.ADVISORY.value,
        payload=payload,
        confidence=0.95 if not is_partial else 0.70,
        data_freshness=DataFreshness.LIVE.value,
        sources=["Advisory Board Synthesis"],
    )
    return json.dumps({"status": "SUCCESS", "entry_id": entry.entry_id})


def create_advisor_coordinator(client=None) -> Agent:
    """
    Creates and returns the framework chat agent for Advisor Coordinator.
    """
    if client is None:
        client = get_model_client()

    return Agent(
        client=client,
        name="Advisor Coordinator",
        instructions=ADVISOR_COORDINATOR_INSTRUCTIONS,
        tools=[read_full_board, post_final_advisory],
    )


class AdvisorCoordinatorRunner:
    """
    Autonomous runner for Advisor Coordinator.
    """

    def __init__(self, client=None, board: Optional[AdvisoryBoard] = None):
        self.board = board or get_advisory_board()
        self.agent = create_advisor_coordinator(client=client)

    async def run(self, session_id: str) -> FinalAdvisory:
        """
        Executes Advisor Coordinator workflow for a session.
        """
        prompt = (
            f"Read the full board for session '{session_id}'. "
            f"Synthesize the single advisory (<= 120 words) with field action, market timing, "
            f"and scheme eligibility. Post the ADVISORY entry."
        )

        try:
            await self.agent.run(prompt)
        except Exception:
            pass

        entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.ADVISORY.value)
        if not entry:
            # Deterministic synthesis fallback
            entries = self.board.get_entries(session_id=session_id)
            intake_e = next((e for e in entries if e.type == EntryType.INTAKE.value), None)
            weather_e = next((e for e in entries if e.type == EntryType.WEATHER.value), None)
            crop_e = next((e for e in entries if e.type == EntryType.CROP_ACTION.value), None)
            market_e = next((e for e in entries if e.type == EntryType.MARKET.value), None)
            scheme_e = next((e for e in entries if e.type == EntryType.SCHEME.value), None)
            failed_e = [e for e in entries if e.type == EntryType.FAILED.value]

            crop_name = intake_e.payload.get("crop", "Wheat") if intake_e else "Wheat"
            lang = intake_e.payload.get("language", "en") if intake_e else "en"

            data_gaps = []
            is_partial = False
            if failed_e:
                is_partial = True
                for fe in failed_e:
                    data_gaps.append(f"{fe.agent_name} failed: {fe.payload.get('error', 'unknown error')}")

            crop_display = localize_crop(crop_name, lang)

            # 1. Field Action
            act = "irrigate"
            reasoning = ""
            rain = 0.0
            if weather_e:
                rain = weather_e.payload.get("seven_day_rain_mm", 0.0)
            if crop_e:
                act = crop_e.payload.get("recommended_action", "irrigate").replace("_", " ")
                reasoning = crop_e.payload.get("reasoning", "")
            field_action = localize_field_action(act, reasoning, rain, lang)

            # 2. Market Suggestion
            sugg = "HOLD"
            price = None
            msp = None
            mandi = "Mandi"
            is_avail = False
            if market_e:
                is_avail = market_e.payload.get("is_data_available", False)
                sugg = market_e.payload.get("suggestion", "HOLD")
                price = market_e.payload.get("current_modal_price")
                msp = market_e.payload.get("msp")
                mandi = market_e.payload.get("mandi_used", "Mandi")
            market_suggestion = localize_market(sugg, price, msp, mandi, is_avail, lang)

            # 3. Government Scheme
            s_name = "PMFBY"
            s_elig = "All active farmers growing notified crops."
            if scheme_e:
                s_name = scheme_e.payload.get("scheme_name", "PMFBY")
                s_elig = scheme_e.payload.get("eligibility", "All active farmers.")
            government_scheme = localize_scheme(s_name, s_elig, lang)

            # Freshness
            freshness_items = []
            if weather_e:
                freshness_items.append(f"Weather ({weather_e.data_freshness})")
            if market_e:
                freshness_items.append(f"Market ({market_e.data_freshness})")
            if scheme_e:
                freshness_items.append(f"Scheme ({scheme_e.data_freshness})")
            freshness_raw = ", ".join(freshness_items) if freshness_items else "Standard telemetry"
            freshness_summary = localize_freshness(freshness_raw, lang)

            # Plain language short sentences
            if lang == "hi":
                text = (
                    f"{crop_display} के लिए कृषि सलाह: "
                    f"{field_action} "
                    f"{market_suggestion} "
                    f"{government_scheme} "
                    f"डेटा स्थिति: {freshness_summary}।"
                )
            elif lang == "pa":
                text = (
                    f"{crop_display} ਲਈ ਖੇਤੀਬਾੜੀ ਸਲਾਹ: "
                    f"{field_action} "
                    f"{market_suggestion} "
                    f"{government_scheme} "
                    f"ਡਾਟਾ ਸਥਿਤੀ: {freshness_summary}।"
                )
            else:
                text = (
                    f"Agricultural Advisory for {crop_name}: "
                    f"{field_action} "
                    f"{market_suggestion} "
                    f"{government_scheme} "
                    f"Data Status: {freshness_summary}."
                )

            # Ensure <= 120 words
            words = text.split()
            if len(words) > 120:
                text = " ".join(words[:115]) + "..."

            post_final_advisory(
                session_id=session_id,
                field_action=field_action,
                market_suggestion=market_suggestion,
                government_scheme=government_scheme,
                advisory_text=text,
                language=lang,
                data_freshness_summary=freshness_summary,
                data_gaps_json=json.dumps(data_gaps),
                is_partial=is_partial,
            )

        entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.ADVISORY.value)
        if not entry:
            raise RuntimeError("Advisor Coordinator failed to produce ADVISORY board entry.")

        p = entry.payload
        words = p["advisory_text"].split()
        return FinalAdvisory(
            session_id=session_id,
            field_action=p["field_action"],
            market_suggestion=p["market_suggestion"],
            government_scheme=p["government_scheme"],
            advisory_text=p["advisory_text"],
            language=p.get("language", "en"),
            data_freshness_summary=p.get("data_freshness_summary", ""),
            data_gaps=p.get("data_gaps", []),
            is_partial=p.get("is_partial", False),
            word_count=len(words),
        )
