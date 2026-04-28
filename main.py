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

ALLOWED_GUILD_ID = 1300038159446441985

SUPPORT_WAITING_VOICE_ID = 1300051682809483294
SUPPORT_CHAT_ID = 1498683004703215796
SUPPORT_ROLE_ID = 1300049212553302109

LEAVE_LOG_CHANNEL_ID = 1498690187427844137
PROTECTION_LOG_CHANNEL_ID = 1498727149388169378

APPLICATION_CHANNEL_ID = 1498758805914259587
INTERVIEW_VOICE_ROOM_ID = 1498759006024368289
APPLICATION_LOG_CHANNEL_ID = 1498762366962368512

STAFF_MAIN_ROLE_ID = 1300049199332720652

STAFF_ROLE_IDS = {
    1300049171860164658: "ادمن +",
    1300049176545067161: "ادمن",
    1300049177769807882: "مشرف +",
    1300049179426426932: "مشرف",
    1494466779915878494: "مشرف متدرب",
    1300049180877787136: "دعم فني"
}

ANTI_LINKS = True
SPAM_LIMIT = 10
SPAM_SECONDS = 5
MASS_MENTION_LIMIT = 10

COLOR_YELLOW = discord.Color.gold()
COLOR_GREY = discord.Color.dark_grey()
COLOR_RED = discord.Color.red()
COLOR_GREEN = discord.Color.green()
COLOR_BLUE = discord.Color.blue()

WARNINGS_FILE = "warnings.json"
APPLICATIONS_FILE = "applications.json"

user_message_times = {}
protection_enabled = True

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

bad_words = [
    "قواد", "خنيث", "قحبه", "قحبة", "شرموط", "سالب", "كس", "كس امك",
    "طيزي", "كسي", "انيكك", "انيك", "ازغب", "جرار", "bitch",
    "معرس", "اعرسك", "ممحون", "محنه", "محنة", "العقه", "العقة",
    "قضي", "زبي", "فقحة", "زبري", "عيري", "منيكه"
]


def load_json(file_name, default):
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            data = json.load(file)

        if file_name == APPLICATIONS_FILE:
            if not isinstance(data, dict):
                return default
            if "counter" not in data:
                data["counter"] = 0
            if "users" not in data:
                data["users"] = {}

        return data
    except:
        return default


def save_json(file_name, data):
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


warnings = load_json(WARNINGS_FILE, {})
applications_data = load_json(APPLICATIONS_FILE, {"counter": 0, "users": {}})


def save_warnings():
    save_json(WARNINGS_FILE, warnings)


def save_applications():
    save_json(APPLICATIONS_FILE, applications_data)


def is_admin(member):
    return member.guild_permissions.administrator


@bot.check
async def restrict_guild(ctx):
    return ctx.guild and ctx.guild.id == ALLOWED_GUILD_ID


@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        await guild.leave()


async def send_app_log(guild, title, description, color):
    channel = guild.get_channel(APPLICATION_LOG_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="🕒 الوقت", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
    await channel.send(embed=embed)


async def send_protection_log(guild, member, violation, message_text, punishment):
    log_channel = guild.get_channel(PROTECTION_LOG_CHANNEL_ID)
    if not log_channel:
        return

    embed = discord.Embed(title="🛡️ سجل مخالفة حماية", color=COLOR_YELLOW)
    embed.add_field(name="👤 العضو", value=f"{member.mention}\n`{member.id}`", inline=False)
    embed.add_field(name="⚠️ المخالفة", value=violation, inline=True)
    embed.add_field(name="🔨 العقوبة", value=punishment, inline=True)
    embed.add_field(name="💬 الرسالة", value=f"```{message_text[:900]}```", inline=False)
    embed.add_field(name="🕒 الوقت", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
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

    warnings[user_id].append({
        "reason": reason,
        "message": message_text,
        "moderator": moderator,
        "time": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    })

    save_warnings()
    return len(warnings[user_id])


async def handle_violation(message, reason):
    old_message = message.content

    try:
        await message.delete()
    except:
        pass

    count = add_warning(message.author, reason, old_message, "النظام التلقائي")

    embed = discord.Embed(
        title="⚠️ تحذير تلقائي",
        description=f"{message.author.mention} أخذت تحذير رقم **{count}**",
        color=COLOR_YELLOW
    )
    embed.add_field(name="السبب", value=reason, inline=False)

    await message.channel.send(embed=embed, delete_after=8)

    punishment = await apply_punishment(message.author, message.channel, count)
    await send_protection_log(message.guild, message.author, reason, old_message, punishment)


# =========================
# نظام التقديم الجديد
# =========================

class SupportApplyModal(discord.ui.Modal, title="تقديم الدعم الفني"):
    name = discord.ui.TextInput(
        label="اسمك",
        placeholder="مثال: جابر",
        required=True,
        max_length=50
    )

    age = discord.ui.TextInput(
        label="عمرك",
        placeholder="مثال: 18",
        required=True,
        max_length=10
    )

    daily_time = discord.ui.TextInput(
        label="كم ساعة تقدر تتواجد؟",
        placeholder="مثال: من 3 إلى 5 ساعات يومياً",
        required=True,
        max_length=60
    )

    experience = discord.ui.TextInput(
        label="خبرتك في الدعم أو الإدارة",
        placeholder="اكتب خبرتك السابقة أو إذا ما عندك خبرة اكتب: لا يوجد",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=600
    )

    why_you = discord.ui.TextInput(
        label="ليش نختارك؟",
        placeholder="اكتب سبب رغبتك بالانضمام للدعم الفني",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=600
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        user_app = applications_data["users"].get(user_id)

        if user_app and user_app.get("status") in ["pending", "accepted"]:
            await interaction.followup.send(
                "❌ عندك تقديم سابق قيد المراجعة أو مقبول مبدئيًا.",
                ephemeral=True
            )
            return

        app_channel = interaction.guild.get_channel(APPLICATION_CHANNEL_ID)

        if not app_channel:
            await interaction.followup.send("❌ روم التقديمات غير موجود.", ephemeral=True)
            return

        applications_data["counter"] += 1
        app_id = f"SUP-{applications_data['counter']:04d}"

        applications_data["users"][user_id] = {
            "app_id": app_id,
            "status": "pending",
            "message_id": None,
            "created_at": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        save_applications()

        embed = discord.Embed(
            title="📋 تقديم دعم فني جديد",
            description=f"رقم الطلب: `{app_id}`\nالحالة: ⏳ قيد المراجعة",
            color=COLOR_YELLOW
        )

        embed.add_field(name="👤 المتقدم", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=False)
        embed.add_field(name="📝 الاسم", value=str(self.name), inline=True)
        embed.add_field(name="🎂 العمر", value=str(self.age), inline=True)
        embed.add_field(name="⏰ التواجد", value=str(self.daily_time), inline=False)
        embed.add_field(name="🧠 الخبرة", value=str(self.experience), inline=False)
        embed.add_field(name="⭐ لماذا نختارك؟", value=str(self.why_you), inline=False)
        embed.add_field(name="🕒 وقت التقديم", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="مقاطعة رسك | نظام تقديم الدعم الفني")

        msg = await app_channel.send(
            content=f"📥 تقديم جديد من {interaction.user.mention} | `{app_id}`",
            embed=embed,
            view=SupportReviewView(interaction.user.id, app_id)
        )

        applications_data["users"][user_id]["message_id"] = msg.id
        save_applications()

        await interaction.followup.send(
            f"✅ تم إرسال تقديمك بنجاح.\nرقم طلبك: `{app_id}`\nانتظر مراجعة الإدارة.",
            ephemeral=True
        )


class SupportApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="بدء التقديم", style=discord.ButtonStyle.green, emoji="📝")
    async def support_apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportApplyModal())


class RejectReasonModal(discord.ui.Modal, title="سبب رفض التقديم"):
    def __init__(self, user_id: int, app_id: str):
        super().__init__()
        self.user_id = user_id
        self.app_id = app_id

    reason = discord.ui.TextInput(
        label="سبب الرفض",
        placeholder="اكتب سبب الرفض",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        member = interaction.guild.get_member(self.user_id)
        reason_text = str(self.reason)

        if member:
            try:
                dm_embed = discord.Embed(
                    title="❌ تم رفض تقديمك للدعم الفني",
                    description="نشكر لك رغبتك في الانضمام لفريق الدعم الفني.",
                    color=COLOR_RED
                )
                dm_embed.add_field(name="📌 رقم الطلب", value=f"`{self.app_id}`", inline=False)
                dm_embed.add_field(name="📝 سبب الرفض", value=reason_text, inline=False)
                dm_embed.add_field(name="🤝 ملاحظة", value="نتمنى لك التوفيق.", inline=False)
                await member.send(embed=dm_embed)
            except:
                pass

        applications_data["users"].setdefault(str(self.user_id), {})
        applications_data["users"][str(self.user_id)]["status"] = "rejected"
        save_applications()

        embed = interaction.message.embeds[0]
        embed.color = COLOR_RED
        embed.add_field(
            name="❌ نتيجة الطلب",
            value=f"تم رفض الطلب\nالمتقدم: <@{self.user_id}>\nبواسطة: {interaction.user.mention}\nالسبب: {reason_text}",
            inline=False
        )

        await interaction.message.edit(
            content=f"❌ تم رفض الطلب الخاص بـ <@{self.user_id}> | `{self.app_id}`",
            embed=embed,
            view=None
        )

        await send_app_log(
            interaction.guild,
            "❌ تم رفض تقديم دعم فني",
            f"المتقدم: <@{self.user_id}>\nرقم الطلب: `{self.app_id}`\nبواسطة: {interaction.user.mention}\nالسبب: {reason_text}",
            COLOR_RED
        )

        await interaction.followup.send("❌ تم رفض الطلب وإرسال السبب للمتقدم.", ephemeral=True)


class SupportReviewView(discord.ui.View):
    def __init__(self, user_id: int, app_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(label="قبول مبدئي", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        member = interaction.guild.get_member(self.user_id)

        if member:
            try:
                dm_embed = discord.Embed(
                    title="✅ تم قبول تقديمك مبدئيًا كدعم فني",
                    description=(
                        "تمت مراجعة طلبك وقبولك مبدئيًا.\n\n"
                        "يرجى التوجه إلى روم انتظار المقابلة الصوتي لإكمال المقابلة."
                    ),
                    color=COLOR_GREEN
                )
                dm_embed.add_field(name="📌 رقم الطلب", value=f"`{self.app_id}`", inline=False)
                dm_embed.add_field(name="🎙️ روم انتظار المقابلة", value=f"<#{INTERVIEW_VOICE_ROOM_ID}>", inline=False)
                dm_embed.add_field(name="⚠️ تنبيه", value="القبول مبدئي فقط، والقرار النهائي بعد المقابلة.", inline=False)
                await member.send(embed=dm_embed)
            except:
                pass

        applications_data["users"].setdefault(str(self.user_id), {})
        applications_data["users"][str(self.user_id)]["status"] = "accepted"
        save_applications()

        embed = interaction.message.embeds[0]
        embed.color = COLOR_GREEN
        embed.add_field(
            name="✅ نتيجة الطلب",
            value=f"تم قبول الطلب مبدئيًا\nالمتقدم: <@{self.user_id}>\nبواسطة: {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(
            content=f"✅ تم قبول الطلب الخاص بـ <@{self.user_id}> | `{self.app_id}`",
            embed=embed,
            view=InterviewDoneView(self.user_id, self.app_id)
        )

        await send_app_log(
            interaction.guild,
            "✅ تم قبول تقديم دعم فني مبدئيًا",
            f"المتقدم: <@{self.user_id}>\nرقم الطلب: `{self.app_id}`\nبواسطة: {interaction.user.mention}\nروم المقابلة: <#{INTERVIEW_VOICE_ROOM_ID}>",
            COLOR_GREEN
        )

        await interaction.followup.send("✅ تم قبول الطلب وإرسال رسالة للمتقدم.", ephemeral=True)

    @discord.ui.button(label="رفض", style=discord.ButtonStyle.red, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        await interaction.response.send_modal(RejectReasonModal(self.user_id, self.app_id))


class InterviewDoneView(discord.ui.View):
    def __init__(self, user_id: int, app_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(label="تمت المقابلة", style=discord.ButtonStyle.blurple, emoji="🎙️")
    async def interview_done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        applications_data["users"].setdefault(str(self.user_id), {})
        applications_data["users"][str(self.user_id)]["status"] = "interview_done"
        save_applications()

        embed = interaction.message.embeds[0]
        embed.color = COLOR_BLUE
        embed.add_field(
            name="🎙️ المقابلة",
            value=f"تم تسجيل أن المقابلة تمت بواسطة {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(
            content=f"🎙️ تمت مقابلة <@{self.user_id}> | `{self.app_id}`",
            embed=embed,
            view=None
        )

        await send_app_log(
            interaction.guild,
            "🎙️ تمت مقابلة متقدم دعم فني",
            f"المتقدم: <@{self.user_id}>\nرقم الطلب: `{self.app_id}`\nبواسطة: {interaction.user.mention}",
            COLOR_BLUE
        )

        await interaction.followup.send("🎙️ تم تسجيل المقابلة.", ephemeral=True)


# =========================
# Keep Alive
# =========================

app = Flask("")


@app.route("/")
def home():
    return "I'm alive"


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run).start()


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

    embed = discord.Embed(title="📤 عضو خرج من السيرفر", color=COLOR_GREY)
    embed.add_field(name="👤 العضو", value=f"{member.mention}\n`{member.name}`", inline=False)
    embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="🚪 طريقة الخروج", value=reason, inline=True)
    embed.add_field(name="👮 بواسطة", value=executor, inline=True)
    embed.add_field(name="🎭 الرولات", value=roles_text, inline=False)

    if member.joined_at:
        embed.add_field(name="📅 دخل السيرفر", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=False)

    embed.set_thumbnail(url=member.display_avatar.url)
    await log_channel.send(embed=embed)


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if after.channel and after.channel.id == SUPPORT_WAITING_VOICE_ID:
        support_chat = bot.get_channel(SUPPORT_CHAT_ID)
        support_role = member.guild.get_role(SUPPORT_ROLE_ID)

        if support_chat and support_role:
            embed = discord.Embed(
                title="🎧 طلب دعم فني",
                description="في شخص دخل انتظار الدعم الفني",
                color=COLOR_YELLOW
            )
            embed.add_field(name="👤 العضو", value=member.mention, inline=True)
            embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)
            embed.add_field(name="🎧 الروم", value=after.channel.mention, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)

            await support_chat.send(content=support_role.mention, embed=embed)


@bot.event
async def on_message(message):
    global protection_enabled

    if message.author.bot:
        return

    if not message.guild or message.guild.id != ALLOWED_GUILD_ID:
        return

    content = message.content.lower()

    if protection_enabled and not is_admin(message.author):

        for word in bad_words:
            if word in content:
                await handle_violation(message, "كلمة ممنوعة / سب")
                return

        if ANTI_LINKS:
            link_words = ["http://", "https://", "discord.gg", ".com", ".net", ".gg"]
            if any(link in content for link in link_words):
                await handle_violation(message, "إرسال رابط ممنوع")
                return

        mentions_count = len(message.mentions) + len(message.role_mentions)

        if message.mention_everyone:
            mentions_count += 10

        if mentions_count >= MASS_MENTION_LIMIT:
            await handle_violation(message, f"منشن كثير ({mentions_count})")
            return

        user_id = message.author.id
        now = time.time()

        if user_id not in user_message_times:
            user_message_times[user_id] = []

        user_message_times[user_id].append(now)
        user_message_times[user_id] = [t for t in user_message_times[user_id] if now - t <= SPAM_SECONDS]

        if len(user_message_times[user_id]) >= SPAM_LIMIT:
            user_message_times[user_id] = []
            await handle_violation(message, f"سبام: {SPAM_LIMIT} رسائل خلال {SPAM_SECONDS} ثواني")
            return

    if "سلام" in content:
        await message.channel.send("وعليكم السلام 👋")

    await bot.process_commands(message)


@bot.command(name="بنق", aliases=["ping"])
async def ping(ctx):
    await ctx.send(embed=discord.Embed(title="🏓 Pong", description="البوت شغال 👑", color=COLOR_YELLOW))


@bot.command(name="هلا", aliases=["hello"])
async def hello(ctx):
    await ctx.send(embed=discord.Embed(title="👋 هلا والله", description=f"يا مرحبا {ctx.author.mention} 🔥", color=COLOR_GREY))


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

    await ctx.send(embed=discord.Embed(title="😂 طقطقة", description=f"{member.mention} {random.choice(roasts)}", color=COLOR_YELLOW))


@bot.command(name="تقييم", aliases=["rate"])
async def rate(ctx, *, thing="أنت"):
    await ctx.send(embed=discord.Embed(title="⭐ تقييم", description=f"تقييمي لـ **{thing}**: **{random.randint(1, 10)}/10** 😂", color=COLOR_YELLOW))


@bot.command(name="مسح", aliases=["clear"])
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(embed=discord.Embed(title="🧹 تم المسح", description=f"تم حذف **{amount}** رسالة ✅", color=COLOR_GREY), delete_after=3)


@bot.command(name="قفل", aliases=["lock"])
@commands.has_permissions(administrator=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=discord.Embed(title="🔒 تم قفل الروم", description="تم منع الأعضاء من الكتابة هنا", color=COLOR_RED))


@bot.command(name="فتح", aliases=["unlock"])
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=discord.Embed(title="🔓 تم فتح الروم", description="تم السماح للأعضاء بالكتابة هنا", color=COLOR_GREEN))


@bot.command(name="ارسال_التقديم")
@commands.has_permissions(administrator=True)
async def send_support_apply(ctx):
    embed = discord.Embed(
        title="🎧 تقديم الدعم الفني",
        description=(
            "**هل ترغب بالانضمام إلى فريق الدعم الفني؟**\n\n"
            "قبل التقديم تأكد من التالي:\n"
            "```diff\n"
            "+ قراءة قوانين السيرفر كاملة\n"
            "+ التعامل باحترام مع اللاعبين\n"
            "+ وجود وقت كافي للتواجد\n"
            "+ كتابة إجابات واضحة وجدية\n"
            "- التقديم العشوائي قد يتم رفضه مباشرة\n"
            "```\n"
            "اضغط الزر بالأسفل لبدء التقديم."
        ),
        color=COLOR_YELLOW
    )

    embed.add_field(
        name="📌 ملاحظة مهمة",
        value="القبول مبدئي فقط، وبعدها لازم تدخل مقابلة صوتية.",
        inline=False
    )

    embed.set_footer(text="مقاطعة رسك | نظام التقديم")
    await ctx.send(embed=embed, view=SupportApplyView())


@bot.command(name="الادارة", aliases=["staff"])
@commands.has_permissions(administrator=True)
async def staff_list(ctx, role: discord.Role):
    if role.id == STAFF_MAIN_ROLE_ID:
        text = ""

        for staff_role_id, staff_role_name in STAFF_ROLE_IDS.items():
            staff_role = ctx.guild.get_role(staff_role_id)

            if staff_role and staff_role.members:
                text += f"\n**{staff_role_name}** {staff_role.mention}\n"

                for member in staff_role.members:
                    if not member.bot:
                        text += f"• {member.mention} — {staff_role_name}\n"

        if text == "":
            text = "مافي أحد معه رتب إدارية."

        await ctx.send(
            content=role.mention,
            embed=discord.Embed(title="📋 طاقم إدارة مقاطعة رسك", description=text[:4000], color=COLOR_YELLOW)
        )
        return

    members = [member for member in role.members if not member.bot]

    if not members:
        await ctx.send(f"مافي أحد معه رتبة {role.mention}")
        return

    text = ""
    for member in members:
        text += f"• {member.mention} — {role.name}\n"

    await ctx.send(
        content=role.mention,
        embed=discord.Embed(title=f"📋 أعضاء رتبة {role.name}", description=text[:4000], color=COLOR_YELLOW)
    )


@bot.command(name="تحذير", aliases=["warn"])
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason="بدون سبب"):
    count = add_warning(member, reason, "تحذير يدوي من الإدارة", f"{ctx.author} ({ctx.author.id})")

    embed = discord.Embed(title="🚫 تحذير إداري", description=f"{member.mention} أخذ تحذير", color=COLOR_YELLOW)
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="عدد التحذيرات الآن", value=str(count), inline=True)

    await ctx.send(embed=embed)

    punishment = await apply_punishment(member, ctx.channel, count)
    await send_protection_log(ctx.guild, member, f"تحذير يدوي: {reason}", "تحذير يدوي من الإدارة", punishment)


@bot.command(name="تحذيرات", aliases=["warnings"])
@commands.has_permissions(administrator=True)
async def warnings_count(ctx, member: discord.Member):
    user_id = str(member.id)
    user_warnings = warnings.get(user_id, [])

    if not user_warnings:
        await ctx.send(embed=discord.Embed(title="✅ لا يوجد تحذيرات", description=f"{member.mention} ما عليه أي تحذيرات", color=COLOR_GREEN))
        return

    embed = discord.Embed(title=f"🚫 تحذيرات {member.name}", description=f"عدد التحذيرات: **{len(user_warnings)}**", color=COLOR_YELLOW)

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
    warnings[str(member.id)] = []
    save_warnings()
    await ctx.send(embed=discord.Embed(title="✅ تم التصفير", description=f"تم تصفير إنذارات {member.mention}", color=COLOR_GREEN))


@bot.command(name="حماية", aliases=["protection"])
@commands.has_permissions(administrator=True)
async def protection(ctx, mode=None):
    global protection_enabled

    if mode is None:
        status = "مفعلة ✅" if protection_enabled else "مطفية ❌"
        await ctx.send(embed=discord.Embed(title="🛡️ حالة الحماية", description=f"الحماية الآن: **{status}**", color=COLOR_YELLOW))
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
    embed = discord.Embed(title="⚙️ إعدادات الحماية", color=COLOR_GREY)
    embed.add_field(name="Anti-Link", value="شغال ✅" if ANTI_LINKS else "مغلق ❌", inline=True)
    embed.add_field(name="Spam", value=f"{SPAM_LIMIT} رسائل / {SPAM_SECONDS} ثواني", inline=True)
    embed.add_field(name="Mass Mention", value=f"{MASS_MENTION_LIMIT} منشن", inline=True)
    embed.add_field(name="Protection Log", value=f"<#{PROTECTION_LOG_CHANNEL_ID}>", inline=False)
    await ctx.send(embed=embed)


keep_alive()
bot.run(TOKEN)
