"""
Control Room Orchestrator
Microsoft Agent Framework (package: agent-framework v1.25.0)

================================================================================
ORCHESTRATOR ARCHITECTURE JUSTIFICATION (Blackboard Pattern):
We choose a custom controller because the Blackboard pattern requires dynamic
state-gated transitions, independent 30s timeouts with exponential retry backoff
per agent, and continuous progress to PARTIAL_ADVISORY upon individual agent
failures without aborting uncoupled parallel branches.
================================================================================

Board State Flow:
1. CREATED -> INTAKE_DONE (Intake Agent runs first)
2. Fan-out parallel execution:
   - Weather Agent -> WEATHER_DONE
   - Market Agent  -> MARKET_DONE
   - Scheme Agent  -> SCHEME_DONE
3. Dependent sequential step:
   - Crop Agent (runs after Weather finishes) -> CROP_DONE
4. Fan-in finalization:
   - Advisor Coordinator (runs after all finish or timeout) -> ADVISORY_READY or PARTIAL_ADVISORY

Verified API:
- agent_framework.observability.get_tracer
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/observability/__init__.py
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from config import (
    AGENT_TIMEOUT_SECONDS,
    AGENT_MAX_RETRIES,
    AGENT_BACKOFF_FACTOR,
    init_observability,
    get_model_client,
)
from board.models import BoardState, EntryType, DataFreshness, FinalAdvisory
from board.advisory_board import get_advisory_board, AdvisoryBoard
from agents.intake_agent import IntakeAgentRunner
from agents.weather_agent import WeatherAgentRunner
from agents.crop_agent import CropAgentRunner
from agents.market_agent import MarketAgentRunner
from agents.scheme_agent import SchemeAgentRunner
from agents.advisor_coordinator import AdvisorCoordinatorRunner

logger = logging.getLogger("ControlRoomOrchestrator")


class ControlRoomOrchestrator:
    """
    Control Room Orchestrator managing asynchronous blackboard workflow,
    fan-out parallel agents, dependency gating, retries with backoff,
    and graceful degradation to PARTIAL_ADVISORY.
    """

    def __init__(
        self,
        board: Optional[AdvisoryBoard] = None,
        timeout_seconds: int = AGENT_TIMEOUT_SECONDS,
        max_retries: int = AGENT_MAX_RETRIES,
        backoff_factor: float = AGENT_BACKOFF_FACTOR,
    ):
        self.board = board or get_advisory_board()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Initialize OpenTelemetry framework observability
        init_observability()
        try:
            from agent_framework.observability import get_tracer  # [VERIFIED: agent-framework v1.25.0]
            self.tracer = get_tracer("control_room_orchestrator")
        except Exception:
            self.tracer = None

        # Instantiate agent runners
        client = get_model_client()
        self.intake_runner = IntakeAgentRunner(client=client, board=self.board)
        self.weather_runner = WeatherAgentRunner(client=client, board=self.board)
        self.crop_runner = CropAgentRunner(client=client, board=self.board)
        self.market_runner = MarketAgentRunner(client=client, board=self.board)
        self.scheme_runner = SchemeAgentRunner(client=client, board=self.board)
        self.coordinator_runner = AdvisorCoordinatorRunner(client=client, board=self.board)

    async def _execute_with_retry_and_timeout(
        self,
        board_session_id: str,
        agent_name: str,
        coro_func,
        *args,
        **kwargs,
    ) -> bool:
        """
        Executes an agent coroutine with per-agent timeout (30s) and exponential backoff retries.
        On permanent failure, posts a FAILED entry to the Advisory Board and returns False.
        """
        for attempt in range(self.max_retries + 1):
            try:
                # Wrap with timeout
                await asyncio.wait_for(coro_func(*args, **kwargs), timeout=self.timeout_seconds)
                logger.info(f"[{agent_name}] completed successfully on attempt {attempt + 1}")
                return True
            except asyncio.TimeoutError:
                logger.warning(f"[{agent_name}] timed out after {self.timeout_seconds}s (attempt {attempt + 1})")
            except Exception as exc:
                logger.error(f"[{agent_name}] failed on attempt {attempt + 1}: {exc}")

            if attempt < self.max_retries:
                sleep_time = self.backoff_factor ** attempt
                await asyncio.sleep(sleep_time)

        # Permanent failure: post FAILED entry to Advisory Board
        logger.error(f"[{agent_name}] permanently failed after {self.max_retries + 1} attempts. Posting FAILED entry.")
        self.board.post_entry(
            session_id=board_session_id,
            agent_name=agent_name,
            type=EntryType.FAILED.value,
            payload={"error": f"Agent {agent_name} failed after {self.max_retries} retries."},
            confidence=0.0,
            data_freshness=DataFreshness.UNAVAILABLE.value,
            sources=[agent_name],
            status="FAILED",
        )
        return False

    async def run(
        self,
        session_id: str,
        crop: str,
        location: str,
        stage: str,
        language: str = "en",
    ) -> FinalAdvisory:
        """
        Runs the full Control Room orchestration sequence.
        """
        logger.info(f"Starting Advisory Control Room session '{session_id}' for {crop} at {location}...")
        self.board.set_state(session_id, BoardState.CREATED.value)

        has_failures = False

        # --- STEP 1: Intake Agent (Sequential Gateway) ---
        intake_success = await self._execute_with_retry_and_timeout(
            session_id,
            "Intake Agent",
            self.intake_runner.run,
            session_id=session_id,
            crop=crop,
            location=location,
            stage=stage,
            language=language,
        )

        if not intake_success:
            self.board.set_state(session_id, BoardState.FAILED.value)
            raise RuntimeError(f"Intake Agent failed to validate request for session '{session_id}'.")

        self.board.set_state(session_id, BoardState.INTAKE_DONE.value)

        # --- STEP 2 & 3: Parallel Fan-out with Dependent Branch ---
        # Weather, Market, and Scheme launch concurrently.
        # Crop Agent executes sequentially right after Weather Agent.

        async def run_weather_and_crop():
            nonlocal has_failures
            w_success = await self._execute_with_retry_and_timeout(
                session_id,
                "Weather Agent",
                self.weather_runner.run,
                session_id=session_id,
            )
            if w_success:
                self.board.set_state(session_id, BoardState.WEATHER_DONE.value)
            else:
                has_failures = True

            c_success = await self._execute_with_retry_and_timeout(
                session_id,
                "Crop Agent",
                self.crop_runner.run,
                session_id=session_id,
            )
            if c_success:
                self.board.set_state(session_id, BoardState.CROP_DONE.value)
            else:
                has_failures = True

        async def run_market_pipeline():
            nonlocal has_failures
            success = await self._execute_with_retry_and_timeout(
                session_id,
                "Market Agent",
                self.market_runner.run,
                session_id=session_id,
            )
            if success:
                self.board.set_state(session_id, BoardState.MARKET_DONE.value)
            else:
                has_failures = True

        async def run_scheme_pipeline():
            nonlocal has_failures
            success = await self._execute_with_retry_and_timeout(
                session_id,
                "Scheme Agent",
                self.scheme_runner.run,
                session_id=session_id,
            )
            if success:
                self.board.set_state(session_id, BoardState.SCHEME_DONE.value)
            else:
                has_failures = True

        # Fan-out: Execute Weather+Crop branch, Market branch, and Scheme branch in parallel
        await asyncio.gather(
            run_weather_and_crop(),
            run_market_pipeline(),
            run_scheme_pipeline(),
        )

        # --- STEP 4: Fan-in to Advisor Coordinator ---
        if has_failures:
            self.board.set_state(session_id, BoardState.PARTIAL_ADVISORY.value)
        else:
            self.board.set_state(session_id, BoardState.ADVISORY_READY.value)

        logger.info(f"Running Advisor Coordinator for session '{session_id}' (Partial mode: {has_failures})...")
        coord_success = await self._execute_with_retry_and_timeout(
            session_id,
            "Advisor Coordinator",
            self.coordinator_runner.run,
            session_id=session_id,
        )

        if not coord_success:
            self.board.set_state(session_id, BoardState.FAILED.value)
            raise RuntimeError(f"Advisor Coordinator failed to produce final advisory for session '{session_id}'.")

        advisory_entry = self.board.get_entry(session_id=session_id, entry_type=EntryType.ADVISORY.value)
        p = advisory_entry.payload
        words = p["advisory_text"].split()

        final_advisory = FinalAdvisory(
            session_id=session_id,
            field_action=p["field_action"],
            market_suggestion=p["market_suggestion"],
            government_scheme=p["government_scheme"],
            advisory_text=p["advisory_text"],
            language=p.get("language", language),
            data_freshness_summary=p.get("data_freshness_summary", ""),
            data_gaps=p.get("data_gaps", []),
            is_partial=p.get("is_partial", has_failures),
            word_count=len(words),
        )

        logger.info(f"Advisory Control Room successfully completed session '{session_id}'. Words: {final_advisory.word_count}")
        return final_advisory

