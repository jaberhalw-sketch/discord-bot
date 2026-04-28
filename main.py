import discord
from discord.ext import commands
import random
from datetime import timedelta
import os
import json
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

SUPPORT_WAITING_VOICE_ID = 1300051682809483294
SUPPORT_CHAT_ID = 1498683004703215796
ADMIN_ROLE_ID = 1300049199332720652
LEAVE_LOG_CHANNEL_ID = 1498690187427844137

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = ["قواد", "خنيث", "قحبه", "قحبة", "شرموط", "سالب", "كس", "كس امك", "طيزي", "اه", "كسي", "انيكك", "انيك", "ازغب", "جرار", "bitch", "معرس", "اعرسك", "ممحون", "محنه", "محنة", "العقه", "العقة", "قضي", "زبي", "فقحة", "زبري", "عيري", "منيكه", "bitch"]

WARNINGS_FILE = "warnings.json"


def load_warnings():
    try:
        with open(WARNINGS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {}


def save_warnings():
    with open(WARNINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(warnings, file, indent=4, ensure_ascii=False)


warnings = load_warnings()


async def apply_punishment(member, channel, count):
    try:
        if count == 2:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=5))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 5 دقائق 🔇")

        elif count == 3:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=30))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 30 دقيقة 🔇")

        elif count >= 4:
            await member.timeout(discord.utils.utcnow() + timedelta(days=1))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت يوم كامل 🔇")

    except Exception as e:
        await channel.send(f"ما قدرت أعطي تايم أوت. السبب: `{e}`")


def add_warning(member, reason, message_text, moderator):
    user_id = str(member.id)

    if user_id not in warnings:
        warnings[user_id] = []

    warning_data = {
        "reason": reason,
        "message": message_text,
        "moderator": moderator,
        "time": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    warnings[user_id].append(warning_data)
    save_warnings()

    return len(warnings[user_id])


app = Flask("")


@app.route("/")
def home():
    return "I'm alive"


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.start()


@bot.event
async def on_ready():
    print(f"Bot is online: {bot.user}")


@bot.event
async def on_member_remove(member):
    log_channel = bot.get_channel(LEAVE_LOG_CHANNEL_ID)
    if not log_channel:
        return

    reason = "خرج من نفسه"
    executor = "غير معروف"

    try:
        async for entry in member.guild.audit_logs(limit=5):
            if entry.target and entry.target.id == member.id:
                if entry.action == discord.AuditLogAction.ban:
                    reason = "باند"
                    executor = entry.user.mention
                    break
                elif entry.action == discord.AuditLogAction.kick:
                    reason = "طرد"
                    executor = entry.user.mention
                    break
    except:
        pass

    roles = [role.mention for role in member.roles if role.name != "@everyone"]
    roles_text = "\n".join(roles) if roles else "ما كان معه رولات"

    embed = discord.Embed(title="📤 عضو خرج من السيرفر", color=discord.Color.red())
    embed.add_field(name="👤 العضو", value=f"{member.mention}\n`{member.name}`", inline=False)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="🚪 طريقة الخروج", value=reason, inline=True)
    embed.add_field(name="👮 بواسطة", value=executor, inline=True)
    embed.add_field(name="🎭 الرولات", value=roles_text, inline=False)

    if member.joined_at:
        embed.add_field(
            name="📅 دخل السيرفر",
            value=f"<t:{int(member.joined_at.timestamp())}:F>",
            inline=False
        )

    embed.set_thumbnail(url=member.display_avatar.url)
    await log_channel.send(embed=embed)


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if after.channel and after.channel.id == SUPPORT_WAITING_VOICE_ID:
        support_chat = bot.get_channel(SUPPORT_CHAT_ID)
        admin_role = member.guild.get_role(ADMIN_ROLE_ID)

        if support_chat and admin_role:
            await support_chat.send(
                f"{admin_role.mention}\n"
                f"🚨 في شخص دخل انتظار الدعم الفني!\n"
                f"👤 العضو: {member.mention}\n"
                f"🎧 الروم: {after.channel.mention}"
            )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    for word in bad_words:
        if word in content:
            old_message = message.content
            await message.delete()

            count = add_warning(
                member=message.author,
                reason="كلمة ممنوعة / سب",
                message_text=old_message,
                moderator="النظام التلقائي"
            )

            await message.channel.send(
                f"{message.author.mention} أخذت تحذير رقم {count} 🚫",
                delete_after=6
            )

            await apply_punishment(message.author, message.channel, count)
            return

    if "سلام" in content:
        await message.channel.send("وعليكم السلام 👋")

    await bot.process_commands(message)


@bot.command(name="بنق", aliases=["ping"])
async def ping(ctx):
    await ctx.send("Pong 👑")


@bot.command(name="هلا", aliases=["hello"])
async def hello(ctx):
    await ctx.send(f"هلا والله {ctx.author.mention} 🔥")


@bot.command(name="طقطق", aliases=["roast"])
async def roast(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    roasts = [
        "ذكاء اصطناعي وأنا مستغرب منك 😂",
        "وجودك لحاله حدث نادر 💀",
        "ياخي أنت glitch في الحياة 😂",
        "لو الكسل بطولة كان أخذت المركز الأول 👑",
        "حتى البوت احتار كيف يرد عليك 💀"
    ]

    await ctx.send(f"{member.mention} {random.choice(roasts)}")


@bot.command(name="تقييم", aliases=["rate"])
async def rate(ctx, *, thing="أنت"):
    await ctx.send(f"تقييمي لـ {thing}: {random.randint(1, 10)}/10 😂")


@bot.command(name="مسح", aliases=["clear"])
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"تم حذف {amount} رسالة ✅", delete_after=3)


@bot.command(name="قفل", aliases=["lock"])
@commands.has_permissions(administrator=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("تم قفل الروم 🔒")


@bot.command(name="فتح", aliases=["unlock"])
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("تم فتح الروم 🔓")


@bot.command(name="تحذير", aliases=["warn"])
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason="بدون سبب"):
    count = add_warning(
        member=member,
        reason=reason,
        message_text="تحذير يدوي من الإدارة",
        moderator=f"{ctx.author} ({ctx.author.id})"
    )

    await ctx.send(
        f"{member.mention} أخذ تحذير 🚫\n"
        f"السبب: {reason}\n"
        f"عدد التحذيرات الآن: {count}"
    )

    await apply_punishment(member, ctx.channel, count)


@bot.command(name="تحذيرات", aliases=["warnings"])
@commands.has_permissions(administrator=True)
async def warnings_count(ctx, member: discord.Member):
    user_id = str(member.id)
    user_warnings = warnings.get(user_id, [])

    if not user_warnings:
        await ctx.send(f"{member.mention} ما عليه أي تحذيرات ✅")
        return

    embed = discord.Embed(
        title=f"🚫 تحذيرات {member.name}",
        description=f"عدد التحذيرات: **{len(user_warnings)}**",
        color=discord.Color.orange()
    )

    for i, warn_data in enumerate(user_warnings[-10:], start=1):
        embed.add_field(
            name=f"تحذير #{i}",
            value=(
                f"**السبب:** {warn_data.get('reason', 'غير معروف')}\n"
                f"**الرسالة:** {warn_data.get('message', 'غير معروف')}\n"
                f"**بواسطة:** {warn_data.get('moderator', 'غير معروف')}\n"
                f"**الوقت:** `{warn_data.get('time', 'غير معروف')}`"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="تصفير", aliases=["resetwarnings"])
@commands.has_permissions(administrator=True)
async def resetwarnings(ctx, member: discord.Member):
    user_id = str(member.id)
    warnings[user_id] = []
    save_warnings()
    await ctx.send(f"تم تصفير إنذارات {member.mention} ✅")


keep_alive()
bot.run(TOKEN)
