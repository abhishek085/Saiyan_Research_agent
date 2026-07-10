"""Saiyan Research Agent — standalone harness.

Public API::

    from harness import Agent
    agent = Agent()
    result = agent.run("search for X")
"""

from __future__ import annotations

from .harness import Agent, AgentResult
from .models import ModelProvider, get_client
from .tool_registry import ToolRegistry, get_tool_registry
from .system_prompt import build_system_prompt, DEFAULT_SYSTEM_PROMPT

__all__ = [
    "Agent",
    "AgentResult",
    "ModelProvider",
    "get_client",
    "ToolRegistry",
    "get_tool_registry",
    "build_system_prompt",
    "DEFAULT_SYSTEM_PROMPT",
]