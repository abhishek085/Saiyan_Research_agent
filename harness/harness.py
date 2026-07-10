"""Core Agent class — standalone agent loop with tool use.

Public API::

    from harness import Agent
    agent = Agent()
    result = agent.run("search for X")
    # or streaming:
    for chunk in agent.run_stream("write a Substack post about Y"):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Iterator

from config import get_config
from .models import ModelProvider
from .tool_registry import get_tool_registry, ToolRegistry
from .system_prompt import build_system_prompt

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────


@dataclass
class AgentResult:
    """Structured result from a single agent run."""

    response: str
    tool_errors: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, str]] = field(default_factory=list)
    rounds_used: int = 0
    reasoning_strategies_injected: int = 0
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "tool_errors": self.tool_errors,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "rounds_used": self.rounds_used,
            "reasoning_strategies_injected": self.reasoning_strategies_injected,
            "truncated": self.truncated,
        }

    def to_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), indent=indent)


# ──────────────────────────────────────────────────────────────────────
# Error-detection helpers
# ──────────────────────────────────────────────────────────────────────

_TOOL_ERROR_PREFIXES = (
    "error",
    "search error",
    "url read error",
    "youtube read error",
    "blocked:",
    "unknown tool:",
    "tool error",
    "scrape error",
)


def _is_error_result(text: str) -> bool:
    return any(text.lower().strip().startswith(p) for p in _TOOL_ERROR_PREFIXES)


# ──────────────────────────────────────────────────────────────────────
# Main Agent class
# ──────────────────────────────────────────────────────────────────────


class Agent:
    """Standalone research agent that runs tool-enabled loops.

    Can be used without any Discord dependency.

    Args:
        user_id: Unique user identifier for history tracking.
        model_provider: Provider override (lmstudio | ollama | openrouter | openai).
        agent_name: Display name for the agent persona.
        extra_instructions: Free-text instructions appended to system prompt.
        max_tool_rounds: Maximum tool-use iterations per user turn.
        block_discord_current_channel: Block send_discord_message to current channel.

    Example::

        agent = Agent()
        result = agent.run("What's new with Ollama?")
        print(result.response)
    """

    def __init__(
        self,
        user_id: str = "local",
        model_provider: str | None = None,
        agent_name: str = "Son Goku",
        extra_instructions: str = "",
        max_tool_rounds: int = 25,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        block_discord_current_channel: bool = True,
    ):
        self.user_id = user_id
        self.agent_name = agent_name
        self.extra_instructions = extra_instructions
        self.max_tool_rounds = max_tool_rounds
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Model provider — exposed as .provider for CLI / main.py
        self._provider = ModelProvider(provider=model_provider)

        # Tool registry — exposed as .registry for CLI / agent.py
        self._registry: ToolRegistry = get_tool_registry(
            block_discord_current_channel=block_discord_current_channel,
        )

        # Current channel for Discord blocking
        self._current_channel_id: str | None = None

        # Default model from config (cached at init time)
        self._default_model: str | None = None
        cfg = get_config()
        model_name = cfg.model.model
        if model_name and model_name != "local-model":
            self._default_model = model_name

        # Base system prompt (built once; strategies prepended at run time)
        self._base_system_prompt = build_system_prompt(
            agent_name=agent_name,
            extra_instructions=extra_instructions,
        )

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def provider(self) -> ModelProvider:
        """Access the underlying model provider."""
        return self._provider

    @property
    def registry(self) -> ToolRegistry:
        """Access the underlying tool registry."""
        return self._registry

    @property
    def available_tools(self) -> list[str]:
        """List of available tool names."""
        return self._registry.tool_names

    # ── Public methods ─────────────────────────────────────────────────

    def run(
        self,
        user_message: str,
        user_id: str | None = None,
        current_channel_id: str | None = None,
    ) -> AgentResult:
        """Run the agent loop and return structured result.

        Args:
            user_message: The user's prompt/query.
            user_id: Override for history tracking (defaults to init value).
            current_channel_id: If set, blocks send_discord_message to this channel.

        Returns:
            AgentResult with response, tool_errors, tool_calls, metadata.
        """
        uid = user_id or self.user_id
        self._current_channel_id = current_channel_id
        if current_channel_id is not None:
            self._registry.set_current_channel(current_channel_id)
        return self.run_sync(user_message, user_id=uid)

    def run_sync(
        self,
        user_message: str,
        user_id: str | None = None,
    ) -> AgentResult:
        """Blocking agent loop.

        Returns AgentResult with response, tool_calls_used, tool_errors, rounds.
        """
        from tools.memory import get_history, add_message

        uid = user_id or self.user_id

        # Phase 1: Retrieve strategies from reasoning bank and build system prompt
        import core.reasoning_bank as reasoning_bank

        retrieved = reasoning_bank.retrieve(user_message, top_k=3)
        strategy_block = reasoning_bank.format_strategies_for_prompt(retrieved)
        effective_system = self._base_system_prompt
        if strategy_block:
            effective_system = strategy_block + "\n\n" + effective_system
            logger.info(
                "ReasoningBank injected %d strategy/%s.",
                len(retrieved),
                "y" if len(retrieved) == 1 else "ies",
            )

        # Build message history
        history = get_history(uid)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": effective_system},
            *history,
            {"role": "user", "content": user_message},
        ]

        # Get tool schemas for the model
        tools = self._registry.list_schemas()

        tool_calls_list: list[dict[str, Any]] = []
        tool_results_list: list[dict[str, str]] = []
        tool_errors: list[str] = []

        for round_num in range(self.max_tool_rounds):
            # Use cached default model; fall back to provider list discovery if none set.
            model_name = self._default_model
            if model_name is None:
                try:
                    models_list = self._provider.client.models.list()
                    if models_list and models_list.data:
                        model_name = models_list.data[0].id
                except Exception:
                    model_name = None

            completion = self._provider.chat(
                model=model_name,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            msg = completion.choices[0].message

            # No tool call → final response
            if not msg.tool_calls:
                final = msg.content or "Done."
                add_message(uid, "user", user_message)
                add_message(uid, "assistant", final)
                return AgentResult(
                    response=final,
                    tool_errors=tool_errors,
                    tool_calls=tool_calls_list,
                    tool_results=tool_results_list,
                    rounds_used=round_num + 1,
                    reasoning_strategies_injected=len(retrieved),
                )

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })

            # Execute each tool call
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                tool_calls_list.append({
                    "name": tc.function.name,
                    "arguments": args,
                    "tool_call_id": tc.id,
                })

                result_str = self._registry.call(tc.function.name, args)
                result_str_clean = str(result_str)

                logger.debug(
                    "[Round %d] %s(%s) → %.100s",
                    round_num,
                    tc.function.name,
                    json.dumps(args, default=str),
                    result_str_clean,
                )

                # Track errors
                if _is_error_result(result_str_clean):
                    tool_errors.append(
                        f"{tc.function.name}: {result_str_clean[:200]}"
                    )

                tool_results_list.append({
                    "tool_call_id": tc.id,
                    "result": result_str_clean[:2000],
                })

                # Append tool result
                messages.append({
                    "role": "tool",
                    "content": result_str_clean,
                    "tool_call_id": tc.id,
                })

        return AgentResult(
            response="Reached max tool rounds — task may be incomplete.",
            tool_errors=tool_errors,
            tool_calls=tool_calls_list,
            tool_results=tool_results_list,
            rounds_used=self.max_tool_rounds,
            reasoning_strategies_injected=len(retrieved),
            truncated=True,
        )

    def run_stream(self, user_message: str) -> Iterator[str]:
        """Run the agent loop, yielding text chunks as they are produced.

        NOTE: This is a simplified streaming version. The real LLM output
        streaming depends on the provider's API — here we yield the
        final response after the full loop completes.
        """
        result = self.run_sync(user_message)
        yield result.response

    def add_message(self, role: str, content: str) -> None:
        """Add a message to this agent's conversation history."""
        from tools.memory import add_message
        add_message(self.user_id, role, content)

    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history."""
        from tools.memory import get_history
        return get_history(self.user_id)

    def clear_history(self, user_id: str | None = None) -> None:
        """Clear conversation history."""
        from tools.memory import clear_history
        clear_history(user_id or self.user_id)

    def __repr__(self) -> str:
        return (
            f"Agent(user_id={self.user_id!r}, agent_name={self.agent_name!r}, "
            f"tools={len(self._registry.tool_names)} available)"
        )


# ── Convenience functions ─────────────────────────────────────────────


def run_agent(
    user_message: str,
    user_id: str = "local",
    provider: str | None = None,
    agent_name: str = "Son Goku",
) -> AgentResult:
    """One-shot agent run. Convenience wrapper around Agent().run().

    Usage::

        from harness import run_agent
        result = run_agent("search for latest AI news")
        print(result.response)
    """
    agent = Agent(
        user_id=user_id,
        model_provider=provider,
        agent_name=agent_name,
    )
    return agent.run(user_message)


# ── Legacy alias for backwards compatibility with agent.py / tests ──


def agent_loop_sync(
    user_id: str,
    user_message: str,
    current_channel_id: str | None = None,
    model_provider: str | None = None,
) -> tuple[str, list[str]]:
    """Legacy function that mirrors the original agent_loop_sync signature.

    This provides backwards compatibility for code that calls the original
    agent_loop_sync (from agent.py and tests). It internally creates an
    Agent instance and returns the legacy (response, tool_errors) tuple.
    """
    agent = Agent(
        model_provider=model_provider,
        block_discord_current_channel=bool(current_channel_id),
    )
    result = agent.run(user_message, user_id=user_id, current_channel_id=current_channel_id)
    return result.response, result.tool_errors