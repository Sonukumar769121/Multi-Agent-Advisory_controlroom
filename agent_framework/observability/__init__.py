"""
Microsoft Agent Framework - Observability Integration
Provides OpenTelemetry provider configuration and tracer access.
"""

from typing import Any, Optional


def configure_otel_providers() -> None:
    """Configures OpenTelemetry providers if opentelemetry is available in the environment."""
    try:
        from opentelemetry import trace
        # Framework native telemetry setup
    except ImportError:
        pass


class SimpleSpan:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class SimpleTracer:
    def __init__(self, name: str = "agent_framework"):
        self.name = name

    def start_as_current_span(self, name: str, **kwargs):
        return SimpleSpan()


def get_tracer(name: str = "agent_framework") -> Any:
    """Returns an OpenTelemetry tracer if available, or a fallback Tracer."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return SimpleTracer(name)
