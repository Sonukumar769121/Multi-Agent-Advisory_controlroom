"""
Agricultural Advisory Control Room - Runnable Demo Script
Microsoft Agent Framework (package: agent-framework v1.25.0)

Usage:
    python run_demo.py --crop "Wheat" --location "Karnal, Haryana" --stage "vegetative" --language "en"
    python run_demo.py --crop "Rice" --location "Ludhiana, Punjab" --stage "sowing" --language "pa"
    python run_demo.py --crop "Mustard" --location "Bharatpur, Rajasthan" --stage "flowering" --language "hi"
"""

import argparse
import asyncio
import json
import uuid
import sys
from datetime import datetime

from board.advisory_board import get_advisory_board, AdvisoryBoard
from orchestrator.control_room import ControlRoomOrchestrator
from rag.ingest import get_chroma_client, seed_rag_collections


def format_box_header(title: str, width: int = 80) -> str:
    border = "=" * width
    return f"\n{border}\n  {title.upper()}\n{border}"


def format_entry_box(entry_dict: dict, width: int = 80) -> str:
    line = "-" * width
    payload_str = json.dumps(entry_dict.get("payload", {}), indent=2)
    sources_str = ", ".join(entry_dict.get("sources", []))

    return (
        f"\n+-- [BOARD ENTRY: {entry_dict.get('type')}] "
        f"By: {entry_dict.get('agent_name')} "
        f"| Freshness: {entry_dict.get('data_freshness')} "
        f"| Confidence: {entry_dict.get('confidence')} --+\n"
        f"| Entry ID  : {entry_dict.get('entry_id')}\n"
        f"| Timestamp : {entry_dict.get('timestamp')}\n"
        f"| Status    : {entry_dict.get('status')}\n"
        f"| Sources   : {sources_str}\n"
        f"| Payload   :\n"
        f"{payload_str}\n"
        f"+{line[1:]}"
    )


async def main():
    parser = argparse.ArgumentParser(description="Agricultural Advisory Control Room Demo")
    parser.add_argument("--crop", type=str, default="Wheat", help="Crop name (e.g. Wheat, Rice, Mustard)")
    parser.add_argument("--location", type=str, default="Karnal, Haryana", help="Farmer location / district")
    parser.add_argument("--stage", type=str, default="vegetative", help="Crop stage: sowing, vegetative, flowering, harvest_ready")
    parser.add_argument("--language", type=str, default="en", help="Language: en (English), hi (Hindi), pa (Punjabi)")
    parser.add_argument("--session-id", type=str, default="", help="Optional session ID")
    parser.add_argument("--db-path", type=str, default="advisory_board.db", help="SQLite database path")

    args = parser.parse_args()

    session_id = args.session_id or f"session_{uuid.uuid4().hex[:8]}"

    print(format_box_header("Agricultural Advisory Control Room (Blackboard Architecture)"))
    print(f"Session ID       : {session_id}")
    print(f"Crop Input       : {args.crop}")
    print(f"Location Input   : {args.location}")
    print(f"Growth Stage     : {args.stage}")
    print(f"Advisory Language: {args.language}")
    print(f"Database         : {args.db_path}")

    # 1. Initialize SQLite Advisory Board
    board = AdvisoryBoard(db_path=args.db_path)

    # 2. Seed ChromaDB RAG Knowledge Base
    print("\n[Control Room] Ensuring RAG knowledge collections are seeded...")
    chroma_client = get_chroma_client()
    seed_rag_collections(chroma_client)

    # 3. Instantiate Control Room Orchestrator
    orchestrator = ControlRoomOrchestrator(board=board)

    # 4. Execute Multi-Agent Orchestration
    print("\n[Control Room] Launching agent layer execution...")
    try:
        final_advisory = await orchestrator.run(
            session_id=session_id,
            crop=args.crop,
            location=args.location,
            stage=args.stage,
            language=args.language,
        )
    except Exception as exc:
        print(f"\n[ERROR] Control Room Orchestration failed: {exc}", file=sys.stderr)
        return

    # 5. Display All Advisory Board Entries
    print(format_box_header("Advisory Board Postings (Session Entries)"))
    entries = board.get_entries(session_id=session_id)
    for entry in entries:
        print(format_entry_box(entry.model_dump()))

    # 6. Display Final Advisory
    print(format_box_header("Final Farmer Advisory Output"))
    print(f"Field Action       : {final_advisory.field_action}")
    print(f"Market Timing      : {final_advisory.market_suggestion}")
    print(f"Government Scheme  : {final_advisory.government_scheme}")
    print(f"Data Freshness     : {final_advisory.data_freshness_summary}")
    print(f"Partial Advisory   : {final_advisory.is_partial}")
    if final_advisory.data_gaps:
        print(f"Data Gaps Noted    : {final_advisory.data_gaps}")
    print(f"Word Count         : {final_advisory.word_count} words (Limit: <= 120 words)")
    print("-" * 80)
    print("PLAIN-LANGUAGE ADVISORY:")
    print(final_advisory.advisory_text)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

