#!/usr/bin/env python3
"""Standalone CLI for the Saiyan Research Agent harness.

Usage::

    # Simple prompt
    python cli.py --prompt "What's new with Ollama?"

    # JSON output
    python cli.py --prompt "What's new with Ollama?" --json

    # Interactive mode
    python cli.py --interactive

    # Write a LinkedIn post
    python cli.py --prompt "Write a LinkedIn post about AI agents" --format linkedin

    # Use a different model provider
    python cli.py --prompt "Search for X" --provider openrouter

    # Custom config file
    python cli.py --prompt "hello" --config-path /path/to/.env

    # Set agent name
    python cli.py --prompt "hello" --agent-name "Vegeta"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap

from config import get_config
from harness import Agent


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy debug logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def cmd_run(agent: Agent, args: argparse.Namespace) -> None:
    """Execute a single prompt and print the result."""
    prompt = args.prompt

    # If format is specified, append a format instruction
    extra = ""
    if args.format:
        format_instructions = {
            "linkedin": "\n\nFormat the output as a LinkedIn post.",
            "substack": "\n\nFormat the output as a full Substack newsletter post.",
            "substack-note": "\n\nFormat the output as a short Substack note.",
            "short-note": "\n\nFormat the output as a short bullet-point summary note.",
            "json": "\n\nFormat the output as a JSON object.",
            "markdown": "\n\nFormat the output in markdown.",
        }
        extra = format_instructions.get(args.format, "")

    effective_prompt = prompt + extra
    print(f"\n🔍 Running agent (provider: {agent._provider.client.base_url})")

    result = agent.run(effective_prompt)

    # Print the main response
    print(f"\n{'='*60}")
    print(f"✅ Response ({result.rounds_used} rounds, {len(result.tool_calls)} tool calls)")
    print(f"{'='*60}")
    print(result.response)

    # Print tool errors if any
    if result.tool_errors:
        print(f"\n⚠️  {len(result.tool_errors)} tool error(s):")
        for err in result.tool_errors:
            print(f"   - {err[:200]}")

    if args.json_output:
        output = {
            "response": result.response,
            "tool_calls": result.tool_calls,
            "tool_errors": result.tool_errors,
            "tool_results": result.tool_results,
            "rounds_used": result.rounds_used,
            "truncated": result.truncated,
        }
        print(f"\n--- JSON ---\n{json.dumps(output, indent=2)}")


def cmd_interactive(agent: Agent) -> None:
    """Run the agent in interactive chat mode."""
    config = get_config()

    print("=" * 60)
    print(f"  Saiyan Research Agent — {config.agent.name}")
    print(f"  Provider: {agent._provider.client.base_url}")
    print(f"  Model:    {config.model.model}")
    print(f"  Tools:    {len(agent.available_tools)}")
    print(f"  Type 'quit' or 'exit' to leave, 'clear' to reset chat.")
    print("=" * 60)

    user_id = "interactive-cli"

    while True:
        try:
            prompt = input("\n🔹 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not prompt:
            continue

        if prompt.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        if prompt.lower() in ("clear", "reset", "/clear", "/reset"):
            agent.clear_history()
            print("Chat history cleared.")
            continue

        if prompt.lower() == "/tools":
            names = agent.available_tools
            print(f"\n🔧 Available tools ({len(names)}):")
            for name in names:
                print(f"   - {name}")
            continue

        if prompt.lower() == "/config":
            print(f"\n📋 Configuration:")
            print(f"   Provider:       {config.model.provider}")
            print(f"   Base URL:       {config.model.base_url}")
            print(f"   Model:          {config.model.model}")
            print(f"   Temperature:    {config.model.temperature}")
            print(f"   Max Tokens:     {config.model.max_tokens}")
            print(f"   Agent:          {config.agent.name}")
            print(f"   Max Rounds:     {config.agent.max_tool_rounds}")
            continue

        if prompt.lower() == "/reasoning":
            import core.reasoning_bank as rb
            results = rb.retrieve(prompt, top_k=5)
            formatted = rb.format_strategies_for_prompt(results)
            print(f"\n📚 Retrieved {len(results)} reasoning strategies:")
            print(formatted)
            continue

        if prompt.lower() in ("/help", "/h", "?"):
            print(textwrap.dedent("""\
                Commands:
                  /tools      - List available tools
                  /config     - Show current configuration
                  /reasoning  - Show reasoning bank strategies for your query
                  /clear      - Reset chat history
                  /help       - Show this help

                  Type 'quit' or 'exit' to leave.
            """))
            continue

        print(f"\n🔍 Thinking...")
        try:
            result = agent.run(prompt)
        except Exception as exc:
            print(f"\n❌ Error: {exc}")
            continue

        print(f"\n{'='*60}")
        print(f"💡 Response ({result.rounds_used} rounds)")
        print(f"{'='*60}")
        print(result.response)

        if result.tool_errors:
            print(f"\n⚠️  {len(result.tool_errors)} error(s):")
            for err in result.tool_errors:
                print(f"   - {err[:150]}")


def cmd_reasoning_bank(args: argparse.Namespace) -> None:
    """Show reasoning bank strategies."""
    import core.reasoning_bank as rb

    if args.reasoning_bank == "list":
        results = rb.retrieve("research", top_k=20)
        if not results:
            print("No strategies found. The reasoning bank is empty.")
            return
        print(f"Found {len(results)} strategies:\n")
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            description = r.get("description", "")
            print(f"{i}. {title}")
            print(f"   {description[:100]}")
            print()
    elif args.reasoning_bank == "status":
        config = get_config()
        print(f"Reasoning bank status:")
        print(f"  Embedding model: {config.reasoning_bank.embedding_model}")
        print(f"  Enabled: {config.reasoning_bank.enabled}")


def cmd_config() -> None:
    """Print current configuration."""
    config = get_config()
    print("Configuration:")
    print(f"  model.provider:       {config.model.provider}")
    print(f"  model.base_url:       {config.model.base_url}")
    api_key_display = config.model.api_key
    if len(api_key_display) > 8:
        api_key_display = api_key_display[:8] + "..." + api_key_display[-4:]
    else:
        api_key_display = "***"
    print(f"  model.api_key:        {api_key_display}")
    print(f"  model.model:          {config.model.model}")
    print(f"  model.temperature:    {config.model.temperature}")
    print(f"  model.max_tokens:     {config.model.max_tokens}")
    print(f"  agent.name:           {config.agent.name}")
    print(f"  agent.max_tool_rounds: {config.agent.max_tool_rounds}")
    print(f"  discord.enabled:      {config.discord.enabled}")
    print(f"  search.enabled:       {config.search.enabled}")
    print(f"  search.url:           {config.search.url}")
    print(f"  notion.enabled:       {config.notion.enabled}")
    print(f"  drive.enabled:        {config.drive.enabled}")
    print(f"  reasoning_bank.enabled: {config.reasoning_bank.enabled}")
    print(f"  reasoning_bank.top_k:   {config.reasoning_bank.top_k}")
    print(f"  reasoning_bank.embedding_model: {config.reasoning_bank.embedding_model}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cli",
        description="Saiyan Research Agent — standalone CLI harness",
        epilog=textwrap.dedent("""\
            Examples:
              python cli.py --prompt "What's new with Ollama?"
              python cli.py --prompt "Write a LinkedIn post about AI" --format linkedin
              python cli.py --interactive
              python cli.py --provider openrouter
              python cli.py --config
        """),
    )

    parser.add_argument(
        "--prompt", "-p", type=str,
        help="Prompt/query to send to the agent",
    )
    parser.add_argument(
        "--format", "-f", type=str,
        help="Output format: linkedin, substack, substack-note, short-note, json, markdown",
    )
    parser.add_argument(
        "--json", "-j", dest="json_output", action="store_true",
        help="Output structured JSON result",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Run in interactive chat mode",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="Model provider override (lmstudio | ollama | openrouter | openai)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name override",
    )
    parser.add_argument(
        "--agent-name", type=str, default=None,
        help="Agent persona name",
    )
    parser.add_argument(
        "--config", action="store_true",
        help="Show current configuration",
    )
    parser.add_argument(
        "--config-path", type=str, default=None,
        help="Path to custom .env file",
    )
    parser.add_argument(
        "--reasoning-bank", type=str, choices=["list", "status"],
        help="Show reasoning bank information",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose/debug logging",
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Show version",
    )

    args = parser.parse_args()

    if args.version:
        print("Saiyan Research Agent CLI v0.2.0 (mini harness)")
        return

    setup_logging(args.verbose)

    # Load config (possibly from custom path)
    if args.config_path:
        _ = get_config(env_file=args.config_path)

    # Show config only
    if args.config:
        cmd_config()
        return

    if args.reasoning_bank:
        cmd_reasoning_bank(args)
        return

    # Build Agent with any overrides
    kwargs = {}
    if args.provider:
        kwargs["model_provider"] = args.provider
    if args.agent_name:
        kwargs["agent_name"] = args.agent_name

    try:
        agent = Agent(**kwargs)
    except Exception as exc:
        print(f"❌ Failed to create agent: {exc}", file=sys.stderr)
        sys.exit(1)

    # Single prompt mode
    if args.prompt:
        cmd_run(agent, args)
        return

    # Interactive mode
    if args.interactive:
        cmd_interactive(agent)
        return

    # No arguments — show help
    parser.print_help()


if __name__ == "__main__":
    main()