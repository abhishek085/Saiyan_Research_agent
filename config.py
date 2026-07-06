"""Config management for Saiyan Research Agent.

Loads settings from:
  1. `.env` file (pydantic BaseModel)
  2. Environment variables (overrides)
  3. Optional YAML config file (overrides env vars)

Usage:
    from config import Config
    cfg = Config()
    print(cfg.model)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(default="lmstudio", description="Provider: lmstudio | ollama | openrouter | openai")
    base_url: str = Field(default="http://localhost:1234/v1", description="API base URL")
    api_key: str = Field(default="lm-studio", description="API key")
    model: str = Field(default="local-model", description="Model name/ID")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Default generation temperature")
    max_tokens: int = Field(default=4096, ge=1, description="Max tokens per completion")


class ReasoningBankConfig(BaseModel):
    """ReasoningBank memory configuration."""

    enabled: bool = Field(default=True)
    top_k: int = Field(default=3, ge=1, le=10, description="Number of strategies to retrieve")
    embedding_model: str = Field(default="nomic-embed-text-v1.5", description="Embedding model name")
    distill_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    judge_temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class AgentConfig(BaseModel):
    """Agent persona and behavior."""

    name: str = Field(default="Son Goku", description="Agent display name")
    system_prompt: str = Field(default="", description="System prompt (empty = use default)")
    max_tool_rounds: int = Field(default=25, ge=1, le=100, description="Max tool-use iterations per turn")
    compress_history_threshold: int = Field(default=30, ge=5, description="Compress history when messages exceed this")
    keep_recent: int = Field(default=10, ge=1, description="Always keep last N messages verbatim")


class DiscordConfig(BaseModel):
    """Discord bot configuration."""

    enabled: bool = Field(default=True)
    token: str = Field(default="", description="Discord bot token")
    log_channel_id: str = Field(default="", description="Channel to log agent activity")
    prefix: str = Field(default="!", description="Bot command prefix")


class NotionConfig(BaseModel):
    """Notion integration configuration."""

    enabled: bool = Field(default=False)
    api_key: str = Field(default="", description="Notion integration API key")
    parent_page_id: str = Field(default="", description="Root page for write operations")


class GoogleDriveConfig(BaseModel):
    """Google Drive integration configuration."""

    enabled: bool = Field(default=False)
    credentials_file: str = Field(default="credentials.json", description="OAuth credentials path")
    token_file: str = Field(default="token.pickle", description="OAuth token cache path")


class SearxNGConfig(BaseModel):
    """Search engine configuration."""

    enabled: bool = Field(default=True)
    url: str = Field(default="http://localhost:8080", description="SearxNG instance URL")
    fallback: str = Field(default="duckduckgo", description="Fallback when SearxNG fails: duckduckgo | none")


class Config(BaseModel):
    """Top-level configuration. Loads from .env, env vars, and optional YAML."""

    model: ModelConfig = Field(default_factory=ModelConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    notion: NotionConfig = Field(default_factory=NotionConfig)
    drive: GoogleDriveConfig = Field(default_factory=GoogleDriveConfig)
    search: SearxNGConfig = Field(default_factory=SearxNGConfig)
    reasoning_bank: ReasoningBankConfig = Field(default_factory=ReasoningBankConfig)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Config":
        """Load config from .env file and environment variables.

        Priority (highest wins):
        1. Actual environment variables
        2. .env file values
        3. Pydantic defaults
        """
        if env_file:
            load_dotenv(str(env_file), override=True)
        else:
            # Try common locations
            candidates = [".env", str(Path.home() / ".saiyan" / ".env")]
            for candidate in candidates:
                if Path(candidate).exists():
                    load_dotenv(candidate, override=False)
                    break

        # Build model-level env var overrides
        model_env: dict[str, Any] = {}
        for key, val in os.environ.items():
            if key.startswith("MODEL_"):
                model_env[key[6:].lower()] = val

        agent_env: dict[str, Any] = {}
        for key, val in os.environ.items():
            if key.startswith("AGENT_"):
                agent_env[key[6:].lower()] = val

        # Backwards compat: LMSTUDIO_* -> model.base_url / model.api_key
        if "LMSTUDIO_BASE_URL" in os.environ:
            model_env.setdefault("base_url", os.environ["LMSTUDIO_BASE_URL"])
        if "LMSTUDIO_API_KEY" in os.environ:
            model_env.setdefault("api_key", os.environ["LMSTUDIO_API_KEY"])
        if "MODEL_NAME" in os.environ:
            model_env.setdefault("model", os.environ["MODEL_NAME"])

        # Backwards compat: SEARXNG_URL -> search.url
        search_env: dict[str, Any] = {}
        if "SEARXNG_URL" in os.environ:
            search_env.setdefault("url", os.environ["SEARXNG_URL"])

        # ─── Build each sub-config from env vars ───
        notion_env: dict[str, Any] = {}
        for key, val in os.environ.items():
            if key.startswith("NOTION_"):
                notion_env[key[7:].lower()] = val

        drive_env: dict[str, Any] = {}
        for key, val in os.environ.items():
            if key.startswith("GOOGLE_"):
                drive_env[key[7:].lower()] = val

        discord_env: dict[str, Any] = {}
        if "DISCORD_TOKEN" in os.environ:
            discord_env["token"] = os.environ["DISCORD_TOKEN"]
        if "DISCORD_LOG_CHANNEL_ID" in os.environ:
            discord_env["log_channel_id"] = os.environ["DISCORD_LOG_CHANNEL_ID"]

        reasoning_env: dict[str, Any] = {}
        if "EMBEDDING_MODEL" in os.environ:
            reasoning_env["embedding_model"] = os.environ["EMBEDDING_MODEL"]

        # Build the top-level config
        return cls(
            model=ModelConfig(**model_env),
            agent=AgentConfig(**agent_env),
            notion=NotionConfig(**notion_env),
            drive=GoogleDriveConfig(**drive_env),
            search=SearxNGConfig(**search_env),
            discord=DiscordConfig(**discord_env),
            reasoning_bank=ReasoningBankConfig(**reasoning_env),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load config from a YAML file, merging with environment variables."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required for YAML config: pip install pyyaml")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        merged: dict[str, Any] = {}
        for key, value in data.items():
            env_key = f"{key.upper()}_{'_'.join(k.upper() for k in value.keys())}" if isinstance(value, dict) else ""
            merged[key] = {k: v for k, v in value.items()}

        return cls(**merged)


# Global singleton
_config: Config | None = None


def get_config(env_file: str | Path | None = None) -> Config:
    """Get the global config singleton."""
    global _config
    if _config is None:
        _config = Config.from_env(env_file)
    return _config


def reset_config():
    """Reset the global config (useful for testing)."""
    global _config
    _config = None