import discord
from discord.ext import commands
import random
from datetime import timedelta
import os

TOKEN = os.getenv("TOKEN")

SUPPORT_WAITING_VOICE_ID = 123456789012345678
SUPPORT_CHAT_ID = 123456789012345678
ADMIN_ROLE_ID = 123456789012345678

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = ["سب"]
warnings = {}

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

@bot.event
async def on_ready():
    print(f"Bot is online: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    for word in bad_words:
        if word in content:
            await message.delete()

            user_id = message.author.id
            warnings[user_id] = warnings.get(user_id, 0) + 1
            count = warnings[user_id]

            await message.channel.send(
                f"{message.author.mention} تحذير رقم {count} 🚫",
                delete_after=5
            )

            return

    if "سلام" in content:
        await message.channel.send("وعليكم السلام 👋")

    await bot.process_commands(message)

@bot.command()
async def ping(ctx):
    await ctx.send("Pong 👑")

@bot.command()
async def hello(ctx):
    await ctx.send(f"هلا والله {ctx.author.mention} 🔥")

@bot.command()
async def roast(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    roasts = ["😂😂", "💀💀"]

    await ctx.send(f"{member.mention} {random.choice(roasts)}")

@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)

keep_alive()
bot.run(TOKEN)
