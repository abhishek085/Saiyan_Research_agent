_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

def send_discord_message(channel_id: str, message: str) -> str:
    import asyncio
    if _bot:
        channel = _bot.get_channel(int(channel_id))
        if channel:
            asyncio.create_task(channel.send(message[:2000]))
            return "✅ Sent!"
    return "Bot not ready."