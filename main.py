import os
import threading
import asyncio

import discord
from discord.ext import commands

from nmcore.config import TOKEN
from nmcore.db import init_db
from nmcore.dashboard import create_app
from nmcore.bot_setup import setup_bot
from nmcore.services.settings import ensure_guild


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


async def safe_startup_guild_sync():
    """
    Do not block Discord heartbeat with SQLite writes.
    This runs guild setup in a worker thread and skips if DB is busy.
    """
    for guild in list(bot.guilds):
        try:
            await asyncio.wait_for(
                asyncio.to_thread(ensure_guild, guild.id, guild.name),
                timeout=2.0
            )
        except Exception:
            pass


@bot.event
async def on_ready():
    try:
        await safe_startup_guild_sync()
    except Exception:
        pass

    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced globally: {len(synced)}")
    except Exception as e:
        print(f"⚠️ Slash sync skipped: {type(e).__name__}: {e}")

    print(f"✅ NM System V9 ready as {bot.user} | guilds={len(bot.guilds)}")


def run_dashboard(app):
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("TOKEN env var is missing")

    init_db()
    setup_bot(bot)

    app = create_app(bot)
    threading.Thread(target=run_dashboard, args=(app,), daemon=True).start()

    bot.run(TOKEN)
