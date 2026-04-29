import discord
from discord.ext import commands
import random
from datetime import timedelta
import os
import json
import time
import sqlite3
from flask import Flask
from threading import Thread

TOKEN = os.getenv("TOKEN")

ALLOWED_GUILD_ID = 1300038159446441985

SUPPORT_WAITING_VOICE_ID = 1300051682809483294
SUPPORT_CHAT_ID = 1498683004703215796
SUPPORT_PING_ROLE_ID = 1300049212553302109

FINAL_SUPPORT_ROLE_ID = 1300049180877787136

LEAVE_LOG_CHANNEL_ID = 1498690187427844137
PROTECTION_LOG_CHANNEL_ID = 1498727149388169378

APPLICATION_CHANNEL_ID = 1498758805914259587
INTERVIEW_VOICE_ROOM_ID = 1498759006024368289
APPLICATION_LOG_CHANNEL_ID = 1498758805914259587
ADMIN_LOG_CHANNEL_ID = 1498727149388169378

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
COLOR_PURPLE = discord.Color.purple()

WARNINGS_FILE = "warnings.json"
DB_FILE = "bot_data.db"

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


# =========================
# Database
# =========================

def db_connect():
    return sqlite3.connect(DB_FILE)


def add_column_if_missing(cur, table, column, column_type):
    cur.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cur.fetchall()]
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def init_db():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT UNIQUE,
            user_id INTEGER,
            message_id INTEGER,
            channel_id INTEGER,
            status TEXT,
            name TEXT,
            age TEXT,
            daily_time TEXT,
            experience TEXT,
            why_you TEXT,
            reviewer_id INTEGER,
            reject_reason TEXT,
            final_reviewer_id INTEGER,
            final_reason TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS application_blacklist (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            moderator_id INTEGER,
            created_at TEXT
        )
    """)

    needed_columns = {
        "app_id": "TEXT",
        "user_id": "INTEGER",
        "message_id": "INTEGER",
        "channel_id": "INTEGER",
        "status": "TEXT",
        "name": "TEXT",
        "age": "TEXT",
        "daily_time": "TEXT",
        "experience": "TEXT",
        "why_you": "TEXT",
        "reviewer_id": "INTEGER",
        "reject_reason": "TEXT",
        "final_reviewer_id": "INTEGER",
        "final_reason": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT"
    }

    for col, col_type in needed_columns.items():
        add_column_if_missing(cur, "applications", col, col_type)

    conn.commit()
    conn.close()


def create_application(user_id, channel_id, name, age, daily_time, experience, why_you):
    conn = db_connect()
    cur = conn.cursor()
    now = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    cur.execute("""
        INSERT INTO applications (
            app_id, user_id, message_id, channel_id, status,
            name, age, daily_time, experience, why_you,
            reviewer_id, reject_reason, final_reviewer_id, final_reason,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "TEMP", user_id, None, channel_id, "pending",
        name, age, daily_time, experience, why_you,
        None, None, None, None, now, now
    ))

    app_number = cur.lastrowid
    app_id = f"SUP-{app_number:04d}"

    cur.execute("UPDATE applications SET app_id = ? WHERE id = ?", (app_id, app_number))

    conn.commit()
    conn.close()
    return app_id


def update_application_message(app_id, message_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE applications SET message_id = ?, updated_at = ? WHERE app_id = ?",
        (message_id, discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), app_id)
    )
    conn.commit()
    conn.close()


def get_active_application(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT app_id, status FROM applications
        WHERE user_id = ? AND status IN ('pending', 'accepted', 'interview_done')
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_application_status(app_id, status, reviewer_id=None, reject_reason=None, final_reviewer_id=None, final_reason=None):
    conn = db_connect()
    cur = conn.cursor()

    if status in ["final_accepted", "final_rejected"]:
        cur.execute("""
            UPDATE applications
            SET status = ?, final_reviewer_id = ?, final_reason = ?, updated_at = ?
            WHERE app_id = ?
        """, (
            status,
            final_reviewer_id,
            final_reason,
            discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            app_id
        ))
    else:
        cur.execute("""
            UPDATE applications
            SET status = ?, reviewer_id = ?, reject_reason = ?, updated_at = ?
            WHERE app_id = ?
        """, (
            status,
            reviewer_id,
            reject_reason,
            discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            app_id
        ))

    conn.commit()
    conn.close()


def get_unfinished_applications():
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT app_id, user_id, message_id, status
        FROM applications
        WHERE status IN ('pending', 'accepted', 'interview_done')
        AND message_id IS NOT NULL
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_application_summary(user_id):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM applications WHERE user_id = ?", (user_id,))
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT app_id, status, created_at
        FROM applications
        WHERE user_id = ?
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    latest = cur.fetchone()

    conn.close()
    return total, latest


def add_to_blacklist(user_id, reason, moderator_id):
    conn = db_connect()
    cur = conn.cursor()
    now = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    cur.execute("""
        INSERT OR REPLACE INTO application_blacklist (user_id, reason, moderator_id, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, reason, moderator_id, now))

    conn.commit()
    conn.close()


def remove_from_blacklist(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM application_blacklist WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_blacklist(user_id):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT reason, moderator_id, created_at FROM application_blacklist WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row


# =========================
# JSON Warnings
# =========================

def load_json(file_name, default):
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return default


def save_json(file_name, data):
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


warnings = load_json(WARNINGS_FILE, {})


def save_warnings():
    save_json(WARNINGS_FILE, warnings)


def is_admin(member):
    return member.guild_permissions.administrator


# =========================
# Guild Restriction
# =========================

@bot.check
async def restrict_guild(ctx):
    return ctx.guild and ctx.guild.id == ALLOWED_GUILD_ID


@bot.event
async def on_guild_join(guild):
    if guild.id != ALLOWED_GUILD_ID:
        await guild.leave()


# =========================
# Logs
# =========================

async def send_admin_log(guild, title, description, color=COLOR_GREY):
    channel = guild.get_channel(ADMIN_LOG_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(title=title, description=description, color=color)
    embed.add_field(name="🕒 الوقت", value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>", inline=False)
    await channel.send(embed=embed)


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


# =========================
# Protection
# =========================

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
# Application System
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

        blacklisted = get_blacklist(interaction.user.id)
        if blacklisted:
            await interaction.followup.send(
                f"❌ أنت ممنوع من التقديم.\nالسبب: `{blacklisted[0]}`",
                ephemeral=True
            )
            return

        active_app = get_active_application(interaction.user.id)
        if active_app:
            await interaction.followup.send(
                f"❌ عندك تقديم سابق مفتوح.\nرقم الطلب: `{active_app[0]}`\nالحالة: `{active_app[1]}`",
                ephemeral=True
            )
            return

        app_channel = interaction.guild.get_channel(APPLICATION_CHANNEL_ID)

        if not app_channel:
            await interaction.followup.send("❌ روم التقديمات غير موجود.", ephemeral=True)
            return

        app_id = create_application(
            user_id=interaction.user.id,
            channel_id=APPLICATION_CHANNEL_ID,
            name=str(self.name),
            age=str(self.age),
            daily_time=str(self.daily_time),
            experience=str(self.experience),
            why_you=str(self.why_you)
        )

        embed = discord.Embed(
            title="📋 تقديم دعم فني جديد",
            description=(
                f"**رقم الطلب:** `{app_id}`\n"
                f"**الحالة:** ⏳ قيد المراجعة\n\n"
                "يرجى مراجعة بيانات المتقدم بعناية قبل القبول أو الرفض."
            ),
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

        update_application_message(app_id, msg.id)

        await interaction.followup.send(
            f"✅ تم إرسال تقديمك بنجاح.\nرقم طلبك: `{app_id}`\nانتظر مراجعة الإدارة.",
            ephemeral=True
        )


class SupportApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="بدء التقديم",
        style=discord.ButtonStyle.green,
        emoji="📝",
        custom_id="support_apply_start_button_v3"
    )
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

        update_application_status(
            app_id=self.app_id,
            status="rejected",
            reviewer_id=interaction.user.id,
            reject_reason=reason_text
        )

        embed = interaction.message.embeds[0]
        embed.color = COLOR_RED
        embed.add_field(
            name="❌ نتيجة الطلب",
            value=(
                f"تم رفض الطلب\n"
                f"المتقدم: <@{self.user_id}>\n"
                f"بواسطة: {interaction.user.mention}\n"
                f"السبب: {reason_text}"
            ),
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

    @discord.ui.button(
        label="قبول مبدئي",
        style=discord.ButtonStyle.green,
        emoji="✅",
        custom_id="support_accept_v3"
    )
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

        update_application_status(
            app_id=self.app_id,
            status="accepted",
            reviewer_id=interaction.user.id
        )

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

    @discord.ui.button(
        label="رفض",
        style=discord.ButtonStyle.red,
        emoji="❌",
        custom_id="support_reject_v3"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        await interaction.response.send_modal(RejectReasonModal(self.user_id, self.app_id))


class InterviewDoneView(discord.ui.View):
    def __init__(self, user_id, app_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(
        label="تمت المقابلة",
        style=discord.ButtonStyle.blurple,
        emoji="🎙️",
        custom_id="interview_done_v3"
    )
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        update_application_status(self.app_id, "interview_done", reviewer_id=interaction.user.id)

        embed = interaction.message.embeds[0]
        embed.color = COLOR_BLUE
        embed.add_field(name="🎙️ المقابلة", value=f"تمت بواسطة {interaction.user.mention}", inline=False)

        await interaction.message.edit(
            content=f"🎙️ تمت مقابلة <@{self.user_id}> | `{self.app_id}`",
            embed=embed,
            view=FinalDecisionView(self.user_id, self.app_id)
        )

        await interaction.followup.send("🎙️ تم تسجيل المقابلة.", ephemeral=True)


class FinalRejectReasonModal(discord.ui.Modal, title="سبب الرفض النهائي"):
    def __init__(self, user_id: int, app_id: str):
        super().__init__()
        self.user_id = user_id
        self.app_id = app_id

    reason = discord.ui.TextInput(
        label="سبب الرفض النهائي",
        placeholder="اكتب سبب الرفض النهائي",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        reason_text = str(self.reason)
        member = interaction.guild.get_member(self.user_id)

        if member:
            try:
                embed_dm = discord.Embed(
                    title="❌ تم رفضك بعد المقابلة",
                    description="نشكر لك وقتك واهتمامك.",
                    color=COLOR_RED
                )
                embed_dm.add_field(name="📌 رقم الطلب", value=f"`{self.app_id}`", inline=False)
                embed_dm.add_field(name="📝 السبب", value=reason_text, inline=False)
                await member.send(embed=embed_dm)
            except:
                pass

        update_application_status(
            self.app_id,
            "final_rejected",
            final_reviewer_id=interaction.user.id,
            final_reason=reason_text
        )

        embed = interaction.message.embeds[0]
        embed.color = COLOR_RED
        embed.add_field(
            name="❌ النتيجة النهائية",
            value=f"تم الرفض النهائي\nبواسطة: {interaction.user.mention}\nالسبب: {reason_text}",
            inline=False
        )

        await interaction.message.edit(
            content=f"❌ تم رفض <@{self.user_id}> نهائيًا | `{self.app_id}`",
            embed=embed,
            view=None
        )

        await interaction.followup.send("❌ تم الرفض النهائي.", ephemeral=True)


class FinalDecisionView(discord.ui.View):
    def __init__(self, user_id, app_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(
        label="قبول نهائي",
        style=discord.ButtonStyle.green,
        emoji="🔥",
        custom_id="final_accept_v3"
    )
    async def final_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        member = interaction.guild.get_member(self.user_id)
        role = interaction.guild.get_role(FINAL_SUPPORT_ROLE_ID)

        if member and role:
            try:
                await member.add_roles(role)
            except Exception as e:
                await interaction.followup.send(f"⚠️ ما قدرت أعطي الرتبة: `{e}`", ephemeral=True)

            try:
                dm_embed = discord.Embed(
                    title="🎉 تم قبولك رسميًا كدعم فني",
                    description="مبروك، تم اعتمادك ضمن فريق الدعم الفني.",
                    color=COLOR_GREEN
                )
                dm_embed.add_field(name="📌 رقم الطلب", value=f"`{self.app_id}`", inline=False)
                await member.send(embed=dm_embed)
            except:
                pass

        update_application_status(
            self.app_id,
            "final_accepted",
            final_reviewer_id=interaction.user.id
        )

        embed = interaction.message.embeds[0]
        embed.color = COLOR_GREEN
        embed.add_field(
            name="🔥 النتيجة النهائية",
            value=f"تم القبول النهائي\nبواسطة: {interaction.user.mention}",
            inline=False
        )

        await interaction.message.edit(
            content=f"🔥 تم قبول <@{self.user_id}> نهائيًا | `{self.app_id}`",
            embed=embed,
            view=None
        )

        await interaction.followup.send("🔥 تم القبول النهائي وإعطاء الرتبة.", ephemeral=True)

    @discord.ui.button(
        label="رفض نهائي",
        style=discord.ButtonStyle.red,
        emoji="❌",
        custom_id="final_reject_v3"
    )
    async def final_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الزر للإدارة فقط.", ephemeral=True)
            return

        await interaction.response.send_modal(FinalRejectReasonModal(self.user_id, self.app_id))


# =========================
# Keep Alive
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "online"


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run).start()


# =========================
# Events
# =========================

@bot.event
async def on_ready():
    init_db()

    try:
        bot.add_view(SupportApplyView())
    except Exception as e:
        print(f"Apply View Error: {e}")

    for app_id, user_id, message_id, status in get_unfinished_applications():
        try:
            if status == "pending":
                bot.add_view(SupportReviewView(user_id, app_id), message_id=message_id)
            elif status == "accepted":
                bot.add_view(InterviewDoneView(user_id, app_id), message_id=message_id)
            elif status == "interview_done":
                bot.add_view(FinalDecisionView(user_id, app_id), message_id=message_id)
        except Exception as e:
            print(f"Restore View Error {app_id}: {e}")

    print(f"Bot Ready: {bot.user}")


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
        support_role = member.guild.get_role(SUPPORT_PING_ROLE_ID)

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


# =========================
# Commands
# =========================

@bot.command(name="مساعدة", aliases=["helpme"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📖 أوامر البوت", color=COLOR_PURPLE)
    embed.description = """
**عامة**
`!بنق`
`!هلا`
`!طقطق @شخص`
`!تقييم الشي`

**إدارة**
`!مسح 10`
`!قفل`
`!فتح`
`!الادارة @رتبة`
`!لوحة`

**الحماية**
`!حماية`
`!حماية تشغيل`
`!حماية ايقاف`
`!اعدادات`

**التحذيرات**
`!تحذير @شخص السبب`
`!تحذيرات @شخص`
`!تصفير @شخص`

**التقديم**
`!ارسال_التقديم`
`!منع_تقديم @شخص السبب`
`!سماح_تقديم @شخص`
`!ملف @شخص`
"""
    await ctx.send(embed=embed)


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
    await send_admin_log(ctx.guild, "🧹 مسح رسائل", f"بواسطة: {ctx.author.mention}\nالروم: {ctx.channel.mention}\nالعدد: `{amount}`")


@bot.command(name="قفل", aliases=["lock"])
@commands.has_permissions(administrator=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=discord.Embed(title="🔒 تم قفل الروم", description="تم منع الأعضاء من الكتابة هنا", color=COLOR_RED))
    await send_admin_log(ctx.guild, "🔒 قفل روم", f"بواسطة: {ctx.author.mention}\nالروم: {ctx.channel.mention}", COLOR_RED)


@bot.command(name="فتح", aliases=["unlock"])
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=discord.Embed(title="🔓 تم فتح الروم", description="تم السماح للأعضاء بالكتابة هنا", color=COLOR_GREEN))
    await send_admin_log(ctx.guild, "🔓 فتح روم", f"بواسطة: {ctx.author.mention}\nالروم: {ctx.channel.mention}", COLOR_GREEN)


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


@bot.command(name="ملف")
async def profile(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    total, latest = get_user_application_summary(member.id)
    user_warnings = warnings.get(str(member.id), [])
    blacklist = get_blacklist(member.id)

    embed = discord.Embed(title="📊 ملف العضو", color=COLOR_BLUE)
    embed.add_field(name="👤 العضو", value=f"{member.mention}\n`{member.id}`", inline=False)
    embed.add_field(name="🚫 التحذيرات", value=str(len(user_warnings)), inline=True)
    embed.add_field(name="📨 عدد التقديمات", value=str(total), inline=True)

    if latest:
        embed.add_field(name="آخر طلب", value=f"`{latest[0]}` | `{latest[1]}`", inline=False)
    else:
        embed.add_field(name="آخر طلب", value="لا يوجد", inline=False)

    if blacklist:
        embed.add_field(name="منع التقديم", value=f"ممنوع ❌\nالسبب: {blacklist[0]}", inline=False)
    else:
        embed.add_field(name="منع التقديم", value="غير ممنوع ✅", inline=False)

    if member.joined_at:
        embed.add_field(name="دخل السيرفر", value=f"<t:{int(member.joined_at.timestamp())}:F>", inline=False)

    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="منع_تقديم")
@commands.has_permissions(administrator=True)
async def blacklist(ctx, member: discord.Member, *, reason="بدون سبب"):
    add_to_blacklist(member.id, reason, ctx.author.id)
    await ctx.send(f"🚫 تم منع {member.mention} من التقديم")
    await send_admin_log(ctx.guild, "🚫 منع تقديم", f"العضو: {member.mention}\nبواسطة: {ctx.author.mention}\nالسبب: {reason}", COLOR_RED)


@bot.command(name="سماح_تقديم")
@commands.has_permissions(administrator=True)
async def unblacklist(ctx, member: discord.Member):
    remove_from_blacklist(member.id)
    await ctx.send(f"✅ تم السماح لـ {member.mention} بالتقديم")
    await send_admin_log(ctx.guild, "✅ سماح تقديم", f"العضو: {member.mention}\nبواسطة: {ctx.author.mention}", COLOR_GREEN)


@bot.command(name="لوحة")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    status = "مفعلة ✅" if protection_enabled else "مطفية ❌"

    embed = discord.Embed(title="🎛️ لوحة التحكم", color=COLOR_PURPLE)
    embed.add_field(name="🛡️ الحماية", value=status, inline=True)
    embed.add_field(name="📨 التقديم", value="`!ارسال_التقديم`", inline=True)
    embed.add_field(name="⚙️ الإعدادات", value="`!اعدادات`", inline=True)
    embed.add_field(name="👤 ملف عضو", value="`!ملف @شخص`", inline=True)
    embed.add_field(name="🚫 منع تقديم", value="`!منع_تقديم @شخص السبب`", inline=True)
    embed.add_field(name="📖 مساعدة", value="`!مساعدة`", inline=True)

    await ctx.send(embed=embed)


# =========================
# Start
# =========================

keep_alive()
bot.run(TOKEN)
