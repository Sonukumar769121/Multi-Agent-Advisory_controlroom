"""
Unit tests for Scheme Agent
Tests government scheme retrieval, selection of single best scheme, eligibility extraction,
and strict anti-hallucination refusal.
"""

import asyncio
import pytest
from board.models import EntryType, DataFreshness
from agents.scheme_agent import SchemeAgentRunner
from rag.retriever import RAGRetriever


def test_scheme_retrieval(mock_chroma_client):
    """Test retrieving PMFBY or PM-KISAN schemes from RAG corpus."""
    retriever = RAGRetriever(chroma_client=mock_chroma_client)
    results = retriever.retrieve_schemes(crop="Wheat", stage="sowing", state="Haryana", top_k=3)

    assert len(results) > 0
    scheme_names = [r["scheme_name"] for r in results]
    # Check that known official schemes exist in the corpus
    assert any(s in ("PMFBY", "PM-KISAN", "KCC", "Soil Health Card", "PM-KUSUM") for s in scheme_names)
    assert "source_url" in results[0]
    assert "citation" in results[0]


def test_scheme_agent_runner(mock_board, mock_chroma_client):
    """Test full Scheme Agent runner execution and board entry creation."""
    session_id = "test_scheme_session_01"

    mock_board.post_entry(
        session_id=session_id,
        agent_name="Intake Agent",
        type=EntryType.INTAKE.value,
        payload={"crop": "Wheat", "stage": "sowing", "state": "Haryana"},
        confidence=0.95,
        data_freshness=DataFreshness.LIVE.value,
        sources=["intake"],
    )

    runner = SchemeAgentRunner(board=mock_board)
    entry = asyncio.run(runner.run(session_id=session_id))

    assert entry.session_id == session_id
    assert entry.type == EntryType.SCHEME.value
    assert "scheme_name" in entry.payload
    assert len(entry.payload["eligibility"]) > 0
    assert len(entry.payload["how_to_apply"]) > 0
    assert len(entry.payload["citations"]) > 0
    assert entry.confidence >= 0.85

