"""
Microsoft Agent Framework - OpenAI Provider Integration
Provides OpenAIChatCompletionClient and OpenAIChatClient wrappers.
"""

from typing import Optional, Dict, Any


class OpenAIChatCompletionClient:
    """
    OpenAI Chat Completion client for Microsoft Agent Framework.
    Supports both OpenAI and Azure OpenAI endpoints.
    """
    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs


class OpenAIChatClient(OpenAIChatCompletionClient):
    """Alias for OpenAIChatCompletionClient."""
    pass
