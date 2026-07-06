"""Discord bot layer for the Saiyan Research Agent.

Uses the harness/ package internally instead of reimplementing the agent loop.
All Discord-specific stuff (bot, commands, message handling) stays here;
the harness provides the core Agent with tools, model, and reasoning bank.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from harness import Agent  # Core agent from harness
from tools.discord_tool import set_bot  # Register bot for send_discord_message

import discord
from discord.ext import commands

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Discord Bot Setup ──────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── Helper: Create Agent Instance ─────────────────────────────────────────

def _create_agent() -> Agent:
    """Create the Agent instance using harness config."""
    model_provider = os.getenv(
        "MODEL_PROVIDER",
        os.getenv("LMSTUDIO_PROVIDER", None),
    )
    agent_name = os.getenv("AGENT_NAME", "Son Goku")
    return Agent(
        model_provider=model_provider,
        agent_name=agent_name,
        block_discord_current_channel=True,
    )


# ─── Post-Processing ────────────────────────────────────────────────────────

async def _post_process_reasoning_bank(
    agent: Agent,
    user_message: str,
    response: str,
    tool_errors: list[str],
) -> None:
    """Phase 2+3: distill one memory item and persist it (runs in background)."""
    try:
        import core.reasoning_bank as reasoning_bank

        item = await asyncio.to_thread(
            reasoning_bank.distill, user_message, response, tool_errors
        )
        if item:
            await asyncio.to_thread(reasoning_bank.save, item)
            logger.info(
                "ReasoningBank saved [%s]: %.80s",
                item["outcome"],
                item["summary"],
            )
    except Exception as exc:
        logger.warning("ReasoningBank post-processing failed: %s", exc)


# ─── Discord Events ─────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    agent = _create_agent()
    set_bot(bot)
    logger.info(
        "✅ %s is online as %s (tools=%d, provider=%s)",
        agent.agent_name,
        bot.user,
        len(agent.available_tools),
        agent._provider.client.base_url,
    )


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mention = bot.user.mentioned_in(message)

    if not (is_dm or is_mention):
        return

    user_id = str(message.author.id)
    user_text = message.content.replace(f"<@{bot.user.id}>", "").strip()

    if not user_text:
        await message.reply("Hey! What can I help with?")
        return

    agent = _create_agent()

    # ── Built-in commands ──
    if user_text.lower() == "!clear":
        agent.clear_history(user_id)
        await message.reply("🧹 Conversation history cleared.")
        return

    if user_text.lower() == "!save":
        try:
            from tools.notion import create_subpage
            from datetime import datetime

            summary = agent.get_history()
            history_text = "\n".join(
                f"{m.get('role', '?')}: {m.get('content', '')[:300]}"
                for m in summary[-20:]
            )
            result = create_subpage(
                title=f"Chat Log {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                content=history_text or "No messages.",
            )
            await message.reply(f"💾 Saved to Notion: {result}")
        except Exception as exc:
            logger.error("!save failed: %s", exc)
            await message.reply(f"⚠️ Could not save to Notion: {exc}")
        return

    if user_text.lower() == "!history":
        summary = agent.get_history()
        lines = [
            f"{m.get('role', '?')}: {m.get('content', '')[:100]}"
            for m in summary[-10:]
        ]
        reply_text = "\n".join(lines) if lines else "No history yet."
        await message.reply(f"📜 Last 10 messages:\n{reply_text}")
        return

    # ── Main agent via harness ──
    async with message.channel.typing():
        result = await asyncio.to_thread(
            agent.run_sync,
            user_text,
            user_id=user_id,
        )

    # Split long responses for Discord's 2000-char limit
    response_text = result.response
    for i in range(0, min(len(response_text), 4000), 1900):
        await message.reply(response_text[i : i + 1900])

    # ── Post-process reasoning bank in background ──
    asyncio.create_task(
        _post_process_reasoning_bank(agent, user_text, response_text, result.tool_errors)
    )

    await bot.process_commands(message)


def main():
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        raise RuntimeError("DISCORD_TOKEN is not set")
    bot.run(discord_token)


if __name__ == "__main__":
    main()