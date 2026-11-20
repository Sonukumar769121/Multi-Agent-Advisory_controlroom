"""
Pytest Fixtures & Recorded Payloads
Provides mock responses for external APIs and isolated in-memory Advisory Boards.
"""

import sys
import pytest

# Windows sandbox asyncio compatibility patch for pytest
if sys.platform == "win32":
    try:
        import socket
        _pair = socket.socketpair()
        _pair[0].close()
        _pair[1].close()
    except Exception:
        from asyncio.proactor_events import BaseProactorEventLoop

        class _DummySocket:
            def fileno(self): return -1
            def setblocking(self, b): pass
            def send(self, b): return len(b)
            def recv(self, n): return b""
            def close(self): pass

        BaseProactorEventLoop._make_self_pipe = lambda self: (
            setattr(self, "_ssock", _DummySocket()),
            setattr(self, "_csock", _DummySocket()),
        )
        BaseProactorEventLoop._loop_self_reading = lambda self, f=None: None
        BaseProactorEventLoop._write_to_self = lambda self: None

from board.advisory_board import AdvisoryBoard, set_advisory_board
from rag.ingest import get_chroma_client, seed_rag_collections


@pytest.fixture
def mock_board():
    """Provides a fresh, isolated in-memory Advisory Board for testing."""
    board = AdvisoryBoard(db_path=":memory:")
    set_advisory_board(board)
    return board


@pytest.fixture
def mock_chroma_client():
    """Provides an in-memory ChromaDB client with seeded collections."""
    client = get_chroma_client(persist_directory=":memory:")
    seed_rag_collections(client)
    return client


@pytest.fixture
def recorded_geocoding_response():
    """Recorded Open-Meteo geocoding response for 'Karnal, Haryana'."""
    return {
        "results": [
            {
                "id": 1267438,
                "name": "Karnal",
                "latitude": 29.6857,
                "longitude": 76.9905,
                "elevation": 253.0,
                "feature_code": "PPLA2",
                "country_code": "IN",
                "admin1_id": 1270260,
                "admin2_id": 1267437,
                "timezone": "Asia/Kolkata",
                "country": "India",
                "admin1": "Haryana",
                "admin2": "Karnal",
            }
        ],
        "generationtime_ms": 0.35,
    }


@pytest.fixture
def recorded_weather_response_dry():
    """Recorded Open-Meteo 7-day forecast representing dry conditions."""
    return {
        "latitude": 29.6857,
        "longitude": 76.9905,
        "generationtime_ms": 0.45,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 253.0,
        "daily": {
            "time": ["2024-11-12", "2024-11-13", "2024-11-14", "2024-11-15", "2024-11-16", "2024-11-17", "2024-11-18"],
            "temperature_2m_max": [27.5, 28.1, 28.4, 27.9, 27.2, 26.8, 26.5],
            "temperature_2m_min": [14.2, 14.8, 15.1, 14.5, 13.9, 13.5, 13.0],
            "precipitation_sum": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "precipitation_probability_max": [5.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0],
            "wind_speed_10m_max": [11.2, 10.5, 9.8, 12.4, 10.1, 9.5, 8.9],
        },
        "hourly": {
            "relative_humidity_2m": [55.0] * 168,
        },
    }


@pytest.fixture
def recorded_weather_response_rainy():
    """Recorded Open-Meteo 7-day forecast representing heavy rainfall (32 mm)."""
    return {
        "latitude": 29.6857,
        "longitude": 76.9905,
        "daily": {
            "time": ["2024-11-12", "2024-11-13", "2024-11-14", "2024-11-15", "2024-11-16", "2024-11-17", "2024-11-18"],
            "temperature_2m_max": [24.0, 22.5, 23.0, 24.5, 25.0, 26.0, 26.5],
            "temperature_2m_min": [16.0, 15.5, 15.0, 14.5, 14.0, 14.0, 13.5],
            "precipitation_sum": [18.5, 10.0, 3.5, 0.0, 0.0, 0.0, 0.0],
            "precipitation_probability_max": [85.0, 75.0, 40.0, 10.0, 5.0, 0.0, 0.0],
            "wind_speed_10m_max": [22.4, 18.2, 14.0, 11.0, 9.5, 8.0, 7.5],
        },
        "hourly": {
            "relative_humidity_2m": [82.0] * 168,
        },
    }


@pytest.fixture
def recorded_agmarknet_wheat_response():
    """Recorded Agmarknet (data.gov.in) response for Wheat in Karnal APMC."""
    return {
        "status": "ok",
        "total": 3,
        "count": 3,
        "limit": "50",
        "offset": "0",
        "records": [
            {
                "state": "Haryana",
                "district": "Karnal",
                "market": "Karnal",
                "commodity": "Wheat",
                "variety": "Other",
                "arrival_date": "10/11/2024",
                "min_price": "2400",
                "max_price": "2520",
                "modal_price": "2475",
            },
            {
                "state": "Haryana",
                "district": "Karnal",
                "market": "Karnal",
                "commodity": "Wheat",
                "variety": "Other",
                "arrival_date": "03/11/2024",
                "min_price": "2380",
                "max_price": "2490",
                "modal_price": "2440",
            },
            {
                "state": "Haryana",
                "district": "Karnal",
                "market": "Karnal",
                "commodity": "Wheat",
                "variety": "Other",
                "arrival_date": "20/10/2024",
                "min_price": "2350",
                "max_price": "2450",
                "modal_price": "2400",
            },
        ],
    }


@pytest.fixture
def recorded_agmarknet_empty_response():
    """Recorded Agmarknet response returning zero records."""
    return {
        "status": "ok",
        "total": 0,
        "count": 0,
        "limit": "50",
        "offset": "0",
        "records": [],
    }

