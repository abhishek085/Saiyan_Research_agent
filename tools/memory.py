# tools/memory.py
import os
from collections import defaultdict
from openai import OpenAI

_histories = defaultdict(list)
MAX_HISTORY = 40        # messages before compression triggers
KEEP_RECENT = 10        # always keep last N messages verbatim
SUMMARY_THRESHOLD = 30  # compress when history exceeds this

def _get_lm():
    return OpenAI(
        base_url=os.getenv("LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"),
        api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    )

def get_history(user_id: str) -> list:
    return _histories[user_id]

def add_message(user_id: str, role: str, content: str):
    _histories[user_id].append({"role": role, "content": content})
    # Auto-compress if over threshold
    if len(_histories[user_id]) >= SUMMARY_THRESHOLD:
        _compress_history(user_id)

def _compress_history(user_id: str):
    """Summarize older messages, keep recent ones verbatim"""
    history = _histories[user_id]
    if len(history) < SUMMARY_THRESHOLD:
        return

    older = history[:-KEEP_RECENT]   # messages to compress
    recent = history[-KEEP_RECENT:]  # messages to keep verbatim

    # Build summary of older messages
    convo_text = "\n".join([f"{m['role'].upper()}: {m['content'][:300]}" for m in older])
    try:
        lm = _get_lm()
        resp = lm.chat.completions.create(
            model=os.getenv("MODEL", "local-model"),
            messages=[{
                "role": "user",
                "content": f"""Summarize this conversation history into a compact context block (max 300 words).
Keep: key decisions, facts, task results, user preferences, any IDs or links mentioned.
Drop: small talk, redundant info, tool errors.

Conversation:
{convo_text}

Output only the summary."""
            }],
            temperature=0.1,
            max_tokens=400
        )
        summary_text = resp.choices[0].message.content.strip()
        compressed = {"role": "system", "content": f"[Previous conversation summary]: {summary_text}"}
        _histories[user_id] = [compressed] + recent
        print(f"🧠 Compressed history for {user_id}: {len(older)} → 1 summary block")
    except Exception as e:
        # Fallback: just trim older messages if LM fails
        _histories[user_id] = recent
        print(f"⚠️ History compression failed ({e}), trimmed to last {KEEP_RECENT}")

def clear_history(user_id: str):
    _histories[user_id] = []

def get_summary(user_id: str) -> str:
    history = _histories[user_id]
    if not history:
        return "No conversation history."
    lines = [f"{m['role'].upper()}: {m['content'][:100]}" for m in history[-10:]]
    return "\n".join(lines)

def history_size(user_id: str) -> int:
    return len(_histories[user_id])