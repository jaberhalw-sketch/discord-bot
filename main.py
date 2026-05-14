import discord
from discord.ext import commands
from datetime import timedelta
import os
import json
import time
import random
import sqlite3
import re
import asyncio
from pathlib import Path
from flask import Flask, request, redirect, session, render_template_string
from threading import Thread
import urllib.parse
import urllib.request
import urllib.error

# =========================
# CONFIG
# =========================

TOKEN = os.getenv("TOKEN")

GUILD_ID = 1318663576210243616

LOG_CHANNEL_ID = None

LOOKING_FOR_GAME_CHANNEL_ID = 1504066361876418703
GIVEAWAYS_CHANNEL_ID = 1370418475314581524
ROLES_CHANNEL_ID = 1504066503501152377
ANNOUNCEMENTS_CHANNEL_ID = 1370433079377920130
LEAVE_INFO_CHANNEL_ID = 1504063808656773170

GAME_VOICE_CATEGORY_ID = 1370419496002781335
GAME_ROOM_DELETE_SECONDS = 300

LOGS_CATEGORY_ID = 1504063695062306948

OWNER_USERNAMES = ["jr_7", "jbh.1"]

BYPASS_USER_IDS = {
    1125198908231004191
}

DM_OWNER_IDS = {
    1125198908231004191,
    881722045031915521,
}

DM_DELAY_SECONDS = 2

# Discord quarantined the bot because of mass/private DM behavior.
# Keep all outbound DM commands disabled. Use !اعلان or normal channels instead.
DM_COMMANDS_ENABLED = False

DB_FILE = "nm_system.db"
WARNINGS_FILE = "warnings.json"
LOG_CHANNELS_FILE = "log_channels.json"
DASHBOARD_SETTINGS_FILE = "dashboard_settings.json"

PREFIX = "!"

ANTI_LINKS = True
SPAM_LIMIT = 10
SPAM_SECONDS = 5
MASS_MENTION_LIMIT = 8
LEVEL_COOLDOWN = 25
COMMANDS_CHANNEL_ID = 1504067161734516757
MEMORY_BACKUP_CHANNEL_ID = 1504161977063178370
MEMORY_BACKUP_INTERVAL_SECONDS = 60 * 60
ECONOMY_EXPLAIN_INTERVAL_SECONDS = 7 * 60 * 60
ECONOMY_EXPLAIN_CHANNEL_ID = COMMANDS_CHANNEL_ID
HOURLY_REWARD_COOLDOWN_SECONDS = 60 * 60
MEMORY_BACKUP_MESSAGE_TAG = "NM_MEMORY_BACKUP_V2"
MEMORY_BACKUP_OLD_TAGS = ["NM_MEMORY_BACKUP_V1", "NM_MEMORY_BACKUP_V2"]
MEMORY_BACKUP_HISTORY_LIMIT = 100
MEMORY_FILES = [DB_FILE, WARNINGS_FILE, LOG_CHANNELS_FILE, DASHBOARD_SETTINGS_FILE]

COIN_NAME = "Retard coin"
MESSAGE_COIN_COOLDOWN = 60
DAILY_REWARD_BASE = 250
LEVEL_UP_COIN_BONUS = 75
SERVER_BOOSTER_ROLE_ID = 1349381214120706218
BOOSTER_WEEKLY_REWARD = 5000
BOOSTER_WEEKLY_COOLDOWN_SECONDS = 7 * 24 * 60 * 60
BOOSTER_WEEKLY_CHECK_INTERVAL_SECONDS = 60 * 60
GAMBLING_CHANNEL_ID = 1504165660341571684
GAMBLE_COOLDOWN_SECONDS = 2
ECONOMY_EMOJI = "🪙"
LEVEL_EMOJI = "📊"
BOT_BRAND = "Retards System"

# =========================
# DASHBOARD / DISCORD OAUTH
# =========================
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", os.getenv("SECRET_KEY", "change-this-secret"))
DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "").rstrip("/")
DISCORD_API_BASE = "https://discord.com/api/v10"
DASHBOARD_ADMIN_ROLE_IDS = {
    int(x.strip())
    for x in os.getenv("DASHBOARD_ADMIN_ROLE_IDS", "").split(",")
    if x.strip().isdigit()
}

# =========================
# ADMIN CONTROL CENTER
# =========================
DEFAULT_SYSTEM_TOGGLES = {
    "utility": True, "admin": True, "economy": True, "levels": True,
    "gambling": True, "protection": True, "lfg": True, "giveaway": True,
    "community": True, "roles": True, "memory": True,
}
COMMAND_SYSTEM_MAP = {
    "مساعدة": "utility", "بنق": "utility", "هلا": "utility", "معلومات": "utility", "طقطق": "utility", "تقييم": "utility",
    "انشاء": "admin", "اعداد": "admin", "لوحة": "admin", "اعلان": "admin", "مسح": "admin", "قفل": "admin", "فتح": "admin",
    "اقتراح": "community", "لعب": "lfg", "سحب": "giveaway", "رولات": "roles",
    "لفلي": "levels", "لفل": "levels", "ترتيب": "levels",
    "رصيدي": "economy", "رصيد": "economy", "يومي": "economy", "بوست": "economy", "تحويل": "economy", "اغنى": "economy",
    "اعطاءفلوس": "economy", "سحبفلوس": "economy", "تصفيرفلوس": "economy",
    "شرح_القمار": "gambling", "حظ": "gambling", "دبل": "gambling", "سلوت": "gambling", "وجه": "gambling", "بلاكجاك": "gambling",
    "حماية": "protection", "اعدادات": "protection", "تحذير": "protection", "تحذيرات": "protection", "تصفير": "protection",
    "حفظ_الذاكرة": "memory", "استرجاع_الذاكرة": "memory", "حالة_الذاكرة": "memory",
}
EMERGENCY_ALLOWED_SYSTEMS = {"utility", "admin", "memory", "protection"}
DASHBOARD_AUDIT_LOG_LIMIT = 100


COLOR_YELLOW = discord.Color.gold()
COLOR_GREEN = discord.Color.green()
COLOR_RED = discord.Color.red()
COLOR_BLUE = discord.Color.blue()
COLOR_GREY = discord.Color.dark_grey()
COLOR_PURPLE = discord.Color.purple()
COLOR_ORANGE = discord.Color.orange()

protection_enabled = True
user_message_times = {}
xp_cooldowns = {}
coin_cooldowns = {}
gamble_cooldowns = {}
game_room_delete_tasks = {}
memory_backup_task = None
economy_explain_task = None
booster_weekly_task = None

LOG_CHANNEL_NAMES = {
    "message": "nm-message-logs",
    "member": "nm-member-logs",
    "moderation": "nm-moderation-logs",
    "role": "nm-role-logs",
    "channel": "nm-channel-logs",
    "voice": "nm-voice-logs",
    "server": "nm-server-logs",
    "game": "nm-game-logs",
    "giveaway": "nm-giveaway-logs",
}

GAME_ROLES = {
    "gta": {"name": "🚗 GTA", "emoji": "🚗"},
    "valorant": {"name": "🎯 Valorant", "emoji": "🎯"},
    "fortnite": {"name": "🏗️ Fortnite", "emoji": "🏗️"},
    "roblox": {"name": "🧱 Roblox", "emoji": "🧱"},
    "minecraft": {"name": "⛏️ Minecraft", "emoji": "⛏️"},
    "counter_strike": {"name": "🔫 Counter Strike", "emoji": "🔫"},
    "dead_by_daylight": {"name": "💀 Dead by Daylight", "emoji": "💀"},
    "overwatch": {"name": "🛡️ Overwatch", "emoji": "🛡️"},
    "arc_raiders": {"name": "🚀 ARC Raiders", "emoji": "🚀"},
    "rocket_league": {"name": "⚽ Rocket League", "emoji": "⚽"},
    "apex": {"name": "🏹 Apex Legends", "emoji": "🏹"},
    "warzone": {"name": "🪖 Warzone", "emoji": "🪖"},
    "rainbow_six": {"name": "🏢 Rainbow Six Siege", "emoji": "🏢"},
    "ea_fc": {"name": "⚽ EA FC", "emoji": "⚽"},
    "rust": {"name": "🪓 Rust", "emoji": "🪓"},
    "league": {"name": "⚔️ League of Legends", "emoji": "⚔️"},
    "cod": {"name": "🎖️ Call of Duty", "emoji": "🎖️"},
    "among_us": {"name": "🛸 Among Us", "emoji": "🛸"},
    "the_finals": {"name": "💥 The Finals", "emoji": "💥"},
    "helldivers": {"name": "🌌 Helldivers 2", "emoji": "🌌"},
}

GAME_ROLE_IDS = {
    "helldivers": 1504078793889812652,
    "the_finals": 1504078792866533406,
    "among_us": 1504078791364837498,
    "cod": 1504078790522044608,
    "league": 1504078789364158594,
    "rust": 1504078787422191698,
    "ea_fc": 1504078787061481543,
    "rainbow_six": 1504078785606320216,
    "warzone": 1504078784465469572,
    "apex": 1504078783169302558,
    "rocket_league": 1504078782401871983,
    "arc_raiders": 1504078781441245204,
    "overwatch": 1504078780665298984,
    "dead_by_daylight": 1504078779964850267,
    "counter_strike": 1504078778719141910,
    "minecraft": 1504078777272111205,
    "roblox": 1504078775699116052,
    "fortnite": 1504078773081870407,
    "valorant": 1504078771903401984,
    "gta": 1504078771106480208,
}

bad_words = [
    "قواد", "خنيث", "قحبه", "قحبة", "شرموط", "شرموطه", "شرموطة",
    "سالب", "كس", "كس امك", "كس اختك", "كس اخوك", "كس والديك",
    "كسمك", "كسمكم", "كسمه", "كسم", "كسختك", "كسامك", "كساختك",
    "كساخوك", "كسابوك", "كسس", "كسي", "كسى", "كىس", "كءس",
    "طيزي", "طيزك", "طيز", "انيكك", "انيك", "انيككك",
    "انيك ابوك", "انيك اختك", "انيك اخوك", "انيك امك",
    "ازغب", "جرار", "معرس", "اعرسك", "ممحون", "ممحونه",
    "ممحونة", "ممحونهه", "محنه", "محنة", "العقه", "العقة",
    "قضي", "زبي", "زب", "زبك", "زبه", "زبري", "زنى", "زاني",
    "زانيه", "زنوه", "فقحة", "فقحه", "عيري", "عيرك", "عير",
    "منيكه", "منيوك", "منيوكه", "منيك", "متناك", "متناكه",
    "مفتوحه", "مقحب", "مقحبه", "ناك", "نيك",
    "مص", "مصه", "مصي", "مصزبي", "مص لين تغص", "مص لين تنام",
    "الحس", "الحسيه", "لحس", "العق",
    "خول", "ديوث", "عرص", "عرصه", "ياعرص", "ياعرصه",
    "قحب", "قحبة", "قحبة*", "قحبه في قحبه", "يقحبه", "ياقحبة", "ياقحبه",
    "بنت القحبه", "يابن القحبه", "يابن القحب", "يابن القحاب",
    "يابن الستين قحبه", "يابن الشرموطه", "يابن الشراميط",
    "يابن المتناك", "يابن المتناكه", "يابن المتانيك",
    "يابن الحرام", "يبن الحرام", "ابن حرام", "ابن قحب", "ابن قحبه",
    "ابن الزاني", "ابن الزانيه", "يابن الزانيه",
    "يا خول", "يخول", "يابن الخول", "يابن الديوث", "يابن الديوثه",
    "ياشرموط", "ياشرموطه", "يازانيه", "يزبي", "يا ابن زبي",
    "ياكسمك", "ياكسختك", "يكسمك", "يامتناك", "يامتناكه",
    "يامهان", "يامهانه", "مهان", "مهانه",
    "جلخ", "جلخت", "اجلخ", "اجلخ عليك",
    "اركب عليه", "اركبه", "اركبي عليه", "اركب على زبي",
    "اركب علي زبي", "اركب على الغالي", "اركب علي الغالي",
    "تعال اركب على زبي", "على زبي", "عض الغالي",
    "تبي تتناك", "تبي تمص", "سكس", "سكىس", "سىكىس", "سىكس",
    "كلزب", "كل زق يبن الشرمطه", "نظام مقحبه",
    "fuck", "fucking", "fucked", "fucker", "motherfucker",
    "shit", "bullshit", "bitch", "bitches",
    "asshole", "dick", "cock", "pussy", "cunt",
    "slut", "whore", "sex", "suck my dick", "smd", "stfu", "kys",
    "3leh", "3r9", "3r9h", "5alk", "5altk", "87bh",
    "a5ok", "a5tk", "abok", "aft7k", "agl5", "ajl5",
    "al3a'le", "al3'aly", "al87bh", "amk", "anek", "anekk",
    "arkb", "arkb 3leh", "arkbe", "arkbh", "arkby",
    "bzne", "bzny", "g7bh", "ghbh", "jtle5",
    "ks", "ks a5tk", "ks-mk", "ks5tk", "kse", "ksmk", "ksy",
    "lanek", "m3r9", "m7nh", "m87bh", "m9", "mfto7", "mfto7h",
    "mhan", "mhanh", "mm7on", "mm7onh", "mnyok", "mtnak", "mtnakh",
    "sharmo6h", "shrame6", "shrm6h", "shrmo6h", "shrmoth",
    "sks", "tjl5", "tm9", "tm9en", "y87bh", "ya87bh",
    "yabn", "ybn", "zane", "zaneh", "zany", "zanyh",
    "zbe", "zbo", "zby", "zpe", "zpo",
    "kos", "kosk", "kosmk", "kosomk", "kos omk", "kos amk",
    "zob", "zeb", "zebi", "zebak",
    "ayri", "ayrk", "eeri", "3air",
    "neek", "nek", "anik", "aneek", "aneekk",
    "sharmoot", "sharmoota", "sharmouta",
    "qahba", "gahba", "8ahba", "9ahba",
    "khaneeth", "khaneth", "5aneeth",
    "teez", "teezak", "teezy", "6eez",
    "mamhon", "mamhoon"
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.messages = True
intents.reactions = True

try:
    intents.moderation = True
except:
    pass

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


# =========================
# JSON
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
LOG_CHANNEL_IDS = load_json(LOG_CHANNELS_FILE, {})


def save_warnings():
    save_json(WARNINGS_FILE, warnings)


def save_log_channels():
    save_json(LOG_CHANNELS_FILE, LOG_CHANNEL_IDS)


# =========================
# DATABASE
# =========================

def db_connect():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS economy (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0
        )
    """)

    cur.execute("PRAGMA table_info(economy)")
    economy_columns = [row[1] for row in cur.fetchall()]

    if "last_boost_weekly" not in economy_columns:
        cur.execute("ALTER TABLE economy ADD COLUMN last_boost_weekly INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            suggestion TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prize TEXT,
            winners INTEGER,
            created_by INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            admin_name TEXT,
            action TEXT,
            details TEXT,
            created_at INTEGER
        )
    """)

    conn.commit()
    conn.close()


def get_level_data(user_id):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("SELECT xp, level FROM levels WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.execute(
            "INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)",
            (user_id, 0, 1)
        )
        conn.commit()
        conn.close()
        return 0, 1

    conn.close()
    return row[0], row[1]


def add_xp(user_id, amount):
    xp, level = get_level_data(user_id)

    xp += amount
    needed = level * 100
    leveled_up = False

    while xp >= needed:
        xp -= needed
        level += 1
        needed = level * 100
        leveled_up = True

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE levels SET xp = ?, level = ? WHERE user_id = ?",
        (xp, level, user_id)
    )
    conn.commit()
    conn.close()

    return xp, level, leveled_up


def get_top_levels(limit=10):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, xp, level
        FROM levels
        ORDER BY level DESC, xp DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_money_data(user_id):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("SELECT balance, last_daily FROM economy WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if not row:
        cur.execute(
            "INSERT INTO economy (user_id, balance, last_daily) VALUES (?, ?, ?)",
            (user_id, 0, 0)
        )
        conn.commit()
        conn.close()
        return 0, 0

    conn.close()
    return row[0], row[1]


def get_balance(user_id):
    balance, last_daily = get_money_data(user_id)
    return balance


def add_money(user_id, amount):
    balance, last_daily = get_money_data(user_id)
    balance += int(amount)

    if balance < 0:
        balance = 0

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ? WHERE user_id = ?",
        (balance, user_id)
    )
    conn.commit()
    conn.close()
    return balance


def remove_money(user_id, amount):
    amount = int(amount)
    balance, last_daily = get_money_data(user_id)

    if amount <= 0:
        return False, balance

    if balance < amount:
        return False, balance

    balance -= amount

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ? WHERE user_id = ?",
        (balance, user_id)
    )
    conn.commit()
    conn.close()
    return True, balance


def set_balance(user_id, amount):
    get_money_data(user_id)
    amount = max(0, int(amount))

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    conn.close()
    return amount


def claim_daily(user_id, level):
    balance, last_daily = get_money_data(user_id)
    now = int(time.time())
    cooldown = HOURLY_REWARD_COOLDOWN_SECONDS

    if now - last_daily < cooldown:
        remaining = cooldown - (now - last_daily)
        return False, remaining, balance, 0

    reward = DAILY_REWARD_BASE + (int(level) * 25)
    balance += reward

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ?, last_daily = ? WHERE user_id = ?",
        (balance, now, user_id)
    )
    conn.commit()
    conn.close()

    return True, 0, balance, reward


def is_server_booster(member):
    if not member or not getattr(member, "guild", None):
        return False

    return any(role.id == SERVER_BOOSTER_ROLE_ID for role in member.roles)


def get_booster_last_claim(user_id):
    get_money_data(user_id)

    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT last_boost_weekly FROM economy WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return 0

    return int(row[0] or 0)


def claim_booster_weekly(user_id):
    balance, last_daily = get_money_data(user_id)
    last_boost = get_booster_last_claim(user_id)
    now = int(time.time())

    if now - last_boost < BOOSTER_WEEKLY_COOLDOWN_SECONDS:
        remaining = BOOSTER_WEEKLY_COOLDOWN_SECONDS - (now - last_boost)
        return False, remaining, balance, 0

    reward = int(BOOSTER_WEEKLY_REWARD)
    balance += reward

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ?, last_boost_weekly = ? WHERE user_id = ?",
        (balance, now, user_id)
    )
    conn.commit()
    conn.close()

    return True, 0, balance, reward


def get_top_money(limit=10):
    conn = db_connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT user_id, balance
        FROM economy
        ORDER BY balance DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()
    return rows


def format_seconds(seconds):
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days} يوم و {hours} ساعة"

    if hours > 0:
        return f"{hours} ساعة و {minutes} دقيقة"

    return f"{minutes} دقيقة"




def xp_progress_bar(xp, needed, size=12):
    try:
        xp = int(xp)
        needed = max(1, int(needed))
        filled = min(size, max(0, round((xp / needed) * size)))
        return "▰" * filled + "▱" * (size - filled)
    except:
        return "▱" * size


def db_table_count(table_name):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cur.fetchone()[0]
        conn.close()
        return int(count)
    except:
        return 0


def db_sum_column(table_name, column_name):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(f"SELECT COALESCE(SUM({column_name}), 0) FROM {table_name}")
        total = cur.fetchone()[0]
        conn.close()
        return int(total or 0)
    except:
        return 0


def safe_len_json(file_name):
    try:
        data = load_json(file_name, {})
        if isinstance(data, dict):
            return len(data)
        if isinstance(data, list):
            return len(data)
        return 0
    except:
        return 0


def format_money(amount):
    try:
        return f"{int(amount):,} {COIN_NAME}"
    except:
        return f"0 {COIN_NAME}"


def short_money(amount):
    try:
        amount = int(amount)
    except:
        amount = 0

    sign = "-" if amount < 0 else ""
    amount = abs(amount)

    if amount >= 1_000_000_000:
        return f"{sign}{amount / 1_000_000_000:.2f}B".rstrip("0").rstrip(".")

    if amount >= 1_000_000:
        return f"{sign}{amount / 1_000_000:.2f}M".rstrip("0").rstrip(".")

    if amount >= 1_000:
        return f"{sign}{amount / 1_000:.1f}K".rstrip("0").rstrip(".")

    return f"{sign}{amount:,}"


def coin_line(amount, bold=True):
    try:
        value = int(amount)
    except:
        value = 0

    if bold:
        return f"**{value:,}** {ECONOMY_EMOJI} {COIN_NAME}"

    return f"{value:,} {ECONOMY_EMOJI} {COIN_NAME}"


def money_delta(amount):
    try:
        amount = int(amount)
    except:
        amount = 0

    sign = "+" if amount >= 0 else ""
    return f"**{sign}{amount:,}** {ECONOMY_EMOJI} {COIN_NAME}"


def get_money_rank(user_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) + 1
            FROM economy
            WHERE balance > (SELECT balance FROM economy WHERE user_id = ?)
        """, (user_id,))
        rank = cur.fetchone()[0]
        conn.close()
        return int(rank or 1)
    except:
        return None


def economy_status_text(user_id):
    balance = get_balance(user_id)
    rank = get_money_rank(user_id)
    rank_text = f"#{rank}" if rank else "غير معروف"
    return balance, rank_text


def clean_bar(percent, length=12):
    percent = max(0, min(1, float(percent)))
    filled = int(round(percent * length))
    return "█" * filled + "░" * (length - filled)


def slot_box(roll):
    return (
        "```txt\n"
        "╔═══════════════╗\n"
        f"║  {roll[0]} │ {roll[1]} │ {roll[2]}  ║\n"
        "╚═══════════════╝\n"
        "```"
    )


def member_display(member):
    if not member:
        return "غير معروف"
    return member.mention

def save_suggestion(user_id, suggestion):
    conn = db_connect()
    cur = conn.cursor()
    now = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    cur.execute(
        "INSERT INTO suggestions (user_id, suggestion, created_at) VALUES (?, ?, ?)",
        (user_id, suggestion, now)
    )

    conn.commit()
    conn.close()


# =========================
# HELPERS
# =========================

def normalize_bad_text(text):
    text = str(text).lower()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ئ": "ي",
        "ؤ": "و",
        "ة": "ه",
        "ڤ": "ف",
        "0": "o",
        "1": "i",
        "2": "ء",
        "3": "ع",
        "4": "a",
        "5": "خ",
        "6": "ط",
        "7": "ح",
        "8": "ق",
        "9": "ص",
        "@": "a",
        "$": "s",
        "!": "i",
        "*": "",
        "_": "",
        "-": "",
        ".": "",
        ",": "",
        "'": "",
        '"': "",
        "`": "",
        " ": "",
        "ـ": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return text


def contains_bad_word(content):
    original = str(content).lower()
    normalized_message = normalize_bad_text(content)

    for word in bad_words:
        word = word.lower().strip()

        if not word:
            continue

        normalized_word = normalize_bad_text(word)

        if len(normalized_word) >= 3 and normalized_word in normalized_message:
            return True

        pattern = r'(?<![\w\u0600-\u06FF])' + re.escape(word) + r'(?![\w\u0600-\u06FF])'

        if re.search(pattern, original):
            return True

    return False


def is_admin(member):
    return member.guild_permissions.administrator


def is_bypass(member):
    return member.id in BYPASS_USER_IDS or is_admin(member)


def parse_duration_to_seconds(duration_text):
    text = duration_text.strip().lower()
    match = re.fullmatch(r"(\d+)\s*([mhd])", text)

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if unit == "m":
        return amount * 60

    if unit == "h":
        return amount * 60 * 60

    if unit == "d":
        return amount * 60 * 60 * 24

    return None


def clean_text(text, limit=900):
    if not text:
        return "بدون نص"

    text = str(text).replace("```", "'''")

    if len(text) > limit:
        text = text[:limit] + "..."

    return text



async def require_commands_channel(ctx):
    if ctx.channel.id == COMMANDS_CHANNEL_ID:
        return True

    embed = discord.Embed(
        title="📍 الروم الغلط",
        description=f"استخدم أوامر اللفل والاقتصاد هنا: <#{COMMANDS_CHANNEL_ID}>",
        color=COLOR_ORANGE
    )
    embed.set_footer(text=f"{BOT_BRAND} | Commands")
    await ctx.send(embed=embed, delete_after=8)
    return False


async def require_gambling_channel(ctx):
    if ctx.channel.id == GAMBLING_CHANNEL_ID:
        return True

    embed = discord.Embed(
        title="🎰 الروم الغلط",
        description=f"أوامر القمار تشتغل فقط هنا: <#{GAMBLING_CHANNEL_ID}>",
        color=COLOR_ORANGE
    )
    embed.set_footer(text=f"{BOT_BRAND} | Gambling")
    await ctx.send(embed=embed, delete_after=8)
    return False


def parse_bet_amount(amount):
    if amount is None:
        return None

    text = str(amount).lower().replace(",", "").strip()

    multipliers = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
    }

    try:
        if text[-1:] in multipliers:
            number = float(text[:-1])
            return int(number * multipliers[text[-1]])

        return int(text)
    except:
        return None


def can_gamble_now(user_id):
    now = time.time()
    last = gamble_cooldowns.get(user_id, 0)

    if now - last < GAMBLE_COOLDOWN_SECONDS:
        return False, GAMBLE_COOLDOWN_SECONDS - (now - last)

    gamble_cooldowns[user_id] = now
    return True, 0


async def validate_gamble(ctx, amount_text):
    if not await require_gambling_channel(ctx):
        return None

    amount = parse_bet_amount(amount_text)

    if amount is None:
        await ctx.send("❌ اكتب مبلغ صحيح. مثال: `!حظ 500` أو `!حظ 10k` أو `!حظ 1m`")
        return None

    if amount <= 0:
        await ctx.send("❌ مبلغ الرهان لازم يكون أكبر من صفر.")
        return None

    ok, remaining = can_gamble_now(ctx.author.id)

    if not ok:
        await ctx.send(f"⏳ انتظر **{remaining:.1f} ثانية** قبل القمار مرة ثانية.", delete_after=4)
        return None

    balance = get_balance(ctx.author.id)

    if balance < amount:
        embed = discord.Embed(
            title="❌ رصيدك ما يكفي",
            description=f"ما تقدر تدخل برهان أعلى من رصيدك.\n\n**Wallet:** {coin_line(balance)}\n**Bet:** {coin_line(amount)}",
            color=COLOR_RED,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} | Gambling")
        await ctx.send(embed=embed)
        return None

    return amount


def gambling_embed(title, status, color, member, bet, result_amount=None, balance=None, details=None, game_name="Gambling"):
    embed = discord.Embed(
        title=title,
        description=status,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.set_author(name=f"{member.display_name} • {game_name}", icon_url=member.display_avatar.url)
    embed.add_field(name="🎯 Bet", value=coin_line(bet), inline=True)

    if result_amount is not None:
        embed.add_field(name="📈 Change", value=money_delta(result_amount), inline=True)

    if balance is not None:
        embed.add_field(name="💼 New Balance", value=coin_line(balance), inline=False)

    if details:
        embed.add_field(name="📌 Details", value=details, inline=False)

    embed.set_footer(text=f"{BOT_BRAND} • {game_name} • Cooldown {GAMBLE_COOLDOWN_SECONDS}s")
    return embed


async def dm_disabled_reply(ctx):
    await ctx.send(
        "❌ أوامر الخاص معطّلة حالياً لأن Discord حجز البوت بسبب نظام السبام.\n"
        "استخدم بدالها: `!اعلان نص الإعلان` أو اكتب الإعلان داخل روم الإعلانات."
    )

def can_use_mass_dm(ctx):
    if ctx.author.id in DM_OWNER_IDS:
        return True

    if ctx.guild and ctx.author.id == ctx.guild.owner_id:
        return True

    return False


def split_dm_embed_text(text):
    if "|" in text:
        title, body = text.split("|", 1)
        title = title.strip()
        body = body.strip()
    else:
        title = "📩 رسالة من إدارة السيرفر"
        body = text.strip()

    if not title:
        title = "📩 رسالة من إدارة السيرفر"

    if not body:
        body = "بدون محتوى"

    return title, body


async def send_private_message(target_member, title, body, sender):
    embed = discord.Embed(
        title=title,
        description=body,
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )

    embed.set_footer(text=f"NM System | Sent by {sender}")

    await target_member.send(embed=embed)


def clean_channel_name(name):
    name = str(name).lower()
    name = re.sub(r"[^a-zA-Z0-9\u0600-\u06FF\- ]", "", name)
    name = name.replace(" ", "-")
    name = name[:80]

    if not name:
        name = "game-room"

    return name


def format_roles_list(member):
    roles = [
        role.mention
        for role in member.roles
        if role.name != "@everyone"
    ]

    if not roles:
        return "ما كان عنده رتب", 0

    text = "\n".join([f"• {role}" for role in roles])

    if len(text) > 1000:
        text = text[:1000] + "\n..."

    return text, len(roles)


async def get_channel_by_id(guild, channel_id):
    if not channel_id:
        return None

    channel = guild.get_channel(int(channel_id))

    if channel:
        return channel

    try:
        channel = await guild.fetch_channel(int(channel_id))
        return channel
    except:
        return None


async def send_to_channel(guild, channel_id, embed=None, content=None, view=None):
    channel = await get_channel_by_id(guild, channel_id)

    if not channel:
        return None

    try:
        return await channel.send(content=content, embed=embed, view=view)
    except:
        return None



# =========================
# MEMORY BACKUP / RESTORE
# =========================

def json_file_valid(file_name):
    path = Path(file_name)
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return False

    try:
        with open(path, "r", encoding="utf-8") as file:
            json.load(file)
        return True
    except:
        return False


def db_file_valid():
    path = Path(DB_FILE)
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return False

    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        return "levels" in tables and "economy" in tables
    except:
        return False


def local_memory_status():
    status = {}

    for file_name in MEMORY_FILES:
        path = Path(file_name)
        exists = path.exists() and path.is_file()
        size = path.stat().st_size if exists else 0

        if file_name == DB_FILE:
            valid = db_file_valid()
        elif file_name.endswith(".json"):
            valid = json_file_valid(file_name)
        else:
            valid = exists and size > 0

        status[file_name] = {
            "exists": exists,
            "size": size,
            "valid": valid,
        }

    return status


def memory_needs_auto_restore():
    # The database is the main memory. If it is missing/corrupted, restore from Discord.
    return not db_file_valid()


def ensure_memory_placeholder_files():
    if not Path(WARNINGS_FILE).exists() or not json_file_valid(WARNINGS_FILE):
        save_json(WARNINGS_FILE, warnings if isinstance(warnings, dict) else {})

    if not Path(LOG_CHANNELS_FILE).exists() or not json_file_valid(LOG_CHANNELS_FILE):
        save_json(LOG_CHANNELS_FILE, LOG_CHANNEL_IDS if isinstance(LOG_CHANNEL_IDS, dict) else {})


def get_existing_memory_files():
    ensure_memory_placeholder_files()
    files = []

    for file_name in MEMORY_FILES:
        path = Path(file_name)
        if path.exists() and path.is_file():
            files.append(path)

    return files


def build_memory_report_text():
    status = local_memory_status()
    level_users = db_table_count("levels")
    economy_users = db_table_count("economy")
    total_coins = db_sum_column("economy", "balance")
    warning_users = safe_len_json(WARNINGS_FILE)
    log_channels_saved = safe_len_json(LOG_CHANNELS_FILE)

    lines = []
    lines.append("```txt")
    lines.append("RETARDS SYSTEM MEMORY REPORT")
    lines.append("----------------------------")
    lines.append(f"Level users      : {level_users}")
    lines.append(f"Economy users    : {economy_users}")
    lines.append(f"Total coins      : {total_coins:,} {COIN_NAME}")
    lines.append(f"Warning users    : {warning_users}")
    lines.append(f"Saved log rooms  : {log_channels_saved}")
    lines.append("")
    lines.append("FILES")

    for file_name, info in status.items():
        state = "OK" if info["valid"] else "CHECK"
        size_kb = round(info["size"] / 1024, 2)
        lines.append(f"- {file_name:<18} {state:<5} {size_kb} KB")

    lines.append("```")
    return "\n".join(lines)


def add_memory_stats_fields(embed):
    level_users = db_table_count("levels")
    economy_users = db_table_count("economy")
    total_coins = db_sum_column("economy", "balance")
    warning_users = safe_len_json(WARNINGS_FILE)
    log_channels_saved = safe_len_json(LOG_CHANNELS_FILE)

    embed.add_field(
        name="📊 اللفل والاقتصاد",
        value=(
            f"**Level users:** `{level_users}`\n"
            f"**Economy users:** `{economy_users}`\n"
            f"**Total coins:** `{total_coins:,}` {COIN_NAME}"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ ملفات النظام",
        value=(
            f"**Warning users:** `{warning_users}`\n"
            f"**Saved log rooms:** `{log_channels_saved}`"
        ),
        inline=True
    )

    top_money = get_top_money(5)
    if top_money:
        money_text = ""
        for i, (user_id, balance) in enumerate(top_money, start=1):
            money_text += f"`{i}.` <@{user_id}> — **{balance:,}**\n"
        embed.add_field(name=f"{ECONOMY_EMOJI} Top Money", value=money_text[:1000], inline=False)

    top_levels = get_top_levels(5)
    if top_levels:
        level_text = ""
        for i, (user_id, xp, level) in enumerate(top_levels, start=1):
            level_text += f"`{i}.` <@{user_id}> — **Lv.{level}** | XP `{xp}`\n"
        embed.add_field(name="🏆 Top Levels", value=level_text[:1000], inline=False)


async def create_memory_backup(guild, reason="Manual backup", requested_by=None):
    channel = await get_channel_by_id(guild, MEMORY_BACKUP_CHANNEL_ID)

    if not channel:
        return False, "ما لقيت روم النسخ الاحتياطي. تأكد من MEMORY_BACKUP_CHANNEL_ID."

    init_db()
    files = get_existing_memory_files()

    if not files:
        return False, "ما لقيت ملفات ذاكرة عشان أحفظها."

    attachments = []

    try:
        for path in files:
            attachments.append(discord.File(str(path), filename=path.name))

        report_text = build_memory_report_text()
        report_path = Path("memory_report.txt")
        report_path.write_text(report_text.replace("```txt\n", "").replace("```", ""), encoding="utf-8")
        attachments.append(discord.File(str(report_path), filename="memory_report.txt"))

        now_unix = int(time.time())
        requester = requested_by.mention if requested_by else "النظام التلقائي"
        file_lines = []

        for path in files:
            size_kb = round(path.stat().st_size / 1024, 2)
            file_lines.append(f"• `{path.name}` — `{size_kb} KB`")

        embed = discord.Embed(
            title="💾 Memory Backup Saved",
            description=(
                f"`{MEMORY_BACKUP_MESSAGE_TAG}`\n\n"
                f"**السبب:** {reason}\n"
                f"**بواسطة:** {requester}\n"
                f"**الوقت:** <t:{now_unix}:F> | <t:{now_unix}:R>\n\n"
                f"✅ تم حفظ ملفات الذاكرة + تقرير مقروء."
            ),
            color=COLOR_BLUE,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="📦 الملفات المحفوظة",
            value="\n".join(file_lines)[:1000],
            inline=False
        )
        add_memory_stats_fields(embed)
        embed.set_footer(text=f"{BOT_BRAND} | Auto Memory System")

        await channel.send(content=MEMORY_BACKUP_MESSAGE_TAG, embed=embed, files=attachments)
        return True, f"تم حفظ النسخة في {channel.mention} مع تقرير واضح."

    except Exception as e:
        return False, f"فشل حفظ النسخة: {e}"


async def find_latest_memory_backup_message(channel, limit=MEMORY_BACKUP_HISTORY_LIMIT):
    try:
        async for message in channel.history(limit=limit):
            has_tag = False
            tags = set(MEMORY_BACKUP_OLD_TAGS + [MEMORY_BACKUP_MESSAGE_TAG])

            if message.content and any(tag in message.content for tag in tags):
                has_tag = True

            if not has_tag and message.embeds:
                for embed in message.embeds:
                    parts = [embed.title or "", embed.description or ""]
                    if any(any(tag in part for tag in tags) for part in parts):
                        has_tag = True
                        break

            if not has_tag:
                continue

            attachment_names = {attachment.filename for attachment in message.attachments}
            needed = set(MEMORY_FILES)

            if needed.intersection(attachment_names):
                return message

    except Exception as e:
        print(f"Find memory backup error: {e}")

    return None


async def restore_memory_from_backup(guild, force=False):
    global warnings, LOG_CHANNEL_IDS

    if not force and not memory_needs_auto_restore():
        ensure_memory_placeholder_files()
        return False, "قاعدة البيانات موجودة وسليمة، ما احتجت أسترجع من الروم."

    channel = await get_channel_by_id(guild, MEMORY_BACKUP_CHANNEL_ID)

    if not channel:
        return False, "ما لقيت روم النسخ الاحتياطي."

    backup_message = await find_latest_memory_backup_message(channel)

    if not backup_message:
        return False, "ما لقيت أي نسخة احتياطية محفوظة في الروم."

    restored_files = []

    try:
        for attachment in backup_message.attachments:
            if attachment.filename not in MEMORY_FILES:
                continue

            file_bytes = await attachment.read()
            if not file_bytes:
                continue

            Path(attachment.filename).write_bytes(file_bytes)
            restored_files.append(attachment.filename)

        if not restored_files:
            return False, "لقيت رسالة Backup لكن ما لقيت ملفات ذاكرة داخلها."

        warnings = load_json(WARNINGS_FILE, {})
        LOG_CHANNEL_IDS = load_json(LOG_CHANNELS_FILE, {})
        init_db()

        return True, "تم استرجاع: " + ", ".join(restored_files)

    except Exception as e:
        return False, f"فشل الاسترجاع: {e}"



def build_economy_guide_embed(auto=False):
    title = "🪙 شرح نظام الاقتصاد واللفل"
    description = (
        "هذا شرح سريع للنظام. كل شيء يشتغل في روم الأوامر فقط.\n"
        f"روم الأوامر: <#{COMMANDS_CHANNEL_ID}>"
    )

    if auto:
        description = (
            "تذكير تلقائي: تقدر تستخدم أوامر الاقتصاد واللفل هنا.\n"
            f"روم الأوامر: <#{COMMANDS_CHANNEL_ID}>"
        )

    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="💰 الفلوس",
        value=(
            f"العملة: **{COIN_NAME}**\n"
            "`!رصيدي` يعرض رصيدك\n"
            "`!رصيد @شخص` يعرض رصيد شخص\n"
            "`!اغنى` يعرض أغنى 10 أعضاء"
        ),
        inline=False
    )

    embed.add_field(
        name="🎁 المكافأة الساعية",
        value=(
            "`!يومي` أو `!ساعتي`\n"
            "تقدر تاخذ مكافأة كل **ساعة**.\n"
            "كل ما لفلك أعلى، المكافأة تزيد شوي."
        ),
        inline=False
    )

    embed.add_field(
        name="📊 اللفل",
        value=(
            "`!لفلي` يعرض لفلك و XP\n"
            "`!لفل @شخص` يعرض لفل شخص\n"
            "`!ترتيب` يعرض ترتيب اللفلات\n"
            "تجمع XP من النشاط والرسائل بدون سبام."
        ),
        inline=False
    )

    embed.add_field(
        name="🔁 التحويل",
        value="`!تحويل @شخص 500` يحول فلوس لشخص ثاني.",
        inline=False
    )

    embed.add_field(
        name="🎰 القمار بعملة البوت",
        value=(
            f"روم القمار: <#{GAMBLING_CHANNEL_ID}>\n"
            "`!شرح_القمار` شرح أوامر القمار\n"
            "`!حظ 500` نسبة 50/50\n"
            "`!دبل 500` أخطر، لكن يعطي دبل\n"
            "`!سلوت 500` رموز وجوائز عشوائية\n"
            "`!وجه 500 ملك` أو `!وجه 500 كتابة`"
        ),
        inline=False
    )

    embed.add_field(
        name="🛡️ أوامر الإدارة",
        value=(
            "`!اعطاءفلوس @شخص 1000`\n"
            "`!سحبفلوس @شخص 500`\n"
            "`!تصفيرفلوس @شخص`"
        ),
        inline=False
    )

    embed.set_footer(text=f"{BOT_BRAND} | Economy Guide")
    return embed


async def economy_explain_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(60)

    while not bot.is_closed():
        try:
            guild = bot.get_guild(GUILD_ID)

            if guild:
                channel = await get_channel_by_id(guild, ECONOMY_EXPLAIN_CHANNEL_ID)

                if channel:
                    await channel.send(embed=build_economy_guide_embed(auto=True))

        except Exception as e:
            print(f"Auto economy guide error: {e}")

        await asyncio.sleep(ECONOMY_EXPLAIN_INTERVAL_SECONDS)


async def memory_backup_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(30)

    while not bot.is_closed():
        try:
            guild = bot.get_guild(GUILD_ID)

            if guild:
                await create_memory_backup(guild, reason="Auto backup")

        except Exception as e:
            print(f"Auto memory backup error: {e}")

        await asyncio.sleep(MEMORY_BACKUP_INTERVAL_SECONDS)

async def create_or_find_log_channels(guild):
    category = guild.get_channel(LOGS_CATEGORY_ID)

    if not category or not isinstance(category, discord.CategoryChannel):
        category = None

    created_or_found = {}

    for log_key, channel_name in LOG_CHANNEL_NAMES.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)

        if not channel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False,
                    send_messages=False
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    manage_channels=True
                )
            }

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="NM System log channel setup"
            )

        else:
            if category and channel.category != category:
                try:
                    await channel.edit(category=category)
                except:
                    pass

        LOG_CHANNEL_IDS[log_key] = channel.id
        created_or_found[log_key] = channel

    save_log_channels()
    return created_or_found


async def get_log_channel_by_type(guild, log_type="general"):
    channel_id = LOG_CHANNEL_IDS.get(log_type)

    if channel_id:
        channel = guild.get_channel(int(channel_id))

        if channel:
            return channel

    if LOG_CHANNEL_ID:
        channel = await get_channel_by_id(guild, LOG_CHANNEL_ID)

        if channel:
            return channel

    names = ["logs", "log", "audit-log", "audit-logs", "لوق", "لوقات"]

    for channel in guild.text_channels:
        if channel.name.lower() in names:
            return channel

    return None


async def send_log(guild, title, description, color=COLOR_GREY, log_type="general"):
    channel = await get_log_channel_by_type(guild, log_type)

    if not channel:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.set_footer(text=f"NM System | {log_type} logs")

    try:
        await channel.send(embed=embed)
    except:
        pass


async def get_audit_executor(guild, action, target_id=None):
    try:
        async for entry in guild.audit_logs(limit=7, action=action):
            if target_id is None:
                return entry

            if entry.target and getattr(entry.target, "id", None) == target_id:
                return entry

        return None
    except:
        return None


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


async def apply_punishment(member, channel, count):
    try:
        if count == 2:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=5))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 5 دقائق.", delete_after=6)
            return "تايم أوت 5 دقائق"

        if count == 3:
            await member.timeout(discord.utils.utcnow() + timedelta(minutes=30))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت 30 دقيقة.", delete_after=6)
            return "تايم أوت 30 دقيقة"

        if count >= 4:
            await member.timeout(discord.utils.utcnow() + timedelta(days=1))
            await channel.send(f"{member.mention} تم إعطاؤه تايم أوت يوم.", delete_after=6)
            return "تايم أوت يوم"

        return "تحذير فقط"

    except Exception as e:
        return f"فشل العقوبة: {e}"


async def handle_violation(message, reason):
    old_message = message.content

    try:
        await message.delete()
    except:
        pass

    count = add_warning(message.author, reason, old_message, "النظام التلقائي")
    punishment = await apply_punishment(message.author, message.channel, count)

    embed = discord.Embed(
        title="⚠️ تحذير تلقائي",
        description=f"{message.author.mention} أخذ تحذير رقم **{count}**",
        color=COLOR_YELLOW
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="الإجراء", value=punishment, inline=False)

    await message.channel.send(embed=embed, delete_after=8)

    await send_log(
        message.guild,
        "🛡️ مخالفة حماية",
        f"""
**العضو:** {message.author.mention}
**ID:** `{message.author.id}`
**الروم:** {message.channel.mention}
**السبب:** {reason}
**الإجراء:** {punishment}

**الرسالة:**
```{clean_text(old_message, 800)}```
""",
        COLOR_YELLOW,
        log_type="moderation"
    )


async def create_or_find_game_roles(guild):
    found_roles = []

    for key, role_id in GAME_ROLE_IDS.items():
        role = guild.get_role(int(role_id))

        if role:
            found_roles.append(role)
        else:
            print(f"Role not found for key {key}: {role_id}")

    return found_roles


async def schedule_delete_empty_game_room(channel):
    if not channel:
        return

    if not isinstance(channel, discord.VoiceChannel):
        return

    if not channel.name.startswith("🎮-"):
        return

    if channel.id in game_room_delete_tasks:
        return

    async def delete_later():
        try:
            await asyncio.sleep(GAME_ROOM_DELETE_SECONDS)

            fresh_channel = channel.guild.get_channel(channel.id)

            if not fresh_channel:
                return

            if len(fresh_channel.members) == 0:
                await send_log(
                    fresh_channel.guild,
                    "🧹 حذف روم لعب فاضي",
                    f"""
**الروم:** `{fresh_channel.name}`
**السبب:** الروم صار فاضي لمدة 5 دقائق.
""",
                    COLOR_GREY,
                    log_type="game"
                )

                await fresh_channel.delete(reason="NM System auto deleted empty game room")

        except asyncio.CancelledError:
            return

        except Exception as e:
            print(f"Auto delete game room error: {e}")

        finally:
            game_room_delete_tasks.pop(channel.id, None)

    task = asyncio.create_task(delete_later())
    game_room_delete_tasks[channel.id] = task


def cancel_game_room_delete(channel):
    if not channel:
        return

    task = game_room_delete_tasks.get(channel.id)

    if task:
        task.cancel()
        game_room_delete_tasks.pop(channel.id, None)


async def create_game_voice_channel(guild, source_channel, game, player_ids, max_players):
    members = []

    for user_id in player_ids:
        member = guild.get_member(user_id)

        if member:
            members.append(member)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            connect=False
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            speak=True,
            manage_channels=True
        )
    }

    for member in members:
        overwrites[member] = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            speak=True,
            stream=True,
            use_voice_activation=True
        )

    category = guild.get_channel(GAME_VOICE_CATEGORY_ID)

    if not category or not isinstance(category, discord.CategoryChannel):
        category = source_channel.category if source_channel else None

    channel_name = f"🎮-{clean_channel_name(game)}"

    voice_channel = await guild.create_voice_channel(
        name=channel_name,
        overwrites=overwrites,
        category=category,
        reason="NM System LFG private voice room"
    )

    players_text = "\n".join([f"• <@{uid}>" for uid in player_ids]) or "لا يوجد"

    embed = discord.Embed(
        title="✅ تم اكتمال التجمع",
        description=(
            f"اللعبة: **{game}**\n"
            f"العدد: **{len(player_ids)}/{max_players}**\n\n"
            f"تم فتح روم فويس خاص:\n{voice_channel.mention}\n\n"
            f"الكل يقدر يشوف الروم، لكن الدخول فقط للمسجلين."
        ),
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="👥 اللاعبين",
        value=players_text[:1000],
        inline=False
    )

    embed.set_footer(text="NM System | Looking For Game")

    if source_channel:
        await source_channel.send(embed=embed)

    await send_log(
        guild,
        "🎮 تم فتح روم لعب خاص",
        f"""
**اللعبة:** {game}
**الروم:** {voice_channel.mention}
**الكاتقوري:** `{category.name if category else 'غير معروف'}`
**العدد:** {len(player_ids)}/{max_players}

**اللاعبين:**
{players_text}
""",
        COLOR_GREEN,
        log_type="game"
    )

    if len(voice_channel.members) == 0:
        await schedule_delete_empty_game_room(voice_channel)

    return voice_channel


# =========================
# VIEWS
# =========================

class JoinPlayView(discord.ui.View):
    def __init__(self, game, max_players, host_id, note=""):
        super().__init__(timeout=None)

        self.game = game
        self.max_players = max_players
        self.host_id = host_id
        self.note = note

        self.players = set()
        self.players.add(host_id)

        self.channel_created = False
        self.created_channel_id = None
        self.cancelled = False

    def make_players_text(self):
        return "\n".join([f"• <@{uid}>" for uid in self.players]) or "لا يوجد"

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    async def create_private_game_voice(self, interaction):
        if self.channel_created:
            return

        voice_channel = await create_game_voice_channel(
            guild=interaction.guild,
            source_channel=interaction.channel,
            game=self.game,
            player_ids=list(self.players),
            max_players=self.max_players
        )

        self.channel_created = True
        self.created_channel_id = voice_channel.id

    async def refresh_embed(self, interaction, status_text=None):
        players_text = self.make_players_text()
        current_count = len(self.players)

        embed = discord.Embed(
            title="🎮 Looking For Game",
            description=f"تجمع على **{self.game}**",
            color=COLOR_GREEN,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(
            name="👤 صاحب التجمع",
            value=f"<@{self.host_id}>",
            inline=True
        )

        embed.add_field(
            name="👥 العدد",
            value=f"{current_count}/{self.max_players}",
            inline=True
        )

        embed.add_field(
            name="📝 ملاحظة",
            value=self.note if self.note else "لا يوجد",
            inline=False
        )

        embed.add_field(
            name="👥 اللي بيدخلون",
            value=players_text[:1000],
            inline=False
        )

        if status_text:
            embed.add_field(
                name="📌 الحالة",
                value=status_text,
                inline=False
            )

        if current_count >= self.max_players and not self.cancelled:
            embed.add_field(
                name="🔒 الحالة",
                value="اكتمل العدد وتم قفل الدخول.",
                inline=False
            )

        embed.set_footer(text="NM System | Looking For Game")

        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(
        label="بدخل",
        style=discord.ButtonStyle.green,
        emoji="🎮",
        custom_id="join_play_button"
    )
    async def join_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.cancelled:
            await interaction.response.send_message("❌ التجمع ملغي.", ephemeral=True)
            return

        if self.channel_created:
            await interaction.response.send_message("❌ التجمع اكتمل وتم فتح الروم.", ephemeral=True)
            return

        if interaction.user.id in self.players:
            await interaction.response.send_message("✅ أنت داخل التجمع أصلًا.", ephemeral=True)
            return

        if len(self.players) >= self.max_players:
            await interaction.response.send_message("❌ التجمع اكتمل، ما تقدر تدخل.", ephemeral=True)
            return

        self.players.add(interaction.user.id)

        if len(self.players) >= self.max_players:
            self.disable_all_buttons()

            await self.refresh_embed(
                interaction,
                status_text="✅ اكتمل العدد. تم فتح روم فويس خاص."
            )

            await interaction.response.send_message(
                "✅ دخلت التجمع، واكتمل العدد. تم فتح الروم الخاص.",
                ephemeral=True
            )

            await self.create_private_game_voice(interaction)
            return

        await self.refresh_embed(interaction)

        await interaction.response.send_message(
            f"✅ تم تسجيلك. العدد الآن {len(self.players)}/{self.max_players}.",
            ephemeral=True
        )

    @discord.ui.button(
        label="بطلع",
        style=discord.ButtonStyle.secondary,
        emoji="🚪",
        custom_id="leave_play_button"
    )
    async def leave_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.cancelled:
            await interaction.response.send_message("❌ التجمع ملغي.", ephemeral=True)
            return

        if self.channel_created:
            await interaction.response.send_message(
                "❌ ما تقدر تطلع بعد ما اكتمل التجمع وانفتح الروم.",
                ephemeral=True
            )
            return

        if interaction.user.id == self.host_id:
            await interaction.response.send_message(
                "⚠️ أنت صاحب التجمع. استخدم زر **إلغاء التجمع** بدل الخروج.",
                ephemeral=True
            )
            return

        if interaction.user.id not in self.players:
            await interaction.response.send_message("❌ أنت مو داخل التجمع.", ephemeral=True)
            return

        self.players.remove(interaction.user.id)

        await self.refresh_embed(
            interaction,
            status_text=f"🚪 {interaction.user.mention} طلع من التجمع."
        )

        await interaction.response.send_message("✅ طلعت من التجمع.", ephemeral=True)

    @discord.ui.button(
        label="إلغاء التجمع",
        style=discord.ButtonStyle.red,
        emoji="❌",
        custom_id="cancel_play_button"
    )
    async def cancel_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message(
                "❌ فقط صاحب التجمع يقدر يلغيه.",
                ephemeral=True
            )
            return

        if self.channel_created:
            await interaction.response.send_message(
                "❌ ما تقدر تلغي التجمع بعد ما اكتمل وانفتح الروم.",
                ephemeral=True
            )
            return

        self.cancelled = True
        self.disable_all_buttons()

        players_text = self.make_players_text()

        embed = discord.Embed(
            title="❌ تم إلغاء التجمع",
            description=f"تم إلغاء تجمع **{self.game}** بواسطة صاحب التجمع.",
            color=COLOR_RED,
            timestamp=discord.utils.utcnow()
        )

        embed.add_field(name="👤 صاحب التجمع", value=f"<@{self.host_id}>", inline=True)
        embed.add_field(name="👥 العدد قبل الإلغاء", value=f"{len(self.players)}/{self.max_players}", inline=True)
        embed.add_field(name="👥 اللي كانوا داخلين", value=players_text[:1000], inline=False)
        embed.set_footer(text="NM System | Looking For Game")

        await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message("✅ تم إلغاء التجمع.", ephemeral=True)

        await send_log(
            interaction.guild,
            "❌ تم إلغاء تجمع لعب",
            f"""
**اللعبة:** {self.game}
**صاحب التجمع:** <@{self.host_id}>
**العدد وقت الإلغاء:** {len(self.players)}/{self.max_players}

**اللاعبين:**
{players_text}
""",
            COLOR_RED,
            log_type="game"
        )


class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.entries = set()

    @discord.ui.button(
        label="دخول السحب",
        style=discord.ButtonStyle.green,
        emoji="🎁",
        custom_id="giveaway_join_button"
    )
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.entries.add(interaction.user.id)
        await interaction.response.send_message("✅ دخلت السحب.", ephemeral=True)


class GameRoleButton(discord.ui.Button):
    def __init__(self, role_key, label, emoji):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"game_role_{role_key}"
        )
        self.role_key = role_key

    async def callback(self, interaction: discord.Interaction):
        role_id = GAME_ROLE_IDS.get(self.role_key)

        if not role_id:
            await interaction.response.send_message("⚠️ الرتبة غير موجودة في الكود.", ephemeral=True)
            return

        role = interaction.guild.get_role(int(role_id))

        if not role:
            await interaction.response.send_message("⚠️ ما لقيت الرتبة في السيرفر. تأكد من ID الرتبة.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ شلت منك رتبة {role.mention}", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ عطيتك رتبة {role.mention}", ephemeral=True)


class GameRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        for key, data in GAME_ROLES.items():
            self.add_item(GameRoleButton(key, data["name"], data["emoji"]))


# =========================
# KEEP ALIVE
# =========================

app = Flask(__name__)
app.secret_key = DASHBOARD_SECRET_KEY

# =========================
# WEB DASHBOARD HELPERS
# =========================

def dashboard_redirect_uri():
    if not DASHBOARD_BASE_URL:
        return ""
    return f"{DASHBOARD_BASE_URL}/callback"


def dashboard_auth_url():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": dashboard_redirect_uri(),
        "response_type": "code",
        "scope": "identify guilds",
        "prompt": "consent",
    }
    return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(params)


def oauth_post_token(code):
    data = urllib.parse.urlencode({
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": dashboard_redirect_uri(),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{DISCORD_API_BASE}/oauth2/token",
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "NM-System-Dashboard/1.0",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = "No response body"
        raise Exception(
            f"Discord token exchange failed: HTTP {e.code}. "
            f"Response: {body}. "
            f"Redirect URI used: {dashboard_redirect_uri()}"
        )


def oauth_get_user(access_token):
    req = urllib.request.Request(
        f"{DISCORD_API_BASE}/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "NM-System-Dashboard/1.0",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = "No response body"
        raise Exception(f"Discord user fetch failed: HTTP {e.code}. Response: {body}")


async def dashboard_fetch_member(user_id):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return None
    member = guild.get_member(int(user_id))
    if member:
        return member
    try:
        return await guild.fetch_member(int(user_id))
    except:
        return None


def dashboard_get_member_sync(user_id):
    try:
        future = asyncio.run_coroutine_threadsafe(dashboard_fetch_member(int(user_id)), bot.loop)
        return future.result(timeout=10)
    except:
        return None


def dashboard_user_has_access(user_id):
    try:
        user_id = int(user_id)
    except:
        return False
    guild = bot.get_guild(GUILD_ID)
    if guild and user_id == int(guild.owner_id):
        return True
    member = dashboard_get_member_sync(user_id)
    if not member:
        return False
    if member.guild_permissions.administrator:
        return True
    if DASHBOARD_ADMIN_ROLE_IDS:
        return any(role.id in DASHBOARD_ADMIN_ROLE_IDS for role in member.roles)
    return False


def dashboard_require_admin():
    if not session.get("discord_user"):
        return redirect("/login")
    if not dashboard_user_has_access(session["discord_user"].get("id")):
        return render_dashboard_page("Access Denied", '<div class="card danger"><h2>🚫 Access Denied</h2><p>حسابك داخل Discord ما عنده صلاحية دخول للداشبورد.</p><p>الدخول مسموح فقط لصاحب السيرفر أو اللي عنده Administrator أو الرتب المحددة.</p><a class="btn" href="/logout">Logout</a></div>', status=403)
    return None


def dashboard_count_table(table):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        value = cur.fetchone()[0]
        conn.close()
        return int(value or 0)
    except:
        return 0


def dashboard_total_coins():
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(balance), 0) FROM economy")
        value = cur.fetchone()[0]
        conn.close()
        return int(value or 0)
    except:
        return 0


def dashboard_set_level_data(user_id, xp=None, level=None):
    old_xp, old_level = get_level_data(user_id)
    new_xp = old_xp if xp is None else max(0, int(xp))
    new_level = old_level if level is None else max(1, int(level))
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (new_xp, new_level, int(user_id)))
    conn.commit()
    conn.close()
    return new_xp, new_level


def dashboard_member_name(user_id):
    member = dashboard_get_member_sync(user_id)
    if member:
        return str(member)
    return f"User {user_id}"


def dashboard_money_rows(limit=10):
    rows = []
    for i, (user_id, balance) in enumerate(get_top_money(limit), start=1):
        rows.append({"rank": i, "user_id": int(user_id), "name": dashboard_member_name(user_id), "balance": int(balance or 0)})
    return rows


def dashboard_level_rows(limit=10):
    rows = []
    for i, (user_id, xp, level) in enumerate(get_top_levels(limit), start=1):
        rows.append({"rank": i, "user_id": int(user_id), "name": dashboard_member_name(user_id), "level": int(level or 1), "xp": int(xp or 0)})
    return rows


def dashboard_memory_summary():
    status = local_memory_status()
    rows = []
    for file_name, info in status.items():
        badge = "OK" if info.get("valid") else "CHECK"
        size_kb = round(int(info.get("size", 0)) / 1024, 2)
        rows.append({"file": file_name, "badge": badge, "size": size_kb})
    return rows




def fmt_num(value):
    try:
        return f"{int(value):,}"
    except:
        return str(value)


def fmt_coin(value):
    return f"🪙 {fmt_num(value)} {COIN_NAME}"


def parse_int_field(value, default=0, minimum=None):
    try:
        n = int(str(value).replace(",", "").strip())
    except:
        n = default
    if minimum is not None and n < minimum:
        n = minimum
    return n


def dashboard_toast_html():
    msg = request.args.get("msg", "")
    err = request.args.get("err", "")
    if msg:
        return f'<div class="toast ok">✅ {clean_text(msg, 260)}</div>'
    if err:
        return f'<div class="toast bad">❌ {clean_text(err, 260)}</div>'
    return ""


def dashboard_table_exists(table_name):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        exists = cur.fetchone() is not None
        conn.close()
        return exists
    except:
        return False


def dashboard_latest_economy_rows(limit=25):
    rows = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT user_id, balance, last_daily FROM economy ORDER BY balance DESC LIMIT ?", (int(limit),))
        for user_id, balance, last_daily in cur.fetchall():
            rows.append({
                "user_id": int(user_id),
                "name": dashboard_member_name(user_id),
                "balance": int(balance or 0),
                "last_daily": int(last_daily or 0),
            })
        conn.close()
    except:
        pass
    return rows


def dashboard_latest_level_rows(limit=25):
    rows = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT user_id, xp, level FROM levels ORDER BY level DESC, xp DESC LIMIT ?", (int(limit),))
        for user_id, xp, level in cur.fetchall():
            rows.append({
                "user_id": int(user_id),
                "name": dashboard_member_name(user_id),
                "xp": int(xp or 0),
                "level": int(level or 1),
            })
        conn.close()
    except:
        pass
    return rows


def dashboard_user_profile(user_id):
    balance = get_balance(int(user_id))
    xp, level = get_level_data(int(user_id))
    user_warnings = warnings.get(str(user_id), [])
    member = dashboard_get_member_sync(user_id)
    return {
        "user_id": int(user_id),
        "name": str(member) if member else f"User {user_id}",
        "avatar": member.display_avatar.url if member else "",
        "balance": balance,
        "xp": xp,
        "level": level,
        "warnings": user_warnings,
        "roles": [r.name for r in member.roles if r.name != "@everyone"] if member else [],
        "joined_at": int(member.joined_at.timestamp()) if member and member.joined_at else None,
    }


def dashboard_load_settings_file():
    try:
        with open(DASHBOARD_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}


def dashboard_save_settings_file(data):
    with open(DASHBOARD_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def dashboard_control_settings():
    data = dashboard_load_settings_file()
    systems = dict(DEFAULT_SYSTEM_TOGGLES)
    saved_systems = data.get("system_toggles", {})
    if isinstance(saved_systems, dict):
        for key, value in saved_systems.items():
            if key in systems:
                systems[key] = bool(value)

    commands = {}
    saved_commands = data.get("command_toggles", {})
    if isinstance(saved_commands, dict):
        for key, value in saved_commands.items():
            commands[str(key)] = bool(value)

    def safe_int(value, default):
        try:
            return int(value)
        except:
            return default

    return {
        "emergency_lockdown": bool(data.get("emergency_lockdown", False)),
        "system_toggles": systems,
        "command_toggles": commands,
        "policies": {
            "large_transfer_alert": safe_int(data.get("large_transfer_alert", 100000), 100000),
            "large_admin_money_alert": safe_int(data.get("large_admin_money_alert", 250000), 250000),
            "large_gamble_alert": safe_int(data.get("large_gamble_alert", 250000), 250000),
        },
        "dashboard_audit_channel_id": safe_int(data.get("dashboard_audit_channel_id", 0), 0),
    }


def is_system_enabled(system_name):
    control = dashboard_control_settings()
    if control.get("emergency_lockdown") and system_name not in EMERGENCY_ALLOWED_SYSTEMS:
        return False
    return bool(control["system_toggles"].get(system_name, True))


def is_command_enabled(command_name):
    control = dashboard_control_settings()
    return bool(control["command_toggles"].get(str(command_name), True))


def command_system(command_name):
    return COMMAND_SYSTEM_MAP.get(str(command_name), "utility")


def dashboard_audit_rows(limit=50):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT admin_id, admin_name, action, details, created_at FROM dashboard_audit ORDER BY id DESC LIMIT ?", (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def dashboard_log_action(action, details="", admin=None, send_discord=True):
    admin_id = 0
    admin_name = "System"
    if admin:
        try:
            admin_id = int(admin.get("id", 0))
            admin_name = str(admin.get("username", "Dashboard Admin"))
        except:
            pass
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("INSERT INTO dashboard_audit (admin_id, admin_name, action, details, created_at) VALUES (?, ?, ?, ?, ?)", (admin_id, admin_name, str(action)[:120], str(details)[:1200], int(time.time())))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Dashboard audit db error: {e}")
    if send_discord and bot and getattr(bot, "loop", None) and bot.loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(send_dashboard_action_log(admin_name, admin_id, action, details), bot.loop)
        except Exception as e:
            print(f"Dashboard audit discord schedule error: {e}")


async def send_dashboard_action_log(admin_name, admin_id, action, details):
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return
        control = dashboard_control_settings()
        channel_id = control.get("dashboard_audit_channel_id") or LOG_CHANNEL_IDS.get("server") or LOG_CHANNEL_IDS.get("moderation")
        channel = await get_channel_by_id(guild, channel_id) if channel_id else await get_log_channel_by_type(guild, "server")
        if not channel:
            return
        embed = discord.Embed(title="🛡️ Dashboard Action", color=COLOR_PURPLE, timestamp=discord.utils.utcnow())
        embed.add_field(name="Admin", value=f"{clean_text(admin_name, 80)} (`{admin_id}`)", inline=False)
        embed.add_field(name="Action", value=clean_text(action, 250), inline=False)
        if details:
            embed.add_field(name="Details", value=clean_text(details, 900), inline=False)
        embed.set_footer(text=f"{BOT_BRAND} | Admin Control Center")
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Dashboard action log error: {e}")


def dashboard_apply_saved_settings():
    global COMMANDS_CHANNEL_ID, GAMBLING_CHANNEL_ID, MEMORY_BACKUP_CHANNEL_ID
    global GAMBLE_COOLDOWN_SECONDS, ECONOMY_EXPLAIN_INTERVAL_SECONDS, BOOSTER_WEEKLY_REWARD, COIN_NAME
    data = dashboard_load_settings_file()
    if not data:
        return
    COMMANDS_CHANNEL_ID = parse_int_field(data.get("COMMANDS_CHANNEL_ID", COMMANDS_CHANNEL_ID), COMMANDS_CHANNEL_ID, 1)
    GAMBLING_CHANNEL_ID = parse_int_field(data.get("GAMBLING_CHANNEL_ID", GAMBLING_CHANNEL_ID), GAMBLING_CHANNEL_ID, 1)
    MEMORY_BACKUP_CHANNEL_ID = parse_int_field(data.get("MEMORY_BACKUP_CHANNEL_ID", MEMORY_BACKUP_CHANNEL_ID), MEMORY_BACKUP_CHANNEL_ID, 1)
    GAMBLE_COOLDOWN_SECONDS = parse_int_field(data.get("GAMBLE_COOLDOWN_SECONDS", GAMBLE_COOLDOWN_SECONDS), GAMBLE_COOLDOWN_SECONDS, 0)
    ECONOMY_EXPLAIN_INTERVAL_SECONDS = parse_int_field(data.get("ECONOMY_EXPLAIN_INTERVAL_SECONDS", ECONOMY_EXPLAIN_INTERVAL_SECONDS), ECONOMY_EXPLAIN_INTERVAL_SECONDS, 60)
    BOOSTER_WEEKLY_REWARD = parse_int_field(data.get("BOOSTER_WEEKLY_REWARD", BOOSTER_WEEKLY_REWARD), BOOSTER_WEEKLY_REWARD, 0)
    if str(data.get("COIN_NAME", "")).strip():
        COIN_NAME = str(data.get("COIN_NAME")).strip()[:40]


dashboard_apply_saved_settings()


DASHBOARD_BASE_TEMPLATE = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} • {{ brand }}</title>
  <style>
    :root{
      --bg:#070a12;--bg2:#0b1020;--panel:rgba(18,24,38,.78);--panel2:rgba(23,31,49,.82);
      --text:#f7fbff;--muted:#92a0b8;--line:rgba(148,163,184,.18);--blue:#5865f2;--purple:#8b5cf6;
      --green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--cyan:#06b6d4;--shadow:0 24px 80px rgba(0,0,0,.42)
    }
    *{box-sizing:border-box} html{scroll-behavior:smooth}
    body{margin:0;min-height:100vh;background:
      radial-gradient(circle at 15% -10%,rgba(88,101,242,.35),transparent 35%),
      radial-gradient(circle at 85% 0%,rgba(139,92,246,.22),transparent 30%),
      linear-gradient(180deg,#090e1b 0%,#070a12 100%);font-family:Inter,ui-sans-serif,system-ui,Arial,sans-serif;color:var(--text)}
    a{color:inherit;text-decoration:none} code{background:rgba(15,23,42,.9);border:1px solid var(--line);padding:3px 7px;border-radius:9px;color:#dbeafe}
    .layout{display:grid;grid-template-columns:278px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:20px;border-right:1px solid var(--line);background:rgba(7,10,18,.68);backdrop-filter:blur(18px)}
    .brand{display:flex;align-items:center;gap:12px;margin-bottom:24px}.logo{width:48px;height:48px;border-radius:18px;background:linear-gradient(135deg,var(--blue),var(--purple));display:grid;place-items:center;font-size:25px;box-shadow:0 18px 45px rgba(88,101,242,.25)}
    .brand h1{font-size:20px;margin:0;letter-spacing:.2px}.brand p{margin:4px 0 0;color:var(--muted);font-size:12px}.navlist{display:grid;gap:8px}.navitem{display:flex;align-items:center;gap:10px;padding:12px 13px;border:1px solid transparent;border-radius:15px;color:#c8d2e4;font-weight:800}.navitem:hover,.navitem.active{background:rgba(88,101,242,.14);border-color:rgba(88,101,242,.26);color:#fff}.navfoot{position:absolute;bottom:20px;left:20px;right:20px;color:var(--muted);font-size:12px}
    .main{padding:24px;max-width:1380px;width:100%;margin:0 auto}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;gap:14px}.headline h2{font-size:30px;margin:0}.headline p{color:var(--muted);margin:6px 0 0}.actions{display:flex;gap:10px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:rgba(23,31,49,.92);padding:10px 14px;border-radius:14px;color:var(--text);display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-weight:900;box-shadow:0 10px 30px rgba(0,0,0,.14)}.btn.primary{background:linear-gradient(135deg,var(--blue),var(--purple));border-color:transparent}.btn.green{background:linear-gradient(135deg,#15803d,#22c55e);border-color:transparent}.btn.red{background:linear-gradient(135deg,#991b1b,#ef4444);border-color:transparent}.btn:hover{transform:translateY(-1px);filter:brightness(1.08)}
    .grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:linear-gradient(180deg,var(--panel),rgba(13,19,33,.9));border:1px solid var(--line);border-radius:24px;padding:18px;box-shadow:var(--shadow);backdrop-filter:blur(16px)}.card h3{margin:0 0 13px;font-size:17px}.stat{position:relative;overflow:hidden}.stat:after{content:"";position:absolute;right:-18px;top:-18px;width:90px;height:90px;border-radius:999px;background:rgba(88,101,242,.16)}.stat .icon{font-size:23px}.stat .num{font-size:32px;font-weight:1000;margin-top:10px}.stat .label{color:var(--muted);font-size:13px;margin-top:4px}.muted{color:var(--muted)}.small{font-size:12px}.toast{padding:13px 15px;border-radius:16px;border:1px solid var(--line);margin-bottom:14px;font-weight:850}.toast.ok{background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.3)}.toast.bad{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.3)}
    .table{width:100%;border-collapse:separate;border-spacing:0 8px}.table th{color:var(--muted);font-size:11px;text-transform:uppercase;text-align:left;padding:0 10px}.table td{padding:12px 10px;background:rgba(15,23,42,.55);border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.table td:first-child{border-left:1px solid var(--line);border-radius:14px 0 0 14px}.table td:last-child{border-right:1px solid var(--line);border-radius:0 14px 14px 0}.pill{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:rgba(88,101,242,.15);color:#dbeafe;font-size:12px;font-weight:950;border:1px solid rgba(88,101,242,.2)}.pill.ok{background:rgba(34,197,94,.16);color:#dcfce7;border-color:rgba(34,197,94,.25)}.pill.bad{background:rgba(239,68,68,.16);color:#fee2e2;border-color:rgba(239,68,68,.25)}.pill.gold{background:rgba(245,158,11,.16);color:#fef3c7;border-color:rgba(245,158,11,.25)}
    .formgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.formbox{background:rgba(15,23,42,.62);border:1px solid var(--line);border-radius:20px;padding:15px}label{display:block;color:var(--muted);font-size:12px;margin:10px 0 6px;font-weight:800}input,select{width:100%;background:rgba(2,6,23,.78);color:var(--text);border:1px solid var(--line);border-radius:14px;padding:12px;outline:none}input:focus,select:focus{border-color:rgba(88,101,242,.75);box-shadow:0 0 0 3px rgba(88,101,242,.12)}.hero{display:grid;grid-template-columns:1.4fr .8fr;gap:14px;margin-bottom:14px}.hero .big{font-size:44px;font-weight:1000;letter-spacing:-1px}.danger{border-color:rgba(239,68,68,.38)}.footer{color:var(--muted);text-align:center;font-size:12px;margin-top:18px}
    @media(max-width:1000px){.layout{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.navfoot{position:static;margin-top:16px}.grid,.grid2,.grid3,.hero,.formgrid{grid-template-columns:1fr}.topbar{align-items:flex-start;flex-direction:column}.main{padding:16px}.headline h2{font-size:24px}}
  .switchgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.switchcard{padding:14px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:rgba(255,255,255,.04)}.toggleline{display:flex;align-items:center;justify-content:space-between;gap:10px}.switch{width:52px;height:28px;border-radius:999px;background:#3b4252;position:relative;display:inline-block}.switch input{display:none}.slider{position:absolute;cursor:pointer;inset:0;border-radius:999px}.slider:before{content:"";position:absolute;height:22px;width:22px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s}.switch input:checked+.slider{background:#22c55e}.switch input:checked+.slider:before{transform:translateX(24px)}.dangerzone{border-color:rgba(239,68,68,.55);background:rgba(239,68,68,.08)}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="brand"><div class="logo">⚙️</div><div><h1>{{ brand }}</h1><p>Discord OAuth Admin Dashboard</p></div></div>
    <nav class="navlist">
      <a class="navitem" href="/dashboard">🏠 Overview</a>
      <a class="navitem" href="/dashboard/economy">🪙 Economy</a>
      <a class="navitem" href="/dashboard/levels">📊 Levels</a>
      <a class="navitem" href="/dashboard/casino">🎰 Casino</a>
      <a class="navitem" href="/dashboard/user">👤 User Lookup</a>
      <a class="navitem" href="/dashboard/memory">💾 Memory</a>
      <a class="navitem" href="/dashboard/control">🛡️ Control Center</a>
      <a class="navitem" href="/dashboard/audit">🕵️ Audit Center</a>
      <a class="navitem" href="/dashboard/settings">⚙️ Settings</a>
      <a class="navitem" href="/oauth_debug">🧪 OAuth Debug</a>
    </nav>
    <div class="navfoot">{% if user %}<div class="pill">👤 {{ user.get('username') }}</div><div style="height:8px"></div><a class="btn" href="/logout">Logout</a>{% else %}<a class="btn primary" href="/login">Login with Discord</a>{% endif %}</div>
  </aside>
  <main class="main">
    <div class="topbar"><div class="headline"><h2>{{ title }}</h2><p>Fast control panel for economy, levels, memory and casino.</p></div><div class="actions"><a class="btn" href="/">Status</a>{% if user %}<a class="btn primary" href="/dashboard">Dashboard</a>{% else %}<a class="btn primary" href="/login">Login</a>{% endif %}</div></div>
    {{ body|safe }}
    <div class="footer">{{ brand }} • Protected by Discord OAuth</div>
  </main>
</div>
</body>
</html>
'''


def render_dashboard_page(title, body, status=200):
    return render_template_string(DASHBOARD_BASE_TEMPLATE, title=title, brand=BOT_BRAND, user=session.get("discord_user"), body=body), status


@app.route("/")
def home():
    body = '''
    <div class="hero">
      <div class="card"><div class="big">✅ System Online</div><p class="muted">البوت شغال والداشبورد جاهز للإدارة. سجل دخولك بـ Discord OAuth.</p><div style="height:12px"></div><a class="btn primary" href="/login">Login with Discord</a></div>
      <div class="card"><h3>🔐 Security</h3><p class="muted">Access is limited to server owner, Administrator permission, or configured admin roles.</p><span class="pill ok">OAuth Protected</span></div>
    </div>
    '''
    return render_dashboard_page("Online", body)


@app.route("/login")
def dashboard_login():
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET or not DASHBOARD_BASE_URL:
        body = '<div class="card danger"><h3>⚠️ Dashboard Variables Missing</h3><p>تأكد أنك حاط المتغيرات في Railway:</p><p><code>DISCORD_CLIENT_ID</code>, <code>DISCORD_CLIENT_SECRET</code>, <code>DASHBOARD_SECRET_KEY</code>, <code>DASHBOARD_BASE_URL</code></p></div>'
        return render_dashboard_page("Setup Required", body, status=500)
    return redirect(dashboard_auth_url())


@app.route("/callback")
def dashboard_callback():
    code = request.args.get("code")
    if not code:
        return render_dashboard_page("OAuth Error", "<div class='card danger'><h3>OAuth Error</h3><p>Discord ما رجع code.</p></div>", status=400)
    try:
        token_data = oauth_post_token(code)
        user = oauth_get_user(token_data["access_token"])
        session["discord_user"] = {"id": user.get("id"), "username": user.get("username"), "global_name": user.get("global_name"), "avatar": user.get("avatar")}
    except Exception as e:
        return render_dashboard_page("OAuth Error", f"<div class='card danger'><h3>OAuth Failed</h3><p>{clean_text(str(e), 600)}</p></div>", status=500)
    return redirect("/dashboard")


@app.route("/logout")
def dashboard_logout():
    session.clear()
    return redirect("/")


@app.route("/oauth_debug")
def dashboard_oauth_debug():
    body = f'''
    <div class='card'>
      <h3>OAuth Debug</h3>
      <p><b>Client ID:</b> <code>{clean_text(DISCORD_CLIENT_ID or 'MISSING', 200)}</code></p>
      <p><b>Client Secret:</b> <span class='pill {'ok' if DISCORD_CLIENT_SECRET else 'bad'}'>{'SET' if DISCORD_CLIENT_SECRET else 'MISSING'}</span></p>
      <p><b>Base URL:</b> <code>{clean_text(DASHBOARD_BASE_URL or 'MISSING', 300)}</code></p>
      <p><b>Redirect URI used by code:</b> <code>{clean_text(dashboard_redirect_uri() or 'MISSING', 300)}</code></p>
      <p><b>Scope:</b> <code>identify guilds</code></p>
      <a class='btn primary' href='/login'>Test Login</a>
    </div>
    '''
    return render_dashboard_page("OAuth Debug", body)


@app.route("/dashboard")
def dashboard_home():
    denied = dashboard_require_admin()
    if denied:
        return denied
    init_db()
    level_users = dashboard_count_table("levels")
    economy_users = dashboard_count_table("economy")
    total_coins = dashboard_total_coins()
    total_warnings = safe_len_json(WARNINGS_FILE)
    log_rooms = safe_len_json(LOG_CHANNELS_FILE)
    top_money = dashboard_money_rows(8)
    top_levels = dashboard_level_rows(8)
    memory = dashboard_memory_summary()
    money_rows = "".join([f"<tr><td><span class='pill gold'>#{r['rank']}</span></td><td>{r['name']}<br><span class='muted small'>{r['user_id']}</span></td><td>{fmt_coin(r['balance'])}</td></tr>" for r in top_money]) or "<tr><td colspan='3'>No data</td></tr>"
    level_rows = "".join([f"<tr><td><span class='pill gold'>#{r['rank']}</span></td><td>{r['name']}<br><span class='muted small'>{r['user_id']}</span></td><td>Lv.{r['level']} • XP {fmt_num(r['xp'])}</td></tr>" for r in top_levels]) or "<tr><td colspan='3'>No data</td></tr>"
    memory_ok = sum(1 for m in memory if m['badge'] == 'OK')
    body = f'''
    {dashboard_toast_html()}
    <div class="hero"><div class="card"><div class="big">Retards System</div><p class="muted">Control economy, levels, memory backups, casino and server utilities from one protected dashboard.</p><div style="height:12px"></div><a class="btn primary" href="/dashboard/economy">Manage Economy</a> <a class="btn" href="/dashboard/settings">Bot Settings</a></div><div class="card"><h3>⚡ Quick Status</h3><p><span class="pill ok">Bot Online</span></p><p class="muted">Memory files healthy: <b>{memory_ok}/{len(memory)}</b></p><p class="muted">Guide interval: <b>{round(ECONOMY_EXPLAIN_INTERVAL_SECONDS/3600, 2)}h</b></p></div></div>
    <div class="grid">
      <div class="card stat"><div class="icon">🪙</div><div class="num">{fmt_num(economy_users)}</div><div class="label">Economy users</div></div>
      <div class="card stat"><div class="icon">💰</div><div class="num">{fmt_num(total_coins)}</div><div class="label">Total {COIN_NAME}</div></div>
      <div class="card stat"><div class="icon">📊</div><div class="num">{fmt_num(level_users)}</div><div class="label">Level users</div></div>
      <div class="card stat"><div class="icon">⚠️</div><div class="num">{fmt_num(total_warnings)}</div><div class="label">Warning users • Logs {fmt_num(log_rooms)}</div></div>
    </div>
    <div style="height:14px"></div>
    <div class="grid2"><div class="card"><h3>🪙 Richest Members</h3><table class="table"><tr><th>Rank</th><th>User</th><th>Balance</th></tr>{money_rows}</table></div><div class="card"><h3>🏆 Highest Levels</h3><table class="table"><tr><th>Rank</th><th>User</th><th>Level</th></tr>{level_rows}</table></div></div>
    <div style="height:14px"></div>
    <div class="grid3">
      <div class="card"><h3>🎰 Casino</h3><p class="muted">Gambling channel:</p><p><code>{GAMBLING_CHANNEL_ID}</code></p><p><span class="pill">Cooldown {GAMBLE_COOLDOWN_SECONDS}s</span></p><a class="btn" href="/dashboard/casino">Open Casino Page</a></div>
      <div class="card"><h3>💾 Memory</h3><p class="muted">Backup channel:</p><p><code>{MEMORY_BACKUP_CHANNEL_ID}</code></p><form method="post" action="/dashboard/backup"><button class="btn primary" type="submit">Create Backup</button></form></div>
      <div class="card"><h3>🛡️ Control Center</h3><p class="muted">اقفل/افتح الأوامر والأنظمة، وشغل وضع الطوارئ.</p><a class="btn red" href="/dashboard/control">Open Control Center</a> <a class="btn" href="/dashboard/audit">Audit Logs</a></div>
      <div class="card"><h3>👤 User Lookup</h3><form method="get" action="/dashboard/user"><label>User ID</label><input name="user_id" placeholder="Discord user ID"><div style="height:10px"></div><button class="btn green">Search</button></form></div>
    </div>
    '''
    return render_dashboard_page("Overview", body)


@app.route("/dashboard/economy", methods=["GET"])
def dashboard_economy_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    rows = dashboard_latest_economy_rows(25)
    table = "".join([f"<tr><td>{r['name']}<br><span class='muted small'>{r['user_id']}</span></td><td>{fmt_coin(r['balance'])}</td><td>{('<t:'+str(r['last_daily'])+':R>') if r['last_daily'] else 'Never'}</td></tr>" for r in rows]) or "<tr><td colspan='3'>No data</td></tr>"
    body = f'''
    {dashboard_toast_html()}
    <div class="grid3">
      <form class="card" method="post" action="/dashboard/economy"><h3>➕ Add Money</h3><label>User ID</label><input name="user_id" required><label>Amount</label><input name="amount" placeholder="5000" required><input type="hidden" name="action" value="add"><div style="height:10px"></div><button class="btn green">Add</button></form>
      <form class="card" method="post" action="/dashboard/economy"><h3>➖ Remove Money</h3><label>User ID</label><input name="user_id" required><label>Amount</label><input name="amount" placeholder="5000" required><input type="hidden" name="action" value="remove"><div style="height:10px"></div><button class="btn red">Remove</button></form>
      <form class="card" method="post" action="/dashboard/economy"><h3>🎯 Set Balance</h3><label>User ID</label><input name="user_id" required><label>New Balance</label><input name="amount" placeholder="100000" required><input type="hidden" name="action" value="set"><div style="height:10px"></div><button class="btn primary">Set</button></form>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>🪙 Economy Leaderboard</h3><table class="table"><tr><th>User</th><th>Balance</th><th>Last Hourly</th></tr>{table}</table></div>
    '''
    return render_dashboard_page("Economy", body)


@app.route("/dashboard/levels", methods=["GET"])
def dashboard_levels_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    rows = dashboard_latest_level_rows(25)
    table = "".join([f"<tr><td>{r['name']}<br><span class='muted small'>{r['user_id']}</span></td><td>Level {r['level']}</td><td>{fmt_num(r['xp'])} XP</td></tr>" for r in rows]) or "<tr><td colspan='3'>No data</td></tr>"
    body = f'''
    {dashboard_toast_html()}
    <div class="grid3">
      <form class="card" method="post" action="/dashboard/levels"><h3>✨ Add XP</h3><label>User ID</label><input name="user_id" required><label>XP Amount</label><input name="amount" placeholder="100" required><input type="hidden" name="action" value="add_xp"><div style="height:10px"></div><button class="btn green">Add XP</button></form>
      <form class="card" method="post" action="/dashboard/levels"><h3>🏆 Set Level</h3><label>User ID</label><input name="user_id" required><label>Level</label><input name="amount" placeholder="10" required><input type="hidden" name="action" value="set_level"><div style="height:10px"></div><button class="btn primary">Set Level</button></form>
      <form class="card" method="post" action="/dashboard/levels"><h3>📊 Set XP</h3><label>User ID</label><input name="user_id" required><label>XP</label><input name="amount" placeholder="250" required><input type="hidden" name="action" value="set_xp"><div style="height:10px"></div><button class="btn primary">Set XP</button></form>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>📊 Level Leaderboard</h3><table class="table"><tr><th>User</th><th>Level</th><th>XP</th></tr>{table}</table></div>
    '''
    return render_dashboard_page("Levels", body)


@app.route("/dashboard/casino", methods=["GET"])
def dashboard_casino_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    body = f'''
    <div class="grid">
      <div class="card stat"><div class="icon">🎰</div><div class="num">∞</div><div class="label">No max bet</div></div>
      <div class="card stat"><div class="icon">⏱️</div><div class="num">{GAMBLE_COOLDOWN_SECONDS}s</div><div class="label">Cooldown</div></div>
      <div class="card stat"><div class="icon">📍</div><div class="num">Room</div><div class="label"><code>{GAMBLING_CHANNEL_ID}</code></div></div>
      <div class="card stat"><div class="icon">🎴</div><div class="num">BJ</div><div class="label">Blackjack enabled</div></div>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>🎲 Casino Games</h3><table class="table"><tr><th>Command</th><th>Game</th><th>Rules</th></tr><tr><td><code>!حظ amount</code></td><td>Lucky Roll</td><td>50/50 double or lose</td></tr><tr><td><code>!دبل amount</code></td><td>Double Risk</td><td>45% win, 55% lose</td></tr><tr><td><code>!سلوت amount</code></td><td>Slot Machine</td><td>2 match = x2, 3 match = x5</td></tr><tr><td><code>!وجه amount ملك/كتابة</code></td><td>Coin Flip</td><td>Guess the side</td></tr><tr><td><code>!بلاكجاك amount</code></td><td>Blackjack</td><td>Hit / Stand buttons</td></tr></table></div>
    <div style="height:14px"></div>
    <div class="card"><h3>🚧 Next Upgrade</h3><p class="muted">نقدر نضيف Casino History Table يخزن كل قمار: اللاعب، اللعبة، الرهان، الربح/الخسارة، الوقت. بعدها الصفحة هذي تعرض أكبر فوز وأكبر خسارة وأقوى مقامرين.</p></div>
    '''
    return render_dashboard_page("Casino", body)


@app.route("/dashboard/user", methods=["GET"])
def dashboard_user_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    user_id = request.args.get("user_id", "").strip()
    profile_html = ""
    if user_id:
        try:
            profile = dashboard_user_profile(int(user_id))
            warns = profile['warnings']
            warn_rows = "".join([f"<tr><td>{clean_text(w.get('time',''),80)}</td><td>{clean_text(w.get('reason',''),120)}</td><td>{clean_text(w.get('message',''),160)}</td></tr>" for w in warns[-10:]]) or "<tr><td colspan='3'>No warnings</td></tr>"
            roles = ", ".join(profile['roles'][:18]) if profile['roles'] else "No roles / not cached"
            profile_html = f'''
            <div style="height:14px"></div><div class="grid2"><div class="card"><h3>👤 {profile['name']}</h3><p><span class="pill">ID</span> <code>{profile['user_id']}</code></p><p><b>Balance:</b> {fmt_coin(profile['balance'])}</p><p><b>Level:</b> {profile['level']} • <b>XP:</b> {fmt_num(profile['xp'])}</p><p><b>Warnings:</b> {len(warns)}</p><p class="muted small">Roles: {clean_text(roles, 500)}</p></div><div class="card"><h3>⚡ Quick Edit</h3><form method="post" action="/dashboard/economy"><input type="hidden" name="user_id" value="{profile['user_id']}"><label>Money Amount</label><input name="amount" value="1000"><label>Action</label><select name="action"><option value="add">Add</option><option value="remove">Remove</option><option value="set">Set</option></select><div style="height:10px"></div><button class="btn green">Apply Money</button></form></div></div>
            <div style="height:14px"></div><div class="card"><h3>⚠️ Last Warnings</h3><table class="table"><tr><th>Time</th><th>Reason</th><th>Message</th></tr>{warn_rows}</table></div>
            '''
        except Exception as e:
            profile_html = f"<div class='toast bad'>User lookup failed: {clean_text(str(e), 250)}</div>"
    body = f'''
    {dashboard_toast_html()}
    <div class="card"><h3>👤 User Lookup</h3><form method="get" action="/dashboard/user"><label>Discord User ID</label><input name="user_id" value="{clean_text(user_id, 80)}" placeholder="1125198908231004191"><div style="height:10px"></div><button class="btn primary">Search User</button></form></div>
    {profile_html}
    '''
    return render_dashboard_page("User Lookup", body)


@app.route("/dashboard/memory", methods=["GET"])
def dashboard_memory_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    memory = dashboard_memory_summary()
    rows = "".join([f"<tr><td>{m['file']}</td><td><span class='pill {'ok' if m['badge']=='OK' else 'bad'}'>{m['badge']}</span></td><td>{m['size']} KB</td></tr>" for m in memory])
    body = f'''
    {dashboard_toast_html()}
    <div class="grid2"><div class="card"><h3>💾 Memory Files</h3><table class="table"><tr><th>File</th><th>Status</th><th>Size</th></tr>{rows}</table></div><div class="card"><h3>Manual Backup</h3><p class="muted">يرسل ملفات الذاكرة + التقرير في روم الباك أب.</p><p><code>{MEMORY_BACKUP_CHANNEL_ID}</code></p><form method="post" action="/dashboard/backup"><button class="btn primary">💾 Create Backup Now</button></form></div></div>
    '''
    return render_dashboard_page("Memory", body)



@app.route("/dashboard/control", methods=["GET"])
def dashboard_control_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    control = dashboard_control_settings()
    systems = control["system_toggles"]
    commands = control["command_toggles"]
    system_labels = {
        "utility": "Utility Commands", "admin": "Admin Commands", "economy": "Economy System", "levels": "Level System",
        "gambling": "Casino / Gambling", "protection": "Protection System", "lfg": "Looking For Game",
        "giveaway": "Giveaways", "community": "Community", "roles": "Role Buttons", "memory": "Memory Backup"
    }
    system_cards = "".join([
        f"""<div class="switchcard"><div class="toggleline"><div><b>{label}</b><p class="muted small">System key: <code>{key}</code></p></div><label class="switch"><input type="checkbox" name="system::{key}" {'checked' if systems.get(key, True) else ''}><span class="slider"></span></label></div></div>"""
        for key, label in system_labels.items()
    ])
    command_cards = "".join([
        f"""<div class="switchcard"><div class="toggleline"><div><b>!{cmd}</b><p class="muted small">{COMMAND_SYSTEM_MAP.get(cmd, 'utility')}</p></div><label class="switch"><input type="checkbox" name="command::{cmd}" {'checked' if commands.get(cmd, True) else ''}><span class="slider"></span></label></div></div>"""
        for cmd in sorted(COMMAND_SYSTEM_MAP.keys())
    ])
    emergency_class = "dangerzone" if control.get("emergency_lockdown") else ""
    emergency_enabled_value = "0" if control.get("emergency_lockdown") else "1"
    emergency_button_class = "green" if control.get("emergency_lockdown") else "red"
    emergency_button_text = "Disable Emergency" if control.get("emergency_lockdown") else "Enable Emergency Lockdown"
    body = f"""
    {dashboard_toast_html()}
    <div class="hero"><div class="card"><div class="big">🛡️ Admin Control Center</div><p class="muted">اقفل وافتح أي أمر أو نظام كامل بدون تعديل الكود. التغييرات فورية وتحفظ بعد الريستارت.</p></div><div class="card {emergency_class}"><h3>🚨 Emergency Mode</h3><p class="muted">يقفل الاقتصاد والقمار واللفل والتحويلات وأغلب أوامر الأعضاء، ويترك الأدوات الإدارية الأساسية.</p><form method="post" action="/dashboard/control/emergency"><input type="hidden" name="enabled" value="{emergency_enabled_value}"><button class="btn {emergency_button_class}">{emergency_button_text}</button></form></div></div>
    <form method="post" action="/dashboard/control/save">
      <div class="card"><h3>🧩 System Toggles</h3><div class="switchgrid">{system_cards}</div></div>
      <div class="card"><h3>⌨️ Command Toggles</h3><p class="muted">إذا قفلت أمر هنا، البوت بيرفضه مباشرة ويقول إنه مقفل من الإدارة.</p><div class="switchgrid">{command_cards}</div></div>
      <div class="card"><h3>🚨 Policy Engine v1</h3><p class="muted">تنبيهات إدارية للأرقام الكبيرة والتصرفات الحساسة.</p><div class="formgrid"><div><label>Large Transfer Alert</label><input name="policy_large_transfer_alert" value="{control['policies']['large_transfer_alert']}"></div><div><label>Large Admin Money Alert</label><input name="policy_large_admin_money_alert" value="{control['policies']['large_admin_money_alert']}"></div><div><label>Large Gamble Alert</label><input name="policy_large_gamble_alert" value="{control['policies']['large_gamble_alert']}"></div><div><label>Dashboard Audit Channel ID</label><input name="dashboard_audit_channel_id" value="{control.get('dashboard_audit_channel_id', 0)}"></div></div></div>
      <div style="height:14px"></div><button class="btn primary" type="submit">Save Control Settings</button>
    </form>
    """
    return render_dashboard_page("Control Center", body)


@app.route("/dashboard/control/save", methods=["POST"])
def dashboard_control_save():
    denied = dashboard_require_admin()
    if denied:
        return denied
    try:
        systems = {key: (request.form.get(f"system::{key}") == "on") for key in DEFAULT_SYSTEM_TOGGLES}
        commands = {key: (request.form.get(f"command::{key}") == "on") for key in COMMAND_SYSTEM_MAP}
        data = dashboard_load_settings_file()
        data["system_toggles"] = systems
        data["command_toggles"] = commands
        data["large_transfer_alert"] = parse_int_field(request.form.get("policy_large_transfer_alert", "100000"), 100000, 0)
        data["large_admin_money_alert"] = parse_int_field(request.form.get("policy_large_admin_money_alert", "250000"), 250000, 0)
        data["large_gamble_alert"] = parse_int_field(request.form.get("policy_large_gamble_alert", "250000"), 250000, 0)
        data["dashboard_audit_channel_id"] = parse_int_field(request.form.get("dashboard_audit_channel_id", "0"), 0, 0)
        dashboard_save_settings_file(data)
        dashboard_log_action("Updated control settings", "Changed command/system toggles and policy thresholds", session.get("discord_user"))
        msg = "Control settings saved."
    except Exception as e:
        return redirect("/dashboard/control?err=" + urllib.parse.quote(str(e)))
    return redirect("/dashboard/control?msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/control/emergency", methods=["POST"])
def dashboard_control_emergency():
    denied = dashboard_require_admin()
    if denied:
        return denied
    enabled = request.form.get("enabled") == "1"
    data = dashboard_load_settings_file()
    data["emergency_lockdown"] = enabled
    dashboard_save_settings_file(data)
    dashboard_log_action("Emergency Lockdown " + ("ENABLED" if enabled else "DISABLED"), "Emergency Mode changed from dashboard", session.get("discord_user"))
    return redirect("/dashboard/control?msg=" + urllib.parse.quote("Emergency mode updated."))


@app.route("/dashboard/audit", methods=["GET"])
def dashboard_audit_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    rows = dashboard_audit_rows(DASHBOARD_AUDIT_LOG_LIMIT)
    table = "".join([
        f"<tr><td><code>{created}</code></td><td>{clean_text(name, 80)}<br><span class='muted small'>{admin_id}</span></td><td>{clean_text(action, 140)}</td><td>{clean_text(details, 400)}</td></tr>"
        for admin_id, name, action, details, created in rows
    ]) or "<tr><td colspan='4'>No dashboard actions yet.</td></tr>"
    body = f"""
    {dashboard_toast_html()}
    <div class="card"><h3>🕵️ Audit Center</h3><p class="muted">كل تعديل من الداشبورد ينحفظ هنا وينرسل في روم اللوقات إذا مضبوط.</p><table class="table"><tr><th>Unix Time</th><th>Admin</th><th>Action</th><th>Details</th></tr>{table}</table></div>
    """
    return render_dashboard_page("Audit Center", body)


@app.route("/dashboard/settings", methods=["GET"])
def dashboard_settings_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    body = f'''
    {dashboard_toast_html()}
    <div class="card"><h3>⚙️ Runtime Settings</h3><p class="muted">التغييرات هنا تنحفظ في <code>{DASHBOARD_SETTINGS_FILE}</code> وتشتغل بعد الريستارت إذا الملف موجود.</p><form method="post" action="/dashboard/settings" class="formgrid"><div><label>Coin Name</label><input name="COIN_NAME" value="{clean_text(COIN_NAME, 40)}"></div><div><label>Commands Channel ID</label><input name="COMMANDS_CHANNEL_ID" value="{COMMANDS_CHANNEL_ID}"></div><div><label>Gambling Channel ID</label><input name="GAMBLING_CHANNEL_ID" value="{GAMBLING_CHANNEL_ID}"></div><div><label>Memory Backup Channel ID</label><input name="MEMORY_BACKUP_CHANNEL_ID" value="{MEMORY_BACKUP_CHANNEL_ID}"></div><div><label>Gamble Cooldown Seconds</label><input name="GAMBLE_COOLDOWN_SECONDS" value="{GAMBLE_COOLDOWN_SECONDS}"></div><div><label>Economy Guide Interval Hours</label><input name="ECONOMY_GUIDE_HOURS" value="{round(ECONOMY_EXPLAIN_INTERVAL_SECONDS/3600, 2)}"></div><div><label>Booster Weekly Reward</label><input name="BOOSTER_WEEKLY_REWARD" value="{BOOSTER_WEEKLY_REWARD}"></div><div style="display:flex;align-items:end"><button class="btn primary" type="submit">Save Settings</button></div></form></div>
    '''
    return render_dashboard_page("Settings", body)


@app.route("/dashboard/settings", methods=["POST"])
def dashboard_settings_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    global COMMANDS_CHANNEL_ID, GAMBLING_CHANNEL_ID, MEMORY_BACKUP_CHANNEL_ID
    global GAMBLE_COOLDOWN_SECONDS, ECONOMY_EXPLAIN_INTERVAL_SECONDS, BOOSTER_WEEKLY_REWARD, COIN_NAME
    try:
        COIN_NAME = str(request.form.get("COIN_NAME", COIN_NAME)).strip()[:40] or COIN_NAME
        COMMANDS_CHANNEL_ID = parse_int_field(request.form.get("COMMANDS_CHANNEL_ID"), COMMANDS_CHANNEL_ID, 1)
        GAMBLING_CHANNEL_ID = parse_int_field(request.form.get("GAMBLING_CHANNEL_ID"), GAMBLING_CHANNEL_ID, 1)
        MEMORY_BACKUP_CHANNEL_ID = parse_int_field(request.form.get("MEMORY_BACKUP_CHANNEL_ID"), MEMORY_BACKUP_CHANNEL_ID, 1)
        GAMBLE_COOLDOWN_SECONDS = parse_int_field(request.form.get("GAMBLE_COOLDOWN_SECONDS"), GAMBLE_COOLDOWN_SECONDS, 0)
        hours_raw = str(request.form.get("ECONOMY_GUIDE_HOURS", "7")).strip()
        try:
            ECONOMY_EXPLAIN_INTERVAL_SECONDS = max(60, int(float(hours_raw) * 3600))
        except:
            pass
        BOOSTER_WEEKLY_REWARD = parse_int_field(request.form.get("BOOSTER_WEEKLY_REWARD"), BOOSTER_WEEKLY_REWARD, 0)
        dashboard_save_settings_file({
            "COIN_NAME": COIN_NAME,
            "COMMANDS_CHANNEL_ID": COMMANDS_CHANNEL_ID,
            "GAMBLING_CHANNEL_ID": GAMBLING_CHANNEL_ID,
            "MEMORY_BACKUP_CHANNEL_ID": MEMORY_BACKUP_CHANNEL_ID,
            "GAMBLE_COOLDOWN_SECONDS": GAMBLE_COOLDOWN_SECONDS,
            "ECONOMY_EXPLAIN_INTERVAL_SECONDS": ECONOMY_EXPLAIN_INTERVAL_SECONDS,
            "BOOSTER_WEEKLY_REWARD": BOOSTER_WEEKLY_REWARD,
        })
        msg = "Settings saved. Some loop intervals may fully apply after restart."
        dashboard_log_action("Settings updated", "Runtime settings were changed from dashboard", session.get("discord_user"))
    except Exception as e:
        return redirect("/dashboard/settings?err=" + urllib.parse.quote(str(e)))
    return redirect("/dashboard/settings?msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/economy", methods=["POST"])
def dashboard_economy_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    try:
        user_id = parse_int_field(request.form.get("user_id", "0"), 0, 1)
        amount = parse_int_field(request.form.get("amount", "0"), 0, 0)
        action = request.form.get("action", "add")
        if action == "add":
            balance = add_money(user_id, amount)
            msg = f"Added {fmt_num(amount)} {COIN_NAME} to {user_id}. New balance: {fmt_num(balance)}"
            dashboard_log_action("Economy: add money", f"Added {fmt_num(amount)} {COIN_NAME} to {user_id}. New balance {fmt_num(balance)}", session.get("discord_user"))
        elif action == "remove":
            ok, balance = remove_money(user_id, amount)
            msg = f"Removed {fmt_num(amount)} {COIN_NAME} from {user_id}. New balance: {fmt_num(balance)}" if ok else f"User {user_id} does not have enough balance. Current: {fmt_num(balance)}"
            dashboard_log_action("Economy: remove money", f"Attempted remove {fmt_num(amount)} {COIN_NAME} from {user_id}. OK={ok}. Balance {fmt_num(balance)}", session.get("discord_user"))
        elif action == "set":
            balance = set_balance(user_id, amount)
            msg = f"Set {user_id} balance to {fmt_num(balance)} {COIN_NAME}"
            dashboard_log_action("Economy: set balance", f"Set {user_id} balance to {fmt_num(balance)} {COIN_NAME}", session.get("discord_user"))
        else:
            msg = "Unknown action."
    except Exception as e:
        msg = f"Economy action failed: {e}"
    back = request.referrer or "/dashboard/economy"
    sep = "&" if "?" in back else "?"
    return redirect(back + sep + "msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/levels", methods=["POST"])
def dashboard_levels_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    try:
        user_id = parse_int_field(request.form.get("user_id", "0"), 0, 1)
        amount = parse_int_field(request.form.get("amount", "0"), 0, 0)
        action = request.form.get("action", "add_xp")
        if action == "add_xp":
            xp, level, leveled = add_xp(user_id, amount)
            msg = f"Added {fmt_num(amount)} XP to {user_id}. Level: {level}, XP: {fmt_num(xp)}"
            dashboard_log_action("Levels: add XP", f"Added {fmt_num(amount)} XP to {user_id}. Level {level}, XP {fmt_num(xp)}", session.get("discord_user"))
        elif action == "set_level":
            xp, level = dashboard_set_level_data(user_id, level=amount)
            msg = f"Set {user_id} level to {level}. XP: {fmt_num(xp)}"
            dashboard_log_action("Levels: set level", f"Set {user_id} level to {level}. XP {fmt_num(xp)}", session.get("discord_user"))
        elif action == "set_xp":
            xp, level = dashboard_set_level_data(user_id, xp=amount)
            msg = f"Set {user_id} XP to {fmt_num(xp)}. Level: {level}"
            dashboard_log_action("Levels: set XP", f"Set {user_id} XP to {fmt_num(xp)}. Level {level}", session.get("discord_user"))
        else:
            msg = "Unknown action."
    except Exception as e:
        msg = f"Level action failed: {e}"
    back = request.referrer or "/dashboard/levels"
    sep = "&" if "?" in back else "?"
    return redirect(back + sep + "msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/backup", methods=["POST"])
def dashboard_backup_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            msg = "Guild not ready. Try again after bot is online."
        else:
            future = asyncio.run_coroutine_threadsafe(create_memory_backup(guild, reason="Dashboard manual backup", requested_by=None), bot.loop)
            ok, result = future.result(timeout=30)
            msg = result
            dashboard_log_action("Memory: manual backup", clean_text(str(result), 500), session.get("discord_user"))
    except Exception as e:
        msg = f"Backup failed: {e}"
    back = request.referrer or "/dashboard/memory"
    sep = "&" if "?" in back else "?"
    return redirect(back + sep + "msg=" + urllib.parse.quote(msg))


def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run).start()


async def booster_weekly_loop():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            guild = bot.get_guild(GUILD_ID)

            if guild:
                role = guild.get_role(SERVER_BOOSTER_ROLE_ID)
                channel = guild.get_channel(COMMANDS_CHANNEL_ID)

                if role:
                    for member in list(role.members):
                        if member.bot:
                            continue

                        success, remaining, balance_amount, reward = claim_booster_weekly(member.id)

                        if success and channel:
                            embed = discord.Embed(
                                title="🚀 Booster Weekly Auto Reward",
                                description=f"{member.mention} استلم مكافأة البوست الأسبوعية تلقائيًا.",
                                color=COLOR_PURPLE,
                                timestamp=discord.utils.utcnow()
                            )
                            embed.add_field(name="🎁 Reward", value=money_delta(reward), inline=True)
                            embed.add_field(name="💼 New Balance", value=coin_line(balance_amount), inline=True)
                            embed.set_footer(text=f"{BOT_BRAND} • Auto Booster Weekly")
                            await channel.send(embed=embed)

        except Exception as e:
            print(f"Booster weekly auto reward error: {e}")

        await asyncio.sleep(BOOSTER_WEEKLY_CHECK_INTERVAL_SECONDS)


# =========================
# BOT EVENTS
# =========================

@bot.check
async def only_one_guild(ctx):
    return ctx.guild and ctx.guild.id == GUILD_ID


@bot.check
async def admin_control_command_guard(ctx):
    if not ctx.command:
        return True
    name = ctx.command.name
    system_name = command_system(name)
    if not is_command_enabled(name):
        embed = discord.Embed(title="🔒 الأمر مقفل", description="هذا الأمر مقفل مؤقتًا من الإدارة عبر الداشبورد.", color=COLOR_RED)
        embed.add_field(name="Command", value=f"`!{name}`", inline=True)
        embed.add_field(name="System", value=f"`{system_name}`", inline=True)
        await ctx.send(embed=embed, delete_after=8)
        return False
    if not is_system_enabled(system_name):
        control = dashboard_control_settings()
        title = "🚨 Emergency Lockdown" if control.get("emergency_lockdown") else "🔒 النظام مقفل"
        desc = "السيرفر حاليًا في وضع الطوارئ، الأوامر غير الضرورية مقفلة مؤقتًا." if control.get("emergency_lockdown") else "النظام هذا مقفل مؤقتًا من الإدارة."
        embed = discord.Embed(title=title, description=desc, color=COLOR_RED)
        embed.add_field(name="Command", value=f"`!{name}`", inline=True)
        embed.add_field(name="System", value=f"`{system_name}`", inline=True)
        await ctx.send(embed=embed, delete_after=8)
        return False
    return True


@bot.event
async def on_guild_join(guild):
    if guild.id != GUILD_ID:
        await guild.leave()


@bot.event
async def on_ready():
    global memory_backup_task, economy_explain_task, booster_weekly_task

    guild = bot.get_guild(GUILD_ID)

    if guild:
        restored, restore_message = await restore_memory_from_backup(guild, force=False)
        if restored:
            print(f"Memory restored on startup: {restore_message}")

    init_db()

    bot.add_view(GameRolesView())

    if memory_backup_task is None or memory_backup_task.done():
        memory_backup_task = asyncio.create_task(memory_backup_loop())

    if economy_explain_task is None or economy_explain_task.done():
        economy_explain_task = asyncio.create_task(economy_explain_loop())

    if booster_weekly_task is None or booster_weekly_task.done():
        booster_weekly_task = asyncio.create_task(booster_weekly_loop())

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Retard coin Economy | !مساعدة"
        )
    )

    print(f"NM System Ready: {bot.user}")


@bot.event
async def on_message(message):
    global protection_enabled

    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        # Outbound DM forwarding is disabled to avoid Discord anti-spam quarantine.
        # The bot will not reply in DMs or forward DMs privately.
        return

    if not message.guild or message.guild.id != GUILD_ID:
        return

    content = message.content.lower()

    now = time.time()
    last_xp = xp_cooldowns.get(message.author.id, 0)

    if is_system_enabled("levels") and now - last_xp >= LEVEL_COOLDOWN and not message.content.startswith(PREFIX):
        xp_cooldowns[message.author.id] = now
        gained = random.randint(8, 16)
        xp, level, leveled_up = add_xp(message.author.id, gained)

        last_coin = coin_cooldowns.get(message.author.id, 0)
        if is_system_enabled("economy") and now - last_coin >= MESSAGE_COIN_COOLDOWN:
            coin_cooldowns[message.author.id] = now
            add_money(message.author.id, random.randint(3, 8))

        if leveled_up:
            bonus = level * LEVEL_UP_COIN_BONUS
            new_balance = add_money(message.author.id, bonus)
            await message.channel.send(
                f"📊 {message.author.mention} وصل لفل **{level}**! 🎉\n"
                f"💰 مكافأة اللفل: **{bonus:,} {COIN_NAME}** | رصيدك: **{new_balance:,}**",
                delete_after=10
            )

    if protection_enabled and is_system_enabled("protection") and not is_bypass(message.author):

        if contains_bad_word(content):
            await handle_violation(message, "كلمة ممنوعة / سب")
            return

        if ANTI_LINKS:
            link_words = ["discord.gg", "discord.com/invite", "http://", "https://"]

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
        msg_now = time.time()

        if user_id not in user_message_times:
            user_message_times[user_id] = []

        user_message_times[user_id].append(msg_now)
        user_message_times[user_id] = [
            t for t in user_message_times[user_id]
            if msg_now - t <= SPAM_SECONDS
        ]

        if len(user_message_times[user_id]) >= SPAM_LIMIT:
            user_message_times[user_id] = []
            await handle_violation(
                message,
                f"سبام: {SPAM_LIMIT} رسائل خلال {SPAM_SECONDS} ثواني"
            )
            return

    await bot.process_commands(message)


# =========================
# AUDIT LOGS
# =========================

@bot.event
async def on_message_delete(message):
    if not message.guild or message.guild.id != GUILD_ID or message.author.bot:
        return

    await send_log(
        message.guild,
        "🗑️ رسالة محذوفة",
        f"""
**العضو:** {message.author.mention}
**ID:** `{message.author.id}`
**الروم:** {message.channel.mention}

**المحتوى:**
```{clean_text(message.content, 900)}```
""",
        COLOR_RED,
        log_type="message"
    )


@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.guild.id != GUILD_ID or before.author.bot:
        return

    if before.content == after.content:
        return

    await send_log(
        before.guild,
        "✏️ رسالة معدلة",
        f"""
**العضو:** {before.author.mention}
**ID:** `{before.author.id}`
**الروم:** {before.channel.mention}

**قبل:**
```{clean_text(before.content, 700)}```

**بعد:**
```{clean_text(after.content, 700)}```
""",
        COLOR_YELLOW,
        log_type="message"
    )


@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return

    created = int(member.created_at.timestamp())

    await send_log(
        member.guild,
        "📥 عضو دخل",
        f"""
**العضو:** {member.mention}
**User:** `{member}`
**ID:** `{member.id}`
**الحساب انشأ:** <t:{created}:F> | <t:{created}:R>
""",
        COLOR_GREEN,
        log_type="member"
    )


@bot.event
async def on_member_remove(member):
    if member.guild.id != GUILD_ID:
        return

    guild = member.guild

    action_type = "📤 خرج من نفسه"
    action_details = "العضو طلع من السيرفر بنفسه."
    executor_text = "لا يوجد"
    reason_text = "لا يوجد"
    color = COLOR_GREY

    now = discord.utils.utcnow()
    max_audit_age_seconds = 15

    try:
        ban_entry = await get_audit_executor(guild, discord.AuditLogAction.ban, member.id)

        if ban_entry:
            age = abs((now - ban_entry.created_at).total_seconds())

            if age <= max_audit_age_seconds:
                action_type = "🔨 تبند"
                executor_text = ban_entry.user.mention if ban_entry.user else "غير معروف"
                reason_text = ban_entry.reason if ban_entry.reason else "بدون سبب مكتوب"
                action_details = "تم حظر العضو من السيرفر."
                color = COLOR_RED

        if action_type == "📤 خرج من نفسه":
            kick_entry = await get_audit_executor(guild, discord.AuditLogAction.kick, member.id)

            if kick_entry:
                age = abs((now - kick_entry.created_at).total_seconds())

                if age <= max_audit_age_seconds:
                    action_type = "👢 انطرد"
                    executor_text = kick_entry.user.mention if kick_entry.user else "غير معروف"
                    reason_text = kick_entry.reason if kick_entry.reason else "بدون سبب مكتوب"
                    action_details = "تم طرد العضو من السيرفر."
                    color = COLOR_RED

    except Exception as e:
        print(f"Leave audit check error: {e}")

    roles_text, roles_count = format_roles_list(member)

    created_at = int(member.created_at.timestamp())

    joined_at_text = "غير معروف"

    if member.joined_at:
        joined_at_text = f"<t:{int(member.joined_at.timestamp())}:F> | <t:{int(member.joined_at.timestamp())}:R>"

    embed = discord.Embed(
        title="🚪 Member Leave Info",
        description="تم تسجيل خروج عضو من السيرفر.",
        color=color,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="👤 معلومات العضو",
        value=(
            f"**Mention:** {member.mention}\n"
            f"**User:** `{member}`\n"
            f"**Display Name:** `{member.display_name}`\n"
            f"**User ID:** `{member.id}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📌 نوع الخروج",
        value=(
            f"**الحالة:** {action_type}\n"
            f"**التفصيل:** {action_details}\n"
            f"**بواسطة:** {executor_text}\n"
            f"**السبب:** {reason_text}"
        ),
        inline=False
    )

    embed.add_field(
        name="📅 تفاصيل الحساب",
        value=(
            f"**تاريخ إنشاء الحساب:** <t:{created_at}:F> | <t:{created_at}:R>\n"
            f"**تاريخ دخول السيرفر:** {joined_at_text}"
        ),
        inline=False
    )

    embed.add_field(
        name=f"🎭 الرتب اللي كانت معه قبل الخروج ({roles_count})",
        value=roles_text,
        inline=False
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="NM System | nm_leave_info")

    leave_channel = await get_channel_by_id(guild, LEAVE_INFO_CHANNEL_ID)

    if leave_channel:
        try:
            await leave_channel.send(embed=embed)
        except:
            pass

    await send_log(
        guild,
        action_type,
        f"""
**العضو:** `{member}`
**ID:** `{member.id}`
**بواسطة:** {executor_text}
**السبب:** {reason_text}

**الرتب اللي كانت معه قبل الخروج:**
{roles_text}
""",
        color,
        log_type="member"
    )


@bot.event
async def on_member_ban(guild, user):
    if guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(guild, discord.AuditLogAction.ban, user.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"
    reason_text = entry.reason if entry and entry.reason else "بدون سبب مكتوب"

    await send_log(
        guild,
        "🔨 عضو تبند",
        f"""
**العضو:** `{user}`
**ID:** `{user.id}`
**بواسطة:** {executor_text}
**السبب:** {reason_text}
""",
        COLOR_RED,
        log_type="member"
    )


@bot.event
async def on_member_unban(guild, user):
    if guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(guild, discord.AuditLogAction.unban, user.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"
    reason_text = entry.reason if entry and entry.reason else "بدون سبب مكتوب"

    await send_log(
        guild,
        "✅ فك باند",
        f"""
**العضو:** `{user}`
**ID:** `{user.id}`
**بواسطة:** {executor_text}
**السبب:** {reason_text}
""",
        COLOR_GREEN,
        log_type="member"
    )


@bot.event
async def on_member_update(before, after):
    if before.guild.id != GUILD_ID:
        return

    before_roles = set(before.roles)
    after_roles = set(after.roles)

    added = after_roles - before_roles
    removed = before_roles - after_roles

    if added:
        roles_text = ", ".join([r.mention for r in added if r.name != "@everyone"])
        entry = await get_audit_executor(after.guild, discord.AuditLogAction.member_role_update, after.id)
        executor_text = entry.user.mention if entry and entry.user else "غير معروف"

        if any(role.id == SERVER_BOOSTER_ROLE_ID for role in added):
            channel = after.guild.get_channel(COMMANDS_CHANNEL_ID)
            success, remaining, balance_amount, reward = claim_booster_weekly(after.id)

            if channel and success:
                embed = discord.Embed(
                    title="🚀 شكراً على Server Boost",
                    description=f"{after.mention} استلمت مكافأة البوست الأسبوعية.",
                    color=COLOR_PURPLE,
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="🎁 Reward", value=money_delta(reward), inline=True)
                embed.add_field(name="💼 New Balance", value=coin_line(balance_amount), inline=True)
                embed.set_footer(text=f"{BOT_BRAND} • Booster Reward")
                await channel.send(embed=embed)

        if roles_text:
            await send_log(
                after.guild,
                "➕ رتبة انضافت",
                f"""
**العضو:** {after.mention}
**الرول:** {roles_text}
**بواسطة:** {executor_text}
""",
                COLOR_GREEN,
                log_type="role"
            )

    if removed:
        roles_text = ", ".join([r.mention for r in removed if r.name != "@everyone"])
        entry = await get_audit_executor(after.guild, discord.AuditLogAction.member_role_update, after.id)
        executor_text = entry.user.mention if entry and entry.user else "غير معروف"

        if roles_text:
            await send_log(
                after.guild,
                "➖ رتبة انشالت",
                f"""
**العضو:** {after.mention}
**الرول:** {roles_text}
**بواسطة:** {executor_text}
""",
                COLOR_RED,
                log_type="role"
            )

    if before.nick != after.nick:
        await send_log(
            after.guild,
            "📝 تغيير نك نيم",
            f"""
**العضو:** {after.mention}
**قبل:** `{before.nick}`
**بعد:** `{after.nick}`
""",
            COLOR_YELLOW,
            log_type="member"
        )

    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until:
            await send_log(
                after.guild,
                "⏳ تايم أوت",
                f"""
**العضو:** {after.mention}
**ينتهي:** <t:{int(after.timed_out_until.timestamp())}:R>
""",
                COLOR_RED,
                log_type="moderation"
            )
        else:
            await send_log(
                after.guild,
                "✅ فك تايم أوت",
                f"**العضو:** {after.mention}",
                COLOR_GREEN,
                log_type="moderation"
            )


@bot.event
async def on_guild_channel_create(channel):
    if channel.guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        channel.guild,
        "➕ روم جديد",
        f"""
**الروم:** {channel.mention if hasattr(channel, 'mention') else channel.name}
**الاسم:** `{channel.name}`
**بواسطة:** {executor_text}
""",
        COLOR_GREEN,
        log_type="channel"
    )


@bot.event
async def on_guild_channel_delete(channel):
    if channel.guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        channel.guild,
        "🗑️ روم انحذف",
        f"""
**الاسم:** `{channel.name}`
**بواسطة:** {executor_text}
""",
        COLOR_RED,
        log_type="channel"
    )


@bot.event
async def on_guild_channel_update(before, after):
    if before.guild.id != GUILD_ID:
        return

    changes = []

    if before.name != after.name:
        changes.append(f"**الاسم:** `{before.name}` → `{after.name}`")

    if before.category != after.category:
        before_cat = before.category.name if before.category else "بدون"
        after_cat = after.category.name if after.category else "بدون"
        changes.append(f"**الكاتقوري:** `{before_cat}` → `{after_cat}`")

    if before.position != after.position:
        changes.append(f"**المكان:** `{before.position}` → `{after.position}`")

    if not changes:
        return

    entry = await get_audit_executor(after.guild, discord.AuditLogAction.channel_update, after.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        after.guild,
        "📝 تعديل روم",
        "\n".join(changes) + f"\n**بواسطة:** {executor_text}",
        COLOR_YELLOW,
        log_type="channel"
    )


@bot.event
async def on_guild_role_create(role):
    if role.guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(role.guild, discord.AuditLogAction.role_create, role.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        role.guild,
        "➕ رتبة جديدة",
        f"""
**الرول:** {role.mention}
**الاسم:** `{role.name}`
**بواسطة:** {executor_text}
""",
        COLOR_GREEN,
        log_type="role"
    )


@bot.event
async def on_guild_role_delete(role):
    if role.guild.id != GUILD_ID:
        return

    entry = await get_audit_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        role.guild,
        "🗑️ رتبة انحذفت",
        f"""
**الاسم:** `{role.name}`
**بواسطة:** {executor_text}
""",
        COLOR_RED,
        log_type="role"
    )


@bot.event
async def on_guild_role_update(before, after):
    if before.guild.id != GUILD_ID:
        return

    changes = []

    if before.name != after.name:
        changes.append(f"**الاسم:** `{before.name}` → `{after.name}`")

    if before.color != after.color:
        changes.append(f"**اللون:** `{before.color}` → `{after.color}`")

    if before.permissions.value != after.permissions.value:
        changes.append("**الصلاحيات:** تغيرت")

    if before.mentionable != after.mentionable:
        changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")

    if before.hoist != after.hoist:
        changes.append(f"**Hoist:** `{before.hoist}` → `{after.hoist}`")

    if not changes:
        return

    entry = await get_audit_executor(after.guild, discord.AuditLogAction.role_update, after.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    await send_log(
        after.guild,
        "🛠️ تعديل رتبة",
        f"""
**الرول:** {after.mention}

{chr(10).join(changes)}

**بواسطة:** {executor_text}
""",
        COLOR_YELLOW,
        log_type="role"
    )


@bot.event
async def on_voice_state_update(member, before, after):
    if member.guild.id != GUILD_ID or member.bot:
        return

    if after.channel and after.channel.name.startswith("🎮-"):
        cancel_game_room_delete(after.channel)

    if before.channel and before.channel.name.startswith("🎮-"):
        if len(before.channel.members) == 0:
            await schedule_delete_empty_game_room(before.channel)

    if before.channel is None and after.channel is not None:
        await send_log(
            member.guild,
            "🔊 دخول فويس",
            f"**العضو:** {member.mention}\n**الروم:** `{after.channel.name}`",
            COLOR_GREEN,
            log_type="voice"
        )

    elif before.channel is not None and after.channel is None:
        await send_log(
            member.guild,
            "🔇 خروج من فويس",
            f"**العضو:** {member.mention}\n**الروم:** `{before.channel.name}`",
            COLOR_GREY,
            log_type="voice"
        )

    elif before.channel != after.channel:
        await send_log(
            member.guild,
            "🔁 نقل فويس",
            f"""
**العضو:** {member.mention}
**من:** `{before.channel.name}`
**إلى:** `{after.channel.name}`
""",
            COLOR_BLUE,
            log_type="voice"
        )


@bot.event
async def on_guild_update(before, after):
    if before.id != GUILD_ID:
        return

    changes = []

    if before.name != after.name:
        changes.append(f"**اسم السيرفر:** `{before.name}` → `{after.name}`")

    if before.icon != after.icon:
        changes.append("**الصورة:** تغيرت")

    if not changes:
        return

    await send_log(
        after,
        "⚙️ تعديل السيرفر",
        "\n".join(changes),
        COLOR_YELLOW,
        log_type="server"
    )


# =========================
# COMMANDS
# =========================

@bot.command(name="مساعدة", aliases=["helpme"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📖 أوامر NM System", color=COLOR_PURPLE)

    embed.description = """
**إنشاء وإعداد**
`!انشاء` - ينشئ رومات اللوقات فقط
`!اعداد` - يجهز الشروحات ولوحة الرولات بدون إنشاء رتب جديدة

**عامة**
`!بنق`
`!هلا`
`!معلومات @شخص`
`!طقطق @شخص`
`!تقييم الشي`

**الحماية**
`!حماية`
`!حماية تشغيل`
`!حماية ايقاف`
`!اعدادات`
`!تحذير @شخص السبب`
`!تحذيرات @شخص`
`!تصفير @شخص`

**Community**
`!اقتراح اقتراحك`
`!لعب Valorant 5 ملاحظة`
`!سحب Nitro 1h 1`
`!رولات`

**رسائل الخاص**
❌ أوامر الخاص معطّلة مؤقتًا بسبب Quarantine من Discord.
استخدم `!اعلان نص الإعلان` بدل إرسال الخاص.

**Level - في روم commands فقط**
`!لفلي`
`!لفل @شخص`
`!ترتيب`

**Economy - في روم commands فقط**
`!اقتصاد` - شرح النظام
`!رصيدي`
`!رصيد @شخص`
`!يومي` أو `!ساعتي`
`!بوست` أو `!اسبوعي`
`!تحويل @شخص 500`
`!اغنى`

**Gambling - في روم القمار فقط**
`!شرح_القمار`
`!حظ 500`
`!دبل 500`
`!سلوت 500`
`!وجه 500 ملك`
`!وجه 500 كتابة`

**Economy Admin**
`!اعطاءفلوس @شخص 1000`
`!سحبفلوس @شخص 500`
`!تصفيرفلوس @شخص`

**إدارة**
`!مسح 10`
`!قفل`
`!فتح`
`!لوحة`
`!اعلان نص الإعلان`
"""

    await ctx.send(embed=embed)


@bot.command(name="انشاء", aliases=["create_logs"])
@commands.has_permissions(administrator=True)
async def create_logs_command(ctx):
    guild = ctx.guild

    if not guild or guild.id != GUILD_ID:
        await ctx.send("❌ هذا الأمر يشتغل بس في السيرفر الأساسي.")
        return

    loading = await ctx.send("⚙️ جاري إنشاء رومات اللوقات فقط...")

    try:
        log_channels = await create_or_find_log_channels(guild)

        embed = discord.Embed(
            title="✅ تم إنشاء رومات اللوقات",
            description="تم إنشاء/تحديث رومات اللوقات داخل الكاتقوري المحدد.",
            color=COLOR_GREEN,
            timestamp=discord.utils.utcnow()
        )

        logs_text = ""

        for log_key, channel in log_channels.items():
            logs_text += f"• `{log_key}` → {channel.mention}\n"

        embed.add_field(name="📁 رومات اللوقات", value=logs_text[:1000], inline=False)
        embed.add_field(
            name="📌 ملاحظة",
            value="إذا الروم موجود من قبل، البوت ما يكرره. يستخدم الموجود ويحفظ ID حقه.",
            inline=False
        )
        embed.set_footer(text="NM System | Logs Setup")

        await loading.edit(content="✅ تم إنشاء رومات اللوقات بنجاح.")
        await ctx.send(embed=embed)

        await send_log(
            guild,
            "⚙️ إنشاء رومات اللوقات",
            f"""
**بواسطة:** {ctx.author.mention}
**الأمر:** `!انشاء`
**الكاتقوري:** `{LOGS_CATEGORY_ID}`
**عدد رومات اللوقات:** `{len(log_channels)}`
""",
            COLOR_BLUE,
            log_type="server"
        )

    except Exception as e:
        await loading.edit(content=f"❌ صار خطأ أثناء إنشاء رومات اللوقات:\n```{e}```")


@bot.command(name="بنق", aliases=["ping"])
async def ping(ctx):
    await ctx.send(
        embed=discord.Embed(
            title="🏓 Pong",
            description="NM System شغال.",
            color=COLOR_GREEN
        )
    )


@bot.command(name="هلا", aliases=["hello"])
async def hello(ctx):
    await ctx.send(
        embed=discord.Embed(
            title="👋 أهلاً",
            description=f"مرحباً {ctx.author.mention}",
            color=COLOR_GREY
        )
    )


@bot.command(name="معلومات", aliases=["info", "user"])
async def user_info(ctx, member: discord.Member = None):
    member = member or ctx.author

    xp, level_num = get_level_data(member.id)
    needed = level_num * 100

    user_warnings = warnings.get(str(member.id), [])
    roles_text, roles_count = format_roles_list(member)

    created_at = int(member.created_at.timestamp())

    joined_at_text = "غير معروف"
    if member.joined_at:
        joined_at_text = f"<t:{int(member.joined_at.timestamp())}:F> | <t:{int(member.joined_at.timestamp())}:R>"

    timeout_text = "لا"
    if member.timed_out_until:
        timeout_text = f"نعم، ينتهي <t:{int(member.timed_out_until.timestamp())}:R>"

    top_role = member.top_role.mention if member.top_role and member.top_role.name != "@everyone" else "لا يوجد"

    embed = discord.Embed(
        title="👤 معلومات العضو",
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="📌 الأساسي",
        value=(
            f"**Mention:** {member.mention}\n"
            f"**User:** `{member}`\n"
            f"**Display Name:** `{member.display_name}`\n"
            f"**User ID:** `{member.id}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📅 التواريخ",
        value=(
            f"**إنشاء الحساب:** <t:{created_at}:F> | <t:{created_at}:R>\n"
            f"**دخول السيرفر:** {joined_at_text}"
        ),
        inline=False
    )

    embed.add_field(name="📊 اللفل", value=f"**Level:** `{level_num}`\n**XP:** `{xp}/{needed}`", inline=True)
    embed.add_field(name="🚫 التحذيرات", value=f"`{len(user_warnings)}` تحذير", inline=True)
    embed.add_field(name="⏳ تايم أوت", value=timeout_text, inline=True)
    embed.add_field(name="🏷️ أعلى رتبة", value=top_role, inline=False)
    embed.add_field(name=f"🎭 الرتب ({roles_count})", value=roles_text, inline=False)
    embed.set_footer(text="NM System | User Info")

    await ctx.send(embed=embed)


@bot.command(name="طقطق", aliases=["roast"])
async def roast(ctx, member: discord.Member = None):
    member = member or ctx.author

    roasts = [
        "حتى البوت احتار في وضعك.",
        "وجودك لحاله حدث نادر.",
        "لو الكسل بطولة كان أخذت المركز الأول.",
        "ياخي أنت glitch في الحياة.",
        "واضح إنك تحتاج تحديث نظام."
    ]

    await ctx.send(
        embed=discord.Embed(
            title="😂 طقطقة",
            description=f"{member.mention} {random.choice(roasts)}",
            color=COLOR_YELLOW
        )
    )


@bot.command(name="تقييم", aliases=["rate"])
async def rate(ctx, *, thing="أنت"):
    await ctx.send(
        embed=discord.Embed(
            title="⭐ تقييم",
            description=f"تقييمي لـ **{thing}**: **{random.randint(1, 10)}/10**",
            color=COLOR_YELLOW
        )
    )


@bot.command(name="اقتراح", aliases=["suggest"])
async def suggest(ctx, *, idea=None):
    if not idea:
        await ctx.send("اكتب كذا: `!اقتراح نسوي فعالية يوم الجمعة`")
        return

    save_suggestion(ctx.author.id, idea)

    embed = discord.Embed(title="💡 اقتراح جديد", description=idea, color=COLOR_YELLOW)
    embed.add_field(name="👤 صاحب الاقتراح", value=ctx.author.mention, inline=False)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="صوّت على الاقتراح")

    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    await send_log(
        ctx.guild,
        "💡 اقتراح جديد",
        f"**من:** {ctx.author.mention}\n**الاقتراح:** {idea[:800]}",
        COLOR_YELLOW,
        log_type="server"
    )


@bot.command(name="لعب", aliases=["play"])
async def play(ctx, game=None, players: int = None, *, note=""):
    if not game or not players:
        await ctx.send("استخدم: `!لعب Valorant 5 نبي قيم سريع`")
        return

    if players < 1:
        await ctx.send("❌ العدد لازم يكون 1 أو أكثر.")
        return

    if players > 20:
        await ctx.send("❌ الحد الأقصى للتجمع 20 لاعب.")
        return

    view = JoinPlayView(
        game=game,
        max_players=players,
        host_id=ctx.author.id,
        note=note
    )

    embed = discord.Embed(
        title="🎮 Looking For Game",
        description=f"تجمع على **{game}**",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(name="👤 صاحب التجمع", value=ctx.author.mention, inline=True)
    embed.add_field(name="👥 العدد", value=f"1/{players}", inline=True)
    embed.add_field(name="📝 ملاحظة", value=note if note else "لا يوجد", inline=False)
    embed.add_field(name="👥 اللي بيدخلون", value=f"• {ctx.author.mention}", inline=False)

    if players == 1:
        embed.add_field(name="🔒 الحالة", value="اكتمل العدد، سيتم فتح الروم الخاص.", inline=False)

    embed.set_footer(text="NM System | اضغط بدخل إذا بتشارك")

    target_msg = await send_to_channel(
        ctx.guild,
        LOOKING_FOR_GAME_CHANNEL_ID,
        embed=embed,
        view=view
    )

    if target_msg:
        await ctx.message.add_reaction("✅")
        source_channel = target_msg.channel
    else:
        target_msg = await ctx.send(embed=embed, view=view)
        source_channel = ctx.channel

    await send_log(
        ctx.guild,
        "🎮 طلب لعب",
        f"""
**من:** {ctx.author.mention}
**اللعبة:** {game}
**العدد:** {players}
**ملاحظة:** {note or 'لا يوجد'}
""",
        COLOR_GREEN,
        log_type="game"
    )

    if players == 1:
        await create_game_voice_channel(
            guild=ctx.guild,
            source_channel=source_channel,
            game=game,
            player_ids=[ctx.author.id],
            max_players=players
        )


@bot.command(name="سحب", aliases=["giveaway"])
@commands.has_permissions(manage_guild=True)
async def giveaway(ctx, prize=None, duration=None, winners: int = 1):
    if not prize or not duration:
        await ctx.send("استخدم: `!سحب Nitro 1h 1`")
        return

    seconds = parse_duration_to_seconds(duration)

    if seconds is None:
        await ctx.send("صيغة المدة غلط. استخدم: `30m` أو `1h` أو `1d`")
        return

    view = GiveawayView()
    end_time = int(time.time() + seconds)

    embed = discord.Embed(
        title="🎁 Giveaway",
        description=f"**الجائزة:** {prize}\n**عدد الفائزين:** {winners}\n**ينتهي:** <t:{end_time}:R>",
        color=COLOR_YELLOW
    )
    embed.add_field(name="طريقة الدخول", value="اضغط زر **دخول السحب**.", inline=False)
    embed.set_footer(text="NM System | Giveaway")

    msg = await send_to_channel(
        ctx.guild,
        GIVEAWAYS_CHANNEL_ID,
        embed=embed,
        view=view
    )

    if not msg:
        msg = await ctx.send(embed=embed, view=view)
    else:
        await ctx.message.add_reaction("✅")

    await send_log(
        ctx.guild,
        "🎁 سحب جديد",
        f"**بواسطة:** {ctx.author.mention}\n**الجائزة:** {prize}\n**المدة:** {duration}\n**الفائزين:** {winners}",
        COLOR_YELLOW,
        log_type="giveaway"
    )

    await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=seconds))

    entries = list(view.entries)

    if not entries:
        await send_to_channel(
            ctx.guild,
            GIVEAWAYS_CHANNEL_ID,
            embed=discord.Embed(
                title="🎁 انتهى السحب",
                description=f"الجائزة: **{prize}**\nمافي أحد دخل.",
                color=COLOR_RED
            )
        )

        await send_log(
            ctx.guild,
            "🎁 انتهى السحب بدون مشاركين",
            f"**الجائزة:** {prize}",
            COLOR_RED,
            log_type="giveaway"
        )
        return

    winners_count = min(winners, len(entries))
    selected = random.sample(entries, winners_count)
    winners_text = " ".join([f"<@{uid}>" for uid in selected])

    result_embed = discord.Embed(
        title="🎉 انتهى السحب",
        description=f"**الجائزة:** {prize}\n**الفائزين:** {winners_text}",
        color=COLOR_GREEN
    )

    await send_to_channel(
        ctx.guild,
        GIVEAWAYS_CHANNEL_ID,
        content=winners_text,
        embed=result_embed
    )

    await send_log(
        ctx.guild,
        "🎉 انتهى السحب",
        f"**الجائزة:** {prize}\n**الفائزين:** {winners_text}",
        COLOR_GREEN,
        log_type="giveaway"
    )


@bot.command(name="رولات", aliases=["roles"])
@commands.has_permissions(administrator=True)
async def roles(ctx):
    embed = discord.Embed(
        title="🎭 Game Roles",
        description="اختار اللعبة اللي تهمك من الأزرار تحت.\nاضغط مرة تأخذ الرتبة، واضغط مرة ثانية تشيلها.",
        color=COLOR_BLUE
    )

    msg = await send_to_channel(
        ctx.guild,
        ROLES_CHANNEL_ID,
        embed=embed,
        view=GameRolesView()
    )

    if msg:
        await ctx.message.add_reaction("✅")
    else:
        await ctx.send(embed=embed, view=GameRolesView())


@bot.command(name="dm")
@commands.has_permissions(administrator=True)
async def dm_user(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmembed")
@commands.has_permissions(administrator=True)
async def dm_user_embed(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmtest")
@commands.has_permissions(administrator=True)
async def dm_test(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmrole")
@commands.has_permissions(administrator=True)
async def dm_role(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmroleembed")
@commands.has_permissions(administrator=True)
async def dm_role_embed(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmall")
@commands.has_permissions(administrator=True)
async def dm_all(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="dmallembed")
@commands.has_permissions(administrator=True)
async def dm_all_embed(ctx, *args, **kwargs):
    await dm_disabled_reply(ctx)

@bot.command(name="لفلي", aliases=["rank"])
async def my_level(ctx):
    if not await require_commands_channel(ctx):
        return

    xp, level = get_level_data(ctx.author.id)
    needed = level * 100
    balance = get_balance(ctx.author.id)
    progress = xp_progress_bar(xp, needed)

    embed = discord.Embed(
        title=f"{LEVEL_EMOJI} Level Profile",
        description=f"{ctx.author.mention}\n`{progress}` **{xp}/{needed} XP**",
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="🏅 Level", value=f"**{level}**", inline=True)
    embed.add_field(name="⚡ XP", value=f"**{xp:,}/{needed:,}**", inline=True)
    embed.add_field(name=f"{ECONOMY_EMOJI} Balance", value=f"**{balance:,}**\n{COIN_NAME}", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Level System")
    await ctx.send(embed=embed)


@bot.command(name="لفل", aliases=["level"])
async def level(ctx, member: discord.Member = None):
    if not await require_commands_channel(ctx):
        return

    member = member or ctx.author
    xp, level_num = get_level_data(member.id)
    needed = level_num * 100
    balance = get_balance(member.id)
    progress = xp_progress_bar(xp, needed)

    embed = discord.Embed(
        title=f"{LEVEL_EMOJI} Level Profile",
        description=f"{member.mention}\n`{progress}` **{xp}/{needed} XP**",
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏅 Level", value=f"**{level_num}**", inline=True)
    embed.add_field(name="⚡ XP", value=f"**{xp:,}/{needed:,}**", inline=True)
    embed.add_field(name=f"{ECONOMY_EMOJI} Balance", value=f"**{balance:,}**\n{COIN_NAME}", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Level System")
    await ctx.send(embed=embed)


@bot.command(name="ترتيب", aliases=["leaderboard", "top"])
async def leaderboard(ctx):
    if not await require_commands_channel(ctx):
        return

    rows = get_top_levels(10)

    if not rows:
        await ctx.send("مافي بيانات لفل للحين.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = ""

    for i, (user_id, xp, level) in enumerate(rows, start=1):
        icon = medals[i - 1] if i <= 3 else f"`#{i}`"
        text += f"{icon} <@{user_id}> — **Level {level}** | `{xp:,} XP`\n"

    embed = discord.Embed(
        title="🏆 Level Leaderboard",
        description=text,
        color=COLOR_YELLOW,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_BRAND} | Top 10 Levels")
    await ctx.send(embed=embed)


@bot.command(name="رصيدي", aliases=["balance", "bal", "فلوسي"])
async def my_balance(ctx):
    if not await require_commands_channel(ctx):
        return

    balance = get_balance(ctx.author.id)
    xp, level = get_level_data(ctx.author.id)
    needed = level * 100
    daily_bonus = DAILY_REWARD_BASE + (int(level) * 25)
    rank = get_money_rank(ctx.author.id)
    progress = clean_bar(xp / needed if needed else 0)

    embed = discord.Embed(
        title=f"{ECONOMY_EMOJI} Retard Wallet",
        description=(
            f"محفظة {ctx.author.mention}\n"
            f"`{progress}` **{xp:,}/{needed:,} XP**"
        ),
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="💼 Balance", value=coin_line(balance), inline=False)
    embed.add_field(name="🏆 Money Rank", value=f"**#{rank}**" if rank else "غير معروف", inline=True)
    embed.add_field(name="🏅 Level", value=f"**{level}**", inline=True)
    embed.add_field(name="⏰ Hourly Reward", value=coin_line(daily_bonus), inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Economy Wallet")
    await ctx.send(embed=embed)


@bot.command(name="رصيد", aliases=["money", "coins"])
async def balance(ctx, member: discord.Member = None):
    if not await require_commands_channel(ctx):
        return

    member = member or ctx.author
    balance_amount = get_balance(member.id)
    xp, level_num = get_level_data(member.id)
    needed = level_num * 100
    daily_bonus = DAILY_REWARD_BASE + (int(level_num) * 25)
    rank = get_money_rank(member.id)
    progress = clean_bar(xp / needed if needed else 0)

    embed = discord.Embed(
        title=f"{ECONOMY_EMOJI} Retard Wallet",
        description=(
            f"محفظة {member.mention}\n"
            f"`{progress}` **{xp:,}/{needed:,} XP**"
        ),
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="💼 Balance", value=coin_line(balance_amount), inline=False)
    embed.add_field(name="🏆 Money Rank", value=f"**#{rank}**" if rank else "غير معروف", inline=True)
    embed.add_field(name="🏅 Level", value=f"**{level_num}**", inline=True)
    embed.add_field(name="⏰ Hourly Reward", value=coin_line(daily_bonus), inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Economy Wallet")
    await ctx.send(embed=embed)


@bot.command(name="يومي", aliases=["daily", "ساعتي", "hourly"])
async def daily(ctx):
    if not await require_commands_channel(ctx):
        return

    xp, level = get_level_data(ctx.author.id)
    success, remaining, balance_amount, reward = claim_daily(ctx.author.id, level)

    if not success:
        embed = discord.Embed(
            title="⏳ المكافأة الساعية مأخوذة",
            description=f"ارجع بعد **{format_seconds(remaining)}**.",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="💼 Balance", value=coin_line(balance_amount), inline=False)
        embed.set_footer(text=f"{BOT_BRAND} • Hourly Reward")
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="🎁 Hourly Reward Claimed",
        description=f"تم إضافة المكافأة لمحفظتك يا {ctx.author.mention}.",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="🎁 Reward", value=money_delta(reward), inline=True)
    embed.add_field(name="💼 New Balance", value=coin_line(balance_amount), inline=True)
    embed.add_field(name="🏅 Level Bonus", value=f"Level **{level}**", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • كل ساعة تقدر تاخذ المكافأة")
    await ctx.send(embed=embed)


@bot.command(name="بوست", aliases=["boost", "booster", "اسبوعي", "weekly"])
async def booster_weekly(ctx):
    if not await require_commands_channel(ctx):
        return

    if not is_server_booster(ctx.author):
        embed = discord.Embed(
            title="🚀 مكافأة البوست الأسبوعية",
            description=f"هذي المكافأة خاصة للي عندهم رتبة <@&{SERVER_BOOSTER_ROLE_ID}>.",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="المطلوب", value="سو Server Boost أو خذ رتبة البوست عشان تقدر تستلمها.", inline=False)
        embed.set_footer(text=f"{BOT_BRAND} • Booster Weekly")
        await ctx.send(embed=embed)
        return

    success, remaining, balance_amount, reward = claim_booster_weekly(ctx.author.id)

    if not success:
        embed = discord.Embed(
            title="⏳ مكافأة البوست مو جاهزة",
            description=f"ارجع بعد **{format_seconds(remaining)}**.",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="💼 Balance", value=coin_line(balance_amount), inline=False)
        embed.set_footer(text=f"{BOT_BRAND} • Booster Weekly")
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="🚀 Booster Weekly Claimed",
        description=f"شكراً على دعم السيرفر يا {ctx.author.mention}.",
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="🎁 Weekly Reward", value=money_delta(reward), inline=True)
    embed.add_field(name="💼 New Balance", value=coin_line(balance_amount), inline=True)
    embed.add_field(name="⏳ Cooldown", value="كل أسبوع", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Server Booster Reward")
    await ctx.send(embed=embed)


@bot.command(name="تحويل", aliases=["pay", "transfer"])
async def transfer_money(ctx, member: discord.Member = None, amount: int = None):
    if not await require_commands_channel(ctx):
        return

    if member is None or amount is None:
        await ctx.send("استخدم: `!تحويل @شخص 500`")
        return

    if member.bot:
        await ctx.send("❌ ما تقدر تحول للبوتات.")
        return

    if member.id == ctx.author.id:
        await ctx.send("❌ ما تقدر تحول لنفسك.")
        return

    if amount <= 0:
        await ctx.send("❌ المبلغ لازم يكون أكبر من صفر.")
        return

    success, new_sender_balance = remove_money(ctx.author.id, amount)

    if not success:
        await ctx.send("❌ رصيدك ما يكفي.")
        return

    new_receiver_balance = add_money(member.id, amount)

    embed = discord.Embed(
        title="✅ Transfer Complete",
        description="تم التحويل بنجاح.",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="من", value=ctx.author.mention, inline=True)
    embed.add_field(name="إلى", value=member.mention, inline=True)
    embed.add_field(name="المبلغ", value=f"**{amount:,}** {COIN_NAME}", inline=False)
    embed.add_field(name="رصيد المرسل", value=f"**{new_sender_balance:,}**", inline=True)
    embed.add_field(name="رصيد المستلم", value=f"**{new_receiver_balance:,}**", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Economy Transfer")
    await ctx.send(embed=embed)


@bot.command(name="اغنى", aliases=["rich", "topmoney"])
async def richest(ctx):
    if not await require_commands_channel(ctx):
        return

    rows = get_top_money(10)

    if not rows:
        await ctx.send("مافي بيانات اقتصاد للحين.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = ""
    total = db_sum_column("economy", "balance")

    for i, (user_id, balance_amount) in enumerate(rows, start=1):
        icon = medals[i - 1] if i <= 3 else f"`#{i}`"
        text += f"{icon} <@{user_id}> — {coin_line(balance_amount)} `({short_money(balance_amount)})`\n"

    embed = discord.Embed(
        title=f"💎 Richest Wallets",
        description=text,
        color=COLOR_YELLOW,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="🏦 Total Economy", value=coin_line(total), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} • Economy Leaderboard")
    await ctx.send(embed=embed)


@bot.command(name="اعطاءفلوس", aliases=["addmoney"])
@commands.has_permissions(administrator=True)
async def admin_add_money(ctx, member: discord.Member = None, amount: int = None):
    if not await require_commands_channel(ctx):
        return

    if member is None or amount is None:
        await ctx.send("استخدم: `!اعطاءفلوس @شخص 1000`")
        return

    if amount <= 0:
        await ctx.send("❌ المبلغ لازم يكون أكبر من صفر.")
        return

    balance_amount = add_money(member.id, amount)
    embed = discord.Embed(title="✅ Admin Economy", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
    embed.description = f"تم إعطاء {member.mention} **{amount:,} {COIN_NAME}**."
    embed.add_field(name="رصيده الآن", value=f"**{balance_amount:,}** {COIN_NAME}", inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Economy Admin")
    await ctx.send(embed=embed)


@bot.command(name="سحبفلوس", aliases=["removemoney"])
@commands.has_permissions(administrator=True)
async def admin_remove_money(ctx, member: discord.Member = None, amount: int = None):
    if not await require_commands_channel(ctx):
        return

    if member is None or amount is None:
        await ctx.send("استخدم: `!سحبفلوس @شخص 500`")
        return

    if amount <= 0:
        await ctx.send("❌ المبلغ لازم يكون أكبر من صفر.")
        return

    success, balance_amount = remove_money(member.id, amount)

    if not success:
        await ctx.send("❌ رصيد العضو ما يكفي للسحب.")
        return

    embed = discord.Embed(title="✅ Admin Economy", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
    embed.description = f"تم سحب **{amount:,} {COIN_NAME}** من {member.mention}."
    embed.add_field(name="رصيده الآن", value=f"**{balance_amount:,}** {COIN_NAME}", inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Economy Admin")
    await ctx.send(embed=embed)


@bot.command(name="تصفيرفلوس", aliases=["resetmoney"])
@commands.has_permissions(administrator=True)
async def admin_reset_money(ctx, member: discord.Member = None):
    if not await require_commands_channel(ctx):
        return

    if member is None:
        await ctx.send("استخدم: `!تصفيرفلوس @شخص`")
        return

    set_balance(member.id, 0)
    embed = discord.Embed(
        title="🧹 Balance Reset",
        description=f"تم تصفير رصيد {member.mention}.",
        color=COLOR_RED,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_BRAND} | Economy Admin")
    await ctx.send(embed=embed)





# =========================
# BLACKJACK SYSTEM
# =========================

CARD_SUITS = ["♠️", "♥️", "♦️", "♣️"]
CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def draw_blackjack_card():
    return random.choice(CARD_RANKS), random.choice(CARD_SUITS)


def card_text(card):
    rank, suit = card
    return f"`{rank}{suit}`"


def hand_text(cards, hide_second=False):
    if hide_second and len(cards) >= 2:
        return f"{card_text(cards[0])} `??`"
    return " ".join(card_text(card) for card in cards)


def hand_value(cards):
    total = 0
    aces = 0

    for rank, _suit in cards:
        if rank == "A":
            aces += 1
            total += 11
        elif rank in ["J", "Q", "K"]:
            total += 10
        else:
            total += int(rank)

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    return total


def is_natural_blackjack(cards):
    return len(cards) == 2 and hand_value(cards) == 21


def build_blackjack_embed(member, bet, player_cards, dealer_cards, status, color, finished=False, change=None, balance=None, hide_dealer=True):
    player_total = hand_value(player_cards)
    dealer_total = hand_value(dealer_cards)

    dealer_display = hand_text(dealer_cards, hide_second=(hide_dealer and not finished))
    dealer_value = "?" if hide_dealer and not finished else str(dealer_total)

    embed = discord.Embed(
        title="🎴 Blackjack Table",
        description=status,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{member.display_name} • NM Casino", icon_url=member.display_avatar.url)
    embed.add_field(name="🎯 Bet", value=coin_line(bet), inline=True)

    if change is not None:
        embed.add_field(name="📈 Change", value=money_delta(change), inline=True)

    if balance is not None:
        embed.add_field(name="💼 Balance", value=coin_line(balance), inline=False)

    embed.add_field(
        name=f"🧍 Your Hand — {player_total}",
        value=hand_text(player_cards),
        inline=False
    )
    embed.add_field(
        name=f"🤵 Dealer Hand — {dealer_value}",
        value=dealer_display,
        inline=False
    )
    embed.set_footer(text=f"{BOT_BRAND} • Blackjack • Hit / Stand")
    return embed


class BlackjackView(discord.ui.View):
    def __init__(self, player_id, bet, player_cards, dealer_cards):
        super().__init__(timeout=90)
        self.player_id = player_id
        self.bet = bet
        self.player_cards = player_cards
        self.dealer_cards = dealer_cards
        self.finished = False

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ هذي طاولة بلاك جاك مو لك.", ephemeral=True)
            return False
        return True

    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    async def finish_game(self, interaction, status, color, change, balance):
        self.finished = True
        self.disable_buttons()
        embed = build_blackjack_embed(
            interaction.user,
            self.bet,
            self.player_cards,
            self.dealer_cards,
            status,
            color,
            finished=True,
            change=change,
            balance=balance,
            hide_dealer=False
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.send_message("اللعبة منتهية.", ephemeral=True)
            return

        self.player_cards.append(draw_blackjack_card())
        player_total = hand_value(self.player_cards)

        if player_total > 21:
            balance = get_balance(self.player_id)
            await self.finish_game(
                interaction,
                "❌ **BUST** — تعديت 21 وخسرت الرهان.",
                COLOR_RED,
                -self.bet,
                balance
            )
            return

        embed = build_blackjack_embed(
            interaction.user,
            self.bet,
            self.player_cards,
            self.dealer_cards,
            "🃏 سحبت كرت. تقدر تسحب زيادة أو توقف.",
            COLOR_BLUE,
            finished=False,
            hide_dealer=True
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.finished:
            await interaction.response.send_message("اللعبة منتهية.", ephemeral=True)
            return

        while hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(draw_blackjack_card())

        player_total = hand_value(self.player_cards)
        dealer_total = hand_value(self.dealer_cards)

        if dealer_total > 21:
            payout = self.bet * 2
            balance = add_money(self.player_id, payout)
            await self.finish_game(
                interaction,
                "✅ **DEALER BUST** — الديلر تعدى 21، فزت.",
                COLOR_GREEN,
                self.bet,
                balance
            )
            return

        if player_total > dealer_total:
            payout = self.bet * 2
            balance = add_money(self.player_id, payout)
            await self.finish_game(
                interaction,
                "✅ **WIN** — مجموعك أعلى من الديلر.",
                COLOR_GREEN,
                self.bet,
                balance
            )
            return

        if player_total < dealer_total:
            balance = get_balance(self.player_id)
            await self.finish_game(
                interaction,
                "❌ **LOSE** — الديلر أعلى منك.",
                COLOR_RED,
                -self.bet,
                balance
            )
            return

        balance = add_money(self.player_id, self.bet)
        await self.finish_game(
            interaction,
            "🟨 **PUSH** — تعادل، رجع لك الرهان.",
            COLOR_YELLOW,
            0,
            balance
        )

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        self.disable_buttons()
        # الرهان تم سحبه عند بداية اللعبة، والوقت انتهى بدون Stand/Hit.

@bot.command(name="شرح_القمار", aliases=["قمار", "gambling", "gamblehelp"])
async def gambling_help(ctx):
    if not await require_gambling_channel(ctx):
        return

    embed = discord.Embed(
        title="🎰 Casino Guide",
        description=(
            f"القمار هنا بعملة البوت فقط: {ECONOMY_EMOJI} **{COIN_NAME}**\n"
            "ما فيه حد أعلى للرهان، تدخل بأي مبلغ موجود في محفظتك.\n"
            f"الانتظار بين كل محاولة ومحاولة: **{GAMBLE_COOLDOWN_SECONDS} ثواني**."
        ),
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="🎲 Lucky Roll",
        value="`!حظ 500` — 50% فوز / 50% خسارة",
        inline=False
    )
    embed.add_field(
        name="💎 Double Risk",
        value="`!دبل 500` — 45% فوز / 55% خسارة",
        inline=False
    )
    embed.add_field(
        name="🎰 Slot Machine",
        value="`!سلوت 500` — 3 نفس بعض = x5، رمزين = x2",
        inline=False
    )
    embed.add_field(
        name="🪙 Coin Flip",
        value="`!وجه 500 ملك` أو `!وجه 500 كتابة`",
        inline=False
    )
    embed.add_field(
        name="🎴 Blackjack",
        value="`!بلاكجاك 500` أو `!blackjack 500` — العب ضد الديلر، Hit أو Stand. Blackjack يدفع x1.5",
        inline=False
    )
    embed.add_field(
        name="💡 اختصارات المبلغ",
        value="`10k` = 10,000 • `1m` = 1,000,000 • مثال: `!حظ 25k`",
        inline=False
    )
    embed.set_footer(text=f"{BOT_BRAND} • Casino")
    await ctx.send(embed=embed)


@bot.command(name="حظ", aliases=["coin", "luck"])
async def gamble_luck(ctx, amount=None):
    bet = await validate_gamble(ctx, amount)
    if bet is None:
        return

    remove_money(ctx.author.id, bet)
    win = random.random() < 0.50

    if win:
        payout = bet * 2
        balance = add_money(ctx.author.id, payout)
        embed = gambling_embed(
            "🎲 Lucky Roll",
            "✅ **WIN** — فزت بالدبل.",
            COLOR_GREEN,
            ctx.author,
            bet,
            result_amount=bet,
            balance=balance,
            details="Chance: **50%** • Payout: **x2**",
            game_name="Lucky Roll"
        )
    else:
        balance = get_balance(ctx.author.id)
        embed = gambling_embed(
            "🎲 Lucky Roll",
            "❌ **LOSE** — راحت عليك هالمرة.",
            COLOR_RED,
            ctx.author,
            bet,
            result_amount=-bet,
            balance=balance,
            details="Chance: **50%** • Better luck next time",
            game_name="Lucky Roll"
        )

    await ctx.send(embed=embed)


@bot.command(name="دبل", aliases=["double"])
async def gamble_double(ctx, amount=None):
    bet = await validate_gamble(ctx, amount)
    if bet is None:
        return

    remove_money(ctx.author.id, bet)
    win = random.random() < 0.45

    if win:
        payout = bet * 2
        balance = add_money(ctx.author.id, payout)
        embed = gambling_embed(
            "💎 Double Risk",
            "✅ **DOUBLE HIT** — مخاطرة وطلعت لك.",
            COLOR_GREEN,
            ctx.author,
            bet,
            result_amount=bet,
            balance=balance,
            details="Chance: **45%** • Payout: **x2**",
            game_name="Double Risk"
        )
    else:
        balance = get_balance(ctx.author.id)
        embed = gambling_embed(
            "💎 Double Risk",
            "❌ **BUST** — الدبل ما ضبط.",
            COLOR_RED,
            ctx.author,
            bet,
            result_amount=-bet,
            balance=balance,
            details="Chance: **45%** • Risk: High",
            game_name="Double Risk"
        )

    await ctx.send(embed=embed)


@bot.command(name="سلوت", aliases=["slot", "slots"])
async def gamble_slot(ctx, amount=None):
    bet = await validate_gamble(ctx, amount)
    if bet is None:
        return

    symbols = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
    roll = [random.choice(symbols) for _ in range(3)]
    remove_money(ctx.author.id, bet)

    unique = len(set(roll))
    machine = slot_box(roll)

    if unique == 1:
        multiplier = 5
        payout = bet * multiplier
        balance = add_money(ctx.author.id, payout)
        result = payout - bet
        title = "🎰 SLOT MACHINE — JACKPOT"
        status = f"🔥 **JACKPOT!**\n{machine}"
        details = f"Three match • Reward: **x{multiplier}**"
        color = COLOR_GREEN
    elif unique == 2:
        multiplier = 2
        payout = bet * multiplier
        balance = add_money(ctx.author.id, payout)
        result = payout - bet
        title = "🎰 SLOT MACHINE — SMALL WIN"
        status = f"✅ **TWO MATCH**\n{machine}"
        details = f"Two match • Reward: **x{multiplier}**"
        color = COLOR_YELLOW
    else:
        balance = get_balance(ctx.author.id)
        result = -bet
        title = "🎰 SLOT MACHINE — LOST"
        status = f"❌ **NO MATCH**\n{machine}"
        details = "No match • Reward: **0**"
        color = COLOR_RED

    embed = gambling_embed(
        title,
        status,
        color,
        ctx.author,
        bet,
        result_amount=result,
        balance=balance,
        details=details,
        game_name="Slot Machine"
    )
    await ctx.send(embed=embed)


@bot.command(name="وجه", aliases=["flip", "coinflip"])
async def gamble_flip(ctx, amount=None, choice=None):
    if not choice:
        if not await require_gambling_channel(ctx):
            return
        await ctx.send("استخدم: `!وجه 500 ملك` أو `!وجه 500 كتابة`")
        return

    bet = await validate_gamble(ctx, amount)
    if bet is None:
        return

    choice = str(choice).lower().strip()
    heads_words = ["ملك", "وجه", "heads", "head", "h"]
    tails_words = ["كتابة", "كتابه", "tails", "tail", "t"]

    if choice in heads_words:
        user_choice = "ملك"
    elif choice in tails_words:
        user_choice = "كتابة"
    else:
        await ctx.send("اختيارك لازم يكون `ملك` أو `كتابة`.")
        return

    remove_money(ctx.author.id, bet)
    result = random.choice(["ملك", "كتابة"])
    win = result == user_choice

    details = f"Your pick: **{user_choice}** • Result: **{result}**"

    if win:
        payout = bet * 2
        balance = add_money(ctx.author.id, payout)
        embed = gambling_embed(
            "🪙 Coin Flip",
            "✅ **CORRECT PICK** — توقعت صح.",
            COLOR_GREEN,
            ctx.author,
            bet,
            result_amount=bet,
            balance=balance,
            details=details,
            game_name="Coin Flip"
        )
    else:
        balance = get_balance(ctx.author.id)
        embed = gambling_embed(
            "🪙 Coin Flip",
            "❌ **WRONG PICK** — توقعت غلط.",
            COLOR_RED,
            ctx.author,
            bet,
            result_amount=-bet,
            balance=balance,
            details=details,
            game_name="Coin Flip"
        )

    await ctx.send(embed=embed)




@bot.command(name="بلاكجاك", aliases=["blackjack", "bj"])
async def gamble_blackjack(ctx, amount=None):
    bet = await validate_gamble(ctx, amount)
    if bet is None:
        return

    # نسحب الرهان من البداية. إذا فزت يرجع لك الرهان + الربح.
    remove_money(ctx.author.id, bet)

    player_cards = [draw_blackjack_card(), draw_blackjack_card()]
    dealer_cards = [draw_blackjack_card(), draw_blackjack_card()]

    player_blackjack = is_natural_blackjack(player_cards)
    dealer_blackjack = is_natural_blackjack(dealer_cards)

    if player_blackjack or dealer_blackjack:
        if player_blackjack and dealer_blackjack:
            balance = add_money(ctx.author.id, bet)
            embed = build_blackjack_embed(
                ctx.author,
                bet,
                player_cards,
                dealer_cards,
                "🟨 **DOUBLE BLACKJACK** — تعادل، رجع لك الرهان.",
                COLOR_YELLOW,
                finished=True,
                change=0,
                balance=balance,
                hide_dealer=False
            )
            await ctx.send(embed=embed)
            return

        if player_blackjack:
            profit = int(bet * 1.5)
            payout = bet + profit
            balance = add_money(ctx.author.id, payout)
            embed = build_blackjack_embed(
                ctx.author,
                bet,
                player_cards,
                dealer_cards,
                "🔥 **BLACKJACK!** — فزت من أول كرتين. الدفع x1.5",
                COLOR_GREEN,
                finished=True,
                change=profit,
                balance=balance,
                hide_dealer=False
            )
            await ctx.send(embed=embed)
            return

        balance = get_balance(ctx.author.id)
        embed = build_blackjack_embed(
            ctx.author,
            bet,
            player_cards,
            dealer_cards,
            "❌ **DEALER BLACKJACK** — الديلر جاب بلاك جاك.",
            COLOR_RED,
            finished=True,
            change=-bet,
            balance=balance,
            hide_dealer=False
        )
        await ctx.send(embed=embed)
        return

    view = BlackjackView(ctx.author.id, bet, player_cards, dealer_cards)
    embed = build_blackjack_embed(
        ctx.author,
        bet,
        player_cards,
        dealer_cards,
        "🎴 اختر: **Hit** عشان تسحب كرت، أو **Stand** عشان توقف.",
        COLOR_PURPLE,
        finished=False,
        hide_dealer=True
    )
    await ctx.send(embed=embed, view=view)


@bot.command(name="حماية", aliases=["protection"])
@commands.has_permissions(administrator=True)
async def protection(ctx, mode=None):
    global protection_enabled

    if mode is None:
        status = "مفعلة ✅" if protection_enabled else "مطفية ❌"
        await ctx.send(
            embed=discord.Embed(
                title="🛡️ حالة الحماية",
                description=f"الحماية الآن: **{status}**",
                color=COLOR_YELLOW
            )
        )
        return

    if mode in ["تشغيل", "on"]:
        protection_enabled = True
        await ctx.send("🛡️ تم تشغيل الحماية.")

    elif mode in ["ايقاف", "إيقاف", "off"]:
        protection_enabled = False
        await ctx.send("🛡️ تم إيقاف الحماية.")

    else:
        await ctx.send("استخدم: `!حماية تشغيل` أو `!حماية ايقاف`")


@bot.command(name="اعدادات", aliases=["settings"])
@commands.has_permissions(administrator=True)
async def settings(ctx):
    embed = discord.Embed(title="⚙️ إعدادات الحماية", color=COLOR_GREY)
    embed.add_field(name="الحماية", value="مفعلة ✅" if protection_enabled else "مطفية ❌", inline=True)
    embed.add_field(name="Anti-Link", value="شغال ✅" if ANTI_LINKS else "مغلق ❌", inline=True)
    embed.add_field(name="Spam", value=f"{SPAM_LIMIT} رسائل / {SPAM_SECONDS} ثواني", inline=True)
    embed.add_field(name="Mass Mention", value=f"{MASS_MENTION_LIMIT} منشن", inline=True)
    embed.add_field(name="Bypass Users", value=str(len(BYPASS_USER_IDS)), inline=True)

    await ctx.send(embed=embed)


@bot.command(name="تحذير", aliases=["warn"])
@commands.has_permissions(administrator=True)
async def warn(ctx, member: discord.Member, *, reason="بدون سبب"):
    count = add_warning(member, reason, "تحذير يدوي", f"{ctx.author} ({ctx.author.id})")

    embed = discord.Embed(
        title="🚫 تحذير إداري",
        description=f"{member.mention} أخذ تحذير.",
        color=COLOR_YELLOW
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="عدد التحذيرات", value=str(count), inline=True)

    await ctx.send(embed=embed)

    punishment = await apply_punishment(member, ctx.channel, count)

    await send_log(
        ctx.guild,
        "🚫 تحذير إداري",
        f"""
**العضو:** {member.mention}
**بواسطة:** {ctx.author.mention}
**السبب:** {reason}
**الإجراء:** {punishment}
""",
        COLOR_YELLOW,
        log_type="moderation"
    )


@bot.command(name="تحذيرات", aliases=["warnings"])
@commands.has_permissions(administrator=True)
async def warnings_count(ctx, member: discord.Member):
    user_warnings = warnings.get(str(member.id), [])

    if not user_warnings:
        await ctx.send(
            embed=discord.Embed(
                title="✅ لا يوجد تحذيرات",
                description=f"{member.mention} ما عليه تحذيرات.",
                color=COLOR_GREEN
            )
        )
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
async def reset_warnings(ctx, member: discord.Member):
    warnings[str(member.id)] = []
    save_warnings()

    await ctx.send(
        embed=discord.Embed(
            title="✅ تم التصفير",
            description=f"تم تصفير تحذيرات {member.mention}.",
            color=COLOR_GREEN
        )
    )

    await send_log(
        ctx.guild,
        "✅ تصفير تحذيرات",
        f"**بواسطة:** {ctx.author.mention}\n**العضو:** {member.mention}",
        COLOR_GREEN,
        log_type="moderation"
    )


@bot.command(name="مسح", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    await ctx.channel.purge(limit=amount + 1)

    await ctx.send(
        embed=discord.Embed(
            title="🧹 تم المسح",
            description=f"تم حذف **{amount}** رسالة.",
            color=COLOR_GREY
        ),
        delete_after=3
    )

    await send_log(
        ctx.guild,
        "🧹 مسح رسائل",
        f"**بواسطة:** {ctx.author.mention}\n**الروم:** {ctx.channel.mention}\n**العدد:** {amount}",
        COLOR_GREY,
        log_type="message"
    )


@bot.command(name="قفل", aliases=["lock"])
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)

    await ctx.send(
        embed=discord.Embed(
            title="🔒 تم قفل الروم",
            description="تم منع الأعضاء من الكتابة هنا.",
            color=COLOR_RED
        )
    )

    await send_log(
        ctx.guild,
        "🔒 قفل روم",
        f"**بواسطة:** {ctx.author.mention}\n**الروم:** {ctx.channel.mention}",
        COLOR_RED,
        log_type="channel"
    )


@bot.command(name="فتح", aliases=["unlock"])
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)

    await ctx.send(
        embed=discord.Embed(
            title="🔓 تم فتح الروم",
            description="تم السماح للأعضاء بالكتابة هنا.",
            color=COLOR_GREEN
        )
    )

    await send_log(
        ctx.guild,
        "🔓 فتح روم",
        f"**بواسطة:** {ctx.author.mention}\n**الروم:** {ctx.channel.mention}",
        COLOR_GREEN,
        log_type="channel"
    )


@bot.command(name="لوحة", aliases=["panel"])
@commands.has_permissions(administrator=True)
async def panel(ctx):
    embed = discord.Embed(title="🎛️ لوحة NM System", color=COLOR_PURPLE)
    embed.add_field(name="📁 إنشاء لوقات", value="`!انشاء`", inline=True)
    embed.add_field(name="⚙️ إعداد النظام", value="`!اعداد`", inline=True)
    embed.add_field(name="👤 معلومات عضو", value="`!معلومات @user`", inline=True)
    embed.add_field(name="🛡️ الحماية", value="`!حماية`", inline=True)
    embed.add_field(name="📊 اللفل", value="`!ترتيب`", inline=True)
    embed.add_field(name="🎮 لعب", value="`!لعب Valorant 5`", inline=True)
    embed.add_field(name="💡 اقتراح", value="`!اقتراح فكرتك`", inline=True)
    embed.add_field(name="🎭 الرولات", value="`!رولات`", inline=True)
    embed.add_field(name="🎁 سحب", value="`!سحب Nitro 1h 1`", inline=True)
    embed.add_field(name="📢 إعلان", value="`!اعلان نص الإعلان`", inline=True)
    embed.add_field(name="📩 DM", value="معطّل بسبب Discord Quarantine", inline=True)
    
    
    
    embed.add_field(name="📖 مساعدة", value="`!مساعدة`", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="اعلان", aliases=["announce"])
@commands.has_permissions(administrator=True)
async def announce(ctx, *, text=None):
    if not text:
        await ctx.send("استخدم: `!اعلان نص الإعلان`")
        return

    embed = discord.Embed(
        title="📢 Announcement",
        description=text,
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"By {ctx.author}")

    msg = await send_to_channel(
        ctx.guild,
        ANNOUNCEMENTS_CHANNEL_ID,
        embed=embed
    )

    if msg:
        await ctx.message.add_reaction("✅")
    else:
        await ctx.send("❌ ما قدرت أرسل في روم announcements. تأكد من صلاحيات البوت.")

    await send_log(
        ctx.guild,
        "📢 إعلان جديد",
        f"**بواسطة:** {ctx.author.mention}\n**الإعلان:** {clean_text(text, 900)}",
        COLOR_BLUE,
        log_type="server"
    )


@bot.command(name="اعداد", aliases=["setup"])
@commands.has_permissions(administrator=True)
async def setup_posts(ctx):
    guild = ctx.guild

    if not guild or guild.id != GUILD_ID:
        await ctx.send("❌ هذا الأمر يشتغل بس في السيرفر الأساسي.")
        return

    loading = await ctx.send("⚙️ جاري تجهيز الشروحات ولوحة الرولات بدون إنشاء رتب جديدة...")

    try:
        game_roles = await create_or_find_game_roles(guild)

        lfg_embed = discord.Embed(
            title="🎮 Looking For Game",
            description=(
                "هذا الروم مخصص للتجمعات والبحث عن لاعبين.\n\n"
                "تقدر تستخدم أمر التجمع، والبوت بينزل رسالة فيها أزرار.\n"
                "إذا اكتمل العدد، البوت يفتح روم فويس خاص باسم اللعبة.\n"
                "الكل يشوف الروم، لكن الدخول فقط للمسجلين."
            ),
            color=COLOR_GREEN,
            timestamp=discord.utils.utcnow()
        )

        lfg_embed.add_field(
            name="✅ الاستخدام",
            value=(
                "`!لعب Valorant 5 نبي قيم سريع`\n"
                "`!لعب CounterStrike 5 نبي كومب`\n"
                "`!لعب Overwatch 5 نبي رانك`\n"
                "`!لعب ARC-Raiders 3 نبي قيم`"
            ),
            inline=False
        )

        lfg_embed.add_field(
            name="📌 الأزرار",
            value=(
                "🎮 **بدخل**: تدخل التجمع.\n"
                "🚪 **بطلع**: تطلع من التجمع قبل يكتمل.\n"
                "❌ **إلغاء التجمع**: لصاحب التجمع فقط."
            ),
            inline=False
        )

        lfg_embed.set_footer(text="NM System | Looking For Game")

        await send_to_channel(guild, LOOKING_FOR_GAME_CHANNEL_ID, embed=lfg_embed)

        giveaways_embed = discord.Embed(
            title="🎁 Giveaways",
            description="هذا الروم مخصص للسحوبات فقط.",
            color=COLOR_YELLOW,
            timestamp=discord.utils.utcnow()
        )

        giveaways_embed.add_field(
            name="✅ الاستخدام",
            value=(
                "`!سحب Nitro 1h 1`\n"
                "`!سحب Robux 30m 1`\n"
                "`!سحب GiftCard 1d 2`"
            ),
            inline=False
        )

        giveaways_embed.set_footer(text="NM System | Giveaways")

        await send_to_channel(guild, GIVEAWAYS_CHANNEL_ID, embed=giveaways_embed)

        roles_info_embed = discord.Embed(
            title="🎭 Roles",
            description=(
                "هذا الروم مخصص لاختيار رتب الألعاب.\n\n"
                "اضغط على الزر المناسب للعبة، وإذا ضغطت مرة ثانية تنشال منك الرتبة."
            ),
            color=COLOR_PURPLE,
            timestamp=discord.utils.utcnow()
        )

        games_text = ""

        for key, data in GAME_ROLES.items():
            role_id = GAME_ROLE_IDS.get(key)
            role = guild.get_role(int(role_id)) if role_id else None

            if role:
                games_text += f"{data['emoji']} {role.mention}\n"
            else:
                games_text += f"{data['emoji']} {data['name']} - غير موجودة\n"

        roles_info_embed.add_field(name="🎮 الألعاب المتوفرة", value=games_text[:1000], inline=False)
        roles_info_embed.set_footer(text="NM System | Game Roles")

        await send_to_channel(guild, ROLES_CHANNEL_ID, embed=roles_info_embed)

        roles_panel_embed = discord.Embed(
            title="🎮 اختر رتب الألعاب",
            description=(
                "اضغط على الزر عشان تأخذ رتبة اللعبة.\n"
                "اضغط مرة ثانية عشان تشيل الرتبة من نفسك."
            ),
            color=COLOR_BLUE,
            timestamp=discord.utils.utcnow()
        )

        roles_panel_embed.set_footer(text="NM System | Role Panel")

        await send_to_channel(
            guild,
            ROLES_CHANNEL_ID,
            embed=roles_panel_embed,
            view=GameRolesView()
        )

        announcements_embed = discord.Embed(
            title="📢 Announcements",
            description="هذا الروم مخصص للإعلانات الرسمية والمهمة.",
            color=COLOR_BLUE,
            timestamp=discord.utils.utcnow()
        )

        announcements_embed.add_field(name="✅ الاستخدام", value="`!اعلان نص الإعلان`", inline=False)
        announcements_embed.set_footer(text="NM System | Announcements")

        await send_to_channel(guild, ANNOUNCEMENTS_CHANNEL_ID, embed=announcements_embed)

        leave_info_embed = discord.Embed(
            title="🚪 Member Leave Info",
            description=(
                "هذا الروم مخصص لتسجيل تفاصيل خروج الأعضاء.\n\n"
                "إذا عضو طلع، انطرد، أو تبند، البوت ينزل هنا معلوماته كاملة."
            ),
            color=COLOR_RED,
            timestamp=discord.utils.utcnow()
        )

        leave_info_embed.add_field(
            name="📌 المعلومات اللي بتنزل هنا",
            value=(
                "• منشن العضو\n"
                "• اليوزر\n"
                "• User ID\n"
                "• هل خرج بنفسه أو انطرد أو تبند\n"
                "• مين طرده أو بنده\n"
                "• السبب إذا موجود\n"
                "• تاريخ إنشاء الحساب\n"
                "• تاريخ دخوله السيرفر\n"
                "• الرتب اللي كانت معه قبل يطلع"
            ),
            inline=False
        )

        leave_info_embed.set_footer(text="NM System | nm_leave_info")

        await send_to_channel(guild, LEAVE_INFO_CHANNEL_ID, embed=leave_info_embed)

        commands_embed = discord.Embed(
            title="🤖 NM System Commands",
            description="هذي أهم أوامر البوت:",
            color=COLOR_GREY,
            timestamp=discord.utils.utcnow()
        )

        commands_embed.add_field(name="📁 اللوقات", value="`!انشاء`", inline=True)
        commands_embed.add_field(name="⚙️ الإعداد", value="`!اعداد`", inline=True)
        commands_embed.add_field(name="👤 معلومات", value="`!معلومات @user`", inline=True)
        commands_embed.add_field(name="🎮 اللعب", value="`!لعب Valorant 5`", inline=True)
        commands_embed.add_field(name="🎭 الرولات", value="`!رولات`", inline=True)
        commands_embed.add_field(name="📩 الخاص", value="`!dmtest`\n`!dmrole`\n`!dmall`", inline=True)
        commands_embed.add_field(name="📊 اللفل", value="`!لفلي`\n`!ترتيب`", inline=True)

        commands_embed.set_footer(text="NM System | Setup Completed")

        await ctx.send(embed=commands_embed)

        await send_log(
            guild,
            "⚙️ إعداد النظام",
            f"""
**بواسطة:** {ctx.author.mention}
**الأمر:** `!اعداد`

تم:
• استخدام رتب الألعاب الموجودة مسبقًا
• لم يتم إنشاء أي رتبة جديدة
• تنزيل شرح looking-for-game
• تنزيل شرح giveaways
• تنزيل شرح roles
• تنزيل لوحة الرولات
• تنزيل شرح announcements
• تنزيل شرح nm_leave_info
• تجهيز فتح رومات اللعب داخل كاتقوري `{GAME_VOICE_CATEGORY_ID}`

**عدد الرتب الموجودة:** `{len(game_roles)}`
""",
            COLOR_BLUE,
            log_type="server"
        )

        await loading.edit(content="✅ تم تجهيز الشروحات ولوحة الرولات بدون إنشاء رتب جديدة.")

    except Exception as e:
        await loading.edit(content=f"❌ صار خطأ أثناء الإعداد:\n```{e}```")



@bot.command(name="حفظ_الذاكرة", aliases=["backup", "حفظ", "نسخة"])
@commands.has_permissions(administrator=True)
async def backup_memory_command(ctx):
    loading = await ctx.send("💾 جاري حفظ نسخة احتياطية من ذاكرة البوت...")
    ok, message = await create_memory_backup(
        ctx.guild,
        reason="Manual backup command",
        requested_by=ctx.author
    )

    if ok:
        await loading.edit(content=f"✅ {message}")
    else:
        await loading.edit(content=f"❌ {message}")


@bot.command(name="استرجاع_الذاكرة", aliases=["restore", "استرجاع"])
@commands.has_permissions(administrator=True)
async def restore_memory_command(ctx):
    loading = await ctx.send("♻️ جاري استرجاع آخر نسخة احتياطية من الروم...")
    ok, message = await restore_memory_from_backup(ctx.guild, force=True)

    if not ok:
        await loading.edit(content=f"❌ {message}")
        return

    init_db()
    await loading.edit(
        content=(
            f"✅ {message}\n"
            "⚠️ يفضّل تسوي Restart للبوت بعد الاسترجاع عشان كل شيء يقرأ الملفات الجديدة بشكل كامل."
        )
    )


@bot.command(name="حالة_الذاكرة", aliases=["memory", "ذاكرة"])
@commands.has_permissions(administrator=True)
async def memory_status_command(ctx):
    init_db()
    status = local_memory_status()
    text = ""

    for file_name, info in status.items():
        state = "✅ سليم" if info["valid"] else "⚠️ يحتاج فحص"
        size_kb = round(info["size"] / 1024, 2)
        text += f"• `{file_name}` — {state} — `{size_kb} KB`\n"

    embed = discord.Embed(
        title="🧠 Memory Status",
        description=text or "مافي ملفات ذاكرة موجودة حالياً.",
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )
    add_memory_stats_fields(embed)
    embed.add_field(name="📌 روم النسخ", value=f"<#{MEMORY_BACKUP_CHANNEL_ID}>", inline=False)
    embed.add_field(name="⏱️ النسخ التلقائي", value=f"كل {MEMORY_BACKUP_INTERVAL_SECONDS // 60} دقيقة", inline=True)
    embed.add_field(name="🔁 Auto restore", value="إذا قاعدة البيانات ناقصة أو خربانة عند التشغيل", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Memory")

    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("⚠️ هذا الأمر مو مسموح هنا أو ما عندك صلاحية.", delete_after=6)
        return

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ما عندك صلاحية تستخدم هذا الأمر.", delete_after=6)
        return

    if isinstance(error, commands.BadArgument):
        await ctx.send("❌ تأكد من المنشن أو الرقم.", delete_after=6)
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ ناقصك شيء في الأمر. اكتب `!مساعدة`.", delete_after=6)
        return

    print(f"Command Error: {error}")


keep_alive()

while True:
    try:
        bot.run(TOKEN)
    except discord.errors.DiscordServerError as e:
        print(f"Discord login server error: {e}. Retrying in 30 seconds...")
        time.sleep(30)
    except discord.errors.HTTPException as e:
        print(f"Discord HTTP error: {e}. Retrying in 30 seconds...")
        time.sleep(30)
    except Exception as e:
        print(f"Unexpected bot crash: {type(e).__name__}: {e}. Retrying in 30 seconds...")
        time.sleep(30)
