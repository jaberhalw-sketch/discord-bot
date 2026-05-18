import os
import threading
import discord
from discord.ext import commands

from nmcore.config import TOKEN, PREFIX, BOT_BRAND
from nmcore.db import init_db
from nmcore.dashboard import create_app
from nmcore.bot_setup import setup_bot
from nmcore.services.settings import ensure_guild

if not TOKEN:
    raise RuntimeError("Missing TOKEN environment variable")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
app = create_app(bot)

@bot.event
async def on_ready():
    init_db()
    for guild in bot.guilds:
        ensure_guild(guild.id, guild.name)
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash commands synced globally: {len(synced)}")
    except Exception as e:
        print(f"⚠️ Slash sync skipped: {type(e).__name__}: {e}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name=f"{BOT_BRAND} V9")
    )
    print(f"✅ {BOT_BRAND} V9 ready as {bot.user} | guilds={len(bot.guilds)}")

setup_bot(bot)

def run_dashboard():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)

if __name__ == "__main__":
    threading.Thread(target=run_dashboard, daemon=True).start()
    bot.run(TOKEN)
