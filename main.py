#!/usr/bin/env python3
"""Saiyan Research Agent — entry point.

Usage:
    # Run standalone CLI (no Discord)
    python main.py --prompt "What's new with Ollama?"
    python main.py --interactive
    python main.py --provider openrouter --model mistral-large

    # Start the Discord bot
    python main.py --discord
"""

from __future__ import annotations

import argparse
import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def demo_harness_import() -> None:
    """Show that the harness can be imported and used standalone."""
    from harness import Agent

    print("=" * 60)
    print("  Saiyan Research Agent — Harness Demo")
    print("=" * 60)
    print()
    print("The harness package provides a standalone agent that works")
    print("without Discord. Here's how to use it:")
    print()

    # Import and create agent
    agent = Agent()

    print(f"  Agent name:     {agent.agent_name}")
    print(f"  Available tools ({len(agent.available_tools)}):")
    for t in agent.available_tools:
        print(f"    - {t}")
    print()
    print(f"  Provider:       {agent._provider.client.base_url}")
    print()
    print("To run a prompt, use:")
    print('  result = agent.run("your prompt here")')
    print('  print(result.response)')
    print()
    print("For interactive mode, run:")
    print("  python cli.py --interactive")
    print()
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="main",
        description="Saiyan Research Agent — entry point",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run a demo that imports the harness and shows available tools",
    )
    parser.add_argument(
        "--discord", action="store_true",
        help="Start the Discord bot",
    )
    parser.add_argument(
        "--prompt", "-p", type=str,
        help="Send a single prompt to the agent (standalone mode)",
    )
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Run the CLI in interactive mode",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="Model provider override (lmstudio | ollama | openrouter | openai)",
    )
    parser.add_argument(
        "--agent-name", type=str, default=None,
        help="Agent persona name",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose/debug logging",
    )
    parser.add_argument(
        "--config-path", type=str, default=None,
        help="Path to custom .env file",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Custom config path
    if args.config_path:
        from config import get_config
        get_config(env_file=args.config_path)

    # Demo mode
    if args.demo:
        demo_harness_import()
        return

    # Discord mode
    if args.discord:
        print("Starting Discord bot...")
        from agent import main as discord_main
        discord_main()
        return

    # Standalone CLI mode (delegate to cli.py)
    if args.prompt or args.interactive:
        from cli import main as cli_main
        # Reconstruct the original args for cli.py
        cli_args = [sys.argv[0]]
        if args.prompt:
            cli_args += ["--prompt", args.prompt]
        if args.interactive:
            cli_args.append("--interactive")
        if args.provider:
            cli_args += ["--provider", args.provider]
        if args.agent_name:
            cli_args += ["--agent-name", args.agent_name]
        if args.verbose:
            cli_args.append("--verbose")
        if args.config_path:
            cli_args += ["--config-path", args.config_path]

        # Temporarily replace sys.argv so cli.py's argparse works
        old_argv = sys.argv
        try:
            sys.argv = cli_args
            cli_main()
        finally:
            sys.argv = old_argv
        return

    # Default: show demo + usage
    demo_harness_import()
    print("\nUsage:")
    print("  python main.py --demo          # Show harness overview")
    print("  python main.py --discord       # Start Discord bot")
    print("  python main.py --prompt 'hello'  # Standalone prompt")
    print("  python main.py --interactive     # REPL mode")
    print("  python cli.py --help             # Full CLI options")


if __name__ == "__main__":
    main()