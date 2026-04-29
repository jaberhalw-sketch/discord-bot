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

# =========================
# إعدادات السيرفر
# =========================
ALLOWED_GUILD_ID = 1300038159446441985

SUPPORT_WAITING_VOICE_ID = 1300051682809483294
SUPPORT_CHAT_ID = 1498683004703215796
SUPPORT_PING_ROLE_ID = 1300049212553302109

# رتبة دعم فني النهائية بعد القبول النهائي
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

# =========================
# إعدادات الحماية
# =========================
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
# SQLite Database
# =========================

def db_connect():
    return sqlite3.connect(DB_FILE)


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
        custom_id="support_apply_start_button_v2"
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
        custom_id="support_accept"
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ للإدارة فقط", ephemeral=True)

        member = interaction.guild.get_member(self.user_id)

        if member:
            try:
                embed = discord.Embed(
                    title="✅ تم قبولك مبدئيًا",
                    description="توجه لروم المقابلة الصوتية",
                    color=COLOR_GREEN
                )
                embed.add_field(name="الروم", value=f"<#{INTERVIEW_VOICE_ROOM_ID}>")
                await member.send(embed=embed)
            except:
                pass

        update_application_status(self.app_id, "accepted", reviewer_id=interaction.user.id)

        embed = interaction.message.embeds[0]
        embed.color = COLOR_GREEN
        embed.add_field(name="الحالة", value="تم قبول مبدئي", inline=False)

        await interaction.message.edit(
            embed=embed,
            view=InterviewDoneView(self.user_id, self.app_id)
        )

    @discord.ui.button(
        label="رفض",
        style=discord.ButtonStyle.red,
        emoji="❌",
        custom_id="support_reject"
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ للإدارة فقط", ephemeral=True)

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
        custom_id="interview_done"
    )
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        update_application_status(self.app_id, "interview_done", reviewer_id=interaction.user.id)

        embed = interaction.message.embeds[0]
        embed.color = COLOR_BLUE
        embed.add_field(name="المقابلة", value="تمت", inline=False)

        await interaction.message.edit(
            embed=embed,
            view=FinalDecisionView(self.user_id, self.app_id)
        )


class FinalDecisionView(discord.ui.View):
    def __init__(self, user_id, app_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.app_id = app_id

    @discord.ui.button(
        label="قبول نهائي",
        style=discord.ButtonStyle.green,
        emoji="🔥",
        custom_id="final_accept"
    )
    async def final_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        member = interaction.guild.get_member(self.user_id)
        role = interaction.guild.get_role(FINAL_SUPPORT_ROLE_ID)

        if member and role:
            await member.add_roles(role)

            try:
                await member.send("🎉 تم قبولك رسميًا كدعم فني")
            except:
                pass

        update_application_status(
            self.app_id,
            "final_accepted",
            final_reviewer_id=interaction.user.id
        )

        embed = interaction.message.embeds[0]
        embed.color = COLOR_GREEN
        embed.add_field(name="النتيجة النهائية", value="تم القبول ✅", inline=False)

        await interaction.message.edit(embed=embed, view=None)

    @discord.ui.button(
        label="رفض نهائي",
        style=discord.ButtonStyle.red,
        emoji="💀",
        custom_id="final_reject"
    )
    async def final_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        update_application_status(
            self.app_id,
            "final_rejected",
            final_reviewer_id=interaction.user.id,
            final_reason="رفض نهائي"
        )

        embed = interaction.message.embeds[0]
        embed.color = COLOR_RED
        embed.add_field(name="النتيجة النهائية", value="تم الرفض ❌", inline=False)

        await interaction.message.edit(embed=embed, view=None)


# =========================
# Commands Polish v2
# =========================

@bot.command(name="مساعدة")
async def help_cmd(ctx):
    embed = discord.Embed(title="📖 أوامر البوت", color=COLOR_PURPLE)
    embed.description = """
!ارسال_التقديم
!مسح
!قفل / !فتح
!تحذير / !تحذيرات
!الادارة
!ملف
!منع_تقديم / !سماح_تقديم
"""
    await ctx.send(embed=embed)


@bot.command(name="ملف")
async def profile(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    total, latest = get_user_application_summary(member.id)

    embed = discord.Embed(title="📊 ملف العضو", color=COLOR_BLUE)
    embed.add_field(name="👤", value=member.mention)
    embed.add_field(name="عدد التقديمات", value=total)

    if latest:
        embed.add_field(name="آخر طلب", value=f"{latest[0]} ({latest[1]})", inline=False)

    await ctx.send(embed=embed)


@bot.command(name="منع_تقديم")
@commands.has_permissions(administrator=True)
async def blacklist(ctx, member: discord.Member, *, reason="بدون سبب"):
    add_to_blacklist(member.id, reason, ctx.author.id)
    await ctx.send(f"🚫 تم منع {member.mention} من التقديم")


@bot.command(name="سماح_تقديم")
@commands.has_permissions(administrator=True)
async def unblacklist(ctx, member: discord.Member):
    remove_from_blacklist(member.id)
    await ctx.send(f"✅ تم السماح لـ {member.mention} بالتقديم")


@bot.command(name="لوحة")
@commands.has_permissions(administrator=True)
async def panel(ctx):
    embed = discord.Embed(title="🎛️ لوحة التحكم", color=COLOR_PURPLE)
    embed.description = "استخدم الأوامر بسرعة من هنا"

    embed.add_field(name="📩 التقديم", value="!ارسال_التقديم")
    embed.add_field(name="🛡️ الحماية", value="!حماية")
    embed.add_field(name="📊 ملف", value="!ملف")
    embed.add_field(name="🚫 بلاك ليست", value="!منع_تقديم")

    await ctx.send(embed=embed)


# =========================
# Ready
# =========================

@bot.event
async def on_ready():
    init_db()

    bot.add_view(SupportApplyView())

    for app_id, user_id, message_id, status in get_unfinished_applications():
        try:
            if status == "pending":
                bot.add_view(SupportReviewView(user_id, app_id), message_id=message_id)
            elif status == "accepted":
                bot.add_view(InterviewDoneView(user_id, app_id), message_id=message_id)
            elif status == "interview_done":
                bot.add_view(FinalDecisionView(user_id, app_id), message_id=message_id)
        except:
            pass

    print(f"Bot Ready: {bot.user}")


# =========================
# Run
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "online"

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run).start()

bot.run(TOKEN)
