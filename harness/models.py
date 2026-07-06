"""Model abstraction layer for the Saiyan Research Agent harness.

Provides a provider-agnostic OpenAI-compatible client that works with
LM Studio, Ollama, OpenRouter, OpenAI, and any other OpenAI-compatible
API endpoint.

Usage::

    from harness.models import get_client, ModelProvider
    client = get_client(provider="openai")
    response = client.chat.completions.create(...)
"""

from __future__ import annotations

import os
import logging
from typing import Literal

from openai import OpenAI

from config import ModelConfig, get_config

logger = logging.getLogger(__name__)

Provider = Literal["lmstudio", "ollama", "openrouter", "openai"]

# Provider-specific base URLs when no explicit URL is set.
_PROVIDER_DEFAULTS: dict[str, str] = {
    "lmstudio": "http://localhost:1234/v1",
    "ollama": "http://localhost:11434/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
}

_PROVIDER_API_KEY_DEFAULTS: dict[str, str] = {
    "lmstudio": "lm-studio",
    "ollama": "ollama",
    "openrouter": "sk-or-proxy-",
    "openai": "sk-",
}


def _resolve_provider_cfg(provider: str | None = None) -> ModelConfig:
    """Return a ModelConfig with all fields populated.

    Priority (highest → lowest):
    1. Explicit provider override keyword argument
    2. config.py global singleton (loaded from env)
    3. Hardcoded defaults
    """
    cfg = get_config()

    # Override provider if requested
    if provider:
        cfg.model.provider = provider

    p = cfg.model.provider

    base_url = cfg.model.base_url
    if not base_url or base_url in _PROVIDER_DEFAULTS.values():
        base_url = _PROVIDER_DEFAULTS.get(p, _PROVIDER_DEFAULTS["lmstudio"])

    api_key = cfg.model.api_key
    default_key = _PROVIDER_API_KEY_DEFAULTS.get(p, "none")
    if not api_key or api_key == default_key:
        api_key = os.environ.get(f"{p.upper()}_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

    model_name = cfg.model.model
    model_env_key = f"{p.upper()}_MODEL"
    if (not model_name or model_name == "local-model") and model_env_key in os.environ:
        model_name = os.environ[model_env_key]

    return ModelConfig(
        provider=p,
        base_url=base_url,
        api_key=api_key,
        model=model_name,
        temperature=cfg.model.temperature,
        max_tokens=cfg.model.max_tokens,
    )


def get_client(provider: str | None = None, **extra_kwargs) -> OpenAI:
    """Return an OpenAI-compatible client configured for the given provider.

    Args:
        provider: Provider name override (lmstudio | ollama | openrouter | openai).
                  If None, uses the config file value.
        **extra_kwargs: Additional keyword arguments forwarded to the OpenAI constructor
                       (e.g., timeout, organization, project).

    Returns:
        Configured openai.OpenAI instance.
    """
    cfg = _resolve_provider_cfg(provider)

    kwargs = extra_kwargs.copy()

    # Only set api_key if non-empty (some providers accept a bare key, some don't)
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key

    # Set a non-empty api_key even for providers that don't require it;
    # OpenAI SDK requires a non-empty value.
    if not kwargs.get("api_key"):
        kwargs["api_key"] = _PROVIDER_API_KEY_DEFAULTS.get(cfg.provider, "none")

    client = OpenAI(base_url=cfg.base_url, **kwargs)

    logger.info(
        "Model client initialised — provider=%s, base_url=%s, model=%s",
        cfg.provider,
        cfg.base_url,
        cfg.model,
    )

    return client


class ModelProvider:
    """Convenience wrapper around a configured OpenAI client.

    Provides :meth:`chat` as a thin shortcut that matches the OpenAI SDK
    interface while using the harness-configured client.
    """

    def __init__(self, provider: str | None = None, **client_kwargs):
        self._client = get_client(provider, **client_kwargs)

    @property
    def client(self) -> OpenAI:
        return self._client

    def chat(self, **kwargs):
        """Run a chat completion.

        Merges default temperature / max_tokens from config when not
        explicitly provided in ``kwargs``.
        """
        cfg = _resolve_provider_cfg()

        # Merge in defaults that weren't overridden
        if "temperature" not in kwargs:
            kwargs["temperature"] = cfg.temperature
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = cfg.max_tokens

        return self._client.chat.completions.create(**kwargs)