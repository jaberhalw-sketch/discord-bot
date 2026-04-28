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

import discord
from discord.ext import commands
import random
from datetime import timedelta
import os
import json
import time
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

# =========================
# IDs عدلها حسب سيرفرك
# =========================
SUPPORT_WAITING_VOICE_ID = 1300051682809483294
SUPPORT_CHAT_ID = 1498683004703215796
ADMIN_ROLE_ID = 1300049199332720652
LEAVE_LOG_CHANNEL_ID = 1498690187427844137
PROTECTION_LOG_CHANNEL_ID = 1498727149388169378

# =========================
# إعدادات الحماية
# =========================
ANTI_LINKS = True
SPAM_LIMIT = 10
SPAM_SECONDS = 5
MASS_MENTION_LIMIT = 10

# =========================
# ثيم البوت: رصاصي + أصفر
# =========================
COLOR_YELLOW = discord.Color.gold()
COLOR_GREY = discord.Color.dark_grey()
COLOR_RED = discord.Color.red()
COLOR_GREEN = discord.Color.green()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = ["قواد", "خنيث", "قحبه", "قحبة", "شرموط", "سالب", "كس", "كس امك", "طيزي", "اه", "كسي", "انيكك", "انيك", "ازغب", "جرار", "bitch", "معرس", "اعرسك", "ممحون", "محنه", "محنة", "العقه", "العقة", "قضي", "زبي", "فقحة", "زبري", "عيري", "منيكه", "bitch"]

WARNINGS_FILE = "warnings.json"

user_message_times = {}
protection_enabled = True


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


def is_admin(member):
    return member.guild_permissions.administrator


async def send_protection_log(guild, member, violation, message_text, punishment):
    log_channel = guild.get_channel(PROTECTION_LOG_CHANNEL_ID)
    if not log_channel:
        return

    embed = discord.Embed(
        title="🛡️ سجل مخالفة حماية",
        color=COLOR_YELLOW
    )
    embed.add_field(name="👤 العضو", value=f"{member.mention}\n`{member.id}`", inline=False)
    embed.add_field(name="⚠️ المخالفة", value=violation, inline=True)
    embed.add_field(name="🔨 العقوبة", value=punishment, inline=True)
    embed.add_field(name="💬 الرسالة", value=f"```{message_text[:900]}```", inline=False)
    embed.add_field(
        name="🕒 الوقت",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
        inline=False
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    await log_channel.send(embed=embed)


async def apply_punishment(member, channel, count):
    try:
        if count == 2:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=5))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 5 دقائق 🔇", delete_after=6)
            return "تايم أوت 5 دقائق"

        elif count == 3:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=30))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 30 دقيقة 🔇", delete_after=6)
            return "تايم أوت 30 دقيقة"

        elif count >= 4:
            await member.timeout(discord.utils.utcnow() + timedelta(days=1))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت يوم كامل 🔇", delete_after=6)
            return "تايم أوت يوم كامل"

        return "تحذير فقط"

    except Exception as e:
        await channel.send(f"ما قدرت أعطي تايم أوت. السبب: `{e}`", delete_after=8)
        return f"فشل التايم أوت: {e}"


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


async def handle_violation(message, reason):
    old_message = message.content

    try:
        await message.delete()
    except:
        pass

    count = add_warning(
        member=message.author,
        reason=reason,
        message_text=old_message,
        moderator="النظام التلقائي"
    )

    embed = discord.Embed(
        title="⚠️ تحذير تلقائي",
        description=f"{message.author.mention} أخذت تحذير رقم **{count}**",
        color=COLOR_YELLOW
    )
    embed.add_field(name="السبب", value=reason, inline=False)

    await message.channel.send(embed=embed, delete_after=8)

    punishment = await apply_punishment(message.author, message.channel, count)

    await send_protection_log(
        guild=message.guild,
        member=message.author,
        violation=reason,
        message_text=old_message,
        punishment=punishment
    )


# =========================
# keep alive
# =========================
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


# =========================
# لوق خروج العضو
# =========================
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

    embed = discord.Embed(
        title="📤 عضو خرج من السيرفر",
        color=COLOR_GREY
    )
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


# =========================
# دعم فني صوتي
# =========================
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if after.channel and after.channel.id == SUPPORT_WAITING_VOICE_ID:
        support_chat = bot.get_channel(SUPPORT_CHAT_ID)
        admin_role = member.guild.get_role(ADMIN_ROLE_ID)

        if support_chat and admin_role:
            embed = discord.Embed(
                title="🎧 طلب دعم فني",
                description="في شخص دخل انتظار الدعم الفني",
                color=COLOR_YELLOW
            )
            embed.add_field(name="👤 العضو", value=member.mention, inline=True)
            embed.add_field(name="🎧 الروم", value=after.channel.mention, inline=True)

            await support_chat.send(content=admin_role.mention, embed=embed)


# =========================
# مراقبة الرسائل
# =========================
@bot.event
async def on_message(message):
    global protection_enabled

    if message.author.bot:
        return

    content = message.content.lower()

    if protection_enabled and not is_admin(message.author):

        # Anti bad words
        for word in bad_words:
            if word in content:
                await handle_violation(message, "كلمة ممنوعة / سب")
                return

        # Anti links
        if ANTI_LINKS:
            link_words = ["http://", "https://", "discord.gg", ".com", ".net", ".gg"]
            if any(link in content for link in link_words):
                await handle_violation(message, "إرسال رابط ممنوع")
                return

        # Anti mass mention
        mentions_count = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            mentions_count += 10

        if mentions_count >= MASS_MENTION_LIMIT:
            await handle_violation(message, f"منشن كثير ({mentions_count})")
            return

        # Anti spam
        user_id = message.author.id
        now = time.time()

        if user_id not in user_message_times:
            user_message_times[user_id] = []

        user_message_times[user_id].append(now)
        user_message_times[user_id] = [
            t for t in user_message_times[user_id]
            if now - t <= SPAM_SECONDS
        ]

        if len(user_message_times[user_id]) >= SPAM_LIMIT:
            user_message_times[user_id] = []
            await handle_violation(message, f"سبام: {SPAM_LIMIT} رسائل خلال {SPAM_SECONDS} ثواني")
            return

    if "سلام" in content:
        await message.channel.send("وعليكم السلام 👋")

    await bot.process_commands(message)


# =========================
# أوامر عامة
# =========================
@bot.command(name="بنق", aliases=["ping"])
async def ping(ctx):
    embed = discord.Embed(
        title="🏓 Pong",
        description="البوت شغال 👑",
        color=COLOR_YELLOW
    )
    await ctx.send(embed=embed)


@bot.command(name="هلا", aliases=["hello"])
async def hello(ctx):
    embed = discord.Embed(
        title="👋 هلا والله",
        description=f"يا مرحبا {ctx.author.mention} 🔥",
        color=COLOR_GREY
    )
    await ctx.send(embed=embed)


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

    embed = discord.Embed(
        title="😂 طقطقة",
        description=f"{member.mention} {random.choice(roasts)}",
        color=COLOR_YELLOW
    )
    await ctx.send(embed=embed)


@bot.command(name="تقييم", aliases=["rate"])
async def rate(ctx, *, thing="أنت"):
    embed = discord.Embed(
        title="⭐ تقييم",
        description=f"تقييمي لـ **{thing}**: **{random.randint(1, 10)}/10** 😂",
        color=COLOR_YELLOW
    )
    await ctx.send(embed=embed)


# =========================
# أوامر الإدارة
# =========================
@bot.command(name="مسح", aliases=["clear"])
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)
    embed = discord.Embed(
        title="🧹 تم المسح",
        description=f"تم حذف **{amount}** رسالة ✅",
        color=COLOR_GREY
    )
    await ctx.send(embed=embed, delete_after=3)


@bot.command(name="قفل", aliases=["lock"])
@commands.has_permissions(administrator=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    embed = discord.Embed(
        title="🔒 تم قفل الروم",
        description="تم منع الأعضاء من الكتابة هنا",
        color=COLOR_RED
    )
    await ctx.send(embed=embed)


@bot.command(name="فتح", aliases=["unlock"])
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    embed = discord.Embed(
        title="🔓 تم فتح الروم",
        description="تم السماح للأعضاء بالكتابة هنا",
        color=COLOR_GREEN
    )
    await ctx.send(embed=embed)


# =========================
# نظام التحذيرات
# =========================
@bot.command(name="تحذير", aliases=["warn"])
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason="بدون سبب"):
    count = add_warning(
        member=member,
        reason=reason,
        message_text="تحذير يدوي من الإدارة",
        moderator=f"{ctx.author} ({ctx.author.id})"
    )

    embed = discord.Embed(
        title="🚫 تحذير إداري",
        description=f"{member.mention} أخذ تحذير",
        color=COLOR_YELLOW
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="عدد التحذيرات الآن", value=str(count), inline=True)

    await ctx.send(embed=embed)

    punishment = await apply_punishment(member, ctx.channel, count)

    await send_protection_log(
        guild=ctx.guild,
        member=member,
        violation=f"تحذير يدوي: {reason}",
        message_text="تحذير يدوي من الإدارة",
        punishment=punishment
    )


@bot.command(name="تحذيرات", aliases=["warnings"])
@commands.has_permissions(administrator=True)
async def warnings_count(ctx, member: discord.Member):
    user_id = str(member.id)
    user_warnings = warnings.get(user_id, [])

    if not user_warnings:
        embed = discord.Embed(
            title="✅ لا يوجد تحذيرات",
            description=f"{member.mention} ما عليه أي تحذيرات",
            color=COLOR_GREEN
        )
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"🚫 تحذيرات {member.name}",
        description=f"عدد التحذيرات: **{len(user_warnings)}**",
        color=COLOR_YELLOW
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

    embed = discord.Embed(
        title="✅ تم التصفير",
        description=f"تم تصفير إنذارات {member.mention}",
        color=COLOR_GREEN
    )
    await ctx.send(embed=embed)


# =========================
# أوامر الحماية
# =========================
@bot.command(name="حماية", aliases=["protection"])
@commands.has_permissions(administrator=True)
async def protection(ctx, mode=None):
    global protection_enabled

    if mode is None:
        status = "مفعلة ✅" if protection_enabled else "مطفية ❌"
        embed = discord.Embed(
            title="🛡️ حالة الحماية",
            description=f"الحماية الآن: **{status}**",
            color=COLOR_YELLOW
        )
        await ctx.send(embed=embed)
        return

    if mode in ["تشغيل", "on"]:
        protection_enabled = True
        await ctx.send("🛡️ تم تشغيل الحماية ✅")
    elif mode in ["ايقاف", "إيقاف", "off"]:
        protection_enabled = False
        await ctx.send("🛡️ تم إيقاف الحماية ❌")
    else:
        await ctx.send("استخدم: `!حماية تشغيل` أو `!حماية إيقاف`")


@bot.command(name="اعدادات", aliases=["settings"])
@commands.has_permissions(administrator=True)
async def settings(ctx):
    embed = discord.Embed(
        title="⚙️ إعدادات الحماية",
        color=COLOR_GREY
    )
    embed.add_field(name="Anti-Link", value="شغال ✅" if ANTI_LINKS else "مغلق ❌", inline=True)
    embed.add_field(name="Spam", value=f"{SPAM_LIMIT} رسائل / {SPAM_SECONDS} ثواني", inline=True)
    embed.add_field(name="Mass Mention", value=f"{MASS_MENTION_LIMIT} منشن", inline=True)
    embed.add_field(name="Protection Log", value=f"<#{PROTECTION_LOG_CHANNEL_ID}>", inline=False)
    await ctx.send(embed=embed)


keep_alive()
bot.run(TOKEN)
