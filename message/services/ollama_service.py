import json
import logging
from typing import Any, Callable, Dict, List, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when the Ollama API cannot be reached or returns an error."""


class OllamaService:
    """HTTP client for the Ollama chat API (cloud or self-hosted) with tool-calling support."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or getattr(settings, "OLLAMA_KEY", "")
        if not self.api_key:
            raise OllamaError(
                "Ollama API key is missing. Ensure OLLAMA_KEY is set in settings/.env."
            )
        self.base_url = (
            base_url or getattr(settings, "OLLAMA_BASE_URL", "https://ollama.com")
        ).rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_MODEL", "gpt-oss:20b")
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT_SECONDS", 60)

    def chat(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Single non-streaming chat completion request."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        if response.status_code != 200:
            raise OllamaError(
                f"Ollama API returned {response.status_code}: {response.text[:500]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise OllamaError(f"Ollama API returned invalid JSON: {exc}") from exc

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        execute_tool: Callable[[str, Dict[str, Any]], str],
        max_tool_calls: Optional[int] = None,
    ) -> str:
        """Run a chat conversation, executing tool calls until the model returns a final reply.

        Follows the Ollama tool-calling protocol: assistant messages containing
        tool_calls are appended to history, each call is executed via
        ``execute_tool`` (which must return a string result), and results are
        appended as ``{"role": "tool", "tool_name": ..., "content": ...}``
        before the next API call.
        """
        if max_tool_calls is None:
            max_tool_calls = getattr(settings, "AI_MAX_TOOL_CALLS", 5)

        history = list(messages)
        tools = tools or []
        tool_calls_made = 0

        while True:
            response = self.chat(history, tools=tools)
            message = response.get("message") or {}
            tool_calls = message.get("tool_calls") or []

            if not tool_calls:
                return (message.get("content") or "").strip()

            if tool_calls_made >= max_tool_calls:
                logger.warning(
                    "Ollama hit the tool-call limit (%s) without a final answer",
                    max_tool_calls,
                )
                return (message.get("content") or "").strip()

            history.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name") or ""
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except (ValueError, TypeError):
                        arguments = {}

                try:
                    result = execute_tool(name, arguments)
                except Exception as exc:  # noqa: BLE001 - tool failures must not kill the reply
                    logger.warning("Tool %s raised: %s", name, exc)
                    result = json.dumps({"error": str(exc)})

                history.append(
                    {"role": "tool", "tool_name": name, "content": str(result)}
                )
                tool_calls_made += 1
