import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"BOT IS READY: {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong ✅")

if not TOKEN:
    raise RuntimeError("TOKEN is missing")

bot.run(TOKEN)
