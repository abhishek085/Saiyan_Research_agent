import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
import discord
from discord.ext import commands

from tools.search import search_web
from tools.x_scraper import scrape_x_post
from tools.content_writer import write_linkedin_post, write_substack_note, write_substack_post, write_short_note
from tools.notion import (
    search_workspace, read_page, read_root_page, inspect_workspace, query_database,
    create_subpage, create_database, add_to_database,
    append_to_page, archive_page, archive_database,
    create_task_list, add_calendar_entry
)
from tools.drive import list_drive_files
from tools.discord_tool import set_bot, send_discord_message
from tools.memory import get_history, add_message, clear_history, get_summary
from tools.url_reader import read_url
import core.reasoning_bank as reasoning_bank

# ─── CLIENTS ──────────────────────────────────────────────────────────────────

lm = OpenAI(
    base_url=os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"),
    api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio")
)
MODEL = os.getenv("MODEL", "local-model")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AGENT_NAME = os.getenv("AGENT_NAME", "Son Goku")

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are {AGENT_NAME}, a local AI agent , your persona is a research assistant. You have access to various tools to help you with tasks, but you must use them wisely and only when necessary.

Your capabilities:
- Search the web using SearxNG for public internet pages
- Scrape X/Twitter posts
- Write LinkedIn posts, Substack notes, full Substack posts, and short bullet notes
- Read any Notion page or database shared with the Notion integration
- Traverse the shared Notion workspace tree including subpages and page mentions
- Write only inside the configured Notion root page
- Create native Notion task lists with checkboxes
- Add calendar entries with proper date fields to Notion databases
- List and search Google Drive files
- Send Discord messages to specific channels

Rules:
- Notion pages are internal workspace documents — do not confuse with Google Drive or public web
- When asked to inspect everything in Notion, use inspect_workspace or read_root_page
- When asked about links inside a Notion page, use read_page with follow_links enabled
- When a user pastes any URL (http/https), always call read_url first to fetch its content before answering
- For X/Twitter URLs specifically, use scrape_x_post instead of read_url to get a cleaner output
- When asked to create a task list, always use create_task_list for native Notion checkboxes
- When adding calendar entries, always use add_calendar_entry with a YYYY-MM-DD date
- Never use send_discord_message to answer in the same chat — reply normally instead
- When someone shares an X link → scrape it → understand → offer LinkedIn post, Substack note, or short note
- Save important outputs to Notion only when it helps the task — do NOT auto-save every reply
- Be concise and fast
- If unsure of a page or database ID, use search_workspace first
- Never use send_discord_message to answer in the same chat — reply normally instead
- Only use send_discord_message when explicitly asked to post to a different channel ID
- Never write outside the root Notion page
- When asked to create a task or to-do list, always use create_task_list for native checkboxes
- When adding calendar entries, always use add_calendar_entry with a YYYY-MM-DD date"""

# ─── TOOL SCHEMA ──────────────────────────────────────────────────────────────

TOOLS = [
    {"type": "function", "function": {
        "name": "search_web", "description": "Search the web for current information",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    }},
    {"type": "function", "function": {
    "name": "read_url",
    "description": "Fetch and read content from any pasted URL — articles, web pages, GitHub repos, docs, etc.",
    "parameters": {"type": "object", "properties": {
        "url": {"type": "string"}
    }, "required": ["url"]}
}},
    {"type": "function", "function": {
        "name": "scrape_x_post", "description": "Scrape text from a public X or Twitter URL",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "write_linkedin_post", "description": "Write a LinkedIn post about a topic",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}, "context": {"type": "string"}
        }, "required": ["topic"]}
    }},
    {"type": "function", "function": {
        "name": "write_substack_post", "description": "Write a full long-form Substack newsletter post about a topic",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}, "context": {"type": "string"}
        }, "required": ["topic"]}
    }},
    {"type": "function", "function": {
        "name": "write_substack_note", "description": "Write a short Substack newsletter note",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}, "context": {"type": "string"}
        }, "required": ["topic"]}
    }},
    {"type": "function", "function": {
        "name": "write_short_note", "description": "Write a short bullet-point summary note",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}, "context": {"type": "string"}
        }, "required": ["topic"]}
    }},
    {"type": "function", "function": {
        "name": "search_workspace",
        "description": "Search or list Notion pages and databases shared with the integration. Leave query empty to list all accessible items.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "page_size": {"type": "integer"}
        }}
    }},
    {"type": "function", "function": {
        "name": "read_page",
        "description": "Read a Notion page by ID and optionally follow subpages and linked page mentions inside it.",
        "parameters": {"type": "object", "properties": {
            "page_id": {"type": "string"},
            "max_depth": {"type": "integer"},
            "follow_links": {"type": "boolean"}
        }, "required": ["page_id"]}
    }},
    {"type": "function", "function": {
        "name": "read_root_page", "description": "Read everything inside the bot's shared Notion root page",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "inspect_workspace",
        "description": "Inspect the shared Notion workspace tree from the root page, including subpages and linked pages.",
        "parameters": {"type": "object", "properties": {
            "max_depth": {"type": "integer"}
        }}
    }},
    {"type": "function", "function": {
        "name": "query_database", "description": "Query rows in any Notion database with optional status filter",
        "parameters": {"type": "object", "properties": {
            "database_id": {"type": "string"}, "filter_status": {"type": "string"}
        }, "required": ["database_id"]}
    }},
    {"type": "function", "function": {
        "name": "create_subpage", "description": "Create a subpage inside the bot's root write page",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "content": {"type": "string"}
        }, "required": ["title"]}
    }},
    {"type": "function", "function": {
        "name": "create_database", "description": "Create a database inside the bot's root write page",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}
    }},
    {"type": "function", "function": {
        "name": "add_to_database", "description": "Add a row to a database inside root page",
        "parameters": {"type": "object", "properties": {
            "database_id": {"type": "string"}, "title": {"type": "string"},
            "content": {"type": "string"}, "status": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}}
        }, "required": ["database_id", "title"]}
    }},
    {"type": "function", "function": {
        "name": "append_to_page", "description": "Append content to any page inside root",
        "parameters": {"type": "object", "properties": {
            "page_id": {"type": "string"}, "content": {"type": "string"}
        }, "required": ["page_id", "content"]}
    }},
    {"type": "function", "function": {
        "name": "create_task_list",
        "description": "Create a native Notion to-do/task list page with checkboxes inside the root page",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "tasks": {"type": "array", "items": {"type": "string"}}
        }, "required": ["title", "tasks"]}
    }},
    {"type": "function", "function": {
        "name": "add_calendar_entry",
        "description": "Add a dated entry to a Notion calendar database with a proper date field",
        "parameters": {"type": "object", "properties": {
            "database_id": {"type": "string"},
            "title": {"type": "string"},
            "date": {"type": "string", "description": "Format: YYYY-MM-DD"},
            "notes": {"type": "string"},
            "status": {"type": "string"}
        }, "required": ["database_id", "title", "date"]}
    }},
    {"type": "function", "function": {
        "name": "archive_page", "description": "Archive a Notion page",
        "parameters": {"type": "object", "properties": {"page_id": {"type": "string"}}, "required": ["page_id"]}
    }},
    {"type": "function", "function": {
        "name": "archive_database", "description": "Archive a Notion database",
        "parameters": {"type": "object", "properties": {"database_id": {"type": "string"}}, "required": ["database_id"]}
    }},
    {"type": "function", "function": {
        "name": "list_drive_files", "description": "List or search files in Google Drive",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
    }},
    {"type": "function", "function": {
        "name": "send_discord_message", "description": "Send a message to a different Discord channel by ID — never use for the current chat",
        "parameters": {"type": "object", "properties": {
            "channel_id": {"type": "string"}, "message": {"type": "string"}
        }, "required": ["channel_id", "message"]}
    }},
]

# ─── TOOL MAP ─────────────────────────────────────────────────────────────────

TOOL_MAP = {
    "search_web":             lambda a: search_web(a["query"]),
    "read_url": lambda a: read_url(a["url"]),
    "scrape_x_post":          lambda a: scrape_x_post(a["url"]),
    "write_linkedin_post":    lambda a: write_linkedin_post(a["topic"], a.get("context", "")),
    "write_substack_note":    lambda a: write_substack_note(a["topic"], a.get("context", "")),
    "write_substack_post":    lambda a: write_substack_post(a["topic"], a.get("context", "")),
    "write_short_note":       lambda a: write_short_note(a["topic"], a.get("context", "")),
    "search_workspace":       lambda a: search_workspace(a.get("query", ""), a.get("page_size", 20)),
    "read_page":              lambda a: read_page(a["page_id"], a.get("max_depth", 2), a.get("follow_links", True)),
    "read_root_page":         lambda _: read_root_page(),
    "inspect_workspace":      lambda a: inspect_workspace(a.get("max_depth", 2)),
    "query_database":         lambda a: query_database(a["database_id"], a.get("filter_status", "")),
    "create_subpage":         lambda a: create_subpage(a["title"], a.get("content", "")),
    "create_database":        lambda a: create_database(a["title"]),
    "add_to_database":        lambda a: add_to_database(a["database_id"], a["title"], a.get("content", ""), a.get("status", "Todo"), a.get("tags")),
    "append_to_page":         lambda a: append_to_page(a["page_id"], a["content"]),
    "create_task_list":       lambda a: create_task_list(a["title"], a["tasks"]),
    "add_calendar_entry":     lambda a: add_calendar_entry(a["database_id"], a["title"], a["date"], a.get("notes", ""), a.get("status", "Todo")),
    "archive_page":           lambda a: archive_page(a["page_id"]),
    "archive_database":       lambda a: archive_database(a["database_id"]),
    "list_drive_files":       lambda a: list_drive_files(a.get("query", "")),
    "send_discord_message":   lambda a: send_discord_message(a["channel_id"], a["message"]),
}

# ─── AGENT LOOP ───────────────────────────────────────────────────────────────

def agent_loop_sync(
    user_id: str,
    user_message: str,
    current_channel_id: str | None = None,
) -> tuple[str, list[str]]:
    """Run the agent loop and return (response, tool_errors)."""
    history = get_history(user_id)

    # ── Phase 1: Retrieve relevant strategies and prepend to system prompt ──
    retrieved = reasoning_bank.retrieve(user_message, top_k=3)
    strategy_block = reasoning_bank.format_strategies_for_prompt(retrieved)
    effective_system = SYSTEM_PROMPT
    if strategy_block:
        effective_system = strategy_block + "\n\n" + SYSTEM_PROMPT
        print(f"🧠 ReasoningBank injected {len(retrieved)} strateg{'y' if len(retrieved)==1 else 'ies'}.")

    messages = [{"role": "system", "content": effective_system}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    tool_errors: list[str] = []

    for round_num in range(25):
        completion = lm.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.2,
            max_tokens=4096
        )
        msg = completion.choices[0].message

        if not msg.tool_calls:
            final = msg.content or "Done."
            add_message(user_id, "user", user_message)
            add_message(user_id, "assistant", final)
            return final, tool_errors

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
        })

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if tc.function.name == "send_discord_message":
                target_channel_id = str(args.get("channel_id", "")).strip()
                if current_channel_id and target_channel_id == current_channel_id:
                    result = "Blocked: cannot send to the current channel. Reply normally instead."
                else:
                    result = send_discord_message(args["channel_id"], args["message"])
            else:
                handler = TOOL_MAP.get(tc.function.name, lambda _: f"Unknown tool: {tc.function.name}")
                result = handler(args)

            result_str = str(result)
            print(f"🔧 [{round_num}] {tc.function.name}({args}) → {result_str[:120]}")
            low = result_str.lower().strip()
            error_prefixes = (
                "error",
                "search error",
                "url read error",
                "youtube read error",
                "blocked:",
                "unknown tool:",
            )
            if low.startswith(error_prefixes):
                tool_errors.append(f"{tc.function.name}: {result_str[:200]}")
            messages.append({
                "role": "tool",
                "content": result_str,
                "tool_call_id": tc.id
            })

    return "Reached max tool rounds — task may be incomplete.", tool_errors

# ─── DISCORD BOT ──────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
set_bot(bot)

@bot.event
async def on_ready():
    print(f"✅ {AGENT_NAME} is online as {bot.user}")
    print(f"🔍 SearxNG: {os.getenv('SEARXNG_URL')}")

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

    # ── Built-in commands ──
    if user_text.lower() == "!clear":
        clear_history(user_id)
        await message.reply("🧹 Conversation history cleared.")
        return

    if user_text.lower() == "!save":
        summary = get_summary(user_id)
        result = create_subpage(
            title=f"Chat Log {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            content=summary
        )
        await message.reply(f"💾 Saved to Notion: {result}")
        return

    if user_text.lower() == "!history":
        summary = get_summary(user_id)
        await message.reply(f"📜 Last 10 messages:\n{summary}" if summary else "No history yet.")
        return

    # ── Main agent ──
    async with message.channel.typing():
        response, tool_errors = await asyncio.to_thread(
            agent_loop_sync, user_id, user_text, str(message.channel.id)
        )

    for i in range(0, min(len(response), 4000), 1900):
        await message.reply(response[i:i+1900])

    # ── Phase 2+3: distill and save to ReasoningBank in background ──
    asyncio.create_task(_post_process_reasoning_bank(user_text, response, tool_errors))

    await bot.process_commands(message)


async def _post_process_reasoning_bank(
    user_message: str,
    response: str,
    tool_errors: list[str],
) -> None:
    """Phase 2+3: distill one memory item and persist it (runs in background)."""
    try:
        item = await asyncio.to_thread(
            reasoning_bank.distill, user_message, response, tool_errors
        )
        if item:
            await asyncio.to_thread(reasoning_bank.save, item)
            print(f"🧠 ReasoningBank saved [{item['outcome']}]: {item['summary'][:80]}")
    except Exception as exc:
        print(f"⚠️  ReasoningBank post-processing failed: {exc}")


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()