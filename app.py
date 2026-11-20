"""
Agricultural Advisory Control Room - Streamlit Interactive UI
Multi-Agent Blackboard (Control Room) Architecture

Run with:
    streamlit run app.py
"""

import asyncio
import json
import uuid
import streamlit as st

import config
from board.advisory_board import AdvisoryBoard
from board.models import BoardState, EntryType, DataFreshness
from orchestrator.control_room import ControlRoomOrchestrator
from rag.ingest import get_chroma_client, seed_rag_collections

st.set_page_config(
    page_title="AgriAdvisory Control Room",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #2e7d32;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #555;
        margin-bottom: 1.5rem;
    }
    .advisory-card {
        background-color: #f1f8e9;
        border-left: 6px solid #4caf50;
        padding: 1.2rem;
        border-radius: 6px;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }
    .entry-card {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        padding: 1rem;
        border-radius: 6px;
        margin-bottom: 0.8rem;
    }
    .badge-live {
        background-color: #4caf50;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-stale {
        background-color: #ff9800;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-unavailable {
        background-color: #9e9e9e;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🌾 Agricultural Advisory Control Room</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Multi-Agent Blackboard System (Microsoft Agent Framework)</div>', unsafe_allow_html=True)

# Initialize Session State
if "board" not in st.session_state:
    st.session_state.board = AdvisoryBoard(db_path=":memory:")
    # Seed RAG
    client = get_chroma_client(":memory:")
    seed_rag_collections(client)

if "last_advisory" not in st.session_state:
    st.session_state.last_advisory = None

if "last_session_id" not in st.session_state:
    st.session_state.last_session_id = None

# Sidebar Controls
with st.sidebar:
    st.header("Farmer Input Profile")

    crop_options = ["Wheat", "Rice", "Mustard", "Cotton", "Maize", "Gram"]
    selected_crop = st.selectbox("Crop", crop_options, index=0)

    location_options = [
        "Karnal, Haryana",
        "Ludhiana, Punjab",
        "Bharatpur, Rajasthan",
        "Indore, Madhya Pradesh",
        "Bhatinda, Punjab",
        "Kurukshetra, Haryana",
    ]
    selected_location = st.selectbox("Location / APMC Mandi", location_options, index=0)

    stage_options = ["sowing", "vegetative", "flowering", "grain_filling", "harvest_ready"]
    selected_stage = st.selectbox("Growth Stage", stage_options, index=1)

    lang_options = {"English": "en", "Hindi (हिंदी)": "hi", "Punjabi (ਪੰਜਾਬੀ)": "pa"}
    selected_lang_label = st.selectbox("Advisory Language", list(lang_options.keys()), index=0)
    selected_language = lang_options[selected_lang_label]

    st.markdown("---")
    st.subheader("Control Room Settings")
    simulate_market_failure = st.checkbox("Simulate Market Agent Failure (Partial Advisory Mode)", value=False)

    run_btn = st.button("🚀 Run Control Room Advisory", type="primary", use_container_width=True, key="sidebar_run_btn")

# Top Bar Action in Main Area
col_top1, col_top2 = st.columns([3, 1])
with col_top1:
    st.info(f"**Current Profile:** Crop: `{selected_crop}` | Location: `{selected_location}` | Stage: `{selected_stage}` | Language: `{selected_lang_label}`")
with col_top2:
    main_run_btn = st.button("⚡ Run Advisory", type="primary", use_container_width=True, key="main_run_btn")

# Main Execution: Runs when clicked OR automatically when user changes crop/location/stage/language
current_profile_signature = (selected_crop, selected_location, selected_stage, selected_language, simulate_market_failure)

if "last_profile_signature" not in st.session_state:
    st.session_state.last_profile_signature = None

profile_changed = (st.session_state.last_profile_signature != current_profile_signature)
should_run = run_btn or main_run_btn or profile_changed or ("auto_first_run" not in st.session_state)

if should_run:
    st.session_state.auto_first_run = True
    st.session_state.last_profile_signature = current_profile_signature
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    st.session_state.last_session_id = session_id

    # Create fresh board for the run
    board = AdvisoryBoard(db_path=":memory:")
    st.session_state.board = board
    orchestrator = ControlRoomOrchestrator(board=board)

    with st.spinner("Control Room Orchestrator executing multi-agent blackboard pipeline..."):
        if simulate_market_failure:
            # Run intake, weather, crop, scheme, but simulate market failure
            async def run_with_mock_failure():
                board.set_state(session_id, BoardState.CREATED.value)
                await orchestrator.intake_runner.run(
                    session_id=session_id,
                    crop=selected_crop,
                    location=selected_location,
                    stage=selected_stage,
                    language=selected_language,
                )
                board.set_state(session_id, BoardState.INTAKE_DONE.value)

                # Weather & Crop
                await orchestrator.weather_runner.run(session_id=session_id)
                board.set_state(session_id, BoardState.WEATHER_DONE.value)
                await orchestrator.crop_runner.run(session_id=session_id)
                board.set_state(session_id, BoardState.CROP_DONE.value)

                # Scheme
                await orchestrator.scheme_runner.run(session_id=session_id)
                board.set_state(session_id, BoardState.SCHEME_DONE.value)

                # Post simulated market failure
                board.post_entry(
                    session_id=session_id,
                    agent_name="Market Agent",
                    type=EntryType.FAILED.value,
                    payload={"error": "Agmarknet APMC mandi service timed out after 30s."},
                    confidence=0.0,
                    data_freshness=DataFreshness.UNAVAILABLE.value,
                    sources=["Market Agent"],
                    status="FAILED",
                )
                board.set_state(session_id, BoardState.PARTIAL_ADVISORY.value)

                # Coordinator
                adv = await orchestrator.coordinator_runner.run(session_id=session_id)
                return adv

            advisory = asyncio.run(run_with_mock_failure())
        else:
            advisory = asyncio.run(
                orchestrator.run(
                    session_id=session_id,
                    crop=selected_crop,
                    location=selected_location,
                    stage=selected_stage,
                    language=selected_language,
                )
            )

        st.session_state.last_advisory = advisory

# Display Advisory & Blackboard Postings
if st.session_state.last_advisory:
    adv = st.session_state.last_advisory
    sess_id = st.session_state.last_session_id
    board = st.session_state.board

    # 1. Final Advisory Card
    st.subheader("📋 Final Farmer Advisory")

    badge_status = "⚠️ PARTIAL ADVISORY" if adv.is_partial else "✅ COMPLETE ADVISORY"
    st.markdown(f"**Status:** {badge_status} | **Session:** `{sess_id}` | **Length:** `{adv.word_count} words` (Limit <= 120 words)")

    st.markdown(f"""
    <div class="advisory-card">
        <h4 style="margin-top:0; color:#2e7d32;">Unified Actionable Advisory ({adv.language.upper()})</h4>
        <p style="font-size: 1.15rem; line-height: 1.6; margin-bottom: 0.8rem;">{adv.advisory_text}</p>
        <hr style="margin: 0.5rem 0; border: 0; border-top: 1px solid #c8e6c9;">
        <small style="color: #666;"><b>Data Freshness:</b> {adv.data_freshness_summary}</small>
    </div>
    """, unsafe_allow_html=True)

    if adv.data_gaps:
        st.warning(f"**Data Gaps Handled:** {', '.join(adv.data_gaps)}")

    # 3 Summary Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"**🚜 {adv.field_action}**")
    with col2:
        st.success(f"**📈 {adv.market_suggestion}**")
    with col3:
        st.warning(f"**🏛️ {adv.government_scheme}**")

    st.markdown("---")

    # 2. Blackboard State & Agent Postings Explorer
    st.subheader("🗂️ Advisory Board (Blackboard Postings)")
    entries = board.get_entries(session_id=sess_id)

    tabs = st.tabs([
        "Intake Agent",
        "Weather Agent",
        "Crop Agent",
        "Market Agent",
        "Scheme Agent",
        "Advisor Coordinator",
        "Raw Blackboard Log",
    ])

    agent_types = {
        "Intake Agent": EntryType.INTAKE.value,
        "Weather Agent": EntryType.WEATHER.value,
        "Crop Agent": EntryType.CROP_ACTION.value,
        "Market Agent": EntryType.MARKET.value,
        "Scheme Agent": EntryType.SCHEME.value,
        "Advisor Coordinator": EntryType.ADVISORY.value,
    }

    for i, (agent_name, e_type) in enumerate(agent_types.items()):
        with tabs[i]:
            matched = [e for e in entries if e.type == e_type]
            failed = [e for e in entries if e.type == EntryType.FAILED.value and e.agent_name == agent_name]

            if matched:
                entry = matched[-1]
                freshness_class = f"badge-{entry.data_freshness}"
                st.markdown(
                    f"**Agent:** `{entry.agent_name}` | "
                    f"**Freshness:** <span class='{freshness_class}'>{entry.data_freshness.upper()}</span> | "
                    f"**Confidence:** `{entry.confidence}` | "
                    f"**Timestamp:** `{entry.timestamp}`",
                    unsafe_allow_html=True,
                )
                st.json(entry.payload)
                st.caption(f"Sources: {', '.join(entry.sources)}")
            elif failed:
                f_entry = failed[-1]
                st.error(f"❌ **{agent_name} Failed:** {f_entry.payload.get('error')}")
                st.caption(f"Status: {f_entry.status} | Data Freshness: {f_entry.data_freshness}")
            else:
                st.info(f"No posting from {agent_name} in this session.")

    with tabs[6]:
        st.markdown(f"**Total Board Entries Posted:** `{len(entries)}`")
        table_md = "| Entry ID | Agent Name | Type | Freshness | Confidence | Status | Timestamp |\n"
        table_md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        for e in entries:
            ts = e.timestamp.split("T")[1][:8] if "T" in e.timestamp else e.timestamp
            table_md += f"| `{e.entry_id[:8]}...` | **{e.agent_name}** | `{e.type}` | `{e.data_freshness}` | `{e.confidence}` | `{e.status}` | `{ts}` |\n"
        st.markdown(table_md)

else:
    st.info("👈 Select a crop, location, and growth stage in the sidebar and click **Run Control Room Advisory** to trigger the multi-agent system.")
