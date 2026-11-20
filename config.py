"""
Agricultural Advisory Control Room - Configuration & LLM Factory
Microsoft Agent Framework (package: agent-framework v1.25.0)

API Verification:
- Client: agent_framework.openai.OpenAIChatCompletionClient
  Verified from official microsoft/agent-framework repository:
  python/packages/core/agent_framework/openai/_chat_client.py
- Observability: agent_framework.observability.configure_otel_providers, get_tracer
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Windows sandbox asyncio compatibility: use SelectorEventLoop to avoid socketpair blocks
if sys.platform == "win32":
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Load .env file
load_dotenv()

# LLM Provider Configuration
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY: Optional[str] = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT: Optional[str] = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

# External APIs
DATA_GOV_IN_API_KEY: str = os.getenv("DATA_GOV_IN_API_KEY", "")

# Control Room Operational Parameters
AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "30"))
AGENT_MAX_RETRIES: int = int(os.getenv("AGENT_MAX_RETRIES", "2"))
AGENT_BACKOFF_FACTOR: float = float(os.getenv("AGENT_BACKOFF_FACTOR", "1.5"))

# Storage Configuration
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "advisory_board.db")
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Observability Configuration
ENABLE_OTEL_TRACING: bool = os.getenv("ENABLE_OTEL_TRACING", "true").lower() in ("true", "1", "yes")
OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "agricultural-advisory-control-room")


def get_model_client():
    """
    Constructs and returns the Microsoft Agent Framework model client
    configured for either OpenAI or Azure OpenAI based on environment variables.

    Verified import path: agent_framework.openai.OpenAIChatCompletionClient
    """
    from agent_framework.openai import OpenAIChatCompletionClient  # [VERIFIED: agent-framework v1.25.0]

    if LLM_PROVIDER == "azure_openai":
        if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
            raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set when LLM_PROVIDER='azure_openai'.")
        return OpenAIChatCompletionClient(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            api_key=AZURE_OPENAI_API_KEY,
            base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}",
        )
    else:
        if not OPENAI_API_KEY:
            # Fallback warning for local dry-runs / mocking
            api_key = "dummy-key-for-mock"
        else:
            api_key = OPENAI_API_KEY
        return OpenAIChatCompletionClient(
            model=OPENAI_MODEL,
            api_key=api_key,
        )


def init_observability():
    """
    Initializes OpenTelemetry tracing through Microsoft Agent Framework's
    built-in observability layer.

    Verified import path: agent_framework.observability.configure_otel_providers
    """
    if ENABLE_OTEL_TRACING:
        try:
            from agent_framework.observability import configure_otel_providers  # [VERIFIED: agent-framework v1.25.0]
            configure_otel_providers()
        except ImportError:
            # If opentelemetry exporters are not configured in environment, skip gracefully
            pass

