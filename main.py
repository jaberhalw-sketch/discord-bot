import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta
import os
import json
import time
import random
import sqlite3
import tempfile
import zipfile
import re
import html
import asyncio
from pathlib import Path
from flask import Flask, request, redirect, session, render_template_string, jsonify
from threading import Thread
import urllib.parse
import urllib.request
import urllib.error

# =========================
# NM SYSTEM PERSISTENT STORAGE PATCH
# Railway redeploy-safe storage.
# If a Railway Volume is mounted at /data, all important files are stored there.
# If /data does not exist, the bot falls back to the current folder.
# =========================
from pathlib import Path as _NMPath
import os as _nmos
import shutil as _nmshutil
import sqlite3 as _nmsqlite3

NM_DATA_DIR = _NMPath(_nmos.getenv("NM_DATA_DIR", "/data"))
try:
    NM_DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    NM_DATA_DIR = _NMPath(".")

NM_MEMORY_FILES = [
    "nm_system.db",
    "warnings.json",
    "log_channels.json",
    "dashboard_settings.json",
    "protection_settings.json",
    "guild_settings.json",
    "money_audit.json",
]

def nm_data_path(filename: str) -> str:
    return str(NM_DATA_DIR / filename)

def nm_migrate_local_file_to_data(filename: str):
    """Move/copy old local data into /data the first time persistent storage is enabled."""
    try:
        local = _NMPath(filename)
        target = NM_DATA_DIR / filename
        if local.exists() and not target.exists() and local.resolve() != target.resolve():
            _nmshutil.copy2(local, target)
            print(f"✅ Migrated {filename} to persistent storage: {target}")
    except Exception as e:
        print(f"⚠️ Could not migrate {filename} to persistent storage: {e}")

for _nm_file in NM_MEMORY_FILES:
    nm_migrate_local_file_to_data(_nm_file)

# Force common file constants to persistent paths.
DB_FILE = nm_data_path("nm_system.db")
DATABASE_FILE = DB_FILE
DATABASE_PATH = DB_FILE
WARNINGS_FILE = nm_data_path("warnings.json")
LOG_CHANNELS_FILE = nm_data_path("log_channels.json")
DASHBOARD_SETTINGS_FILE = nm_data_path("dashboard_settings.json")
PROTECTION_SETTINGS_FILE = nm_data_path("protection_settings.json")
GUILD_SETTINGS_FILE = nm_data_path("guild_settings.json")
MONEY_AUDIT_FILE = nm_data_path("money_audit.json")

def nm_open_json_path(filename):
    return nm_data_path(filename)

def nm_persistent_sqlite_connect(*args, **kwargs):
    return _nmsqlite3.connect(DB_FILE, check_same_thread=False)



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

DB_FILE = nm_data_path("nm_system.db")
WARNINGS_FILE = nm_data_path("warnings.json")
LOG_CHANNELS_FILE = nm_data_path("log_channels.json")
DASHBOARD_SETTINGS_FILE = nm_data_path("dashboard_settings.json")

PREFIX = "!"

ANTI_LINKS = True
SPAM_LIMIT = 10
SPAM_SECONDS = 5
MASS_MENTION_LIMIT = 8

# Protection dashboard controls
PROTECTION_BAD_WORDS_ENABLED = True
PROTECTION_LINKS_ENABLED = True
PROTECTION_SPAM_ENABLED = True
PROTECTION_MASS_MENTION_ENABLED = True
PROTECTION_DELETE_MESSAGES = True
PROTECTION_TIMEOUTS_ENABLED = True
PROTECTION_BYPASS_ADMINS = True
PROTECTION_LOG_ONLY_MODE = False
PROTECTION_LINK_WHITELIST = []
PROTECTION_IGNORED_CHANNEL_IDS = set()

LEVEL_COOLDOWN = 25
COMMANDS_CHANNEL_ID = 1504067161734516757
MEMORY_BACKUP_CHANNEL_ID = 1504161977063178370
MEMORY_BACKUP_INTERVAL_SECONDS = 60 * 60
ECONOMY_EXPLAIN_INTERVAL_SECONDS = 7 * 60 * 60
ECONOMY_EXPLAIN_CHANNEL_ID = COMMANDS_CHANNEL_ID
ECONOMY_GUIDE_AUTO_ENABLED = True
HOURLY_REWARD_COOLDOWN_SECONDS = 60 * 60
MEMORY_BACKUP_MESSAGE_TAG = "NM_MEMORY_BACKUP_V2"
MEMORY_BACKUP_OLD_TAGS = ["NM_MEMORY_BACKUP_V1", "NM_MEMORY_BACKUP_V2"]
MEMORY_BACKUP_HISTORY_LIMIT = 100
MEMORY_FILES = [DB_FILE, WARNINGS_FILE, LOG_CHANNELS_FILE, DASHBOARD_SETTINGS_FILE]

COIN_NAME = "NM Coin"
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
BOT_BRAND = "NM System"

# =========================
# CUSTOMIZABLE MODULE SETTINGS
# These values can be changed from the dashboard and are saved in dashboard_settings.json.
# =========================
SHOP_CHANNEL_ID = COMMANDS_CHANNEL_ID
EVENTS_CHANNEL_ID = GIVEAWAYS_CHANNEL_ID
BOT_ANNOUNCEMENTS_CHANNEL_ID = GIVEAWAYS_CHANNEL_ID
VIP_ROLE_ID = 0
EVENT_WINNER_ROLE_ID = 0
VIP_ROLE_NAME = "💎 VIP"
EVENT_WINNER_ROLE_NAME = "🏆 Event Winner"
VIP_ROLE_COLOR = 0x7C3AED
EVENT_WINNER_ROLE_COLOR = 0xF59E0B
SHOP_ENABLED = True
EVENTS_ENABLED = True
SHOP_VIP_PRICE = 50000
SHOP_VIP_DAYS = 7
LOOTBOX_PRICE = 10000
LOOTBOX_COOLDOWN_SECONDS = 10
DEFAULT_EVENT_PRIZE = 100000
DEFAULT_EVENT_DURATION_MINUTES = 60
PUBLIC_LEADERBOARD_ENABLED = True

# =========================
# REAL ESTATE EMPIRE SETTINGS
# Limited property system controlled from the market buttons.
# =========================
REAL_ESTATE_ENABLED = True
REAL_ESTATE_RENT_COOLDOWN_SECONDS = 6 * 60 * 60
REAL_ESTATE_SALE_TAX_PERCENT = 5
AUCTION_MINUTES_DEFAULT = 30
auction_task = None

PROPERTY_TYPES = {
    "room": {
        "emoji": "🏚️",
        "name": "Small Room",
        "count": 20,
        "price": 25000,
        "rent": 1000,
        "upgrade_base": 15000,
        "max_level": 5,
    },
    "apartment": {
        "emoji": "🏠",
        "name": "Apartment",
        "count": 10,
        "price": 100000,
        "rent": 5000,
        "upgrade_base": 60000,
        "max_level": 5,
    },
    "office": {
        "emoji": "🏢",
        "name": "Office",
        "count": 5,
        "price": 300000,
        "rent": 18000,
        "upgrade_base": 180000,
        "max_level": 5,
    },
    "tower": {
        "emoji": "🏙️",
        "name": "Tower",
        "count": 2,
        "price": 1000000,
        "rent": 75000,
        "upgrade_base": 650000,
        "max_level": 5,
    },
    "palace": {
        "emoji": "👑",
        "name": "Royal Palace",
        "count": 1,
        "price": 3500000,
        "rent": 250000,
        "upgrade_base": 2000000,
        "max_level": 5,
    },
}

lootbox_cooldowns = {}
timed_roles_task = None

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

# Dashboard permission tiers.
# OWNER = full control over every dashboard page/action.
# ADMIN = limited dashboard access for monitoring + warnings management only.
DASHBOARD_OWNER_ROLE_IDS = {
    int(x.strip())
    for x in os.getenv("DASHBOARD_OWNER_ROLE_IDS", "").split(",")
    if x.strip().isdigit()
}

DASHBOARD_LIMITED_ADMIN_ROLE_IDS = {
    int(x.strip())
    for x in os.getenv("DASHBOARD_LIMITED_ADMIN_ROLE_IDS", os.getenv("DASHBOARD_ADMIN_ROLE_IDS", "")).split(",")
    if x.strip().isdigit()
}

DASHBOARD_OWNER_USER_IDS = {
    int(x.strip())
    for x in os.getenv("DASHBOARD_OWNER_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

# Private dashboard owner exception.
# This is intentionally not shown or editable in the dashboard Admin Access page.
# Keep it here so the main developer/admin can never get locked out even if he is not the Discord server owner.
DASHBOARD_PRIVATE_OWNER_USER_IDS = {1125198908231004191}
DASHBOARD_PRIVATE_OWNER_USERNAMES = {"jbh.1", "jr_7", "d75gxgjm94", "jaber", "jaber hamad"}

# =========================
# ADMIN CONTROL CENTER
# =========================
DEFAULT_SYSTEM_TOGGLES = {
    "utility": True, "admin": True, "economy": True, "levels": True,
    "gambling": True, "protection": True, "lfg": True, "giveaway": True,
    "community": True, "roles": True, "memory": True, "shop": True, "events": True,
}
COMMAND_SYSTEM_MAP = {
    "مساعدة": "utility", "بنق": "utility", "هلا": "utility", "معلومات": "utility", "طقطق": "utility", "تقييم": "utility",
    "انشاء": "admin", "اعداد": "admin", "لوحة": "admin", "اعلان": "admin", "مسح": "admin", "قفل": "admin", "فتح": "admin",
    "اقتراح": "community", "لعب": "lfg", "سحب": "giveaway", "رولات": "roles",
    "لفلي": "levels", "لفل": "levels", "ترتيب": "levels",
    "رصيدي": "economy", "رصيد": "economy", "راتب": "economy", "بوست": "economy", "تحويل": "economy", "اغنى": "economy",
    "اعطاءفلوس": "economy", "سحبفلوس": "economy", "تصفيرفلوس": "economy",
    "متجر": "shop", "شراء": "shop", "صندوق": "shop",
    "عقارات": "shop", "عقاراتي": "shop", "ايجار": "shop", "ملاك": "shop",
    "عرض_عقار": "shop", "سوق_العقارات": "shop", "مزادات": "shop", "مزاد_عقار": "shop",
    "فعاليات": "events", "فعالية": "events",
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
BOT_STARTED_AT = time.time()

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
    return sqlite3.connect(DB_FILE, check_same_thread=False)


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
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            commands_channel_id INTEGER DEFAULT 0,
            gambling_channel_id INTEGER DEFAULT 0,
            logs_category_id INTEGER DEFAULT 0,
            setup_done INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_economy (
            guild_id INTEGER,
            user_id INTEGER,
            balance INTEGER DEFAULT 0,
            last_daily INTEGER DEFAULT 0,
            last_boost_weekly INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_levels (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            PRIMARY KEY (guild_id, user_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_warning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            reason TEXT,
            message TEXT,
            moderator TEXT,
            source TEXT,
            status TEXT DEFAULT 'active',
            created_at INTEGER,
            cleared_at INTEGER DEFAULT 0,
            cleared_by TEXT DEFAULT '',
            clear_reason TEXT DEFAULT ''
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_guild_economy_guild_balance ON guild_economy(guild_id, balance)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_guild_levels_guild_level ON guild_levels(guild_id, level, xp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_guild_warning_history_guild_user ON guild_warning_history(guild_id, user_id)")


    cur.execute("""
        CREATE TABLE IF NOT EXISTS guild_protection_settings (
            guild_id INTEGER PRIMARY KEY,
            settings_json TEXT DEFAULT '{}',
            updated_at INTEGER DEFAULT 0
        )
    """)
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


    cur.execute("""
        CREATE TABLE IF NOT EXISTS money_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            new_balance INTEGER DEFAULT 0,
            source_type TEXT DEFAULT 'system',
            source_label TEXT DEFAULT '',
            admin_id INTEGER DEFAULT 0,
            admin_name TEXT DEFAULT '',
            batch_id TEXT DEFAULT '',
            details TEXT DEFAULT '',
            created_at INTEGER
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_audit_user ON money_audit(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_audit_source ON money_audit(source_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_audit_created ON money_audit(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_audit_batch ON money_audit(batch_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS warning_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reason TEXT,
            message TEXT,
            moderator TEXT,
            source TEXT,
            status TEXT DEFAULT 'active',
            created_at INTEGER,
            cleared_at INTEGER DEFAULT 0,
            cleared_by TEXT DEFAULT '',
            clear_reason TEXT DEFAULT '',
            legacy_key TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS shop_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_key TEXT,
            price INTEGER,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lootbox_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            price INTEGER,
            reward_type TEXT,
            reward_value TEXT,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS timed_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role_id INTEGER,
            expires_at INTEGER,
            reason TEXT,
            active INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_key TEXT,
            title TEXT,
            prize INTEGER,
            starts_at INTEGER,
            ends_at INTEGER,
            created_by INTEGER,
            status TEXT DEFAULT 'active'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS real_estate_properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_key TEXT,
            unit_number INTEGER,
            display_name TEXT,
            owner_id INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            last_rent_claim INTEGER DEFAULT 0,
            for_sale_price INTEGER DEFAULT 0,
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS real_estate_auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER,
            seller_id INTEGER,
            start_price INTEGER,
            highest_bid INTEGER DEFAULT 0,
            highest_bidder INTEGER DEFAULT 0,
            ends_at INTEGER,
            status TEXT DEFAULT 'active',
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS command_center_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            user_id INTEGER DEFAULT 0,
            user_name TEXT DEFAULT '',
            channel_id INTEGER DEFAULT 0,
            channel_name TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            created_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_log_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER DEFAULT 0,
            log_type TEXT DEFAULT 'general',
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            color INTEGER DEFAULT 0,
            discord_channel_id INTEGER DEFAULT 0,
            discord_channel_name TEXT DEFAULT '',
            discord_message_id INTEGER DEFAULT 0,
            deleted_from_discord INTEGER DEFAULT 0,
            deleted_by_id INTEGER DEFAULT 0,
            deleted_by_name TEXT DEFAULT '',
            created_at INTEGER,
            deleted_at INTEGER DEFAULT 0
        )
    """)

    try:
        cur.execute("PRAGMA table_info(dashboard_log_vault)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "guild_id" not in existing_columns:
            cur.execute("ALTER TABLE dashboard_log_vault ADD COLUMN guild_id INTEGER DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_guild_time ON dashboard_log_vault (guild_id, id DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_message ON dashboard_log_vault (discord_message_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_type ON dashboard_log_vault (guild_id, log_type)")
    except Exception as e:
        print(f"Log Vault migration error: {e}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_command_messages (
            message_id INTEGER PRIMARY KEY,
            user_id INTEGER DEFAULT 0,
            command_name TEXT DEFAULT '',
            created_at INTEGER
        )
    """)


    migrate_warnings_json_to_history(cur)

    conn.commit()
    conn.close()
    # Persist SQLite as the source of truth so cleared warnings do not come back after restart.
    rebuild_warnings_json_from_active_history()
    seed_real_estate_properties()
    return

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


def add_money(user_id, amount, source_type="system_earned", admin_id=0, admin_name="", details="", batch_id=""):
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
    cc_record_event("money", user_id=user_id, amount=int(amount), details=details or f"Money added. New balance: {balance}")
    money_audit_record(user_id=user_id, amount=int(amount), new_balance=balance, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=details or f"Money added. New balance: {balance}", batch_id=batch_id)
    return balance


def remove_money(user_id, amount, source_type="system_spend", admin_id=0, admin_name="", details="", batch_id=""):
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
    cc_record_event("money", user_id=user_id, amount=-int(amount), details=details or f"Money removed. New balance: {balance}")
    money_audit_record(user_id=user_id, amount=-int(amount), new_balance=balance, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=details or f"Money removed. New balance: {balance}", batch_id=batch_id)
    return True, balance


def set_balance(user_id, amount, source_type="dashboard_set", admin_id=0, admin_name="", details="", batch_id=""):
    old_balance = get_balance(user_id)
    amount = max(0, int(amount))
    delta = int(amount) - int(old_balance)

    conn = db_connect()
    cur = conn.cursor()
    cur.execute(
        "UPDATE economy SET balance = ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    conn.close()
    cc_record_event("money_set", user_id=user_id, amount=int(delta), details=details or f"Balance set to: {amount}. Delta: {delta}")
    money_audit_record(user_id=user_id, amount=int(delta), new_balance=amount, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=details or f"Balance set from {old_balance} to {amount}. Delta: {delta}", batch_id=batch_id)
    return amount


async def get_all_human_members(guild):
    """Return non-bot members. Tries to chunk the guild first so bulk economy actions hit everyone."""
    if not guild:
        return []

    try:
        await guild.chunk(cache=True)
    except Exception:
        pass

    return [member for member in guild.members if not member.bot]


async def bulk_add_money_to_all(guild, amount, source_type="dashboard_bulk_add", admin_id=0, admin_name=""):
    amount = int(amount)
    if amount <= 0:
        return {"count": 0, "total_added": 0, "members": []}

    members = await get_all_human_members(guild)
    touched = []
    batch_id = f"{source_type}:{int(time.time())}:{random.randint(1000, 9999)}"

    for member in members:
        balance = add_money(member.id, amount, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=f"Bulk economy add by {admin_name or admin_id}. Amount each: {amount}", batch_id=batch_id)
        touched.append((member.id, balance))

    return {
        "count": len(touched),
        "total_added": len(touched) * amount,
        "members": touched,
        "batch_id": batch_id,
    }


async def bulk_remove_money_from_all(guild, amount, source_type="dashboard_bulk_remove", admin_id=0, admin_name=""):
    amount = int(amount)
    if amount <= 0:
        return {"count": 0, "total_removed": 0, "members": []}

    members = await get_all_human_members(guild)
    touched = []
    total_removed = 0
    batch_id = f"{source_type}:{int(time.time())}:{random.randint(1000, 9999)}"

    for member in members:
        current_balance = get_balance(member.id)
        removed = min(current_balance, amount)
        new_balance = max(0, current_balance - amount)
        if removed > 0:
            set_balance(member.id, new_balance, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=f"Bulk economy remove by {admin_name or admin_id}. Requested: {amount}. Removed: {removed}", batch_id=batch_id)
        total_removed += removed
        touched.append((member.id, removed, new_balance))

    return {
        "count": len(touched),
        "total_removed": total_removed,
        "members": touched,
        "batch_id": batch_id,
    }


def claim_daily(user_id, level):
    """Atomic salary claim.
    This prevents double salary claims if the command is triggered twice at the same moment.
    """
    user_id = int(user_id)
    now = int(time.time())
    cooldown = int(HOURLY_REWARD_COOLDOWN_SECONDS)
    reward = int(DAILY_REWARD_BASE + (int(level) * 25))

    # Ensure row exists first.
    get_money_data(user_id)

    conn = db_connect()
    cur = conn.cursor()
    try:
        cur.execute("SELECT balance, last_daily FROM economy WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        balance = int(row[0] or 0) if row else 0
        last_daily = int(row[1] or 0) if row else 0

        if now - last_daily < cooldown:
            conn.close()
            remaining = cooldown - (now - last_daily)
            return False, remaining, balance, 0

        cur.execute("""
            UPDATE economy
            SET balance = balance + ?, last_daily = ?
            WHERE user_id = ? AND (? - COALESCE(last_daily, 0)) >= ?
        """, (reward, now, user_id, now, cooldown))

        if cur.rowcount != 1:
            # Another duplicate command/process claimed it first.
            cur.execute("SELECT balance, last_daily FROM economy WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            balance = int(row[0] or 0) if row else balance
            last_daily = int(row[1] or now) if row else now
            conn.commit()
            conn.close()
            remaining = max(0, cooldown - (now - last_daily))
            return False, remaining, balance, 0

        cur.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        new_balance = int(cur.fetchone()[0] or 0)
        conn.commit()
        conn.close()

        cc_record_event(
            "money",
            user_id=user_id,
            amount=reward,
            details=f"Salary claimed. New balance: {new_balance}"
        )
        money_audit_record(user_id=user_id, amount=reward, new_balance=new_balance, source_type="salary", details=f"Hourly salary claimed. Level: {level}. New balance: {new_balance}")
        return True, 0, new_balance, reward
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        print(f"Salary claim error: {e}")
        balance, _ = get_money_data(user_id)
        return False, cooldown, balance, 0

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

    money_audit_record(user_id=user_id, amount=reward, new_balance=balance, source_type="booster_salary", details=f"Booster weekly reward claimed. New balance: {balance}")

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
        return f"{int(amount):,} {nm_coin_name()}"
    except:
        return f"0 {nm_coin_name()}"


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

    short = f" (`{short_money(value)}`)" if abs(value) >= 100_000 else ""
    if bold:
        return f"{ECONOMY_EMOJI} **{value:,}** {nm_coin_name()}{short}"

    return f"{ECONOMY_EMOJI} {value:,} {nm_coin_name()}{short}"


def money_delta(amount):
    try:
        amount = int(amount)
    except:
        amount = 0

    sign = "+" if amount >= 0 else ""
    icon = "📈" if amount > 0 else "📉" if amount < 0 else "➖"
    return f"{icon} **{sign}{amount:,}** {ECONOMY_EMOJI} {nm_coin_name()}"


def casino_status_line(label, value):
    return f"**{label}:** {value}"


def pretty_casino_box(lines):
    body = "\n".join(lines)
    return f"```ansi\n{body}\n```"


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
        "╭───────────────╮\n"
        "│   NM CASINO   │\n"
        "├───────────────┤\n"
        f"│  {roll[0]}  │  {roll[1]}  │  {roll[2]}  │\n"
        "╰───────────────╯\n"
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
    """Normalize text without joining words together.
    This is intentionally safe for profanity detection:
    - spaces stay as separators
    - punctuation becomes separators
    - single banned words must match full tokens
    - banned phrases must match complete token sequences
    """
    text = str(text or "").lower()

    replacements = {
        "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه", "ڤ": "ف",
        "0": "o", "1": "i", "2": "ء", "3": "ع", "4": "a", "5": "خ", "6": "ط", "7": "ح", "8": "ق", "9": "ص",
        "@": "a", "$": "s", "!": "i",
        "ـ": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Do NOT remove spaces. Anything that is not Arabic/English letters or numbers becomes a separator.
    text = re.sub(r"[^a-z0-9\u0600-\u06FF]+", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_bad_word(content):
    normalized_message = normalize_bad_text(content)
    if not normalized_message:
        return False

    tokens = normalized_message.split()
    token_set = set(tokens)

    for raw_word in bad_words:
        normalized_word = normalize_bad_text(raw_word)
        if not normalized_word:
            continue

        parts = normalized_word.split()

        # Single banned word: exact standalone token only.
        if len(parts) == 1:
            if parts[0] in token_set:
                return True
            continue

        # Banned phrase: complete phrase only, with real separators between words.
        phrase_pattern = r"(?<![\w\u0600-\u06FF])" + r"\s+".join(re.escape(part) for part in parts) + r"(?![\w\u0600-\u06FF])"
        if re.search(phrase_pattern, normalized_message):
            return True

    return False

def is_admin(member):
    return member.guild_permissions.administrator


def is_bypass(member):
    return member.id in BYPASS_USER_IDS or is_admin(member)


def claim_command_message_once(ctx):
    """Prevents the same Discord command message from being executed twice.
    This protects money commands if Discord/Railway delivers the same command twice or two handlers overlap.
    """
    try:
        message_id = int(getattr(ctx.message, "id", 0) or 0)
        if message_id <= 0:
            return True

        command_name = ctx.command.name if getattr(ctx, "command", None) else "unknown"
        now = int(time.time())

        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processed_command_messages (
                message_id INTEGER PRIMARY KEY,
                user_id INTEGER DEFAULT 0,
                command_name TEXT DEFAULT '',
                created_at INTEGER
            )
        """)
        cur.execute(
            "INSERT OR IGNORE INTO processed_command_messages (message_id, user_id, command_name, created_at) VALUES (?, ?, ?, ?)",
            (message_id, int(ctx.author.id), str(command_name), now)
        )
        inserted = cur.rowcount == 1

        # Keep the table small. Message IDs are only needed as a short-term duplicate guard.
        cur.execute("DELETE FROM processed_command_messages WHERE created_at < ?", (now - 86400,))
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        print(f"Command duplicate guard error: {e}")
        return True


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




# =========================
# MULTI-GUILD FOUNDATION / PUBLIC BOT PHASE 1
# =========================

def create_default_guild_settings(guild):
    if not guild:
        return
    try:
        now = int(time.time())
        if int(guild.id) == int(GUILD_ID):
            commands_id = COMMANDS_CHANNEL_ID
            gambling_id = GAMBLING_CHANNEL_ID
            logs_id = LOGS_CATEGORY_ID
            setup_done = 1
        else:
            commands_id = 0
            gambling_id = 0
            logs_id = 0
            setup_done = 0

        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO guild_settings
            (guild_id, guild_name, enabled, commands_channel_id, gambling_channel_id, logs_category_id, setup_done, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
        """, (int(guild.id), str(guild.name)[:180], int(commands_id), int(gambling_id), int(logs_id), int(setup_done), now, now))
        cur.execute("UPDATE guild_settings SET guild_name = ?, updated_at = ? WHERE guild_id = ?", (str(guild.name)[:180], now, int(guild.id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Create guild settings error: {e}")


def get_guild_settings(guild_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT guild_id, guild_name, enabled, commands_channel_id, gambling_channel_id, logs_category_id, setup_done
            FROM guild_settings WHERE guild_id = ?
        """, (int(guild_id),))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "guild_id": int(row[0]),
                "guild_name": row[1] or "",
                "enabled": bool(row[2]),
                "commands_channel_id": int(row[3] or 0),
                "gambling_channel_id": int(row[4] or 0),
                "logs_category_id": int(row[5] or 0),
                "setup_done": bool(row[6]),
            }
    except Exception as e:
        print(f"Get guild settings error: {e}")

    return {
        "guild_id": int(guild_id or 0),
        "guild_name": "",
        "enabled": True,
        "commands_channel_id": 0,
        "gambling_channel_id": 0,
        "logs_category_id": 0,
        "setup_done": False,
    }


def get_effective_commands_channel_id(guild_id):
    settings = get_guild_settings(guild_id)
    if int(guild_id) == int(GUILD_ID) and not settings.get("commands_channel_id"):
        return COMMANDS_CHANNEL_ID
    return int(settings.get("commands_channel_id") or 0)


def get_effective_gambling_channel_id(guild_id):
    settings = get_guild_settings(guild_id)
    if int(guild_id) == int(GUILD_ID) and not settings.get("gambling_channel_id"):
        return GAMBLING_CHANNEL_ID
    return int(settings.get("gambling_channel_id") or 0)


def is_guild_enabled(guild_id):
    if not guild_id:
        return False
    return bool(get_guild_settings(guild_id).get("enabled", True))


async def interaction_channel_check(interaction, channel_id, label="الأوامر"):
    if not interaction.guild:
        await interaction.response.send_message("❌ هذا الأمر يشتغل داخل السيرفر فقط.", ephemeral=True)
        return False

    if not is_guild_enabled(interaction.guild.id):
        await interaction.response.send_message("❌ البوت غير مفعل في هذا السيرفر.", ephemeral=True)
        return False

    if channel_id and interaction.channel and interaction.channel.id != int(channel_id):
        await interaction.response.send_message(f"📍 استخدم {label} هنا: <#{int(channel_id)}>", ephemeral=True)
        return False

    return True


# =========================
# GLOBAL V3 MULTI-GUILD DATA HELPERS
# Slash commands use these tables so each server has independent economy/level data.
# Old ! commands are kept for the main guild as a compatibility layer.
# =========================

def v3_guild_id_from_interaction(interaction):
    return int(interaction.guild.id) if interaction and interaction.guild else 0


def v3_ensure_guild_user(guild_id, user_id):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO guild_economy (guild_id, user_id, balance, last_daily, last_boost_weekly) VALUES (?, ?, 0, 0, 0)", (guild_id, user_id))
    cur.execute("INSERT OR IGNORE INTO guild_levels (guild_id, user_id, xp, level) VALUES (?, ?, 0, 1)", (guild_id, user_id))
    conn.commit()
    conn.close()


def v3_get_money_data(guild_id, user_id):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    v3_ensure_guild_user(guild_id, user_id)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT balance, last_daily FROM guild_economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    conn.close()
    return (int(row[0] or 0), int(row[1] or 0)) if row else (0, 0)


def v3_get_balance(guild_id, user_id):
    return v3_get_money_data(guild_id, user_id)[0]


def v3_set_balance(guild_id, user_id, amount, source_type="v3_set", admin_id=0, admin_name="", details="", batch_id=""):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    amount = max(0, int(amount or 0))
    v3_ensure_guild_user(guild_id, user_id)
    old_balance = v3_get_balance(guild_id, user_id)
    delta = amount - old_balance
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE guild_economy SET balance = ? WHERE guild_id = ? AND user_id = ?", (amount, guild_id, user_id))
    conn.commit()
    conn.close()
    try:
        cc_record_event("money_set", user_id=user_id, amount=delta, details=f"Guild {guild_id} | {details or 'V3 balance set'}")
        money_audit_record(user_id=user_id, amount=delta, new_balance=amount, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=f"Guild {guild_id} | {details or 'V3 balance set'}", batch_id=batch_id)
    except Exception:
        pass
    return amount


def v3_add_money(guild_id, user_id, amount, source_type="v3_system_earned", admin_id=0, admin_name="", details="", batch_id=""):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    amount = int(amount or 0)
    balance, _ = v3_get_money_data(guild_id, user_id)
    balance = max(0, balance + amount)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE guild_economy SET balance = ? WHERE guild_id = ? AND user_id = ?", (balance, guild_id, user_id))
    conn.commit()
    conn.close()
    try:
        cc_record_event("money", user_id=user_id, amount=amount, details=f"Guild {guild_id} | {details or 'V3 money added'}")
        money_audit_record(user_id=user_id, amount=amount, new_balance=balance, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=f"Guild {guild_id} | {details or 'V3 money added'}", batch_id=batch_id)
    except Exception:
        pass
    return balance


def v3_remove_money(guild_id, user_id, amount, source_type="v3_system_spend", admin_id=0, admin_name="", details="", batch_id=""):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    amount = int(amount or 0)
    if amount <= 0:
        return False, v3_get_balance(guild_id, user_id)
    balance, _ = v3_get_money_data(guild_id, user_id)
    if balance < amount:
        return False, balance
    balance -= amount
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE guild_economy SET balance = ? WHERE guild_id = ? AND user_id = ?", (balance, guild_id, user_id))
    conn.commit()
    conn.close()
    try:
        cc_record_event("money", user_id=user_id, amount=-amount, details=f"Guild {guild_id} | {details or 'V3 money removed'}")
        money_audit_record(user_id=user_id, amount=-amount, new_balance=balance, source_type=source_type, admin_id=admin_id, admin_name=admin_name, details=f"Guild {guild_id} | {details or 'V3 money removed'}", batch_id=batch_id)
    except Exception:
        pass
    return True, balance


def v3_get_level_data(guild_id, user_id):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    v3_ensure_guild_user(guild_id, user_id)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT xp, level FROM guild_levels WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    conn.close()
    return (int(row[0] or 0), int(row[1] or 1)) if row else (0, 1)


def v3_add_xp(guild_id, user_id, amount):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    xp, level = v3_get_level_data(guild_id, user_id)
    xp += int(amount or 0)
    needed = level * 100
    leveled_up = False
    while xp >= needed:
        xp -= needed
        level += 1
        needed = level * 100
        leveled_up = True
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("UPDATE guild_levels SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?", (xp, level, guild_id, user_id))
    conn.commit()
    conn.close()
    return xp, level, leveled_up


def v3_get_top_money(guild_id, limit=10):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, balance
        FROM guild_economy
        WHERE guild_id = ?
        ORDER BY balance DESC
        LIMIT ?
    """, (int(guild_id or 0), int(limit)))
    rows = cur.fetchall()
    conn.close()
    return rows


def v3_get_top_levels(guild_id, limit=10):
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, xp, level
        FROM guild_levels
        WHERE guild_id = ?
        ORDER BY level DESC, xp DESC
        LIMIT ?
    """, (int(guild_id or 0), int(limit)))
    rows = cur.fetchall()
    conn.close()
    return rows


def v3_get_money_rank(guild_id, user_id):
    try:
        guild_id = int(guild_id or 0)
        user_id = int(user_id or 0)
        v3_ensure_guild_user(guild_id, user_id)
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) + 1
            FROM guild_economy
            WHERE guild_id = ? AND balance > (
                SELECT balance FROM guild_economy WHERE guild_id = ? AND user_id = ?
            )
        """, (guild_id, guild_id, user_id))
        rank = int(cur.fetchone()[0] or 1)
        conn.close()
        return rank
    except Exception:
        return None


def v3_claim_salary(guild_id, user_id, level):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    now = int(time.time())
    reward = DAILY_REWARD_BASE + (int(level or 1) * 25)
    cooldown = HOURLY_REWARD_COOLDOWN_SECONDS
    v3_ensure_guild_user(guild_id, user_id)
    conn = db_connect()
    cur = conn.cursor()
    cur.execute("SELECT balance, last_daily FROM guild_economy WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    row = cur.fetchone()
    balance = int(row[0] or 0) if row else 0
    last_daily = int(row[1] or 0) if row else 0
    if now - last_daily < cooldown:
        conn.close()
        return False, cooldown - (now - last_daily), balance, 0
    balance += reward
    cur.execute("UPDATE guild_economy SET balance = ?, last_daily = ? WHERE guild_id = ? AND user_id = ?", (balance, now, guild_id, user_id))
    conn.commit()
    conn.close()
    try:
        cc_record_event("money", user_id=user_id, amount=reward, details=f"Guild {guild_id} | V3 salary claimed")
        money_audit_record(user_id=user_id, amount=reward, new_balance=balance, source_type="v3_salary", details=f"Guild {guild_id} | Salary")
    except Exception:
        pass
    return True, 0, balance, reward


def v3_parse_bet_amount(amount):
    try:
        if isinstance(amount, int):
            return int(amount)
        return parse_bet_amount(str(amount))
    except Exception:
        return None


async def v3_require_commands_interaction(interaction):
    return await interaction_channel_check(interaction, get_effective_commands_channel_id(interaction.guild.id if interaction.guild else 0), "روم الأوامر")


async def v3_require_gambling_interaction(interaction):
    return await interaction_channel_check(interaction, get_effective_gambling_channel_id(interaction.guild.id if interaction.guild else 0), "روم القمار")


def v3_wallet_embed(guild_id, target):
    balance_amount = v3_get_balance(guild_id, target.id)
    xp, level_num = v3_get_level_data(guild_id, target.id)
    needed = level_num * 100
    salary_bonus = DAILY_REWARD_BASE + (int(level_num) * 25)
    rank = v3_get_money_rank(guild_id, target.id)
    progress = clean_bar(xp / needed if needed else 0, 14)
    embed = discord.Embed(
        title=f"{ECONOMY_EMOJI} Wallet",
        description=f"**محفظة {target.mention}**\n`{progress}` **{xp:,}/{needed:,} XP**",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{target.display_name} • Wallet", icon_url=target.display_avatar.url)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="💼 الرصيد", value=coin_line(balance_amount), inline=False)
    embed.add_field(name="🏆 ترتيب الغنى", value=f"**#{rank}**" if rank else "غير معروف", inline=True)
    embed.add_field(name="🏅 اللفل", value=f"**{level_num}**", inline=True)
    embed.add_field(name="💸 الراتب القادم", value=coin_line(salary_bonus), inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Global V3")
    return embed


def v3_shop_embed(guild_id, member=None):
    embed = discord.Embed(
        title="🛒 Global V3 Shop",
        description="المتجر العالمي التجريبي. كل سيرفر له اقتصاد مستقل. بعض المشتريات المتقدمة تبقى على نظام ! مؤقتًا إلى حين نقل المتجر بالكامل.",
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💎 VIP", value=f"السعر: {coin_line(SHOP_VIP_PRICE)}\nالمدة: **{SHOP_VIP_DAYS} أيام**\nاستخدم: `/buy item:vip`", inline=False)
    embed.add_field(name="🎁 Lootbox", value=f"السعر: {coin_line(LOOTBOX_PRICE)}\nاستخدم: `/lootbox`", inline=False)
    if member:
        embed.set_author(name=f"{member.display_name} • Wallet", icon_url=member.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(v3_get_balance(guild_id, member.id)), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} • Global V3 Shop")
    return embed

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

    # يمنع تنفيذ نفس رسالة القمار مرتين، عشان ما ينخصم الرهان مرتين.
    if not claim_command_message_once(ctx):
        return None

    amount = parse_bet_amount(amount_text)

    if amount is None:
        embed = discord.Embed(
            title="🎰 مبلغ غير صحيح",
            description="اكتب مبلغ واضح مثل: `/حظ 500` أو `/حظ 10k` أو `/حظ 1m`",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} • NM Casino")
        await ctx.send(embed=embed, delete_after=10)
        return None

    if amount <= 0:
        embed = discord.Embed(
            title="❌ رهان مرفوض",
            description="مبلغ الرهان لازم يكون أكبر من صفر.",
            color=COLOR_RED,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} • NM Casino")
        await ctx.send(embed=embed, delete_after=8)
        return None

    ok, remaining = can_gamble_now(ctx.author.id)

    if not ok:
        embed = discord.Embed(
            title="⏳ انتظر شوي",
            description=f"باقي **{remaining:.1f} ثانية** قبل محاولة القمار التالية.",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} • Cooldown {GAMBLE_COOLDOWN_SECONDS}s")
        await ctx.send(embed=embed, delete_after=4)
        return None

    balance = get_balance(ctx.author.id)

    if balance < amount:
        missing = amount - balance
        embed = discord.Embed(
            title="❌ رصيدك ما يكفي",
            description="ما تقدر تدخل برهان أعلى من الموجود في محفظتك.",
            color=COLOR_RED,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{ctx.author.display_name} • Wallet Check", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="💼 محفظتك", value=coin_line(balance), inline=True)
        embed.add_field(name="🎯 الرهان", value=coin_line(amount), inline=True)
        embed.add_field(name="📉 الناقص", value=coin_line(missing), inline=False)
        embed.set_footer(text=f"{BOT_BRAND} • NM Casino")
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

    embed.set_author(name=f"{member.display_name} • NM Casino", icon_url=member.display_avatar.url)
    embed.add_field(name="🎯 الرهان", value=coin_line(bet), inline=True)

    if result_amount is not None:
        embed.add_field(name="💸 النتيجة", value=money_delta(result_amount), inline=True)

    if balance is not None:
        embed.add_field(name="💼 الرصيد الجديد", value=coin_line(balance), inline=False)

    if details:
        embed.add_field(name="📌 تفاصيل اللعبة", value=details, inline=False)

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
    level_users = nm_db_table_count("levels")
    economy_users = nm_db_table_count("economy")
    total_coins = nm_db_sum_column("economy", "balance")
    warning_users = safe_len_json(WARNINGS_FILE)
    log_channels_saved = safe_len_json(LOG_CHANNELS_FILE)

    lines = []
    lines.append("```txt")
    lines.append("NM SYSTEM MEMORY REPORT")
    lines.append("----------------------------")
    lines.append(f"Level users      : {level_users}")
    lines.append(f"Economy users    : {economy_users}")
    lines.append(f"Total coins      : {total_coins:,} {nm_coin_name()}")
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
    level_users = nm_db_table_count("levels")
    economy_users = nm_db_table_count("economy")
    total_coins = nm_db_sum_column("economy", "balance")
    warning_users = safe_len_json(WARNINGS_FILE)
    log_channels_saved = safe_len_json(LOG_CHANNELS_FILE)

    embed.add_field(
        name="📊 اللفل والاقتصاد",
        value=(
            f"**Level users:** `{level_users}`\n"
            f"**Economy users:** `{economy_users}`\n"
            f"**Total coins:** `{total_coins:,}` {nm_coin_name()}"
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
    """Premium-looking economy guide embed focused on the new slash commands."""
    title = "🪙 NM System Guide"
    description = (
        f"**الدليل الرسمي للأوامر الجديدة في {BOT_BRAND}.**\n"
        "استخدم أوامر `/` لأنها أوضح، أسرع، وتشتغل بشكل أفضل مع النسخة العالمية.\n"
        f"الأوامر العامة في <#{COMMANDS_CHANNEL_ID}>، والكازينو في <#{GAMBLING_CHANNEL_ID}>."
    )

    if auto:
        title = "🪙 NM System • Quick Guide"
        description = (
            "تذكير سريع بالأوامر الجديدة.\n"
            "استخدم أوامر `/` بدل أوامر `!` القديمة.\n"
            f"الأوامر العامة: <#{COMMANDS_CHANNEL_ID}> • الكازينو: <#{GAMBLING_CHANNEL_ID}>"
        )

    embed = discord.Embed(
        title=title,
        description=description,
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="💼 المحفظة والفلوس",
        value=(
            "`/رصيدي` أو `/balance` — عرض رصيدك\n"
            "`/اغنى` أو `/top` — توب أغنى الأعضاء\n"
            "`/تحويل user amount` أو `/transfer` — تحويل فلوس لعضو\n"
            f"**العملة:** {nm_coin_name()}"
        ),
        inline=False
    )

    embed.add_field(
        name="⏱️ الراتب",
        value=(
            f"`/راتب` أو `/salary` — تستلم راتبك كل **{format_seconds(HOURLY_REWARD_COOLDOWN_SECONDS)}**\n"
            "كل ما ارتفع لفلك، تزيد مكافأتك."
        ),
        inline=True
    )

    embed.add_field(
        name="📊 اللفل",
        value=(
            "`/لفلي` أو `/rank` — عرض لفلك و XP\n"
            "`/ترتيب` أو `/levels` — توب اللفلات"
        ),
        inline=True
    )

    embed.add_field(
        name="🎰 الكازينو",
        value=(
            f"يشتغل فقط في <#{GAMBLING_CHANNEL_ID}>\n"
            "`/حظ amount` أو `/luck` — 50/50\n"
            "`/دبل amount` أو `/double` — مخاطرة أعلى\n"
            "`/سلوت amount` أو `/slot` — سلوت وجوائز\n"
            "`/وجه amount choice` أو `/flip` — ملك/كتابة\n"
            "`/بلاكجاك amount` أو `/blackjack` — ضد الديلر"
        ),
        inline=False
    )

    embed.add_field(
        name="🛒 المتجر والجوائز",
        value=(
            "`/متجر` أو `/shop` — عرض المتجر\n"
            "`/شراء item` أو `/buy` — شراء منتج\n"
            "`/صندوق` أو `/lootbox` — فتح صندوق حظ\n"
            "الـ VIP وجوائز الفعاليات مربوطة بالنظام."
        ),
        inline=False
    )

    embed.add_field(
        name="🌍 إعداد السيرفر",
        value=(
            "`/setup_status` — يعرض حالة إعداد السيرفر الحالي\n"
            "كل سيرفر له روماته وإعداداته الخاصة من الداشبورد."
        ),
        inline=False
    )

    embed.add_field(
        name="📌 ملاحظة مهمة",
        value=(
            "أوامر `!` القديمة باقية مؤقتًا لسيرفرك الأساسي، لكن الشرح الرسمي من الآن يعتمد أوامر `/`.\n"
            "إذا ما ظهر لك أمر `/` سو Refresh للديسكورد أو استخدم `!syncslash` للـ Owner."
        ),
        inline=False
    )

    embed.set_footer(text=f"{BOT_BRAND} • Slash Commands • Global V3")
    return embed

def economy_guide_last_sent_key():
    return "ECONOMY_GUIDE_LAST_SENT_AT"


def economy_guide_last_sent_at():
    try:
        return int(get_dashboard_setting(economy_guide_last_sent_key(), 0) or 0)
    except:
        return 0


def economy_guide_mark_sent():
    try:
        dashboard_merge_settings({economy_guide_last_sent_key(): int(time.time())})
    except Exception as e:
        print(f"Economy guide timestamp save error: {e}")


async def economy_explain_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(60)

    while not bot.is_closed():
        try:
            if not ECONOMY_GUIDE_AUTO_ENABLED:
                await asyncio.sleep(300)
                continue

            now = int(time.time())
            last_sent = economy_guide_last_sent_at()
            remaining = int(ECONOMY_EXPLAIN_INTERVAL_SECONDS) - (now - last_sent)

            # Important: do not send immediately after every Railway redeploy/restart.
            if last_sent > 0 and remaining > 0:
                await asyncio.sleep(min(max(remaining, 60), 3600))
                continue

            # First time only: wait one full interval instead of spamming right after deploy.
            if last_sent <= 0:
                economy_guide_mark_sent()
                await asyncio.sleep(min(max(int(ECONOMY_EXPLAIN_INTERVAL_SECONDS), 300), 3600))
                continue

            guild = bot.get_guild(GUILD_ID)
            if guild:
                channel = await get_channel_by_id(guild, ECONOMY_EXPLAIN_CHANNEL_ID)
                if channel:
                    await channel.send(embed=build_economy_guide_embed(auto=True))
                    economy_guide_mark_sent()

        except Exception as e:
            print(f"Auto economy guide error: {e}")

        await asyncio.sleep(min(max(int(ECONOMY_EXPLAIN_INTERVAL_SECONDS), 300), 3600))

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

    # Multi-guild fallback: find the standard log channel name inside the current guild.
    # This makes logs keep working even when the guild-specific channel IDs are not stored globally.
    standard_name = LOG_CHANNEL_NAMES.get(log_type)
    if standard_name:
        channel = discord.utils.get(guild.text_channels, name=standard_name)
        if channel:
            return channel

    names = ["logs", "log", "audit-log", "audit-logs", "لوق", "لوقات"]

    for channel in guild.text_channels:
        if channel.name.lower() in names:
            return channel

    return None



# =========================
# DASHBOARD LOG VAULT
# Keeps an independent copy of every Discord log inside the dashboard.
# If someone deletes the Discord log message, the dashboard copy stays saved.
# =========================

LOG_VAULT_LIMIT = 12000


def log_vault_ensure_table(cur=None):
    close_conn = False
    conn = None
    if cur is None:
        conn = db_connect()
        cur = conn.cursor()
        close_conn = True

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_log_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER DEFAULT 0,
            log_type TEXT DEFAULT 'general',
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            color INTEGER DEFAULT 0,
            discord_channel_id INTEGER DEFAULT 0,
            discord_channel_name TEXT DEFAULT '',
            discord_message_id INTEGER DEFAULT 0,
            deleted_from_discord INTEGER DEFAULT 0,
            deleted_by_id INTEGER DEFAULT 0,
            deleted_by_name TEXT DEFAULT '',
            created_at INTEGER,
            deleted_at INTEGER DEFAULT 0
        )
    """)

    try:
        cur.execute("PRAGMA table_info(dashboard_log_vault)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "guild_id" not in existing_columns:
            cur.execute("ALTER TABLE dashboard_log_vault ADD COLUMN guild_id INTEGER DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_guild_time ON dashboard_log_vault (guild_id, id DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_message ON dashboard_log_vault (discord_message_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_vault_type ON dashboard_log_vault (guild_id, log_type)")
    except Exception as e:
        print(f"Log Vault migration error: {e}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS processed_command_messages (
            message_id INTEGER PRIMARY KEY,
            user_id INTEGER DEFAULT 0,
            command_name TEXT DEFAULT '',
            created_at INTEGER
        )
    """)


    if close_conn and conn:
        conn.commit()
        conn.close()


def log_vault_color_value(color):
    try:
        return int(getattr(color, "value", int(color)))
    except Exception:
        return 0


def log_vault_record(log_type, title, description, color=0, guild_id=0):
    if not guild_id:
        guild_id = nm_safe_int(globals().get('CURRENT_LOG_GUILD_ID', 0) or GUILD_ID, GUILD_ID)
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        cur.execute("""
            INSERT INTO dashboard_log_vault
            (guild_id, log_type, title, description, color, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            int(guild_id or 0),
            str(log_type or "general")[:80],
            str(title or "")[:220],
            str(description or "")[:5000],
            int(log_vault_color_value(color)),
            int(time.time())
        ))
        vault_id = int(cur.lastrowid)
        cur.execute("""
            DELETE FROM dashboard_log_vault
            WHERE id NOT IN (
                SELECT id FROM dashboard_log_vault
                ORDER BY id DESC
                LIMIT ?
            )
        """, (LOG_VAULT_LIMIT,))
        conn.commit()
        conn.close()
        return vault_id
    except Exception as e:
        print(f"Log Vault record error: {e}")
        return None


def log_vault_attach_discord_message(vault_id, channel_id=0, channel_name="", message_id=0):
    if not vault_id:
        return
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        cur.execute("""
            UPDATE dashboard_log_vault
            SET discord_channel_id = ?, discord_channel_name = ?, discord_message_id = ?
            WHERE id = ?
        """, (int(channel_id or 0), str(channel_name or "")[:120], int(message_id or 0), int(vault_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Log Vault attach error: {e}")


def log_vault_mark_deleted(message_id, deleted_by_id=0, deleted_by_name="Unknown"):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        cur.execute("""
            SELECT id, deleted_from_discord
            FROM dashboard_log_vault
            WHERE discord_message_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (int(message_id or 0),))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        if int(row[1] or 0) == 1:
            conn.close()
            return False
        cur.execute("""
            UPDATE dashboard_log_vault
            SET deleted_from_discord = 1,
                deleted_by_id = ?,
                deleted_by_name = ?,
                deleted_at = ?
            WHERE id = ?
        """, (int(deleted_by_id or 0), str(deleted_by_name or "Unknown")[:120], int(time.time()), int(row[0])))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Log Vault mark deleted error: {e}")
        return False


def log_vault_is_known_message(message_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        cur.execute("SELECT id FROM dashboard_log_vault WHERE discord_message_id = ? LIMIT 1", (int(message_id or 0),))
        row = cur.fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def log_vault_is_log_channel(channel):
    try:
        if not channel:
            return False
        channel_id = int(getattr(channel, "id", 0) or 0)
        channel_name = str(getattr(channel, "name", "") or "").lower().strip()
        if channel_id in cc_log_channel_ids():
            return True
        if channel_name in cc_log_channel_names():
            return True
        return False
    except Exception:
        return False


async def log_vault_deleted_by_from_audit(guild, bot_message_author_id=None):
    try:
        async for entry in guild.audit_logs(limit=8, action=discord.AuditLogAction.message_delete):
            # Discord audit logs for message delete normally target the author whose message was deleted.
            if bot_message_author_id and entry.target and getattr(entry.target, "id", None) != bot_message_author_id:
                continue
            if (discord.utils.utcnow() - entry.created_at).total_seconds() > 20:
                continue
            return entry.user
    except Exception:
        return None
    return None



def log_vault_type_meta(log_type):
    key = str(log_type or "general").lower().strip()
    meta = {
        "message": ("💬", "Message"),
        "member": ("👥", "Member"),
        "moderation": ("🛡️", "Moderation"),
        "role": ("🎭", "Roles"),
        "channel": ("#️⃣", "Channels"),
        "voice": ("🎙️", "Voice"),
        "server": ("🏠", "Server"),
        "game": ("🎮", "Game"),
        "giveaway": ("🎁", "Giveaway"),
        "economy": ("🪙", "Economy"),
        "discord_log": ("📦", "Discord Log"),
        "general": ("📌", "General"),
        "protection": ("🛡️", "Protection"),
    }
    for prefix, value in meta.items():
        if key == prefix or key.startswith(prefix):
            return value
    return "📄", str(log_type or "general").replace("_", " ").title()


def log_vault_short_text(text, limit=240):
    text = str(text or "").replace("\r", " ").strip()
    text = re.sub(r"\n{2,}", "\n", text)
    one_line = re.sub(r"\s+", " ", text)
    if len(one_line) > limit:
        return one_line[:limit].rstrip() + "..."
    return one_line or "No details"


def log_vault_recent(guild_id=0, limit=80, offset=0, log_type="all", query="", deleted_filter="all", channel_id="all"):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        clauses = []
        params = []
        if int(guild_id or 0):
            clauses.append("(guild_id = ? OR guild_id = 0)")
            params.append(int(guild_id))
        if log_type and log_type != "all":
            clauses.append("log_type = ?")
            params.append(str(log_type))
        if channel_id and str(channel_id) != "all":
            try:
                clauses.append("discord_channel_id = ?")
                params.append(int(channel_id))
            except Exception:
                pass
        if deleted_filter == "deleted":
            clauses.append("deleted_from_discord = 1")
        elif deleted_filter == "active":
            clauses.append("deleted_from_discord = 0")
        if query:
            clauses.append("(title LIKE ? OR description LIKE ? OR discord_channel_name LIKE ? OR deleted_by_name LIKE ? OR log_type LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like, like, like])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur.execute(f"""
            SELECT id, guild_id, log_type, title, description, discord_channel_id, discord_channel_name,
                   discord_message_id, deleted_from_discord, deleted_by_id, deleted_by_name, created_at, deleted_at
            FROM dashboard_log_vault
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, tuple(params + [int(limit), int(offset)]))
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where}", tuple(params))
        total_matches = int(cur.fetchone()[0] or 0)
        conn.close()
        return rows, total_matches
    except Exception as e:
        print(f"Log Vault recent error: {e}")
        return [], 0


def log_vault_counts(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        where = ""
        params = []
        if int(guild_id or 0):
            where = "WHERE (guild_id = ? OR guild_id = 0)"
            params.append(int(guild_id))
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where}", tuple(params))
        total = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where + (' AND' if where else 'WHERE')} deleted_from_discord = 1", tuple(params))
        deleted = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(DISTINCT log_type) FROM dashboard_log_vault {where}", tuple(params))
        types = int(cur.fetchone()[0] or 0)
        since = int(time.time()) - 86400
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where + (' AND' if where else 'WHERE')} created_at >= ?", tuple(params + [since]))
        today = int(cur.fetchone()[0] or 0)
        conn.close()
        return total, deleted, types, today
    except Exception as e:
        print(f"Log Vault counts error: {e}")
        return 0, 0, 0, 0


def log_vault_types(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        where = ""
        params = []
        if int(guild_id or 0):
            where = "WHERE (guild_id = ? OR guild_id = 0)"
            params.append(int(guild_id))
        cur.execute(f"SELECT log_type, COUNT(*) FROM dashboard_log_vault {where} GROUP BY log_type ORDER BY COUNT(*) DESC")
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def log_vault_top_channels(guild_id=0, limit=8):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        where = "WHERE discord_channel_name != ''"
        params = []
        if int(guild_id or 0):
            where += " AND (guild_id = ? OR guild_id = 0)"
            params.append(int(guild_id))
        cur.execute(f"""
            SELECT discord_channel_name, COUNT(*)
            FROM dashboard_log_vault
            {where}
            GROUP BY discord_channel_name
            ORDER BY COUNT(*) DESC
            LIMIT ?
        """, tuple(params + [int(limit)]))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def log_vault_channels(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        clauses = ["discord_channel_id != 0"]
        params = []
        if int(guild_id or 0):
            clauses.append("(guild_id = ? OR guild_id = 0)")
            params.append(int(guild_id))
        where = "WHERE " + " AND ".join(clauses)
        cur.execute(f"""
            SELECT discord_channel_id, COALESCE(NULLIF(discord_channel_name, ''), 'unknown') AS name,
                   COUNT(*) AS total,
                   SUM(CASE WHEN deleted_from_discord = 1 THEN 1 ELSE 0 END) AS deleted_total,
                   MAX(created_at) AS last_time
            FROM dashboard_log_vault
            {where}
            GROUP BY discord_channel_id, name
            ORDER BY last_time DESC, total DESC
        """, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Log Vault channels error: {e}")
        return []



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

    vault_id = log_vault_record(log_type, title, description, color, guild_id=getattr(guild, "id", 0))

    try:
        sent_message = await channel.send(embed=embed)
        log_vault_attach_discord_message(
            vault_id,
            channel_id=getattr(channel, "id", 0),
            channel_name=getattr(channel, "name", ""),
            message_id=getattr(sent_message, "id", 0)
        )
        cc_record_event(
            "discord_log",
            guild_id=getattr(guild, "id", GUILD_ID),
            channel_id=getattr(channel, "id", 0),
            channel_name=getattr(channel, "name", ""),
            details=f"{log_type} | {title}"
        )
    except Exception as e:
        if vault_id:
            log_vault_attach_discord_message(vault_id, 0, "SEND_FAILED", 0)
        print(f"Send log error: {e}")


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


def warning_time_to_unix(time_text=None):
    if not time_text:
        return int(time.time())
    try:
        return int(time.mktime(time.strptime(str(time_text).replace(" UTC", ""), "%Y-%m-%d %H:%M:%S")))
    except:
        return int(time.time())


def make_warning_legacy_key(user_id, reason, message_text, created_at):
    raw = f"{int(user_id)}|{created_at}|{str(reason)[:120]}|{str(message_text)[:180]}"
    return raw[:500]


def migrate_warnings_json_to_history(cur=None):
    close_conn = False
    conn = None
    if cur is None:
        conn = db_connect()
        cur = conn.cursor()
        close_conn = True
    try:
        if not isinstance(warnings, dict):
            return
        for user_id, items in warnings.items():
            if not isinstance(items, list):
                continue
            for warn_data in items:
                if not isinstance(warn_data, dict):
                    continue
                reason = str(warn_data.get("reason", "غير معروف"))
                message_text = str(warn_data.get("message", "غير معروف"))
                moderator = str(warn_data.get("moderator", "غير معروف"))
                created_at = warning_time_to_unix(warn_data.get("time"))
                legacy_key = make_warning_legacy_key(user_id, reason, message_text, created_at)

                # Do not resurrect warnings that were already cleared from the dashboard.
                # Older JSON backups can still contain the warning after it has been marked
                # cleared in SQLite, so we skip importing if the same user/reason/message
                # already exists in history in any status.
                cur.execute("""
                    SELECT id FROM warning_history
                    WHERE user_id = ? AND reason = ? AND message = ?
                    LIMIT 1
                """, (int(user_id), reason, message_text))
                if cur.fetchone():
                    continue

                cur.execute("""
                    INSERT OR IGNORE INTO warning_history
                    (user_id, reason, message, moderator, source, status, created_at, legacy_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (int(user_id), reason, message_text, moderator, "legacy_json", "active", int(created_at), legacy_key))
        if close_conn and conn:
            conn.commit()
    except Exception as e:
        print(f"Warning migration error: {e}")
    finally:
        if close_conn and conn:
            conn.close()


def record_warning_history(user_id, reason, message_text, moderator, source="bot"):
    created_at = int(time.time())
    legacy_key = make_warning_legacy_key(user_id, reason, message_text, created_at)
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO warning_history
            (user_id, reason, message, moderator, source, status, created_at, legacy_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(user_id), str(reason), str(message_text), str(moderator), str(source), "active", created_at, legacy_key))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning history insert error: {e}")


def get_warning_history(user_id=None, status="all", limit=100):
    rows = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        query = "SELECT id, user_id, reason, message, moderator, source, status, created_at, cleared_at, cleared_by, clear_reason FROM warning_history"
        clauses = []
        params = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(int(user_id))
        if status in ("active", "cleared"):
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        cur.execute(query, tuple(params))
        for row in cur.fetchall():
            rows.append({
                "id": row[0], "user_id": row[1], "reason": row[2], "message": row[3],
                "moderator": row[4], "source": row[5], "status": row[6], "created_at": row[7],
                "cleared_at": row[8], "cleared_by": row[9], "clear_reason": row[10]
            })
        conn.close()
    except Exception as e:
        print(f"Get warning history error: {e}")
    return rows


def get_active_warning_count(user_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM warning_history WHERE user_id = ? AND status = 'active'", (int(user_id),))
        count = int(cur.fetchone()[0] or 0)
        conn.close()
        return count
    except:
        return len(warnings.get(str(user_id), []))


def get_warning_summary_counts():
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM warning_history WHERE status = 'active'")
        active = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM warning_history WHERE status = 'cleared'")
        cleared = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM warning_history WHERE status = 'active'")
        active_users = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM warning_history")
        total_users = int(cur.fetchone()[0] or 0)
        conn.close()
        return active, cleared, active_users, total_users
    except:
        return 0, 0, 0, 0


def rebuild_warnings_json_from_active_history():
    """
    Keeps warnings.json in sync with SQLite warning_history.
    This prevents cleared dashboard warnings from coming back after a bot restart
    or memory restore. Only active warnings are written back to warnings.json.
    """
    global warnings
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, reason, message, moderator, created_at
            FROM warning_history
            WHERE status = 'active'
            ORDER BY created_at ASC, id ASC
        """)
        rebuilt = {}
        for user_id, reason, message_text, moderator, created_at in cur.fetchall():
            key = str(int(user_id))
            rebuilt.setdefault(key, []).append({
                "reason": str(reason or "غير معروف"),
                "message": str(message_text or "غير معروف"),
                "moderator": str(moderator or "غير معروف"),
                "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(created_at or time.time())))
            })
        conn.close()
        warnings = rebuilt
        save_warnings()
        return True
    except Exception as e:
        print(f"Rebuild warnings json error: {e}")
        return False


def schedule_memory_backup_after_warning_change(reason="Warnings updated"):
    """
    Railway storage is ephemeral. If a warning is cleared from the dashboard and the bot is redeployed
    before the next hourly auto-backup, startup restore can bring back the old Discord backup.
    This schedules an immediate backup after warning changes so cleared warnings stay cleared after redeploys.
    """
    try:
        if not bot or not getattr(bot, "loop", None):
            return False

        async def _backup_later():
            try:
                await bot.wait_until_ready()
                await asyncio.sleep(2)
                guild = bot.get_guild(GUILD_ID)
                if guild:
                    await create_memory_backup(guild, reason=reason)
            except Exception as e:
                print(f"Warning-change backup error: {e}")

        bot.loop.call_soon_threadsafe(lambda: bot.loop.create_task(_backup_later()))
        return True
    except Exception as e:
        print(f"Schedule warning-change backup error: {e}")
        return False


def clear_warnings_for_user(user_id, cleared_by="Dashboard", clear_reason="Manual clear"):
    user_id = int(user_id)
    active_before = get_active_warning_count(user_id)
    warnings[str(user_id)] = []
    save_warnings()
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            UPDATE warning_history
            SET status = 'cleared', cleared_at = ?, cleared_by = ?, clear_reason = ?
            WHERE user_id = ? AND status = 'active'
        """, (int(time.time()), str(cleared_by), str(clear_reason), user_id))
        conn.commit()
        conn.close()
        rebuild_warnings_json_from_active_history()
        schedule_memory_backup_after_warning_change(reason=f"Warnings cleared for user {user_id}")
    except Exception as e:
        print(f"Clear warning history error: {e}")
    return active_before


def clear_single_warning_by_id(warning_id, cleared_by="Dashboard", clear_reason="Manual clear"):
    """
    Clears one active warning row without deleting it.
    The row stays in warning_history with status='cleared'.
    """
    warning_id = int(warning_id)
    changed = 0
    user_id = None

    try:
        conn = db_connect()
        cur = conn.cursor()

        cur.execute("SELECT user_id FROM warning_history WHERE id = ? AND status = 'active'", (warning_id,))
        row = cur.fetchone()

        if not row:
            conn.close()
            return 0, None

        user_id = int(row[0])

        cur.execute("""
            UPDATE warning_history
            SET status = 'cleared',
                cleared_at = ?,
                cleared_by = ?,
                clear_reason = ?
            WHERE id = ? AND status = 'active'
        """, (int(time.time()), str(cleared_by), str(clear_reason), warning_id))

        changed = cur.rowcount
        conn.commit()
        conn.close()
        rebuild_warnings_json_from_active_history()
        if changed:
            schedule_memory_backup_after_warning_change(reason=f"Warning #{warning_id} cleared")

    except Exception as e:
        print(f"Clear single warning error: {e}")
        return 0, user_id

    return int(changed or 0), user_id




def add_warning(member, reason, message_text, moderator):
    user_id = str(member.id)

    if user_id not in warnings:
        warnings[user_id] = []

    warn_record = {
        "reason": reason,
        "message": message_text,
        "moderator": moderator,
        "time": discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }

    warnings[user_id].append(warn_record)
    save_warnings()
    record_warning_history(member.id, reason, message_text, moderator, source="bot")
    schedule_memory_backup_after_warning_change(reason=f"Warning added for user {member.id}")
    return get_active_warning_count(member.id)


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
    settings = get_guild_protection_settings(message.guild.id) if message.guild else protection_default_settings()

    if settings.get("delete_messages") and not settings.get("log_only"):
        try:
            await message.delete()
        except:
            pass

    count = add_warning(message.author, reason, old_message, "النظام التلقائي")
    cc_record_event(
        "violation",
        guild_id=message.guild.id,
        user_id=message.author.id,
        user_name=str(message.author),
        channel_id=message.channel.id,
        channel_name=getattr(message.channel, "name", "unknown"),
        details=f"{reason} | Warning #{count} | Message: {old_message[:300]}"
    )
    if settings.get("log_only"):
        punishment = "Log only / بدون عقوبة"
    elif settings.get("timeouts"):
        punishment = await apply_punishment(message.author, message.channel, count)
    else:
        punishment = "تحذير فقط / Timeouts disabled"

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
# REAL ESTATE EMPIRE HELPERS
# =========================

def property_config(type_key):
    return PROPERTY_TYPES.get(str(type_key))


def property_title(row):
    # row: id, type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price
    if not row:
        return "Unknown Property"
    _, type_key, unit_number, display_name, *_ = row
    cfg = property_config(type_key) or {}
    emoji = cfg.get("emoji", "🏠")
    name = display_name or cfg.get("name", str(type_key))
    return f"{emoji} {name} #{unit_number}"


def property_rent_amount(type_key, level=1):
    cfg = property_config(type_key)
    if not cfg:
        return 0
    base = int(cfg.get("rent", 0))
    level = max(1, int(level or 1))
    return int(base * (1 + ((level - 1) * 0.35)))


def property_upgrade_cost(type_key, level=1):
    cfg = property_config(type_key)
    if not cfg:
        return 0
    base = int(cfg.get("upgrade_base", 0))
    level = max(1, int(level or 1))
    return int(base * level)


def seed_real_estate_properties():
    try:
        conn = db_connect()
        cur = conn.cursor()
        now = int(time.time())
        for type_key, cfg in PROPERTY_TYPES.items():
            cur.execute("SELECT COUNT(*) FROM real_estate_properties WHERE type_key = ?", (type_key,))
            existing = int(cur.fetchone()[0] or 0)
            target = int(cfg.get("count", 0))
            for unit in range(existing + 1, target + 1):
                cur.execute(
                    """
                    INSERT INTO real_estate_properties
                    (type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price, created_at)
                    VALUES (?, ?, ?, 0, 1, 0, 0, ?)
                    """,
                    (type_key, unit, cfg.get("name", type_key), now)
                )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"seed_real_estate_properties error: {e}")


def get_property_by_id(property_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price
            FROM real_estate_properties WHERE id = ?
        """, (int(property_id),))
        row = cur.fetchone()
        conn.close()
        return row
    except:
        return None


def get_available_property(type_key):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price
            FROM real_estate_properties
            WHERE type_key = ? AND owner_id = 0
            ORDER BY unit_number ASC LIMIT 1
        """, (str(type_key),))
        row = cur.fetchone()
        conn.close()
        return row
    except:
        return None


def real_estate_counts():
    data = {}
    try:
        conn = db_connect()
        cur = conn.cursor()
        for type_key, cfg in PROPERTY_TYPES.items():
            cur.execute("SELECT COUNT(*) FROM real_estate_properties WHERE type_key=?", (type_key,))
            total = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*) FROM real_estate_properties WHERE type_key=? AND owner_id=0", (type_key,))
            available = int(cur.fetchone()[0] or 0)
            data[type_key] = {"total": total, "available": available, "owned": max(0, total - available)}
        conn.close()
    except Exception as e:
        print(f"real_estate_counts error: {e}")
    return data


def get_user_properties(user_id, limit=25):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price
            FROM real_estate_properties
            WHERE owner_id = ?
            ORDER BY type_key ASC, unit_number ASC
            LIMIT ?
        """, (int(user_id), int(limit)))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def get_for_sale_properties(limit=10):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type_key, unit_number, display_name, owner_id, level, last_rent_claim, for_sale_price
            FROM real_estate_properties
            WHERE for_sale_price > 0 AND owner_id > 0
            ORDER BY for_sale_price ASC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def set_property_owner(property_id, owner_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("UPDATE real_estate_properties SET owner_id=?, for_sale_price=0 WHERE id=?", (int(owner_id), int(property_id)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"set_property_owner error: {e}")
        return False


def set_property_for_sale(property_id, owner_id, price):
    row = get_property_by_id(property_id)
    if not row:
        return False, "ما لقيت العقار."
    if int(row[4] or 0) != int(owner_id):
        return False, "هذا العقار مب ملكك."
    if int(price) <= 0:
        return False, "السعر لازم يكون أكبر من صفر."
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("UPDATE real_estate_properties SET for_sale_price=? WHERE id=?", (int(price), int(property_id)))
        conn.commit()
        conn.close()
        return True, "تم عرض العقار للبيع."
    except Exception as e:
        return False, str(e)


def buy_property_from_system(user_id, type_key):
    cfg = property_config(type_key)
    if not cfg:
        return False, "نوع العقار غير معروف.", None, 0
    row = get_available_property(type_key)
    if not row:
        return False, "Sold Out — هذا النوع خلص من السوق الأساسي. اشترِ من لاعب أو ادخل مزاد.", None, 0
    price = int(cfg.get("price", 0))
    ok, balance = remove_money(user_id, price)
    if not ok:
        return False, f"رصيدك ما يكفي. تحتاج {coin_line(price)}.", row, price
    set_property_owner(row[0], user_id)
    return True, "تم شراء العقار بنجاح.", get_property_by_id(row[0]), price


def buy_property_listing(buyer_id, property_id):
    row = get_property_by_id(property_id)
    if not row:
        return False, "ما لقيت العقار.", None
    owner_id = int(row[4] or 0)
    price = int(row[7] or 0)
    if owner_id <= 0 or price <= 0:
        return False, "العقار مب معروض للبيع حالياً.", row
    if owner_id == int(buyer_id):
        return False, "ما تقدر تشتري عقارك من نفسك.", row
    ok, new_balance = remove_money(buyer_id, price)
    if not ok:
        return False, f"رصيدك ما يكفي. السعر: {coin_line(price)}", row
    tax = int(price * (REAL_ESTATE_SALE_TAX_PERCENT / 100))
    seller_gets = price - tax
    add_money(owner_id, seller_gets)
    set_property_owner(property_id, buyer_id)
    return True, f"تم الشراء. البائع استلم {coin_line(seller_gets)} بعد ضريبة {REAL_ESTATE_SALE_TAX_PERCENT}%.", get_property_by_id(property_id)


def collect_rent_for_user(user_id):
    rows = get_user_properties(user_id, limit=200)
    now = int(time.time())
    total = 0
    ready = []
    next_remaining = None
    for row in rows:
        prop_id, type_key, unit_number, display_name, owner_id, level, last_claim, sale_price = row
        last_claim = int(last_claim or 0)
        elapsed = now - last_claim
        if last_claim == 0 or elapsed >= REAL_ESTATE_RENT_COOLDOWN_SECONDS:
            rent = property_rent_amount(type_key, level)
            total += rent
            ready.append((prop_id, rent))
        else:
            remaining = REAL_ESTATE_RENT_COOLDOWN_SECONDS - elapsed
            next_remaining = remaining if next_remaining is None else min(next_remaining, remaining)
    if total <= 0:
        return False, 0, next_remaining or REAL_ESTATE_RENT_COOLDOWN_SECONDS, len(rows)
    try:
        conn = db_connect()
        cur = conn.cursor()
        for prop_id, rent in ready:
            cur.execute("UPDATE real_estate_properties SET last_rent_claim=? WHERE id=?", (now, int(prop_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"collect_rent update error: {e}")
    balance = add_money(user_id, total)
    return True, total, 0, len(rows)


def upgrade_property(user_id, property_id):
    row = get_property_by_id(property_id)
    if not row:
        return False, "ما لقيت العقار.", None
    prop_id, type_key, unit_number, display_name, owner_id, level, last_claim, sale_price = row
    if int(owner_id or 0) != int(user_id):
        return False, "هذا العقار مب ملكك.", row
    cfg = property_config(type_key) or {}
    max_level = int(cfg.get("max_level", 5))
    level = int(level or 1)
    if level >= max_level:
        return False, f"العقار وصل أعلى تطوير Level {max_level}.", row
    cost = property_upgrade_cost(type_key, level)
    ok, balance = remove_money(user_id, cost)
    if not ok:
        return False, f"رصيدك ما يكفي. تكلفة التطوير: {coin_line(cost)}", row
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("UPDATE real_estate_properties SET level=? WHERE id=?", (level + 1, int(property_id)))
        conn.commit()
        conn.close()
    except Exception as e:
        add_money(user_id, cost)
        return False, f"فشل التطوير ورجعت لك الفلوس: {e}", row
    return True, f"تم تطوير العقار إلى Level {level + 1}. الدخل الجديد: {coin_line(property_rent_amount(type_key, level + 1))}", get_property_by_id(property_id)


def create_property_auction(seller_id, property_id, minutes, start_price):
    row = get_property_by_id(property_id)
    if not row:
        return False, "ما لقيت العقار.", None
    if int(row[4] or 0) != int(seller_id):
        return False, "هذا العقار مب ملكك.", row
    if int(start_price) <= 0:
        return False, "سعر البداية لازم يكون أكبر من صفر.", row
    minutes = max(5, min(int(minutes), 1440))
    ends_at = int(time.time()) + minutes * 60
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT id FROM real_estate_auctions WHERE property_id=? AND status='active'", (int(property_id),))
        if cur.fetchone():
            conn.close()
            return False, "فيه مزاد شغال على هذا العقار بالفعل.", row
        cur.execute("UPDATE real_estate_properties SET for_sale_price=0 WHERE id=?", (int(property_id),))
        cur.execute("""
            INSERT INTO real_estate_auctions
            (property_id, seller_id, start_price, highest_bid, highest_bidder, ends_at, status, created_at)
            VALUES (?, ?, ?, 0, 0, ?, 'active', ?)
        """, (int(property_id), int(seller_id), int(start_price), ends_at, int(time.time())))
        auction_id = cur.lastrowid
        conn.commit()
        conn.close()
        return True, "تم فتح المزاد.", auction_id
    except Exception as e:
        return False, str(e), row


def get_active_auctions(limit=5):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.property_id, a.seller_id, a.start_price, a.highest_bid, a.highest_bidder, a.ends_at,
                   p.type_key, p.unit_number, p.display_name, p.level
            FROM real_estate_auctions a
            JOIN real_estate_properties p ON p.id = a.property_id
            WHERE a.status='active'
            ORDER BY a.ends_at ASC LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def get_auction(auction_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.property_id, a.seller_id, a.start_price, a.highest_bid, a.highest_bidder, a.ends_at,
                   p.type_key, p.unit_number, p.display_name, p.level
            FROM real_estate_auctions a
            JOIN real_estate_properties p ON p.id = a.property_id
            WHERE a.id=? AND a.status='active'
        """, (int(auction_id),))
        row = cur.fetchone()
        conn.close()
        return row
    except:
        return None


def place_auction_bid(user_id, auction_id, amount):
    row = get_auction(auction_id)
    if not row:
        return False, "المزاد غير موجود أو انتهى.", None
    auction_id, property_id, seller_id, start_price, highest_bid, highest_bidder, ends_at, type_key, unit_number, display_name, level = row
    now = int(time.time())
    if now >= int(ends_at):
        return False, "المزاد انتهى. انتظر التسوية.", row
    if int(seller_id) == int(user_id):
        return False, "ما تقدر تزايد على مزادك.", row
    min_required = max(int(start_price), int(highest_bid) + 1)
    amount = int(amount)
    if amount < min_required:
        return False, f"لازم تزايد على الأقل بـ {coin_line(min_required)}.", row
    balance = get_balance(user_id)
    if balance < amount:
        return False, f"رصيدك ما يكفي. رصيدك: {coin_line(balance)}", row
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("UPDATE real_estate_auctions SET highest_bid=?, highest_bidder=? WHERE id=?", (amount, int(user_id), int(auction_id)))
        conn.commit()
        conn.close()
        return True, "تم تسجيل مزايدتك. الفلوس تُخصم عند نهاية المزاد إذا فزت.", get_auction(auction_id)
    except Exception as e:
        return False, str(e), row


async def settle_ended_auctions(guild=None):
    try:
        now = int(time.time())
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, property_id, seller_id, start_price, highest_bid, highest_bidder, ends_at
            FROM real_estate_auctions
            WHERE status='active' AND ends_at <= ?
        """, (now,))
        rows = cur.fetchall()
        for auction_id, property_id, seller_id, start_price, highest_bid, highest_bidder, ends_at in rows:
            if int(highest_bidder or 0) > 0 and int(highest_bid or 0) > 0:
                buyer_balance = get_balance(highest_bidder)
                if buyer_balance >= int(highest_bid):
                    remove_money(highest_bidder, highest_bid)
                    tax = int(int(highest_bid) * (REAL_ESTATE_SALE_TAX_PERCENT / 100))
                    seller_gets = int(highest_bid) - tax
                    add_money(seller_id, seller_gets)
                    cur.execute("UPDATE real_estate_properties SET owner_id=?, for_sale_price=0 WHERE id=?", (int(highest_bidder), int(property_id)))
                    cur.execute("UPDATE real_estate_auctions SET status='sold' WHERE id=?", (int(auction_id),))
                    if guild:
                        channel = await get_channel_by_id(guild, EVENTS_CHANNEL_ID)
                        if channel:
                            await channel.send(embed=discord.Embed(title="🔨 انتهى مزاد عقار", description=f"العقار #{property_id} انباع لـ <@{highest_bidder}> بسعر {coin_line(highest_bid)}.\nالبائع استلم {coin_line(seller_gets)}.", color=COLOR_GREEN))
                else:
                    cur.execute("UPDATE real_estate_auctions SET status='failed' WHERE id=?", (int(auction_id),))
            else:
                cur.execute("UPDATE real_estate_auctions SET status='ended_no_bid' WHERE id=?", (int(auction_id),))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"settle_ended_auctions error: {e}")


async def auction_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(30)
    while not bot.is_closed():
        try:
            guild = bot.get_guild(GUILD_ID)
            await settle_ended_auctions(guild)
        except Exception as e:
            print(f"auction_loop error: {e}")
        await asyncio.sleep(60)


def build_market_embed(member=None):
    embed = discord.Embed(
        title="🛒 NM Market",
        description=(
            "متجر واضح بالأزرار — اختر اللي تبيه من تحت.\n"
            "العقارات **محدودة**؛ إذا خلصت لازم تشتري من لاعب أو تدخل مزاد."
        ),
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💎 VIP Pass", value=f"السعر: {coin_line(SHOP_VIP_PRICE)}\nالمدة: **{SHOP_VIP_DAYS} أيام**", inline=True)
    embed.add_field(name="🎁 Mystery Box", value=f"السعر: {coin_line(LOOTBOX_PRICE)}\nجوائز عشوائية و VIP مؤقت", inline=True)
    embed.add_field(name="🏙️ Real Estate", value="عقارات محدودة + إيجار + بيع بين الأعضاء + مزادات", inline=False)
    if member:
        embed.set_author(name=f"{member.display_name} • Market", icon_url=member.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(member.id)), inline=True)
        embed.add_field(name="🏠 عقاراتك", value=f"`{len(get_user_properties(member.id, 200))}` عقار", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Market Buttons")
    return embed


def build_real_estate_embed(member=None):
    counts = real_estate_counts()
    embed = discord.Embed(
        title="🏙️ Real Estate Empire",
        description=f"كل عقار محدود وله دخل كل **{format_seconds(REAL_ESTATE_RENT_COOLDOWN_SECONDS)}**. اشترِ بدري قبل ما يخلص السوق.",
        color=COLOR_BLUE,
        timestamp=discord.utils.utcnow()
    )
    for key, cfg in PROPERTY_TYPES.items():
        c = counts.get(key, {"available": 0, "total": cfg.get("count", 0)})
        status = "✅ متوفر" if c["available"] > 0 else "❌ Sold Out"
        embed.add_field(
            name=f"{cfg['emoji']} {cfg['name']}",
            value=(
                f"السعر: {coin_line(cfg['price'])}\n"
                f"الإيجار: {coin_line(cfg['rent'])}\n"
                f"المتاح: **{c['available']} / {c['total']}** — {status}"
            ),
            inline=True
        )
    if member:
        embed.set_author(name=f"{member.display_name} • Real Estate", icon_url=member.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(member.id)), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Limited Properties")
    return embed


def build_user_assets_embed(member):
    rows = get_user_properties(member.id, 100)
    embed = discord.Embed(title="💼 ممتلكاتي", color=COLOR_PURPLE, timestamp=discord.utils.utcnow())
    embed.set_author(name=f"{member.display_name} • Assets", icon_url=member.display_avatar.url)
    if not rows:
        embed.description = "ما عندك عقارات حالياً. افتح السوق واشترِ أول عقار."
    else:
        total_rent = sum(property_rent_amount(r[1], r[5]) for r in rows)
        lines = []
        for r in rows[:12]:
            sale = f" | للبيع: {coin_line(r[7], bold=False)}" if int(r[7] or 0) > 0 else ""
            lines.append(f"`#{r[0]}` {property_title(r)} — Lv.{r[5]} — إيجار {short_money(property_rent_amount(r[1], r[5]))}{sale}")
        embed.description = "\n".join(lines)
        if len(rows) > 12:
            embed.description += f"\n... و {len(rows)-12} عقارات زيادة"
        embed.add_field(name="📈 دخل الإيجار الكامل", value=coin_line(total_rent), inline=True)
    embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(member.id)), inline=True)
    embed.set_footer(text="استخدم الأزرار لجمع الإيجار، عرض للبيع، فتح مزاد، أو تطوير عقار.")
    return embed


def build_property_market_embed(member=None):
    rows = get_for_sale_properties(10)
    embed = discord.Embed(title="🏘️ سوق العقارات بين الأعضاء", color=COLOR_BLUE, timestamp=discord.utils.utcnow())
    if not rows:
        embed.description = "ما فيه عقارات معروضة للبيع حالياً."
    else:
        lines = []
        for r in rows:
            lines.append(f"`#{r[0]}` {property_title(r)} — Lv.{r[5]} — السعر {coin_line(r[7], bold=False)} — المالك <@{r[4]}>")
        embed.description = "\n".join(lines)[:3900]
    if member:
        embed.set_author(name=f"{member.display_name} • Property Market", icon_url=member.display_avatar.url)
    embed.set_footer(text=f"الضريبة على البيع: {REAL_ESTATE_SALE_TAX_PERCENT}%")
    return embed


def build_auction_embed(member=None):
    auctions = get_active_auctions(5)
    embed = discord.Embed(title="🔨 مزادات العقارات", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
    if not auctions:
        embed.description = "ما فيه مزادات شغالة حالياً."
    else:
        lines = []
        for a in auctions:
            auction_id, prop_id, seller_id, start_price, highest_bid, highest_bidder, ends_at, type_key, unit_number, display_name, level = a
            title = f"{(property_config(type_key) or {}).get('emoji','🏠')} {display_name} #{unit_number}"
            high = coin_line(highest_bid if highest_bid else start_price, bold=False)
            bidder = f"<@{highest_bidder}>" if int(highest_bidder or 0) else "لا يوجد"
            lines.append(f"`A#{auction_id}` {title} — أعلى سعر: {high} — المزايد: {bidder} — ينتهي <t:{int(ends_at)}:R>")
        embed.description = "\n".join(lines)
    if member:
        embed.set_author(name=f"{member.display_name} • Auctions", icon_url=member.display_avatar.url)
    embed.set_footer(text="المزايدة لا تخصم إلا إذا انتهى المزاد وفزت.")
    return embed

# =========================
# VIEWS
# =========================


class MarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="VIP Pass", style=discord.ButtonStyle.primary, emoji="💎")
    async def vip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💎 VIP Pass",
            description=(
                f"السعر: {coin_line(SHOP_VIP_PRICE)}\n"
                f"المدة: **{SHOP_VIP_DAYS} أيام**\n\n"
                "تحصل على رتبة VIP مؤقتة ومنظر مميز في السيرفر."
            ),
            color=COLOR_PURPLE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.display_name} • VIP Checkout", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(interaction.user.id)), inline=True)
        await interaction.response.send_message(embed=embed, view=VipConfirmView(), ephemeral=True)

    @discord.ui.button(label="Mystery Box", style=discord.ButtonStyle.success, emoji="🎁")
    async def box_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎁 Mystery Box",
            description=(
                f"السعر: {coin_line(LOOTBOX_PRICE)}\n"
                "الجوائز: Coins / VIP مؤقت / Event Winner مؤقت / Jackpot\n\n"
                "اضغط فتح الصندوق إذا جاهز للحظ."
            ),
            color=COLOR_GREEN,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.display_name} • Lootbox", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(interaction.user.id)), inline=True)
        await interaction.response.send_message(embed=embed, view=LootboxConfirmView(), ephemeral=True)

    @discord.ui.button(label="Real Estate", style=discord.ButtonStyle.secondary, emoji="🏙️")
    async def real_estate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_real_estate_embed(interaction.user), view=RealEstateView(), ephemeral=True)

    @discord.ui.button(label="ممتلكاتي", style=discord.ButtonStyle.secondary, emoji="💼")
    async def assets_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_user_assets_embed(interaction.user), view=MyAssetsView(), ephemeral=True)

    @discord.ui.button(label="رصيدي", style=discord.ButtonStyle.secondary, emoji="🪙")
    async def wallet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        xp, lvl = get_level_data(interaction.user.id)
        embed = discord.Embed(title="💼 Wallet", color=COLOR_BLUE, timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="الرصيد", value=coin_line(get_balance(interaction.user.id)), inline=False)
        embed.add_field(name="Level", value=f"Lv.{lvl} | XP {xp}/{lvl*100}", inline=True)
        embed.add_field(name="العقارات", value=f"{len(get_user_properties(interaction.user.id, 200))} عقار", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class VipConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="تأكيد شراء VIP", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        vip_role, _ = await ensure_custom_roles(guild)
        if not vip_role:
            await interaction.response.send_message("❌ ما قدرت أجهز رتبة VIP. تأكد من صلاحية Manage Roles.", ephemeral=True)
            return
        ok, new_balance = remove_money(interaction.user.id, SHOP_VIP_PRICE)
        if not ok:
            await interaction.response.send_message(f"❌ رصيدك ما يكفي. تحتاج {coin_line(SHOP_VIP_PRICE)}.", ephemeral=True)
            return
        try:
            await interaction.user.add_roles(vip_role, reason=f"{BOT_BRAND} shop VIP button purchase")
            expires_at = int(time.time()) + int(SHOP_VIP_DAYS) * 86400
            add_timed_role_record(interaction.user.id, vip_role.id, expires_at, "Shop VIP button purchase")
            record_shop_purchase(interaction.user.id, "vip_button", SHOP_VIP_PRICE)
            embed = discord.Embed(title="✅ تم شراء VIP", description=f"تم إعطاؤك {vip_role.mention} لمدة **{SHOP_VIP_DAYS} أيام**.", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
            embed.add_field(name="السعر", value=coin_line(SHOP_VIP_PRICE), inline=True)
            embed.add_field(name="رصيدك الجديد", value=coin_line(new_balance), inline=True)
            embed.add_field(name="ينتهي", value=f"<t:{expires_at}:R>", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            add_money(interaction.user.id, SHOP_VIP_PRICE)
            await interaction.response.send_message(f"❌ فشل إعطاء الرتبة ورجعت لك الفلوس: `{clean_text(str(e), 250)}`", ephemeral=True)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="تم الإلغاء.", embed=None, view=None)


class LootboxConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="فتح الصندوق", style=discord.ButtonStyle.success, emoji="🎁")
    async def open_box(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = time.time()
        last = lootbox_cooldowns.get(interaction.user.id, 0)
        if now - last < LOOTBOX_COOLDOWN_SECONDS:
            await interaction.response.send_message(f"⏳ باقي {LOOTBOX_COOLDOWN_SECONDS - (now-last):.1f} ثانية.", ephemeral=True)
            return
        lootbox_cooldowns[interaction.user.id] = now
        ok, new_balance = remove_money(interaction.user.id, LOOTBOX_PRICE)
        if not ok:
            await interaction.response.send_message(f"❌ رصيدك ما يكفي. سعر الصندوق {coin_line(LOOTBOX_PRICE)}.", ephemeral=True)
            return
        rewards = [
            ("coins", int(LOOTBOX_PRICE * 0.25), 28, "Common"),
            ("coins", int(LOOTBOX_PRICE * 0.75), 24, "Uncommon"),
            ("coins", int(LOOTBOX_PRICE * 1.5), 20, "Rare"),
            ("coins", int(LOOTBOX_PRICE * 3), 12, "Epic"),
            ("vip_hours", 12, 8, "Epic VIP"),
            ("winner_hours", 6, 5, "Legendary Role"),
            ("coins", int(LOOTBOX_PRICE * 7), 3, "Mythic Jackpot"),
        ]
        pool=[]
        for reward_type, value, weight, rarity in rewards:
            pool.extend([(reward_type, value, rarity)] * int(weight))
        reward_type, value, rarity = random.choice(pool)
        desc=""
        color=COLOR_BLUE
        if reward_type == "coins":
            add_money(interaction.user.id, int(value))
            profit = int(value) - int(LOOTBOX_PRICE)
            desc = f"ربحت {coin_line(value)}\nصافي النتيجة: {money_delta(profit)}"
            color = COLOR_GREEN if profit >= 0 else COLOR_YELLOW
        elif reward_type == "vip_hours":
            vip_role, _ = await ensure_custom_roles(interaction.guild)
            if vip_role:
                await interaction.user.add_roles(vip_role, reason=f"{BOT_BRAND} lootbox VIP reward")
                expires_at = int(time.time()) + int(value) * 3600
                add_timed_role_record(interaction.user.id, vip_role.id, expires_at, "Lootbox VIP reward")
                desc = f"ربحت {vip_role.mention} لمدة **{value} ساعة**. ينتهي <t:{expires_at}:R>"
            color = COLOR_PURPLE
        else:
            _, winner_role = await ensure_custom_roles(interaction.guild)
            if winner_role:
                await interaction.user.add_roles(winner_role, reason=f"{BOT_BRAND} lootbox winner reward")
                expires_at = int(time.time()) + int(value) * 3600
                add_timed_role_record(interaction.user.id, winner_role.id, expires_at, "Lootbox winner reward")
                desc = f"ربحت {winner_role.mention} لمدة **{value} ساعات**. ينتهي <t:{expires_at}:R>"
            color = COLOR_ORANGE
        record_lootbox(interaction.user.id, LOOTBOX_PRICE, reward_type, value)
        record_shop_purchase(interaction.user.id, "lootbox_button", LOOTBOX_PRICE)
        embed = discord.Embed(title=f"🎁 Mystery Box • {rarity}", description=desc, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{interaction.user.display_name} فتح صندوق", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="رصيدك الآن", value=coin_line(get_balance(interaction.user.id)), inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="تم الإلغاء.", embed=None, view=None)


class PurchasePropertyButton(discord.ui.Button):
    def __init__(self, type_key):
        cfg = property_config(type_key)
        label = cfg.get("name", type_key) if cfg else type_key
        emoji = cfg.get("emoji", "🏠") if cfg else "🏠"
        super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
        self.type_key = type_key

    async def callback(self, interaction: discord.Interaction):
        if not REAL_ESTATE_ENABLED:
            await interaction.response.send_message("🔒 نظام العقارات مقفل مؤقتًا.", ephemeral=True)
            return
        ok, message, row, price = buy_property_from_system(interaction.user.id, self.type_key)
        if not ok:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
            return
        embed = discord.Embed(title="✅ تم شراء عقار", description=f"ملكت الآن: **{property_title(row)}**", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
        embed.add_field(name="السعر", value=coin_line(price), inline=True)
        embed.add_field(name="الإيجار", value=coin_line(property_rent_amount(row[1], row[5])), inline=True)
        embed.add_field(name="رصيدك", value=coin_line(get_balance(interaction.user.id)), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RealEstateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        for type_key in PROPERTY_TYPES.keys():
            self.add_item(PurchasePropertyButton(type_key))

    @discord.ui.button(label="عقاراتي", style=discord.ButtonStyle.secondary, emoji="💼", row=2)
    async def my_properties(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_user_assets_embed(interaction.user), view=MyAssetsView())

    @discord.ui.button(label="جمع الإيجار", style=discord.ButtonStyle.success, emoji="💰", row=2)
    async def collect_rent(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, total, remaining, count = collect_rent_for_user(interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"⏳ ما فيه إيجار جاهز. أقرب إيجار بعد: **{format_seconds(remaining)}**", ephemeral=True)
            return
        await interaction.response.send_message(f"✅ جمعت إيجار {count} عقار: {coin_line(total)}\nرصيدك الآن: {coin_line(get_balance(interaction.user.id))}", ephemeral=True)

    @discord.ui.button(label="سوق اللاعبين", style=discord.ButtonStyle.secondary, emoji="🏘️", row=2)
    async def player_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_property_market_embed(interaction.user), view=PropertyMarketView())

    @discord.ui.button(label="المزادات", style=discord.ButtonStyle.secondary, emoji="🔨", row=2)
    async def auctions(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_auction_embed(interaction.user), view=AuctionListView())


class MyAssetsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="جمع الإيجار", style=discord.ButtonStyle.success, emoji="💰")
    async def collect(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok, total, remaining, count = collect_rent_for_user(interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"⏳ ما فيه إيجار جاهز. أقرب إيجار بعد: **{format_seconds(remaining)}**", ephemeral=True)
            return
        await interaction.response.edit_message(embed=build_user_assets_embed(interaction.user), view=self)
        await interaction.followup.send(f"✅ جمعت: {coin_line(total)}", ephemeral=True)

    @discord.ui.button(label="عرض للبيع", style=discord.ButtonStyle.secondary, emoji="🏷️")
    async def list_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ListPropertyModal())

    @discord.ui.button(label="فتح مزاد", style=discord.ButtonStyle.secondary, emoji="🔨")
    async def start_auction(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StartAuctionModal())

    @discord.ui.button(label="تطوير عقار", style=discord.ButtonStyle.primary, emoji="⬆️")
    async def upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UpgradePropertyModal())

    @discord.ui.button(label="رجوع للسوق", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_real_estate_embed(interaction.user), view=RealEstateView())


class ListPropertyModal(discord.ui.Modal, title="عرض عقار للبيع"):
    property_id = discord.ui.TextInput(label="Property ID", placeholder="مثال: 12", required=True, max_length=20)
    price = discord.ui.TextInput(label="السعر", placeholder="مثال: 150000", required=True, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prop_id = int(str(self.property_id.value).strip())
            price = parse_bet_amount(str(self.price.value).strip())
        except:
            await interaction.response.send_message("❌ البيانات غير صحيحة.", ephemeral=True)
            return
        if price is None:
            await interaction.response.send_message("❌ السعر غير صحيح.", ephemeral=True)
            return
        ok, msg = set_property_for_sale(prop_id, interaction.user.id, price)
        color = COLOR_GREEN if ok else COLOR_RED
        await interaction.response.send_message(embed=discord.Embed(title="🏷️ عرض عقار للبيع", description=msg, color=color), ephemeral=True)


class StartAuctionModal(discord.ui.Modal, title="فتح مزاد عقار"):
    property_id = discord.ui.TextInput(label="Property ID", placeholder="مثال: 12", required=True, max_length=20)
    minutes = discord.ui.TextInput(label="مدة المزاد بالدقائق", placeholder="مثال: 30", required=True, max_length=20)
    start_price = discord.ui.TextInput(label="سعر البداية", placeholder="مثال: 100000", required=True, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prop_id = int(str(self.property_id.value).strip())
            minutes = int(str(self.minutes.value).strip())
            start_price = parse_bet_amount(str(self.start_price.value).strip())
        except:
            await interaction.response.send_message("❌ البيانات غير صحيحة.", ephemeral=True)
            return
        if start_price is None:
            await interaction.response.send_message("❌ سعر البداية غير صحيح.", ephemeral=True)
            return
        ok, msg, auction_id = create_property_auction(interaction.user.id, prop_id, minutes, start_price)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return
        embed = discord.Embed(title="🔨 مزاد عقار جديد", description=f"فتح <@{interaction.user.id}> مزاد على العقار `#{prop_id}`.\nسعر البداية: {coin_line(start_price)}\nينتهي بعد: **{minutes} دقيقة**", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
        channel = await get_channel_by_id(interaction.guild, EVENTS_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed, view=AuctionListView())
        await interaction.response.send_message("✅ تم فتح المزاد ونشره في روم الفعاليات.", ephemeral=True)


class UpgradePropertyModal(discord.ui.Modal, title="تطوير عقار"):
    property_id = discord.ui.TextInput(label="Property ID", placeholder="مثال: 12", required=True, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            prop_id = int(str(self.property_id.value).strip())
        except:
            await interaction.response.send_message("❌ رقم العقار غير صحيح.", ephemeral=True)
            return
        ok, msg, row = upgrade_property(interaction.user.id, prop_id)
        await interaction.response.send_message(embed=discord.Embed(title="⬆️ تطوير عقار", description=msg, color=COLOR_GREEN if ok else COLOR_RED), ephemeral=True)


class PropertyMarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        rows = get_for_sale_properties(5)
        for row in rows:
            self.add_item(BuyListingButton(row[0], row[7]))

    @discord.ui.button(label="تحديث", style=discord.ButtonStyle.secondary, emoji="🔄", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_property_market_embed(interaction.user), view=PropertyMarketView())

    @discord.ui.button(label="رجوع للعقارات", style=discord.ButtonStyle.secondary, emoji="↩️", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_real_estate_embed(interaction.user), view=RealEstateView())


class BuyListingButton(discord.ui.Button):
    def __init__(self, property_id, price):
        super().__init__(label=f"شراء #{property_id}", style=discord.ButtonStyle.success, emoji="🛒")
        self.property_id = int(property_id)

    async def callback(self, interaction: discord.Interaction):
        ok, msg, row = buy_property_listing(interaction.user.id, self.property_id)
        await interaction.response.send_message(embed=discord.Embed(title="🏘️ شراء عقار", description=msg, color=COLOR_GREEN if ok else COLOR_RED), ephemeral=True)


class AuctionListView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        rows = get_active_auctions(5)
        for row in rows:
            auction_id = row[0]
            self.add_item(BidButton(auction_id, 10000, f"A#{auction_id} +10k"))
            self.add_item(BidButton(auction_id, 50000, f"A#{auction_id} +50k"))

    @discord.ui.button(label="مزايدة مخصصة", style=discord.ButtonStyle.primary, emoji="✍️", row=3)
    async def custom_bid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomBidModal())

    @discord.ui.button(label="تحديث", style=discord.ButtonStyle.secondary, emoji="🔄", row=3)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_auction_embed(interaction.user), view=AuctionListView())


class BidButton(discord.ui.Button):
    def __init__(self, auction_id, increment, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji="🔨")
        self.auction_id = int(auction_id)
        self.increment = int(increment)

    async def callback(self, interaction: discord.Interaction):
        row = get_auction(self.auction_id)
        if not row:
            await interaction.response.send_message("❌ المزاد غير موجود أو انتهى.", ephemeral=True)
            return
        current = int(row[4] or row[3] or 0)
        amount = current + self.increment
        ok, msg, new_row = place_auction_bid(interaction.user.id, self.auction_id, amount)
        await interaction.response.send_message(embed=discord.Embed(title="🔨 مزايدة", description=f"{msg}\nالمبلغ: {coin_line(amount)}", color=COLOR_GREEN if ok else COLOR_RED), ephemeral=True)


class CustomBidModal(discord.ui.Modal, title="مزايدة مخصصة"):
    auction_id = discord.ui.TextInput(label="Auction ID", placeholder="مثال: 1", required=True, max_length=20)
    amount = discord.ui.TextInput(label="مبلغ المزايدة", placeholder="مثال: 250000", required=True, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            auction_id = int(str(self.auction_id.value).strip())
            amount = parse_bet_amount(str(self.amount.value).strip())
        except:
            await interaction.response.send_message("❌ البيانات غير صحيحة.", ephemeral=True)
            return
        if amount is None:
            await interaction.response.send_message("❌ المبلغ غير صحيح.", ephemeral=True)
            return
        ok, msg, row = place_auction_bid(interaction.user.id, auction_id, amount)
        await interaction.response.send_message(embed=discord.Embed(title="🔨 مزايدة مخصصة", description=f"{msg}\nالمبلغ: {coin_line(amount)}", color=COLOR_GREEN if ok else COLOR_RED), ephemeral=True)


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

@app.before_request
def nm_bridge_before_dashboard_request():
    try:
        if request.path.startswith("/dashboard"):
            nm_bridge_local_restore_to_data("dashboard request")
    except Exception:
        pass



# =========================
# NM STABLE MULTI-GUILD CORE
# Safe version: no aggressive rewrites, only selected guild routing + persistence.
# =========================

def nm_stable_selected_guild_id(default=None):
    """Single safe resolver for dashboard-selected guild."""
    try:
        path = str(getattr(request, "path", "") or "")
        m = re.search(r"/dashboard/guild/(\d+)", path)
        if m:
            gid = int(m.group(1))
            session["selected_guild_id"] = gid
            session["dashboard_active_guild_id"] = gid
            return gid
    except Exception:
        pass

    try:
        gid = request.args.get("guild_id") or request.form.get("guild_id")
        if gid:
            gid = int(gid)
            session["selected_guild_id"] = gid
            session["dashboard_active_guild_id"] = gid
            return gid
    except Exception:
        pass

    try:
        gid = session.get("dashboard_active_guild_id") or session.get("selected_guild_id") or default or GUILD_ID
        return int(gid)
    except Exception:
        return int(default or GUILD_ID or 0)


def nm_stable_selected_guild(default=None):
    try:
        gid = nm_stable_selected_guild_id(default)
        return bot.get_guild(int(gid)) if bot else None
    except Exception:
        return None


def nm_stable_selected_member_count():
    guild = nm_stable_selected_guild()
    if not guild:
        return 0
    try:
        return int(getattr(guild, "member_count", 0) or len(getattr(guild, "members", []) or []) or 0)
    except Exception:
        return 0


@app.before_request
def nm_stable_dashboard_before_request():
    try:
        if request.path.startswith("/dashboard"):
            nm_stable_selected_guild_id()
    except Exception:
        pass




# =========================
# NM PERSISTENT DATA BRIDGE FIX
# Fixes Railway Volume + memory restore mismatch.
# If /data is empty but local restored files have data, copy local -> /data.
# Never overwrite a non-empty /data file with an empty local file.
# =========================
def nm_file_size(path):
    try:
        return Path(path).stat().st_size
    except Exception:
        return 0

def nm_sqlite_table_count(path):
    try:
        if not Path(path).exists() or nm_file_size(path) < 1024:
            return 0
        conn = sqlite3.connect(str(path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        score = len(tables)
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                score += int(cur.fetchone()[0] or 0)
            except Exception:
                pass
        conn.close()
        return score
    except Exception:
        return 0

def nm_json_score(path):
    try:
        if not Path(path).exists() or nm_file_size(path) <= 2:
            return 0
        import json
        data = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
        if isinstance(data, dict):
            return len(data.keys())
        if isinstance(data, list):
            return len(data)
        return 1
    except Exception:
        return 0

def nm_data_file_score(path):
    p = Path(path)
    if p.suffix.lower() == ".db":
        return nm_sqlite_table_count(p)
    if p.suffix.lower() == ".json":
        return nm_json_score(p)
    return nm_file_size(p)

def nm_bridge_local_restore_to_data(reason="startup"):
    """Make /data match the best available restored local files."""
    try:
        if "NM_DATA_DIR" not in globals():
            return
        data_dir = Path(NM_DATA_DIR)
        if not data_dir.exists():
            return

        files = globals().get("NM_MEMORY_FILES", [
            "nm_system.db",
            "warnings.json",
            "log_channels.json",
            "dashboard_settings.json",
            "protection_settings.json",
            "guild_settings.json",
            "money_audit.json",
        ])

        changed = []
        for filename in files:
            local = Path(filename)
            target = data_dir / filename

            local_score = nm_data_file_score(local)
            target_score = nm_data_file_score(target)

            # Copy restored local file into /data only if it is clearly better/non-empty.
            if local.exists() and local_score > 0 and (not target.exists() or target_score == 0 or local_score > target_score):
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(local, target)
                    changed.append(f"{filename}: local({local_score}) -> data({target_score})")
                except Exception as e:
                    print(f"NM bridge copy failed for {filename}: {e}")

            # If /data has the good copy and local missing, keep local mirror for backup systems.
            elif target.exists() and target_score > 0 and (not local.exists() or local_score == 0):
                try:
                    shutil.copy2(target, local)
                    changed.append(f"{filename}: data({target_score}) -> local({local_score})")
                except Exception as e:
                    print(f"NM bridge mirror failed for {filename}: {e}")

        if changed:
            print("✅ NM data bridge fixed restored files:", "; ".join(changed))
        else:
            print(f"✅ NM data bridge checked: no changes needed ({reason})")
    except Exception as e:
        print(f"NM data bridge failed: {e}")


# =========================
# NM DASHBOARD CHANGE PERSIST HOOK
# Any dashboard POST is immediately flushed to persistent storage and memory backup.
# =========================
def nm_dashboard_persist_now(reason="dashboard change"):
    try:
        if "save_dashboard_settings" in globals():
            save_dashboard_settings()
    except Exception as e:
        print(f"save_dashboard_settings failed: {e}")

    try:
        if "sync_warnings_json_from_history" in globals():
            sync_warnings_json_from_history()
    except Exception:
        pass

    try:
        if bot and getattr(bot, "loop", None) and bot.loop.is_running():
            async def _nm_backup():
                try:
                    if "memory_backup_now" in globals():
                        try:
                            await memory_backup_now(reason=reason)
                        except TypeError:
                            await memory_backup_now()
                    elif "send_memory_backup" in globals():
                        await send_memory_backup()
                except Exception as e:
                    print(f"NM memory backup failed: {e}")
            asyncio.run_coroutine_threadsafe(_nm_backup(), bot.loop)
    except Exception as e:
        print(f"NM backup schedule failed: {e}")

@app.after_request
def nm_persist_dashboard_after_request(response):
    try:
        if request.method == "POST" and request.path.startswith("/dashboard"):
            nm_dashboard_persist_now(f"dashboard post {request.path}")
    except Exception as e:
        print(f"NM dashboard persist hook failed: {e}")
    return response



# =========================
# NM SYSTEM STRICT MULTI-GUILD ISOLATION
# كل شيء في الداشبورد لازم يشتغل على السيرفر المختار فقط
# =========================

def nm_int(value, default=0):
    try:
        return int(value)
    except:
        return default



def nm_active_guild_id():
    return nm_stable_selected_guild_id()

def nm_set_active_guild(guild_id):
    guild_id = nm_int(guild_id, GUILD_ID)
    try:
        session["selected_guild_id"] = guild_id
    except:
        pass
    return guild_id


def nm_guild_only_clause(column="guild_id", include_legacy=False):
    gid = nm_active_guild_id()
    if include_legacy:
        return f"({column} = ? OR {column} IS NULL OR {column} = 0)", [gid]
    return f"{column} = ?", [gid]


def nm_ensure_guild_column(cur, table_name):
    """Make old tables multi-guild safe by adding guild_id if missing."""
    try:
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = [row[1] for row in cur.fetchall()]
        if "guild_id" not in cols:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN guild_id INTEGER DEFAULT 0")
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_guild ON {table_name}(guild_id)")
        except:
            pass
    except Exception as e:
        print(f"Guild column migration skipped for {table_name}: {e}")


def nm_migrate_core_tables_for_guilds():
    """Migration guard: every core table gets guild_id so old/global rows stop leaking between servers."""
    tables = [
        "economy",
        "levels",
        "warning_history",
        "dashboard_log_vault",
        "command_center_events",
        "money_audit",
        "real_estate_properties",
        "real_estate_auctions",
        "shop_purchases",
        "lootbox_history",
        "dashboard_audit",
        "guild_settings",
    ]
    try:
        conn = db_connect()
        cur = conn.cursor()
        for table in tables:
            nm_ensure_guild_column(cur, table)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"NM guild migration failed: {e}")


def nm_safe_selected_guild_settings():
    gid = nm_active_guild_id()
    try:
        if "get_guild_settings" in globals():
            return get_guild_settings(gid)
    except Exception:
        pass
    return {}


def nm_coin_name():
    gid = nm_active_guild_id()
    try:
        settings = nm_safe_selected_guild_settings()
        for key in ("coin_name", "currency_name", "economy_coin_name"):
            value = settings.get(key)
            if value:
                return str(value)
    except Exception:
        pass
    try:
        return str(dashboard_settings.get("coin_name") or dashboard_settings.get("currency_name") or "NM Coin")
    except:
        return "NM Coin"


def nm_save_coin_name(name):
    gid = nm_active_guild_id()
    name = clean_text(str(name or "NM Coin"), 40) if "clean_text" in globals() else str(name or "NM Coin")[:40]
    if not name.strip():
        name = "NM Coin"

    try:
        if "get_guild_settings" in globals() and "save_guild_settings" in globals():
            settings = get_guild_settings(gid)
            settings["coin_name"] = name
            settings["currency_name"] = name
            settings["economy_coin_name"] = name
            save_guild_settings(gid, settings)
    except Exception as e:
        print(f"Guild coin save failed: {e}")

    try:
        if "dashboard_settings" in globals():
            dashboard_settings["coin_name"] = name
            dashboard_settings["currency_name"] = name
            dashboard_settings["economy_coin_name"] = name
            if "save_dashboard_settings" in globals():
                save_dashboard_settings()
    except Exception as e:
        print(f"Dashboard coin save failed: {e}")

    try:
        globals()["COIN_NAME"] = name
    except:
        pass

    nm_persist_dashboard_change("coin name changed")
    return name


def nm_persist_dashboard_change(reason="dashboard change"):
    """Save files + send memory backup after dashboard changes so Railway redeploy doesn't revert."""
    try:
        if "save_dashboard_settings" in globals():
            save_dashboard_settings()
    except Exception as e:
        print(f"save_dashboard_settings failed: {e}")

    try:
        if "sync_warnings_json_from_history" in globals():
            sync_warnings_json_from_history()
    except Exception:
        pass

    try:
        if bot and getattr(bot, "loop", None) and bot.loop.is_running():
            async def _run_backup():
                try:
                    if "memory_backup_now" in globals():
                        try:
                            await memory_backup_now(reason=reason)
                        except TypeError:
                            await memory_backup_now()
                    elif "send_memory_backup" in globals():
                        await send_memory_backup()
                except Exception as e:
                    print(f"NM backup failed: {e}")
            asyncio.run_coroutine_threadsafe(_run_backup(), bot.loop)
    except Exception as e:
        print(f"NM backup schedule failed: {e}")


@app.before_request
def nm_before_request_isolation():
    try:
        gid = request.args.get("guild_id") or request.form.get("guild_id")
        if gid:
            nm_set_active_guild(gid)
    except Exception:
        pass


@app.after_request
def nm_after_request_persist(response):
    try:
        if request.method == "POST" and request.path.startswith("/dashboard"):
            coin = (
                request.form.get("coin_name")
                or request.form.get("currency_name")
                or request.form.get("economy_coin_name")
                or request.form.get("coin")
            )
            if coin is not None:
                nm_save_coin_name(coin)
            else:
                nm_persist_dashboard_change(f"dashboard post {request.path}")
    except Exception as e:
        print(f"NM after request persist failed: {e}")
    return response



# =========================
# NM DURABLE DASHBOARD SAVE + GUILD ISOLATION PATCH
# =========================

def nm_safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


def nm_current_dashboard_guild_id():
    return nm_safe_int(
        request.args.get("guild_id")
        or request.form.get("guild_id")
        or session.get("selected_guild_id")
        or GUILD_ID,
        GUILD_ID
    )


def nm_schedule_memory_backup(reason="dashboard change"):
    """Push updated files/db to memory backup after dashboard changes so Railway redeploy will not restore old state."""
    try:
        if not bot or not getattr(bot, "loop", None) or not bot.loop.is_running():
            return

        async def _backup():
            try:
                # Most current builds use memory_backup_now(), some use auto backup wrappers.
                if "memory_backup_now" in globals():
                    try:
                        await memory_backup_now(reason=reason)
                    except TypeError:
                        await memory_backup_now()
                elif "send_memory_backup" in globals():
                    await send_memory_backup()
            except Exception as e:
                print(f"NM memory backup failed: {e}")

        asyncio.run_coroutine_threadsafe(_backup(), bot.loop)
    except Exception as e:
        print(f"NM schedule backup failed: {e}")


def nm_persist_everything(reason="dashboard change"):
    try:
        if "save_dashboard_settings" in globals():
            save_dashboard_settings()
    except Exception as e:
        print(f"save_dashboard_settings failed: {e}")

    try:
        if "sync_warnings_json_from_history" in globals():
            sync_warnings_json_from_history()
    except Exception as e:
        print(f"sync_warnings_json_from_history failed: {e}")

    nm_schedule_memory_backup(reason)


def nm_set_coin_name_everywhere(guild_id, name):
    name = clean_text(str(name or "NM Coin"), 40) if "clean_text" in globals() else str(name or "NM Coin")[:40]
    if not name.strip():
        name = "NM Coin"
    guild_id = nm_safe_int(guild_id, GUILD_ID)

    # Per-guild settings if available
    try:
        if "get_guild_settings" in globals() and "save_guild_settings" in globals():
            settings = get_guild_settings(guild_id)
            settings["coin_name"] = name
            settings["currency_name"] = name
            settings["economy_coin_name"] = name
            save_guild_settings(guild_id, settings)
    except Exception as e:
        print(f"Per-guild coin save failed: {e}")

    # Global fallback for old pages
    try:
        if "dashboard_settings" in globals():
            dashboard_settings["coin_name"] = name
            dashboard_settings["currency_name"] = name
            dashboard_settings["economy_coin_name"] = name
            if "save_dashboard_settings" in globals():
                save_dashboard_settings()
    except Exception as e:
        print(f"Global coin save failed: {e}")

    # Also update global variable if code uses COIN_NAME at runtime.
    try:
        globals()["COIN_NAME"] = name
    except Exception:
        pass

    nm_persist_everything("coin name changed")
    return name


@app.after_request
def nm_dashboard_post_persist_after_request(response):
    """Any dashboard POST means state changed; immediately backup so redeploy doesn't revert it."""
    try:
        if request.method == "POST" and request.path.startswith("/dashboard"):
            coin = (
                request.form.get("coin_name")
                or request.form.get("currency_name")
                or request.form.get("economy_coin_name")
                or request.form.get("coin")
            )
            if coin is not None:
                nm_set_coin_name_everywhere(nm_current_dashboard_guild_id(), coin)
            else:
                nm_persist_everything(f"dashboard post {request.path}")
    except Exception as e:
        print(f"NM dashboard post persist failed: {e}")
    return response


app.secret_key = DASHBOARD_SECRET_KEY


@app.after_request
def dashboard_fast_headers(response):
    try:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "private, max-age=15"
    except Exception:
        pass
    return response

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


def oauth_get_user_guilds(access_token):
    req = urllib.request.Request(
        f"{DISCORD_API_BASE}/users/@me/guilds",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "NM-System-Dashboard/1.0",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = "No response body"
        raise Exception(f"Discord guilds fetch failed: HTTP {e.code}. Response: {body}")


def dashboard_user_guilds():
    guilds = session.get("discord_guilds") or []
    return guilds if isinstance(guilds, list) else []


def dashboard_user_guild_map():
    result = {}
    for item in dashboard_user_guilds():
        try:
            result[int(item.get("id"))] = item
        except Exception:
            pass
    return result


def dashboard_oauth_guild_permissions(guild_id):
    item = dashboard_user_guild_map().get(int(guild_id))
    if not item:
        return 0, False
    try:
        perms = int(item.get("permissions") or 0)
    except Exception:
        perms = 0
    return perms, bool(item.get("owner"))


def dashboard_has_manage_guild_oauth(guild_id):
    try:
        perms, is_owner = dashboard_oauth_guild_permissions(int(guild_id))
        return bool(is_owner or (perms & 0x8) or (perms & 0x20))
    except Exception:
        return False


def dashboard_require_login():
    if not session.get("discord_user"):
        return redirect("/login")
    return None


def dashboard_bot_guild_ids():
    try:
        return {int(g.id) for g in bot.guilds}
    except Exception:
        return set()


def dashboard_get_bot_guild(guild_id):
    try:
        return bot.get_guild(int(guild_id))
    except Exception:
        return None


def dashboard_can_manage_guild(guild_id):
    try:
        guild_id = int(guild_id)
    except Exception:
        return False
    if dashboard_current_user_is_owner():
        return True
    if guild_id in dashboard_bot_guild_ids() and dashboard_has_manage_guild_oauth(guild_id):
        return True
    return False


def dashboard_guild_channels_html(guild, selected_id=0, text_only=True, include_none=True):
    options = []
    if include_none:
        options.append(f"<option value='0' {'selected' if not selected_id else ''}>Not set</option>")
    if not guild:
        return "".join(options)
    channels = guild.text_channels if text_only else guild.channels
    for channel in channels:
        try:
            selected = "selected" if int(channel.id) == int(selected_id or 0) else ""
            options.append(f"<option value='{int(channel.id)}' {selected}>#{dash_escape(channel.name, 80)}</option>")
        except Exception:
            pass
    return "".join(options)


def dashboard_guild_categories_html(guild, selected_id=0, include_none=True):
    options = []
    if include_none:
        options.append(f"<option value='0' {'selected' if not selected_id else ''}>Not set</option>")
    if not guild:
        return "".join(options)
    for category in guild.categories:
        try:
            selected = "selected" if int(category.id) == int(selected_id or 0) else ""
            options.append(f"<option value='{int(category.id)}' {selected}>📁 {dash_escape(category.name, 80)}</option>")
        except Exception:
            pass
    return "".join(options)


def update_guild_settings_from_dashboard(guild_id, enabled, commands_channel_id, gambling_channel_id, logs_category_id, setup_done=True):
    try:
        now = int(time.time())
        guild = dashboard_get_bot_guild(int(guild_id))
        guild_name = str(guild.name)[:180] if guild else get_guild_settings(guild_id).get("guild_name", "")
        conn = db_connect()
        cur = conn.cursor()
        cur.execute('''
            INSERT OR IGNORE INTO guild_settings
            (guild_id, guild_name, enabled, commands_channel_id, gambling_channel_id, logs_category_id, setup_done, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (int(guild_id), guild_name, int(bool(enabled)), int(commands_channel_id or 0), int(gambling_channel_id or 0), int(logs_category_id or 0), int(bool(setup_done)), now, now))
        cur.execute('''
            UPDATE guild_settings
            SET guild_name = ?, enabled = ?, commands_channel_id = ?, gambling_channel_id = ?, logs_category_id = ?, setup_done = ?, updated_at = ?
            WHERE guild_id = ?
        ''', (guild_name, int(bool(enabled)), int(commands_channel_id or 0), int(gambling_channel_id or 0), int(logs_category_id or 0), int(bool(setup_done)), now, int(guild_id)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Dashboard guild settings update error: {e}")
        return False


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


async def dashboard_fetch_member_from_guild(guild_id, user_id):
    guild = bot.get_guild(int(guild_id or 0)) if bot else None
    if not guild:
        return None
    try:
        member = guild.get_member(int(user_id))
        if member:
            return member
        return await guild.fetch_member(int(user_id))
    except Exception:
        return None


def dashboard_get_member_in_guild_sync(guild_id, user_id, timeout=4):
    try:
        future = asyncio.run_coroutine_threadsafe(
            dashboard_fetch_member_from_guild(int(guild_id or 0), int(user_id)),
            bot.loop
        )
        return future.result(timeout=timeout)
    except Exception:
        return None


def dashboard_current_guild_id_safe():
    try:
        raw = request.args.get("guild_id") or session.get("dashboard_active_guild_id") or GUILD_ID
        return int(raw)
    except Exception:
        return int(GUILD_ID)


def dashboard_role_chip_for_role(role, include_id=False, special=None):
    try:
        if not role or getattr(role, "name", "@everyone") == "@everyone":
            return ""
        color = "#94a3b8"
        try:
            if getattr(role, "color", None) and int(role.color.value) != 0:
                color = str(role.color)
        except Exception:
            pass
        name = html.escape(str(role.name))
        cls = "rolechip" + (f" {special}" if special else "")
        title = f"ID: {int(role.id)}"
        extra = f" <span class='muted small'>#{int(role.id)}</span>" if include_id else ""
        return f"<span class='{cls}' title='{html.escape(title)}'><span class='role-dot' style='background:{html.escape(color)}'></span><span class='role-name'>@{name}</span>{extra}</span>"
    except Exception:
        return ""


def dashboard_member_roles_html(member, limit=4):
    try:
        roles = [r for r in getattr(member, "roles", []) if getattr(r, "name", "@everyone") != "@everyone"]
        roles = sorted(roles, key=lambda r: getattr(r, "position", 0), reverse=True)
        shown = roles[:int(limit)]
        chips = []
        for role in shown:
            special = None
            try:
                rid = int(role.id)
                if rid in (set(DASHBOARD_OWNER_ROLE_IDS) | dashboard_dynamic_owner_role_ids()):
                    special = "owner"
                elif rid in (set(DASHBOARD_LIMITED_ADMIN_ROLE_IDS) | set(DASHBOARD_ADMIN_ROLE_IDS) | dashboard_dynamic_admin_role_ids()):
                    special = "admin"
            except Exception:
                pass
            chips.append(dashboard_role_chip_for_role(role, special=special))
        if len(roles) > len(shown):
            chips.append(f"<span class='rolechip more'>+{len(roles)-len(shown)} roles</span>")
        return "<div class='memberroles'>" + "".join(chips) + "</div>" if chips else "<div class='memberroles'><span class='rolechip more'>No roles</span></div>"
    except Exception:
        return ""


def dashboard_member_identity_html(user_id, guild_id=0, include_id=True, include_roles=True, compact=False):
    try:
        user_id = int(user_id or 0)
    except Exception:
        user_id = 0
    if not user_id:
        return "<span class='muted'>Unknown User</span>"

    try:
        gid = int(guild_id or 0) or dashboard_current_guild_id_safe()
    except Exception:
        gid = int(GUILD_ID)

    member = dashboard_get_member_in_guild_sync(gid, user_id, timeout=2) if gid else dashboard_get_member_sync(user_id)
    if not member:
        id_html = f"<span class='muted small'>ID: <code>{user_id}</code></span>" if include_id else ""
        return f"<div class='membercard'><span class='memberavatar blank'>?</span><div class='membermeta'><b>User {user_id}</b>{id_html}</div></div>"

    nick = html.escape(str(getattr(member, "display_name", "") or member.name))
    username = html.escape(str(member))
    raw_name = html.escape(str(getattr(member, "name", "") or username))
    discrim = html.escape(str(getattr(member, "discriminator", "") or ""))
    avatar = ""
    try:
        avatar = member.display_avatar.url
    except Exception:
        avatar = ""
    if compact:
        img = f"<img src='{html.escape(avatar)}'>" if avatar else ""
        label = f"{nick} <span class='muted small'>@{username}</span>"
        return f"<span class='mini-member' title='ID: {user_id}'>{img}<span>{label}</span></span>"

    avatar_html = f"<img class='memberavatar' src='{html.escape(avatar)}'>" if avatar else "<span class='memberavatar blank'>?</span>"
    id_html = f"<span class='userline'>ID: <code>{user_id}</code></span>" if include_id else ""
    username_line = f"<span class='userline'>Username: @{username}</span>"
    nick_line = f"<b>{nick}</b>"
    roles_html = dashboard_member_roles_html(member) if include_roles else ""
    return f"<div class='membercard'>{avatar_html}<div class='membermeta'>{nick_line}{username_line}{id_html}{roles_html}</div></div>"


def dashboard_member_name_in_guild(user_id, guild_id=0, include_id=True):
    return dashboard_member_identity_html(user_id, guild_id=guild_id, include_id=include_id, include_roles=True, compact=False)


def dashboard_member_chip_in_guild(user_id, guild_id=0):
    return dashboard_member_identity_html(user_id, guild_id=guild_id, include_id=True, include_roles=False, compact=True)


def log_vault_unique_urls(urls, limit=8):
    seen = set()
    out = []
    for url in urls or []:
        u = str(url or "").strip().strip("<>")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u[:900])
        if len(out) >= int(limit):
            break
    return out


def log_vault_is_media_url(url):
    try:
        low = str(url or "").lower().split("?")[0]
        if any(low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]):
            return True
        if "cdn.discordapp.com/attachments/" in low or "media.discordapp.net/attachments/" in low:
            return True
    except Exception:
        pass
    return False


def log_vault_clean_url(url):
    return str(url or "").strip().strip("<>")[:900]


def log_vault_attachments_html(urls, preview=True):
    urls = log_vault_unique_urls(urls, limit=8 if preview else 30)
    if not urls:
        return ""

    items = []
    shown = urls[:6] if preview else urls
    for idx, url in enumerate(shown, 1):
        safe = html.escape(log_vault_clean_url(url))
        is_media = log_vault_is_media_url(url)
        icon = "🖼️" if is_media else "📎"
        label = f"{'Media' if is_media else 'Attachment'} {idx}"
        items.append(
            f"<a class='log-attachment compact {'media' if is_media else 'file'}' href='{safe}' target='_blank' rel='noopener' title='Open attachment'>"
            f"<span class='attachment-icon'>{icon}</span><span>{html.escape(label)}</span></a>"
        )

    if preview and len(urls) > len(shown):
        items.append(f"<span class='log-attachment more'>+{len(urls)-len(shown)} more</span>")

    return "<div class='log-attachments compact'>" + "".join(items) + "</div>"


def log_vault_strip_and_collect_urls(text):
    text = str(text or "")
    urls = []

    def keep_url(url):
        url = log_vault_clean_url(url)
        if url and url not in urls:
            urls.append(url)
        return " [attachment] "

    text = re.sub(
        r"!\[[^\]]*\]\((https?://[^\s\)]+)\)",
        lambda match: keep_url(match.group(1)),
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\[[^\]]*\]\((https?://[^\s\)]+)\)",
        lambda match: keep_url(match.group(1)),
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"https?://[^\s<>'\"`]+",
        lambda match: keep_url(match.group(0)),
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"!\[[^\]]*\]", " [attachment] ", text)
    text = re.sub(
        r"\b[\w.-]+\.(?:png|jpg|jpeg|gif|webp)(?:\?size=\d+)?",
        " [attachment] ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"(?:\s*\[attachment\]\s*){2,}", " [attachments] ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text, urls


def log_vault_enrich_user_ids_html(text, guild_id=0, limit=6000):
    raw = str(text or "")[:int(limit)]
    if not raw:
        return ""

    mention_re = re.compile(r"<@!?(\d{15,25})>")
    id_re = re.compile(r"(?<!\d)(\d{17,22})(?!\d)")
    cache = {}

    def chip(uid):
        uid = str(uid)
        if uid not in cache:
            cache[uid] = dashboard_member_chip_in_guild(int(uid), guild_id)
        return cache[uid]

    parts = []
    pos = 0
    for m in mention_re.finditer(raw):
        before = raw[pos:m.start()]
        parts.append(html.escape(before))
        parts.append(chip(m.group(1)))
        pos = m.end()
    parts.append(html.escape(raw[pos:]))
    html_text = "".join(parts)

    def repl_id(match):
        uid = match.group(1)
        try:
            member = dashboard_get_member_in_guild_sync(guild_id, int(uid), timeout=1) if guild_id else dashboard_get_member_sync(int(uid))
            if not member:
                return uid
            return chip(uid)
        except Exception:
            return uid

    try:
        html_text = id_re.sub(repl_id, html_text)
    except Exception:
        pass
    return html_text


def log_vault_render_log_html(text, guild_id=0, preview=True):
    clean, urls = log_vault_strip_and_collect_urls(text)
    if preview:
        clean = log_vault_short_text(clean, 260)
        if clean.endswith("..."):
            clean = clean[:-3].rstrip() + "…"
    else:
        clean = clean[:5000]
    rendered = log_vault_enrich_user_ids_html(clean, guild_id, 5000)
    rendered = rendered.replace("\n", "<br>")
    if not rendered.strip():
        rendered = "<span class='muted'>No text content</span>"
    return f"<div class='log-clean-text'>{rendered}</div>" + log_vault_attachments_html(urls, preview=preview)


def dashboard_member_has_role(member, role_ids):
    try:
        if not member or not role_ids:
            return False
        return any(int(role.id) in role_ids for role in member.roles)
    except:
        return False


def dashboard_session_is_private_owner(user=None):
    """Private fallback owner check using the Discord OAuth session.
    This is not shown in the dashboard access page.
    """
    try:
        user = user or (session.get("discord_user") or {})

        raw_id = user.get("id")
        if raw_id is not None and int(raw_id) in DASHBOARD_PRIVATE_OWNER_USER_IDS:
            return True

        possible_names = {
            str(user.get("username") or "").lower().strip(),
            str(user.get("global_name") or "").lower().strip(),
            str(user.get("display_name") or "").lower().strip(),
        }

        private_names = {str(name).lower().strip() for name in DASHBOARD_PRIVATE_OWNER_USERNAMES}
        return bool(possible_names.intersection(private_names))
    except Exception:
        return False



def is_dashboard_owner_user(user_id):
    try:
        user_id = int(user_id)
    except Exception:
        return False
    try:
        if user_id in DASHBOARD_PRIVATE_OWNER_USER_IDS:
            return True
        if user_id in DASHBOARD_OWNER_USER_IDS or user_id in dashboard_dynamic_owner_user_ids():
            return True
        guild = bot.get_guild(GUILD_ID) if bot else None
        if guild and int(guild.owner_id) == user_id:
            return True
        return dashboard_access_level(user_id) == "owner"
    except Exception:
        return user_id in DASHBOARD_PRIVATE_OWNER_USER_IDS

def dashboard_access_level(user_id):
    """
    Returns:
      owner = full dashboard access
      admin = limited dashboard access
      none  = no dashboard access

    Access can be controlled from /dashboard/admin-access.
    Railway/env owner IDs and the Discord guild owner remain bootstrap owners so you cannot lock yourself out.
    """
    try:
        user_id = int(user_id)
    except:
        return "none"

    guild = bot.get_guild(GUILD_ID)

    # Bootstrap owners: keep these forever for safety.
    # Private owner IDs are hardcoded and not exposed in the dashboard UI.
    if user_id in DASHBOARD_PRIVATE_OWNER_USER_IDS:
        return "owner"

    if user_id in DASHBOARD_OWNER_USER_IDS or user_id in dashboard_dynamic_owner_user_ids():
        return "owner"

    if guild and user_id == int(guild.owner_id):
        return "owner"

    if user_id in dashboard_dynamic_admin_user_ids():
        return "admin"

    member = dashboard_get_member_sync(user_id)

    if not member:
        return "none"

    owner_roles = set(DASHBOARD_OWNER_ROLE_IDS) | dashboard_dynamic_owner_role_ids()
    admin_roles = set(DASHBOARD_LIMITED_ADMIN_ROLE_IDS) | set(DASHBOARD_ADMIN_ROLE_IDS) | dashboard_dynamic_admin_role_ids()

    if dashboard_member_has_role(member, owner_roles):
        return "owner"

    if dashboard_member_has_role(member, admin_roles):
        return "admin"

    # Discord Administrator is allowed to enter only as limited admin, unless you give it an Owner Access role above.
    if member.guild_permissions.administrator:
        return "admin"

    return "none"


def dashboard_user_has_access(user_id):
    return dashboard_access_level(user_id) in ("owner", "admin")


def dashboard_current_access_level():
    user = session.get("discord_user") or {}

    # Private exception can work even if the OAuth ID format changes or the ID was not the expected one.
    if dashboard_session_is_private_owner(user):
        return "owner"

    return dashboard_access_level(user.get("id"))


def dashboard_current_user_is_owner():
    # Strong owner fallback: private exception wins before any role/admin logic.
    if dashboard_session_is_private_owner(session.get("discord_user") or {}):
        return True
    return dashboard_current_access_level() == "owner"


def dashboard_access_denied_html(message="حسابك ما عنده صلاحية لهذا الجزء من الداشبورد."):
    return render_dashboard_page(
        "Access Denied",
        f"""
        <div class="card danger">
          <h2>🚫 Access Denied</h2>
          <p>{clean_text(message, 500)}</p>
          <p class="muted">Owner يقدر يسوي كل شيء. Admin صلاحياته محدودة.</p>
          <a class="btn" href="/dashboard">Back to Dashboard</a>
          <a class="btn" href="/logout">Logout</a>
        </div>
        """,
        status=403
    )


def dashboard_require_admin():
    if not session.get("discord_user"):
        return redirect("/login")
    if dashboard_current_access_level() not in ("owner", "admin"):
        return dashboard_access_denied_html("حسابك داخل Discord ما عنده صلاحية دخول للداشبورد.")
    return None


def dashboard_require_owner():
    denied = dashboard_require_admin()
    if denied:
        return denied
    if not dashboard_current_user_is_owner():
        return dashboard_access_denied_html("هذه الصفحة أو العملية مخصصة لرتبة Owner فقط.")
    return None


def dashboard_role_badge_html():
    level = dashboard_current_access_level()
    if level == "owner":
        return "<span class='pill ok'>Owner Access</span>"
    if level == "admin":
        return "<span class='pill'>Admin Limited</span>"
    return "<span class='pill bad'>No Access</span>"


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


def dashboard_role_name(role_id, guild_id=0):
    try:
        gid = int(guild_id or 0) or dashboard_current_guild_id_safe()
        guild = bot.get_guild(gid) if bot else None
        if guild:
            role = guild.get_role(int(role_id))
            if role:
                return dashboard_role_chip_for_role(role, include_id=True)
        return f"<span class='rolechip more'>Role {int(role_id)}</span>"
    except:
        return f"<span class='rolechip more'>Role {role_id}</span>"


def dashboard_member_name(user_id):
    return dashboard_member_identity_html(user_id, guild_id=dashboard_current_guild_id_safe(), include_id=True, include_roles=True, compact=False)


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
    return f"🪙 {fmt_num(value)} {nm_coin_name()}"


def money_audit_user_name(user_id):
    try:
        guild = bot.get_guild(GUILD_ID) if bot else None
        member = guild.get_member(int(user_id)) if guild else None
        if member:
            return str(member)
    except:
        pass
    return str(user_id or "Unknown")


def money_audit_source_label(source_type):
    labels = {
        "dashboard_admin_add": "Dashboard admin grant",
        "discord_admin_add": "Discord admin grant",
        "dashboard_bulk_add": "Dashboard give everyone",
        "discord_bulk_add": "Discord give everyone",
        "dashboard_admin_remove": "Dashboard admin remove",
        "discord_admin_remove": "Discord admin remove",
        "dashboard_bulk_remove": "Dashboard take everyone",
        "discord_bulk_remove": "Discord take everyone",
        "dashboard_set": "Dashboard set balance",
        "discord_reset": "Discord reset balance",
        "salary": "Salary",
        "booster_salary": "Booster reward",
        "transfer_in": "Transfer received",
        "transfer_out": "Transfer sent",
        "system_earned": "Earned / system reward",
        "system_spend": "Spend / loss",
    }
    return labels.get(str(source_type or "system"), str(source_type or "system"))


def money_audit_record(user_id, amount, new_balance=0, source_type="system", admin_id=0, admin_name="", details="", batch_id="", user_name=""):
    try:
        user_id = int(user_id or 0)
        amount = int(amount or 0)
        new_balance = int(new_balance or 0)
        source_type = str(source_type or "system")[:80]
        source_label = money_audit_source_label(source_type)[:120]
        if not user_name:
            user_name = money_audit_user_name(user_id)
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS money_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT DEFAULT '',
                amount INTEGER DEFAULT 0,
                new_balance INTEGER DEFAULT 0,
                source_type TEXT DEFAULT 'system',
                source_label TEXT DEFAULT '',
                admin_id INTEGER DEFAULT 0,
                admin_name TEXT DEFAULT '',
                batch_id TEXT DEFAULT '',
                details TEXT DEFAULT '',
                created_at INTEGER
            )
        """)
        cur.execute("""
            INSERT INTO money_audit
            (user_id, user_name, amount, new_balance, source_type, source_label, admin_id, admin_name, batch_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            str(user_name or "")[:140],
            amount,
            new_balance,
            source_type,
            source_label,
            int(admin_id or 0),
            str(admin_name or "")[:140],
            str(batch_id or "")[:140],
            str(details or "")[:1200],
            int(time.time())
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Money audit record error: {e}")


def money_audit_member_summary(user_id):
    try:
        user_id = int(user_id)
        conn = db_connect()
        cur = conn.cursor()
        admin_sources = ("dashboard_admin_add", "discord_admin_add", "dashboard_bulk_add", "discord_bulk_add", "dashboard_set")
        earned_exclude = admin_sources + ("dashboard_admin_remove", "discord_admin_remove", "dashboard_bulk_remove", "discord_bulk_remove", "discord_reset")
        cur.execute(f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM money_audit
            WHERE user_id = ? AND amount > 0 AND source_type IN ({','.join(['?']*len(admin_sources))})
        """, (user_id, *admin_sources))
        admin_received = int(cur.fetchone()[0] or 0)
        cur.execute(f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM money_audit
            WHERE user_id = ? AND amount > 0 AND source_type NOT IN ({','.join(['?']*len(earned_exclude))})
        """, (user_id, *earned_exclude))
        earned_received = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM money_audit WHERE user_id = ? AND amount < 0", (user_id,))
        removed_or_spent = abs(int(cur.fetchone()[0] or 0))
        cur.execute("SELECT COUNT(*) FROM money_audit WHERE user_id = ?", (user_id,))
        entries = int(cur.fetchone()[0] or 0)
        conn.close()
        balance = get_balance(user_id)
        tracked_positive = admin_received + earned_received
        untracked_or_old = balance - tracked_positive
        return {"balance": balance, "admin_received": admin_received, "earned_received": earned_received, "removed_or_spent": removed_or_spent, "entries": entries, "untracked_or_old": untracked_or_old}
    except Exception as e:
        print(f"Money audit summary error: {e}")
        bal = get_balance(user_id)
        return {"balance": bal, "admin_received": 0, "earned_received": 0, "removed_or_spent": 0, "entries": 0, "untracked_or_old": bal}


def money_audit_global_stats():
    try:
        conn = db_connect()
        cur = conn.cursor()
        admin_sources = ("dashboard_admin_add", "discord_admin_add", "dashboard_bulk_add", "discord_bulk_add", "dashboard_set")
        cur.execute(f"""
            SELECT COUNT(DISTINCT user_id), COALESCE(SUM(amount), 0), COUNT(*)
            FROM money_audit
            WHERE amount > 0 AND source_type IN ({','.join(['?']*len(admin_sources))})
        """, admin_sources)
        people, total, entries = cur.fetchone()
        cur.execute("SELECT COUNT(DISTINCT batch_id) FROM money_audit WHERE batch_id != '' AND amount > 0")
        batches = int(cur.fetchone()[0] or 0)
        conn.close()
        return int(people or 0), int(total or 0), int(entries or 0), batches
    except Exception as e:
        print(f"Money audit stats error: {e}")
        return 0, 0, 0, 0


def money_audit_recent_rows(limit=80, user_id=None, admin_only=False, batch_id=""):
    try:
        conn = db_connect()
        cur = conn.cursor()
        query = """
            SELECT id, user_id, user_name, amount, new_balance, source_type, source_label, admin_id, admin_name, batch_id, details, created_at
            FROM money_audit
        """
        clauses = []
        params = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(int(user_id))
        if batch_id:
            clauses.append("batch_id = ?")
            params.append(str(batch_id))
        if admin_only:
            clauses.append("source_type IN ('dashboard_admin_add','discord_admin_add','dashboard_bulk_add','discord_bulk_add','dashboard_set','dashboard_admin_remove','discord_admin_remove','dashboard_bulk_remove','discord_bulk_remove','discord_reset')")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Money audit recent rows error: {e}")
        return []


def money_audit_top_admin_received(limit=10):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, user_name, COALESCE(SUM(amount),0) AS total, COUNT(*) AS entries
            FROM money_audit
            WHERE amount > 0 AND source_type IN ('dashboard_admin_add','discord_admin_add','dashboard_bulk_add','discord_bulk_add','dashboard_set')
            GROUP BY user_id, user_name
            ORDER BY total DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def money_audit_bulk_batches(limit=10):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT batch_id, source_label, admin_name, COUNT(*) AS people, COALESCE(SUM(amount),0) AS total, MAX(created_at) AS last_time
            FROM money_audit
            WHERE batch_id != ''
            GROUP BY batch_id, source_label, admin_name
            ORDER BY MAX(id) DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def parse_int_field(value, default=0, minimum=None):
    try:
        raw = str(value).replace(",", "").strip()
        if raw.lower().startswith("0x"):
            n = int(raw, 16)
        else:
            n = int(raw)
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
    active_warnings = get_warning_history(user_id=int(user_id), status="active", limit=50)
    warning_history = get_warning_history(user_id=int(user_id), status="all", limit=100)
    gid = dashboard_current_guild_id_safe()
    member = dashboard_get_member_in_guild_sync(gid, user_id) or dashboard_get_member_sync(user_id)
    return {
        "user_id": int(user_id),
        "name": dashboard_member_identity_html(user_id, guild_id=gid, include_id=True, include_roles=True),
        "avatar": member.display_avatar.url if member else "",
        "balance": balance,
        "xp": xp,
        "level": level,
        "warnings": active_warnings,
        "warning_history": warning_history,
        "roles": [dashboard_role_chip_for_role(r) for r in member.roles if r.name != "@everyone"] if member else [],
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


def dashboard_merge_settings(updates):
    data = dashboard_load_settings_file()
    if not isinstance(data, dict):
        data = {}
    data.update(updates)
    dashboard_save_settings_file(data)
    return data


def get_dashboard_setting(key, default=None):
    data = dashboard_load_settings_file()
    if isinstance(data, dict) and key in data:
        return data.get(key)
    return default


def dashboard_setting_int_set(key):
    values = get_dashboard_setting(key, [])
    if not isinstance(values, list):
        return set()
    cleaned = set()
    for value in values:
        try:
            cleaned.add(int(value))
        except:
            pass
    return cleaned


def dashboard_dynamic_owner_role_ids():
    return dashboard_setting_int_set("dashboard_owner_role_ids")


def dashboard_dynamic_admin_role_ids():
    return dashboard_setting_int_set("dashboard_admin_role_ids")


def dashboard_dynamic_owner_user_ids():
    return dashboard_setting_int_set("dashboard_owner_user_ids")


def dashboard_dynamic_admin_user_ids():
    return dashboard_setting_int_set("dashboard_admin_user_ids")


def parse_dashboard_role_id_list(values):
    cleaned = []
    seen = set()
    for value in values:
        try:
            role_id = int(value)
        except:
            continue
        if role_id <= 0 or role_id in seen:
            continue
        seen.add(role_id)
        cleaned.append(role_id)
    return cleaned




def parse_dashboard_int_list(values):
    cleaned = []
    seen = set()
    if isinstance(values, str):
        values = values.replace("\n", ",").split(",")
    if not isinstance(values, (list, tuple, set)):
        return cleaned
    for value in values:
        try:
            item = int(str(value).strip())
        except:
            continue
        if item <= 0 or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    return cleaned


def parse_text_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_items = str(value).replace("\r", "\n").replace(",", "\n").split("\n")
    cleaned = []
    seen = set()
    for item in raw_items:
        text = str(item).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text[:120])
    return cleaned

# =========================
# PROTECTION CORE SETTINGS (PER GUILD)
# =========================
raid_join_times = {}

PROTECTION_SETTING_KEYS = [
    "protection_enabled", "bad_words", "links", "invites", "spam", "mass_mentions",
    "anti_bot_join", "anti_raid", "anti_channel_create", "anti_channel_delete", "anti_channel_rename",
    "anti_channel_permission_update", "anti_role_create", "anti_role_delete", "anti_role_permission_update",
    "anti_ban_abuse", "anti_kick_abuse", "anti_webhook_update", "anti_emoji_delete", "anti_guild_update", "anti_invite_delete",
    "delete_messages", "timeouts", "bypass_admins", "log_only",
]


def protection_default_settings():
    return {
        "protection_enabled": True,
        "bad_words": True,
        "links": bool(ANTI_LINKS),
        "invites": True,
        "spam": True,
        "mass_mentions": True,
        "anti_bot_join": False,
        "anti_raid": False,
        "anti_channel_create": False,
        "anti_channel_delete": False,
        "anti_channel_rename": False,
        "anti_channel_permission_update": False,
        "anti_role_create": False,
        "anti_role_delete": False,
        "anti_role_permission_update": False,
        "anti_ban_abuse": False,
        "anti_kick_abuse": False,
        "anti_webhook_update": False,
        "anti_emoji_delete": False,
        "anti_guild_update": False,
        "anti_invite_delete": False,
        "delete_messages": True,
        "timeouts": True,
        "bypass_admins": True,
        "log_only": False,
        "punishment": "timeout_10m",
        "spam_limit": int(SPAM_LIMIT),
        "spam_seconds": int(SPAM_SECONDS),
        "mass_mention_limit": int(MASS_MENTION_LIMIT),
        "raid_join_limit": 8,
        "raid_seconds": 20,
        "quarantine_role_name": "NM Quarantine",
        "link_whitelist": [],
        "ignored_channels": [],
        "ignored_roles": [],
    }


def ensure_guild_protection_table():
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS guild_protection_settings (
                guild_id INTEGER PRIMARY KEY,
                settings_json TEXT DEFAULT '{}',
                updated_at INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Protection table ensure error: {e}")
        return False


def normalize_protection_settings(data=None):
    base = protection_default_settings()
    if isinstance(data, dict):
        base.update(data)

    for key in PROTECTION_SETTING_KEYS:
        base[key] = bool(base.get(key))

    allowed_punishments = {"log_only", "warn", "timeout_10m", "timeout_1h", "quarantine", "kick", "ban"}
    if base.get("punishment") not in allowed_punishments:
        base["punishment"] = "timeout_10m"

    base["spam_limit"] = parse_int_field(base.get("spam_limit"), SPAM_LIMIT, 2)
    base["spam_seconds"] = parse_int_field(base.get("spam_seconds"), SPAM_SECONDS, 1)
    base["mass_mention_limit"] = parse_int_field(base.get("mass_mention_limit"), MASS_MENTION_LIMIT, 1)
    base["raid_join_limit"] = parse_int_field(base.get("raid_join_limit"), 8, 2)
    base["raid_seconds"] = parse_int_field(base.get("raid_seconds"), 20, 5)
    base["quarantine_role_name"] = str(base.get("quarantine_role_name") or "NM Quarantine")[:80]
    base["link_whitelist"] = parse_text_list(base.get("link_whitelist", []))
    base["ignored_channels"] = parse_dashboard_int_list(base.get("ignored_channels", []))
    base["ignored_roles"] = parse_dashboard_int_list(base.get("ignored_roles", []))
    return base


def get_guild_protection_settings(guild_id):
    guild_id = int(guild_id or 0)
    ensure_guild_protection_table()
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("SELECT settings_json FROM guild_protection_settings WHERE guild_id = ?", (guild_id,))
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            try:
                loaded = json.loads(row[0])
            except:
                loaded = {}
            return normalize_protection_settings(loaded)
    except Exception as e:
        print(f"Get guild protection settings error: {e}")
    return normalize_protection_settings({})


def save_guild_protection_settings(guild_id, settings):
    guild_id = int(guild_id or 0)
    settings = normalize_protection_settings(settings)
    ensure_guild_protection_table()
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO guild_protection_settings (guild_id, settings_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                settings_json = excluded.settings_json,
                updated_at = excluded.updated_at
        """, (guild_id, json.dumps(settings, ensure_ascii=False), int(time.time())))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Save guild protection settings error: {e}")
        return False


def protection_channel_ignored_for(settings, channel_id):
    try:
        return int(channel_id or 0) in {int(x) for x in settings.get("ignored_channels", [])}
    except:
        return False


def protection_member_ignored_by_role(settings, member):
    try:
        ignored_roles = {int(x) for x in settings.get("ignored_roles", [])}
        return any(int(role.id) in ignored_roles for role in getattr(member, "roles", []))
    except:
        return False


def protection_link_allowed_for(settings, content):
    text = str(content or "").lower()
    for allowed in settings.get("link_whitelist", []):
        allowed = str(allowed).lower().strip()
        if allowed and allowed in text:
            return True
    return False



def protection_channel_ignored(channel_id):
    try:
        return int(channel_id) in {int(x) for x in PROTECTION_IGNORED_CHANNEL_IDS}
    except:
        return False


def protection_link_allowed(content):
    text = str(content or "").lower()
    for item in PROTECTION_LINK_WHITELIST:
        item = str(item).strip().lower()
        if item and item in text:
            return True
    return False

def dashboard_get_guild_roles():
    guild = bot.get_guild(GUILD_ID) if bot else None
    if not guild:
        return []
    roles = []
    for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
        if role.name == "@everyone":
            continue
        roles.append(role)
    return roles


async def dashboard_chunk_guild_members():
    guild = bot.get_guild(GUILD_ID) if bot else None
    if not guild:
        return []
    try:
        await guild.chunk(cache=True)
    except Exception:
        pass
    return list(guild.members)


def dashboard_get_guild_members_sync(force_chunk=True):
    guild = bot.get_guild(GUILD_ID) if bot else None
    if not guild:
        return []
    if force_chunk:
        try:
            future = asyncio.run_coroutine_threadsafe(dashboard_chunk_guild_members(), bot.loop)
            members = future.result(timeout=12)
            if members:
                return members
        except Exception:
            pass
    try:
        return list(guild.members)
    except Exception:
        return []


def dashboard_members_for_role(role_id):
    role_id = int(role_id)
    members = []
    for member in dashboard_get_guild_members_sync(force_chunk=True):
        try:
            if any(r.id == role_id for r in member.roles):
                members.append(member)
        except Exception:
            pass
    return sorted(members, key=lambda m: str(m.display_name).lower())


def dashboard_member_access_badge(user_id):
    level = dashboard_access_level(int(user_id))
    if int(user_id) in DASHBOARD_PRIVATE_OWNER_USER_IDS:
        return "<span class='pill ok'>Owner</span>"
    if level == "owner":
        return "<span class='pill ok'>Owner</span>"
    if level == "admin":
        return "<span class='pill'>Admin</span>"
    return "<span class='pill bad'>No Access</span>"


def dashboard_member_card_line(member):
    try:
        avatar = member.display_avatar.url
    except Exception:
        avatar = ""
    if avatar:
        avatar_html = f"<img src='{dash_escape(avatar, 300)}' class='miniavatar'>"
    else:
        avatar_html = "<span class='miniavatar blankavatar'>?</span>"
    bot_badge = " <span class='muted small'>BOT</span>" if getattr(member, "bot", False) else ""
    return (
        f"<a class='memberline' href='/dashboard/admin-access/member/{member.id}'>"
        f"{avatar_html}"
        f"<span><b>{dash_escape(member.display_name, 80)}</b>{bot_badge}<br>"
        f"<span class='muted small'>@{dash_escape(str(member), 90)} • ID: <code>{member.id}</code></span>{dashboard_member_roles_html(member, limit=3)}</span>"
        f"<span class='memberbadge'>{dashboard_member_access_badge(member.id)}</span>"
        f"</a>"
    )


def parse_dashboard_user_id_list(values):
    cleaned = []
    seen = set()
    for value in values:
        try:
            user_id = int(str(value).strip())
        except Exception:
            continue
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        cleaned.append(user_id)
    return cleaned


def parse_bool_field(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "enable"}


async def create_or_get_named_role(guild, role_id, role_name, color_int, hoist=True):
    """Find a role by saved ID/name or create it. Returns the role or None."""
    role = None
    try:
        if int(role_id or 0) > 0:
            role = guild.get_role(int(role_id))
    except:
        role = None

    if not role:
        role = discord.utils.get(guild.roles, name=role_name)

    if role:
        try:
            await role.edit(
                name=role_name,
                color=discord.Color(int(color_int)),
                hoist=bool(hoist),
                mentionable=False,
                reason=f"{BOT_BRAND} auto role style refresh"
            )
        except Exception as e:
            print(f"Role edit failed for {role_name}: {e}")
        return role

    try:
        return await guild.create_role(
            name=role_name,
            color=discord.Color(int(color_int)),
            hoist=bool(hoist),
            mentionable=False,
            reason=f"{BOT_BRAND} auto created customizable role"
        )
    except Exception as e:
        print(f"Role create failed for {role_name}: {e}")
        return None


async def ensure_custom_roles(guild):
    """Create/refresh VIP and Event Winner roles and save their IDs."""
    global VIP_ROLE_ID, EVENT_WINNER_ROLE_ID

    vip = await create_or_get_named_role(guild, VIP_ROLE_ID, VIP_ROLE_NAME, VIP_ROLE_COLOR, hoist=True)
    winner = await create_or_get_named_role(guild, EVENT_WINNER_ROLE_ID, EVENT_WINNER_ROLE_NAME, EVENT_WINNER_ROLE_COLOR, hoist=True)

    updates = {}
    if vip:
        VIP_ROLE_ID = int(vip.id)
        updates["VIP_ROLE_ID"] = VIP_ROLE_ID
    if winner:
        EVENT_WINNER_ROLE_ID = int(winner.id)
        updates["EVENT_WINNER_ROLE_ID"] = EVENT_WINNER_ROLE_ID
    if updates:
        dashboard_merge_settings(updates)
    return vip, winner


def record_shop_purchase(user_id, item_key, price):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO shop_purchases (user_id, item_key, price, created_at) VALUES (?, ?, ?, ?)",
            (int(user_id), str(item_key), int(price), int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"record_shop_purchase error: {e}")


def record_lootbox(user_id, price, reward_type, reward_value):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO lootbox_history (user_id, price, reward_type, reward_value, created_at) VALUES (?, ?, ?, ?, ?)",
            (int(user_id), int(price), str(reward_type), str(reward_value), int(time.time()))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"record_lootbox error: {e}")


def add_timed_role_record(user_id, role_id, expires_at, reason=""):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO timed_roles (user_id, role_id, expires_at, reason, active) VALUES (?, ?, ?, ?, 1)",
            (int(user_id), int(role_id), int(expires_at), str(reason)[:200])
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"add_timed_role_record error: {e}")


def create_event_record(event_key, title, prize, starts_at, ends_at, created_by):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO active_events (event_key, title, prize, starts_at, ends_at, created_by, status) VALUES (?, ?, ?, ?, ?, ?, 'active')",
            (str(event_key), str(title), int(prize), int(starts_at), int(ends_at), int(created_by))
        )
        event_id = cur.lastrowid
        conn.commit()
        conn.close()
        return event_id
    except Exception as e:
        print(f"create_event_record error: {e}")
        return None


def get_active_events(limit=10):
    rows = []
    try:
        now = int(time.time())
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("UPDATE active_events SET status='ended' WHERE status='active' AND ends_at <= ?", (now,))
        cur.execute("SELECT id, event_key, title, prize, starts_at, ends_at, created_by, status FROM active_events WHERE status='active' ORDER BY ends_at ASC LIMIT ?", (int(limit),))
        rows = cur.fetchall()
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"get_active_events error: {e}")
    return rows


async def timed_roles_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(20)
    while not bot.is_closed():
        try:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                now = int(time.time())
                conn = db_connect()
                cur = conn.cursor()
                cur.execute("SELECT id, user_id, role_id FROM timed_roles WHERE active=1 AND expires_at <= ?", (now,))
                rows = cur.fetchall()
                for row_id, user_id, role_id in rows:
                    member = guild.get_member(int(user_id))
                    role = guild.get_role(int(role_id))
                    if member and role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason=f"{BOT_BRAND} timed role expired")
                        except Exception as e:
                            print(f"Timed role remove failed: {e}")
                    cur.execute("UPDATE timed_roles SET active=0 WHERE id=?", (int(row_id),))
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Timed roles loop error: {e}")
        await asyncio.sleep(60)


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
    try:
        cc_record_event("dashboard_action", user_id=admin_id, user_name=admin_name, details=f"{action}: {details}")
    except Exception:
        pass
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


# =========================
# COMMAND CENTER / SERVER INTELLIGENCE
# =========================

COMMAND_CENTER_EVENT_LIMIT = 5000


def dash_escape(value, limit=500):
    text = clean_text(str(value or ""), limit)
    return html.escape(text)


def cc_time(unix_time):
    try:
        unix_time = int(unix_time)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(unix_time))
    except:
        return "Unknown"


def cc_since_hours(hours=24):
    return int(time.time()) - (int(hours) * 60 * 60)


def cc_record_event(event_type, user_id=0, user_name="", channel_id=0, channel_name="", amount=0, details=""):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_center_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                user_id INTEGER DEFAULT 0,
                user_name TEXT DEFAULT '',
                channel_id INTEGER DEFAULT 0,
                channel_name TEXT DEFAULT '',
                amount INTEGER DEFAULT 0,
                details TEXT DEFAULT '',
                created_at INTEGER
            )
        """)
        cur.execute("""
            INSERT INTO command_center_events
            (event_type, user_id, user_name, channel_id, channel_name, amount, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(event_type)[:80],
            int(user_id or 0),
            str(user_name or "")[:120],
            int(channel_id or 0),
            str(channel_name or "")[:120],
            int(amount or 0),
            str(details or "")[:1200],
            int(time.time())
        ))

        cur.execute("""
            DELETE FROM command_center_events
            WHERE id NOT IN (
                SELECT id FROM command_center_events
                ORDER BY id DESC
                LIMIT ?
            )
        """, (COMMAND_CENTER_EVENT_LIMIT,))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Command Center event error: {e}")


def cc_count_events(event_type=None, since=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        if event_type:
            cur.execute("SELECT COUNT(*) FROM command_center_events WHERE event_type = ? AND created_at >= ?", (str(event_type), int(since)))
        else:
            cur.execute("SELECT COUNT(*) FROM command_center_events WHERE created_at >= ?", (int(since),))
        count = int(cur.fetchone()[0] or 0)
        conn.close()
        return count
    except:
        return 0


def cc_sum_amount(event_type=None, since=0, positive_only=False, negative_only=False):
    try:
        conn = db_connect()
        cur = conn.cursor()
        query = "SELECT COALESCE(SUM(amount), 0) FROM command_center_events WHERE created_at >= ?"
        params = [int(since)]
        if event_type:
            query += " AND event_type = ?"
            params.append(str(event_type))
        if positive_only:
            query += " AND amount > 0"
        if negative_only:
            query += " AND amount < 0"
        cur.execute(query, tuple(params))
        total = int(cur.fetchone()[0] or 0)
        conn.close()
        return total
    except:
        return 0


def cc_recent_events(limit=80, event_type=None):
    try:
        conn = db_connect()
        cur = conn.cursor()
        if event_type:
            cur.execute("""
                SELECT event_type, user_id, user_name, channel_name, amount, details, created_at
                FROM command_center_events
                WHERE event_type = ?
                ORDER BY id DESC
                LIMIT ?
            """, (str(event_type), int(limit)))
        else:
            cur.execute("""
                SELECT event_type, user_id, user_name, channel_name, amount, details, created_at
                FROM command_center_events
                ORDER BY id DESC
                LIMIT ?
            """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []



def cc_log_channel_ids():
    """Channels excluded from activity analytics so log rooms do not dominate Top Active Channels."""
    ids = set()
    try:
        for value in (LOG_CHANNEL_IDS or {}).values():
            if str(value).isdigit():
                ids.add(int(value))
    except Exception:
        pass
    try:
        for value in (LOG_CHANNEL_NAMES or {}).values():
            # names handled separately in cc_log_channel_names
            pass
    except Exception:
        pass
    return ids


def cc_log_channel_names():
    names = set()
    try:
        names.update(str(name).lower().strip() for name in (LOG_CHANNEL_NAMES or {}).values())
    except Exception:
        pass
    names.update({
        "logs", "log", "audit-log", "audit-logs", "لوق", "لوقات",
        "nm-message-logs", "nm-member-logs", "nm-moderation-logs", "nm-role-logs",
        "nm-channel-logs", "nm-voice-logs", "nm-server-logs", "nm-game-logs", "nm-giveaway-logs",
    })
    return {name for name in names if name}


def cc_log_channel_filter_sql(prefix=""):
    excluded_ids = sorted(cc_log_channel_ids())
    excluded_names = sorted(cc_log_channel_names())
    clauses = []
    params = []
    channel_id_col = f"{prefix}channel_id" if prefix else "channel_id"
    channel_name_col = f"LOWER({prefix}channel_name)" if prefix else "LOWER(channel_name)"
    if excluded_ids:
        placeholders = ",".join(["?"] * len(excluded_ids))
        clauses.append(f"{channel_id_col} NOT IN ({placeholders})")
        params.extend(excluded_ids)
    if excluded_names:
        placeholders = ",".join(["?"] * len(excluded_names))
        clauses.append(f"{channel_name_col} NOT IN ({placeholders})")
        params.extend(excluded_names)
    if not clauses:
        return "", []
    return " AND " + " AND ".join(clauses), params


def cc_count_clean_messages(since=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        extra_sql, extra_params = cc_log_channel_filter_sql()
        cur.execute(
            "SELECT COUNT(*) FROM command_center_events WHERE event_type = 'message' AND created_at >= ? AND channel_name != ''" + extra_sql,
            tuple([int(since)] + extra_params)
        )
        count = int(cur.fetchone()[0] or 0)
        conn.close()
        return count
    except Exception:
        return 0

def cc_top_channels(since=0, limit=8):
    try:
        conn = db_connect()
        cur = conn.cursor()
        extra_sql, extra_params = cc_log_channel_filter_sql()
        cur.execute("""
            SELECT channel_name, COUNT(*)
            FROM command_center_events
            WHERE event_type = 'message' AND created_at >= ? AND channel_name != ''
        """ + extra_sql + """
            GROUP BY channel_name
            ORDER BY COUNT(*) DESC
            LIMIT ?
        """, tuple([int(since)] + extra_params + [int(limit)]))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def cc_top_users_by_event(event_type="message", since=0, limit=8):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, user_name, COUNT(*)
            FROM command_center_events
            WHERE event_type = ? AND created_at >= ? AND user_id != 0
            GROUP BY user_id, user_name
            ORDER BY COUNT(*) DESC
            LIMIT ?
        """, (str(event_type), int(since), int(limit)))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def cc_money_movers(since=0, positive=True, limit=8):
    try:
        conn = db_connect()
        cur = conn.cursor()
        if positive:
            cur.execute("""
                SELECT user_id, user_name, SUM(amount) AS total
                FROM command_center_events
                WHERE event_type = 'money' AND amount > 0 AND created_at >= ? AND user_id != 0
                GROUP BY user_id, user_name
                ORDER BY total DESC
                LIMIT ?
            """, (int(since), int(limit)))
        else:
            cur.execute("""
                SELECT user_id, user_name, SUM(amount) AS total
                FROM command_center_events
                WHERE event_type = 'money' AND amount < 0 AND created_at >= ? AND user_id != 0
                GROUP BY user_id, user_name
                ORDER BY total ASC
                LIMIT ?
            """, (int(since), int(limit)))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def cc_active_warning_rows(limit=10):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, COUNT(*) AS total
            FROM warning_history
            WHERE status = 'active'
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def cc_warning_reason_rows(limit=8):
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT reason, COUNT(*) AS total
            FROM warning_history
            GROUP BY reason
            ORDER BY total DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []


def cc_database_size():
    try:
        path = Path(DB_FILE)
        if not path.exists():
            return "0 KB"
        size_kb = path.stat().st_size / 1024
        if size_kb >= 1024:
            return f"{size_kb / 1024:.2f} MB"
        return f"{size_kb:.2f} KB"
    except:
        return "Unknown"


def cc_bot_uptime_text():
    try:
        seconds = int(time.time() - BOT_STARTED_AT)
        return format_seconds(seconds)
    except:
        return "Unknown"



def cc_guild_snapshot():
    guild = nm_stable_selected_guild()
    if not guild:
        return {
            "guild_ok": False,
            "members": 0,
            "humans": 0,
            "bots": 0,
            "online": 0,
            "voice": 0,
            "text_channels": 0,
            "voice_channels": 0,
        }

    members = list(getattr(guild, "members", []) or [])
    total = int(getattr(guild, "member_count", 0) or len(members) or 0)
    bots = len([m for m in members if getattr(m, "bot", False)])
    humans = max(0, total - bots)
    online = len([m for m in members if not getattr(m, "bot", False) and str(getattr(m, "status", "offline")) != "offline"])
    voice = len([m for m in members if not getattr(m, "bot", False) and getattr(m, "voice", None) and m.voice and m.voice.channel])

    return {
        "guild_ok": True,
        "members": total,
        "humans": humans,
        "bots": bots,
        "online": online,
        "voice": voice,
        "text_channels": len(getattr(guild, "text_channels", []) or []),
        "voice_channels": len(getattr(guild, "voice_channels", []) or []),
    }

def dashboard_selected_guild_stats():
    """Stats shown in the sidebar/top card should be for the currently selected guild only.
    Global bot network totals stay in Owner Console, not in the selected-server sidebar.
    """
    try:
        guild_id = int(session.get("selected_guild_id") or request.args.get("guild_id") or GUILD_ID)
    except:
        guild_id = GUILD_ID

    guild = bot.get_guild(int(guild_id)) if bot else None
    if not guild:
        return {
            "guild_id": int(guild_id or 0),
            "name": "No server selected",
            "servers": 1,
            "users": 0,
            "members": 0,
            "humans": 0,
            "bots": 0,
            "online": 0,
            "voice": 0,
            "text_channels": 0,
            "voice_channels": 0,
            "is_selected": True,
        }

    members = list(getattr(guild, "members", []) or [])
    humans = [m for m in members if not getattr(m, "bot", False)]
    bots_count = len([m for m in members if getattr(m, "bot", False)])
    online = len([m for m in humans if str(getattr(m, "status", "offline")) != "offline"])
    voice = len([m for m in humans if getattr(m, "voice", None) and m.voice and m.voice.channel])

    # If member cache is incomplete, guild.member_count is usually more accurate for total.
    total_members = int(getattr(guild, "member_count", 0) or len(members) or 0)

    return {
        "guild_id": int(guild.id),
        "name": str(guild.name),
        "servers": 1,
        "users": total_members,
        "members": total_members,
        "humans": max(0, total_members - bots_count) if total_members else len(humans),
        "bots": bots_count,
        "online": online,
        "voice": voice,
        "text_channels": len(getattr(guild, "text_channels", []) or []),
        "voice_channels": len(getattr(guild, "voice_channels", []) or []),
        "is_selected": True,
    }



def dashboard_apply_saved_settings():
    global COMMANDS_CHANNEL_ID, GAMBLING_CHANNEL_ID, MEMORY_BACKUP_CHANNEL_ID
    global GAMBLE_COOLDOWN_SECONDS, ECONOMY_EXPLAIN_INTERVAL_SECONDS, BOOSTER_WEEKLY_REWARD, COIN_NAME, ECONOMY_GUIDE_AUTO_ENABLED
    global SHOP_CHANNEL_ID, EVENTS_CHANNEL_ID, BOT_ANNOUNCEMENTS_CHANNEL_ID, GIVEAWAYS_CHANNEL_ID
    global GAME_VOICE_CATEGORY_ID, LOGS_CATEGORY_ID, ECONOMY_EXPLAIN_CHANNEL_ID
    global VIP_ROLE_ID, EVENT_WINNER_ROLE_ID, VIP_ROLE_NAME, EVENT_WINNER_ROLE_NAME, VIP_ROLE_COLOR, EVENT_WINNER_ROLE_COLOR
    global SHOP_ENABLED, EVENTS_ENABLED, SHOP_VIP_PRICE, SHOP_VIP_DAYS, LOOTBOX_PRICE, LOOTBOX_COOLDOWN_SECONDS
    global DEFAULT_EVENT_PRIZE, DEFAULT_EVENT_DURATION_MINUTES, PUBLIC_LEADERBOARD_ENABLED, DAILY_REWARD_BASE, LEVEL_UP_COIN_BONUS
    global protection_enabled, ANTI_LINKS, SPAM_LIMIT, SPAM_SECONDS, MASS_MENTION_LIMIT
    global PROTECTION_BAD_WORDS_ENABLED, PROTECTION_LINKS_ENABLED, PROTECTION_SPAM_ENABLED, PROTECTION_MASS_MENTION_ENABLED
    global PROTECTION_DELETE_MESSAGES, PROTECTION_TIMEOUTS_ENABLED, PROTECTION_BYPASS_ADMINS, PROTECTION_LOG_ONLY_MODE
    global PROTECTION_LINK_WHITELIST, PROTECTION_IGNORED_CHANNEL_IDS
    data = dashboard_load_settings_file()
    if not data:
        return
    COMMANDS_CHANNEL_ID = parse_int_field(data.get("COMMANDS_CHANNEL_ID", COMMANDS_CHANNEL_ID), COMMANDS_CHANNEL_ID, 1)
    GAMBLING_CHANNEL_ID = parse_int_field(data.get("GAMBLING_CHANNEL_ID", GAMBLING_CHANNEL_ID), GAMBLING_CHANNEL_ID, 1)
    MEMORY_BACKUP_CHANNEL_ID = parse_int_field(data.get("MEMORY_BACKUP_CHANNEL_ID", MEMORY_BACKUP_CHANNEL_ID), MEMORY_BACKUP_CHANNEL_ID, 1)
    GIVEAWAYS_CHANNEL_ID = parse_int_field(data.get("GIVEAWAYS_CHANNEL_ID", GIVEAWAYS_CHANNEL_ID), GIVEAWAYS_CHANNEL_ID, 1)
    SHOP_CHANNEL_ID = parse_int_field(data.get("SHOP_CHANNEL_ID", SHOP_CHANNEL_ID), SHOP_CHANNEL_ID, 1)
    EVENTS_CHANNEL_ID = parse_int_field(data.get("EVENTS_CHANNEL_ID", EVENTS_CHANNEL_ID), EVENTS_CHANNEL_ID, 1)
    BOT_ANNOUNCEMENTS_CHANNEL_ID = parse_int_field(data.get("BOT_ANNOUNCEMENTS_CHANNEL_ID", BOT_ANNOUNCEMENTS_CHANNEL_ID), BOT_ANNOUNCEMENTS_CHANNEL_ID, 1)
    ECONOMY_EXPLAIN_CHANNEL_ID = parse_int_field(data.get("ECONOMY_EXPLAIN_CHANNEL_ID", ECONOMY_EXPLAIN_CHANNEL_ID), ECONOMY_EXPLAIN_CHANNEL_ID, 1)
    GAME_VOICE_CATEGORY_ID = parse_int_field(data.get("GAME_VOICE_CATEGORY_ID", GAME_VOICE_CATEGORY_ID), GAME_VOICE_CATEGORY_ID, 1)
    LOGS_CATEGORY_ID = parse_int_field(data.get("LOGS_CATEGORY_ID", LOGS_CATEGORY_ID), LOGS_CATEGORY_ID, 1)
    VIP_ROLE_ID = parse_int_field(data.get("VIP_ROLE_ID", VIP_ROLE_ID), VIP_ROLE_ID, 0)
    EVENT_WINNER_ROLE_ID = parse_int_field(data.get("EVENT_WINNER_ROLE_ID", EVENT_WINNER_ROLE_ID), EVENT_WINNER_ROLE_ID, 0)
    GAMBLE_COOLDOWN_SECONDS = parse_int_field(data.get("GAMBLE_COOLDOWN_SECONDS", GAMBLE_COOLDOWN_SECONDS), GAMBLE_COOLDOWN_SECONDS, 0)
    ECONOMY_EXPLAIN_INTERVAL_SECONDS = parse_int_field(data.get("ECONOMY_EXPLAIN_INTERVAL_SECONDS", ECONOMY_EXPLAIN_INTERVAL_SECONDS), ECONOMY_EXPLAIN_INTERVAL_SECONDS, 60)
    ECONOMY_GUIDE_AUTO_ENABLED = parse_bool_field(data.get("ECONOMY_GUIDE_AUTO_ENABLED", ECONOMY_GUIDE_AUTO_ENABLED), ECONOMY_GUIDE_AUTO_ENABLED)
    BOOSTER_WEEKLY_REWARD = parse_int_field(data.get("BOOSTER_WEEKLY_REWARD", BOOSTER_WEEKLY_REWARD), BOOSTER_WEEKLY_REWARD, 0)
    DAILY_REWARD_BASE = parse_int_field(data.get("DAILY_REWARD_BASE", DAILY_REWARD_BASE), DAILY_REWARD_BASE, 0)
    LEVEL_UP_COIN_BONUS = parse_int_field(data.get("LEVEL_UP_COIN_BONUS", LEVEL_UP_COIN_BONUS), LEVEL_UP_COIN_BONUS, 0)
    SHOP_ENABLED = parse_bool_field(data.get("SHOP_ENABLED", SHOP_ENABLED), SHOP_ENABLED)
    EVENTS_ENABLED = parse_bool_field(data.get("EVENTS_ENABLED", EVENTS_ENABLED), EVENTS_ENABLED)
    SHOP_VIP_PRICE = parse_int_field(data.get("SHOP_VIP_PRICE", SHOP_VIP_PRICE), SHOP_VIP_PRICE, 0)
    SHOP_VIP_DAYS = parse_int_field(data.get("SHOP_VIP_DAYS", SHOP_VIP_DAYS), SHOP_VIP_DAYS, 1)
    LOOTBOX_PRICE = parse_int_field(data.get("LOOTBOX_PRICE", LOOTBOX_PRICE), LOOTBOX_PRICE, 0)
    LOOTBOX_COOLDOWN_SECONDS = parse_int_field(data.get("LOOTBOX_COOLDOWN_SECONDS", LOOTBOX_COOLDOWN_SECONDS), LOOTBOX_COOLDOWN_SECONDS, 0)
    DEFAULT_EVENT_PRIZE = parse_int_field(data.get("DEFAULT_EVENT_PRIZE", DEFAULT_EVENT_PRIZE), DEFAULT_EVENT_PRIZE, 0)
    DEFAULT_EVENT_DURATION_MINUTES = parse_int_field(data.get("DEFAULT_EVENT_DURATION_MINUTES", DEFAULT_EVENT_DURATION_MINUTES), DEFAULT_EVENT_DURATION_MINUTES, 1)
    PUBLIC_LEADERBOARD_ENABLED = parse_bool_field(data.get("PUBLIC_LEADERBOARD_ENABLED", PUBLIC_LEADERBOARD_ENABLED), PUBLIC_LEADERBOARD_ENABLED)

    protection_enabled = parse_bool_field(data.get("protection_enabled", protection_enabled), protection_enabled)
    PROTECTION_BAD_WORDS_ENABLED = parse_bool_field(data.get("PROTECTION_BAD_WORDS_ENABLED", PROTECTION_BAD_WORDS_ENABLED), PROTECTION_BAD_WORDS_ENABLED)
    PROTECTION_LINKS_ENABLED = parse_bool_field(data.get("PROTECTION_LINKS_ENABLED", data.get("ANTI_LINKS", PROTECTION_LINKS_ENABLED)), PROTECTION_LINKS_ENABLED)
    ANTI_LINKS = PROTECTION_LINKS_ENABLED
    PROTECTION_SPAM_ENABLED = parse_bool_field(data.get("PROTECTION_SPAM_ENABLED", PROTECTION_SPAM_ENABLED), PROTECTION_SPAM_ENABLED)
    PROTECTION_MASS_MENTION_ENABLED = parse_bool_field(data.get("PROTECTION_MASS_MENTION_ENABLED", PROTECTION_MASS_MENTION_ENABLED), PROTECTION_MASS_MENTION_ENABLED)
    PROTECTION_DELETE_MESSAGES = parse_bool_field(data.get("PROTECTION_DELETE_MESSAGES", PROTECTION_DELETE_MESSAGES), PROTECTION_DELETE_MESSAGES)
    PROTECTION_TIMEOUTS_ENABLED = parse_bool_field(data.get("PROTECTION_TIMEOUTS_ENABLED", PROTECTION_TIMEOUTS_ENABLED), PROTECTION_TIMEOUTS_ENABLED)
    PROTECTION_BYPASS_ADMINS = parse_bool_field(data.get("PROTECTION_BYPASS_ADMINS", PROTECTION_BYPASS_ADMINS), PROTECTION_BYPASS_ADMINS)
    PROTECTION_LOG_ONLY_MODE = parse_bool_field(data.get("PROTECTION_LOG_ONLY_MODE", PROTECTION_LOG_ONLY_MODE), PROTECTION_LOG_ONLY_MODE)
    SPAM_LIMIT = parse_int_field(data.get("SPAM_LIMIT", SPAM_LIMIT), SPAM_LIMIT, 2)
    SPAM_SECONDS = parse_int_field(data.get("SPAM_SECONDS", SPAM_SECONDS), SPAM_SECONDS, 1)
    MASS_MENTION_LIMIT = parse_int_field(data.get("MASS_MENTION_LIMIT", MASS_MENTION_LIMIT), MASS_MENTION_LIMIT, 1)
    PROTECTION_LINK_WHITELIST = parse_text_list(data.get("PROTECTION_LINK_WHITELIST", PROTECTION_LINK_WHITELIST))
    PROTECTION_IGNORED_CHANNEL_IDS = set(parse_dashboard_int_list(data.get("PROTECTION_IGNORED_CHANNEL_IDS", list(PROTECTION_IGNORED_CHANNEL_IDS))))

    if str(data.get("COIN_NAME", "")).strip():
        COIN_NAME = str(data.get("COIN_NAME")).strip()[:40]
    if str(data.get("VIP_ROLE_NAME", "")).strip():
        VIP_ROLE_NAME = str(data.get("VIP_ROLE_NAME")).strip()[:80]
    if str(data.get("EVENT_WINNER_ROLE_NAME", "")).strip():
        EVENT_WINNER_ROLE_NAME = str(data.get("EVENT_WINNER_ROLE_NAME")).strip()[:80]
    VIP_ROLE_COLOR = parse_int_field(str(data.get("VIP_ROLE_COLOR", VIP_ROLE_COLOR)).replace("#", "0x"), VIP_ROLE_COLOR, 0)
    EVENT_WINNER_ROLE_COLOR = parse_int_field(str(data.get("EVENT_WINNER_ROLE_COLOR", EVENT_WINNER_ROLE_COLOR)).replace("#", "0x"), EVENT_WINNER_ROLE_COLOR, 0)


dashboard_apply_saved_settings()

# =========================
# GLOBAL BOT STATS / PUBLIC COUNTERS
# =========================

DASHBOARD_STATS_CACHE = {"at": 0, "data": None}
DASHBOARD_STATS_CACHE_SECONDS = 20


def dashboard_global_bot_stats(force=False):
    """Fast cached bot-wide counters for dashboard/public status pages."""
    now = time.time()
    cached = DASHBOARD_STATS_CACHE.get("data")
    if not force and cached and now - int(DASHBOARD_STATS_CACHE.get("at", 0)) < DASHBOARD_STATS_CACHE_SECONDS:
        return cached

    try:
        guilds = list(bot.guilds) if bot else []
    except Exception:
        guilds = []

    total_guilds = len(guilds)
    total_members = 0
    total_humans = 0
    total_bots = 0
    total_online = 0
    total_text = 0
    total_voice = 0

    for guild in guilds:
        try:
            # member_count is instant and does not require walking every cached member.
            member_count = int(getattr(guild, "member_count", 0) or 0)
            members = list(getattr(guild, "members", []) or [])
            bot_count = sum(1 for m in members if getattr(m, "bot", False))
            human_count = max(0, member_count - bot_count) if member_count else sum(1 for m in members if not getattr(m, "bot", False))

            total_members += member_count or len(members)
            total_humans += human_count
            total_bots += bot_count
            total_online += sum(1 for m in members if not getattr(m, "bot", False) and str(getattr(m, "status", "offline")) != "offline")
            total_text += len(getattr(guild, "text_channels", []) or [])
            total_voice += len(getattr(guild, "voice_channels", []) or [])
        except Exception:
            pass

    data = {
        "guilds": total_guilds,
        "members": total_members,
        "humans": total_humans,
        "bots": total_bots,
        "online": total_online,
        "text_channels": total_text,
        "voice_channels": total_voice,
    }
    DASHBOARD_STATS_CACHE["at"] = now
    DASHBOARD_STATS_CACHE["data"] = data
    return data



def dashboard_global_stats_html(compact=False):
    if compact:
        members = nm_stable_selected_member_count()
        return f"""
        <div class="globalstats compact">
          <div><b>1</b><span>Server</span></div>
          <div><b>{members:,}</b><span>Members</span></div>
        </div>
        """

    stats = dashboard_global_bot_stats()
    return f"""
    <div class="grid">
      <div class="card stat"><div class="icon">🌍</div><div class="num">{stats['guilds']:,}</div><div class="label">Servers using the bot</div></div>
      <div class="card stat"><div class="icon">👥</div><div class="num">{stats['humans']:,}</div><div class="label">Human users across all servers</div></div>
      <div class="card stat"><div class="icon">🟢</div><div class="num">{stats['online']:,}</div><div class="label">Online users currently cached</div></div>
      <div class="card stat"><div class="icon">📡</div><div class="num">{stats['text_channels']:,} / {stats['voice_channels']:,}</div><div class="label">Text / Voice channels</div></div>
    </div>
    """

def dashboard_guild_initials(name):
    try:
        parts = [x for x in re.split(r"\s+", str(name or "")) if x]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()
    except Exception:
        return "?"


def dashboard_guild_access_label(guild_id):
    try:
        guild_id = int(guild_id)
        if dashboard_current_user_is_owner():
            return "Bot Owner", "owner"
        perms, is_owner = dashboard_oauth_guild_permissions(guild_id)
        if is_owner:
            return "Server Owner", "owner"
        if perms & 0x8:
            return "Administrator", "admin"
        if perms & 0x20:
            return "Manage Server", "admin"
        return "No Access", "none"
    except Exception:
        return "Unknown", "none"


def dashboard_guild_setup_state(guild):
    try:
        settings = get_guild_settings(int(guild.id))
        missing = []
        if not int(settings.get("commands_channel_id") or 0):
            missing.append("commands")
        if not int(settings.get("gambling_channel_id") or 0):
            missing.append("gambling")
        if not int(settings.get("logs_category_id") or 0):
            missing.append("logs")
        me = guild.me or guild.get_member(bot.user.id) if bot and bot.user else None
        perms = me.guild_permissions if me else None
        if perms:
            if not perms.manage_channels:
                missing.append("manage channels")
            if not perms.embed_links:
                missing.append("embeds")
            if not perms.view_audit_log:
                missing.append("audit log")
        if missing:
            return "Needs Setup", "warn", ", ".join(missing[:3])
        return "Ready", "ok", "setup complete"
    except Exception:
        return "Unknown", "warn", "could not inspect"


def dashboard_visible_bot_guilds_for_current_user(limit=80):
    try:
        all_guilds = sorted(list(bot.guilds), key=lambda g: str(g.name).lower()) if bot else []
    except Exception:
        all_guilds = []

    if dashboard_current_user_is_owner():
        return all_guilds[:int(limit)]

    visible = []
    bot_ids = dashboard_bot_guild_ids()
    for item in dashboard_user_guilds():
        try:
            gid = int(item.get("id"))
            if gid not in bot_ids:
                continue
            if not dashboard_has_manage_guild_oauth(gid):
                continue
            guild = bot.get_guild(gid) if bot else None
            if guild:
                visible.append(guild)
        except Exception:
            pass
    visible = sorted(visible, key=lambda g: str(g.name).lower())
    return visible[:int(limit)]


def dashboard_server_rail_html():
    user = session.get("discord_user")
    if not user:
        return ""

    guilds = dashboard_visible_bot_guilds_for_current_user(limit=90)
    active_id = int(nm_stable_selected_guild_id())

    items = []
    # Home/account button
    avatar = ""
    try:
        uid = str(user.get("id") or "")
        av = str(user.get("avatar") or "")
        if uid and av:
            avatar = f"https://cdn.discordapp.com/avatars/{uid}/{av}.png?size=64"
    except Exception:
        avatar = ""
    if avatar:
        account_inner = f"<img src='{avatar}' alt='me'>"
    else:
        account_inner = "👤"
    items.append(f"<a class='serverbubble account' href='/dashboard' title='Dashboard'>{account_inner}</a>")
    items.append("<div class='serversep'></div>")

    for guild in guilds:
        try:
            gid = int(guild.id)
            active = " active" if gid == active_id else ""
            label, access_class = dashboard_guild_access_label(gid)
            state_text, state_class, state_tip = dashboard_guild_setup_state(guild)
            title = f"{dash_escape(guild.name, 80)} • {label} • {state_text}: {dash_escape(state_tip, 80)}"
            if guild.icon:
                inner = f"<img src='{guild.icon.url}' alt='{dash_escape(guild.name, 40)}'>"
            else:
                inner = f"<span>{dashboard_guild_initials(guild.name)}</span>"
            crown = "<em>👑</em>" if access_class == "owner" else ""
            items.append(
                f"<a class='serverbubble {state_class}{active}' href='/dashboard/select-guild/{gid}' title='{title}'>"
                f"{inner}<i></i>{crown}</a>"
            )
        except Exception:
            pass

    if dashboard_current_user_is_owner():
        items.append("<div class='serversep'></div>")
        items.append("<a class='serverbubble ownerbtn' href='/dashboard/owner-console' title='Owner Console'>👑</a>")

    return "<aside class='serverrail'>" + "".join(items) + "</aside>"



# =========================
# NM DISCORD BACKUP RECOVERY
# يسترجع آخر ملفات الباك أب من روم memory backup إلى /data + local
# بدون ما يكتب فوق ملف فيه بيانات بملف فاضي
# =========================

def nm_recovery_score(path):
    try:
        p = Path(path)
        if not p.exists():
            return 0
        if p.suffix.lower() == ".db":
            try:
                conn = sqlite3.connect(str(p))
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                score = len(tables)
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        score += int(cur.fetchone()[0] or 0)
                    except Exception:
                        pass
                conn.close()
                return score
            except Exception:
                return p.stat().st_size
        if p.suffix.lower() == ".json":
            try:
                import json
                raw = p.read_text(encoding="utf-8")
                if not raw.strip():
                    return 0
                data = json.loads(raw)
                if isinstance(data, dict):
                    return len(data)
                if isinstance(data, list):
                    return len(data)
                return 1
            except Exception:
                return p.stat().st_size
        return p.stat().st_size
    except Exception:
        return 0


async def nm_restore_latest_discord_memory_backup(reason="startup"):
    """Pull latest backup attachments from Discord memory channel into persistent storage."""
    try:
        files = globals().get("NM_MEMORY_FILES", [
            "nm_system.db",
            "warnings.json",
            "log_channels.json",
            "dashboard_settings.json",
            "protection_settings.json",
            "guild_settings.json",
            "money_audit.json",
        ])

        channel_id = int(globals().get("MEMORY_BACKUP_CHANNEL_ID", 0) or 0)
        if not channel_id:
            print("⚠️ NM recovery: MEMORY_BACKUP_CHANNEL_ID is missing.")
            return

        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as e:
                print(f"⚠️ NM recovery: cannot fetch memory backup channel {channel_id}: {e}")
                return

        found = {}
        async for msg in channel.history(limit=120):
            for att in getattr(msg, "attachments", []) or []:
                name = str(getattr(att, "filename", "") or "")
                if name in files and name not in found:
                    found[name] = att
            if len(found) >= len(files):
                break

        if not found:
            print("⚠️ NM recovery: no backup attachments found in memory channel.")
            return

        restored = []
        skipped = []

        data_dir = Path(globals().get("NM_DATA_DIR", "/data"))
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            data_dir = Path(".")

        for filename, att in found.items():
            data_target = data_dir / filename
            local_target = Path(filename)
            temp_target = data_dir / f".incoming_{filename}"

            try:
                await att.save(str(temp_target))
            except Exception as e:
                print(f"⚠️ NM recovery: failed downloading {filename}: {e}")
                continue

            incoming_score = nm_recovery_score(temp_target)
            data_score = nm_recovery_score(data_target)
            local_score = nm_recovery_score(local_target)
            best_existing = max(data_score, local_score)

            # Only restore if incoming is useful and existing is empty/weaker.
            if incoming_score > 0 and incoming_score >= best_existing:
                try:
                    shutil.copy2(temp_target, data_target)
                    shutil.copy2(temp_target, local_target)
                    restored.append(f"{filename} incoming={incoming_score} old={best_existing}")
                except Exception as e:
                    print(f"⚠️ NM recovery: failed applying {filename}: {e}")
            else:
                skipped.append(f"{filename} incoming={incoming_score} existing={best_existing}")

            try:
                temp_target.unlink(missing_ok=True)
            except Exception:
                pass

        if restored:
            print("✅ NM recovery restored backups:", "; ".join(restored))
            # Reload dashboard settings if the project has a loader.
            try:
                if "load_dashboard_settings" in globals():
                    globals()["dashboard_settings"] = load_dashboard_settings()
            except Exception:
                pass
            try:
                if "load_log_channels" in globals():
                    globals()["log_channels"] = load_log_channels()
            except Exception:
                pass
        if skipped:
            print("ℹ️ NM recovery skipped:", "; ".join(skipped))
    except Exception as e:
        print(f"❌ NM recovery fatal error: {e}")


@app.route("/dashboard/recover-memory-backup")
def nm_manual_recover_memory_backup_page():
    try:
        if bot and getattr(bot, "loop", None) and bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(nm_restore_latest_discord_memory_backup("manual dashboard recovery"), bot.loop)
            return "<h2>Recovery started</h2><p>Wait 10 seconds, then refresh dashboard.</p><a href='/dashboard'>Back</a>"
    except Exception as e:
        return f"<h2>Recovery failed</h2><pre>{dash_escape(str(e), 1000)}</pre>"
    return "<h2>Recovery unavailable</h2><p>Bot loop is not ready.</p>"


@app.route('/dashboard/select-guild/<int:guild_id>')
def dashboard_select_guild(guild_id):
    denied = dashboard_require_admin()
    if denied:
        return denied
    if not dashboard_can_manage_guild(int(guild_id)):
        return dashboard_access_denied_html("ما عندك صلاحية إدارة هذا السيرفر من الداشبورد.")
    dashboard_set_active_guild(int(guild_id))
    # افتح setup للسيرفر المختار عشان يكون واضح وش السيرفر اللي تتحكم فيه.
    return redirect(f"/dashboard/guild/{int(guild_id)}/setup")




def dashboard_active_guild_stats():
    gid = nm_stable_selected_guild_id()
    guild = bot.get_guild(int(gid)) if bot else None
    if not guild:
        return {
            "guild_id": int(gid or 0),
            "name": "Selected Server",
            "servers": 1,
            "server_count": 1,
            "users": 0,
            "members": 0,
            "member_count": 0,
        }

    member_count = int(getattr(guild, "member_count", 0) or len(getattr(guild, "members", []) or []) or 0)
    return {
        "guild_id": int(guild.id),
        "name": str(guild.name),
        "servers": 1,
        "server_count": 1,
        "users": member_count,
        "members": member_count,
        "member_count": member_count,
    }

def dashboard_selected_server_count():
    return 1



def dashboard_selected_member_count():
    return nm_stable_selected_member_count()

def nm_db_table_count(table_name):
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_ensure_guild_column(cur, table_name)
        cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE guild_id = ?", (nm_active_guild_id(),))
        count = int(cur.fetchone()[0] or 0)
        conn.commit()
        conn.close()
        return count
    except Exception:
        try:
            return db_table_count(table_name)
        except:
            return 0


def nm_db_sum_column(table_name, column_name):
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_ensure_guild_column(cur, table_name)
        cur.execute(f"SELECT COALESCE(SUM({column_name}), 0) FROM {table_name} WHERE guild_id = ?", (nm_active_guild_id(),))
        total = int(cur.fetchone()[0] or 0)
        conn.commit()
        conn.close()
        return total
    except Exception:
        try:
            return db_sum_column(table_name, column_name)
        except:
            return 0

DASHBOARD_BASE_TEMPLATE = r'''
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} • {{ brand }}</title>
  <style>
    :root{--bg:#050714;--bg2:#0a1022;--panel:rgba(14,20,37,.78);--panel2:rgba(20,29,52,.86);--glass:rgba(255,255,255,.055);--glass2:rgba(255,255,255,.085);--text:#f8fbff;--muted:#94a3b8;--line:rgba(148,163,184,.16);--line2:rgba(148,163,184,.25);--blue:#5865f2;--purple:#8b5cf6;--pink:#ec4899;--green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--cyan:#06b6d4;--shadow:0 18px 44px rgba(0,0,0,.30);--soft:0 10px 24px rgba(0,0,0,.18)}
    *{box-sizing:border-box} html{scroll-behavior:smooth} body{margin:0;min-height:100vh;overflow-x:hidden;color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;background:radial-gradient(circle at 12% -10%,rgba(88,101,242,.35),transparent 34%),radial-gradient(circle at 92% 0%,rgba(139,92,246,.28),transparent 32%),radial-gradient(circle at 50% 110%,rgba(6,182,212,.12),transparent 28%),linear-gradient(180deg,#091021 0%,#050714 100%)}
    body:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 70% 10%,rgba(88,101,242,.08),transparent 30%);opacity:.8}
    a{color:inherit;text-decoration:none} code{background:rgba(2,6,23,.9);border:1px solid var(--line);padding:3px 7px;border-radius:9px;color:#dbeafe;word-break:break-word}
    .layout{display:grid;grid-template-columns:74px 290px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:20px 18px;border-right:1px solid var(--line);background:linear-gradient(180deg,rgba(7,10,18,.92),rgba(7,10,18,.72));overflow-y:auto;overflow-x:hidden}.sidebar::-webkit-scrollbar{width:8px}.sidebar::-webkit-scrollbar-thumb{background:rgba(148,163,184,.2);border-radius:999px}
    .serverrail{position:sticky;top:0;height:100vh;padding:14px 10px;border-right:1px solid var(--line);background:rgba(3,7,18,.72);display:flex;flex-direction:column;align-items:center;gap:10px;overflow-y:auto;overflow-x:hidden}.serverrail::-webkit-scrollbar{width:0}.serverbubble{width:50px;height:50px;border-radius:18px;display:grid;place-items:center;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.08);position:relative;transition:.16s ease;color:#fff;font-weight:1000}.serverbubble img{width:100%;height:100%;border-radius:18px;object-fit:cover}.serverbubble span{font-size:15px}.serverbubble:hover{border-radius:15px;transform:translateY(-1px);background:rgba(88,101,242,.18);border-color:rgba(139,92,246,.38)}.serverbubble.active{border-radius:15px;box-shadow:0 0 0 3px rgba(88,101,242,.24);border-color:rgba(139,92,246,.55)}.serverbubble.active:before{content:'';position:absolute;left:-9px;top:11px;bottom:11px;width:4px;border-radius:999px;background:#fff}.serverbubble i{position:absolute;right:-2px;bottom:-2px;width:13px;height:13px;border-radius:999px;border:3px solid #050714;background:#f59e0b}.serverbubble.ok i{background:#22c55e}.serverbubble.bad i{background:#ef4444}.serverbubble.warn i{background:#f59e0b}.serverbubble em{position:absolute;right:-6px;top:-6px;font-style:normal;font-size:13px;background:rgba(15,23,42,.96);border:1px solid var(--line);border-radius:999px;width:22px;height:22px;display:grid;place-items:center}.serversep{width:34px;height:1px;background:var(--line);margin:2px 0}.serverbubble.account{margin-bottom:2px}.serverbubble.ownerbtn{background:linear-gradient(135deg,rgba(245,158,11,.28),rgba(139,92,246,.16));}
    .brand{display:flex;align-items:center;gap:13px;padding:10px 7px 20px;margin-bottom:4px}.logo{width:58px;height:58px;border-radius:22px;background:linear-gradient(135deg,#5865f2,#8b5cf6 58%,#ec4899);display:grid;place-items:center;font-size:29px;box-shadow:0 24px 55px rgba(88,101,242,.32);position:relative}.logo:after{content:"";position:absolute;inset:-1px;border-radius:23px;border:1px solid rgba(255,255,255,.22)}.brand h1{font-size:23px;margin:0;letter-spacing:-.35px}.brand p{margin:5px 0 0;color:var(--muted);font-size:12px}
    .navsection{margin:14px 0 8px;padding:0 8px;color:#64748b;font-size:10px;letter-spacing:.15em;text-transform:uppercase;font-weight:1000}.navlist{display:grid;gap:7px}.navitem{display:flex;align-items:center;gap:11px;padding:12px 13px;border:1px solid transparent;border-radius:17px;color:#cbd5e1;font-weight:900;letter-spacing:-.1px;position:relative;transition:.18s ease}.navicon{width:28px;height:28px;border-radius:11px;display:grid;place-items:center;background:rgba(255,255,255,.06);box-shadow:inset 0 0 0 1px rgba(255,255,255,.06)}.navitem:hover{background:rgba(255,255,255,.06);border-color:var(--line);transform:translateX(2px)}.navitem.active{background:linear-gradient(135deg,rgba(88,101,242,.26),rgba(139,92,246,.18));border-color:rgba(139,92,246,.38);color:#fff;box-shadow:0 12px 30px rgba(88,101,242,.12)}.navitem.active:before{content:"";position:absolute;left:-18px;top:12px;bottom:12px;width:4px;border-radius:999px;background:linear-gradient(180deg,#8b5cf6,#06b6d4)}.ownerlock{margin-left:auto;font-size:11px;color:#fbbf24}.navfoot{margin-top:22px;padding:14px;border:1px solid var(--line);border-radius:22px;background:rgba(15,23,42,.52);box-shadow:var(--soft)}.userbox{display:flex;gap:10px;align-items:center;margin-bottom:11px}.userdot{width:36px;height:36px;border-radius:14px;background:linear-gradient(135deg,#312e81,#8b5cf6);display:grid;place-items:center}.userbox b{display:block}.userbox span{font-size:12px;color:var(--muted)}
    .main{padding:26px;max-width:1540px;width:100%;min-width:0;margin:0 auto}.topbar{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;gap:14px}.headline h2{font-size:34px;line-height:1.05;margin:0;letter-spacing:-.85px}.headline p{color:var(--muted);margin:8px 0 0}.actions{display:flex;gap:10px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:rgba(20,29,52,.82);padding:10px 14px;border-radius:15px;color:var(--text);display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-weight:950;box-shadow:0 10px 30px rgba(0,0,0,.16);transition:.16s ease}.btn.primary{background:linear-gradient(135deg,var(--blue),var(--purple));border-color:transparent}.btn.green{background:linear-gradient(135deg,#15803d,#22c55e);border-color:transparent}.btn.red{background:linear-gradient(135deg,#991b1b,#ef4444);border-color:transparent}.btn:hover{transform:translateY(-1px);filter:brightness(1.08)}
    .grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:linear-gradient(180deg,var(--panel),rgba(10,16,31,.92));border:1px solid var(--line);border-radius:26px;padding:19px;box-shadow:var(--shadow);min-width:0;overflow:hidden}.card h3{margin:0 0 13px;font-size:18px;letter-spacing:-.25px}.stat{position:relative;overflow:hidden}.stat:after{content:"";position:absolute;right:-20px;top:-20px;width:100px;height:100px;border-radius:999px;background:linear-gradient(135deg,rgba(88,101,242,.18),rgba(6,182,212,.08))}.stat .icon{font-size:24px}.stat .num{font-size:34px;font-weight:1000;margin-top:10px;letter-spacing:-.8px}.stat .label{color:var(--muted);font-size:13px;margin-top:4px}.muted{color:var(--muted)}.small{font-size:12px}.toast{padding:13px 15px;border-radius:17px;border:1px solid var(--line);margin-bottom:14px;font-weight:900}.toast.ok{background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.3)}.toast.bad{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.3)}
    .tablewrap{width:100%;overflow-x:auto}.table{width:100%;border-collapse:separate;border-spacing:0 8px}.table th{color:var(--muted);font-size:11px;text-transform:uppercase;text-align:left;padding:0 10px;white-space:nowrap}.table td{padding:12px 10px;background:rgba(15,23,42,.56);border-top:1px solid var(--line);border-bottom:1px solid var(--line);vertical-align:top}.table td:first-child{border-left:1px solid var(--line);border-radius:14px 0 0 14px}.table td:last-child{border-right:1px solid var(--line);border-radius:0 14px 14px 0}.pill{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:rgba(88,101,242,.15);color:#dbeafe;font-size:12px;font-weight:950;border:1px solid rgba(88,101,242,.22);white-space:nowrap}.pill.ok{background:rgba(34,197,94,.16);color:#dcfce7;border-color:rgba(34,197,94,.25)}.pill.bad{background:rgba(239,68,68,.16);color:#fee2e2;border-color:rgba(239,68,68,.25)}.pill.gold{background:rgba(245,158,11,.16);color:#fef3c7;border-color:rgba(245,158,11,.25)}.pill.cyan{background:rgba(6,182,212,.14);color:#cffafe;border-color:rgba(6,182,212,.25)}
    .formgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.formbox{background:rgba(15,23,42,.62);border:1px solid var(--line);border-radius:22px;padding:15px}label{display:block;color:var(--muted);font-size:12px;margin:10px 0 6px;font-weight:900}input,select,textarea{width:100%;background:rgba(2,6,23,.78);color:var(--text);border:1px solid var(--line);border-radius:15px;padding:12px;outline:none}input:focus,select:focus,textarea:focus{border-color:rgba(88,101,242,.75);box-shadow:0 0 0 3px rgba(88,101,242,.12)}.hero{display:grid;grid-template-columns:1.4fr .8fr;gap:14px;margin-bottom:14px}.hero .big{font-size:44px;font-weight:1000;letter-spacing:-1.4px}.danger{border-color:rgba(239,68,68,.38)}.footer{color:var(--muted);text-align:center;font-size:12px;margin-top:18px}.prodivider{height:1px;background:linear-gradient(90deg,transparent,var(--line2),transparent);margin:14px 0}
    .switchgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.switchcard{padding:14px;border:1px solid rgba(255,255,255,.10);border-radius:16px;background:rgba(255,255,255,.04)}.toggleline{display:flex;align-items:center;justify-content:space-between;gap:10px}.switch{width:52px;height:28px;border-radius:999px;background:#3b4252;position:relative;display:inline-block}.switch input{display:none}.slider{position:absolute;cursor:pointer;inset:0;border-radius:999px}.slider:before{content:"";position:absolute;height:22px;width:22px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s}.switch input:checked+.slider{background:#22c55e}.switch input:checked+.slider:before{transform:translateX(24px)}.dangerzone{border-color:rgba(239,68,68,.55);background:rgba(239,68,68,.08)}

    .globalstats{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0;padding:10px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.045)}.globalstats div{padding:8px;border-radius:14px;background:rgba(15,23,42,.45);text-align:center}.globalstats b{display:block;font-size:22px;letter-spacing:-.4px}.globalstats span{display:block;color:var(--muted);font-size:11px;font-weight:900;text-transform:uppercase;margin-top:2px}.globalstats.compact{grid-template-columns:1fr 1fr}
    .card,.navitem,.btn{will-change:auto}.card{content-visibility:auto;contain-intrinsic-size:260px}.sidebar .card{content-visibility:visible}.navitem span:nth-child(2){overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tablewrap{border-radius:18px}.quickgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.guildlist{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.compactnote{padding:10px 12px;border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.04);color:var(--muted);font-size:12px}

    .membercard{display:flex;align-items:flex-start;gap:10px;max-width:420px;min-width:0;overflow:hidden}.memberavatar{width:38px;height:38px;border-radius:14px;object-fit:cover;flex:0 0 auto;background:rgba(88,101,242,.16);display:grid;place-items:center}.memberavatar.blank{display:grid;place-items:center;color:#c4b5fd;font-weight:1000}.membermeta{min-width:0;display:grid;gap:3px}.membermeta b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:320px}.userline{display:block;color:var(--muted);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:360px}.mini-member{display:inline-flex;align-items:center;gap:6px;vertical-align:middle;border:1px solid rgba(88,101,242,.28);background:rgba(88,101,242,.12);color:#dbeafe;border-radius:999px;padding:3px 8px;font-weight:900;font-size:12px;max-width:260px;overflow:hidden}.mini-member img{width:18px;height:18px;border-radius:50%;object-fit:cover;flex:0 0 auto}.mini-member span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.memberroles{display:flex;gap:5px;flex-wrap:wrap;margin-top:4px}.rolechip{display:inline-flex;align-items:center;gap:5px;border:1px solid rgba(148,163,184,.20);background:rgba(15,23,42,.70);border-radius:999px;padding:3px 7px;font-size:11px;font-weight:900;max-width:180px}.role-dot{width:8px;height:8px;border-radius:999px;flex:0 0 auto}.role-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rolechip.owner{border-color:rgba(245,158,11,.35);background:rgba(245,158,11,.10)}.rolechip.admin{border-color:rgba(88,101,242,.35);background:rgba(88,101,242,.12)}.rolechip.more{color:var(--muted)}
    @media(max-width:1100px){.layout{grid-template-columns:1fr}.serverrail{position:relative;height:auto;flex-direction:row;justify-content:flex-start;overflow-x:auto;overflow-y:hidden}.sidebar{position:relative;height:auto}.grid,.grid2,.grid3,.hero,.formgrid{grid-template-columns:1fr}.topbar{align-items:flex-start;flex-direction:column}.main{padding:16px}.headline h2{font-size:26px}.hero .big{font-size:32px}.navfoot{margin-bottom:0}.guildlist{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div class="layout">
  {{ server_rail|safe }}
  <aside class="sidebar">
    <div class="brand"><div class="logo">⚙️</div><div><h1>{{ brand }}</h1><p>Fast selected-server control panel</p></div></div>
    {{ global_stats_compact|safe }}
    <nav class="navlist">
      <div class="navsection">Monitor</div>
      <a class="navitem" href="/dashboard"><span class="navicon">🏠</span><span>Overview</span></a>
      <a class="navitem" href="/dashboard/guilds"><span class="navicon">🌍</span><span>Guilds</span></a>
      <a class="navitem" href="/dashboard/command-center"><span class="navicon">🧠</span><span>Command Center</span></a>
      <a class="navitem" href="/dashboard/log-vault"><span class="navicon">🗄️</span><span>Log Vault</span></a>
      <a class="navitem" href="/dashboard/user"><span class="navicon">👤</span><span>User Lookup</span></a>
      <a class="navitem" href="/dashboard/warnings"><span class="navicon">⚠️</span><span>Warnings</span></a>
      {% if access_level == 'owner' %}<a class="navitem" href="/dashboard/protection"><span class="navicon">🛡️</span><span>Protection</span><span class="ownerlock">Owner</span></a>{% endif %}
      <div class="navsection">Systems</div>
      <a class="navitem" href="/dashboard/economy"><span class="navicon">🪙</span><span>Economy</span></a>
      {% if access_level == 'owner' %}<a class="navitem" href="/dashboard/money-audit"><span class="navicon">🏦</span><span>Money Audit</span><span class="ownerlock">Owner</span></a>{% endif %}
      <a class="navitem" href="/dashboard/levels"><span class="navicon">📊</span><span>Levels</span></a>
      <a class="navitem" href="/dashboard/casino"><span class="navicon">🎰</span><span>Casino</span></a>
      <a class="navitem" href="/dashboard/shop"><span class="navicon">🛒</span><span>Shop</span></a>
      <a class="navitem" href="/dashboard/events"><span class="navicon">🎉</span><span>Events</span></a>
      <a class="navitem" href="/dashboard/memory"><span class="navicon">💾</span><span>Memory</span></a>
      <div class="navsection">Owner Tools</div>
      {% if access_level == 'owner' %}
      <a class="navitem" href="/dashboard/owner-console"><span class="navicon">👑</span><span>Owner Console</span><span class="ownerlock">Owner</span></a>
      <a class="navitem" href="/dashboard/admin-access"><span class="navicon">🔐</span><span>Admin Access</span><span class="ownerlock">Owner</span></a>
      <a class="navitem" href="/dashboard/control"><span class="navicon">🛡️</span><span>Control Center</span><span class="ownerlock">Owner</span></a>
      <a class="navitem" href="/dashboard/audit"><span class="navicon">🕵️</span><span>Audit Center</span><span class="ownerlock">Owner</span></a>
      <a class="navitem" href="/dashboard/settings"><span class="navicon">⚙️</span><span>Settings</span><span class="ownerlock">Owner</span></a>
      <a class="navitem" href="/oauth_debug"><span class="navicon">🧪</span><span>OAuth Debug</span><span class="ownerlock">Owner</span></a>
      {% else %}
      <div class="card" style="padding:12px;border-radius:18px;background:rgba(245,158,11,.08);box-shadow:none"><span class="pill gold">Owner tools hidden</span><p class="muted small" style="margin:8px 0 0">Admin Limited يشوف المراقبة والإدارة الأساسية فقط.</p></div>
      {% endif %}
    </nav>
    <div class="navfoot">
      {% if user %}
      <div class="userbox"><div class="userdot">👤</div><div><b>{{ user.get('username') }}</b><span>{{ role_badge|safe }}</span></div></div>
      <a class="btn" href="/logout">Logout</a>
      {% else %}
      <a class="btn primary" href="/login">Login with Discord</a>
      {% endif %}
    </div>
  </aside>
  <main class="main">
    <div class="topbar"><div class="headline"><h2>{{ title }}</h2><p>Fast monitoring, clean controls, and global server management.</p></div><div class="actions"><a class="btn" href="/">Status</a>{% if user %}<a class="btn primary" href="/dashboard">Dashboard</a>{% else %}<a class="btn primary" href="/login">Login</a>{% endif %}</div></div>
    {{ body|safe }}
    <div class="footer">{{ brand }} • Protected by Discord OAuth • {{ role_badge|safe }}</div>
  </main>
</div>
<script>
  (() => {
    const path = window.location.pathname;
    document.querySelectorAll('.navitem').forEach(a => {
      const href = a.getAttribute('href');
      if (href && (path === href || (href !== '/dashboard' && path.startsWith(href)))) a.classList.add('active');
    });

    const toast = (message, type='ok') => {
      let box = document.getElementById('live-toast');
      if (!box) {
        box = document.createElement('div');
        box.id = 'live-toast';
        box.style.position = 'fixed';
        box.style.top = '18px';
        box.style.right = '18px';
        box.style.zIndex = '99999';
        box.style.display = 'grid';
        box.style.gap = '8px';
        document.body.appendChild(box);
      }
      const item = document.createElement('div');
      item.className = 'toast ' + (type === 'bad' ? 'bad' : 'ok');
      item.style.boxShadow = '0 18px 45px rgba(0,0,0,.32)';
      item.textContent = message;
      box.appendChild(item);
      setTimeout(() => item.style.opacity = '0', 2200);
      setTimeout(() => item.remove(), 2700);
    };

    const setSaving = (form, saving) => {
      const state = form.querySelector('[data-live-state]');
      if (state) {
        state.textContent = saving ? 'Saving...' : 'Saved';
        state.classList.toggle('ok', !saving);
        state.classList.toggle('gold', saving);
      }
      form.querySelectorAll('[data-live-submit]').forEach(btn => {
        btn.disabled = saving;
        btn.style.opacity = saving ? '.65' : '1';
      });
    };

    const updateSwitchBadges = (form) => {
      form.querySelectorAll('.protect-switch').forEach(card => {
        const input = card.querySelector('input[type="checkbox"]');
        const badge = card.querySelector('em');
        if (!input || !badge) return;
        badge.textContent = input.checked ? 'ON' : 'OFF';
        badge.style.background = input.checked ? 'rgba(34,197,94,.16)' : 'rgba(239,68,68,.14)';
        badge.style.borderColor = input.checked ? 'rgba(34,197,94,.30)' : 'rgba(239,68,68,.25)';
        badge.style.color = input.checked ? '#dcfce7' : '#fee2e2';
      });
    };

    const liveSubmit = async (form, silent=false) => {
      if (form.dataset.saving === '1') { form.dataset.pending = '1'; return; }
      form.dataset.saving = '1';
      form.dataset.pending = '0';
      setSaving(form, true);
      try {
        const res = await fetch(form.action, {
          method: form.method || 'POST',
          body: new FormData(form),
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' },
          credentials: 'same-origin'
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) throw new Error(data.error || 'Failed to save');
        setSaving(form, false);
        updateSwitchBadges(form);
        if (!silent) toast(data.message || 'Saved successfully');
      } catch (err) {
        setSaving(form, false);
        toast(err.message || 'Save failed', 'bad');
      } finally {
        form.dataset.saving = '0';
        if (form.dataset.pending === '1') {
          form.dataset.pending = '0';
          liveSubmit(form, true);
        }
      }
    };

    document.querySelectorAll('form[data-live="true"]').forEach(form => {
      let timer = null;
      updateSwitchBadges(form);
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        liveSubmit(form);
      });
      if (form.dataset.autosave === 'true') {
        form.addEventListener('change', () => {
          updateSwitchBadges(form);
          clearTimeout(timer);
          timer = setTimeout(() => liveSubmit(form, true), 280);
        });
        form.addEventListener('input', (e) => {
          if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) {
            clearTimeout(timer);
            timer = setTimeout(() => liveSubmit(form, true), 700);
          }
        });
      }
    });
  })();
</script>

    <script>
      document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".vault-card .log-clean-text img, .vault-card img:not(.memberavatar):not(.miniavatar):not(.servericon)").forEach(function (img) {
          img.remove();
        });
      });
    </script>


<script>
document.addEventListener("DOMContentLoaded", function () {
  const selectedServerMembers = "__NM_SELECTED_MEMBERS__";
  document.querySelectorAll("*").forEach(function(el){
    if (el.childNodes && el.childNodes.length === 1 && el.textContent.trim() === "SERVERS") el.textContent = "SERVER";
    if (el.childNodes && el.childNodes.length === 1 && el.textContent.trim() === "USERS") el.textContent = "MEMBERS";
  });
});
</script>


<script>
document.addEventListener("DOMContentLoaded", function () {
  const pathMatch = location.pathname.match(/\/dashboard\/guild\/(\d+)/);
  const gid = pathMatch ? pathMatch[1] : new URLSearchParams(location.search).get("guild_id");
  if (!gid) return;

  document.querySelectorAll('a[href^="/dashboard"]').forEach(a => {
    try {
      const raw = a.getAttribute("href");
      const u = new URL(raw, location.origin);
      if (!u.pathname.includes("/dashboard/guild/") && !u.searchParams.get("guild_id")) {
        u.searchParams.set("guild_id", gid);
        a.setAttribute("href", u.pathname + u.search + u.hash);
      }
    } catch(e) {}
  });

  document.querySelectorAll('form').forEach(f => {
    if (!f.querySelector('input[name="guild_id"]')) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "guild_id";
      input.value = gid;
      f.appendChild(input);
    }
  });
});
</script>

</body>
</html>
'''



def render_dashboard_page(title, body, status=200):
    user = session.get("discord_user")
    access_level = dashboard_current_access_level() if user else "none"
    role_badge = dashboard_role_badge_html() if user else ""
    return render_template_string(
        DASHBOARD_BASE_TEMPLATE,
        title=title,
        brand=BOT_BRAND,
        user=user,
        body=body,
        access_level=access_level,
        role_badge=role_badge,
        global_stats_compact=dashboard_global_stats_html(compact=True),
        server_rail=dashboard_server_rail_html(),
    ), status


@app.route("/")
def home():
    body = f'''
    <div class="hero">
      <div class="card"><div class="big">✅ System Online</div><p class="muted">البوت شغال والداشبورد جاهز للإدارة. هذه إحصائيات شبكة البوت مثل البوتات الكبيرة.</p><div style="height:12px"></div><a class="btn primary" href="/login">Login with Discord</a></div>
      <div class="card"><h3>🌍 Bot Network</h3><p class="muted">عدد السيرفرات والأعضاء يتحدث من اتصال البوت الحالي.</p><span class="pill ok">Live Count</span></div>
    </div>
    <div style="height:14px"></div>
    {dashboard_global_stats_html()}
    '''
    return render_dashboard_page("Online", body)


@app.route("/top")
def public_top_page():
    if not PUBLIC_LEADERBOARD_ENABLED:
        return "Public leaderboard is disabled.", 403
    money_rows = get_top_money(10)
    level_rows = get_top_levels(10)
    money_html = "".join([f"<tr><td>#{i}</td><td>{dashboard_member_name(uid)}</td><td>{fmt_coin(balance)}</td></tr>" for i,(uid,balance) in enumerate(money_rows, start=1)]) or "<tr><td colspan='3'>No data</td></tr>"
    level_html = "".join([f"<tr><td>#{i}</td><td>{dashboard_member_name(uid)}</td><td>Lv.{level} • XP {xp}</td></tr>" for i,(uid,xp,level) in enumerate(level_rows, start=1)]) or "<tr><td colspan='3'>No data</td></tr>"
    events = get_active_events(5)
    event_html = "".join([f"<tr><td>{clean_text(title,100)}</td><td>{fmt_coin(prize)}</td><td>{ends}</td></tr>" for eid,key,title,prize,start,ends,created,status in events]) or "<tr><td colspan='3'>No active events</td></tr>"
    body = f"""
    <div class="hero"><div class="card"><div class="big">🏆 {BOT_BRAND} Leaderboard</div><p class="muted">Public server rankings and active events.</p><div style="height:12px"></div><a class="btn primary" href="/login">Admin Login</a></div><div class="card"><h3>🪙 Currency</h3><p class="muted">{nm_coin_name()}</p><span class="pill ok">Public View</span></div></div>
    <div style="height:16px"></div>
    <div class="grid2"><div class="card"><h3>🪙 Top Richest</h3><table class="table"><tr><th>Rank</th><th>User</th><th>Balance</th></tr>{money_html}</table></div><div class="card"><h3>📊 Top Levels</h3><table class="table"><tr><th>Rank</th><th>User</th><th>Level</th></tr>{level_html}</table></div></div>
    <div style="height:16px"></div><div class="card"><h3>🎉 Active Events</h3><table class="table"><tr><th>Event</th><th>Prize</th><th>Ends Unix</th></tr>{event_html}</table></div>
    """
    return render_dashboard_page("Public Leaderboard", body)


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
        access_token = token_data["access_token"]
        user = oauth_get_user(access_token)
        user_guilds = oauth_get_user_guilds(access_token)
        session["discord_user"] = {"id": user.get("id"), "username": user.get("username"), "global_name": user.get("global_name"), "avatar": user.get("avatar")}
        session["discord_guilds"] = user_guilds
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




# =========================
# GLOBAL DASHBOARD PHASE 3 HELPERS
# =========================


def dashboard_set_active_guild(guild_id):
    try:
        gid = int(guild_id)
    except Exception:
        gid = int(GUILD_ID)
    try:
        session["dashboard_active_guild_id"] = gid
        session["selected_guild_id"] = gid
    except Exception:
        pass
    return gid


def dashboard_get_active_guild_id():
    return nm_stable_selected_guild_id()

def dashboard_guild_banner(guild_id, label="Selected Guild"):
    guild = bot.get_guild(int(guild_id)) if bot else None
    name = guild.name if guild else get_guild_settings(guild_id).get("guild_name", "Unknown Guild")
    icon = guild.icon.url if guild and guild.icon else ""
    if icon:
        icon_html = f'<img src="{icon}" style="width:44px;height:44px;border-radius:16px;border:1px solid var(--line);object-fit:cover">'
    else:
        icon_html = '<div style="width:44px;height:44px;border-radius:16px;border:1px solid var(--line);display:grid;place-items:center;background:rgba(59,130,246,.15)">🌍</div>'
    return f"""
    <div class="card" style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:12px">
        {icon_html}
        <div>
          <div class="muted small">{dash_escape(label, 80)}</div>
          <h3 style="margin:2px 0 0">{dash_escape(name, 120)}</h3>
          <div class="muted small"><code>{int(guild_id)}</code></div>
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <a class="btn" href="/dashboard/guilds">Switch Guild</a>
        <a class="btn" href="/dashboard/guild/{int(guild_id)}/setup">Setup</a>
        <a class="btn" href="/dashboard/guild/{int(guild_id)}/command-center">Command Center</a>
        <a class="btn" href="/dashboard/guild/{int(guild_id)}/warnings">Warnings</a>
      </div>
    </div>
    """

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
    <div class="hero"><div class="card"><div class="big">NM System</div><p class="muted">Control servers, economy, levels, memory backups, casino and protection from one powerful dashboard.</p><div style="height:12px"></div><a class="btn primary" href="/dashboard/economy">Manage Economy</a> <a class="btn" href="/dashboard/settings">Bot Settings</a></div><div class="card"><h3>⚡ Quick Status</h3><p><span class="pill ok">Bot Online</span></p><p class="muted">Memory files healthy: <b>{memory_ok}/{len(memory)}</b></p><p class="muted">Guide interval: <b>{round(ECONOMY_EXPLAIN_INTERVAL_SECONDS/3600, 2)}h</b></p></div></div>
    <div class="grid">
      <div class="card stat"><div class="icon">🪙</div><div class="num">{fmt_num(economy_users)}</div><div class="label">Economy users</div></div>
      <div class="card stat"><div class="icon">💰</div><div class="num">{fmt_num(total_coins)}</div><div class="label">Total {nm_coin_name()}</div></div>
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




# =========================
# BOT OWNER GLOBAL MONITOR
# =========================

def dashboard_owner_guild_permissions_snapshot(guild):
    """Return important bot permission checks for a guild."""
    checks = []
    try:
        me = getattr(guild, "me", None) or guild.get_member(bot.user.id)
        perms = me.guild_permissions if me else None
        checks = [
            ("View Channels", bool(perms and perms.view_channel)),
            ("Send Messages", bool(perms and perms.send_messages)),
            ("Embed Links", bool(perms and perms.embed_links)),
            ("Manage Channels", bool(perms and perms.manage_channels)),
            ("Manage Roles", bool(perms and perms.manage_roles)),
            ("Read Message History", bool(perms and perms.read_message_history)),
            ("View Audit Log", bool(perms and perms.view_audit_log)),
            ("Moderate Members", bool(perms and getattr(perms, "moderate_members", False))),
            ("Manage Messages", bool(perms and perms.manage_messages)),
        ]
    except Exception:
        pass
    return checks


def dashboard_owner_guild_log_status(guild, settings=None):
    """Count the existing log rooms by configured names, and report missing log rooms."""
    try:
        if not guild:
            return 0, len(LOG_CHANNEL_NAMES), list(LOG_CHANNEL_NAMES.values()), []
        existing_names = {str(c.name).lower(): c for c in guild.text_channels}
        missing = []
        existing = []
        for key, name in LOG_CHANNEL_NAMES.items():
            channel = existing_names.get(str(name).lower())
            if channel:
                existing.append(channel)
            else:
                missing.append(name)
        outside = []
        logs_category_id = int((settings or {}).get("logs_category_id") or 0)
        if logs_category_id:
            for channel in existing:
                try:
                    if not channel.category or int(channel.category.id) != logs_category_id:
                        outside.append(channel.name)
                except Exception:
                    pass
        return len(existing), len(LOG_CHANNEL_NAMES), missing, outside
    except Exception:
        return 0, len(LOG_CHANNEL_NAMES), list(LOG_CHANNEL_NAMES.values()), []


def dashboard_owner_guild_health_badges(guild, settings):
    badges = []
    try:
        if settings.get("enabled"):
            badges.append("<span class='pill ok'>Enabled</span>")
        else:
            badges.append("<span class='pill bad'>Disabled</span>")

        if settings.get("setup_done"):
            badges.append("<span class='pill ok'>Setup Done</span>")
        else:
            badges.append("<span class='pill warn'>Needs Setup</span>")

        if settings.get("commands_channel_id"):
            badges.append("<span class='pill ok'>Commands Set</span>")
        else:
            badges.append("<span class='pill warn'>No Commands Room</span>")

        if settings.get("gambling_channel_id"):
            badges.append("<span class='pill ok'>Gambling Set</span>")
        else:
            badges.append("<span class='pill warn'>No Gambling Room</span>")

        log_found, log_total, missing, outside = dashboard_owner_guild_log_status(guild, settings)
        if log_found >= log_total:
            badges.append("<span class='pill ok'>Logs Ready</span>")
        elif log_found > 0:
            badges.append(f"<span class='pill warn'>Logs {log_found}/{log_total}</span>")
        else:
            badges.append("<span class='pill bad'>No Log Rooms</span>")
    except Exception:
        badges.append("<span class='pill bad'>Status Error</span>")
    return " ".join(badges)


def dashboard_owner_guild_card(guild):
    settings = get_guild_settings(guild.id)
    log_found, log_total, missing_logs, outside_logs = dashboard_owner_guild_log_status(guild, settings)
    permission_checks = dashboard_owner_guild_permissions_snapshot(guild)
    ok_perms = sum(1 for _, ok in permission_checks if ok)
    total_perms = len(permission_checks) or 1
    bad_perm_names = [name for name, ok in permission_checks if not ok]

    humans = len([m for m in guild.members if not m.bot])
    bots = len([m for m in guild.members if m.bot])
    online = len([m for m in guild.members if not m.bot and str(m.status) != "offline"])
    voice = len([m for m in guild.members if not m.bot and getattr(m, "voice", None) and m.voice and m.voice.channel])

    owner_text = "Unknown"
    try:
        owner_text = f"{dash_escape(str(guild.owner), 90)}" if guild.owner else f"Owner ID: {guild.owner_id}"
    except Exception:
        owner_text = f"Owner ID: {getattr(guild, 'owner_id', 'Unknown')}"

    icon_html = "🌍"
    try:
        if guild.icon:
            icon_html = f"<img src='{guild.icon.url}' style='width:46px;height:46px;border-radius:16px;object-fit:cover'>"
    except Exception:
        pass

    missing_logs_text = ", ".join(missing_logs[:5]) + ("..." if len(missing_logs) > 5 else "") if missing_logs else "None"
    outside_logs_text = ", ".join(outside_logs[:5]) + ("..." if len(outside_logs) > 5 else "") if outside_logs else "None"
    bad_perms_text = ", ".join(bad_perm_names[:5]) + ("..." if len(bad_perm_names) > 5 else "") if bad_perm_names else "All important permissions OK"

    commands_text = f"<#{settings.get('commands_channel_id')}>" if settings.get("commands_channel_id") else "<span class='muted'>Not set</span>"
    gambling_text = f"<#{settings.get('gambling_channel_id')}>" if settings.get("gambling_channel_id") else "<span class='muted'>Not set</span>"
    logs_text = f"<#{settings.get('logs_category_id')}>" if settings.get("logs_category_id") else "<span class='muted'>Not set</span>"

    created_text = "Unknown"
    try:
        created_text = guild.created_at.strftime("%Y-%m-%d")
    except Exception:
        pass

    return f"""
    <div class="card">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;">
        <div style="display:flex;gap:12px;align-items:center;min-width:0;">
          <div>{icon_html}</div>
          <div style="min-width:0;">
            <h3 style="margin:0 0 4px">{dash_escape(guild.name, 120)}</h3>
            <p class="muted small" style="margin:0">Guild ID: <code>{guild.id}</code> • Owner: {owner_text}</p>
          </div>
        </div>
        <div style="text-align:right;white-space:nowrap">{dashboard_owner_guild_health_badges(guild, settings)}</div>
      </div>

      <div style="height:12px"></div>
      <div class="grid3">
        <div><span class="muted small">Members</span><div class="cc-stat" style="font-size:22px">{humans:,}</div><p class="muted small">Online: {online:,} • Voice: {voice:,} • Bots: {bots:,}</p></div>
        <div><span class="muted small">Channels</span><div class="cc-stat" style="font-size:22px">{len(guild.text_channels):,} / {len(guild.voice_channels):,}</div><p class="muted small">Text / Voice • Created: {created_text}</p></div>
        <div><span class="muted small">Bot Permissions</span><div class="cc-stat" style="font-size:22px">{ok_perms}/{total_perms}</div><p class="muted small">{dash_escape(bad_perms_text, 180)}</p></div>
      </div>

      <div style="height:10px"></div>
      <div class="grid3">
        <div><span class="muted small">Commands Room</span><p>{commands_text}</p></div>
        <div><span class="muted small">Gambling Room</span><p>{gambling_text}</p></div>
        <div><span class="muted small">Logs Category</span><p>{logs_text}</p></div>
      </div>

      <div class="card" style="padding:12px;box-shadow:none;background:rgba(255,255,255,.035);margin-top:10px">
        <p class="muted small" style="margin:0"><b>Logs:</b> {log_found}/{log_total} موجودة • <b>Missing:</b> {dash_escape(missing_logs_text, 180)} • <b>Outside category:</b> {dash_escape(outside_logs_text, 180)}</p>
      </div>

      <div style="height:12px"></div>
      <a class="btn primary" href="/dashboard/guild/{guild.id}/setup">Setup</a>
      <a class="btn" href="/dashboard/guild/{guild.id}/command-center">Command Center</a>
      <a class="btn" href="/dashboard/guild/{guild.id}/protection">Protection</a>
      <a class="btn" href="/dashboard/guild/{guild.id}/warnings">Warnings</a>
      <a class="btn" href="/dashboard/guild/{guild.id}/log-vault">Log Vault</a>
    </div>
    """


@app.route("/dashboard/owner-console", methods=["GET"])
def dashboard_owner_console_page():
    denied = dashboard_require_owner()
    if denied:
        return denied
    init_db()

    guilds = []
    try:
        guilds = sorted(list(bot.guilds), key=lambda g: str(g.name).lower())
    except Exception:
        guilds = []

    stats = dashboard_global_bot_stats()
    total_guilds = stats.get("guilds", len(guilds))
    total_members = stats.get("members", 0)
    total_humans = stats.get("humans", 0)
    total_online = stats.get("online", 0)
    total_text = stats.get("text_channels", 0)
    total_voice = stats.get("voice_channels", 0)

    setup_done = 0
    enabled_count = 0
    logs_ready = 0
    settings_cache = {}
    for g in guilds:
        st = get_guild_settings(g.id)
        settings_cache[g.id] = st
        if st.get("setup_done"):
            setup_done += 1
        if st.get("enabled"):
            enabled_count += 1
        # Log room scan can be expensive. Keep it only for the visible page cards below.

    q = str(request.args.get("q", "")).lower().strip()
    page = max(1, parse_bet_amount(request.args.get("page", "1")) or 1)
    per_page = 12
    filtered = guilds
    if q:
        filtered = [g for g in guilds if q in str(g.name).lower() or q in str(g.id)]

    total_filtered = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    visible_guilds = filtered[start:end]
    rows = "".join([dashboard_owner_guild_card(g) for g in visible_guilds])
    if not rows:
        rows = "<div class='card warn'><h3>No servers found</h3><p class='muted'>ما لقيت سيرفرات مطابقة للبحث.</p></div>"

    prev_q = f"?q={urllib.parse.quote(q)}&page={page-1}" if page > 1 else ""
    next_q = f"?q={urllib.parse.quote(q)}&page={page+1}" if end < total_filtered else ""
    pager_html = f"""
    <div class='card' style='padding:12px;box-shadow:none'>
      <div style='display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap'>
        <span class='muted small'>Showing {start + 1 if total_filtered else 0}-{min(end, total_filtered)} of {total_filtered} servers</span>
        <div>
          {f'<a class="btn" href="/dashboard/owner-console{prev_q}">Previous</a>' if prev_q else ''}
          {f'<a class="btn primary" href="/dashboard/owner-console{next_q}">Next</a>' if next_q else ''}
        </div>
      </div>
    </div>
    """

    body = f"""
    {dashboard_toast_html()}
    <div class="hero">
      <div class="card">
        <div class="big">👑 Bot Owner Console</div>
        <p class="muted">مركز مراقبة خاص لصاحب البوت. هنا تشوف كل السيرفرات اللي دخلها البوت، وتفتح إعدادات أي سيرفر مباشرة بدون الاعتماد على صلاحياتك داخل السيرفر.</p>
        <p><span class="pill ok">Owner Only</span> <span class="pill">All Bot Guilds</span> <span class="pill">Global Monitoring</span></p>
      </div>
      <div class="card">
        <h3>Quick Search</h3>
        <form method="get" action="/dashboard/owner-console">
          <input name="q" value="{dash_escape(q, 80)}" placeholder="Search by server name or guild ID">
          <div style="height:10px"></div>
          <button class="btn primary" type="submit">Search</button>
          <a class="btn" href="/dashboard/owner-console">Reset</a>
        </form>
      </div>
    </div>

    <div style="height:14px"></div>
    <div class="grid">
      <div class="card"><h3>🌍 Servers</h3><div class="cc-stat">{total_guilds:,}</div><p class="muted small">Enabled: {enabled_count:,} • Setup done: {setup_done:,}</p></div>
      <div class="card"><h3>👥 Members</h3><div class="cc-stat">{total_humans:,}</div><p class="muted small">Total accounts: {total_members:,} • Online humans: {total_online:,}</p></div>
      <div class="card"><h3>📡 Channels</h3><div class="cc-stat">{total_text:,} / {total_voice:,}</div><p class="muted small">Text / Voice across all servers</p></div>
      <div class="card"><h3>⚡ Fast Mode</h3><div class="cc-stat">ON</div><p class="muted small">Log details load on visible server cards only</p></div>
    </div>

    <div style="height:14px"></div>
    <div class="card">
      <h3>صلاحياتك كصاحب البوت</h3>
      <p class="muted">أنت كـ Owner تقدر تدخل Setup وCommand Center وProtection وWarnings وLog Vault لأي سيرفر البوت داخله، حتى لو ما كنت صاحب السيرفر نفسه. Admin العادي ما يشوف هذه الصفحة.</p>
    </div>

    <div style="height:14px"></div>
    {pager_html}
    <div style="height:14px"></div>
    <div class="guildlist">{rows}</div>
    <div style="height:14px"></div>
    {pager_html}
    """
    return render_dashboard_page("Bot Owner Console", body)


@app.route("/dashboard/guilds", methods=["GET"])
def dashboard_guild_selector_page():
    denied = dashboard_require_login()
    if denied:
        return denied
    init_db()
    bot_ids = dashboard_bot_guild_ids()
    oauth_map = dashboard_user_guild_map()
    rows = []
    candidate_ids = set(oauth_map.keys()) & bot_ids
    if dashboard_current_user_is_owner():
        candidate_ids |= bot_ids

    for guild_id in sorted(candidate_ids):
        guild = dashboard_get_bot_guild(guild_id)
        oauth_item = oauth_map.get(guild_id, {})
        settings = get_guild_settings(guild_id)
        if not dashboard_can_manage_guild(guild_id):
            continue
        name = guild.name if guild else (oauth_item.get("name") or settings.get("guild_name") or f"Guild {guild_id}")
        status = "Ready" if settings.get("setup_done") else "Needs setup"
        status_class = "ok" if settings.get("setup_done") else "warn"
        enabled = "Enabled" if settings.get("enabled") else "Disabled"
        enabled_class = "ok" if settings.get("enabled") else "bad"
        commands_text = f"<#{settings.get('commands_channel_id')}>" if settings.get('commands_channel_id') else "Not set"
        gambling_text = f"<#{settings.get('gambling_channel_id')}>" if settings.get('gambling_channel_id') else "Not set"
        rows.append(f'''
        <div class="card">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
            <div><h3>🌍 {dash_escape(name, 120)}</h3><p class="muted small"><code>{guild_id}</code></p></div>
            <div style="text-align:right"><span class="pill {status_class}">{status}</span> <span class="pill {enabled_class}">{enabled}</span></div>
          </div>
          <div style="height:10px"></div>
          <p class="muted small">Commands: {commands_text} • Gambling: {gambling_text}</p>
          <a class="btn primary" href="/dashboard/guild/{guild_id}/setup">Setup</a>
          <a class="btn" href="/dashboard/guild/{guild_id}/command-center">Command Center</a>
          <a class="btn" href="/dashboard/guild/{guild_id}/protection">Protection</a>
          <a class="btn" href="/dashboard/guild/{guild_id}/warnings">Warnings</a>
        </div>
        ''')

    if not rows:
        rows.append('''
        <div class="card warn">
          <h3>ما فيه سيرفرات قابلة للإدارة</h3>
          <p class="muted">تأكد أن البوت موجود في السيرفر وأن حسابك عنده Manage Server أو Administrator، أو أنك داخل كـ Owner في الداشبورد.</p>
          <a class="btn" href="/login">Refresh Discord Login</a>
        </div>
        ''')

    body = f'''
    {dashboard_toast_html()}
    <div class="hero">
      <div class="card"><div class="big">🌍 Guild Selector</div><p class="muted">اختار السيرفر اللي تبي تضبطه. Owner يشوف كل السيرفرات اللي دخلها البوت، أما Admin يشوف فقط السيرفرات اللي عنده فيها Manage Server أو Administrator.</p></div>
      <div class="card"><h3>Global Dashboard</h3><p><span class="pill ok">Multi-Guild Setup</span></p><p class="muted small">لكل سيرفر إعداداته الخاصة: روم الأوامر، روم القمار، وكاتقوري اللوقات.</p></div>
    </div>
    <div style="height:14px"></div>
    <div class="grid2">{''.join(rows)}</div>
    '''
    return render_dashboard_page("Guilds", body)


@app.route("/dashboard/guild/<int:guild_id>/setup", methods=["GET", "POST"])
def dashboard_guild_setup_page(guild_id):
    denied = dashboard_require_login()
    if denied:
        return denied
    init_db()
    guild = dashboard_get_bot_guild(guild_id)
    if not guild:
        return render_dashboard_page("Guild Setup", "<div class='card danger'><h3>Bot is not in this server</h3><p>البوت لازم يكون داخل السيرفر عشان تقدر تضبطه.</p></div>", status=404)
    if not dashboard_can_manage_guild(guild_id):
        return dashboard_access_denied_html("ما عندك صلاحية إدارة هذا السيرفر من الداشبورد. تحتاج Manage Server أو Administrator داخل السيرفر.")

    if request.method == "POST":
        enabled = request.form.get("enabled") == "on"
        commands_channel_id = safe_int(request.form.get("commands_channel_id"), 0)
        gambling_channel_id = safe_int(request.form.get("gambling_channel_id"), 0)
        logs_category_id = safe_int(request.form.get("logs_category_id"), 0)
        ok = update_guild_settings_from_dashboard(guild_id, enabled, commands_channel_id, gambling_channel_id, logs_category_id, setup_done=True)
        if ok:
            dashboard_log_action("guild_setup_update", f"Guild {guild_id}: commands={commands_channel_id}, gambling={gambling_channel_id}, logs={logs_category_id}, enabled={enabled}", admin=session.get("discord_user"))
            session["toast"] = "تم حفظ إعدادات السيرفر."
        else:
            session["toast"] = "صار خطأ أثناء حفظ إعدادات السيرفر."
        return redirect(f"/dashboard/guild/{guild_id}/setup")

    settings = get_guild_settings(guild_id)
    enabled_checked = "checked" if settings.get("enabled") else ""
    commands_options = dashboard_guild_channels_html(guild, settings.get("commands_channel_id"), text_only=True)
    gambling_options = dashboard_guild_channels_html(guild, settings.get("gambling_channel_id"), text_only=True)
    logs_options = dashboard_guild_categories_html(guild, settings.get("logs_category_id"))
    current_commands = f"<#{settings.get('commands_channel_id')}>" if settings.get('commands_channel_id') else "<span class='muted'>Not set</span>"
    current_gambling = f"<#{settings.get('gambling_channel_id')}>" if settings.get('gambling_channel_id') else "<span class='muted'>Not set</span>"
    current_logs = f"<#{settings.get('logs_category_id')}>" if settings.get('logs_category_id') else "<span class='muted'>Not set</span>"
    setup_badge = "Setup done" if settings.get("setup_done") else "Needs setup"
    setup_class = "ok" if settings.get("setup_done") else "warn"

    body = f'''
    {dashboard_toast_html()}
    <div class="hero">
      <div class="card"><div class="big">⚙️ {dash_escape(guild.name, 120)}</div><p class="muted">Guild ID: <code>{guild.id}</code></p><p><span class="pill {setup_class}">{setup_badge}</span></p></div>
      <div class="card"><h3>What this controls</h3><p class="muted small">هذه الإعدادات تستخدمها أوامر السلاش العالمية مثل /salary و /luck، وبعد المراحل القادمة بتصير كل أنظمة البوت تقرأ إعدادات السيرفر من هنا.</p></div>
    </div>
    <div style="height:14px"></div>
    <form class="card" method="post" action="/dashboard/guild/{guild.id}/setup">
      <h3>🌍 Server Setup</h3>
      <label style="display:flex;align-items:center;gap:10px;margin:10px 0;"><input type="checkbox" name="enabled" {enabled_checked} style="width:auto;"><span>Enable bot systems in this server</span></label>
      <div class="grid3">
        <div><label>Commands Channel</label><select name="commands_channel_id">{commands_options}</select><p class="muted small">الأوامر الاقتصادية والعامة تشتغل هنا.</p></div>
        <div><label>Gambling Channel</label><select name="gambling_channel_id">{gambling_options}</select><p class="muted small">أوامر القمار مثل /luck تشتغل هنا.</p></div>
        <div><label>Logs Category</label><select name="logs_category_id">{logs_options}</select><p class="muted small">مكان إنشاء/ترتيب رومات اللوقات لاحقًا.</p></div>
      </div>
      <div style="height:14px"></div>
      <button class="btn primary" type="submit">Save Guild Setup</button>
      <a class="btn" href="/dashboard/guilds">Back to Guilds</a>
    </form>
    <div style="height:14px"></div>
    <div class="grid2">
      <div class="card"><h3>✅ Current Effective Settings</h3><p>Commands: {current_commands}</p><p>Gambling: {current_gambling}</p><p>Logs Category: {current_logs}</p></div>
      <div class="card"><h3>🧪 Test Commands</h3><p class="muted small">بعد الحفظ جرب داخل السيرفر:</p><p><code>/setup_status</code></p><p><code>/ping</code></p><p><code>/salary</code></p></div>
    </div>
    '''
    return render_dashboard_page("Guild Setup", body)

@app.route("/dashboard/guild/<int:guild_id>/command-center", methods=["GET"])
def dashboard_guild_command_center_redirect(guild_id):
    denied = dashboard_require_admin()
    if denied:
        return denied
    dashboard_set_active_guild(guild_id)
    return redirect(f"/dashboard/command-center?guild_id={int(guild_id)}")


@app.route("/dashboard/guild/<int:guild_id>/warnings", methods=["GET"])
def dashboard_guild_warnings_redirect(guild_id):
    denied = dashboard_require_admin()
    if denied:
        return denied
    dashboard_set_active_guild(guild_id)
    return redirect(f"/dashboard/warnings?guild_id={int(guild_id)}")


@app.route("/dashboard/guild/<int:guild_id>/log-vault", methods=["GET"])
def dashboard_guild_log_vault_redirect(guild_id):
    denied = dashboard_require_owner()
    if denied:
        return denied
    dashboard_set_active_guild(guild_id)
    return redirect(f"/dashboard/log-vault?guild_id={int(guild_id)}")


@app.route("/dashboard/guild/<int:guild_id>/protection", methods=["GET"])
def dashboard_guild_protection_redirect(guild_id):
    denied = dashboard_require_owner()
    if denied:
        return denied
    dashboard_set_active_guild(guild_id)
    return redirect(f"/dashboard/protection?guild_id={int(guild_id)}")



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
    <div class="grid2">
      <form class="card danger" method="post" action="/dashboard/economy">
        <h3>🌍 Give Money To Everyone</h3>
        <p class="muted small">يعطي كل أعضاء السيرفر غير البوتات نفس المبلغ. العملية قوية، استخدمها بحذر.</p>
        <label>Amount per member</label><input name="amount" placeholder="1000" required>
        <label>Confirmation</label><input name="confirm" placeholder="اكتب CONFIRM" required>
        <input type="hidden" name="action" value="bulk_add">
        <div style="height:10px"></div><button class="btn green">Give Everyone</button>
      </form>
      <form class="card danger" method="post" action="/dashboard/economy">
        <h3>🌍 Take Money From Everyone</h3>
        <p class="muted small">يسحب من كل أعضاء السيرفر غير البوتات. إذا رصيد العضو أقل من المبلغ، يصير رصيده 0.</p>
        <label>Amount per member</label><input name="amount" placeholder="1000" required>
        <label>Confirmation</label><input name="confirm" placeholder="اكتب CONFIRM" required>
        <input type="hidden" name="action" value="bulk_remove">
        <div style="height:10px"></div><button class="btn red">Take From Everyone</button>
      </form>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>🪙 Economy Leaderboard</h3><table class="table"><tr><th>User</th><th>Balance</th><th>Last Salary</th></tr>{table}</table></div>
    '''
    return render_dashboard_page("Economy", body)




@app.route('/dashboard/money-audit', methods=['GET'])
def dashboard_money_audit_page():
    denied = dashboard_require_owner()
    if denied:
        return denied

    init_db()
    user_id_raw = (request.args.get('user_id') or '').strip()
    batch_id = (request.args.get('batch_id') or '').strip()
    admin_only = (request.args.get('admin_only') or '1') == '1'
    user_id = int(user_id_raw) if user_id_raw.isdigit() else None

    people_count, admin_total, admin_entries, batch_count = money_audit_global_stats()
    rows = money_audit_recent_rows(120, user_id=user_id, admin_only=admin_only, batch_id=batch_id)
    top_rows = money_audit_top_admin_received(12)
    batches = money_audit_bulk_batches(10)

    selected_summary_html = ''
    if user_id:
        summary = money_audit_member_summary(user_id)
        selected_summary_html = f'''
        <div class="grid3">
          <div class="card"><h3>👤 Selected Member</h3><p>{dashboard_member_name(user_id)}</p><p class="muted small"><code>{user_id}</code></p></div>
          <div class="card"><h3>🧾 Admin Money Received</h3><div class="cc-stat" style="color:#fbbf24">{fmt_coin(summary['admin_received'])}</div><p class="muted small">فلوس وصلت له من Owner/Admin أو Give Everyone.</p></div>
          <div class="card"><h3>⛏️ Earned / System Money</h3><div class="cc-stat" style="color:#22c55e">{fmt_coin(summary['earned_received'])}</div><p class="muted small">راتب، قمار، جوائز، تحويلات أو مصادر غير إدارية مسجلة.</p></div>
        </div>
        <div style="height:12px"></div>
        <div class="grid3">
          <div class="card"><h3>💼 Current Balance</h3><div class="cc-stat">{fmt_coin(summary['balance'])}</div></div>
          <div class="card"><h3>📉 Removed / Spent Logged</h3><div class="cc-stat" style="color:#ef4444">{fmt_coin(summary['removed_or_spent'])}</div></div>
          <div class="card"><h3>🕰️ Old / Untracked</h3><div class="cc-stat">{fmt_coin(summary['untracked_or_old'])}</div><p class="muted small">رصيد موجود من قبل نظام التتبع أو فرق بسبب خسائر/صرف.</p></div>
        </div>
        <div style="height:14px"></div>
        '''

    top_html = ''.join([
        f"<tr><td>{dashboard_member_name(uid)}<br><span class='muted small'><code>{uid}</code> • {dash_escape(name, 80)}</span></td><td>{fmt_coin(total)}</td><td>{entries}</td><td><a class='btn' href='/dashboard/money-audit?user_id={uid}&admin_only=0'>Open</a></td></tr>"
        for uid, name, total, entries in top_rows
    ]) or "<tr><td colspan='4'>No admin money grants tracked yet.</td></tr>"

    batch_html = ''.join([
        f"<tr><td><code>{dash_escape(bid, 60)}</code><br><span class='muted small'>{dash_escape(label, 80)}</span></td><td>{dash_escape(admin_name, 80)}</td><td>{people}</td><td>{fmt_coin(total)}</td><td>{cc_time(ts)}</td><td><a class='btn' href='/dashboard/money-audit?batch_id={urllib.parse.quote(str(bid))}&admin_only=0'>Recipients</a></td></tr>"
        for bid, label, admin_name, people, total, ts in batches
    ]) or "<tr><td colspan='6'>No bulk actions tracked yet.</td></tr>"

    rows_html = ''.join([
        f'''
        <tr>
          <td><code>#{rid}</code><br><span class="muted small">{cc_time(created_at)}</span></td>
          <td>{dashboard_member_name(uid)}<br><span class="muted small"><code>{uid}</code> • {dash_escape(user_name, 90)}</span></td>
          <td><span class="pill {'ok' if amount > 0 else 'bad'}">{amount:+,}</span><br><span class="muted small">Balance: {fmt_coin(new_balance)}</span></td>
          <td>{dash_escape(label, 100)}<br><span class="muted small"><code>{dash_escape(source, 80)}</code></span></td>
          <td>{dashboard_member_name(admin_id) if admin_id else '<span class="muted">System/User</span>'}<br><span class="muted small">{dash_escape(admin_name, 90)}</span></td>
          <td>{dash_escape(details, 220)}{('<br><span class="muted small">Batch: <code>'+dash_escape(batch, 90)+'</code></span>') if batch else ''}</td>
        </tr>
        '''
        for rid, uid, user_name, amount, new_balance, source, label, admin_id, admin_name, batch, details, created_at in rows
    ]) or "<tr><td colspan='6'>No money logs found.</td></tr>"

    body = f'''
    {dashboard_toast_html()}
    <style>
      .cc-stat {{font-size:28px;font-weight:1000;margin-top:8px}}
      .audit-filter {{display:grid;grid-template-columns:1fr 1fr auto auto;gap:10px;align-items:end}}
      @media(max-width:900px){{.audit-filter{{grid-template-columns:1fr}}}}
    </style>
    <div class="hero">
      <div class="card">
        <div class="big">🏦 Money Audit</div>
        <p class="muted">Owner-only money tracker. يحفظ كل فلوس وصلت من الإدارة، Give Everyone، والفلوس اللي جت من مصادر عادية مثل الراتب والقمار والتحويلات.</p>
        <span class="pill gold">Owner Only</span>
        <span class="pill">Admin grants are never hidden</span>
      </div>
      <div class="card">
        <h3>📊 Admin Money Summary</h3>
        <div class="cc-stat">{fmt_coin(admin_total)}</div>
        <p class="muted small">{people_count} members received admin money • {admin_entries} entries • {batch_count} bulk batches</p>
      </div>
    </div>

    <form class="card audit-filter" method="get" action="/dashboard/money-audit">
      <div><label>User ID</label><input name="user_id" value="{dash_escape(user_id_raw, 40)}" placeholder="اختياري: اكتب User ID"></div>
      <div><label>Bulk Batch ID</label><input name="batch_id" value="{dash_escape(batch_id, 100)}" placeholder="اختياري"></div>
      <div><label>Mode</label><select name="admin_only"><option value="1" {'selected' if admin_only else ''}>Admin money only</option><option value="0" {'' if admin_only else 'selected'}>All money logs</option></select></div>
      <div><button class="btn primary">Filter</button></div>
    </form>

    <div style="height:14px"></div>
    {selected_summary_html}

    <div class="grid2">
      <div class="card"><h3>👑 Top Members By Admin Money</h3><div class="tablewrap"><table class="table"><tr><th>Member</th><th>Admin received</th><th>Entries</th><th>Open</th></tr>{top_html}</table></div></div>
      <div class="card"><h3>🌍 Latest Give Everyone Batches</h3><div class="tablewrap"><table class="table"><tr><th>Batch</th><th>Admin</th><th>People</th><th>Total</th><th>Time</th><th>View</th></tr>{batch_html}</table></div></div>
    </div>

    <div style="height:14px"></div>
    <div class="card">
      <h3>🧾 Money Logs</h3>
      <p class="muted small">أي إعطاء من الداشبورد أو Discord admin command يتسجل هنا. لو استخدمت Give Everyone يطلع كل شخص وصله المبلغ داخل نفس الـ batch.</p>
      <div class="tablewrap"><table class="table"><tr><th>ID / Time</th><th>Member</th><th>Amount</th><th>Source</th><th>Admin</th><th>Details</th></tr>{rows_html}</table></div>
    </div>
    '''
    return render_dashboard_page('Money Audit', body)


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
    <div class="card"><h3>🎲 Casino Games</h3><table class="table"><tr><th>Command</th><th>Game</th><th>Rules</th></tr><tr><td><code>/حظ amount</code></td><td>Lucky Roll</td><td>50/50 double or lose</td></tr><tr><td><code>/دبل amount</code></td><td>Double Risk</td><td>45% win, 55% lose</td></tr><tr><td><code>/سلوت amount</code></td><td>Slot Machine</td><td>2 match = x2, 3 match = x5</td></tr><tr><td><code>/وجه amount choice</code></td><td>Coin Flip</td><td>Guess the side</td></tr><tr><td><code>/بلاكجاك amount</code></td><td>Blackjack</td><td>Hit / Stand buttons</td></tr></table></div>
    <div style="height:14px"></div>
    <div class="card"><h3>🚧 Next Upgrade</h3><p class="muted">نقدر نضيف Casino History Table يخزن كل قمار: اللاعب، اللعبة، الرهان، الربح/الخسارة، الوقت. بعدها الصفحة هذي تعرض أكبر فوز وأكبر خسارة وأقوى مقامرين.</p></div>
    '''
    return render_dashboard_page("Casino", body)


@app.route("/dashboard/shop")
def dashboard_shop_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    purchases = []
    try:
        conn = db_connect(); cur = conn.cursor()
        cur.execute("SELECT user_id, item_key, price, created_at FROM shop_purchases ORDER BY id DESC LIMIT 20")
        purchases = cur.fetchall(); conn.close()
    except:
        pass
    rows = "".join([f"<tr><td>{dashboard_member_name(u)}</td><td><code>{clean_text(item,40)}</code></td><td>{fmt_coin(price)}</td><td>{created}</td></tr>" for u,item,price,created in purchases]) or "<tr><td colspan='4'>No purchases yet</td></tr>"
    status = "ON" if SHOP_ENABLED else "OFF"
    body = f"""
    <div class="grid">
      <div class="card stat"><div class="icon">🛒</div><div class="num">{status}</div><div class="label">Shop Status</div></div>
      <div class="card stat"><div class="icon">💎</div><div class="num">{short_money(SHOP_VIP_PRICE)}</div><div class="label">VIP Price</div></div>
      <div class="card stat"><div class="icon">🎁</div><div class="num">{short_money(LOOTBOX_PRICE)}</div><div class="label">Lootbox Price</div></div>
      <div class="card stat"><div class="icon">📍</div><div class="num">Room</div><div class="label"><code>{SHOP_CHANNEL_ID}</code></div></div>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>🛍️ Commands</h3><table class="table"><tr><th>Command</th><th>Use</th></tr><tr><td><code>/متجر</code></td><td>Shows the shop</td></tr><tr><td><code>/شراء vip</code></td><td>Buy VIP role for {SHOP_VIP_DAYS} days</td></tr><tr><td><code>/شراء صندوق</code> / <code>/صندوق</code></td><td>Open lootbox</td></tr></table></div>
    <div style="height:14px"></div>
    <div class="card"><h3>🧾 Latest Purchases</h3><table class="table"><tr><th>User</th><th>Item</th><th>Price</th><th>Unix Time</th></tr>{rows}</table></div>
    """
    return render_dashboard_page("Shop", body)


@app.route("/dashboard/events")
def dashboard_events_page():
    denied = dashboard_require_admin()
    if denied:
        return denied
    selected_guild_id = dashboard_get_active_guild_id()
    guild_banner = dashboard_guild_banner(selected_guild_id, "Events Guild")
    events = get_active_events(20)
    rows = "".join([f"<tr><td>#{eid}</td><td>{clean_text(title,120)}</td><td>{fmt_coin(prize)}</td><td>{end}</td><td>{dashboard_member_name(created)}</td></tr>" for eid,key,title,prize,start,end,created,status in events]) or "<tr><td colspan='5'>No active events</td></tr>"
    status = "ON" if EVENTS_ENABLED else "OFF"
    body = f"""
    {dashboard_toast_html()}
    {guild_banner}
    <div class="grid">
      <div class="card stat"><div class="icon">🎉</div><div class="num">{status}</div><div class="label">Events Status</div></div>
      <div class="card stat"><div class="icon">🏆</div><div class="num">{short_money(DEFAULT_EVENT_PRIZE)}</div><div class="label">Default Prize</div></div>
      <div class="card stat"><div class="icon">⏱️</div><div class="num">{DEFAULT_EVENT_DURATION_MINUTES}m</div><div class="label">Default Duration</div></div>
      <div class="card stat"><div class="icon">📍</div><div class="num">Room</div><div class="label"><code>{EVENTS_CHANNEL_ID}</code></div></div>
    </div>
    <div style="height:14px"></div>
    <div class="card"><h3>⚡ Start Event</h3><form method="post" action="/dashboard/events/start" class="formgrid"><div><label>Title</label><input name="title" value="Casino Night"></div><div><label>Prize</label><input name="prize" value="{DEFAULT_EVENT_PRIZE}"></div><div><label>Duration Minutes</label><input name="minutes" value="{DEFAULT_EVENT_DURATION_MINUTES}"></div><div style="display:flex;align-items:end"><button class="btn primary">Start Event</button></div></form></div>
    <div style="height:14px"></div>
    <div class="card"><h3>📅 Active Events</h3><table class="table"><tr><th>ID</th><th>Title</th><th>Prize</th><th>Ends Unix</th><th>Created By</th></tr>{rows}</table></div>
    """
    return render_dashboard_page("Events", body)


@app.route("/dashboard/events/start", methods=["POST"])
def dashboard_events_start_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    try:
        title = str(request.form.get("title", "Server Event")).strip()[:80] or "Server Event"
        prize = parse_int_field(request.form.get("prize"), DEFAULT_EVENT_PRIZE, 0)
        minutes = parse_int_field(request.form.get("minutes"), DEFAULT_EVENT_DURATION_MINUTES, 1)
        guild = bot.get_guild(GUILD_ID)
        user = session.get("discord_user") or {}
        created_by = int(user.get("id", 0) or 0)
        now = int(time.time()); ends = now + minutes * 60
        event_id = create_event_record("dashboard", title, prize, now, ends, created_by)
        if guild and bot.loop.is_running():
            async def send_event():
                ch = await get_channel_by_id(guild, EVENTS_CHANNEL_ID)
                if ch:
                    embed = discord.Embed(title=f"🎉 {title}", description=f"فعالية جديدة بدأت!\n\n**الجائزة:** {coin_line(prize)}\n**تنتهي:** <t:{ends}:R>", color=COLOR_PURPLE, timestamp=discord.utils.utcnow())
                    embed.set_footer(text=f"{BOT_BRAND} | Event #{event_id}")
                    await ch.send(embed=embed)
            asyncio.run_coroutine_threadsafe(send_event(), bot.loop)
        dashboard_log_action("Started event", f"{title} | prize={prize} | minutes={minutes}", session.get("discord_user"))
        return redirect("/dashboard/events?msg=" + urllib.parse.quote("Event started and announced."))
    except Exception as e:
        return redirect("/dashboard/events?err=" + urllib.parse.quote(str(e)))


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
            history = profile.get('warning_history', [])
            warn_rows = "".join([
                f"<tr><td><span class='pill {'ok' if w.get('status')=='cleared' else 'bad'}'>{clean_text(w.get('status',''),40)}</span></td>"
                f"<td><t:{int(w.get('created_at') or 0)}:R></td>"
                f"<td>{clean_text(w.get('reason',''),140)}</td>"
                f"<td>{clean_text(w.get('message',''),180)}</td>"
                f"<td>{clean_text(w.get('moderator',''),120)}</td>"
                f"<td>{clean_text(w.get('cleared_by',''),100)}</td></tr>"
                for w in history[:20]
            ]) or "<tr><td colspan='6'>No warning history</td></tr>"
            roles = ", ".join(profile['roles'][:18]) if profile['roles'] else "No roles / not cached"
            profile_html = f'''
            <div style="height:14px"></div><div class="grid2"><div class="card"><h3>👤 Member Profile</h3><div>{profile['name']}</div><p><span class="pill">ID</span> <code>{profile['user_id']}</code></p><p><b>Balance:</b> {fmt_coin(profile['balance'])}</p><p><b>Admin Received:</b> {fmt_coin(money_audit_member_summary(profile['user_id'])['admin_received'])}</p><p><b>Earned / System:</b> {fmt_coin(money_audit_member_summary(profile['user_id'])['earned_received'])}</p><p><b>Level:</b> {profile['level']} • <b>XP:</b> {fmt_num(profile['xp'])}</p><p><b>Active Warnings:</b> {len(warns)} • <b>Total History:</b> {len(history)}</p><div class="muted small" style="margin-top:8px">Roles:</div><div class="memberroles">{roles}</div></div><div class="card"><h3>⚡ Quick Edit</h3><form method="post" action="/dashboard/economy"><input type="hidden" name="user_id" value="{profile['user_id']}"><label>Money Amount</label><input name="amount" value="1000"><label>Action</label><select name="action"><option value="add">Add</option><option value="remove">Remove</option><option value="set">Set</option></select><div style="height:10px"></div><button class="btn green">Apply Money</button></form><hr><form method="post" action="/dashboard/warnings/clear"><input type="hidden" name="user_id" value="{profile['user_id']}"><label>Clear Reason</label><input name="reason" value="Cleared from user profile"><div style="height:10px"></div><button class="btn red">Clear Active Warnings</button></form></div></div>
            <div style="height:14px"></div><div class="card"><h3>⚠️ Warning History</h3><table class="table"><tr><th>Status</th><th>Time</th><th>Reason</th><th>Message</th><th>By</th><th>Cleared By</th></tr>{warn_rows}</table><p class="muted small">يعرض آخر 20 إنذار، وحتى الإنذارات المتصفرة مستقبلاً.</p></div>
            '''
        except Exception as e:
            profile_html = f"<div class='toast bad'>User lookup failed: {clean_text(str(e), 250)}</div>"
    body = f'''
    {dashboard_toast_html()}
    <div class="card"><h3>👤 User Lookup</h3><form method="get" action="/dashboard/user"><label>Discord User ID</label><input name="user_id" value="{clean_text(user_id, 80)}" placeholder="1125198908231004191"><div style="height:10px"></div><button class="btn primary">Search User</button></form></div>
    {profile_html}
    '''
    return render_dashboard_page("User Lookup", body)



def dashboard_warning_table_rows(rows):
    if not rows:
        return "<div class='warning-empty'>No warnings found</div>"

    html_rows = ""

    for w in rows:
        warning_id = int(w.get("id") or 0)
        status = clean_text(w.get("status", ""), 40)
        pill = "ok" if status == "cleared" else "bad"
        created = int(w.get("created_at") or 0)
        cleared_at = int(w.get("cleared_at") or 0)
        cleared_text = f"<t:{cleared_at}:R>" if cleared_at else "-"
        user_id = int(w.get("user_id") or 0)

        if status == "active":
            action_html = f"""
            <form method="post" action="/dashboard/warnings/clear-one" class="warning-clear-form js-warning-clear">
              <input type="hidden" name="warning_id" value="{warning_id}">
              <input type="hidden" name="ajax" value="1">
              <input name="reason" value="Removed from dashboard" placeholder="Clear reason">
              <button class="btn red">Clear</button>
            </form>
            """
        else:
            action_html = "<span class='muted small'>Saved in history</span>"

        select_html = ""
        if status == "active":
            select_html = f"""
              <label class="warning-select-wrap" title="Select this warning">
                <input type="checkbox" class="js-warning-select" value="{warning_id}">
                <span>Select</span>
              </label>
            """

        html_rows += f"""
        <div class="warning-row" data-warning-id="{warning_id}" data-user-id="{user_id}" data-status="{status}">
          <div class="warning-main">
            <div class="warning-user-block">
              <div class="warning-status-line">
                <span class="pill {pill}">{status}</span>
                <span class="muted small">ID: {warning_id}</span>
              </div>
              {select_html}
              <div class="warning-member">{dashboard_member_name(user_id)}</div>
              <div class="muted small mono">{user_id}</div>
            </div>

            <div class="warning-content-block">
              <div class="warning-meta">
                <span><b>Time:</b> <t:{created}:R></span>
                <span class="muted small">{cc_time(created) if 'cc_time' in globals() else created}</span>
                <span><b>By:</b> {dash_escape(w.get('moderator',''),140) if 'dash_escape' in globals() else html.escape(clean_text(w.get('moderator',''),140))}</span>
              </div>
              <div class="warning-reason"><b>Reason:</b> {dash_escape(w.get('reason',''),220) if 'dash_escape' in globals() else html.escape(clean_text(w.get('reason',''),220))}</div>
              <div class="warning-message">{dash_escape(w.get('message',''),520) if 'dash_escape' in globals() else html.escape(clean_text(w.get('message',''),520))}</div>
              <div class="warning-cleared muted small"><b>Cleared:</b> {cleared_text} • <b>By:</b> {dash_escape(w.get('cleared_by',''),120) if 'dash_escape' in globals() else html.escape(clean_text(w.get('cleared_by',''),120)) or '-'} • <b>Reason:</b> {dash_escape(w.get('clear_reason',''),180) if 'dash_escape' in globals() else html.escape(clean_text(w.get('clear_reason',''),180)) or '-'}</div>
            </div>
          </div>

          <div class="warning-action-block">
            {action_html}
          </div>
        </div>
        """

    return html_rows


@app.route("/dashboard/warnings", methods=["GET"])
def dashboard_warnings_page():
    denied = dashboard_require_admin()
    if denied:
        return denied

    selected_guild_id = dashboard_get_active_guild_id()
    guild_banner = dashboard_guild_banner(selected_guild_id, "Warnings Guild")

    status = request.args.get("status", "all").strip().lower()
    if status not in ("active", "cleared", "all"):
        status = "all"

    user_id_raw = request.args.get("user_id", "").strip()
    uid = int(user_id_raw) if user_id_raw.isdigit() else None

    active, cleared, active_users, total_users = get_warning_summary_counts()
    rows = get_warning_history(user_id=uid, status=status, limit=300)
    table = dashboard_warning_table_rows(rows)

    active_selected = "primary" if status == "active" else ""
    cleared_selected = "primary" if status == "cleared" else ""
    all_selected = "primary" if status == "all" else ""

    body = f'''
    {dashboard_toast_html()}
    {guild_banner}

    <style>
      .warning-tabs {{
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin-top:10px;
      }}
      .warning-actions {{
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        align-items:end;
      }}
      .warning-actions input, .warning-actions select {{
        min-width:190px;
      }}
      .warnings-list {{
        display:flex;
        flex-direction:column;
        gap:12px;
      }}
      .warning-row {{
        display:grid;
        grid-template-columns:minmax(0, 1fr) minmax(210px, 260px);
        gap:14px;
        padding:16px;
        border:1px solid var(--line);
        border-radius:18px;
        background:rgba(15,23,42,.55);
        overflow:hidden;
        transition:.18s ease;
      }}
      .warning-row:hover {{ border-color:rgba(88,101,242,.38); transform:translateY(-1px); }}
      .warning-cleared-row {{ opacity:.72; }}
      .warning-main {{
        display:grid;
        grid-template-columns:220px minmax(0, 1fr);
        gap:14px;
        min-width:0;
      }}
      .warning-user-block,
      .warning-content-block,
      .warning-action-block {{
        min-width:0;
      }}
      .warning-status-line {{
        display:flex;
        gap:8px;
        align-items:center;
        flex-wrap:wrap;
      }}
      .warning-select-wrap {{
        display:inline-flex;
        align-items:center;
        gap:8px;
        margin-top:10px;
        padding:8px 10px;
        border:1px solid rgba(148,163,184,.18);
        background:rgba(2,6,23,.35);
        border-radius:12px;
        color:var(--muted);
        font-size:13px;
        cursor:pointer;
        user-select:none;
      }}
      .warning-select-wrap input {{
        width:16px;
        height:16px;
        min-width:16px !important;
        accent-color:#5865f2;
      }}
      .warning-row.is-selected {{
        border-color:rgba(88,101,242,.9);
        box-shadow:0 0 0 1px rgba(88,101,242,.45), 0 18px 40px rgba(88,101,242,.10);
      }}
      .bulk-warning-bar {{
        position:sticky;
        top:12px;
        z-index:5;
        display:flex;
        align-items:end;
        justify-content:space-between;
        gap:12px;
        padding:14px;
        margin-bottom:14px;
        border:1px solid rgba(88,101,242,.28);
        border-radius:18px;
        background:rgba(15,23,42,.92);
        backdrop-filter:blur(14px);
      }}
      .bulk-warning-left, .bulk-warning-right {{
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        align-items:end;
      }}
      .bulk-warning-bar input {{
        min-width:260px;
      }}
      .bulk-count {{
        font-weight:900;
        color:#c4b5fd;
      }}
      .warning-member {{
        margin-top:10px;
        font-weight:900;
        word-break:break-word;
      }}
      .mono {{
        font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        word-break:break-all;
      }}
      .warning-meta {{
        display:flex;
        gap:12px;
        flex-wrap:wrap;
        color:var(--muted);
        font-size:13px;
        margin-bottom:8px;
      }}
      .warning-reason {{
        font-weight:800;
        margin-bottom:8px;
        word-break:break-word;
        overflow-wrap:anywhere;
      }}
      .warning-message {{
        padding:12px;
        border-radius:14px;
        background:rgba(2,6,23,.45);
        border:1px solid rgba(148,163,184,.14);
        line-height:1.6;
        word-break:break-word;
        overflow-wrap:anywhere;
        white-space:pre-wrap;
      }}
      .warning-cleared {{
        margin-top:9px;
        word-break:break-word;
        overflow-wrap:anywhere;
      }}
      .warning-clear-form {{
        display:flex;
        flex-direction:column;
        gap:10px;
        align-items:stretch;
      }}
      .warning-clear-form input {{
        width:100%;
        min-width:0 !important;
      }}
      .warning-clear-form button {{
        width:100%;
      }}
      .warning-empty {{
        padding:18px;
        color:var(--muted);
        border:1px dashed var(--line);
        border-radius:16px;
      }}
      @media (max-width:1100px) {{
        .warning-row {{
          grid-template-columns:1fr;
        }}
        .warning-main {{
          grid-template-columns:1fr;
        }}
      }}
    </style>

    <div class="hero">
      <div class="card">
        <div class="big">⚠️ Warnings Manager</div>
        <p class="muted">إدارة الإنذارات بشكل مباشر. أي إنذار يتم إزالته ما ينحذف؛ يتحول إلى Cleared ويبقى محفوظ في نفس الجدول.</p>
        <div>{dashboard_role_badge_html()}</div>
      </div>
      <div class="card">
        <h3>Quick Status</h3>
        <p class="muted">Owner كامل الصلاحيات. Admin صلاحيات محدودة حسب الداشبورد.</p>
      </div>
    </div>

    <div class="grid4">
      <div class="card stat"><div class="icon">⚠️</div><div class="num">{fmt_num(active)}</div><div class="label">Active Warnings</div></div>
      <div class="card stat"><div class="icon">✅</div><div class="num">{fmt_num(cleared)}</div><div class="label">Cleared Warnings</div></div>
      <div class="card stat"><div class="icon">👥</div><div class="num">{fmt_num(active_users)}</div><div class="label">Users with Active</div></div>
      <div class="card stat"><div class="icon">📚</div><div class="num">{fmt_num(total_users)}</div><div class="label">Users in History</div></div>
    </div>

    <div style="height:14px"></div>

    <div class="card">
      <h3>🔎 Filter</h3>
      <div class="warning-tabs">
        <a class="btn {all_selected}" href="/dashboard/warnings?status=all">All History</a>
        <a class="btn {active_selected}" href="/dashboard/warnings?status=active">Active Only</a>
        <a class="btn {cleared_selected}" href="/dashboard/warnings?status=cleared">Cleared Only</a>
      </div>
      <div style="height:12px"></div>
      <form method="get" action="/dashboard/warnings" class="warning-actions">
        <div>
          <label>Status</label>
          <select name="status">
            <option value="all" {'selected' if status=='all' else ''}>All history</option>
            <option value="active" {'selected' if status=='active' else ''}>Active only</option>
            <option value="cleared" {'selected' if status=='cleared' else ''}>Cleared only</option>
          </select>
        </div>
        <div>
          <label>User ID</label>
          <input name="user_id" value="{clean_text(user_id_raw,80)}" placeholder="Optional Discord user ID">
        </div>
        <div>
          <label>&nbsp;</label>
          <button class="btn primary">Apply</button>
        </div>
      </form>
    </div>

    <div style="height:14px"></div>

    <div class="card">
      <h3>🧹 Clear All Active Warnings For User</h3>
      <p class="muted">يمسح الإنذارات النشطة لعضو معيّن من الحالة فقط، لكن يحفظها في السجل كـ Cleared.</p>
      <form method="post" action="/dashboard/warnings/clear" class="warning-actions js-warning-clear-all">
        <input type="hidden" name="ajax" value="1">
        <div>
          <label>User ID</label>
          <input name="user_id" required placeholder="Discord user ID">
        </div>
        <div>
          <label>Reason</label>
          <input name="reason" value="Removed from dashboard">
        </div>
        <div>
          <label>&nbsp;</label>
          <button class="btn red">Clear User Active Warnings</button>
        </div>
      </form>
    </div>

    <div style="height:14px"></div>

    <div class="card">
      <h3>📋 Warning History</h3>
      <p class="muted small">تقدر تحدد أكثر من إنذار وتسوي عليها Clear دفعة وحدة. الإنذارات المزالة تبقى محفوظة كـ Cleared.</p>

      <div class="bulk-warning-bar">
        <div class="bulk-warning-left">
          <button type="button" class="btn" id="selectActiveWarnings">Select active</button>
          <button type="button" class="btn" id="clearSelectionWarnings">Clear selection</button>
          <span class="muted small"><span class="bulk-count" id="selectedWarningsCount">0</span> selected</span>
        </div>
        <div class="bulk-warning-right">
          <div>
            <label>Bulk clear reason</label>
            <input id="bulkWarningReason" value="Removed from dashboard" placeholder="Reason for selected warnings">
          </div>
          <button type="button" class="btn red" id="bulkClearWarningsBtn">Clear Selected</button>
        </div>
      </div>

      <div class="warnings-list">
        {table}
      </div>
    </div>
    

    <script>
      function showWarningToast(message, ok=true) {{
        let box = document.querySelector('.js-warning-toast');
        if (!box) {{
          box = document.createElement('div');
          box.className = 'toast js-warning-toast';
          const target = document.querySelector('.hero') || document.body;
          target.parentNode.insertBefore(box, target.nextSibling);
        }}
        box.className = 'toast js-warning-toast ' + (ok ? 'ok' : 'bad');
        box.textContent = message;
        setTimeout(() => {{ if (box) box.remove(); }}, 3500);
      }}

      async function postWarningForm(form) {{
        const btn = form.querySelector('button');
        const oldText = btn ? btn.textContent : '';
        if (btn) {{ btn.disabled = true; btn.textContent = 'Saving...'; }}
        try {{
          const res = await fetch(form.action, {{
            method: 'POST',
            body: new FormData(form),
            headers: {{ 'X-Requested-With': 'XMLHttpRequest' }}
          }});
          const data = await res.json();
          if (!data.ok) throw new Error(data.error || 'Failed');
          return data;
        }} finally {{
          if (btn) {{ btn.disabled = false; btn.textContent = oldText; }}
        }}
      }}

      const selectedWarnings = new Set();

      function updateWarningSelectionUI() {{
        document.querySelectorAll('.js-warning-select').forEach(chk => {{
          const row = chk.closest('.warning-row');
          if (chk.checked) {{
            selectedWarnings.add(chk.value);
            if (row) row.classList.add('is-selected');
          }} else {{
            selectedWarnings.delete(chk.value);
            if (row) row.classList.remove('is-selected');
          }}
        }});
        const count = document.getElementById('selectedWarningsCount');
        if (count) count.textContent = selectedWarnings.size;
      }}

      document.querySelectorAll('.js-warning-select').forEach(chk => {{
        chk.addEventListener('change', updateWarningSelectionUI);
      }});

      const selectActiveBtn = document.getElementById('selectActiveWarnings');
      if (selectActiveBtn) {{
        selectActiveBtn.addEventListener('click', () => {{
          const activeChecks = Array.from(document.querySelectorAll('.warning-row[data-status="active"] .js-warning-select'));
          const allSelected = activeChecks.length > 0 && activeChecks.every(chk => chk.checked);
          activeChecks.forEach(chk => chk.checked = !allSelected);
          updateWarningSelectionUI();
          selectActiveBtn.textContent = allSelected ? 'Select active' : 'Unselect active';
        }});
      }}

      const clearSelectionBtn = document.getElementById('clearSelectionWarnings');
      if (clearSelectionBtn) {{
        clearSelectionBtn.addEventListener('click', () => {{
          document.querySelectorAll('.js-warning-select').forEach(chk => chk.checked = false);
          updateWarningSelectionUI();
        }});
      }}

      const bulkClearBtn = document.getElementById('bulkClearWarningsBtn');
      if (bulkClearBtn) {{
        bulkClearBtn.addEventListener('click', async () => {{
          updateWarningSelectionUI();
          const ids = Array.from(selectedWarnings);
          if (!ids.length) {{ showWarningToast('Select at least one active warning first.', false); return; }}
          if (!confirm('Clear ' + ids.length + ' selected warnings? They will stay saved as cleared.')) return;
          const oldText = bulkClearBtn.textContent;
          bulkClearBtn.disabled = true;
          bulkClearBtn.textContent = 'Clearing...';
          try {{
            const formData = new FormData();
            ids.forEach(id => formData.append('warning_ids', id));
            formData.append('reason', (document.getElementById('bulkWarningReason') || {{}}).value || 'Removed from dashboard');
            formData.append('ajax', '1');
            const res = await fetch('/dashboard/warnings/clear-selected', {{
              method: 'POST',
              body: formData,
              headers: {{ 'X-Requested-With': 'XMLHttpRequest' }}
            }});
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'Failed');
            (data.cleared_ids || []).forEach(id => {{
              const row = document.querySelector('.warning-row[data-warning-id="' + id + '"]');
              if (!row) return;
              row.dataset.status = 'cleared';
              row.classList.add('warning-cleared-row');
              row.classList.remove('is-selected');
              const chk = row.querySelector('.js-warning-select');
              if (chk) {{ chk.checked = false; chk.disabled = true; }}
              const pill = row.querySelector('.pill');
              if (pill) {{ pill.className = 'pill ok'; pill.textContent = 'cleared'; }}
              const action = row.querySelector('.warning-action-block');
              if (action) action.innerHTML = '<span class="muted small">Saved in history</span>';
              const clearedLine = row.querySelector('.warning-cleared');
              if (clearedLine) clearedLine.innerHTML = '<b>Cleared:</b> just now • <b>By:</b> Dashboard • <b>Reason:</b> ' + (data.reason || 'Removed from dashboard');
            }});
            selectedWarnings.clear();
            updateWarningSelectionUI();
            showWarningToast(data.message || 'Selected warnings cleared.');
          }} catch (err) {{
            showWarningToast(err.message || 'Could not clear selected warnings.', false);
          }} finally {{
            bulkClearBtn.disabled = false;
            bulkClearBtn.textContent = oldText;
          }}
        }});
      }}

      document.querySelectorAll('.js-warning-clear').forEach(form => {{
        form.addEventListener('submit', async (e) => {{
          e.preventDefault();
          if (!confirm('Clear this warning? It will stay saved as cleared.')) return;
          try {{
            const data = await postWarningForm(form);
            const row = form.closest('.warning-row');
            if (row) {{
              row.dataset.status = 'cleared';
              row.classList.add('warning-cleared-row');
              const pill = row.querySelector('.pill');
              if (pill) {{ pill.className = 'pill ok'; pill.textContent = 'cleared'; }}
              const action = row.querySelector('.warning-action-block');
              if (action) action.innerHTML = '<span class="muted small">Saved in history</span>';
              const clearedLine = row.querySelector('.warning-cleared');
              if (clearedLine) clearedLine.innerHTML = '<b>Cleared:</b> just now • <b>By:</b> Dashboard • <b>Reason:</b> ' + (data.reason || 'Removed from dashboard');
            }}
            showWarningToast(data.message || 'Warning cleared and saved in history.');
          }} catch (err) {{
            showWarningToast(err.message || 'Could not clear warning.', false);
          }}
        }});
      }});

      document.querySelectorAll('.js-warning-clear-all').forEach(form => {{
        form.addEventListener('submit', async (e) => {{
          e.preventDefault();
          const userId = (form.querySelector('input[name="user_id"]') || {{}}).value || '';
          if (!userId.trim()) {{ showWarningToast('Write a User ID first.', false); return; }}
          if (!confirm('Clear all active warnings for this user? They will stay saved as cleared.')) return;
          try {{
            const data = await postWarningForm(form);
            document.querySelectorAll('.warning-row[data-user-id="' + userId.trim() + '"][data-status="active"]').forEach(row => {{
              row.dataset.status = 'cleared';
              row.classList.add('warning-cleared-row');
              const pill = row.querySelector('.pill');
              if (pill) {{ pill.className = 'pill ok'; pill.textContent = 'cleared'; }}
              const action = row.querySelector('.warning-action-block');
              if (action) action.innerHTML = '<span class="muted small">Saved in history</span>';
            }});
            showWarningToast(data.message || 'Warnings cleared and saved in history.');
          }} catch (err) {{
            showWarningToast(err.message || 'Could not clear warnings.', false);
          }}
        }});
      }});
    </script>

    '''

    return render_dashboard_page("Warnings", body)


@app.route("/dashboard/warnings/clear-one", methods=["POST"])
def dashboard_clear_single_warning():
    denied = dashboard_require_admin()
    if denied:
        return denied

    warning_id = request.form.get("warning_id", "").strip()
    reason = request.form.get("reason", "Removed from dashboard").strip() or "Removed from dashboard"

    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("ajax") == "1"

    if not warning_id.isdigit():
        if wants_json:
            return {"ok": False, "error": "Invalid warning ID"}, 400
        return redirect("/dashboard/warnings?err=" + urllib.parse.quote("Invalid warning ID"))

    admin = session.get("discord_user") or {}
    admin_name = admin.get("username", "Dashboard Admin")
    cleared, user_id = clear_single_warning_by_id(
        int(warning_id),
        cleared_by=f"{admin_name} ({admin.get('id','0')})",
        clear_reason=reason
    )

    dashboard_log_action("Cleared one warning", f"warning_id={warning_id} | user_id={user_id} | count={cleared} | reason={reason}", admin)

    if cleared:
        if wants_json:
            return {"ok": True, "cleared": int(cleared), "user_id": str(user_id or ""), "reason": reason, "message": "Warning cleared and saved in history."}
        return redirect("/dashboard/warnings?status=all&user_id=" + urllib.parse.quote(str(user_id or "")) + "&msg=" + urllib.parse.quote("Warning cleared and saved in history."))

    if wants_json:
        return {"ok": False, "error": "Warning not found or already cleared."}, 404
    return redirect("/dashboard/warnings?status=all&err=" + urllib.parse.quote("Warning not found or already cleared."))


@app.route("/dashboard/warnings/clear-selected", methods=["POST"])
def dashboard_clear_selected_warnings():
    denied = dashboard_require_admin()
    if denied:
        return denied

    raw_ids = request.form.getlist("warning_ids")
    reason = request.form.get("reason", "Removed from dashboard").strip() or "Removed from dashboard"
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("ajax") == "1"

    warning_ids = []
    for item in raw_ids:
        if str(item).isdigit():
            warning_ids.append(int(item))

    warning_ids = list(dict.fromkeys(warning_ids))[:100]

    if not warning_ids:
        if wants_json:
            return {"ok": False, "error": "No valid warning IDs selected."}, 400
        return redirect("/dashboard/warnings?err=" + urllib.parse.quote("No valid warning IDs selected."))

    admin = session.get("discord_user") or {}
    admin_name = admin.get("username", "Dashboard Admin")
    cleared_ids = []
    affected_users = set()

    for warning_id in warning_ids:
        cleared, user_id = clear_single_warning_by_id(
            int(warning_id),
            cleared_by=f"{admin_name} ({admin.get('id','0')})",
            clear_reason=reason
        )
        if cleared:
            cleared_ids.append(int(warning_id))
            if user_id:
                affected_users.add(str(user_id))

    dashboard_log_action(
        "Bulk cleared warnings",
        f"count={len(cleared_ids)} | ids={','.join(map(str, cleared_ids[:50]))} | reason={reason}",
        admin
    )

    if wants_json:
        return {
            "ok": True,
            "cleared": len(cleared_ids),
            "cleared_ids": cleared_ids,
            "affected_users": sorted(affected_users),
            "reason": reason,
            "message": f"Cleared {len(cleared_ids)} selected warnings and kept them in history."
        }

    return redirect("/dashboard/warnings?status=all&msg=" + urllib.parse.quote(f"Cleared {len(cleared_ids)} selected warnings and kept them in history."))


@app.route("/dashboard/warnings/clear", methods=["POST"])
def dashboard_clear_warnings():
    denied = dashboard_require_admin()
    if denied:
        return denied

    user_id = request.form.get("user_id", "").strip()
    reason = request.form.get("reason", "Removed from dashboard").strip() or "Removed from dashboard"

    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.form.get("ajax") == "1"

    if not user_id.isdigit():
        if wants_json:
            return {"ok": False, "error": "Invalid user ID"}, 400
        return redirect("/dashboard/warnings?err=" + urllib.parse.quote("Invalid user ID"))

    admin = session.get("discord_user") or {}
    admin_name = admin.get("username", "Dashboard Admin")

    cleared = clear_warnings_for_user(
        int(user_id),
        cleared_by=f"{admin_name} ({admin.get('id','0')})",
        clear_reason=reason
    )

    dashboard_log_action("Cleared user warnings", f"user_id={user_id} | count={cleared} | reason={reason}", admin)
    if wants_json:
        return {"ok": True, "cleared": int(cleared), "user_id": user_id, "reason": reason, "message": f"Cleared {cleared} active warnings and kept them in history."}
    return redirect("/dashboard/warnings?status=all&user_id=" + urllib.parse.quote(user_id) + "&msg=" + urllib.parse.quote(f"Cleared {cleared} active warnings and kept them in history."))



@app.route("/dashboard/admin-access", methods=["GET"])
def dashboard_admin_access_page():
    # Admin Access is Owner-only. Private owner exception is checked first so Jaber cannot be locked out.
    if not dashboard_session_is_private_owner(session.get("discord_user") or {}):
        denied = dashboard_require_owner()
        if denied:
            return denied
    elif not session.get("discord_user"):
        return redirect("/login")

    owner_role_ids = dashboard_dynamic_owner_role_ids() | set(DASHBOARD_OWNER_ROLE_IDS)
    admin_role_ids = dashboard_dynamic_admin_role_ids() | set(DASHBOARD_LIMITED_ADMIN_ROLE_IDS) | set(DASHBOARD_ADMIN_ROLE_IDS)
    owner_user_ids = dashboard_dynamic_owner_user_ids() | set(DASHBOARD_OWNER_USER_IDS)
    admin_user_ids = dashboard_dynamic_admin_user_ids()

    # Owner wins if the same role/user is selected in both lists.
    admin_role_ids = admin_role_ids - owner_role_ids
    admin_user_ids = admin_user_ids - owner_user_ids - set(DASHBOARD_PRIVATE_OWNER_USER_IDS)

    roles = dashboard_get_guild_roles()

    # IMPORTANT PERFORMANCE FIX:
    # Do NOT chunk/fetch members once for every role. That makes /admin-access look like it is loading forever.
    # Default uses cached members instantly. Add ?refresh=1 when you want to force one guild chunk refresh.
    force_refresh = str(request.args.get("refresh", "")).strip() == "1"
    all_members = dashboard_get_guild_members_sync(force_chunk=force_refresh)
    humans = [m for m in all_members if not getattr(m, "bot", False)]
    member_count = len(humans)
    bot_count = len([m for m in all_members if getattr(m, "bot", False)])

    members_by_role = {}
    for member in all_members:
        try:
            if getattr(member, "bot", False):
                continue
            for role in getattr(member, "roles", []):
                members_by_role.setdefault(int(role.id), []).append(member)
        except Exception:
            pass

    for rid in list(members_by_role.keys()):
        try:
            members_by_role[rid] = sorted(members_by_role[rid], key=lambda m: str(m.display_name).lower())
        except Exception:
            pass

    def fast_access_badge_for_member(member):
        try:
            uid = int(member.id)
            if uid in DASHBOARD_PRIVATE_OWNER_USER_IDS or uid in owner_user_ids:
                return "<span class='pill ok'>Owner</span>"
            if uid in admin_user_ids:
                return "<span class='pill'>Admin</span>"
            role_ids = {int(r.id) for r in getattr(member, "roles", [])}
            if role_ids.intersection(owner_role_ids):
                return "<span class='pill ok'>Owner</span>"
            if role_ids.intersection(admin_role_ids):
                return "<span class='pill'>Admin</span>"
        except Exception:
            pass
        return "<span class='pill bad'>No Access</span>"

    def member_line_fast(member):
        try:
            avatar = member.display_avatar.url
        except Exception:
            avatar = ""
        if avatar:
            avatar_html = f"<img src='{dash_escape(avatar, 300)}' class='miniavatar'>"
        else:
            avatar_html = "<span class='miniavatar blankavatar'>?</span>"
        return (
            f"<a class='memberline' href='/dashboard/admin-access/member/{member.id}'>"
            f"{avatar_html}"
            f"<span><b>{dash_escape(member.display_name, 80)}</b><br>"
            f"<span class='muted small'>@{dash_escape(str(member), 90)} • ID: <code>{member.id}</code></span>{dashboard_member_roles_html(member, limit=3)}</span>"
            f"<span class='memberbadge'>{fast_access_badge_for_member(member)}</span>"
            f"</a>"
        )

    role_rows = []
    for role in roles:
        human_members = members_by_role.get(int(role.id), [])
        sample_members = human_members[:6]
        more_count = max(0, len(human_members) - len(sample_members))
        member_links = "".join([member_line_fast(member) for member in sample_members])
        if more_count:
            member_links += f"<div class='muted small' style='padding:8px 0 0 42px'>+{more_count} more members</div>"
        if not member_links:
            member_links = "<span class='muted small'>No human members in this role.</span>"

        managed_note = " <span class='muted small'>Managed</span>" if getattr(role, "managed", False) else ""
        owner_checked = "checked" if role.id in owner_role_ids else ""
        admin_checked = "checked" if role.id in admin_role_ids else ""
        role_rows.append(f"""
        <tr>
          <td>
            {dashboard_role_chip_for_role(role, include_id=False)}{managed_note}<br>
            <span class="muted small">ID: <code>{role.id}</code> • Position: {role.position} • Members: {len(human_members)}</span>
          </td>
          <td><label class="checkrow ownercheck"><input type="checkbox" name="owner_roles" value="{role.id}" {owner_checked}> Owner</label></td>
          <td><label class="checkrow admincheck"><input type="checkbox" name="admin_roles" value="{role.id}" {admin_checked}> Admin</label></td>
          <td>{member_links}</td>
        </tr>
        """)

    roles_html = "".join(role_rows) or "<tr><td colspan='4'>No roles found. Make sure the bot is online and can read the guild.</td></tr>"

    owner_users_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<br><span class='muted small'>ID: <code>{uid}</code></span></td><td><span class='pill ok'>Owner</span></td><td><a class='btn smallbtn' href='/dashboard/admin-access/member/{uid}'>Edit</a></td></tr>"
        for uid in sorted(owner_user_ids)
    ]) or "<tr><td colspan='3'>No visible direct Owner users. Private owner exception is hidden.</td></tr>"

    admin_users_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<br><span class='muted small'>ID: <code>{uid}</code></span></td><td><span class='pill'>Admin</span></td><td><a class='btn smallbtn' href='/dashboard/admin-access/member/{uid}'>Edit</a></td></tr>"
        for uid in sorted(admin_user_ids)
    ]) or "<tr><td colspan='3'>No direct Admin users selected yet.</td></tr>"

    owner_roles_text = ", ".join([dashboard_role_name(rid) for rid in sorted(owner_role_ids)]) if owner_role_ids else "No Owner Access roles selected yet. Bootstrap owner still works."
    admin_roles_text = ", ".join([dashboard_role_name(rid) for rid in sorted(admin_role_ids)]) if admin_role_ids else "No Admin Access roles selected yet."

    member_cache_note = "Forced refresh used." if force_refresh else "Using fast cached members. If members are missing, click Refresh Members once."

    body = f"""
    {dashboard_toast_html()}

    <style>
      .access-note {{line-height:1.8}}
      .checkrow {{display:flex; align-items:center; gap:10px; margin:0; color:var(--text); font-size:13px; font-weight:900}}
      .checkrow input {{width:auto; transform:scale(1.15)}}
      .ownercheck {{color:#fde68a}}
      .admincheck {{color:#bfdbfe}}
      .access-box {{border:1px solid var(--line); border-radius:18px; padding:14px; background:rgba(15,23,42,.55)}}
      .miniavatar {{width:30px;height:30px;border-radius:999px;object-fit:cover;flex:0 0 auto;background:#1e293b;display:inline-flex;align-items:center;justify-content:center}}
      .blankavatar {{font-size:12px;color:var(--muted)}}
      .memberline {{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--text);padding:8px;border:1px solid rgba(148,163,184,.12);border-radius:14px;margin:6px 0;background:rgba(2,6,23,.25)}}
      .memberline:hover {{border-color:rgba(124,92,255,.65);background:rgba(124,92,255,.08)}}
      .memberbadge {{margin-left:auto}}
      .smallbtn {{padding:8px 12px;font-size:12px;border-radius:12px}}
      .quickform {{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
      .quickform input {{max-width:320px}}
      .table td {{vertical-align:top}}
    </style>

    <div class="hero">
      <div class="card">
        <div class="big">🔐 Admin Access</div>
        <p class="muted">هنا تضبط صلاحيات الداشبورد من داخل الموقع: رتب كاملة أو أشخاص محددين. اضغط على أي عضو عشان تختار صلاحياته.</p>
        <div style="height:10px"></div>
        <span class="pill gold">Owner = Full Access</span>
        <span class="pill">Admin = Limited Access</span>
        <span class="pill ok">Members loaded: {member_count}</span>
        <span class="pill">Bots: {bot_count}</span>
        <span class="pill">{dash_escape(member_cache_note, 120)}</span>
        <a class="btn smallbtn" href="/dashboard/admin-access?refresh=1">🔄 Refresh Members</a>
      </div>
      <div class="card">
        <h3>🛡️ الشرح</h3>
        <p class="muted access-note">
          <b>Owner</b> يقدر يسوي كل شيء داخل الداشبورد. <b>Admin</b> يدخل صفحات المراقبة والإنذارات والأشياء المحدودة فقط.<br>
          تقدر تعطي الصلاحية عن طريق رتبة كاملة أو تضغط عضو وتعطيه صلاحية مباشرة.
        </p>
      </div>
    </div>

    <div class="grid2">
      <div class="card">
        <h3>👑 Owner Access</h3>
        <p class="muted access-note">صلاحية كاملة: Settings, Control Center, Audit, OAuth Debug, Memory actions, Economy/Levels edit, Admin Access.</p>
        <div class="access-box">{owner_roles_text}</div>
      </div>
      <div class="card">
        <h3>🧰 Admin Access</h3>
        <p class="muted access-note">صلاحية محدودة: Overview, Command Center, Warnings, User Lookup ومراقبة السيرفر بدون التحكم الخطير.</p>
        <div class="access-box">{admin_roles_text}</div>
      </div>
    </div>

    <div style="height:14px"></div>

    <div class="card">
      <h3>👤 Give Access to Specific Member</h3>
      <p class="muted">إذا الشخص ما عنده رتبة معينة أو تبي استثناء واضح، حط User ID واضغط Open. بعدين اختار Owner / Admin / No Access.</p>
      <form class="quickform" method="get" action="/dashboard/admin-access/member-open">
        <input name="user_id" placeholder="Discord User ID" required>
        <button class="btn">Open Member</button>
      </form>
    </div>

    <div style="height:14px"></div>

    <div class="grid2">
      <div class="card">
        <h3>👑 Direct Owner Users</h3>
        <table class="table"><tr><th>Member</th><th>Access</th><th>Action</th></tr>{owner_users_html}</table>
      </div>
      <div class="card">
        <h3>🧰 Direct Admin Users</h3>
        <table class="table"><tr><th>Member</th><th>Access</th><th>Action</th></tr>{admin_users_html}</table>
      </div>
    </div>

    <div style="height:14px"></div>

    <form method="post" action="/dashboard/admin-access">
      <div class="card">
        <h3>⚙️ Roles & Members</h3>
        <p class="muted">تقدر تحدد الرتب وتشوف أول أعضاء داخل كل رتبة. اضغط على أي عضو عشان تعطيه صلاحية مباشرة. إذا رتبة مختارة Owner و Admin بنفس الوقت، بيتم اعتمادها Owner فقط.</p>
        <table class="table">
          <tr><th>Discord Role</th><th>Owner</th><th>Admin</th><th>Members in Role</th></tr>
          {roles_html}
        </table>
        <div style="height:12px"></div>
        <button class="btn green" onclick="return confirm('Save dashboard access roles?');">💾 Save Role Access</button>
        <a class="btn" href="/dashboard">Back</a>
      </div>
    </form>
    """
    return render_dashboard_page("Admin Access", body)


@app.route("/dashboard/admin-access/member-open", methods=["GET"])
def dashboard_admin_access_member_open():
    denied = dashboard_require_owner()
    if denied:
        return denied
    user_id = str(request.args.get("user_id", "")).strip()
    if not user_id.isdigit():
        return redirect("/dashboard/admin-access?err=" + urllib.parse.quote("Enter a valid Discord User ID."))
    return redirect(f"/dashboard/admin-access/member/{user_id}")


@app.route("/dashboard/admin-access/member/<int:user_id>", methods=["GET"])
def dashboard_member_access_page(user_id):
    denied = dashboard_require_owner()
    if denied:
        return denied

    member = dashboard_get_member_sync(user_id)
    direct_owner_ids = dashboard_dynamic_owner_user_ids()
    direct_admin_ids = dashboard_dynamic_admin_user_ids()

    if user_id in DASHBOARD_PRIVATE_OWNER_USER_IDS:
        direct_state = "private_owner"
    elif user_id in direct_owner_ids or user_id in DASHBOARD_OWNER_USER_IDS:
        direct_state = "owner"
    elif user_id in direct_admin_ids:
        direct_state = "admin"
    else:
        direct_state = "none"

    name = str(member) if member else f"User {user_id}"
    display_name = member.display_name if member else name
    avatar = member.display_avatar.url if member else ""
    avatar_html = f"<img src='{dash_escape(avatar, 300)}' style='width:74px;height:74px;border-radius:24px;object-fit:cover'>" if avatar else "<div style='width:74px;height:74px;border-radius:24px;background:#1e293b;display:flex;align-items:center;justify-content:center'>?</div>"
    roles_html = ""
    if member:
        role_parts = []
        for role in sorted([r for r in member.roles if r.name != "@everyone"], key=lambda r: r.position, reverse=True):
            access_hint = ""
            if role.id in (dashboard_dynamic_owner_role_ids() | set(DASHBOARD_OWNER_ROLE_IDS)):
                access_hint = " <span class='pill ok'>Owner role</span>"
            elif role.id in (dashboard_dynamic_admin_role_ids() | set(DASHBOARD_LIMITED_ADMIN_ROLE_IDS) | set(DASHBOARD_ADMIN_ROLE_IDS)):
                access_hint = " <span class='pill'>Admin role</span>"
            role_parts.append(f"<div class='rolepill'>@{dash_escape(role.name, 80)}{access_hint}<br><span class='muted small'>ID: <code>{role.id}</code></span></div>")
        roles_html = "".join(role_parts) or "<p class='muted'>No roles.</p>"
    else:
        roles_html = "<p class='muted'>Member not found in cache. You can still set direct access by ID.</p>"

    owner_checked = "checked" if direct_state == "owner" else ""
    admin_checked = "checked" if direct_state == "admin" else ""
    none_checked = "checked" if direct_state == "none" else ""
    private_note = ""
    disabled = ""
    if direct_state == "private_owner":
        owner_checked = "checked"
        disabled = "disabled"
        private_note = "<div class='toast ok'>هذا العضو عنده Private Owner Exception داخل الكود وما يطلع ضمن قوائم التعديل العادية.</div>"

    body = f"""
    {dashboard_toast_html()}
    {private_note}
    <style>
      .profilehead {{display:flex;gap:16px;align-items:center}}
      .rolepill {{border:1px solid var(--line);border-radius:16px;padding:10px 12px;margin:8px 0;background:rgba(15,23,42,.45)}}
      .radioaccess {{display:grid;gap:10px;margin-top:12px}}
      .radioaccess label {{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);border-radius:16px;padding:14px;background:rgba(15,23,42,.45);font-weight:900}}
      .radioaccess input {{width:auto;margin-top:3px}}
    </style>

    <div class="card">
      <div class="profilehead">
        {avatar_html}
        <div>
          <div class="big">{dash_escape(display_name, 100)}</div>
          <p class="muted">@{dash_escape(name, 120)} • ID: <code>{user_id}</code></p>
          {dashboard_member_access_badge(user_id)}
        </div>
      </div>
    </div>

    <div style="height:14px"></div>

    <div class="grid2">
      <div class="card">
        <h3>🔐 Dashboard Permission</h3>
        <p class="muted">اختار صلاحية مباشرة لهذا العضو. الصلاحية المباشرة تفيد لو ما تبي تعطي رتبة كاملة صلاحية داشبورد.</p>
        <form method="post" action="/dashboard/admin-access/member/{user_id}">
          <div class="radioaccess">
            <label><input type="radio" name="access_level" value="owner" {owner_checked} {disabled}> <span>👑 Owner<br><span class='muted small'>Full access to everything in dashboard.</span></span></label>
            <label><input type="radio" name="access_level" value="admin" {admin_checked} {disabled}> <span>🧰 Admin<br><span class='muted small'>Limited access for monitoring and moderation.</span></span></label>
            <label><input type="radio" name="access_level" value="none" {none_checked} {disabled}> <span>🚫 No Direct Access<br><span class='muted small'>Remove direct access. Role-based access can still apply.</span></span></label>
          </div>
          <div style="height:12px"></div>
          <button class="btn green" {disabled}>💾 Save Member Access</button>
          <a class="btn" href="/dashboard/admin-access">Back</a>
        </form>
      </div>
      <div class="card">
        <h3>🏷️ Discord Roles</h3>
        <p class="muted">الرتب اللي عند العضو حاليًا، وإذا رتبة منها تعطي صلاحية داشبورد بيطلع جنبها توضيح.</p>
        {roles_html}
      </div>
    </div>
    """
    return render_dashboard_page("Member Access", body)


@app.route("/dashboard/admin-access/member/<int:user_id>", methods=["POST"])
def dashboard_member_access_action(user_id):
    denied = dashboard_require_owner()
    if denied:
        return denied

    if int(user_id) in DASHBOARD_PRIVATE_OWNER_USER_IDS:
        return redirect(f"/dashboard/admin-access/member/{user_id}?err=" + urllib.parse.quote("Private owner exception cannot be changed here."))

    level = str(request.form.get("access_level", "none")).strip().lower()
    if level not in {"owner", "admin", "none"}:
        level = "none"

    data = dashboard_load_settings_file()
    owner_ids = set(parse_dashboard_user_id_list(data.get("dashboard_owner_user_ids", [])))
    admin_ids = set(parse_dashboard_user_id_list(data.get("dashboard_admin_user_ids", [])))

    owner_ids.discard(int(user_id))
    admin_ids.discard(int(user_id))

    if level == "owner":
        owner_ids.add(int(user_id))
    elif level == "admin":
        admin_ids.add(int(user_id))

    dashboard_merge_settings({
        "dashboard_owner_user_ids": sorted(owner_ids),
        "dashboard_admin_user_ids": sorted(admin_ids),
        "dashboard_member_access_updated_at": int(time.time()),
        "dashboard_member_access_updated_by": str((session.get("discord_user") or {}).get("username", "Dashboard")),
    })

    admin = session.get("discord_user", {}).get("username", "Dashboard")
    dashboard_log_action("Updated dashboard member access", f"user_id={user_id} | level={level}", admin)
    return redirect(f"/dashboard/admin-access/member/{user_id}?msg=" + urllib.parse.quote("Member dashboard access saved."))


@app.route("/dashboard/admin-access", methods=["POST"])
def dashboard_admin_access_action():
    denied = dashboard_require_owner()
    if denied:
        return denied

    owner_roles = parse_dashboard_role_id_list(request.form.getlist("owner_roles"))
    admin_roles = parse_dashboard_role_id_list(request.form.getlist("admin_roles"))
    owner_set = set(owner_roles)
    admin_roles = [role_id for role_id in admin_roles if role_id not in owner_set]

    dashboard_merge_settings({
        "dashboard_owner_role_ids": owner_roles,
        "dashboard_admin_role_ids": admin_roles,
        "dashboard_access_updated_at": int(time.time()),
        "dashboard_access_updated_by": str((session.get("discord_user") or {}).get("username", "Dashboard")),
    })

    admin = session.get("discord_user", {}).get("username", "Dashboard")
    dashboard_log_action("Updated dashboard access roles", f"owner_roles={owner_roles} | admin_roles={admin_roles}", admin)

    return redirect("/dashboard/admin-access?msg=" + urllib.parse.quote("Admin Access roles saved."))


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
    denied = dashboard_require_owner()
    if denied:
        return denied
    selected_guild_id = dashboard_get_active_guild_id()
    guild_banner = dashboard_guild_banner(selected_guild_id, "Control Center Guild")
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
    {guild_banner}
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
    denied = dashboard_require_owner()
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
    denied = dashboard_require_owner()
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
    denied = dashboard_require_owner()
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





# =========================
# NM LOG VAULT STRICT GUILD FILTER OVERRIDE
# =========================

def nm_log_vault_where(guild_id=0, log_type="all", query="", deleted_filter="all", channel_id="all", include_legacy=False):
    where = []
    params = []

    gid = nm_safe_int(guild_id, 0)
    if gid:
        if include_legacy:
            where.append("(guild_id = ? OR guild_id IS NULL OR guild_id = 0)")
            params.append(gid)
        else:
            where.append("guild_id = ?")
            params.append(gid)

    if log_type and str(log_type) != "all":
        where.append("log_type = ?")
        params.append(str(log_type))

    if channel_id and str(channel_id) != "all":
        try:
            where.append("discord_channel_id = ?")
            params.append(int(channel_id))
        except:
            pass

    if deleted_filter == "deleted":
        where.append("deleted_from_discord = 1")
    elif deleted_filter == "saved":
        where.append("(deleted_from_discord IS NULL OR deleted_from_discord = 0)")

    if query:
        like = f"%{str(query)[:120]}%"
        where.append("(title LIKE ? OR description LIKE ? OR discord_channel_name LIKE ? OR deleted_by_name LIKE ?)")
        params.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    return where_sql, params


def log_vault_recent(guild_id=0, limit=80, offset=0, log_type="all", query="", deleted_filter="all", channel_id="all"):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_vault_where(guild_id, log_type, query, deleted_filter, channel_id, include_legacy)

        cur.execute(f"""
            SELECT id, guild_id, log_type, title, description, discord_channel_id, discord_channel_name,
                   discord_message_id, deleted_from_discord, deleted_by_id, deleted_by_name, created_at, deleted_at
            FROM dashboard_log_vault
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, tuple(params + [int(limit), int(offset)]))
        rows = cur.fetchall()

        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql}", tuple(params))
        total = int(cur.fetchone()[0] or 0)

        conn.close()
        return rows, total
    except Exception as e:
        print(f"Log Vault recent error: {e}")
        return [], 0


def log_vault_counts(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_vault_where(guild_id, "all", "", "all", "all", include_legacy)
        since = int(time.time()) - 86400

        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql}", tuple(params))
        total = int(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql + (' AND' if where_sql else 'WHERE')} deleted_from_discord = 1", tuple(params))
        deleted = int(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COUNT(DISTINCT log_type) FROM dashboard_log_vault {where_sql}", tuple(params))
        types = int(cur.fetchone()[0] or 0)

        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql + (' AND' if where_sql else 'WHERE')} created_at >= ?", tuple(params + [since]))
        today = int(cur.fetchone()[0] or 0)

        conn.close()
        return total, deleted, types, today
    except Exception as e:
        print(f"Log Vault counts error: {e}")
        return 0, 0, 0, 0


def log_vault_types(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_vault_where(guild_id, "all", "", "all", "all", include_legacy)

        cur.execute(f"""
            SELECT log_type, COUNT(*)
            FROM dashboard_log_vault
            {where_sql}
            GROUP BY log_type
            ORDER BY COUNT(*) DESC
        """, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Log Vault types error: {e}")
        return []


def log_vault_channels(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_vault_where(guild_id, "all", "", "all", "all", include_legacy)

        cur.execute(f"""
            SELECT discord_channel_id, discord_channel_name, COUNT(*)
            FROM dashboard_log_vault
            {where_sql}
            GROUP BY discord_channel_id, discord_channel_name
            ORDER BY COUNT(*) DESC
        """, tuple(params))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Log Vault channels error: {e}")
        return []



# =========================
# NM STRICT LOG VAULT OVERRIDE - no mixed guild logs
# =========================

def nm_log_where(guild_id=0, log_type="all", query="", deleted_filter="all", channel_id="all", include_legacy=False):
    gid = nm_int(guild_id or nm_active_guild_id(), GUILD_ID)
    where = []
    params = []

    if include_legacy:
        where.append("(guild_id = ? OR guild_id IS NULL OR guild_id = 0)")
        params.append(gid)
    else:
        where.append("guild_id = ?")
        params.append(gid)

    if log_type and str(log_type) != "all":
        where.append("log_type = ?")
        params.append(str(log_type))

    if channel_id and str(channel_id) != "all":
        try:
            where.append("discord_channel_id = ?")
            params.append(int(channel_id))
        except:
            pass

    if deleted_filter == "deleted":
        where.append("deleted_from_discord = 1")
    elif deleted_filter == "saved":
        where.append("(deleted_from_discord IS NULL OR deleted_from_discord = 0)")

    if query:
        like = f"%{str(query)[:150]}%"
        where.append("(title LIKE ? OR description LIKE ? OR discord_channel_name LIKE ? OR deleted_by_name LIKE ?)")
        params.extend([like, like, like, like])

    return "WHERE " + " AND ".join(where), params


def log_vault_recent(guild_id=0, limit=80, offset=0, log_type="all", query="", deleted_filter="all", channel_id="all"):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        nm_ensure_guild_column(cur, "dashboard_log_vault")
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_where(guild_id, log_type, query, deleted_filter, channel_id, include_legacy)
        cur.execute(f"""
            SELECT id, guild_id, log_type, title, description, discord_channel_id, discord_channel_name,
                   discord_message_id, deleted_from_discord, deleted_by_id, deleted_by_name, created_at, deleted_at
            FROM dashboard_log_vault
            {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, tuple(params + [int(limit), int(offset)]))
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql}", tuple(params))
        total = int(cur.fetchone()[0] or 0)
        conn.commit()
        conn.close()
        return rows, total
    except Exception as e:
        print(f"Strict Log Vault recent error: {e}")
        return [], 0


def log_vault_counts(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        nm_ensure_guild_column(cur, "dashboard_log_vault")
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_where(guild_id, "all", "", "all", "all", include_legacy)
        since = int(time.time()) - 86400

        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql}", tuple(params))
        total = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql} AND deleted_from_discord = 1", tuple(params))
        deleted = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(DISTINCT log_type) FROM dashboard_log_vault {where_sql}", tuple(params))
        types = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(*) FROM dashboard_log_vault {where_sql} AND created_at >= ?", tuple(params + [since]))
        today = int(cur.fetchone()[0] or 0)

        conn.commit()
        conn.close()
        return total, deleted, types, today
    except Exception as e:
        print(f"Strict Log Vault counts error: {e}")
        return 0, 0, 0, 0


def log_vault_types(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        nm_ensure_guild_column(cur, "dashboard_log_vault")
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_where(guild_id, "all", "", "all", "all", include_legacy)
        cur.execute(f"""
            SELECT log_type, COUNT(*)
            FROM dashboard_log_vault
            {where_sql}
            GROUP BY log_type
            ORDER BY COUNT(*) DESC
        """, tuple(params))
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return rows
    except Exception as e:
        print(f"Strict Log Vault types error: {e}")
        return []


def log_vault_channels(guild_id=0):
    try:
        conn = db_connect()
        cur = conn.cursor()
        log_vault_ensure_table(cur)
        nm_ensure_guild_column(cur, "dashboard_log_vault")
        include_legacy = bool(request.args.get("legacy") == "1") if request else False
        where_sql, params = nm_log_where(guild_id, "all", "", "all", "all", include_legacy)
        cur.execute(f"""
            SELECT discord_channel_id, discord_channel_name, COUNT(*)
            FROM dashboard_log_vault
            {where_sql}
            GROUP BY discord_channel_id, discord_channel_name
            ORDER BY COUNT(*) DESC
        """, tuple(params))
        rows = cur.fetchall()
        conn.commit()
        conn.close()
        return rows
    except Exception as e:
        print(f"Strict Log Vault channels error: {e}")
        return []


@app.route("/dashboard/log-vault", methods=["GET"])
def dashboard_log_vault_page():
    denied = dashboard_require_owner()
    if denied:
        return denied

    init_db()
    selected_guild_id = dashboard_get_active_guild_id()
    guild_banner = dashboard_guild_banner(selected_guild_id, "Log Vault Guild")
    log_type = request.args.get("type", "all").strip() or "all"
    deleted_filter = request.args.get("deleted", "all").strip() or "all"
    channel_filter = request.args.get("channel_id", "all").strip() or "all"
    query = request.args.get("q", "").strip()[:120]
    try:
        page = max(1, int(request.args.get("page", "1")))
    except Exception:
        page = 1
    try:
        limit = max(25, min(100, int(request.args.get("limit", "50"))))
    except Exception:
        limit = 50
    offset = (page - 1) * limit

    total, deleted_total, types_count, today = log_vault_counts(selected_guild_id)
    type_rows = log_vault_types(selected_guild_id)
    channel_rows = log_vault_channels(selected_guild_id)

    selected_channel_name = "All log rooms"
    for cid, cname, ctotal, cdeleted, clast in channel_rows:
        if str(cid) == str(channel_filter):
            selected_channel_name = f"#{cname}"
            break

    type_options = '<option value="all">All log types</option>'
    for t, count in type_rows:
        selected = "selected" if str(t) == log_type else ""
        icon, label = log_vault_type_meta(t)
        type_options += f'<option value="{dash_escape(t, 80)}" {selected}>{icon} {dash_escape(label, 80)} ({int(count)})</option>'

    deleted_options = "".join([
        f'<option value="all" {"selected" if deleted_filter == "all" else ""}>All logs</option>',
        f'<option value="active" {"selected" if deleted_filter == "active" else ""}>Still in Discord</option>',
        f'<option value="deleted" {"selected" if deleted_filter == "deleted" else ""}>Deleted from Discord</option>',
    ])

    rows, total_matches = log_vault_recent(
        guild_id=selected_guild_id,
        limit=limit,
        offset=offset,
        log_type=log_type,
        query=query,
        deleted_filter=deleted_filter,
        channel_id=channel_filter,
    )
    total_pages = max(1, (total_matches + limit - 1) // limit)

    def vault_url(**updates):
        params = {
            "guild_id": selected_guild_id,
            "q": query,
            "type": log_type,
            "deleted": deleted_filter,
            "channel_id": channel_filter,
            "limit": limit,
            "page": page,
        }
        params.update(updates)
        return "/dashboard/log-vault?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})

    all_active = "active" if channel_filter == "all" else ""
    channel_nav = f"""
      <a class="vault-room {all_active}" href="{vault_url(channel_id='all', page=1)}">
        <div class="room-icon">📁</div>
        <div class="room-main"><b>All log rooms</b><span>كل اللوقات</span></div>
        <div class="room-count">{total:,}</div>
      </a>
    """
    for cid, cname, ctotal, cdeleted, clast in channel_rows:
        active = "active" if str(cid) == str(channel_filter) else ""
        danger = " danger" if int(cdeleted or 0) else ""
        channel_nav += f"""
          <a class="vault-room {active}" href="{vault_url(channel_id=str(cid), page=1)}">
            <div class="room-icon">#</div>
            <div class="room-main"><b>#{dash_escape(cname, 55)}</b><span>Last: {cc_time(clast)}</span></div>
            <div class="room-count{danger}">{int(ctotal):,}</div>
          </a>
        """
    if len(channel_rows) == 0:
        channel_nav += "<div class='muted' style='padding:12px'>No log channels saved yet.</div>"

    cards = ""
    for row in rows:
        vault_id, row_guild_id, row_type, title, description, channel_id, channel_name, message_id, deleted_flag, deleted_by_id, deleted_by_name, created_at, deleted_at = row
        icon, type_label = log_vault_type_meta(row_type)
        title_text = dash_escape(title or "Untitled log", 180)
        summary = log_vault_render_log_html(description, selected_guild_id, preview=True)
        full_desc = log_vault_render_log_html(description, selected_guild_id, preview=False)
        status = "<span class='vault-status saved'>Saved</span>"
        deleted_line = ""
        if int(deleted_flag or 0) == 1:
            deleter = dashboard_member_chip_in_guild(deleted_by_id, selected_guild_id) if deleted_by_id else dash_escape(deleted_by_name or "Unknown", 80)
            deleted_line = f"<div class='vault-deleted'>Deleted by {deleter} • {cc_time(deleted_at)}</div>"
            status = "<span class='vault-status deleted'>Deleted in Discord</span>"
        channel_label = f"#{dash_escape(channel_name, 80)}" if channel_name else "Unknown channel"
        msg_link = ""
        if selected_guild_id and channel_id and message_id:
            msg_link = f"<a class='btn sm' target='_blank' href='https://discord.com/channels/{int(selected_guild_id)}/{int(channel_id)}/{int(message_id)}'>Open Discord</a>"
        source_tag = ""
        if row_guild_id and selected_guild_id and int(row_guild_id) != int(selected_guild_id):
            source_tag = f"<span class='pill warn'>Legacy / Global</span>"
        cards += f"""
        <div class="discord-log-row">
          <div class="log-avatar">{icon}</div>
          <div class="log-body">
            <div class="log-head">
              <b>{dash_escape(type_label, 80)}</b>
              <span class="pill">{channel_label}</span>
              {status}
              {source_tag}
              <span class="log-time">{cc_time(created_at)}</span>
            </div>
            <div class="log-title">{title_text}</div>
            <div class="log-summary">{summary}</div>
            {deleted_line}
            <details class="vault-details">
              <summary>Show full log</summary>
              <div class="full-log-content">{full_desc}</div>
            </details>
            <div class="log-actions">
              <span class="muted small">Vault ID #{int(vault_id)} • Msg <code>{int(message_id or 0)}</code></span>
              {msg_link}
            </div>
          </div>
        </div>
        """
    if not cards:
        cards = "<div class='empty-vault'><h3>No logs in this room</h3><p class='muted'>اختر روم ثاني من اليسار أو غير الفلاتر.</p></div>"

    prev_link = vault_url(page=max(1, page - 1))
    next_link = vault_url(page=min(total_pages, page + 1))
    pagination = f"""
    <div class="vault-pagination">
      <a class="btn {'disabled' if page <= 1 else ''}" href="{prev_link}">← Previous</a>
      <span class="pill">Page {page:,} / {total_pages:,}</span>
      <span class="muted">Showing {len(rows):,} of {total_matches:,}</span>
      <a class="btn {'disabled' if page >= total_pages else ''}" href="{next_link}">Next →</a>
    </div>
    """

    body = f"""
    {dashboard_toast_html()}
    {guild_banner}
    <style>
      .vault-shell {{ display:grid; grid-template-columns: 320px 1fr; gap:16px; align-items:start; }}
      .vault-rooms {{ position:sticky; top:12px; max-height:calc(100vh - 120px); overflow:auto; border:1px solid var(--line); border-radius:24px; background:rgba(2,6,23,.55); padding:12px; }}
      .vault-rooms h3 {{ margin:6px 8px 10px; }}
      .vault-room {{ display:grid; grid-template-columns:38px 1fr auto; gap:10px; align-items:center; padding:11px; border-radius:16px; color:var(--text); text-decoration:none; border:1px solid transparent; margin-bottom:6px; }}
      .vault-room:hover, .vault-room.active {{ background:rgba(124,58,237,.16); border-color:rgba(124,58,237,.36); }}
      .room-icon {{ width:36px; height:36px; border-radius:14px; display:grid; place-items:center; background:rgba(15,23,42,.9); color:#a78bfa; font-weight:950; }}
      .room-main {{ min-width:0; }}
      .room-main b {{ display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
      .room-main span {{ display:block; color:var(--muted); font-size:12px; margin-top:2px; }}
      .room-count {{ border-radius:999px; padding:5px 8px; background:rgba(59,130,246,.13); color:#93c5fd; font-weight:900; font-size:12px; }}
      .room-count.danger {{ background:rgba(239,68,68,.13); color:#fca5a5; }}
      .vault-panel {{ min-width:0; }}
      .vault-toolbar {{ border:1px solid var(--line); border-radius:24px; background:rgba(15,23,42,.55); padding:14px; margin-bottom:12px; }}
      .vault-titlebar {{ display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }}
      .discord-log-list {{ border:1px solid var(--line); border-radius:24px; overflow:hidden; background:rgba(2,6,23,.40); }}
      .discord-log-row {{ display:flex; gap:12px; padding:14px 16px; border-bottom:1px solid rgba(148,163,184,.12); }}
      .discord-log-row:last-child {{ border-bottom:0; }}
      .discord-log-row:hover {{ background:rgba(15,23,42,.50); }}
      .log-avatar {{ width:42px; height:42px; border-radius:999px; flex:0 0 auto; display:grid; place-items:center; background:rgba(124,58,237,.16); border:1px solid rgba(124,58,237,.28); font-size:21px; }}
      .log-body {{ min-width:0; flex:1; }}
      .log-head {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
      .log-head b {{ color:#ddd6fe; }}
      .log-time {{ color:var(--muted); font-size:12px; margin-inline-start:auto; }}
      .log-title {{ font-weight:950; font-size:16px; margin-top:6px; overflow-wrap:anywhere; }}
      .log-summary {{ color:var(--muted); line-height:1.55; margin-top:8px; overflow-wrap:anywhere; max-width:100%; }}
      .log-clean-text {{ white-space:normal; word-break:break-word; }}
      .log-attachments {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }}
      .log-attachment {{ text-decoration:none; border:1px solid rgba(148,163,184,.16); background:rgba(15,23,42,.72); border-radius:14px; overflow:hidden; color:#dbeafe; font-size:12px; font-weight:900; }}
      .log-attachment.media {{ width:148px; display:block; }}
      .log-attachment.media img {{ display:block; width:148px; height:96px; object-fit:cover; background:#020617; }}
      .log-attachment.media span {{ display:block; padding:7px 9px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
      .log-attachment.file, .log-attachment.more {{ padding:10px 12px; display:inline-flex; align-items:center; }}
      .user-chip {{ display:inline-flex; align-items:center; gap:4px; border:1px solid rgba(59,130,246,.28); background:rgba(59,130,246,.12); color:#bfdbfe; border-radius:999px; padding:2px 7px; font-weight:900; white-space:normal; }}
      .log-actions {{ display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-top:10px; }}

      /* NM clean log rendering override */
      .log-clean-text { line-height:1.75; overflow-wrap:anywhere; word-break:break-word; }
      .vault-card .log-clean-text img,
      .vault-card img:not(.memberavatar):not(.miniavatar):not(.servericon) {
        display:none !important;
        width:0 !important;
        height:0 !important;
        max-width:0 !important;
        max-height:0 !important;
      }
      .log-attachments.compact { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }
      .log-attachment.compact {
        display:inline-flex !important;
        align-items:center;
        gap:7px;
        max-width:220px;
        padding:8px 11px;
        border-radius:999px;
        border:1px solid rgba(96,165,250,.22);
        background:rgba(15,23,42,.75);
        color:#bfdbfe;
        text-decoration:none;
        font-size:12px;
        font-weight:900;
        overflow:hidden;
      }
      .log-attachment.compact span:last-child { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .log-attachment.compact:hover { border-color:rgba(139,92,246,.55); background:rgba(88,101,242,.18); }
      .attachment-icon { flex:0 0 auto; }
      .vault-details .log-attachments .log-attachment.compact { max-width:260px; }

      .vault-status {{ border-radius:999px; padding:5px 9px; font-size:12px; font-weight:900; }}
      .vault-status.saved {{ color:#86efac; background:rgba(34,197,94,.12); border:1px solid rgba(34,197,94,.25); }}
      .vault-status.deleted {{ color:#fca5a5; background:rgba(239,68,68,.13); border:1px solid rgba(239,68,68,.25); }}
      .vault-deleted {{ margin-top:8px; color:#fca5a5; font-size:13px; font-weight:800; }}
      .vault-details {{ margin-top:9px; }}
      .vault-details summary {{ cursor:pointer; color:#93c5fd; font-weight:900; }}
      .full-log-content {{ background:rgba(2,6,23,.64); border:1px solid var(--line); border-radius:16px; padding:12px; max-height:360px; overflow:auto; margin-top:8px; }}
      .vault-pagination {{ display:flex; align-items:center; justify-content:center; gap:10px; flex-wrap:wrap; margin:14px 0; }}
      .btn.sm {{ padding:7px 10px; font-size:12px; }}
      .btn.disabled {{ pointer-events:none; opacity:.45; }}
      .empty-vault {{ text-align:center; padding:40px 20px; }}
      @media (max-width: 980px) {{ .vault-shell {{ grid-template-columns:1fr; }} .vault-rooms {{ position:relative; max-height:360px; }} .log-time {{ margin-inline-start:0; }} }}
    </style>

    <div class="card">
      <div class="big">🗄️ Log Vault</div>
      <p class="muted">صار مثل Discord: اختر روم اللوق من اليسار، وتشوف لوقات هذا الروم فقط. أرقام الأعضاء تتحول تلقائيًا إلى النك نيم واليوزر داخل السيرفر.</p>
      <div style="height:10px"></div>
      <span class="pill ok">Owner Only</span>
      <span class="pill">Room-based view</span>
      <span class="pill">Per-server vault</span><span class="pill ok">Strict guild mode</span><span class="pill ok">Legacy hidden</span>
      <span class="pill">Saved: {total:,}</span>
      <span class="pill danger">Deleted: {deleted_total:,}</span>
    </div>

    <div style="height:14px"></div>
    <div class="vault-shell">
      <aside class="vault-rooms">
        <h3>Log Rooms</h3>
        {channel_nav}
      </aside>

      <main class="vault-panel">
        <div class="vault-toolbar">
          <div class="vault-titlebar">
            <div>
              <h2 style="margin:0">{dash_escape(selected_channel_name, 90)}</h2>
              <p class="muted" style="margin:4px 0 0">{total_matches:,} logs match your filters</p>
            </div>
            <a class="btn" href="/dashboard/log-vault?guild_id={int(selected_guild_id or 0)}">All rooms</a><a class="btn" href="/dashboard/log-vault?guild_id={int(selected_guild_id or 0)}&legacy=1">Show legacy</a><a class="btn" href="/dashboard/log-vault?guild_id={int(selected_guild_id or 0)}&legacy=1">Show legacy</a>
          </div>
          <form method="get" class="formgrid">
            <input type="hidden" name="guild_id" value="{int(selected_guild_id or 0)}">
            <input type="hidden" name="channel_id" value="{dash_escape(channel_filter, 80)}">
            <div><label>Search</label><input name="q" value="{dash_escape(query, 120)}" placeholder="title, text, deleter, type"></div>
            <div><label>Type</label><select name="type">{type_options}</select></div>
            <div><label>Status</label><select name="deleted">{deleted_options}</select></div>
            <div><label>Limit</label><input name="limit" value="{limit}"></div>
            <div style="display:flex;align-items:end;gap:8px"><button class="btn primary" type="submit">Apply</button><a class="btn" href="{vault_url(channel_id=channel_filter, q='', type='all', deleted='all', page=1)}">Reset</a></div>
          </form>
        </div>

        {pagination}
        <div class="discord-log-list">{cards}</div>
        {pagination}
      </main>
    </div>
    """
    return render_dashboard_page("Log Vault", body)


@app.route("/dashboard/command-center", methods=["GET"])
def dashboard_command_center_page():
    denied = dashboard_require_admin()
    if denied:
        return denied

    init_db()
    selected_guild_id = dashboard_get_active_guild_id()
    guild_banner = dashboard_guild_banner(selected_guild_id, "Command Center Guild")

    since_24h = cc_since_hours(24)
    since_1h = cc_since_hours(1)
    guild_data = cc_guild_snapshot()

    bot_ping = "Offline"
    if bot and getattr(bot, "latency", None) is not None:
        try:
            bot_ping = f"{round(bot.latency * 1000)} ms"
        except:
            bot_ping = "Unknown"

    db_ok = "OK" if db_file_valid() else "CHECK"
    memory_status = local_memory_status()
    memory_bad = [name for name, info in memory_status.items() if not info.get("valid")]
    memory_text = "All memory files OK" if not memory_bad else "Check: " + ", ".join(memory_bad)

    total_money = nm_db_sum_column("economy", "balance")
    economy_users = nm_db_table_count("economy")
    level_users = nm_db_table_count("levels")
    active_warnings, cleared_warnings, active_warning_users, total_warning_users = get_warning_summary_counts()

    messages_24h = cc_count_clean_messages(since_24h)
    commands_24h = cc_count_events("command", since_24h)
    violations_24h = cc_count_events("violation", since_24h)
    joins_24h = cc_count_events("member_join", since_24h)
    leaves_24h = cc_count_events("member_leave", since_24h)
    money_created_24h = cc_sum_amount("money", since_24h, positive_only=True)
    money_removed_24h = abs(cc_sum_amount("money", since_24h, negative_only=True))

    messages_1h = cc_count_clean_messages(since_1h)
    commands_1h = cc_count_events("command", since_1h)
    violations_1h = cc_count_events("violation", since_1h)

    top_channels_html = "".join([
        f"<tr><td>#{dash_escape(name, 80)}</td><td><b>{count}</b> messages</td></tr>"
        for name, count in cc_top_channels(since_24h, 8)
    ]) or "<tr><td colspan='2'>No channel activity yet.</td></tr>"

    top_users_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<span class='muted small'>{dash_escape(name, 80)}</span></td><td><b>{count}</b> messages</td></tr>"
        for uid, name, count in cc_top_users_by_event("message", since_24h, 8)
    ]) or "<tr><td colspan='2'>No user activity yet.</td></tr>"

    top_commands_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<span class='muted small'>{dash_escape(name, 80)}</span></td><td><b>{count}</b> commands</td></tr>"
        for uid, name, count in cc_top_users_by_event("command", since_24h, 8)
    ]) or "<tr><td colspan='2'>No commands yet.</td></tr>"

    money_gain_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<span class='muted small'>{dash_escape(name, 80)}</span></td><td><b style='color:#22c55e'>+{int(total):,}</b></td></tr>"
        for uid, name, total in cc_money_movers(since_24h, True, 8)
    ]) or "<tr><td colspan='2'>No money gains tracked yet.</td></tr>"

    money_loss_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}<span class='muted small'>{dash_escape(name, 80)}</span></td><td><b style='color:#ef4444'>{int(total):,}</b></td></tr>"
        for uid, name, total in cc_money_movers(since_24h, False, 8)
    ]) or "<tr><td colspan='2'>No money losses tracked yet.</td></tr>"

    watchlist_html = "".join([
        f"<tr><td>{dashboard_member_name(uid)}</td><td><span class='pill bad'>{count} active warnings</span></td></tr>"
        for uid, count in cc_active_warning_rows(10)
    ]) or "<tr><td colspan='2'>No active warning watchlist.</td></tr>"

    warning_reasons_html = "".join([
        f"<tr><td>{dash_escape(reason, 120)}</td><td><b>{count}</b></td></tr>"
        for reason, count in cc_warning_reason_rows(8)
    ]) or "<tr><td colspan='2'>No warnings yet.</td></tr>"

    recent_rows = cc_recent_events(80)
    recent_html = "".join([
        f"""
        <tr>
          <td><code>{cc_time(created_at)}</code></td>
          <td><span class='pill'>{dash_escape(event_type, 60)}</span></td>
          <td>{dashboard_member_name(user_id) if user_id else "<span class='muted'>System</span>"}<br><span class='muted small'>{dash_escape(user_name, 90)}</span></td>
          <td>{dash_escape(channel_name, 90)}</td>
          <td>{int(amount):,}</td>
          <td>{dash_escape(details, 220)}</td>
        </tr>
        """
        for event_type, user_id, user_name, channel_name, amount, details, created_at in recent_rows
    ]) or "<tr><td colspan='6'>No live events tracked yet.</td></tr>"

    body = f"""
    {dashboard_toast_html()}

    <style>
      .cc-tabs {{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0;}}
      .cc-tabs a {{text-decoration:none;}}
      .cc-stat {{font-size:28px;font-weight:1000;margin-top:8px;}}
      .cc-sub {{color:var(--muted);font-size:13px;margin-top:4px;}}
      .cc-ok {{border:1px solid rgba(34,197,94,.35);}}
      .cc-warn {{border:1px solid rgba(245,158,11,.35);}}
      .cc-danger {{border:1px solid rgba(239,68,68,.35);}}
      .table td {{vertical-align:top;}}
    </style>

    <div class="hero">
      <div class="card">
        <div class="big">🧠 Server Command Center</div>
        <p class="muted">مركز مراقبة مباشر للسيرفر: نشاط، أوامر، اقتصاد، تحذيرات، لوقات، وصحة النظام. بدون Server Risk Score.</p>
        <div style="height:10px"></div>
        <span class="pill ok">Live Monitoring</span>
        <span class="pill">24h Window</span>
      </div>
      <div class="card {'cc-ok' if guild_data['guild_ok'] else 'cc-danger'}">
        <h3>🤖 Bot Status</h3>
        <div class="cc-stat">{'🟢 Online' if guild_data['guild_ok'] else '🔴 Offline'}</div>
        <div class="cc-sub">Ping: {bot_ping} • Uptime: {cc_bot_uptime_text()}</div>
      </div>
    </div>

    <div class="cc-tabs">
      <a class="btn" href="#overview">Overview</a>
      <a class="btn" href="#live">Live Logs</a>
      <a class="btn" href="#economy">Economy Monitor</a>
      <a class="btn" href="#members">Member Watchlist</a>
      <a class="btn" href="#moderation">Moderation</a>
      <a class="btn" href="#system">System Health</a>
    </div>

    <div id="overview" class="grid">
      <div class="card"><h3>👥 Members</h3><div class="cc-stat">{guild_data['humans']}</div><div class="cc-sub">Online: {guild_data['online']} • Voice: {guild_data['voice']} • Bots: {guild_data['bots']}</div></div>
      <div class="card"><h3>💬 Messages 24h</h3><div class="cc-stat">{messages_24h:,}</div><div class="cc-sub">Last hour: {messages_1h:,}</div></div>
      <div class="card"><h3>⌨️ Commands 24h</h3><div class="cc-stat">{commands_24h:,}</div><div class="cc-sub">Last hour: {commands_1h:,}</div></div>
      <div class="card"><h3>⚠️ Violations 24h</h3><div class="cc-stat">{violations_24h:,}</div><div class="cc-sub">Last hour: {violations_1h:,}</div></div>
      <div class="card"><h3>📥 Joins / Leaves</h3><div class="cc-stat">+{joins_24h} / -{leaves_24h}</div><div class="cc-sub">Last 24 hours</div></div>
      <div class="card"><h3>🪙 Total Economy</h3><div class="cc-stat">{total_money:,}</div><div class="cc-sub">{economy_users} economy users • {level_users} level users</div></div>
    </div>

    <div style="height:16px"></div>

    <div class="grid2">
      <div class="card"><h3>🔥 Top Active Channels</h3><table class="table"><tr><th>Channel</th><th>Activity</th></tr>{top_channels_html}</table></div>
      <div class="card"><h3>👑 Top Active Members</h3><table class="table"><tr><th>Member</th><th>Messages</th></tr>{top_users_html}</table></div>
    </div>

    <div id="economy" style="height:16px"></div>
    <div class="grid">
      <div class="card"><h3>📈 Money Created 24h</h3><div class="cc-stat" style="color:#22c55e">+{money_created_24h:,}</div><div class="cc-sub">{nm_coin_name()}</div></div>
      <div class="card"><h3>📉 Money Removed 24h</h3><div class="cc-stat" style="color:#ef4444">-{money_removed_24h:,}</div><div class="cc-sub">{nm_coin_name()}</div></div>
      <div class="card"><h3>🏦 Database Economy</h3><div class="cc-stat">{total_money:,}</div><div class="cc-sub">Total server money</div></div>
    </div>

    <div style="height:16px"></div>

    <div class="grid2">
      <div class="card"><h3>💸 Biggest Money Gains 24h</h3><table class="table"><tr><th>Member</th><th>Gained</th></tr>{money_gain_html}</table></div>
      <div class="card"><h3>🧾 Biggest Money Losses 24h</h3><table class="table"><tr><th>Member</th><th>Lost</th></tr>{money_loss_html}</table></div>
    </div>

    <div id="members" style="height:16px"></div>
    <div class="grid2">
      <div class="card">
        <h3>👁️ Member Watchlist</h3>
        <p class="muted">يعرض أكثر أعضاء عليهم تحذيرات نشطة. هذا مراقبة إدارية مب عقوبة تلقائية.</p>
        <table class="table"><tr><th>Member</th><th>Status</th></tr>{watchlist_html}</table>
      </div>
      <div class="card"><h3>⌨️ Top Command Users 24h</h3><table class="table"><tr><th>Member</th><th>Commands</th></tr>{top_commands_html}</table></div>
    </div>

    <div id="moderation" style="height:16px"></div>
    <div class="grid">
      <div class="card"><h3>⚠️ Active Warnings</h3><div class="cc-stat">{active_warnings:,}</div><div class="cc-sub">{active_warning_users} users affected</div></div>
      <div class="card"><h3>✅ Cleared Warnings</h3><div class="cc-stat">{cleared_warnings:,}</div><div class="cc-sub">Total cleared history</div></div>
      <div class="card"><h3>👥 Warning Users</h3><div class="cc-stat">{total_warning_users:,}</div><div class="cc-sub">All-time unique users</div></div>
    </div>

    <div style="height:16px"></div>
    <div class="card"><h3>📌 Top Warning Reasons</h3><table class="table"><tr><th>Reason</th><th>Total</th></tr>{warning_reasons_html}</table></div>

    <div id="system" style="height:16px"></div>
    <div class="grid">
      <div class="card {'cc-ok' if db_ok == 'OK' else 'cc-danger'}"><h3>🗄️ Database</h3><div class="cc-stat">{db_ok}</div><div class="cc-sub">Size: {cc_database_size()}</div></div>
      <div class="card {'cc-ok' if not memory_bad else 'cc-warn'}"><h3>💾 Memory Backup Files</h3><div class="cc-stat">{'OK' if not memory_bad else 'CHECK'}</div><div class="cc-sub">{dash_escape(memory_text, 220)}</div></div>
      <div class="card"><h3>📡 Channels</h3><div class="cc-stat">{guild_data['text_channels']} / {guild_data['voice_channels']}</div><div class="cc-sub">Text / Voice channels</div></div>
    </div>

    <div id="live" style="height:16px"></div>
    <div class="card">
      <h3>📡 Live Logs Feed</h3>
      <p class="muted">آخر الأحداث المهمة من الرسائل، الأوامر، الاقتصاد، المخالفات، الدخول والخروج.</p>
      <table class="table">
        <tr><th>Time</th><th>Type</th><th>User</th><th>Channel</th><th>Amount</th><th>Details</th></tr>
        {recent_html}
      </table>
    </div>
    """

    return render_dashboard_page("Command Center", body)

@app.route("/dashboard/protection", methods=["GET"])
def dashboard_protection_page():
    denied = dashboard_require_admin()
    if denied:
        return denied

    selected_guild_id = dashboard_get_active_guild_id()
    if not dashboard_can_manage_guild(selected_guild_id):
        return dashboard_access_denied_html("ما عندك صلاحية إدارة حماية هذا السيرفر.")

    settings = get_guild_protection_settings(selected_guild_id)
    guild = bot.get_guild(int(selected_guild_id)) if bot else None

    def checked(key):
        return "checked" if bool(settings.get(key)) else ""

    def option(value, label):
        selected = "selected" if settings.get("punishment") == value else ""
        return f"<option value='{value}' {selected}>{label}</option>"

    channels = []
    roles = []
    if guild:
        channels = sorted(guild.text_channels, key=lambda c: (c.category.name if c.category else "", c.position))
        roles = [r for r in sorted(guild.roles, key=lambda r: r.position, reverse=True) if r.name != "@everyone"]

    ignored_channels = {int(x) for x in settings.get("ignored_channels", [])}
    ignored_roles = {int(x) for x in settings.get("ignored_roles", [])}
    channel_options = "".join([
        f"<label class='mini-check'><input type='checkbox' name='ignored_channels' value='{c.id}' {'checked' if c.id in ignored_channels else ''}> #{dash_escape(c.name, 80)}</label>"
        for c in channels[:160]
    ]) or "<p class='muted'>ما قدرت أقرأ رومات السيرفر. تأكد البوت داخل السيرفر وعنده صلاحيات.</p>"
    role_options = "".join([
        f"<label class='mini-check'><input type='checkbox' name='ignored_roles' value='{r.id}' {'checked' if r.id in ignored_roles else ''}> {dash_escape(r.name, 80)}</label>"
        for r in roles[:120]
    ]) or "<p class='muted'>ما قدرت أقرأ رتب السيرفر.</p>"

    whitelist_text = "\n".join(settings.get("link_whitelist", []))

    modules = [
        ("protection_enabled", "Master Protection", "القفل الرئيسي لكل أنظمة الحماية."),
        ("bad_words", "Bad Words Filter", "فلتر الكلمات الممنوعة والسب بدون ظلم الكلمات الطبيعية."),
        ("links", "Anti Links", "منع الروابط العامة غير المسموحة."),
        ("invites", "Anti Discord Invites", "منع دعوات الديسكورد غير المصرح بها."),
        ("spam", "Anti Spam", "يمسك الرسائل المتكررة خلال مدة قصيرة."),
        ("mass_mentions", "Mass Mention Guard", "يمسك المنشن الجماعي و@everyone."),
        ("anti_bot_join", "Anti Bot Join", "يراقب دخول البوتات الجديدة للسيرفر."),
        ("anti_raid", "Anti Raid", "يراقب دخول عدد كبير من الأعضاء خلال وقت قصير."),
        ("anti_channel_create", "Anti Channel Create", "يراقب إنشاء الرومات المفاجئ."),
        ("anti_channel_delete", "Anti Channel Delete", "يراقب حذف الرومات ويحفظ اللوق."),
        ("anti_channel_rename", "Anti Channel Rename", "يراقب تغيير أسماء الرومات."),
        ("anti_channel_permission_update", "Anti Channel Permission Update", "يراقب تعديل صلاحيات الرومات."),
        ("anti_role_create", "Anti Role Create", "يراقب إنشاء الرتب."),
        ("anti_role_delete", "Anti Role Delete", "يراقب حذف الرتب."),
        ("anti_role_permission_update", "Anti Role Permission Update", "يراقب تعديل صلاحيات الرتب الخطيرة."),
        ("anti_ban_abuse", "Anti Ban Abuse", "يراقب الباندات المشبوهة من الأدمنز."),
        ("anti_kick_abuse", "Anti Kick Abuse", "يراقب الطرد المشبوه."),
        ("anti_webhook_update", "Anti Webhook Abuse", "يراقب إنشاء/تعديل الويب هوك."),
        ("anti_emoji_delete", "Anti Emoji Delete", "يراقب حذف الإيموجيات."),
        ("anti_guild_update", "Anti Server Update", "يراقب تغيير اسم/صورة السيرفر."),
        ("anti_invite_delete", "Anti Invite Delete", "يراقب حذف الدعوات."),
    ]

    module_cards = "".join([
        f"""
        <label class='protect-switch'>
          <input type='checkbox' name='{key}' {checked(key)}>
          <div><b>{title}</b><span>{desc}</span></div>
          <em>{'ON' if settings.get(key) else 'OFF'}</em>
        </label>
        """
        for key, title, desc in modules
    ])

    guild_banner = dashboard_guild_banner(selected_guild_id, "Protection Guild")
    body = f"""
    {dashboard_toast_html()}
    {guild_banner}
    <style>
      .protect-hero{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(260px,.8fr);gap:16px}}
      .protect-switch{{display:grid;grid-template-columns:54px minmax(0,1fr) 48px;align-items:center;gap:12px;padding:14px;border:1px solid var(--line);border-radius:18px;background:rgba(255,255,255,.045);margin-bottom:10px}}
      .protect-switch:hover{{border-color:rgba(139,92,246,.45);background:rgba(255,255,255,.07)}}
      .protect-switch input{{width:22px;height:22px;accent-color:var(--purple)}}
      .protect-switch b{{display:block;font-size:14px}}
      .protect-switch span{{display:block;color:var(--muted);font-size:12px;margin-top:4px;line-height:1.35}}
      .protect-switch em{{font-style:normal;font-size:11px;font-weight:1000;color:#dbeafe;background:rgba(88,101,242,.2);border:1px solid rgba(88,101,242,.28);padding:6px 8px;border-radius:999px;text-align:center}}
      .mini-check{{display:block;padding:10px 11px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.035);margin:6px 0;color:#dbeafe;font-weight:800}}
      .mini-check input{{margin-right:8px;accent-color:var(--purple)}}
      .scrollbox{{max-height:330px;overflow:auto;padding-right:6px}}
      textarea{{min-height:120px;resize:vertical}}
      @media(max-width:950px){{.protect-hero{{grid-template-columns:1fr}}}}
    </style>

    <div class='protect-hero'>
      <div class='card'>
        <div class='big'>🛡️ NM Protection Core</div>
        <p class='muted'>مركز حماية شامل للسيرفر المختار. كل إعداد هنا خاص بهذا السيرفر فقط.</p>
        <div style='height:10px'></div>
        <span class='pill {'ok' if settings.get('protection_enabled') else 'danger'}'>Master: {'ON' if settings.get('protection_enabled') else 'OFF'}</span>
        <span class='pill'>Spam: {settings.get('spam_limit')}/{settings.get('spam_seconds')}s</span>
        <span class='pill'>Raid: {settings.get('raid_join_limit')}/{settings.get('raid_seconds')}s</span>
      </div>
      <div class='card'>
        <h3>⚡ Action Mode</h3>
        <p class='muted'>اختر كيف يتصرف البوت مع التخريب الإداري مثل حذف الرومات أو تعديل صلاحيات الرتب.</p>
        <p><span class='pill gold'>Log Only للتجربة</span> <span class='pill danger'>Ban/Kick بحذر</span></p>
      </div>
    </div>

    <div style='height:16px'></div>
    <form method='post' data-live='true' data-autosave='true' action='/dashboard/protection?guild_id={int(selected_guild_id)}'>
      <input type='hidden' name='guild_id' value='{int(selected_guild_id)}'>
      <div class='grid2'>
        <div class='card'><h3>🔌 Protection Modules</h3>{module_cards}</div>
        <div class='card'>
          <h3>⚙️ Thresholds & Punishment</h3>
          <label>Default Punishment for Anti-Abuse</label>
          <select name='punishment'>
            {option('log_only', 'Log only / تسجيل فقط')}
            {option('warn', 'Warn executor')}
            {option('timeout_10m', 'Timeout 10 minutes')}
            {option('timeout_1h', 'Timeout 1 hour')}
            {option('quarantine', 'Quarantine role')}
            {option('kick', 'Kick executor')}
            {option('ban', 'Ban executor')}
          </select>
          <label>Spam Limit</label><input name='spam_limit' value='{int(settings.get('spam_limit'))}'>
          <label>Spam Window Seconds</label><input name='spam_seconds' value='{int(settings.get('spam_seconds'))}'>
          <label>Mass Mention Limit</label><input name='mass_mention_limit' value='{int(settings.get('mass_mention_limit'))}'>
          <label>Raid Join Limit</label><input name='raid_join_limit' value='{int(settings.get('raid_join_limit'))}'>
          <label>Raid Window Seconds</label><input name='raid_seconds' value='{int(settings.get('raid_seconds'))}'>
          <label>Quarantine Role Name</label><input name='quarantine_role_name' value='{dash_escape(settings.get('quarantine_role_name'), 80)}'>
          <label class='mini-check'><input type='checkbox' name='delete_messages' {checked('delete_messages')}> Delete violating messages</label>
          <label class='mini-check'><input type='checkbox' name='timeouts' {checked('timeouts')}> Auto timeouts for warnings</label>
          <label class='mini-check'><input type='checkbox' name='bypass_admins' {checked('bypass_admins')}> Bypass administrators</label>
          <label class='mini-check'><input type='checkbox' name='log_only' {checked('log_only')}> Log Only Mode</label>
        </div>
      </div>

      <div style='height:16px'></div>
      <div class='grid2'>
        <div class='card'><h3>✅ Link Whitelist</h3><p class='muted'>دومين أو رابط في كل سطر.</p><textarea name='link_whitelist'>{dash_escape(whitelist_text, 3000)}</textarea></div>
        <div class='card'><h3>🚪 Ignored Channels</h3><p class='muted'>اختر الرومات اللي ما تشتغل فيها الحماية.</p><div class='scrollbox'>{channel_options}</div></div>
      </div>

      <div style='height:16px'></div>
      <div class='card'><h3>🎭 Ignored Roles</h3><p class='muted'>أي عضو معه رتبة من هنا ما تنطبق عليه الحماية.</p><div class='scrollbox'>{role_options}</div></div>

      <div style='height:16px'></div>
      <button class='btn primary' type='submit' data-live-submit>💾 Save Protection Settings</button>
      <span class='pill ok' data-live-state>Live Save Ready</span>
      <a class='btn' href='/dashboard/guild/{int(selected_guild_id)}/command-center'>🧠 Command Center</a>
      <a class='btn' href='/dashboard/guild/{int(selected_guild_id)}/log-vault'>📦 Log Vault</a>
    </form>
    """
    return render_dashboard_page("Protection", body)


@app.route("/dashboard/protection", methods=["POST"])
def dashboard_protection_action():
    denied = dashboard_require_admin()
    if denied:
        return denied
    guild_id = int(request.form.get("guild_id") or request.args.get("guild_id") or dashboard_get_active_guild_id())
    if not dashboard_can_manage_guild(guild_id):
        return dashboard_access_denied_html("ما عندك صلاحية تعديل حماية هذا السيرفر.")

    keys = [
        "protection_enabled", "bad_words", "links", "invites", "spam", "mass_mentions",
        "anti_bot_join", "anti_raid", "anti_channel_create", "anti_channel_delete", "anti_channel_rename",
        "anti_channel_permission_update", "anti_role_create", "anti_role_delete", "anti_role_permission_update",
        "anti_ban_abuse", "anti_kick_abuse", "anti_webhook_update", "anti_emoji_delete", "anti_guild_update", "anti_invite_delete",
        "delete_messages", "timeouts", "bypass_admins", "log_only"
    ]
    settings = get_guild_protection_settings(guild_id)
    for key in keys:
        settings[key] = key in request.form
    settings["punishment"] = request.form.get("punishment", settings.get("punishment", "timeout_10m"))
    settings["spam_limit"] = parse_int_field(request.form.get("spam_limit"), settings.get("spam_limit", 8), 2)
    settings["spam_seconds"] = parse_int_field(request.form.get("spam_seconds"), settings.get("spam_seconds", 5), 1)
    settings["mass_mention_limit"] = parse_int_field(request.form.get("mass_mention_limit"), settings.get("mass_mention_limit", 8), 1)
    settings["raid_join_limit"] = parse_int_field(request.form.get("raid_join_limit"), settings.get("raid_join_limit", 8), 2)
    settings["raid_seconds"] = parse_int_field(request.form.get("raid_seconds"), settings.get("raid_seconds", 20), 5)
    settings["quarantine_role_name"] = request.form.get("quarantine_role_name", "NM Quarantine")[:80]
    settings["link_whitelist"] = parse_text_list(request.form.get("link_whitelist", ""))
    settings["ignored_channels"] = parse_dashboard_int_list(request.form.getlist("ignored_channels"))
    settings["ignored_roles"] = parse_dashboard_int_list(request.form.getlist("ignored_roles"))
    save_guild_protection_settings(guild_id, settings)
    dashboard_log_action("Protection updated", f"Protection settings changed for guild {guild_id}", session.get("discord_user"))

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.accept_mimetypes.best == "application/json":
        return jsonify({
            "ok": True,
            "message": "Protection settings saved live.",
            "guild_id": guild_id,
            "protection_enabled": bool(settings.get("protection_enabled")),
            "log_only": bool(settings.get("log_only")),
            "punishment": settings.get("punishment", "timeout_10m"),
        })

    return redirect(f"/dashboard/protection?guild_id={guild_id}&msg=" + urllib.parse.quote("Protection settings saved."))


@app.route("/dashboard/api/live-status", methods=["GET"])
def dashboard_api_live_status():
    denied = dashboard_require_admin()
    if denied:
        return jsonify({"ok": False, "error": "Access denied"}), 403
    try:
        guild_id = int(request.args.get("guild_id") or dashboard_get_active_guild_id() or GUILD_ID)
    except:
        guild_id = GUILD_ID
    guild = bot.get_guild(guild_id) if bot else None
    protection = get_guild_protection_settings(guild_id)
    return jsonify({
        "ok": True,
        "guild_id": guild_id,
        "bot_online": bool(bot and bot.user),
        "ping_ms": round(bot.latency * 1000) if bot and getattr(bot, "latency", None) is not None else None,
        "members": len(guild.members) if guild else 0,
        "channels": len(guild.channels) if guild else 0,
        "protection_enabled": bool(protection.get("protection_enabled")),
        "log_only": bool(protection.get("log_only")),
        "punishment": protection.get("punishment", "timeout_10m"),
        "updated_at": int(time.time()),
    })


@app.route("/dashboard/settings", methods=["GET"])
def dashboard_settings_page():
    denied = dashboard_require_owner()
    if denied:
        return denied

    def checked(v):
        return "checked" if bool(v) else ""

    body = f"""
    {dashboard_toast_html()}
    <div class="card">
      <h3>⚙️ Customization Center</h3>
      <p class="muted">كل شيء هنا قابل للتعديل من الداشبورد. الرومات، الرتب، الاقتصاد، القمار، المتجر، الفعاليات، والباك أب.</p>
      <form method="post" action="/dashboard/settings">
        <div class="grid">
          <div class="card"><h3>🏷️ Brand</h3>
            <label>Bot Brand</label><input name="BOT_BRAND" value="{clean_text(BOT_BRAND, 40)}">
            <label>Coin Name</label><input name="COIN_NAME" value="{clean_text(COIN_NAME, 40)}">
          </div>
          <div class="card"><h3>📺 Channels</h3>
            <label>Commands Channel ID</label><input name="COMMANDS_CHANNEL_ID" value="{COMMANDS_CHANNEL_ID}">
            <label>Gambling Channel ID</label><input name="GAMBLING_CHANNEL_ID" value="{GAMBLING_CHANNEL_ID}">
            <label>Shop Channel ID</label><input name="SHOP_CHANNEL_ID" value="{SHOP_CHANNEL_ID}">
            <label>Events Channel ID</label><input name="EVENTS_CHANNEL_ID" value="{EVENTS_CHANNEL_ID}">
            <label>Announcements Channel ID</label><input name="BOT_ANNOUNCEMENTS_CHANNEL_ID" value="{BOT_ANNOUNCEMENTS_CHANNEL_ID}">
            <label>Giveaways Channel ID</label><input name="GIVEAWAYS_CHANNEL_ID" value="{GIVEAWAYS_CHANNEL_ID}">
            <label>Memory Backup Channel ID</label><input name="MEMORY_BACKUP_CHANNEL_ID" value="{MEMORY_BACKUP_CHANNEL_ID}">
            <label>Economy Guide Channel ID</label><input name="ECONOMY_EXPLAIN_CHANNEL_ID" value="{ECONOMY_EXPLAIN_CHANNEL_ID}">
          </div>
          <div class="card"><h3>🎭 Roles</h3>
            <label>VIP Role ID</label><input name="VIP_ROLE_ID" value="{VIP_ROLE_ID}">
            <label>VIP Role Name</label><input name="VIP_ROLE_NAME" value="{clean_text(VIP_ROLE_NAME, 80)}">
            <label>VIP Role Color Hex</label><input name="VIP_ROLE_COLOR" value="#{int(VIP_ROLE_COLOR):06X}">
            <label>Event Winner Role ID</label><input name="EVENT_WINNER_ROLE_ID" value="{EVENT_WINNER_ROLE_ID}">
            <label>Event Winner Role Name</label><input name="EVENT_WINNER_ROLE_NAME" value="{clean_text(EVENT_WINNER_ROLE_NAME, 80)}">
            <label>Event Winner Role Color Hex</label><input name="EVENT_WINNER_ROLE_COLOR" value="#{int(EVENT_WINNER_ROLE_COLOR):06X}">
            <p class="muted">إذا خليت Role ID = 0، البوت ينشئ الرتبة تلقائيًا.</p>
          </div>
          <div class="card"><h3>💰 Economy</h3>
            <label>Salary Base</label><input name="DAILY_REWARD_BASE" value="{DAILY_REWARD_BASE}">
            <label>Level Up Coin Bonus</label><input name="LEVEL_UP_COIN_BONUS" value="{LEVEL_UP_COIN_BONUS}">
            <label>Booster Weekly Reward</label><input name="BOOSTER_WEEKLY_REWARD" value="{BOOSTER_WEEKLY_REWARD}">
            <label>Economy Guide Interval Hours</label><input name="ECONOMY_GUIDE_HOURS" value="{round(ECONOMY_EXPLAIN_INTERVAL_SECONDS/3600, 2)}">
            <label><input type="checkbox" name="ECONOMY_GUIDE_AUTO_ENABLED" {checked(ECONOMY_GUIDE_AUTO_ENABLED)}> Auto Economy Guide Enabled</label>
            <p class="muted">Auto guide now respects the saved last-send time, so redeploying the bot will not spam the guide again.</p>
          </div>
          <div class="card"><h3>🎰 Casino</h3>
            <label>Gamble Cooldown Seconds</label><input name="GAMBLE_COOLDOWN_SECONDS" value="{GAMBLE_COOLDOWN_SECONDS}">
            <p class="muted">نسب الألعاب الأساسية تبقى ثابتة الآن، ونقدر نضيف sliders لاحقًا.</p>
          </div>
          <div class="card"><h3>🛒 Shop</h3>
            <label><input type="checkbox" name="SHOP_ENABLED" {checked(SHOP_ENABLED)}> Shop Enabled</label>
            <label>VIP Price</label><input name="SHOP_VIP_PRICE" value="{SHOP_VIP_PRICE}">
            <label>VIP Duration Days</label><input name="SHOP_VIP_DAYS" value="{SHOP_VIP_DAYS}">
            <label>Lootbox Price</label><input name="LOOTBOX_PRICE" value="{LOOTBOX_PRICE}">
            <label>Lootbox Cooldown Seconds</label><input name="LOOTBOX_COOLDOWN_SECONDS" value="{LOOTBOX_COOLDOWN_SECONDS}">
          </div>
          <div class="card"><h3>🎉 Events</h3>
            <label><input type="checkbox" name="EVENTS_ENABLED" {checked(EVENTS_ENABLED)}> Events Enabled</label>
            <label>Default Event Prize</label><input name="DEFAULT_EVENT_PRIZE" value="{DEFAULT_EVENT_PRIZE}">
            <label>Default Event Duration Minutes</label><input name="DEFAULT_EVENT_DURATION_MINUTES" value="{DEFAULT_EVENT_DURATION_MINUTES}">
            <label><input type="checkbox" name="PUBLIC_LEADERBOARD_ENABLED" {checked(PUBLIC_LEADERBOARD_ENABLED)}> Public Leaderboard Enabled</label>
          </div>
          <div class="card"><h3>🧩 Categories</h3>
            <label>LFG Voice Category ID</label><input name="GAME_VOICE_CATEGORY_ID" value="{GAME_VOICE_CATEGORY_ID}">
            <label>Logs Category ID</label><input name="LOGS_CATEGORY_ID" value="{LOGS_CATEGORY_ID}">
          </div>
        </div>
        <div style="height:16px"></div>
        <button class="btn primary" type="submit">💾 Save Full Customization</button>
        <a class="btn" href="/dashboard/create-roles">✨ Create / Refresh VIP Roles</a>
      </form>
    </div>
    """
    return render_dashboard_page("Customization", body)


@app.route("/dashboard/settings", methods=["POST"])
def dashboard_settings_action():
    denied = dashboard_require_owner()
    if denied:
        return denied
    global BOT_BRAND, COMMANDS_CHANNEL_ID, GAMBLING_CHANNEL_ID, MEMORY_BACKUP_CHANNEL_ID, GIVEAWAYS_CHANNEL_ID
    global SHOP_CHANNEL_ID, EVENTS_CHANNEL_ID, BOT_ANNOUNCEMENTS_CHANNEL_ID, ECONOMY_EXPLAIN_CHANNEL_ID, GAME_VOICE_CATEGORY_ID, LOGS_CATEGORY_ID
    global GAMBLE_COOLDOWN_SECONDS, ECONOMY_EXPLAIN_INTERVAL_SECONDS, BOOSTER_WEEKLY_REWARD, COIN_NAME, ECONOMY_GUIDE_AUTO_ENABLED
    global VIP_ROLE_ID, EVENT_WINNER_ROLE_ID, VIP_ROLE_NAME, EVENT_WINNER_ROLE_NAME, VIP_ROLE_COLOR, EVENT_WINNER_ROLE_COLOR
    global SHOP_ENABLED, EVENTS_ENABLED, SHOP_VIP_PRICE, SHOP_VIP_DAYS, LOOTBOX_PRICE, LOOTBOX_COOLDOWN_SECONDS
    global DEFAULT_EVENT_PRIZE, DEFAULT_EVENT_DURATION_MINUTES, PUBLIC_LEADERBOARD_ENABLED, DAILY_REWARD_BASE, LEVEL_UP_COIN_BONUS
    try:
        BOT_BRAND = str(request.form.get("BOT_BRAND", BOT_BRAND)).strip()[:40] or BOT_BRAND
        COIN_NAME = str(request.form.get("COIN_NAME", COIN_NAME)).strip()[:40] or COIN_NAME
        COMMANDS_CHANNEL_ID = parse_int_field(request.form.get("COMMANDS_CHANNEL_ID"), COMMANDS_CHANNEL_ID, 1)
        GAMBLING_CHANNEL_ID = parse_int_field(request.form.get("GAMBLING_CHANNEL_ID"), GAMBLING_CHANNEL_ID, 1)
        SHOP_CHANNEL_ID = parse_int_field(request.form.get("SHOP_CHANNEL_ID"), SHOP_CHANNEL_ID, 1)
        EVENTS_CHANNEL_ID = parse_int_field(request.form.get("EVENTS_CHANNEL_ID"), EVENTS_CHANNEL_ID, 1)
        BOT_ANNOUNCEMENTS_CHANNEL_ID = parse_int_field(request.form.get("BOT_ANNOUNCEMENTS_CHANNEL_ID"), BOT_ANNOUNCEMENTS_CHANNEL_ID, 1)
        GIVEAWAYS_CHANNEL_ID = parse_int_field(request.form.get("GIVEAWAYS_CHANNEL_ID"), GIVEAWAYS_CHANNEL_ID, 1)
        MEMORY_BACKUP_CHANNEL_ID = parse_int_field(request.form.get("MEMORY_BACKUP_CHANNEL_ID"), MEMORY_BACKUP_CHANNEL_ID, 1)
        ECONOMY_EXPLAIN_CHANNEL_ID = parse_int_field(request.form.get("ECONOMY_EXPLAIN_CHANNEL_ID"), ECONOMY_EXPLAIN_CHANNEL_ID, 1)
        GAME_VOICE_CATEGORY_ID = parse_int_field(request.form.get("GAME_VOICE_CATEGORY_ID"), GAME_VOICE_CATEGORY_ID, 1)
        LOGS_CATEGORY_ID = parse_int_field(request.form.get("LOGS_CATEGORY_ID"), LOGS_CATEGORY_ID, 1)
        VIP_ROLE_ID = parse_int_field(request.form.get("VIP_ROLE_ID"), VIP_ROLE_ID, 0)
        EVENT_WINNER_ROLE_ID = parse_int_field(request.form.get("EVENT_WINNER_ROLE_ID"), EVENT_WINNER_ROLE_ID, 0)
        VIP_ROLE_NAME = str(request.form.get("VIP_ROLE_NAME", VIP_ROLE_NAME)).strip()[:80] or VIP_ROLE_NAME
        EVENT_WINNER_ROLE_NAME = str(request.form.get("EVENT_WINNER_ROLE_NAME", EVENT_WINNER_ROLE_NAME)).strip()[:80] or EVENT_WINNER_ROLE_NAME
        VIP_ROLE_COLOR = parse_int_field(str(request.form.get("VIP_ROLE_COLOR", VIP_ROLE_COLOR)).replace("#", "0x"), VIP_ROLE_COLOR, 0)
        EVENT_WINNER_ROLE_COLOR = parse_int_field(str(request.form.get("EVENT_WINNER_ROLE_COLOR", EVENT_WINNER_ROLE_COLOR)).replace("#", "0x"), EVENT_WINNER_ROLE_COLOR, 0)
        GAMBLE_COOLDOWN_SECONDS = parse_int_field(request.form.get("GAMBLE_COOLDOWN_SECONDS"), GAMBLE_COOLDOWN_SECONDS, 0)
        DAILY_REWARD_BASE = parse_int_field(request.form.get("DAILY_REWARD_BASE"), DAILY_REWARD_BASE, 0)
        LEVEL_UP_COIN_BONUS = parse_int_field(request.form.get("LEVEL_UP_COIN_BONUS"), LEVEL_UP_COIN_BONUS, 0)
        BOOSTER_WEEKLY_REWARD = parse_int_field(request.form.get("BOOSTER_WEEKLY_REWARD"), BOOSTER_WEEKLY_REWARD, 0)
        try:
            ECONOMY_EXPLAIN_INTERVAL_SECONDS = max(60, int(float(str(request.form.get("ECONOMY_GUIDE_HOURS", "7")).strip()) * 3600))
        except:
            pass
        ECONOMY_GUIDE_AUTO_ENABLED = "ECONOMY_GUIDE_AUTO_ENABLED" in request.form
        SHOP_ENABLED = "SHOP_ENABLED" in request.form
        EVENTS_ENABLED = "EVENTS_ENABLED" in request.form
        PUBLIC_LEADERBOARD_ENABLED = "PUBLIC_LEADERBOARD_ENABLED" in request.form
        SHOP_VIP_PRICE = parse_int_field(request.form.get("SHOP_VIP_PRICE"), SHOP_VIP_PRICE, 0)
        SHOP_VIP_DAYS = parse_int_field(request.form.get("SHOP_VIP_DAYS"), SHOP_VIP_DAYS, 1)
        LOOTBOX_PRICE = parse_int_field(request.form.get("LOOTBOX_PRICE"), LOOTBOX_PRICE, 0)
        LOOTBOX_COOLDOWN_SECONDS = parse_int_field(request.form.get("LOOTBOX_COOLDOWN_SECONDS"), LOOTBOX_COOLDOWN_SECONDS, 0)
        DEFAULT_EVENT_PRIZE = parse_int_field(request.form.get("DEFAULT_EVENT_PRIZE"), DEFAULT_EVENT_PRIZE, 0)
        DEFAULT_EVENT_DURATION_MINUTES = parse_int_field(request.form.get("DEFAULT_EVENT_DURATION_MINUTES"), DEFAULT_EVENT_DURATION_MINUTES, 1)
        dashboard_merge_settings({
            "BOT_BRAND": BOT_BRAND, "COIN_NAME": COIN_NAME,
            "COMMANDS_CHANNEL_ID": COMMANDS_CHANNEL_ID, "GAMBLING_CHANNEL_ID": GAMBLING_CHANNEL_ID,
            "SHOP_CHANNEL_ID": SHOP_CHANNEL_ID, "EVENTS_CHANNEL_ID": EVENTS_CHANNEL_ID,
            "BOT_ANNOUNCEMENTS_CHANNEL_ID": BOT_ANNOUNCEMENTS_CHANNEL_ID, "GIVEAWAYS_CHANNEL_ID": GIVEAWAYS_CHANNEL_ID,
            "MEMORY_BACKUP_CHANNEL_ID": MEMORY_BACKUP_CHANNEL_ID, "ECONOMY_EXPLAIN_CHANNEL_ID": ECONOMY_EXPLAIN_CHANNEL_ID,
            "GAME_VOICE_CATEGORY_ID": GAME_VOICE_CATEGORY_ID, "LOGS_CATEGORY_ID": LOGS_CATEGORY_ID,
            "VIP_ROLE_ID": VIP_ROLE_ID, "EVENT_WINNER_ROLE_ID": EVENT_WINNER_ROLE_ID,
            "VIP_ROLE_NAME": VIP_ROLE_NAME, "EVENT_WINNER_ROLE_NAME": EVENT_WINNER_ROLE_NAME,
            "VIP_ROLE_COLOR": VIP_ROLE_COLOR, "EVENT_WINNER_ROLE_COLOR": EVENT_WINNER_ROLE_COLOR,
            "GAMBLE_COOLDOWN_SECONDS": GAMBLE_COOLDOWN_SECONDS,
            "ECONOMY_EXPLAIN_INTERVAL_SECONDS": ECONOMY_EXPLAIN_INTERVAL_SECONDS,
            "ECONOMY_GUIDE_AUTO_ENABLED": ECONOMY_GUIDE_AUTO_ENABLED,
            "DAILY_REWARD_BASE": DAILY_REWARD_BASE, "LEVEL_UP_COIN_BONUS": LEVEL_UP_COIN_BONUS,
            "BOOSTER_WEEKLY_REWARD": BOOSTER_WEEKLY_REWARD,
            "SHOP_ENABLED": SHOP_ENABLED, "EVENTS_ENABLED": EVENTS_ENABLED,
            "SHOP_VIP_PRICE": SHOP_VIP_PRICE, "SHOP_VIP_DAYS": SHOP_VIP_DAYS,
            "LOOTBOX_PRICE": LOOTBOX_PRICE, "LOOTBOX_COOLDOWN_SECONDS": LOOTBOX_COOLDOWN_SECONDS,
            "DEFAULT_EVENT_PRIZE": DEFAULT_EVENT_PRIZE, "DEFAULT_EVENT_DURATION_MINUTES": DEFAULT_EVENT_DURATION_MINUTES,
            "PUBLIC_LEADERBOARD_ENABLED": PUBLIC_LEADERBOARD_ENABLED,
        })
        dashboard_log_action("Customization updated", "Full runtime customization settings were changed", session.get("discord_user"))
        msg = "Customization saved. Most settings apply instantly; role/category changes may need a quick refresh."
    except Exception as e:
        return redirect("/dashboard/settings?err=" + urllib.parse.quote(str(e)))
    return redirect("/dashboard/settings?msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/create-roles")
def dashboard_create_roles_action():
    denied = dashboard_require_owner()
    if denied:
        return denied
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return redirect("/dashboard/settings?err=" + urllib.parse.quote("Guild not loaded yet."))
        fut = asyncio.run_coroutine_threadsafe(ensure_custom_roles(guild), bot.loop)
        fut.result(timeout=15)
        dashboard_log_action("Created/refreshed custom roles", f"VIP={VIP_ROLE_ID}, Winner={EVENT_WINNER_ROLE_ID}", session.get("discord_user"))
        return redirect("/dashboard/settings?msg=" + urllib.parse.quote("VIP/Event Winner roles created or refreshed."))
    except Exception as e:
        return redirect("/dashboard/settings?err=" + urllib.parse.quote(str(e)))


@app.route("/dashboard/economy", methods=["POST"])
def dashboard_economy_action():
    denied = dashboard_require_owner()
    if denied:
        return denied
    try:
        action = request.form.get("action", "add")
        amount = parse_int_field(request.form.get("amount", "0"), 0, 0)

        if action in {"bulk_add", "bulk_remove"}:
            confirm = (request.form.get("confirm") or "").strip().lower()
            if confirm not in {"confirm", "تأكيد", "تاكيد"}:
                msg = "Bulk action cancelled. اكتب CONFIRM في خانة التأكيد."
            elif amount <= 0:
                msg = "Amount must be greater than 0."
            else:
                guild = bot.get_guild(GUILD_ID)
                if not guild:
                    msg = "Guild is not loaded yet. Try again after the bot is fully online."
                elif action == "bulk_add":
                    admin_user = session.get("discord_user") or {}
                    fut = asyncio.run_coroutine_threadsafe(bulk_add_money_to_all(guild, amount, source_type="dashboard_bulk_add", admin_id=admin_user.get("id", 0), admin_name=admin_user.get("username", "Dashboard Owner")), bot.loop)
                    result = fut.result(timeout=90)
                    msg = f"Added {fmt_num(amount)} {nm_coin_name()} to {fmt_num(result['count'])} members. Total added: {fmt_num(result['total_added'])}."
                    dashboard_log_action("Economy: bulk add all", msg, session.get("discord_user"))
                else:
                    admin_user = session.get("discord_user") or {}
                    fut = asyncio.run_coroutine_threadsafe(bulk_remove_money_from_all(guild, amount, source_type="dashboard_bulk_remove", admin_id=admin_user.get("id", 0), admin_name=admin_user.get("username", "Dashboard Owner")), bot.loop)
                    result = fut.result(timeout=90)
                    msg = f"Took up to {fmt_num(amount)} {nm_coin_name()} from {fmt_num(result['count'])} members. Total removed: {fmt_num(result['total_removed'])}."
                    dashboard_log_action("Economy: bulk remove all", msg, session.get("discord_user"))
        else:
            user_id = parse_int_field(request.form.get("user_id", "0"), 0, 1)
            if action == "add":
                admin_user = session.get("discord_user") or {}
                balance = add_money(user_id, amount, source_type="dashboard_admin_add", admin_id=admin_user.get("id", 0), admin_name=admin_user.get("username", "Dashboard Owner"), details="Dashboard manual add money")
                msg = f"Added {fmt_num(amount)} {nm_coin_name()} to {user_id}. New balance: {fmt_num(balance)}"
                dashboard_log_action("Economy: add money", f"Added {fmt_num(amount)} {nm_coin_name()} to {user_id}. New balance {fmt_num(balance)}", session.get("discord_user"))
            elif action == "remove":
                admin_user = session.get("discord_user") or {}
                ok, balance = remove_money(user_id, amount, source_type="dashboard_admin_remove", admin_id=admin_user.get("id", 0), admin_name=admin_user.get("username", "Dashboard Owner"), details="Dashboard manual remove money")
                msg = f"Removed {fmt_num(amount)} {nm_coin_name()} from {user_id}. New balance: {fmt_num(balance)}" if ok else f"User {user_id} does not have enough balance. Current: {fmt_num(balance)}"
                dashboard_log_action("Economy: remove money", f"Attempted remove {fmt_num(amount)} {nm_coin_name()} from {user_id}. OK={ok}. Balance {fmt_num(balance)}", session.get("discord_user"))
            elif action == "set":
                admin_user = session.get("discord_user") or {}
                balance = set_balance(user_id, amount, source_type="dashboard_set", admin_id=admin_user.get("id", 0), admin_name=admin_user.get("username", "Dashboard Owner"), details="Dashboard manual set balance")
                msg = f"Set {user_id} balance to {fmt_num(balance)} {nm_coin_name()}"
                dashboard_log_action("Economy: set balance", f"Set {user_id} balance to {fmt_num(balance)} {nm_coin_name()}", session.get("discord_user"))
            else:
                msg = "Unknown action."
    except Exception as e:
        msg = f"Economy action failed: {e}"
    back = request.referrer or "/dashboard/economy"
    sep = "&" if "?" in back else "?"
    return redirect(back + sep + "msg=" + urllib.parse.quote(msg))


@app.route("/dashboard/levels", methods=["POST"])
def dashboard_levels_action():
    denied = dashboard_require_owner()
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
    denied = dashboard_require_owner()
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
    init_db()
    create_default_guild_settings(guild)
    await send_log(
        bot.get_guild(GUILD_ID),
        "🌍 Bot Added To New Server",
        f"**Server:** `{guild.name}`\n**Guild ID:** `{guild.id}`\n**Members:** `{getattr(guild, 'member_count', 0)}`",
        COLOR_BLUE,
        log_type="server"
    )


@bot.event
async def on_ready():
    nm_v4_boot_normalize_brand_coin()
    nm_pg_boot()
    nm_auto_restore_bundled_memory("on_ready")
    await nm_restore_latest_discord_memory_backup("on_ready")
    nm_bridge_local_restore_to_data("on_ready")
    print("✅ NM stable polished build active")
    print(f"✅ NM persistent storage active: {NM_DATA_DIR}")
    try:
        await nm_sync_slash_commands()
    except Exception:
        pass
    global memory_backup_task, economy_explain_task, booster_weekly_task, timed_roles_task, auction_task

    guild = bot.get_guild(GUILD_ID)

    if guild:
        restored, restore_message = await restore_memory_from_backup(guild, force=False)
        if restored:
            print(f"Memory restored on startup: {restore_message}")

    init_db()

    for live_guild in bot.guilds:
        create_default_guild_settings(live_guild)

    # =========================
    # SLASH COMMAND SYNC - CLEAN MODE
    # =========================
    # Important:
    # Older builds copied global slash commands into every guild.
    # Discord then showed two copies of the same command: one global + one guild command.
    # This clean mode keeps ONE source only: global commands.
    # It also deletes old guild-specific copies so the command menu stops duplicating.
    try:
        global_synced = await bot.tree.sync()
        print(f"✅ Slash commands synced globally: {len(global_synced)}")
    except Exception as e:
        print(f"❌ Global slash sync error: {type(e).__name__}: {e}")

    try:
        for live_guild in bot.guilds:
            guild_obj = discord.Object(id=live_guild.id)
            bot.tree.clear_commands(guild=guild_obj)
            cleared = await bot.tree.sync(guild=guild_obj)
            print(f"🧹 Cleared guild-specific duplicate slash commands in {live_guild.name} ({live_guild.id}). Remaining guild commands: {len(cleared)}")
            await asyncio.sleep(1)
    except Exception as e:
        print(f"❌ Guild duplicate cleanup error: {type(e).__name__}: {e}")

    if guild:
        await ensure_custom_roles(guild)

    bot.add_view(GameRolesView())

    if memory_backup_task is None or memory_backup_task.done():
        memory_backup_task = asyncio.create_task(memory_backup_loop())

    if economy_explain_task is None or economy_explain_task.done():
        economy_explain_task = asyncio.create_task(economy_explain_loop())

    if booster_weekly_task is None or booster_weekly_task.done():
        booster_weekly_task = asyncio.create_task(booster_weekly_loop())

    if timed_roles_task is None or timed_roles_task.done():
        timed_roles_task = asyncio.create_task(timed_roles_loop())

    if auction_task is None or auction_task.done():
        auction_task = asyncio.create_task(auction_loop())

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="7 Servers | !راتب + /راتب"
        )
    )

    print(f"NM System Ready: {bot.user}")



# =========================
# NM LEGACY ! COMMAND BRIDGE
# =========================
_nm_legacy_done = set()

def nm_legacy_gid(message):
    try:
        return int(message.guild.id)
    except Exception:
        return GUILD_ID

def nm_legacy_coin(guild_id):
    try:
        if "get_guild_settings" in globals():
            s = get_guild_settings(int(guild_id))
            return s.get("coin_name") or s.get("currency_name") or s.get("economy_coin_name") or "NM Coin"
    except Exception:
        pass
    return "NM Coin"

def nm_legacy_ensure_economy(cur):
    cur.execute("CREATE TABLE IF NOT EXISTS economy (guild_id INTEGER DEFAULT 0, user_id INTEGER, balance INTEGER DEFAULT 0)")
    try:
        nm_ensure_guild_column(cur, "economy")
    except Exception:
        pass

def nm_legacy_balance(guild_id, user_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_legacy_ensure_economy(cur)
        cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=? LIMIT 1", (int(guild_id), int(user_id)))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO economy (guild_id,user_id,balance) VALUES (?,?,?)", (int(guild_id), int(user_id), 0))
            conn.commit()
            bal = 0
        else:
            bal = int(row[0] or 0)
        conn.close()
        return bal
    except Exception as e:
        print(f"legacy balance error: {e}")
        return 0

def nm_legacy_add_money(guild_id, user_id, amount):
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_legacy_ensure_economy(cur)
        cur.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=? LIMIT 1", (int(guild_id), int(user_id)))
        if not cur.fetchone():
            cur.execute("INSERT INTO economy (guild_id,user_id,balance) VALUES (?,?,?)", (int(guild_id), int(user_id), 0))
        cur.execute("UPDATE economy SET balance=COALESCE(balance,0)+? WHERE guild_id=? AND user_id=?", (int(amount), int(guild_id), int(user_id)))
        conn.commit()
        conn.close()
        try:
            nm_persist_dashboard_change("legacy economy change")
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"legacy add money error: {e}")
        return False

def nm_legacy_take_money(guild_id, user_id, amount):
    if nm_legacy_balance(guild_id, user_id) < int(amount):
        return False
    return nm_legacy_add_money(guild_id, user_id, -int(amount))

def nm_legacy_amount(raw):
    try:
        return max(1, int(str(raw).replace(",", "").strip()))
    except Exception:
        return 0

def nm_legacy_level(guild_id, user_id):
    try:
        conn = db_connect()
        cur = conn.cursor()
        try:
            nm_ensure_guild_column(cur, "levels")
        except Exception:
            pass
        cur.execute("SELECT level,xp FROM levels WHERE guild_id=? AND user_id=? LIMIT 1", (int(guild_id), int(user_id)))
        row = cur.fetchone()
        conn.close()
        if row:
            return int(row[0] or 1), int(row[1] or 0)
    except Exception:
        pass
    return 1, 0

async def nm_legacy_salary(message):
    gid = nm_legacy_gid(message)
    uid = int(message.author.id)
    level = nm_get_level_safe(gid, uid)
    ok, remaining, bal, amount = nm_salary_safe(gid, uid, level)
    if not ok:
        return await message.channel.send(f"⏳ {message.author.mention} تقدر تستلم راتب جديد بعد **{max(1, int(remaining)//60)} دقيقة**.")

    coin = nm_legacy_coin(gid)
    embed = discord.Embed(
        title=f"{message.author.display_name} • Salary",
        description=f"**تم استلام الراتب 💸**\n\nتم إيداع الراتب في محفظتك يا {message.author.mention}\n\n📈 **+{amount:,} 🪙 {coin}**  Level **{level}**\n\n**الرصيد الجديد 💼**\n🪙 **{bal:,} {coin}**",
        color=0x22c55e
    )
    try:
        embed.set_thumbnail(url=message.author.display_avatar.url)
    except Exception:
        pass
    embed.set_footer(text="NM System • تقدر تستلم راتب جديد كل ساعة")
    await message.channel.send(embed=embed)

async def nm_legacy_balance_cmd(message):
    gid = nm_legacy_gid(message)
    member = message.mentions[0] if message.mentions else message.author
    coin = nm_legacy_coin(gid)
    bal = nm_legacy_balance(gid, int(member.id))
    embed = discord.Embed(title=f"{member.display_name} • Wallet", description=f"🪙 **{bal:,} {coin}**", color=0x8b5cf6)
    try:
        embed.set_thumbnail(url=member.display_avatar.url)
    except Exception:
        pass
    await message.channel.send(embed=embed)

async def nm_legacy_luck(message, amount):
    gid = nm_legacy_gid(message)
    uid = int(message.author.id)
    amount = nm_legacy_amount(amount)
    coin = nm_legacy_coin(gid)
    if amount <= 0:
        return await message.channel.send("اكتب مبلغ صحيح. مثال: `!حظ 100`")
    if not nm_legacy_take_money(gid, uid, amount):
        return await message.channel.send(f"❌ رصيدك ما يكفي. رصيدك: **{nm_legacy_balance(gid, uid):,} {coin}**")
    import random
    if random.random() < 0.5:
        nm_legacy_add_money(gid, uid, amount * 2)
        await message.channel.send(f"🎉 فزت! ربحت **{amount:,} {coin}**\nرصيدك: **{nm_legacy_balance(gid, uid):,} {coin}**")
    else:
        await message.channel.send(f"💀 خسرت **{amount:,} {coin}**\nرصيدك: **{nm_legacy_balance(gid, uid):,} {coin}**")

async def nm_legacy_slot(message, amount):
    gid = nm_legacy_gid(message)
    uid = int(message.author.id)
    amount = nm_legacy_amount(amount)
    coin = nm_legacy_coin(gid)
    if amount <= 0:
        return await message.channel.send("اكتب مبلغ صحيح. مثال: `!سلوت 100`")
    if not nm_legacy_take_money(gid, uid, amount):
        return await message.channel.send(f"❌ رصيدك ما يكفي. رصيدك: **{nm_legacy_balance(gid, uid):,} {coin}**")
    import random
    icons = ["🍒","🍋","🍇","💎","7️⃣"]
    roll = [random.choice(icons) for _ in range(3)]
    if len(set(roll)) == 1:
        prize = amount * 5
        nm_legacy_add_money(gid, uid, prize)
        return await message.channel.send(f"🎰 {' | '.join(roll)}\n🔥 جاك بوت! ربحت **{prize:,} {coin}**")
    if len(set(roll)) == 2:
        prize = amount * 2
        nm_legacy_add_money(gid, uid, prize)
        return await message.channel.send(f"🎰 {' | '.join(roll)}\n🎉 ربحت **{prize:,} {coin}**")
    await message.channel.send(f"🎰 {' | '.join(roll)}\n💀 خسرت **{amount:,} {coin}**")

async def nm_legacy_top(message):
    gid = nm_legacy_gid(message)
    coin = nm_legacy_coin(gid)
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_legacy_ensure_economy(cur)
        cur.execute("SELECT user_id,balance FROM economy WHERE guild_id=? ORDER BY balance DESC LIMIT 10", (gid,))
        rows = cur.fetchall()
        conn.close()
    except Exception:
        rows = []
    if not rows:
        return await message.channel.send("ما فيه بيانات اقتصاد للحين.")
    lines = []
    for i, (uid, bal) in enumerate(rows, 1):
        m = message.guild.get_member(int(uid)) if message.guild else None
        lines.append(f"**#{i}** {(m.mention if m else f'`{uid}`')} — 🪙 **{int(bal):,} {coin}**")
    await message.channel.send(embed=discord.Embed(title="🏆 أغنى الأعضاء", description="\n".join(lines), color=0xf59e0b))

async def nm_handle_legacy_bang(message):
    if not message.guild or message.author.bot:
        return False
    content = (message.content or "").strip()
    if not content.startswith("!"):
        return False
    if message.id in _nm_legacy_done:
        return True
    _nm_legacy_done.add(message.id)
    if len(_nm_legacy_done) > 5000:
        _nm_legacy_done.clear()

    parts = content.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in {"!ping","!بنق","!بينق"}:
        await message.channel.send(f"🏓 Pong! `{round(bot.latency*1000)}ms`")
        return True
    if cmd in {"!راتب","!salary"}:
        await nm_legacy_salary(message)
        return True
    if cmd in {"!رصيدي","!رصيد","!balance","!wallet","!فلوسي"}:
        await nm_legacy_balance_cmd(message)
        return True
    if cmd in {"!اغنى","!top","!توب"}:
        await nm_legacy_top(message)
        return True
    if cmd in {"!حظ","!luck","!دبل","!double"}:
        await nm_legacy_luck(message, args[0] if args else 0)
        return True
    if cmd in {"!سلوت","!slot"}:
        await nm_legacy_slot(message, args[0] if args else 0)
        return True
    if cmd in {"!شرح","!اقتصاد","!help","!مساعدة"}:
        coin = nm_legacy_coin(nm_legacy_gid(message))
        embed = discord.Embed(
            title="📘 NM System",
            description=f"`!راتب` أو `/راتب`\n`!رصيدي` أو `/رصيدي`\n`!اغنى` أو `/اغنى`\n`!حظ 100` أو `/حظ`\n`!سلوت 100` أو `/سلوت`\n\nالعملة: **{coin}**",
            color=0x5865F2
        )
        await message.channel.send(embed=embed)
        return True
    return False

@bot.event
async def on_message(message):
    if await nm_handle_legacy_bang(message):
        return
    global protection_enabled

    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        # Outbound DM forwarding is disabled to avoid Discord anti-spam quarantine.
        # The bot will not reply in DMs or forward DMs privately.
        return

    if not message.guild or not is_guild_enabled(message.guild.id):
        return

    raw_content = (message.content or "").strip().lower()

    # Emergency direct replies: these bypass the dashboard command guard.
    # If these work, the bot is reading messages and command processing is healthy enough to debug from Discord.
    if raw_content in ("!بنق", "!بينق", "!بنج", "!ping", "!p"):
        await message.channel.send(
            embed=discord.Embed(
                title="🏓 Pong",
                description=f"{BOT_BRAND} شغال.\nLatency: `{round(bot.latency * 1000)} ms`",
                color=COLOR_GREEN,
                timestamp=discord.utils.utcnow()
            )
        )
        return

    cc_record_event(
        "message",
        user_id=message.author.id,
        user_name=str(message.author),
        channel_id=message.channel.id,
        channel_name=getattr(message.channel, "name", "unknown"),
        details=message.content[:250]
    )

    content = message.content.lower()

    now = time.time()
    last_xp = xp_cooldowns.get(message.author.id, 0)

    if is_system_enabled("levels") and now - last_xp >= LEVEL_COOLDOWN and not message.content.startswith(PREFIX):
        xp_cooldowns[message.author.id] = now
        gained = random.randint(8, 16)
        xp, level, leveled_up = add_xp(message.author.id, gained)

        if is_system_enabled("economy") and nm_message_coin_allowed(message.guild.id if message.guild else 0, message.author.id):
            try:
                v3_add_money(message.guild.id if message.guild else 0, message.author.id, random.randint(3, 8), source_type="message_coin", details="Persistent message coin reward")
            except Exception:
                add_money(message.author.id, random.randint(3, 8))

        if leveled_up and nm_level_bonus_allowed(message.guild.id if message.guild else 0, message.author.id, level):
            bonus = level * LEVEL_UP_COIN_BONUS
            try:
                new_balance = v3_add_money(message.guild.id if message.guild else 0, message.author.id, bonus, source_type="level_bonus", details=f"Level {level} bonus")
            except Exception:
                new_balance = add_money(message.author.id, bonus)
            await message.channel.send(
                f"📊 {message.author.mention} وصل لفل **{level}**! 🎉\n"
                f"💰 مكافأة اللفل: **{bonus:,} {nm_coin_name()}** | رصيدك: **{new_balance:,}**",
                delete_after=10
            )

    protection_settings = get_guild_protection_settings(message.guild.id)
    protection_skip_member = False
    if message.author.id in BYPASS_USER_IDS:
        protection_skip_member = True
    elif protection_settings.get("bypass_admins") and is_bypass(message.author):
        protection_skip_member = True
    elif protection_member_ignored_by_role(protection_settings, message.author):
        protection_skip_member = True

    if protection_settings.get("protection_enabled") and is_system_enabled("protection") and not protection_skip_member and not protection_channel_ignored_for(protection_settings, message.channel.id):

        if protection_settings.get("bad_words") and contains_bad_word(content):
            await handle_violation(message, "كلمة ممنوعة / سب")
            return

        if protection_settings.get("links"):
            link_words = ["http://", "https://"]
            invite_words = ["discord.gg", "discord.com/invite", "discordapp.com/invite"]
            blocked_link = any(link in content for link in link_words)
            blocked_invite = protection_settings.get("invites") and any(link in content for link in invite_words)
            if (blocked_link or blocked_invite) and not protection_link_allowed_for(protection_settings, content):
                await handle_violation(message, "إرسال رابط أو دعوة ممنوعة")
                return

        if protection_settings.get("mass_mentions"):
            mentions_count = len(message.mentions) + len(message.role_mentions)

            if message.mention_everyone:
                mentions_count += 10

            if mentions_count >= int(protection_settings.get("mass_mention_limit", MASS_MENTION_LIMIT)):
                await handle_violation(message, f"منشن كثير ({mentions_count})")
                return

        if protection_settings.get("spam"):
            user_key = (message.guild.id, message.author.id)
            msg_now = time.time()
            spam_seconds = int(protection_settings.get("spam_seconds", SPAM_SECONDS))
            spam_limit = int(protection_settings.get("spam_limit", SPAM_LIMIT))

            if user_key not in user_message_times:
                user_message_times[user_key] = []

            user_message_times[user_key].append(msg_now)
            user_message_times[user_key] = [
                t for t in user_message_times[user_key]
                if msg_now - t <= spam_seconds
            ]

            if len(user_message_times[user_key]) >= spam_limit:
                user_message_times[user_key] = []
                await handle_violation(
                    message,
                    f"سبام: {spam_limit} رسائل خلال {spam_seconds} ثواني"
                )
                return

    await bot.process_commands(message)


# =========================
# AUDIT LOGS
# =========================

@bot.event
async def on_message_delete(message):
    if not message.guild or message.guild.id != GUILD_ID:
        return

    # If someone deletes a bot log message from a log room, keep the dashboard vault copy and mark who deleted it.
    if message.author.bot:
        if log_vault_is_log_channel(message.channel) and log_vault_is_known_message(message.id):
            deleter = await log_vault_deleted_by_from_audit(message.guild, getattr(message.author, "id", 0))
            deleted_by_id = getattr(deleter, "id", 0) if deleter else 0
            deleted_by_name = str(deleter) if deleter else "Unknown"
            changed = log_vault_mark_deleted(message.id, deleted_by_id, deleted_by_name)
            if changed:
                cc_record_event(
                    "log_deleted",
                    user_id=deleted_by_id,
                    user_name=deleted_by_name,
                    channel_id=message.channel.id,
                    channel_name=getattr(message.channel, "name", "unknown"),
                    details=f"Discord log message deleted. Message ID: {message.id}"
                )
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
async def on_raw_message_delete(payload):
    try:
        if getattr(payload, "guild_id", None) != GUILD_ID:
            return
        message_id = int(getattr(payload, "message_id", 0) or 0)
        if not message_id or not log_vault_is_known_message(message_id):
            return
        # This catches uncached deleted log messages. Deleter may be unknown here; cached deletes use on_message_delete.
        changed = log_vault_mark_deleted(message_id, 0, "Unknown / uncached delete")
        if changed:
            cc_record_event(
                "log_deleted",
                channel_id=int(getattr(payload, "channel_id", 0) or 0),
                channel_name="unknown",
                details=f"Uncached Discord log message deleted. Message ID: {message_id}"
            )
    except Exception as e:
        print(f"Raw log delete watch error: {e}")


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
    if not is_guild_enabled(member.guild.id):
        return

    cc_record_event(
        "member_join",
        user_id=member.id,
        user_name=str(member),
        details="Member joined the server"
    )

    protection_settings = get_guild_protection_settings(member.guild.id)
    if protection_settings.get("protection_enabled"):
        if member.bot and protection_settings.get("anti_bot_join"):
            await send_log(
                member.guild,
                "🛡️ Anti Bot Join",
                f"**Bot:** {member.mention} (`{member.id}`) دخل السيرفر.\nراجع Audit Log لمعرفة من أضافه.",
                COLOR_YELLOW,
                log_type="server"
            )
        if not member.bot and protection_settings.get("anti_raid"):
            now_ts = time.time()
            gid = int(member.guild.id)
            raid_join_times.setdefault(gid, [])
            raid_join_times[gid].append(now_ts)
            raid_join_times[gid] = [t for t in raid_join_times[gid] if now_ts - t <= int(protection_settings.get("raid_seconds", 20))]
            if len(raid_join_times[gid]) >= int(protection_settings.get("raid_join_limit", 8)):
                await send_log(
                    member.guild,
                    "🚨 Anti Raid Alert",
                    f"دخل **{len(raid_join_times[gid])}** أعضاء خلال **{protection_settings.get('raid_seconds', 20)} ثانية**.",
                    COLOR_RED,
                    log_type="member"
                )

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
    if not is_guild_enabled(member.guild.id):
        return

    cc_record_event(
        "member_leave",
        user_id=member.id,
        user_name=str(member),
        details="Member left the server"
    )

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

    if action_type == "👢 انطرد" and get_guild_protection_settings(guild.id).get("anti_kick_abuse"):
        await protection_handle_audit_event(
            guild,
            discord.AuditLogAction.kick,
            member.id,
            "anti_kick_abuse",
            "Anti Kick Abuse",
            f"تم طرد العضو `{member}` (`{member.id}`)",
            log_type="moderation"
        )

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
    if not is_guild_enabled(guild.id):
        return

    entry = await get_audit_executor(guild, discord.AuditLogAction.ban, user.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"
    reason_text = entry.reason if entry and entry.reason else "بدون سبب مكتوب"

    if get_guild_protection_settings(guild.id).get("anti_ban_abuse"):
        await protection_handle_audit_event(
            guild,
            discord.AuditLogAction.ban,
            user.id,
            "anti_ban_abuse",
            "Anti Ban Abuse",
            f"تم حظر العضو `{user}` (`{user.id}`)",
            log_type="moderation"
        )

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
    if not is_guild_enabled(guild.id):
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
    if not is_guild_enabled(before.guild.id):
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
    if not is_guild_enabled(channel.guild.id):
        return

    entry = await get_audit_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    if get_guild_protection_settings(channel.guild.id).get("anti_channel_create"):
        await protection_handle_audit_event(
            channel.guild,
            discord.AuditLogAction.channel_create,
            channel.id,
            "anti_channel_create",
            "Anti Channel Create",
            f"تم إنشاء روم `{channel.name}`",
            log_type="channel"
        )

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
    if not is_guild_enabled(channel.guild.id):
        return

    entry = await get_audit_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    if get_guild_protection_settings(channel.guild.id).get("anti_channel_delete"):
        await protection_handle_audit_event(
            channel.guild,
            discord.AuditLogAction.channel_delete,
            channel.id,
            "anti_channel_delete",
            "Anti Channel Delete",
            f"تم حذف روم `{channel.name}`",
            log_type="channel"
        )

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
    if not is_guild_enabled(before.guild.id):
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

    protection_settings = get_guild_protection_settings(after.guild.id)
    channel_setting_key = None
    if before.name != after.name and protection_settings.get("anti_channel_rename"):
        channel_setting_key = "anti_channel_rename"
    elif before.overwrites != after.overwrites and protection_settings.get("anti_channel_permission_update"):
        channel_setting_key = "anti_channel_permission_update"
    if channel_setting_key:
        await protection_handle_audit_event(
            after.guild,
            discord.AuditLogAction.channel_update,
            after.id,
            channel_setting_key,
            "Anti Channel Update",
            f"تم تعديل روم `{before.name}` → `{after.name}`",
            log_type="channel"
        )

    await send_log(
        after.guild,
        "📝 تعديل روم",
        "\n".join(changes) + f"\n**بواسطة:** {executor_text}",
        COLOR_YELLOW,
        log_type="channel"
    )


@bot.event
async def on_guild_role_create(role):
    if not is_guild_enabled(role.guild.id):
        return

    entry = await get_audit_executor(role.guild, discord.AuditLogAction.role_create, role.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    if get_guild_protection_settings(role.guild.id).get("anti_role_create"):
        await protection_handle_audit_event(
            role.guild,
            discord.AuditLogAction.role_create,
            role.id,
            "anti_role_create",
            "Anti Role Create",
            f"تم إنشاء رتبة `{role.name}`",
            log_type="role"
        )

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
    if not is_guild_enabled(role.guild.id):
        return

    entry = await get_audit_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
    executor_text = entry.user.mention if entry and entry.user else "غير معروف"

    if get_guild_protection_settings(role.guild.id).get("anti_role_delete"):
        await protection_handle_audit_event(
            role.guild,
            discord.AuditLogAction.role_delete,
            role.id,
            "anti_role_delete",
            "Anti Role Delete",
            f"تم حذف رتبة `{role.name}`",
            log_type="role"
        )

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
    if not is_guild_enabled(before.guild.id):
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

    if before.permissions.value != after.permissions.value and get_guild_protection_settings(after.guild.id).get("anti_role_permission_update"):
        await protection_handle_audit_event(
            after.guild,
            discord.AuditLogAction.role_update,
            after.id,
            "anti_role_permission_update",
            "Anti Role Update",
            f"تم تعديل صلاحيات رتبة `{after.name}`",
            log_type="role"
        )

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
    if not is_guild_enabled(before.id):
        return

    changes = []

    if before.name != after.name:
        changes.append(f"**اسم السيرفر:** `{before.name}` → `{after.name}`")

    if before.icon != after.icon:
        changes.append("**الصورة:** تغيرت")

    if not changes:
        return

    if get_guild_protection_settings(after.id).get("anti_guild_update"):
        await protection_handle_audit_event(
            after,
            discord.AuditLogAction.guild_update,
            after.id,
            "anti_guild_update",
            "Anti Server Update",
            "تم تعديل معلومات السيرفر",
            log_type="server"
        )

    await send_log(
        after,
        "⚙️ تعديل السيرفر",
        "\n".join(changes),
        COLOR_YELLOW,
        log_type="server"
    )



@bot.event
async def on_webhooks_update(channel):
    try:
        if not channel or not getattr(channel, "guild", None) or not is_guild_enabled(channel.guild.id):
            return
        if get_guild_protection_settings(channel.guild.id).get("anti_webhook_update"):
            await protection_handle_audit_event(
                channel.guild,
                discord.AuditLogAction.webhook_create,
                None,
                "anti_webhook_update",
                "Anti Webhook Update",
                f"تغيرت Webhooks في الروم {getattr(channel, 'mention', channel.name)}",
                log_type="server"
            )
        await send_log(
            channel.guild,
            "🪝 Webhook Update",
            f"**الروم:** {getattr(channel, 'mention', channel.name)}",
            COLOR_YELLOW,
            log_type="server"
        )
    except Exception as e:
        print(f"Webhook update log error: {e}")


@bot.event
async def on_guild_emojis_update(guild, before, after):
    try:
        if not is_guild_enabled(guild.id):
            return
        removed = [emoji for emoji in before if emoji not in after]
        if removed and get_guild_protection_settings(guild.id).get("anti_emoji_delete"):
            names = ", ".join([str(e.name) for e in removed[:10]])
            await protection_handle_audit_event(
                guild,
                discord.AuditLogAction.emoji_delete,
                None,
                "anti_emoji_delete",
                "Anti Emoji Delete",
                f"تم حذف إيموجيات: `{clean_text(names, 400)}`",
                log_type="server"
            )
        if removed:
            await send_log(
                guild,
                "🗑️ Emoji Deleted",
                "\n".join([f"• `{e.name}`" for e in removed[:20]]),
                COLOR_RED,
                log_type="server"
            )
    except Exception as e:
        print(f"Emoji update log error: {e}")


@bot.event
async def on_invite_delete(invite):
    try:
        guild = invite.guild
        if not guild or not is_guild_enabled(guild.id):
            return
        if get_guild_protection_settings(guild.id).get("anti_invite_delete"):
            await protection_handle_audit_event(
                guild,
                discord.AuditLogAction.invite_delete,
                None,
                "anti_invite_delete",
                "Anti Invite Delete",
                f"تم حذف دعوة: `{getattr(invite, 'code', 'unknown')}`",
                log_type="server"
            )
        await send_log(
            guild,
            "🗑️ Invite Deleted",
            f"**Code:** `{getattr(invite, 'code', 'unknown')}`",
            COLOR_YELLOW,
            log_type="server"
        )
    except Exception as e:
        print(f"Invite delete log error: {e}")


# =========================
# COMMANDS
# =========================

@bot.command(name="مساعدة", aliases=["helpme"])
async def help_cmd(ctx):
    embed = discord.Embed(title="📖 أوامر NM System", color=COLOR_PURPLE)

    embed.description = """
**الأوامر الجديدة /**
`/شرح` - الدليل الرسمي
`/ping` - فحص البوت
`/setup_status` - حالة إعداد السيرفر

**Economy**
`/رصيدي` أو `/balance`
`/راتب` أو `/salary`
`/تحويل user amount` أو `/transfer`
`/اغنى` أو `/top`

**Levels**
`/لفلي` أو `/rank`
`/ترتيب` أو `/levels`

**Casino**
`/حظ amount` أو `/luck`
`/دبل amount` أو `/double`
`/سلوت amount` أو `/slot`
`/وجه amount choice` أو `/flip`
`/بلاكجاك amount` أو `/blackjack`

**Shop**
`/متجر` أو `/shop`
`/شراء item` أو `/buy`
`/صندوق` أو `/lootbox`

**ملاحظة**
أوامر `!` القديمة ما زالت موجودة مؤقتًا لسيرفرك الأساسي، لكن الشرح الرسمي والتطوير الجديد يعتمد على أوامر `/`.
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


@bot.command(name="بنق", aliases=["ping", "بينق", "بنج", "p"])
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
    embed.add_field(name=f"{ECONOMY_EMOJI} Balance", value=f"**{balance:,}**\n{nm_coin_name()}", inline=True)
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
    embed.add_field(name=f"{ECONOMY_EMOJI} Balance", value=f"**{balance:,}**\n{nm_coin_name()}", inline=True)
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
    salary_bonus = DAILY_REWARD_BASE + (int(level) * 25)
    rank = get_money_rank(ctx.author.id)
    progress = clean_bar(xp / needed if needed else 0, 14)

    embed = discord.Embed(
        title=f"{ECONOMY_EMOJI} Economy Wallet",
        description=(
            f"**محفظة {ctx.author.mention}**\n"
            f"`{progress}` **{xp:,}/{needed:,} XP**"
        ),
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{ctx.author.display_name} • Wallet", icon_url=ctx.author.display_avatar.url)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="💼 الرصيد", value=coin_line(balance), inline=False)
    embed.add_field(name="🏆 ترتيب الغنى", value=f"**#{rank}**" if rank else "غير معروف", inline=True)
    embed.add_field(name="🏅 اللفل", value=f"**{level}**", inline=True)
    embed.add_field(name="💸 الراتب القادم", value=coin_line(salary_bonus), inline=True)
    embed.add_field(name="⚡ أوامر سريعة", value="`/راتب` • `/تحويل user amount` • `/اغنى`", inline=False)
    embed.set_footer(text=f"{BOT_BRAND} • Economy System")
    await ctx.send(embed=embed)


@bot.command(name="رصيد", aliases=["money", "coins"])
async def balance(ctx, member: discord.Member = None):
    if not await require_commands_channel(ctx):
        return

    member = member or ctx.author
    balance_amount = get_balance(member.id)
    xp, level_num = get_level_data(member.id)
    needed = level_num * 100
    salary_bonus = DAILY_REWARD_BASE + (int(level_num) * 25)
    rank = get_money_rank(member.id)
    progress = clean_bar(xp / needed if needed else 0, 14)

    embed = discord.Embed(
        title=f"{ECONOMY_EMOJI} Economy Wallet",
        description=(
            f"**محفظة {member.mention}**\n"
            f"`{progress}` **{xp:,}/{needed:,} XP**"
        ),
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{member.display_name} • Wallet", icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="💼 الرصيد", value=coin_line(balance_amount), inline=False)
    embed.add_field(name="🏆 ترتيب الغنى", value=f"**#{rank}**" if rank else "غير معروف", inline=True)
    embed.add_field(name="🏅 اللفل", value=f"**{level_num}**", inline=True)
    embed.add_field(name="💸 الراتب القادم", value=coin_line(salary_bonus), inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Economy System")
    await ctx.send(embed=embed)


@bot.command(name="راتب", aliases=["salary", "pay"])
async def salary(ctx):
    if not await require_commands_channel(ctx):
        return

    # يمنع تنفيذ نفس أمر الراتب مرتين لو صار تكرار من ديسكورد/الاستضافة.
    if not claim_command_message_once(ctx):
        return

    xp, level = get_level_data(ctx.author.id)
    success, remaining, balance_amount, reward = nm_salary_safe(ctx.guild.id if ctx.guild else 0, ctx.author.id, level)

    if not success:
        embed = discord.Embed(
            title="⏳ الراتب غير جاهز",
            description=f"راتبك القادم بعد **{format_seconds(remaining)}**.",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{ctx.author.display_name} • Salary", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="💼 محفظتك الآن", value=coin_line(balance_amount), inline=False)
        embed.add_field(name="💡 الأمر", value="استخدم `/راتب` كل ساعة.", inline=False)
        embed.set_footer(text=f"{BOT_BRAND} • Salary System")
        await ctx.send(embed=embed)
        return

    embed = discord.Embed(
        title="💸 تم استلام الراتب",
        description=f"تم إيداع الراتب في محفظتك يا {ctx.author.mention}.",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{ctx.author.display_name} • Salary", icon_url=ctx.author.display_avatar.url)
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="💵 الراتب", value=money_delta(reward), inline=True)
    embed.add_field(name="🏅 بونص اللفل", value=f"Level **{level}**", inline=True)
    embed.add_field(name="💼 الرصيد الجديد", value=coin_line(balance_amount), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} • تقدر تستلم راتب جديد كل ساعة")
    await ctx.send(embed=embed)


@bot.command(name="تحويل", aliases=["transfer"])
async def transfer_money(ctx, member: discord.Member = None, amount: int = None):
    if not await require_commands_channel(ctx):
        return

    if member is None or amount is None:
        await ctx.send("استخدم: `/تحويل user 500`")
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

    success, new_sender_balance = remove_money(ctx.author.id, amount, source_type="transfer_out", details=f"Transfer to {member.id}")

    if not success:
        await ctx.send("❌ رصيدك ما يكفي.")
        return

    new_receiver_balance = add_money(member.id, amount, source_type="transfer_in", details=f"Transfer from {ctx.author.id}")

    embed = discord.Embed(
        title="✅ Transfer Complete",
        description="تم التحويل بنجاح.",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="من", value=ctx.author.mention, inline=True)
    embed.add_field(name="إلى", value=member.mention, inline=True)
    embed.add_field(name="المبلغ", value=f"**{amount:,}** {nm_coin_name()}", inline=False)
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
    total = nm_db_sum_column("economy", "balance")

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

    balance_amount = add_money(member.id, amount, source_type="discord_admin_add", admin_id=ctx.author.id, admin_name=str(ctx.author), details=f"Discord admin add money by {ctx.author}")
    embed = discord.Embed(title="✅ Admin Economy", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
    embed.description = f"تم إعطاء {member.mention} **{amount:,} {nm_coin_name()}**."
    embed.add_field(name="رصيده الآن", value=f"**{balance_amount:,}** {nm_coin_name()}", inline=False)
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

    success, balance_amount = remove_money(member.id, amount, source_type="discord_admin_remove", admin_id=ctx.author.id, admin_name=str(ctx.author), details=f"Discord admin remove money by {ctx.author}")

    if not success:
        await ctx.send("❌ رصيد العضو ما يكفي للسحب.")
        return

    embed = discord.Embed(title="✅ Admin Economy", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
    embed.description = f"تم سحب **{amount:,} {nm_coin_name()}** من {member.mention}."
    embed.add_field(name="رصيده الآن", value=f"**{balance_amount:,}** {nm_coin_name()}", inline=False)
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

    set_balance(member.id, 0, source_type="discord_reset", admin_id=ctx.author.id, admin_name=str(ctx.author), details=f"Discord admin reset balance by {ctx.author}")
    embed = discord.Embed(
        title="🧹 Balance Reset",
        description=f"تم تصفير رصيد {member.mention}.",
        color=COLOR_RED,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_BRAND} | Economy Admin")
    await ctx.send(embed=embed)


@bot.command(name="اعطاء_الكل", aliases=["giveall", "addallmoney"])
@commands.has_permissions(administrator=True)
async def admin_add_money_all(ctx, amount: int = None, confirm: str = None):
    if not await require_commands_channel(ctx):
        return

    if amount is None or amount <= 0:
        await ctx.send("استخدم: `!اعطاء_الكل 1000 CONFIRM`")
        return

    if str(confirm or "").lower() not in {"confirm", "تأكيد", "تاكيد"}:
        embed = discord.Embed(
            title="⚠️ تأكيد مطلوب",
            description="هذا الأمر بيعطي كل أعضاء السيرفر فلوس. للتأكيد اكتب:\n`!اعطاء_الكل المبلغ CONFIRM`",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} | Bulk Economy")
        await ctx.send(embed=embed)
        return

    result = await bulk_add_money_to_all(ctx.guild, amount, source_type="discord_bulk_add", admin_id=ctx.author.id, admin_name=str(ctx.author))
    embed = discord.Embed(
        title="🌍 تم إعطاء الكل فلوس",
        description=f"تم إعطاء **{amount:,} {nm_coin_name()}** لكل عضو غير بوت.",
        color=COLOR_GREEN,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👥 عدد الأعضاء", value=f"`{result['count']:,}`", inline=True)
    embed.add_field(name="💰 إجمالي المبلغ المضاف", value=coin_line(result['total_added']), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Bulk Economy")
    await ctx.send(embed=embed)
    await send_log(ctx.guild, "🌍 Bulk Economy Add", f"**By:** {ctx.author.mention}\n**Amount each:** `{amount:,}` {nm_coin_name()}\n**Members:** `{result['count']:,}`\n**Total added:** `{result['total_added']:,}`", COLOR_GREEN, log_type="server")


@bot.command(name="سحب_من_الكل", aliases=["takeall", "removeallmoney"])
@commands.has_permissions(administrator=True)
async def admin_remove_money_all(ctx, amount: int = None, confirm: str = None):
    if not await require_commands_channel(ctx):
        return

    if amount is None or amount <= 0:
        await ctx.send("استخدم: `!سحب_من_الكل 1000 CONFIRM`")
        return

    if str(confirm or "").lower() not in {"confirm", "تأكيد", "تاكيد"}:
        embed = discord.Embed(
            title="⚠️ تأكيد مطلوب",
            description="هذا الأمر بيسحب فلوس من كل أعضاء السيرفر. إذا رصيد العضو أقل من المبلغ، يصير رصيده 0. للتأكيد اكتب:\n`!سحب_من_الكل المبلغ CONFIRM`",
            color=COLOR_ORANGE,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"{BOT_BRAND} | Bulk Economy")
        await ctx.send(embed=embed)
        return

    result = await bulk_remove_money_from_all(ctx.guild, amount, source_type="discord_bulk_remove", admin_id=ctx.author.id, admin_name=str(ctx.author))
    embed = discord.Embed(
        title="🌍 تم السحب من الكل",
        description=f"تم سحب حتى **{amount:,} {nm_coin_name()}** من كل عضو غير بوت.",
        color=COLOR_RED,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👥 عدد الأعضاء", value=f"`{result['count']:,}`", inline=True)
    embed.add_field(name="💸 إجمالي المبلغ المسحوب", value=coin_line(result['total_removed']), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Bulk Economy")
    await ctx.send(embed=embed)
    await send_log(ctx.guild, "🌍 Bulk Economy Remove", f"**By:** {ctx.author.mention}\n**Amount each:** `{amount:,}` {nm_coin_name()}\n**Members:** `{result['count']:,}`\n**Total removed:** `{result['total_removed']:,}`", COLOR_RED, log_type="server")





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
        title="🎴 Blackjack • NM Casino",
        description=status,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{member.display_name} • Blackjack Table", icon_url=member.display_avatar.url)
    embed.add_field(name="🎯 الرهان", value=coin_line(bet), inline=True)

    if change is not None:
        embed.add_field(name="💸 النتيجة", value=money_delta(change), inline=True)

    if balance is not None:
        embed.add_field(name="💼 الرصيد", value=coin_line(balance), inline=False)

    embed.add_field(
        name=f"🧍 يدك — {player_total}",
        value=hand_text(player_cards),
        inline=False
    )
    embed.add_field(
        name=f"🤵 الديلر — {dealer_value}",
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

@bot.command(name="اقتصاد", aliases=["شرح", "شرح_الاقتصاد", "economy", "guide"])
async def economy_guide_command(ctx):
    if not ctx.guild or ctx.guild.id != GUILD_ID:
        return

    if not await require_commands_channel(ctx):
        return

    await ctx.send(embed=build_economy_guide_embed(auto=False))


@bot.command(name="شرح_القمار", aliases=["قمار", "gambling", "gamblehelp"])
async def gambling_help(ctx):
    if not await require_gambling_channel(ctx):
        return

    embed = discord.Embed(
        title="🎰 Casino Guide",
        description=(
            f"القمار هنا بعملة البوت فقط: {ECONOMY_EMOJI} **{nm_coin_name()}**\n"
            "ما فيه حد أعلى للرهان، تدخل بأي مبلغ موجود في محفظتك.\n"
            f"الانتظار بين كل محاولة ومحاولة: **{GAMBLE_COOLDOWN_SECONDS} ثواني**."
        ),
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="🎲 Lucky Roll",
        value="`/حظ amount` أو `/luck amount` — 50% فوز / 50% خسارة",
        inline=False
    )
    embed.add_field(
        name="💎 Double Risk",
        value="`/دبل amount` أو `/double amount` — 45% فوز / 55% خسارة",
        inline=False
    )
    embed.add_field(
        name="🎰 Slot Machine",
        value="`/سلوت amount` أو `/slot amount` — 3 نفس بعض = x5، رمزين = x2",
        inline=False
    )
    embed.add_field(
        name="🪙 Coin Flip",
        value="`/وجه amount choice` أو `/flip amount choice` — choice: ملك/كتابة",
        inline=False
    )
    embed.add_field(
        name="🎴 Blackjack",
        value="`/بلاكجاك amount` أو `/blackjack amount` — ضد الديلر. Blackjack يدفع x1.5",
        inline=False
    )
    embed.add_field(
        name="💡 اختصارات المبلغ",
        value="`10k` = 10,000 • `1m` = 1,000,000 • مثال: `/حظ 25k`",
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
            "✅ **فوز نظيف** — دبل الرهان وصل لمحفظتك.",
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
            "❌ **خسارة** — الرهان راح للكازينو.",
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
            "💎 **دبل ناجح** — مخاطرة عالية وربحت.",
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
            "💥 **فشل الدبل** — المخاطرة ما ضبطت.",
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
        await ctx.send("استخدم: `/وجه amount choice` أو `/flip amount choice` — choice: ملك/كتابة")
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
            "✅ **اختيار صحيح** — الكوين جات على اختيارك.",
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
            "❌ **اختيار غلط** — الكوين عاندتك.",
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
    cleared_count = clear_warnings_for_user(
        member.id,
        cleared_by=f"{ctx.author} ({ctx.author.id})",
        clear_reason="Discord command resetwarnings"
    )

    await ctx.send(
        embed=discord.Embed(
            title="✅ تم التصفير",
            description=f"تم تصفير تحذيرات {member.mention} وحفظها في سجل الداشبورد.\n**العدد:** `{cleared_count}`",
            color=COLOR_GREEN
        )
    )

    await send_log(
        ctx.guild,
        "✅ تصفير تحذيرات",
        f"**بواسطة:** {ctx.author.mention}\n**العضو:** {member.mention}\n**عدد الإنذارات:** `{cleared_count}`\n**ملاحظة:** تم حفظها في Warning History.",
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
    embed.add_field(name="📊 اللفل", value="`/ترتيب`", inline=True)
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
            description="هذي أهم أوامر البوت الجديدة `/`، والأوامر القديمة `!` باقية مؤقتًا:",
            color=COLOR_GREY,
            timestamp=discord.utils.utcnow()
        )

        commands_embed.add_field(name="📁 اللوقات", value="`!انشاء`", inline=True)
        commands_embed.add_field(name="⚙️ الإعداد", value="`!اعداد`", inline=True)
        commands_embed.add_field(name="👤 معلومات", value="`!معلومات @user`", inline=True)
        commands_embed.add_field(name="🎮 اللعب", value="`!لعب Valorant 5`", inline=True)
        commands_embed.add_field(name="🎭 الرولات", value="`!رولات`", inline=True)
        commands_embed.add_field(name="📩 الخاص", value="`!dmtest`\n`!dmrole`\n`!dmall`", inline=True)
        commands_embed.add_field(name="📊 اللفل", value="`!لفلي`\n`/ترتيب`", inline=True)

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


# =========================
# SHOP / LOOTBOX / EVENTS COMMANDS
# =========================

async def require_shop_channel(ctx):
    if ctx.channel.id == SHOP_CHANNEL_ID:
        return True
    embed = discord.Embed(
        title="🛒 الروم الغلط",
        description=f"أوامر المتجر تشتغل هنا: <#{SHOP_CHANNEL_ID}>",
        color=COLOR_ORANGE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_BRAND} | Shop")
    await ctx.send(embed=embed, delete_after=8)
    return False


async def require_events_channel(ctx):
    if ctx.channel.id == EVENTS_CHANNEL_ID:
        return True
    embed = discord.Embed(
        title="🎉 الروم الغلط",
        description=f"أوامر الفعاليات تشتغل هنا: <#{EVENTS_CHANNEL_ID}>",
        color=COLOR_ORANGE,
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_BRAND} | Events")
    await ctx.send(embed=embed, delete_after=8)
    return False


def build_shop_embed(member=None):
    embed = discord.Embed(
        title="🛒 متجر السيرفر",
        description="اشترِ مزايا باستخدام عملة السيرفر. كل شيء قابل للتغيير من الداشبورد.",
        color=COLOR_PURPLE,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(
        name="💎 VIP",
        value=(
            f"السعر: {coin_line(SHOP_VIP_PRICE)}\n"
            f"المدة: **{SHOP_VIP_DAYS} أيام**\n"
            f"الأمر: `/شراء vip`\n"
            f"الرول: <@&{VIP_ROLE_ID}>"
        ),
        inline=False
    )
    embed.add_field(
        name="🎁 صندوق الحظ",
        value=(
            f"السعر: {coin_line(LOOTBOX_PRICE)}\n"
            "جوائز عشوائية: Coins / VIP مؤقت / Winner Role مؤقت\n"
            "الأمر: `/صندوق` أو `/شراء صندوق`"
        ),
        inline=False
    )
    if member:
        embed.set_author(name=f"{member.display_name} • Wallet", icon_url=member.display_avatar.url)
        embed.add_field(name="💼 رصيدك", value=coin_line(get_balance(member.id)), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Customizable Shop")
    return embed


@bot.command(name="متجر", aliases=["shop", "market"])
async def shop_command(ctx):
    if not SHOP_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 المتجر مقفل", description="الإدارة قفلت المتجر مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_shop_channel(ctx):
        return
    await ctx.send(embed=build_market_embed(ctx.author), view=MarketView())


@bot.command(name="شراء", aliases=["buy"])
async def buy_command(ctx, item: str = None):
    if not SHOP_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 المتجر مقفل", description="الإدارة قفلت المتجر مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_shop_channel(ctx):
        return
    if not item:
        await ctx.send(embed=build_shop_embed(ctx.author))
        return

    item_key = str(item).strip().lower()
    if item_key in ["vip", "في اي بي", "فيب", "viprole"]:
        guild = ctx.guild
        vip_role, _ = await ensure_custom_roles(guild)
        if not vip_role:
            await ctx.send(embed=discord.Embed(title="❌ مشكلة رتبة VIP", description="ما قدرت ألقى أو أنشئ رتبة VIP. تأكد من صلاحية Manage Roles وترتيب رتبة البوت.", color=COLOR_RED))
            return
        ok, new_balance = remove_money(ctx.author.id, SHOP_VIP_PRICE)
        if not ok:
            await ctx.send(embed=discord.Embed(title="❌ رصيدك ما يكفي", description=f"تحتاج {coin_line(SHOP_VIP_PRICE)} لشراء VIP.\nرصيدك: {coin_line(get_balance(ctx.author.id))}", color=COLOR_RED))
            return
        try:
            await ctx.author.add_roles(vip_role, reason=f"{BOT_BRAND} shop VIP purchase")
            expires_at = int(time.time()) + int(SHOP_VIP_DAYS) * 86400
            add_timed_role_record(ctx.author.id, vip_role.id, expires_at, "Shop VIP purchase")
            record_shop_purchase(ctx.author.id, "vip", SHOP_VIP_PRICE)
            embed = discord.Embed(title="✅ تم شراء VIP", description=f"استمتعت بـ {vip_role.mention} لمدة **{SHOP_VIP_DAYS} أيام**.", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
            embed.add_field(name="💰 السعر", value=coin_line(SHOP_VIP_PRICE), inline=True)
            embed.add_field(name="💼 رصيدك الجديد", value=coin_line(new_balance), inline=True)
            embed.add_field(name="⏳ ينتهي", value=f"<t:{expires_at}:R>", inline=False)
            embed.set_footer(text=f"{BOT_BRAND} | Shop")
            await ctx.send(embed=embed)
        except Exception as e:
            add_money(ctx.author.id, SHOP_VIP_PRICE)
            await ctx.send(embed=discord.Embed(title="❌ فشل إعطاء الرتبة", description=f"رجعت لك المبلغ. السبب: `{clean_text(str(e), 300)}`", color=COLOR_RED))
        return

    if item_key in ["صندوق", "lootbox", "box"]:
        await lootbox_command(ctx)
        return

    await ctx.send(embed=discord.Embed(title="❌ منتج غير معروف", description="استخدم `/متجر` عشان تشوف المنتجات.", color=COLOR_RED), delete_after=8)


@bot.command(name="صندوق", aliases=["lootbox", "box"])
async def lootbox_command(ctx):
    if not SHOP_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 الصناديق مقفلة", description="الإدارة قفلت المتجر مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_shop_channel(ctx):
        return

    now = time.time()
    last = lootbox_cooldowns.get(ctx.author.id, 0)
    if now - last < LOOTBOX_COOLDOWN_SECONDS:
        await ctx.send(embed=discord.Embed(title="⏳ انتظر شوي", description=f"باقي **{LOOTBOX_COOLDOWN_SECONDS - (now-last):.1f} ثانية** قبل تفتح صندوق ثاني.", color=COLOR_ORANGE), delete_after=5)
        return
    lootbox_cooldowns[ctx.author.id] = now

    ok, new_balance = remove_money(ctx.author.id, LOOTBOX_PRICE)
    if not ok:
        await ctx.send(embed=discord.Embed(title="❌ رصيدك ما يكفي", description=f"سعر الصندوق: {coin_line(LOOTBOX_PRICE)}\nرصيدك: {coin_line(get_balance(ctx.author.id))}", color=COLOR_RED))
        return

    # Weighted rewards: safe but exciting.
    rewards = [
        ("coins", int(LOOTBOX_PRICE * 0.25), 28, "Common"),
        ("coins", int(LOOTBOX_PRICE * 0.75), 24, "Uncommon"),
        ("coins", int(LOOTBOX_PRICE * 1.5), 20, "Rare"),
        ("coins", int(LOOTBOX_PRICE * 3), 12, "Epic"),
        ("vip_hours", 12, 8, "Epic VIP"),
        ("winner_hours", 6, 5, "Legendary Role"),
        ("coins", int(LOOTBOX_PRICE * 7), 3, "Mythic Jackpot"),
    ]
    pool = []
    for reward_type, value, weight, rarity in rewards:
        pool.extend([(reward_type, value, rarity)] * int(weight))
    reward_type, value, rarity = random.choice(pool)

    desc = ""
    color = COLOR_BLUE
    if reward_type == "coins":
        final_balance = add_money(ctx.author.id, int(value))
        profit = int(value) - int(LOOTBOX_PRICE)
        desc = f"ربحت {coin_line(value)} من الصندوق.\nصافي النتيجة: {money_delta(profit)}"
        color = COLOR_GREEN if profit >= 0 else COLOR_YELLOW
        record_lootbox(ctx.author.id, LOOTBOX_PRICE, "coins", value)
    elif reward_type == "vip_hours":
        vip_role, _ = await ensure_custom_roles(ctx.guild)
        if vip_role:
            await ctx.author.add_roles(vip_role, reason=f"{BOT_BRAND} lootbox VIP reward")
            expires_at = int(time.time()) + int(value) * 3600
            add_timed_role_record(ctx.author.id, vip_role.id, expires_at, "Lootbox VIP reward")
            desc = f"ربحت {vip_role.mention} لمدة **{value} ساعة**.\nينتهي: <t:{expires_at}:R>"
        else:
            refund = int(LOOTBOX_PRICE * 2)
            final_balance = add_money(ctx.author.id, refund)
            desc = f"كان مفروض تفوز VIP، لكن الرتبة غير جاهزة. عوضتك {coin_line(refund)}."
        color = COLOR_PURPLE
        record_lootbox(ctx.author.id, LOOTBOX_PRICE, "vip_hours", value)
    else:
        _, winner_role = await ensure_custom_roles(ctx.guild)
        if winner_role:
            await ctx.author.add_roles(winner_role, reason=f"{BOT_BRAND} lootbox winner role reward")
            expires_at = int(time.time()) + int(value) * 3600
            add_timed_role_record(ctx.author.id, winner_role.id, expires_at, "Lootbox Event Winner reward")
            desc = f"ربحت {winner_role.mention} لمدة **{value} ساعات**.\nينتهي: <t:{expires_at}:R>"
        else:
            refund = int(LOOTBOX_PRICE * 3)
            final_balance = add_money(ctx.author.id, refund)
            desc = f"كان مفروض تفوز Winner Role، لكن الرتبة غير جاهزة. عوضتك {coin_line(refund)}."
        color = COLOR_ORANGE
        record_lootbox(ctx.author.id, LOOTBOX_PRICE, "winner_hours", value)

    record_shop_purchase(ctx.author.id, "lootbox", LOOTBOX_PRICE)
    embed = discord.Embed(title=f"🎁 صندوق الحظ • {rarity}", description=desc, color=color, timestamp=discord.utils.utcnow())
    embed.set_author(name=f"{ctx.author.display_name} فتح صندوق", icon_url=ctx.author.display_avatar.url)
    embed.add_field(name="💰 سعر الصندوق", value=coin_line(LOOTBOX_PRICE), inline=True)
    embed.add_field(name="💼 رصيدك الآن", value=coin_line(get_balance(ctx.author.id)), inline=True)
    embed.set_footer(text=f"{BOT_BRAND} | Lootbox")
    await ctx.send(embed=embed)



@bot.command(name="عقارات", aliases=["realestate", "real_estate", "properties"])
async def real_estate_command(ctx):
    if not SHOP_ENABLED or not REAL_ESTATE_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 العقارات مقفلة", description="الإدارة قفلت نظام العقارات مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_shop_channel(ctx):
        return
    await ctx.send(embed=build_real_estate_embed(ctx.author), view=RealEstateView())


@bot.command(name="عقاراتي", aliases=["myproperties", "assets"])
async def my_properties_command(ctx):
    if not await require_shop_channel(ctx):
        return
    await ctx.send(embed=build_user_assets_embed(ctx.author), view=MyAssetsView())


@bot.command(name="ايجار", aliases=["rent"])
async def rent_command(ctx):
    if not await require_shop_channel(ctx):
        return
    ok, total, remaining, count = collect_rent_for_user(ctx.author.id)
    if not ok:
        await ctx.send(embed=discord.Embed(title="⏳ الإيجار غير جاهز", description=f"عقاراتك: `{count}`\nأقرب إيجار بعد: **{format_seconds(remaining)}**", color=COLOR_ORANGE), delete_after=10)
        return
    embed = discord.Embed(title="💰 تم جمع الإيجار", description=f"جمعت من عقاراتك: {coin_line(total)}", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
    embed.add_field(name="رصيدك الآن", value=coin_line(get_balance(ctx.author.id)), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="سوق_العقارات", aliases=["propertymarket"])
async def property_market_command(ctx):
    if not await require_shop_channel(ctx):
        return
    await ctx.send(embed=build_property_market_embed(ctx.author), view=PropertyMarketView())


@bot.command(name="مزادات", aliases=["auctions"])
async def auctions_command(ctx):
    if not await require_shop_channel(ctx):
        return
    await settle_ended_auctions(ctx.guild)
    await ctx.send(embed=build_auction_embed(ctx.author), view=AuctionListView())


@bot.command(name="عرض_عقار", aliases=["list_property"])
async def list_property_command(ctx, property_id: int = None, price: str = None):
    if not await require_shop_channel(ctx):
        return
    if property_id is None or price is None:
        await ctx.send("استخدم: `!عرض_عقار رقم_العقار السعر` مثال: `!عرض_عقار 12 150k`", delete_after=10)
        return
    parsed_price = parse_bet_amount(price)
    if parsed_price is None:
        await ctx.send("❌ السعر غير صحيح.", delete_after=8)
        return
    ok, msg = set_property_for_sale(property_id, ctx.author.id, parsed_price)
    await ctx.send(embed=discord.Embed(title="🏷️ عرض عقار للبيع", description=msg, color=COLOR_GREEN if ok else COLOR_RED))


@bot.command(name="مزاد_عقار", aliases=["auction_property"])
async def auction_property_command(ctx, property_id: int = None, minutes: int = None, start_price: str = None):
    if not await require_shop_channel(ctx):
        return
    if property_id is None or minutes is None or start_price is None:
        await ctx.send("استخدم: `!مزاد_عقار رقم_العقار الدقائق سعر_البداية` مثال: `!مزاد_عقار 12 30 100k`", delete_after=10)
        return
    parsed_price = parse_bet_amount(start_price)
    if parsed_price is None:
        await ctx.send("❌ سعر البداية غير صحيح.", delete_after=8)
        return
    ok, msg, auction_id = create_property_auction(ctx.author.id, property_id, minutes, parsed_price)
    if not ok:
        await ctx.send(embed=discord.Embed(title="❌ فشل فتح المزاد", description=msg, color=COLOR_RED))
        return
    embed = discord.Embed(title="🔨 مزاد عقار جديد", description=f"فتح {ctx.author.mention} مزاد على العقار `#{property_id}`.\nسعر البداية: {coin_line(parsed_price)}\nينتهي: <t:{int(time.time()) + int(minutes)*60}:R>", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
    channel = await get_channel_by_id(ctx.guild, EVENTS_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed, view=AuctionListView())
    await ctx.send("✅ تم فتح المزاد.", delete_after=6)


@bot.command(name="ملاك", aliases=["landlords"])
async def landlords_command(ctx):
    if not await require_shop_channel(ctx):
        return
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT owner_id, COUNT(*) as c
            FROM real_estate_properties
            WHERE owner_id > 0
            GROUP BY owner_id
            ORDER BY c DESC
            LIMIT 10
        """)
        rows = cur.fetchall()
        conn.close()
    except:
        rows = []
    embed = discord.Embed(title="🏙️ أكبر ملاك العقارات", color=COLOR_BLUE, timestamp=discord.utils.utcnow())
    if not rows:
        embed.description = "ما فيه ملاك عقارات حتى الآن."
    else:
        embed.description = "\n".join([f"`{i}.` <@{uid}> — **{count}** عقار" for i, (uid, count) in enumerate(rows, 1)])
    await ctx.send(embed=embed)


@bot.command(name="فعاليات", aliases=["events"])
async def events_list_command(ctx):
    if not EVENTS_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 الفعاليات مقفلة", description="الإدارة قفلت نظام الفعاليات مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_events_channel(ctx):
        return
    events = get_active_events(10)
    embed = discord.Embed(title="🎉 الفعاليات الحالية", color=COLOR_PURPLE, timestamp=discord.utils.utcnow())
    if not events:
        embed.description = "ما فيه فعاليات شغالة حاليًا."
    else:
        for event_id, event_key, title, prize, starts_at, ends_at, created_by, status in events:
            embed.add_field(name=f"#{event_id} • {title}", value=f"الجائزة: {coin_line(prize)}\nتنتهي: <t:{int(ends_at)}:R>", inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Events")
    await ctx.send(embed=embed)


@bot.command(name="فعالية", aliases=["event"])
@commands.has_permissions(manage_guild=True)
async def event_start_command(ctx, minutes: int = None, prize: str = None, *, title="Casino Night"):
    if not EVENTS_ENABLED:
        await ctx.send(embed=discord.Embed(title="🔒 الفعاليات مقفلة", description="الإدارة قفلت نظام الفعاليات مؤقتًا.", color=COLOR_RED), delete_after=8)
        return
    if not await require_events_channel(ctx):
        return
    minutes = minutes or DEFAULT_EVENT_DURATION_MINUTES
    prize_amount = parse_bet_amount(prize) if prize else DEFAULT_EVENT_PRIZE
    if not prize_amount or prize_amount < 0:
        prize_amount = DEFAULT_EVENT_PRIZE
    now = int(time.time())
    ends = now + int(minutes) * 60
    event_id = create_event_record("manual", title, prize_amount, now, ends, ctx.author.id)
    embed = discord.Embed(title=f"🎉 {title}", description="فعالية جديدة بدأت!", color=COLOR_PURPLE, timestamp=discord.utils.utcnow())
    embed.add_field(name="🏆 الجائزة", value=coin_line(prize_amount), inline=True)
    embed.add_field(name="⏳ المدة", value=f"{minutes} دقيقة", inline=True)
    embed.add_field(name="📅 تنتهي", value=f"<t:{ends}:R>", inline=False)
    embed.set_footer(text=f"{BOT_BRAND} | Event #{event_id}")
    await ctx.send(embed=embed)
    announcement_channel = await get_channel_by_id(ctx.guild, BOT_ANNOUNCEMENTS_CHANNEL_ID)
    if announcement_channel and announcement_channel.id != ctx.channel.id:
        await announcement_channel.send(embed=embed)




# =========================
# SLASH COMMANDS / PUBLIC BOT PHASE 1
# Prefix commands stay available for the main guild, but Global V3 slash commands are now the public multi-server layer.
# =========================

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000) if bot and getattr(bot, "latency", None) is not None else 0
    await interaction.response.send_message(f"🏓 Pong • `{latency}ms`", ephemeral=True)


@bot.tree.command(name="balance", description="Show your wallet balance")
@app_commands.describe(member="Optional member to check")
async def slash_balance(interaction: discord.Interaction, member: discord.Member = None):
    if not await v3_require_commands_interaction(interaction):
        return
    target = member or interaction.user
    await interaction.response.send_message(embed=v3_wallet_embed(interaction.guild.id, target))


@bot.tree.command(name="رصيدي", description="عرض رصيدك أو رصيد عضو")
@app_commands.describe(member="عضو اختياري")
async def slash_balance_ar(interaction: discord.Interaction, member: discord.Member = None):
    if not await v3_require_commands_interaction(interaction):
        return
    await interaction.response.send_message(embed=v3_wallet_embed(interaction.guild.id, member or interaction.user))





# =========================
# NM AUTO RESTORE BUNDLED MEMORY
# Put nm_system.db/json files next to main.py once. On startup this copies the best non-empty data into /data automatically.
# =========================

def nm_auto_restore_score(path):
    try:
        p = Path(path)
        if not p.exists():
            return 0
        if p.suffix.lower() == ".db":
            try:
                conn = sqlite3.connect(str(p))
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check")
                integrity = str(cur.fetchone()[0] or "")
                if integrity.lower() != "ok":
                    # Damaged DB still may have readable rows, but give it lower priority.
                    penalty = 100000
                else:
                    penalty = 0
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                score = len(tables)
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        score += int(cur.fetchone()[0] or 0)
                    except Exception:
                        pass
                conn.close()
                return max(0, score - penalty)
            except Exception:
                return 0
        if p.suffix.lower() == ".json":
            try:
                import json
                raw = p.read_text(encoding="utf-8")
                if not raw.strip():
                    return 0
                data = json.loads(raw)
                if isinstance(data, dict):
                    return len(data)
                if isinstance(data, list):
                    return len(data)
                return 1
            except Exception:
                return p.stat().st_size
        return p.stat().st_size
    except Exception:
        return 0


def nm_auto_restore_bundled_memory(reason="startup"):
    try:
        data_dir = Path(globals().get("NM_DATA_DIR", "/data"))
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            data_dir = Path(".")

        files = [
            "nm_system.db",
            "warnings.json",
            "log_channels.json",
            "dashboard_settings.json",
            "protection_settings.json",
            "guild_settings.json",
            "money_audit.json",
        ]

        changed = []
        for filename in files:
            bundled = Path(filename)
            target = data_dir / filename

            bundled_score = nm_auto_restore_score(bundled)
            target_score = nm_auto_restore_score(target)

            # Restore if /data is empty/weaker. Never replace useful /data with empty bundled file.
            if bundled.exists() and bundled_score > 0 and bundled_score > target_score:
                shutil.copy2(bundled, target)
                changed.append(f"{filename}: bundled({bundled_score}) -> data({target_score})")

            # Mirror data back to local for memory-backup systems if local is empty.
            elif target.exists() and target_score > 0 and bundled_score == 0:
                shutil.copy2(target, bundled)
                changed.append(f"{filename}: data({target_score}) -> bundled/local({bundled_score})")

        if changed:
            print("✅ NM AUTO RESTORE applied:", "; ".join(changed))
        else:
            print(f"✅ NM AUTO RESTORE checked: no changes needed ({reason})")
    except Exception as e:
        print(f"❌ NM AUTO RESTORE failed: {e}")


# =========================
# NM MONEY DUPLICATION KILL SWITCH + PERSISTENT REWARD LOCKS
# يمنع تكرار الراتب/فلوس الرسائل بعد كل Redeploy
# =========================

nm_auto_restore_bundled_memory("module import")

def nm_reward_lock_table():
    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nm_reward_locks (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reward_key TEXT NOT NULL,
                last_ts INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id, reward_key)
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"NM reward lock table error: {e}")

def nm_reward_check_and_mark(guild_id, user_id, reward_key, cooldown_seconds):
    """Atomic persistent cooldown. Survives Railway redeploy."""
    nm_reward_lock_table()
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    reward_key = str(reward_key or "reward")
    now = int(time.time())
    cooldown_seconds = int(cooldown_seconds or 0)

    try:
        conn = db_connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO nm_reward_locks (guild_id, user_id, reward_key, last_ts)
            VALUES (?, ?, ?, 0)
        """, (guild_id, user_id, reward_key))
        cur.execute("""
            SELECT last_ts FROM nm_reward_locks
            WHERE guild_id = ? AND user_id = ? AND reward_key = ?
        """, (guild_id, user_id, reward_key))
        row = cur.fetchone()
        last_ts = int(row[0] or 0) if row else 0

        if now - last_ts < cooldown_seconds:
            conn.commit()
            conn.close()
            return False, cooldown_seconds - (now - last_ts)

        cur.execute("""
            UPDATE nm_reward_locks
            SET last_ts = ?
            WHERE guild_id = ? AND user_id = ? AND reward_key = ?
        """, (now, guild_id, user_id, reward_key))
        conn.commit()
        conn.close()
        return True, 0
    except Exception as e:
        print(f"NM reward lock check error: {e}")
        return False, cooldown_seconds

def nm_get_level_safe(guild_id, user_id):
    try:
        if "v3_get_level_data" in globals():
            xp, level = v3_get_level_data(guild_id, user_id)
            return int(level or 1)
    except Exception:
        pass
    try:
        level, xp = nm_legacy_level(guild_id, user_id)
        return int(level or 1)
    except Exception:
        return 1

def nm_salary_safe(guild_id, user_id, level=None):
    guild_id = int(guild_id or 0)
    user_id = int(user_id or 0)
    level = int(level or nm_get_level_safe(guild_id, user_id) or 1)
    cooldown = int(globals().get("HOURLY_REWARD_COOLDOWN_SECONDS", 3600))
    reward = int(globals().get("DAILY_REWARD_BASE", 250)) + (level * 25)

    allowed, remaining = nm_reward_check_and_mark(guild_id, user_id, "salary", cooldown)
    if not allowed:
        try:
            bal = v3_get_balance(guild_id, user_id)
        except Exception:
            bal = nm_legacy_balance(guild_id, user_id) if "nm_legacy_balance" in globals() else 0
        return False, remaining, bal, 0

    try:
        balance = v3_add_money(guild_id, user_id, reward, source_type="safe_salary", details="Persistent locked salary")
    except Exception:
        try:
            nm_legacy_add_money(guild_id, user_id, reward)
            balance = nm_legacy_balance(guild_id, user_id)
        except Exception:
            balance = 0

    try:
        money_audit_record(user_id=user_id, amount=reward, new_balance=balance, source_type="safe_salary", details=f"Guild {guild_id} | Persistent locked salary")
    except Exception:
        pass

    try:
        nm_dashboard_persist_now("salary paid with persistent lock")
    except Exception:
        pass

    return True, 0, balance, reward

# Override V3 salary completely so slash salary cannot pay again after redeploy.
def v3_claim_salary(guild_id, user_id, level):
    return nm_salary_safe(guild_id, user_id, level)

def nm_message_coin_allowed(guild_id, user_id):
    cooldown = int(globals().get("MESSAGE_COIN_COOLDOWN", 300))
    return nm_reward_check_and_mark(guild_id, user_id, "message_coin", cooldown)[0]

def nm_level_bonus_allowed(guild_id, user_id, level):
    return nm_reward_check_and_mark(guild_id, user_id, f"level_bonus_{int(level or 0)}", 999999999)[0]


@bot.tree.command(name="salary", description="Claim your salary")
async def slash_salary(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    xp, level = v3_get_level_data(interaction.guild.id, interaction.user.id)
    success, remaining, balance_amount, reward = v3_claim_salary(interaction.guild.id, interaction.user.id, level)
    if not success:
        embed = discord.Embed(title="⏳ الراتب غير جاهز", description=f"راتبك القادم بعد **{format_seconds(remaining)}**.", color=COLOR_ORANGE, timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{interaction.user.display_name} • Salary", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="💼 محفظتك الآن", value=coin_line(balance_amount), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    embed = discord.Embed(title="💸 Salary Claimed", description=f"تم إيداع راتبك: {coin_line(reward)}", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
    embed.set_author(name=f"{interaction.user.display_name} • Salary", icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="💼 رصيدك الجديد", value=coin_line(balance_amount), inline=False)
    embed.set_footer(text=f"{BOT_BRAND} • Global V3")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="راتب", description="استلام الراتب")
async def slash_salary_ar(interaction: discord.Interaction):
    await slash_salary.callback(interaction)


@bot.tree.command(name="transfer", description="Transfer coins to another member")
@app_commands.describe(member="Member to receive coins", amount="Amount to transfer")
async def slash_transfer(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not await v3_require_commands_interaction(interaction):
        return
    if member.bot or member.id == interaction.user.id:
        await interaction.response.send_message("❌ اختر عضو صحيح غير نفسك وغير بوت.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("❌ المبلغ لازم يكون أكبر من صفر.", ephemeral=True)
        return
    ok, sender_balance = v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_transfer_out", details=f"Transfer to {member.id}")
    if not ok:
        await interaction.response.send_message(f"❌ رصيدك ما يكفي. رصيدك: **{sender_balance:,}**", ephemeral=True)
        return
    receiver_balance = v3_add_money(interaction.guild.id, member.id, amount, source_type="v3_transfer_in", details=f"Transfer from {interaction.user.id}")
    embed = discord.Embed(title="🔁 Transfer Complete", description=f"{interaction.user.mention} حول {coin_line(amount)} إلى {member.mention}", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
    embed.add_field(name="رصيدك", value=coin_line(sender_balance), inline=True)
    embed.add_field(name="رصيد المستلم", value=coin_line(receiver_balance), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="تحويل", description="تحويل فلوس لعضو")
@app_commands.describe(member="العضو", amount="المبلغ")
async def slash_transfer_ar(interaction: discord.Interaction, member: discord.Member, amount: int):
    await slash_transfer.callback(interaction, member, amount)


@bot.tree.command(name="top", description="Show top richest members")
async def slash_top(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    rows = v3_get_top_money(interaction.guild.id, 10)
    if not rows:
        await interaction.response.send_message("ما فيه بيانات اقتصاد للحين.", ephemeral=True)
        return
    text = ""
    for index, (user_id, balance_amount) in enumerate(rows, start=1):
        text += f"`{index}.` <@{user_id}> — **{int(balance_amount):,}** {nm_coin_name()}\n"
    embed = discord.Embed(title=f"{ECONOMY_EMOJI} Richest Members", description=text[:3900], color=COLOR_YELLOW, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"{BOT_BRAND} • Global V3")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="اغنى", description="عرض أغنى أعضاء السيرفر")
async def slash_top_ar(interaction: discord.Interaction):
    await slash_top.callback(interaction)


@bot.tree.command(name="rank", description="Show your level and XP")
@app_commands.describe(member="Optional member to check")
async def slash_rank(interaction: discord.Interaction, member: discord.Member = None):
    if not await v3_require_commands_interaction(interaction):
        return
    target = member or interaction.user
    xp, level = v3_get_level_data(interaction.guild.id, target.id)
    needed = level * 100
    progress = xp_progress_bar(xp, needed, 14)
    embed = discord.Embed(title="📊 Level Profile", description=f"{target.mention}\n`{progress}` **{xp:,}/{needed:,} XP**", color=COLOR_BLUE, timestamp=discord.utils.utcnow())
    embed.set_author(name=f"{target.display_name} • Level {level}", icon_url=target.display_avatar.url)
    embed.add_field(name="Level", value=f"**{level}**", inline=True)
    embed.add_field(name="XP", value=f"**{xp:,}/{needed:,}**", inline=True)
    embed.set_footer(text=f"{BOT_BRAND} • Global V3 Levels")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="لفلي", description="عرض لفلك و XP")
@app_commands.describe(member="عضو اختياري")
async def slash_rank_ar(interaction: discord.Interaction, member: discord.Member = None):
    await slash_rank.callback(interaction, member)


@bot.tree.command(name="levels", description="Show top level members")
async def slash_levels(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    rows = v3_get_top_levels(interaction.guild.id, 10)
    if not rows:
        await interaction.response.send_message("ما فيه بيانات لفل للحين.", ephemeral=True)
        return
    text = ""
    for i, (user_id, xp, level) in enumerate(rows, start=1):
        text += f"`{i}.` <@{user_id}> — **Lv.{int(level)}** | XP `{int(xp):,}`\n"
    embed = discord.Embed(title="🏆 Level Leaderboard", description=text[:3900], color=COLOR_BLUE, timestamp=discord.utils.utcnow())
    embed.set_footer(text=f"{BOT_BRAND} • Global V3")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ترتيب", description="ترتيب اللفلات")
async def slash_levels_ar(interaction: discord.Interaction):
    await slash_levels.callback(interaction)


async def v3_gamble_check(interaction, amount):
    if not await v3_require_gambling_interaction(interaction):
        return None
    amount = int(amount or 0)
    if amount <= 0:
        await interaction.response.send_message("❌ مبلغ الرهان لازم يكون أكبر من صفر.", ephemeral=True)
        return None
    ok, remaining = can_gamble_now(interaction.user.id)
    if not ok:
        await interaction.response.send_message(f"⏳ انتظر **{remaining:.1f} ثانية** قبل محاولة القمار التالية.", ephemeral=True)
        return None
    balance_before = v3_get_balance(interaction.guild.id, interaction.user.id)
    if balance_before < amount:
        await interaction.response.send_message(f"❌ رصيدك ما يكفي. رصيدك الحالي: **{balance_before:,}**", ephemeral=True)
        return None
    return amount


@bot.tree.command(name="luck", description="50/50 gamble using your bot coins")
@app_commands.describe(amount="Bet amount")
async def slash_luck(interaction: discord.Interaction, amount: int):
    amount = await v3_gamble_check(interaction, amount)
    if amount is None:
        return
    v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_bet", details="Lucky roll bet")
    win = random.random() < 0.50
    if win:
        payout = amount * 2
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, payout, source_type="v3_gamble_win", details="Lucky roll payout")
        embed = gambling_embed("🎲 Lucky Roll", "✅ **فوز نظيف** — دبل الرهان وصل لمحفظتك.", COLOR_GREEN, interaction.user, amount, result_amount=amount, balance=balance_after, details="Chance: **50%** • Payout: **x2**", game_name="Global V3 Lucky Roll")
    else:
        balance_after = v3_get_balance(interaction.guild.id, interaction.user.id)
        embed = gambling_embed("🎲 Lucky Roll", "❌ **خسارة** — الرهان راح للكازينو.", COLOR_RED, interaction.user, amount, result_amount=-amount, balance=balance_after, details="Chance: **50%**", game_name="Global V3 Lucky Roll")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="حظ", description="رهان حظ 50/50")
@app_commands.describe(amount="المبلغ")
async def slash_luck_ar(interaction: discord.Interaction, amount: int):
    await slash_luck.callback(interaction, amount)


@bot.tree.command(name="double", description="High risk double-or-nothing gamble")
@app_commands.describe(amount="Bet amount")
async def slash_double(interaction: discord.Interaction, amount: int):
    amount = await v3_gamble_check(interaction, amount)
    if amount is None:
        return
    v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_bet", details="Double bet")
    win = random.random() < 0.42
    if win:
        payout = amount * 2
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, payout, source_type="v3_gamble_win", details="Double payout")
        embed = gambling_embed("🔥 Double", "✅ فزت بالدبل.", COLOR_GREEN, interaction.user, amount, result_amount=amount, balance=balance_after, details="Chance: **42%** • Payout: **x2**", game_name="Global V3 Double")
    else:
        balance_after = v3_get_balance(interaction.guild.id, interaction.user.id)
        embed = gambling_embed("🔥 Double", "❌ خسرت الرهان.", COLOR_RED, interaction.user, amount, result_amount=-amount, balance=balance_after, details="Chance: **42%**", game_name="Global V3 Double")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="دبل", description="رهان دبل")
@app_commands.describe(amount="المبلغ")
async def slash_double_ar(interaction: discord.Interaction, amount: int):
    await slash_double.callback(interaction, amount)


@bot.tree.command(name="slot", description="Play slot machine")
@app_commands.describe(amount="Bet amount")
async def slash_slot(interaction: discord.Interaction, amount: int):
    amount = await v3_gamble_check(interaction, amount)
    if amount is None:
        return
    v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_bet", details="Slot bet")
    symbols = ["🍒", "🍋", "🔔", "💎", "7️⃣"]
    roll = [random.choice(symbols) for _ in range(3)]
    multiplier = 0
    if roll[0] == roll[1] == roll[2]:
        multiplier = 5 if roll[0] in ["💎", "7️⃣"] else 3
    elif len(set(roll)) == 2:
        multiplier = 1
    payout = amount * multiplier
    result_delta = -amount
    if payout > 0:
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, payout, source_type="v3_gamble_win", details="Slot payout")
        result_delta = payout - amount
        color = COLOR_GREEN if result_delta >= 0 else COLOR_YELLOW
        status = "✅ ربح" if result_delta > 0 else "↩️ رجع لك الرهان"
    else:
        balance_after = v3_get_balance(interaction.guild.id, interaction.user.id)
        color = COLOR_RED
        status = "❌ خسارة"
    embed = gambling_embed("🎰 Slot Machine", status + "\n" + slot_box(roll), color, interaction.user, amount, result_amount=result_delta, balance=balance_after, details=f"Multiplier: **x{multiplier}**", game_name="Global V3 Slots")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="سلوت", description="لعبة السلوت")
@app_commands.describe(amount="المبلغ")
async def slash_slot_ar(interaction: discord.Interaction, amount: int):
    await slash_slot.callback(interaction, amount)


@bot.tree.command(name="flip", description="Coin flip gamble")
@app_commands.describe(amount="Bet amount", choice="heads or tails")
async def slash_flip(interaction: discord.Interaction, amount: int, choice: str):
    amount = await v3_gamble_check(interaction, amount)
    if amount is None:
        return
    normalized = str(choice).lower().strip()
    heads_values = {"heads", "head", "ملك", "وجه"}
    tails_values = {"tails", "tail", "كتابة", "كتابه"}
    if normalized not in heads_values and normalized not in tails_values:
        await interaction.response.send_message("اكتب choice: `heads` أو `tails` أو `ملك` أو `كتابة`.", ephemeral=True)
        return
    picked_heads = normalized in heads_values
    result_heads = random.choice([True, False])
    v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_bet", details="Coin flip bet")
    won = picked_heads == result_heads
    result_text = "ملك" if result_heads else "كتابة"
    if won:
        payout = amount * 2
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, payout, source_type="v3_gamble_win", details="Coin flip payout")
        embed = gambling_embed("🪙 Coin Flip", f"✅ طلعت **{result_text}** وفزت.", COLOR_GREEN, interaction.user, amount, result_amount=amount, balance=balance_after, details="Chance: **50%**", game_name="Global V3 Coin Flip")
    else:
        balance_after = v3_get_balance(interaction.guild.id, interaction.user.id)
        embed = gambling_embed("🪙 Coin Flip", f"❌ طلعت **{result_text}** وخسرت.", COLOR_RED, interaction.user, amount, result_amount=-amount, balance=balance_after, details="Chance: **50%**", game_name="Global V3 Coin Flip")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="وجه", description="ملك أو كتابة")
@app_commands.describe(amount="المبلغ", choice="ملك أو كتابة")
async def slash_flip_ar(interaction: discord.Interaction, amount: int, choice: str):
    await slash_flip.callback(interaction, amount, choice)


@bot.tree.command(name="blackjack", description="Simple blackjack against the dealer")
@app_commands.describe(amount="Bet amount")
async def slash_blackjack(interaction: discord.Interaction, amount: int):
    amount = await v3_gamble_check(interaction, amount)
    if amount is None:
        return
    # Lightweight slash blackjack resolver. Button blackjack also exists on /بلاكجاك for the main guild.
    v3_remove_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_bet", details="Blackjack bet")
    player = random.randint(16, 21)
    dealer = random.randint(16, 21)
    if player > dealer:
        payout = amount * 2
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, payout, source_type="v3_gamble_win", details="Blackjack payout")
        color = COLOR_GREEN
        status = "✅ فزت على الديلر"
        delta = amount
    elif player == dealer:
        balance_after = v3_add_money(interaction.guild.id, interaction.user.id, amount, source_type="v3_gamble_push", details="Blackjack push refund")
        color = COLOR_ORANGE
        status = "↩️ تعادل ورجع رهانك"
        delta = 0
    else:
        balance_after = v3_get_balance(interaction.guild.id, interaction.user.id)
        color = COLOR_RED
        status = "❌ الديلر فاز"
        delta = -amount
    embed = gambling_embed("🃏 Blackjack", status, color, interaction.user, amount, result_amount=delta, balance=balance_after, details=f"يدك: **{player}** | الديلر: **{dealer}**", game_name="Global V3 Blackjack")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="بلاكجاك", description="بلاكجاك ضد الديلر")
@app_commands.describe(amount="المبلغ")
async def slash_blackjack_ar(interaction: discord.Interaction, amount: int):
    await slash_blackjack.callback(interaction, amount)


@bot.tree.command(name="shop", description="Show the server shop")
async def slash_shop(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    await interaction.response.send_message(embed=v3_shop_embed(interaction.guild.id, interaction.user))


@bot.tree.command(name="متجر", description="عرض المتجر")
async def slash_shop_ar(interaction: discord.Interaction):
    await slash_shop.callback(interaction)


@bot.tree.command(name="buy", description="Buy a shop item")
@app_commands.describe(item="vip or lootbox")
async def slash_buy(interaction: discord.Interaction, item: str):
    if not await v3_require_commands_interaction(interaction):
        return
    item_key = str(item or "").lower().strip()
    if item_key in ["lootbox", "box", "صندوق"]:
        await slash_lootbox.callback(interaction)
        return
    if item_key not in ["vip", "فيب", "viprole"]:
        await interaction.response.send_message("❌ منتج غير معروف. استخدم `/shop`.", ephemeral=True)
        return
    ok, new_balance = v3_remove_money(interaction.guild.id, interaction.user.id, SHOP_VIP_PRICE, source_type="v3_shop_vip", details="VIP purchase")
    if not ok:
        await interaction.response.send_message(f"❌ رصيدك ما يكفي. السعر: {coin_line(SHOP_VIP_PRICE)}", ephemeral=True)
        return
    try:
        vip_role, _ = await ensure_custom_roles(interaction.guild)
        if vip_role:
            await interaction.user.add_roles(vip_role, reason=f"{BOT_BRAND} Global V3 VIP purchase")
        expires_at = int(time.time()) + int(SHOP_VIP_DAYS) * 86400
        if vip_role:
            add_timed_role_record(interaction.user.id, vip_role.id, expires_at, "Global V3 VIP purchase")
        embed = discord.Embed(title="✅ VIP Purchased", description=f"اشتريت VIP لمدة **{SHOP_VIP_DAYS} أيام**.", color=COLOR_GREEN, timestamp=discord.utils.utcnow())
        embed.add_field(name="السعر", value=coin_line(SHOP_VIP_PRICE), inline=True)
        embed.add_field(name="رصيدك", value=coin_line(new_balance), inline=True)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        v3_add_money(interaction.guild.id, interaction.user.id, SHOP_VIP_PRICE, source_type="v3_shop_refund", details="VIP purchase refund")
        await interaction.response.send_message(f"❌ فشل إعطاء الرتبة وتم إرجاع المبلغ. السبب: `{clean_text(str(e), 250)}`", ephemeral=True)


@bot.tree.command(name="شراء", description="شراء منتج من المتجر")
@app_commands.describe(item="vip أو صندوق")
async def slash_buy_ar(interaction: discord.Interaction, item: str):
    await slash_buy.callback(interaction, item)


@bot.tree.command(name="lootbox", description="Open a lootbox")
async def slash_lootbox(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    now = time.time()
    last = lootbox_cooldowns.get(interaction.user.id, 0)
    if now - last < LOOTBOX_COOLDOWN_SECONDS:
        await interaction.response.send_message(f"⏳ باقي **{LOOTBOX_COOLDOWN_SECONDS - (now-last):.1f} ثانية** قبل صندوق ثاني.", ephemeral=True)
        return
    lootbox_cooldowns[interaction.user.id] = now
    ok, new_balance = v3_remove_money(interaction.guild.id, interaction.user.id, LOOTBOX_PRICE, source_type="v3_lootbox_cost", details="Lootbox cost")
    if not ok:
        await interaction.response.send_message(f"❌ رصيدك ما يكفي. سعر الصندوق: {coin_line(LOOTBOX_PRICE)}", ephemeral=True)
        return
    rewards = [("coins", int(LOOTBOX_PRICE * 0.25), 30, "Common"), ("coins", int(LOOTBOX_PRICE * 1.0), 30, "Uncommon"), ("coins", int(LOOTBOX_PRICE * 2.0), 20, "Rare"), ("coins", int(LOOTBOX_PRICE * 5.0), 8, "Epic"), ("nothing", 0, 12, "Empty")]
    pool = []
    for reward_type, value, weight, rarity in rewards:
        pool.extend([(reward_type, value, rarity)] * int(weight))
    reward_type, value, rarity = random.choice(pool)
    if reward_type == "coins" and value > 0:
        final_balance = v3_add_money(interaction.guild.id, interaction.user.id, value, source_type="v3_lootbox_reward", details="Lootbox coin reward")
        profit = value - LOOTBOX_PRICE
        desc = f"ربحت {coin_line(value)}.\nصافي النتيجة: {money_delta(profit)}"
        color = COLOR_GREEN if profit >= 0 else COLOR_YELLOW
    else:
        final_balance = v3_get_balance(interaction.guild.id, interaction.user.id)
        desc = "الصندوق طلع فاضي. حظ أوفر."
        color = COLOR_RED
    embed = discord.Embed(title=f"🎁 Lootbox • {rarity}", description=desc, color=color, timestamp=discord.utils.utcnow())
    embed.set_author(name=f"{interaction.user.display_name} فتح صندوق", icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="سعر الصندوق", value=coin_line(LOOTBOX_PRICE), inline=True)
    embed.add_field(name="رصيدك الآن", value=coin_line(final_balance), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="صندوق", description="فتح صندوق حظ")
async def slash_lootbox_ar(interaction: discord.Interaction):
    await slash_lootbox.callback(interaction)


@bot.tree.command(name="economy", description="Show the economy guide")
async def slash_economy_guide(interaction: discord.Interaction):
    if not await v3_require_commands_interaction(interaction):
        return
    await interaction.response.send_message(embed=build_economy_guide_embed(auto=False), ephemeral=False)


@bot.tree.command(name="شرح", description="شرح الاقتصاد والأوامر")
async def slash_economy_guide_ar(interaction: discord.Interaction):
    await slash_economy_guide.callback(interaction)



# =========================
# SLASH SETUP STATUS / GUILD SETUP ASSISTANT
# =========================

def setup_user_can_manage(member):
    """Who can use setup actions from /setup_status."""
    try:
        if not member:
            return False
        if int(member.id) in DASHBOARD_PRIVATE_OWNER_USER_IDS:
            return True
        perms = getattr(member, "guild_permissions", None)
        return bool(perms and (perms.administrator or perms.manage_guild or perms.manage_channels))
    except Exception:
        return False


def setup_channel_line(guild, channel_id, label, kind="text"):
    try:
        channel_id = int(channel_id or 0)
    except Exception:
        channel_id = 0

    if not channel_id:
        return f"❌ **{label}:** غير محدد\n> اضبطه من الداشبورد: **Guilds → Setup**"

    channel = guild.get_channel(channel_id)
    if not channel:
        return f"⚠️ **{label}:** محفوظ لكن الروم غير موجود\n> ID: `{channel_id}` — عدله من الداشبورد."

    return f"✅ **{label}:** {channel.mention}"


def setup_log_channels_status(guild, settings=None):
    settings = settings or get_guild_settings(guild.id)
    category_id = int(settings.get("logs_category_id") or 0)
    category = guild.get_channel(category_id) if category_id else None

    existing = []
    missing = []
    outside_category = []

    for log_key, channel_name in LOG_CHANNEL_NAMES.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            existing.append((log_key, channel_name, channel))
            if category and channel.category_id != category.id:
                outside_category.append((log_key, channel_name, channel))
        else:
            missing.append((log_key, channel_name))

    return {
        "category_id": category_id,
        "category": category,
        "existing": existing,
        "missing": missing,
        "outside_category": outside_category,
        "total": len(LOG_CHANNEL_NAMES),
    }


def build_setup_status_embed(guild):
    create_default_guild_settings(guild)
    settings = get_guild_settings(guild.id)
    logs = setup_log_channels_status(guild, settings)

    commands_line = setup_channel_line(guild, settings.get("commands_channel_id"), "Commands Channel")
    gambling_line = setup_channel_line(guild, settings.get("gambling_channel_id"), "Gambling Channel")

    if logs["category"]:
        category_line = f"✅ **Logs Category:** {logs['category'].mention}"
    elif logs["category_id"]:
        category_line = f"⚠️ **Logs Category:** محفوظ لكن الكاتقوري غير موجود\n> ID: `{logs['category_id']}` — عدله من الداشبورد."
    else:
        category_line = "❌ **Logs Category:** غير محدد\n> تقدر تضغط زر **Create / Repair Logs** أو تحدده من الداشبورد."

    existing_count = len(logs["existing"])
    missing_count = len(logs["missing"])
    outside_count = len(logs["outside_category"])

    if missing_count == 0 and outside_count == 0:
        log_rooms_line = f"✅ **Log Rooms:** `{existing_count}/{logs['total']}` جاهزة ومرتبة."
    elif missing_count == 0 and outside_count > 0:
        log_rooms_line = f"⚠️ **Log Rooms:** `{existing_count}/{logs['total']}` موجودة، لكن `{outside_count}` خارج الكاتقوري المحدد."
    else:
        log_rooms_line = f"❌ **Log Rooms:** `{existing_count}/{logs['total']}` موجودة — ناقص `{missing_count}`."

    missing_names = ", ".join([f"`#{name}`" for _, name in logs["missing"][:8]])
    if len(logs["missing"]) > 8:
        missing_names += f" +{len(logs['missing']) - 8} more"
    if not missing_names:
        missing_names = "لا يوجد"

    outside_names = ", ".join([f"`#{name}`" for _, name, _ in logs["outside_category"][:8]])
    if len(logs["outside_category"]) > 8:
        outside_names += f" +{len(logs['outside_category']) - 8} more"
    if not outside_names:
        outside_names = "لا يوجد"

    bot_member = guild.me or guild.get_member(bot.user.id)
    perms = None
    try:
        perms = bot_member.guild_permissions if bot_member else None
    except Exception:
        perms = None

    needed = {
        "Manage Channels": bool(perms and perms.manage_channels),
        "Send Messages": bool(perms and perms.send_messages),
        "Embed Links": bool(perms and perms.embed_links),
        "Read Message History": bool(perms and perms.read_message_history),
        "View Audit Log": bool(perms and perms.view_audit_log),
    }
    perms_text = "\n".join([f"{'✅' if ok else '❌'} {name}" for name, ok in needed.items()])

    setup_done = bool(settings.get("setup_done")) and settings.get("commands_channel_id") and settings.get("gambling_channel_id") and missing_count == 0
    color = COLOR_GREEN if setup_done else COLOR_ORANGE

    embed = discord.Embed(
        title="🧩 Server Setup Status",
        description=(
            f"تفاصيل إعداد **{guild.name}**.\n"
            "إذا الرومات موجودة لكن مو صحيحة، عدلها من الداشبورد: **Guilds → Setup**."
        ),
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="🏷️ Server", value=f"**{guild.name}**\n`{guild.id}`", inline=False)
    embed.add_field(name="📍 Main Channels", value=f"{commands_line}\n{gambling_line}", inline=False)
    embed.add_field(name="🧾 Logs Setup", value=f"{category_line}\n{log_rooms_line}", inline=False)
    embed.add_field(name="❌ Missing Log Rooms", value=missing_names, inline=False)
    embed.add_field(name="📦 Existing But Outside Category", value=outside_names, inline=False)
    embed.add_field(name="🔐 Bot Permissions", value=perms_text, inline=True)
    embed.add_field(
        name="✅ What the button does",
        value=(
            "**Create / Repair Logs** ينشئ الكاتقوري إذا ناقص، ينشئ رومات اللوق الناقصة، "
            "وينقل الرومات الموجودة للكاتقوري المحدد."
        ),
        inline=False
    )
    embed.set_footer(text=f"{BOT_BRAND} • Setup Assistant")
    return embed


async def create_or_repair_guild_log_channels(guild):
    """Create/repair the standard log category and log rooms for the current guild."""
    create_default_guild_settings(guild)
    settings = get_guild_settings(guild.id)

    category = guild.get_channel(int(settings.get("logs_category_id") or 0))
    created_category = False

    if not category or not isinstance(category, discord.CategoryChannel):
        category = discord.utils.get(guild.categories, name="NM System Logs")

    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, embed_links=True, read_message_history=True),
        }
        category = await guild.create_category(
            "NM System Logs",
            overwrites=overwrites,
            reason="NM System setup logs category"
        )
        created_category = True

    created = []
    found = []
    moved = []

    for log_key, channel_name in LOG_CHANNEL_NAMES.items():
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            found.append(channel_name)
            if channel.category_id != category.id:
                try:
                    await channel.edit(category=category, reason="NM System setup repair log channel category")
                    moved.append(channel_name)
                except Exception:
                    pass
        else:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, embed_links=True, read_message_history=True),
            }
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="NM System setup create log channel"
            )
            created.append(channel_name)

        # Keep the old single-guild JSON working for the main guild.
        if int(guild.id) == int(GUILD_ID):
            try:
                fresh_channel = discord.utils.get(guild.text_channels, name=channel_name)
                if fresh_channel:
                    LOG_CHANNEL_IDS[log_key] = fresh_channel.id
            except Exception:
                pass

    if int(guild.id) == int(GUILD_ID):
        save_log_channels()

    update_guild_settings_from_dashboard(
        guild.id,
        enabled=settings.get("enabled", True),
        commands_channel_id=settings.get("commands_channel_id", 0),
        gambling_channel_id=settings.get("gambling_channel_id", 0),
        logs_category_id=category.id,
        setup_done=bool(settings.get("commands_channel_id") and settings.get("gambling_channel_id"))
    )

    return {
        "category": category,
        "created_category": created_category,
        "created": created,
        "found": found,
        "moved": moved,
    }


class SetupStatusView(discord.ui.View):
    def __init__(self, guild_id, requester_id):
        super().__init__(timeout=300)
        self.guild_id = int(guild_id)
        self.requester_id = int(requester_id)

        if DASHBOARD_BASE_URL:
            self.add_item(discord.ui.Button(
                label="Open Dashboard Setup",
                emoji="⚙️",
                style=discord.ButtonStyle.link,
                url=f"{DASHBOARD_BASE_URL}/dashboard/guild/{self.guild_id}/setup"
            ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or int(interaction.guild.id) != self.guild_id:
            await interaction.response.send_message("❌ هذا الزر مو لهذا السيرفر.", ephemeral=True)
            return False
        if int(interaction.user.id) != self.requester_id and not setup_user_can_manage(interaction.user):
            await interaction.response.send_message("❌ تحتاج Manage Server / Administrator عشان تستخدم أزرار الإعداد.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Create / Repair Logs", emoji="🧱", style=discord.ButtonStyle.success)
    async def create_logs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not setup_user_can_manage(interaction.user):
            await interaction.response.send_message("❌ تحتاج Manage Server أو Administrator لإنشاء رومات اللوقات.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = await create_or_repair_guild_log_channels(interaction.guild)
            embed = build_setup_status_embed(interaction.guild)
            summary = (
                f"✅ تم تجهيز اللوقات.\n"
                f"Category: {result['category'].mention}\n"
                f"Created rooms: `{len(result['created'])}`\n"
                f"Moved rooms: `{len(result['moved'])}`\n"
                f"Already existed: `{len(result['found'])}`\n\n"
                "إذا تبي تغير مكان الرومات أو الكاتقوري، عدلها من الداشبورد: **Guilds → Setup**."
            )
            embed.add_field(name="🧱 Action Result", value=summary, inline=False)
            await interaction.followup.send(embed=embed, view=SetupStatusView(interaction.guild.id, interaction.user.id), ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ فشل إنشاء/إصلاح اللوقات: `{type(e).__name__}: {str(e)[:700]}`", ephemeral=True)

    @discord.ui.button(label="Refresh Status", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_setup_status_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=SetupStatusView(interaction.guild.id, interaction.user.id))

@bot.tree.command(name="setup_status", description="Show this server setup status")
async def slash_setup_status(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("❌ هذا الأمر يشتغل داخل السيرفر فقط.", ephemeral=True)
        return

    embed = build_setup_status_embed(interaction.guild)
    view = SetupStatusView(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Make slash command errors visible instead of Discord showing 'The application did not respond'."""
    try:
        original_error = getattr(error, "original", error)
        error_text = f"{type(original_error).__name__}: {str(original_error)[:900]}"
        print(f"Slash Command Error: {error_text}")

        message = (
            "❌ صار خطأ داخل أمر السلاش.\n"
            "انسخ آخر سطر من Railway Logs إذا تكرر الخطأ.\n"
            f"```txt\n{clean_text(error_text, 900)}\n```"
        )

        if not interaction.response.is_done():
            await interaction.response.send_message(message, ephemeral=True)
        else:
            await interaction.followup.send(message, ephemeral=True)
    except Exception as e:
        print(f"Slash error handler failed: {type(e).__name__}: {e}")


@bot.event
async def on_command_completion(ctx):
    try:
        if not ctx.guild or ctx.guild.id != GUILD_ID:
            return
        command_name = ctx.command.name if ctx.command else "unknown"
        cc_record_event(
            "command",
            user_id=ctx.author.id,
            user_name=str(ctx.author),
            channel_id=ctx.channel.id,
            channel_name=getattr(ctx.channel, "name", "unknown"),
            details=f"!{command_name}"
        )
    except Exception as e:
        print(f"Command Center command log error: {e}")


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




@bot.command(name="syncslash", aliases=["sync_slash", "تحديث_السلاش"])
async def sync_slash_commands_command(ctx):
    """Owner-only command to force slash command sync for the current guild."""
    if not ctx.guild:
        return

    if not is_dashboard_owner_user(ctx.author.id):
        await ctx.send("❌ هذا الأمر للـ Owner فقط.", delete_after=8)
        return

    try:
        global_synced = await bot.tree.sync()
        guild_obj = discord.Object(id=ctx.guild.id)
        bot.tree.clear_commands(guild=guild_obj)
        guild_synced = await bot.tree.sync(guild=guild_obj)
        await ctx.send(
            f"✅ تم تحديث أوامر / وتنظيف التكرار.\n"
            f"Global commands: `{len(global_synced)}`\n"
            f"Guild duplicate commands cleared: `{len(guild_synced)}`"
        )
    except Exception as e:
        await ctx.send(f"❌ فشل تحديث أوامر السلاش: `{type(e).__name__}: {str(e)[:300]}`")


# =========================
# NM SLASH SYNC SAFETY
# =========================
async def nm_sync_slash_commands():
    try:
        synced = await bot.tree.sync()
        print(f"✅ NM slash commands synced globally: {len(synced)}")
        return len(synced)
    except Exception as e:
        print(f"❌ NM slash sync failed: {e}")
        return 0

try:
    @bot.command(name="syncslash", aliases=["تحديث_السلاش"])
    async def nm_syncslash_command(ctx):
        count = await nm_sync_slash_commands()
        await ctx.reply(f"✅ Synced slash commands: `{count}`")
except Exception:
    pass



# =========================
# NM STABLE GUILD OPEN ROUTES
# These routes are intentionally placed late so specific routes like /setup win first.
# =========================

@app.route("/dashboard/guild/<int:guild_id>", endpoint="nm_stable_open_guild_root")
def nm_stable_open_guild_root(guild_id):
    dashboard_set_active_guild(int(guild_id))
    return redirect(f"/dashboard?guild_id={int(guild_id)}")


@app.route("/dashboard/guild/<int:guild_id>/<path:page>", endpoint="nm_stable_open_guild_page")
def nm_stable_open_guild_page(guild_id, page):
    dashboard_set_active_guild(int(guild_id))
    page = str(page or "").strip("/").lower()
    route_map = {
        "overview": "/dashboard",
        "setup": "/dashboard/guild-setup",
        "guild-setup": "/dashboard/guild-setup",
        "command-center": "/dashboard/command-center",
        "log-vault": "/dashboard/log-vault",
        "logs": "/dashboard/log-vault",
        "user-lookup": "/dashboard/user-lookup",
        "warnings": "/dashboard/warnings",
        "protection": "/dashboard/protection",
        "economy": "/dashboard/economy",
        "money-audit": "/dashboard/money-audit",
        "levels": "/dashboard/levels",
        "casino": "/dashboard/casino",
        "shop": "/dashboard/shop",
        "events": "/dashboard/events",
        "memory": "/dashboard/memory",
        "owner-console": "/dashboard/owner-console",
        "admin-access": "/dashboard/admin-access",
        "control": "/dashboard/control",
        "control-center": "/dashboard/control",
        "audit": "/dashboard/audit",
        "audit-center": "/dashboard/audit",
        "settings": "/dashboard/settings",
        "oauth-debug": "/dashboard/oauth-debug",
    }
    target = route_map.get(page, "/dashboard")
    return redirect(f"{target}?guild_id={int(guild_id)}")



# =========================
# NM LEGACY DATA RESCUE PATCH
# Old data may exist with guild_id = 0/NULL after switching to per-server mode.
# This patch shows legacy data when selected-guild data is empty and provides a migration route.
# =========================

def nm_rescue_selected_gid():
    try:
        return int(
            request.args.get("guild_id")
            or request.form.get("guild_id")
            or session.get("selected_guild_id")
            or session.get("dashboard_active_guild_id")
            or GUILD_ID
        )
    except Exception:
        return int(GUILD_ID)

def nm_rescue_ensure_guild_col(cur, table):
    try:
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if "guild_id" not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER DEFAULT 0")
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_guild_id ON {table}(guild_id)")
        except Exception:
            pass
    except Exception as e:
        print(f"NM rescue ensure guild col failed for {table}: {e}")

def nm_rescue_count(cur, table, guild_id):
    try:
        nm_rescue_ensure_guild_col(cur, table)
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE guild_id = ?", (int(guild_id),))
        selected = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE guild_id IS NULL OR guild_id = 0")
        legacy = int(cur.fetchone()[0] or 0)
        return selected, legacy
    except Exception:
        return 0, 0

def nm_rescue_sum(cur, table, column, guild_id):
    try:
        nm_rescue_ensure_guild_col(cur, table)
        cur.execute(f"SELECT COALESCE(SUM({column}), 0) FROM {table} WHERE guild_id = ?", (int(guild_id),))
        selected = int(cur.fetchone()[0] or 0)
        cur.execute(f"SELECT COALESCE(SUM({column}), 0) FROM {table} WHERE guild_id IS NULL OR guild_id = 0")
        legacy = int(cur.fetchone()[0] or 0)
        return selected, legacy
    except Exception:
        return 0, 0

def nm_rescue_effective_where(table, guild_id):
    """If selected guild has no rows but legacy has rows, read legacy rows instead of showing empty."""
    try:
        conn = db_connect()
        cur = conn.cursor()
        selected, legacy = nm_rescue_count(cur, table, guild_id)
        conn.commit()
        conn.close()
        if selected == 0 and legacy > 0:
            return "(guild_id IS NULL OR guild_id = 0)", []
        return "guild_id = ?", [int(guild_id)]
    except Exception:
        return "guild_id = ?", [int(guild_id)]

def dashboard_count_table(table):
    gid = nm_rescue_selected_gid()
    try:
        conn = db_connect()
        cur = conn.cursor()
        selected, legacy = nm_rescue_count(cur, table, gid)
        conn.commit()
        conn.close()
        return selected if selected > 0 else legacy
    except Exception:
        return 0

def dashboard_total_coins():
    gid = nm_rescue_selected_gid()
    try:
        conn = db_connect()
        cur = conn.cursor()
        selected, legacy = nm_rescue_sum(cur, "economy", "balance", gid)
        conn.commit()
        conn.close()
        return selected if selected > 0 else legacy
    except Exception:
        return 0

def dashboard_money_rows(limit=10):
    gid = nm_rescue_selected_gid()
    rows = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_rescue_ensure_guild_col(cur, "economy")
        where, params = nm_rescue_effective_where("economy", gid)
        cur.execute(f"SELECT user_id, balance FROM economy WHERE {where} ORDER BY balance DESC LIMIT ?", tuple(params + [int(limit)]))
        data = cur.fetchall()
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"NM rescue dashboard_money_rows error: {e}")
        data = []

    for i, (user_id, balance) in enumerate(data, start=1):
        try:
            name = dashboard_member_name(user_id)
        except Exception:
            name = f"User {user_id}"
        rows.append({"rank": i, "user_id": int(user_id), "name": name, "balance": int(balance or 0)})
    return rows

def dashboard_level_rows(limit=10):
    gid = nm_rescue_selected_gid()
    rows = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        nm_rescue_ensure_guild_col(cur, "levels")
        where, params = nm_rescue_effective_where("levels", gid)
        cur.execute(f"SELECT user_id, xp, level FROM levels WHERE {where} ORDER BY level DESC, xp DESC LIMIT ?", tuple(params + [int(limit)]))
        data = cur.fetchall()
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"NM rescue dashboard_level_rows error: {e}")
        data = []

    for i, (user_id, xp, level) in enumerate(data, start=1):
        try:
            name = dashboard_member_name(user_id)
        except Exception:
            name = f"User {user_id}"
        rows.append({"rank": i, "user_id": int(user_id), "name": name, "level": int(level or 1), "xp": int(xp or 0)})
    return rows

@app.route("/dashboard/rescue-legacy-data")
def nm_rescue_legacy_data_page():
    """Move old guild_id=0/NULL data to selected guild. Use only after selecting the correct server."""
    gid = nm_rescue_selected_gid()
    tables = [
        "economy",
        "levels",
        "warning_history",
        "dashboard_log_vault",
        "command_center_events",
        "money_audit",
        "real_estate_properties",
        "real_estate_auctions",
        "shop_purchases",
        "lootbox_history",
        "dashboard_audit",
    ]
    results = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        for table in tables:
            try:
                nm_rescue_ensure_guild_col(cur, table)
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE guild_id IS NULL OR guild_id = 0")
                before = int(cur.fetchone()[0] or 0)
                if before > 0:
                    cur.execute(f"UPDATE {table} SET guild_id = ? WHERE guild_id IS NULL OR guild_id = 0", (int(gid),))
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE guild_id = ?", (int(gid),))
                after = int(cur.fetchone()[0] or 0)
                results.append(f"{table}: moved legacy {before}, selected now {after}")
            except Exception as e:
                results.append(f"{table}: skipped ({type(e).__name__}: {str(e)[:120]})")
        conn.commit()
        conn.close()
        try:
            nm_dashboard_persist_now("legacy data rescued")
        except Exception:
            pass
    except Exception as e:
        results.append(f"FATAL: {type(e).__name__}: {e}")

    body = "<br>".join(dash_escape(x, 300) for x in results)
    return f"""
    <div style='font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px'>
      <h1>NM Legacy Data Rescue</h1>
      <p>Target guild: <b>{int(gid)}</b></p>
      <div style='line-height:1.8;background:#111a33;padding:20px;border-radius:12px'>{body}</div>
      <p style='margin-top:20px'>Now go back to dashboard and refresh.</p>
      <a style='color:#8b5cf6' href='/dashboard?guild_id={int(gid)}'>Back to Dashboard</a>
    </div>
    """

@app.route("/dashboard/rescue-status")
def nm_rescue_status_page():
    gid = nm_rescue_selected_gid()
    tables = ["economy", "levels", "warning_history", "dashboard_log_vault", "command_center_events", "money_audit"]
    lines = []
    try:
        conn = db_connect()
        cur = conn.cursor()
        for table in tables:
            selected, legacy = nm_rescue_count(cur, table, gid)
            lines.append(f"{table}: selected={selected}, legacy={legacy}")
        conn.close()
    except Exception as e:
        lines.append(f"error: {type(e).__name__}: {e}")
    body = "<br>".join(dash_escape(x, 300) for x in lines)
    return f"""
    <div style='font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px'>
      <h1>NM Rescue Status</h1>
      <p>Selected guild: <b>{int(gid)}</b></p>
      <div style='line-height:1.8;background:#111a33;padding:20px;border-radius:12px'>{body}</div>
      <p><a style='color:#8b5cf6' href='/dashboard/rescue-legacy-data?guild_id={int(gid)}'>Move legacy data to this guild</a></p>
      <p><a style='color:#8b5cf6' href='/dashboard?guild_id={int(gid)}'>Back</a></p>
    </div>
    """




@app.route("/dashboard/disable-auto-money")
def nm_disable_auto_money_route():
    try:
        globals()["MESSAGE_COIN_COOLDOWN"] = 999999999
        if "dashboard_settings" in globals():
            dashboard_settings["message_coin_rewards_enabled"] = False
            dashboard_settings["message_coin_cooldown"] = 999999999
            try:
                save_dashboard_settings()
            except Exception:
                pass
        try:
            nm_dashboard_persist_now("auto money disabled")
        except Exception:
            pass
    except Exception as e:
        return f"<h2>Error</h2><pre>{dash_escape(str(e), 1000)}</pre>"
    return "<h2>Auto message money disabled</h2><p>Salary still works with persistent cooldown.</p><a href='/dashboard'>Back</a>"




@app.route("/dashboard/force-restore-bundled-memory")
def nm_force_restore_bundled_memory_route():
    try:
        nm_auto_restore_bundled_memory("manual force")
        return "<h2>Bundled memory restore checked/applied.</h2><p>Refresh the dashboard.</p><a href='/dashboard'>Back</a>"
    except Exception as e:
        return f"<h2>Restore failed</h2><pre>{dash_escape(str(e), 1000)}</pre>"




# =========================
# NM DASHBOARD MEMORY UPLOAD
# Allows owner to upload memory files from dashboard and safely restore them into /data.
# =========================

NM_ALLOWED_MEMORY_UPLOADS = {
    "nm_system.db",
    "warnings.json",
    "log_channels.json",
    "dashboard_settings.json",
    "protection_settings.json",
    "guild_settings.json",
    "money_audit.json",
    "memory_report.txt",
}

def nm_memory_upload_score(path):
    try:
        p = Path(path)
        if not p.exists():
            return 0
        if p.suffix.lower() == ".db":
            try:
                conn = sqlite3.connect(str(p))
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check")
                integrity = str(cur.fetchone()[0] or "")
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                score = len(tables)
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        score += int(cur.fetchone()[0] or 0)
                    except Exception:
                        pass
                conn.close()
                if integrity.lower() != "ok":
                    # Damaged DB can still be used only if current data is empty, but rank it lower.
                    return max(1, score // 10)
                return score
            except Exception:
                return 0
        if p.suffix.lower() == ".json":
            try:
                import json
                raw = p.read_text(encoding="utf-8")
                if not raw.strip():
                    return 0
                data = json.loads(raw)
                if isinstance(data, dict):
                    return len(data)
                if isinstance(data, list):
                    return len(data)
                return 1
            except Exception:
                return p.stat().st_size
        return p.stat().st_size
    except Exception:
        return 0


def nm_safe_apply_memory_file(src_path, filename, force=False):
    filename = Path(filename).name
    if filename not in NM_ALLOWED_MEMORY_UPLOADS:
        return False, f"{filename}: blocked file name"

    try:
        data_dir = Path(globals().get("NM_DATA_DIR", "/data"))
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            data_dir = Path(".")

        local_target = Path(filename)
        data_target = data_dir / filename

        incoming_score = nm_memory_upload_score(src_path)
        local_score = nm_memory_upload_score(local_target)
        data_score = nm_memory_upload_score(data_target)
        best_existing = max(local_score, data_score)

        if incoming_score <= 0:
            return False, f"{filename}: rejected, empty or unreadable"

        if not force and incoming_score < best_existing:
            return False, f"{filename}: skipped, uploaded score {incoming_score} < existing score {best_existing}"

        shutil.copy2(src_path, data_target)
        shutil.copy2(src_path, local_target)
        return True, f"{filename}: restored, uploaded score {incoming_score}, old score {best_existing}"
    except Exception as e:
        return False, f"{filename}: failed {type(e).__name__}: {str(e)[:200]}"


def nm_extract_zip_memory_upload(zip_path, force=False):
    results = []
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="nm_memory_zip_"))
        with zipfile.ZipFile(zip_path, "r") as z:
            for member in z.namelist():
                name = Path(member).name
                if not name or name not in NM_ALLOWED_MEMORY_UPLOADS:
                    continue
                extracted = temp_dir / name
                extracted.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as src_f, open(extracted, "wb") as out_f:
                    shutil.copyfileobj(src_f, out_f)
                ok, msg = nm_safe_apply_memory_file(extracted, name, force=force)
                results.append(msg)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
    except Exception as e:
        results.append(f"zip failed: {type(e).__name__}: {str(e)[:200]}")
    return results


@app.route("/dashboard/memory-upload", methods=["GET", "POST"])
def nm_dashboard_memory_upload_page():
    try:
        # Simple owner/admin gate if helpers exist; don't lock owner out if session helper names differ.
        user_id = 0
        try:
            user_id = int((session.get("discord_user") or session.get("user") or {}).get("id") or session.get("user_id") or 0)
        except Exception:
            pass
        try:
            if "PRIVATE_OWNER_IDS" in globals() and PRIVATE_OWNER_IDS and user_id and user_id not in PRIVATE_OWNER_IDS:
                # allow normal dashboard access pages to handle auth elsewhere; only strict when we know owner IDs
                pass
        except Exception:
            pass

        if request.method == "POST":
            force = bool(request.form.get("force") == "1")
            results = []

            files = request.files.getlist("memory_files")
            if not files:
                results.append("No files uploaded.")

            temp_dir = Path(tempfile.mkdtemp(prefix="nm_memory_upload_"))
            for f in files:
                raw_name = Path(f.filename or "").name
                if not raw_name:
                    continue

                save_path = temp_dir / raw_name
                f.save(str(save_path))

                if raw_name.endswith(".zip"):
                    results.extend(nm_extract_zip_memory_upload(save_path, force=force))
                else:
                    ok, msg = nm_safe_apply_memory_file(save_path, raw_name, force=force)
                    results.append(msg)

            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

            try:
                if "nm_auto_restore_bundled_memory" in globals():
                    nm_auto_restore_bundled_memory("after dashboard upload")
            except Exception:
                pass
            try:
                if "nm_bridge_local_restore_to_data" in globals():
                    nm_bridge_local_restore_to_data("after dashboard upload")
            except Exception:
                pass
            try:
                if "nm_dashboard_persist_now" in globals():
                    nm_dashboard_persist_now("memory uploaded from dashboard")
            except Exception:
                pass

            result_html = "".join(f"<li>{dash_escape(str(r), 500)}</li>" for r in results)
            return f"""
            <div style="font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px">
              <h1>Memory Upload Result</h1>
              <ul style="line-height:1.8;background:#111a33;padding:20px;border-radius:12px">{result_html}</ul>
              <p>Restart/Redeploy after upload if the dashboard does not refresh immediately.</p>
              <a style="color:#8b5cf6" href="/dashboard">Back to Dashboard</a>
            </div>
            """

        allowed = ", ".join(sorted(NM_ALLOWED_MEMORY_UPLOADS))
        return f"""
        <div style="font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px">
          <h1>NM Memory Upload</h1>
          <p>Upload memory files or a zip bundle. The bot will safely copy stronger files into <code>/data</code>.</p>
          <p style="color:#9ca3af">Allowed: {dash_escape(allowed, 1000)}</p>
          <form method="POST" enctype="multipart/form-data" style="background:#111a33;padding:20px;border-radius:14px;max-width:760px">
            <input type="file" name="memory_files" multiple style="display:block;margin-bottom:16px;color:white">
            <label style="display:block;margin-bottom:16px">
              <input type="checkbox" name="force" value="1">
              Force overwrite even if current file looks stronger
            </label>
            <button style="background:#8b5cf6;color:white;border:0;border-radius:10px;padding:12px 18px;font-weight:800">Upload Memory</button>
          </form>
          <p><a style="color:#8b5cf6" href="/dashboard">Back</a></p>
        </div>
        """
    except Exception as e:
        return f"<h2>Memory upload error</h2><pre>{dash_escape(str(e), 1200)}</pre>"




# =========================
# NM SYSTEM V4 FULL POSTGRES PATCH
# PostgreSQL becomes the main persistent database.
# DATABASE_URL must exist in Railway variables.
# Requires: psycopg[binary]>=3.2.0
# =========================

NM_V4_POSTGRES_ENABLED = False
NM_PG_AUTO_MIGRATE_DONE = False
NM_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception as _e:
    psycopg = None
    dict_row = None
    print(f"⚠️ NM V4 Postgres disabled: psycopg import failed: {_e}")

NM_PG_SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS nm_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS guild_settings (guild_id BIGINT PRIMARY KEY, settings JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS guild_channels (guild_id BIGINT NOT NULL, channel_key TEXT NOT NULL, channel_id BIGINT NOT NULL DEFAULT 0, channel_name TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (guild_id, channel_key));
CREATE TABLE IF NOT EXISTS guild_protection_settings (guild_id BIGINT PRIMARY KEY, settings JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS economy (guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, balance BIGINT NOT NULL DEFAULT 0, admin_given BIGINT NOT NULL DEFAULT 0, earned_money BIGINT NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS levels (guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, xp BIGINT NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS salary_cooldowns (guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, last_claim BIGINT NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id));
CREATE TABLE IF NOT EXISTS reward_locks (guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, reward_key TEXT NOT NULL, last_ts BIGINT NOT NULL DEFAULT 0, PRIMARY KEY (guild_id, user_id, reward_key));
CREATE TABLE IF NOT EXISTS warnings (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, reason TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '', moderator_id BIGINT NOT NULL DEFAULT 0, moderator_name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), cleared_at TIMESTAMPTZ, cleared_by BIGINT NOT NULL DEFAULT 0, clear_reason TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_nm_warnings_guild_user ON warnings(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_nm_warnings_status ON warnings(guild_id, status);
CREATE TABLE IF NOT EXISTS log_vault (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL, log_type TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', color BIGINT NOT NULL DEFAULT 0, discord_channel_id BIGINT NOT NULL DEFAULT 0, discord_channel_name TEXT NOT NULL DEFAULT '', discord_message_id BIGINT NOT NULL DEFAULT 0, deleted_from_discord BOOLEAN NOT NULL DEFAULT FALSE, deleted_by_id BIGINT NOT NULL DEFAULT 0, deleted_by_name TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL DEFAULT 0, deleted_at BIGINT NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_nm_log_vault_guild_time ON log_vault(guild_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_nm_log_vault_channel ON log_vault(guild_id, discord_channel_id);
CREATE INDEX IF NOT EXISTS idx_nm_log_vault_type ON log_vault(guild_id, log_type);
CREATE TABLE IF NOT EXISTS command_center_events (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL, event_type TEXT NOT NULL DEFAULT '', user_id BIGINT NOT NULL DEFAULT 0, user_name TEXT NOT NULL DEFAULT '', channel_id BIGINT NOT NULL DEFAULT 0, channel_name TEXT NOT NULL DEFAULT '', amount BIGINT NOT NULL DEFAULT 0, details TEXT NOT NULL DEFAULT '', created_at BIGINT NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_nm_command_center_guild_time ON command_center_events(guild_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_nm_command_center_type ON command_center_events(guild_id, event_type);
CREATE TABLE IF NOT EXISTS money_audit (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL, user_id BIGINT NOT NULL, amount BIGINT NOT NULL DEFAULT 0, new_balance BIGINT NOT NULL DEFAULT 0, source_type TEXT NOT NULL DEFAULT '', details TEXT NOT NULL DEFAULT '', actor_id BIGINT NOT NULL DEFAULT 0, created_at BIGINT NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_nm_money_audit_guild_time ON money_audit(guild_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_nm_money_audit_user ON money_audit(guild_id, user_id);
CREATE TABLE IF NOT EXISTS dashboard_admin_access (guild_id BIGINT NOT NULL, target_type TEXT NOT NULL, target_id BIGINT NOT NULL, access_level TEXT NOT NULL DEFAULT 'admin', granted_by BIGINT NOT NULL DEFAULT 0, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (guild_id, target_type, target_id));
CREATE TABLE IF NOT EXISTS shop_purchases (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, user_id BIGINT NOT NULL DEFAULT 0, item_key TEXT NOT NULL DEFAULT '', price BIGINT NOT NULL DEFAULT 0, created_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS lootbox_history (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, user_id BIGINT NOT NULL DEFAULT 0, reward TEXT NOT NULL DEFAULT '', amount BIGINT NOT NULL DEFAULT 0, created_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS real_estate_properties (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, property_key TEXT NOT NULL DEFAULT '', owner_id BIGINT NOT NULL DEFAULT 0, data JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS real_estate_auctions (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, property_key TEXT NOT NULL DEFAULT '', data JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS timed_roles (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, user_id BIGINT NOT NULL DEFAULT 0, role_id BIGINT NOT NULL DEFAULT 0, expires_at BIGINT NOT NULL DEFAULT 0, data JSONB NOT NULL DEFAULT '{}'::jsonb);
CREATE TABLE IF NOT EXISTS giveaways (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, channel_id BIGINT NOT NULL DEFAULT 0, message_id BIGINT NOT NULL DEFAULT 0, data JSONB NOT NULL DEFAULT '{}'::jsonb, created_at BIGINT NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS suggestions (id BIGSERIAL PRIMARY KEY, guild_id BIGINT NOT NULL DEFAULT 0, user_id BIGINT NOT NULL DEFAULT 0, content TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at BIGINT NOT NULL DEFAULT 0);
'''

def nm_pg_available():
    return bool(psycopg and NM_DATABASE_URL)

def nm_pg_conn():
    return psycopg.connect(NM_DATABASE_URL, row_factory=dict_row)

def nm_pg_json(data):
    try:
        return json.dumps(data or {}, ensure_ascii=False)
    except Exception:
        return "{}"

def nm_pg_unjson(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}

def nm_pg_init():
    global NM_V4_POSTGRES_ENABLED
    if not nm_pg_available():
        print("⚠️ NM V4 Postgres is not active. Missing DATABASE_URL or psycopg.")
        return False
    try:
        with nm_pg_conn() as conn:
            conn.execute(NM_PG_SCHEMA_SQL)
            conn.commit()
        NM_V4_POSTGRES_ENABLED = True
        print("✅ NM V4 Postgres schema ready.")
        return True
    except Exception as e:
        NM_V4_POSTGRES_ENABLED = False
        print(f"❌ NM V4 Postgres schema failed: {type(e).__name__}: {e}")
        return False

def nm_pg_meta_get(key, default=""):
    try:
        if not NM_V4_POSTGRES_ENABLED:
            return default
        with nm_pg_conn() as conn:
            row = conn.execute("SELECT value FROM nm_meta WHERE key=%s", (str(key),)).fetchone()
            return row["value"] if row else default
    except Exception:
        return default

def nm_pg_meta_set(key, value):
    try:
        if not NM_V4_POSTGRES_ENABLED:
            return
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO nm_meta (key,value,updated_at) VALUES (%s,%s,NOW()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()", (str(key), str(value)))
            conn.commit()
    except Exception as e:
        print(f"PG meta save failed: {e}")

def nm_pg_sqlite_rows(table):
    try:
        candidates = [Path("nm_system.db"), Path("/data/nm_system.db")]
        db_path = next((p for p in candidates if p.exists() and p.stat().st_size > 0), None)
        if not db_path:
            return []
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cur.fetchone():
            conn.close()
            return []
        cur.execute(f"SELECT * FROM {table}")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"PG migrate sqlite skip {table}: {type(e).__name__}: {e}")
        return []

def nm_pg_load_json_file(name):
    for p in [Path(name), Path("/data") / name]:
        try:
            if p.exists() and p.stat().st_size > 0:
                return json.loads(p.read_text(encoding="utf-8") or "{}")
        except Exception:
            pass
    return {}

def nm_pg_migrate_once():
    global NM_PG_AUTO_MIGRATE_DONE
    if not NM_V4_POSTGRES_ENABLED or NM_PG_AUTO_MIGRATE_DONE:
        return
    if nm_pg_meta_get("sqlite_migrated_v4", "0") == "1":
        NM_PG_AUTO_MIGRATE_DONE = True
        print("✅ NM V4 Postgres migration already done.")
        return
    counts = {}
    try:
        print("⏳ NM V4 Postgres auto migration started...")
        with nm_pg_conn() as conn:
            main_gid = int(globals().get("GUILD_ID", 0) or 0)
            ds = nm_pg_load_json_file("dashboard_settings.json")
            if ds and main_gid:
                conn.execute("INSERT INTO guild_settings (guild_id,settings,updated_at) VALUES (%s,%s::jsonb,NOW()) ON CONFLICT (guild_id) DO UPDATE SET settings=guild_settings.settings || EXCLUDED.settings, updated_at=NOW()", (main_gid, nm_pg_json(ds)))
                counts["dashboard_settings"] = len(ds)
            lc = nm_pg_load_json_file("log_channels.json")
            for key, cid in (lc.items() if isinstance(lc, dict) else []):
                if main_gid:
                    conn.execute("INSERT INTO guild_channels (guild_id,channel_key,channel_id,updated_at) VALUES (%s,%s,%s,NOW()) ON CONFLICT (guild_id,channel_key) DO UPDATE SET channel_id=EXCLUDED.channel_id, updated_at=NOW()", (main_gid, str(key), int(cid or 0)))
                    counts["log_channels"] = counts.get("log_channels", 0) + 1
            wj = nm_pg_load_json_file("warnings.json")
            for uid, items in (wj.items() if isinstance(wj, dict) else []):
                for item in (items if isinstance(items, list) else []):
                    conn.execute("INSERT INTO warnings (guild_id,user_id,reason,message,moderator_name,status) VALUES (%s,%s,%s,%s,%s,'active')", (main_gid, int(uid), str(item.get("reason","")), str(item.get("message","")), str(item.get("moderator",""))))
                    counts["warnings_json"] = counts.get("warnings_json", 0) + 1
            for r in nm_pg_sqlite_rows("economy"):
                gid, uid = int(r.get("guild_id") or 0), int(r.get("user_id") or 0)
                if uid:
                    conn.execute("INSERT INTO economy (guild_id,user_id,balance,admin_given,earned_money,updated_at) VALUES (%s,%s,%s,%s,%s,NOW()) ON CONFLICT (guild_id,user_id) DO UPDATE SET balance=EXCLUDED.balance, admin_given=GREATEST(economy.admin_given,EXCLUDED.admin_given), earned_money=GREATEST(economy.earned_money,EXCLUDED.earned_money), updated_at=NOW()", (gid, uid, int(r.get("balance") or 0), int(r.get("admin_given") or 0), int(r.get("earned_money") or 0)))
                    counts["economy"] = counts.get("economy", 0) + 1
            for r in nm_pg_sqlite_rows("levels"):
                gid, uid = int(r.get("guild_id") or 0), int(r.get("user_id") or 0)
                if uid:
                    conn.execute("INSERT INTO levels (guild_id,user_id,xp,level,updated_at) VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (guild_id,user_id) DO UPDATE SET xp=EXCLUDED.xp, level=EXCLUDED.level, updated_at=NOW()", (gid, uid, int(r.get("xp") or 0), int(r.get("level") or 1)))
                    counts["levels"] = counts.get("levels", 0) + 1
            for table in ("guild_settings", "guild_protection_settings"):
                for r in nm_pg_sqlite_rows(table):
                    gid = int(r.get("guild_id") or 0)
                    if not gid:
                        continue
                    data = {k:v for k,v in r.items() if k not in ("guild_id","id","created_at","updated_at")}
                    conn.execute(f"INSERT INTO {table} (guild_id,settings,updated_at) VALUES (%s,%s::jsonb,NOW()) ON CONFLICT (guild_id) DO UPDATE SET settings={table}.settings || EXCLUDED.settings, updated_at=NOW()", (gid, nm_pg_json(data)))
                    counts[table] = counts.get(table, 0) + 1
            for r in nm_pg_sqlite_rows("dashboard_log_vault"):
                conn.execute("INSERT INTO log_vault (guild_id,log_type,title,description,color,discord_channel_id,discord_channel_name,discord_message_id,deleted_from_discord,deleted_by_id,deleted_by_name,created_at,deleted_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(r.get("guild_id") or 0), str(r.get("log_type") or ""), str(r.get("title") or ""), str(r.get("description") or ""), int(r.get("color") or 0), int(r.get("discord_channel_id") or 0), str(r.get("discord_channel_name") or ""), int(r.get("discord_message_id") or 0), bool(int(r.get("deleted_from_discord") or 0)), int(r.get("deleted_by_id") or 0), str(r.get("deleted_by_name") or ""), int(r.get("created_at") or time.time()), int(r.get("deleted_at") or 0)))
                counts["log_vault"] = counts.get("log_vault", 0) + 1
            for r in nm_pg_sqlite_rows("command_center_events"):
                conn.execute("INSERT INTO command_center_events (guild_id,event_type,user_id,user_name,channel_id,channel_name,amount,details,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(r.get("guild_id") or 0), str(r.get("event_type") or ""), int(r.get("user_id") or 0), str(r.get("user_name") or ""), int(r.get("channel_id") or 0), str(r.get("channel_name") or ""), int(r.get("amount") or 0), str(r.get("details") or ""), int(r.get("created_at") or time.time())))
                counts["command_center_events"] = counts.get("command_center_events", 0) + 1
            for r in nm_pg_sqlite_rows("money_audit"):
                conn.execute("INSERT INTO money_audit (guild_id,user_id,amount,new_balance,source_type,details,actor_id,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (int(r.get("guild_id") or 0), int(r.get("user_id") or 0), int(r.get("amount") or 0), int(r.get("new_balance") or 0), str(r.get("source_type") or ""), str(r.get("details") or ""), int(r.get("actor_id") or 0), int(r.get("created_at") or time.time())))
                counts["money_audit"] = counts.get("money_audit", 0) + 1
            conn.execute("INSERT INTO nm_meta (key,value,updated_at) VALUES ('sqlite_migrated_v4','1',NOW()) ON CONFLICT (key) DO UPDATE SET value='1', updated_at=NOW()")
            conn.commit()
        NM_PG_AUTO_MIGRATE_DONE = True
        print("✅ NM V4 Postgres auto migration completed:", counts)
    except Exception as e:
        print(f"❌ NM V4 Postgres auto migration failed: {type(e).__name__}: {e}")

def pg_get_guild_settings(guild_id):
    try:
        with nm_pg_conn() as conn:
            row = conn.execute("SELECT settings FROM guild_settings WHERE guild_id=%s", (int(guild_id),)).fetchone()
            return nm_pg_unjson(row["settings"]) if row else {}
    except Exception as e:
        print(f"PG get settings failed: {e}")
        return {}

def pg_save_guild_settings(guild_id, settings):
    try:
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO guild_settings (guild_id,settings,updated_at) VALUES (%s,%s::jsonb,NOW()) ON CONFLICT (guild_id) DO UPDATE SET settings=EXCLUDED.settings, updated_at=NOW()", (int(guild_id), nm_pg_json(settings)))
            conn.commit()
        return True
    except Exception as e:
        print(f"PG save settings failed: {e}")
        return False

def pg_get_balance(guild_id, user_id):
    try:
        with nm_pg_conn() as conn:
            row = conn.execute("SELECT balance FROM economy WHERE guild_id=%s AND user_id=%s", (int(guild_id), int(user_id))).fetchone()
            if row:
                return int(row["balance"] or 0)
            conn.execute("INSERT INTO economy (guild_id,user_id,balance) VALUES (%s,%s,0) ON CONFLICT DO NOTHING", (int(guild_id), int(user_id)))
            conn.commit()
            return 0
    except Exception as e:
        print(f"PG balance failed: {e}")
        return 0

def pg_add_money(guild_id, user_id, amount, source_type="earned", details="", actor_id=0):
    try:
        guild_id, user_id, amount = int(guild_id), int(user_id), int(amount)
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO economy (guild_id,user_id,balance) VALUES (%s,%s,0) ON CONFLICT DO NOTHING", (guild_id, user_id))
            if amount > 0 and source_type in ("admin","admin_give","give_all","dashboard_admin"):
                conn.execute("UPDATE economy SET balance=balance+%s, admin_given=admin_given+%s, updated_at=NOW() WHERE guild_id=%s AND user_id=%s", (amount, amount, guild_id, user_id))
            elif amount > 0:
                conn.execute("UPDATE economy SET balance=balance+%s, earned_money=earned_money+%s, updated_at=NOW() WHERE guild_id=%s AND user_id=%s", (amount, amount, guild_id, user_id))
            else:
                conn.execute("UPDATE economy SET balance=balance+%s, updated_at=NOW() WHERE guild_id=%s AND user_id=%s", (amount, guild_id, user_id))
            row = conn.execute("SELECT balance FROM economy WHERE guild_id=%s AND user_id=%s", (guild_id, user_id)).fetchone()
            bal = int(row["balance"] or 0)
            conn.execute("INSERT INTO money_audit (guild_id,user_id,amount,new_balance,source_type,details,actor_id,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (guild_id,user_id,amount,bal,str(source_type),str(details),int(actor_id or 0),int(time.time())))
            conn.commit()
            return bal
    except Exception as e:
        print(f"PG add money failed: {e}")
        return 0

def pg_claim_salary(guild_id, user_id, level=1):
    now = int(time.time())
    cooldown = int(globals().get("HOURLY_REWARD_COOLDOWN_SECONDS", 3600))
    reward = int(globals().get("DAILY_REWARD_BASE", 250)) + int(level or 1) * 25
    try:
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO salary_cooldowns (guild_id,user_id,last_claim) VALUES (%s,%s,0) ON CONFLICT DO NOTHING", (int(guild_id), int(user_id)))
            row = conn.execute("SELECT last_claim FROM salary_cooldowns WHERE guild_id=%s AND user_id=%s", (int(guild_id), int(user_id))).fetchone()
            last = int(row["last_claim"] or 0) if row else 0
            rem = cooldown - (now - last)
            if rem > 0:
                return False, rem, pg_get_balance(guild_id,user_id), 0
            conn.execute("UPDATE salary_cooldowns SET last_claim=%s WHERE guild_id=%s AND user_id=%s", (now, int(guild_id), int(user_id)))
            conn.commit()
        bal = pg_add_money(guild_id, user_id, reward, "salary", "Postgres salary")
        return True, 0, bal, reward
    except Exception as e:
        print(f"PG salary failed: {e}")
        return False, cooldown, pg_get_balance(guild_id,user_id), 0

def pg_get_level_data(guild_id, user_id):
    try:
        with nm_pg_conn() as conn:
            row = conn.execute("SELECT xp,level FROM levels WHERE guild_id=%s AND user_id=%s", (int(guild_id), int(user_id))).fetchone()
            if row:
                return int(row["xp"] or 0), int(row["level"] or 1)
            conn.execute("INSERT INTO levels (guild_id,user_id,xp,level) VALUES (%s,%s,0,1) ON CONFLICT DO NOTHING", (int(guild_id), int(user_id)))
            conn.commit()
            return 0,1
    except Exception as e:
        print(f"PG level failed: {e}")
        return 0,1

def pg_get_protection_settings(guild_id):
    try:
        with nm_pg_conn() as conn:
            row = conn.execute("SELECT settings FROM guild_protection_settings WHERE guild_id=%s", (int(guild_id),)).fetchone()
        base = protection_default_settings() if "protection_default_settings" in globals() else {}
        if row:
            base.update(nm_pg_unjson(row["settings"]))
        return base
    except Exception:
        return protection_default_settings() if "protection_default_settings" in globals() else {}

def pg_save_protection_settings(guild_id, settings):
    try:
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO guild_protection_settings (guild_id,settings,updated_at) VALUES (%s,%s::jsonb,NOW()) ON CONFLICT (guild_id) DO UPDATE SET settings=EXCLUDED.settings, updated_at=NOW()", (int(guild_id), nm_pg_json(settings)))
            conn.commit()
        return True
    except Exception as e:
        print(f"PG protection save failed: {e}")
        return False

def pg_log_vault_record(log_type, title, description, color=0, guild_id=0):
    try:
        with nm_pg_conn() as conn:
            row = conn.execute("INSERT INTO log_vault (guild_id,log_type,title,description,color,created_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id", (int(guild_id or globals().get("GUILD_ID",0) or 0), str(log_type), str(title), str(description), int(color or 0), int(time.time()))).fetchone()
            conn.commit()
            return int(row["id"])
    except Exception as e:
        print(f"PG log vault failed: {e}")
        return 0

def pg_log_vault_attach_discord_message(vault_id, channel_id=0, channel_name="", message_id=0):
    try:
        if not vault_id:
            return
        with nm_pg_conn() as conn:
            conn.execute("UPDATE log_vault SET discord_channel_id=%s, discord_channel_name=%s, discord_message_id=%s WHERE id=%s", (int(channel_id or 0), str(channel_name or ""), int(message_id or 0), int(vault_id)))
            conn.commit()
    except Exception as e:
        print(f"PG log attach failed: {e}")

def pg_log_vault_recent(guild_id=0, limit=80, offset=0, log_type="all", query="", deleted_filter="all", channel_id="all"):
    try:
        wh = ["guild_id=%s"]; params=[int(guild_id or 0)]
        if log_type and log_type!="all": wh.append("log_type=%s"); params.append(str(log_type))
        if channel_id and str(channel_id)!="all": wh.append("discord_channel_id=%s"); params.append(int(channel_id))
        if deleted_filter=="deleted": wh.append("deleted_from_discord=TRUE")
        if deleted_filter=="saved": wh.append("deleted_from_discord=FALSE")
        if query:
            q=f"%{str(query)[:120]}%"; wh.append("(title ILIKE %s OR description ILIKE %s OR discord_channel_name ILIKE %s)"); params += [q,q,q]
        where=" WHERE "+" AND ".join(wh)
        with nm_pg_conn() as conn:
            rows = conn.execute("SELECT * FROM log_vault "+where+" ORDER BY id DESC LIMIT %s OFFSET %s", tuple(params+[int(limit),int(offset)])).fetchall()
            total = conn.execute("SELECT COUNT(*) AS c FROM log_vault "+where, tuple(params)).fetchone()["c"]
        out=[]
        for r in rows:
            out.append((r["id"],r["guild_id"],r["log_type"],r["title"],r["description"],r["discord_channel_id"],r["discord_channel_name"],r["discord_message_id"],int(bool(r["deleted_from_discord"])),r["deleted_by_id"],r["deleted_by_name"],r["created_at"],r["deleted_at"]))
        return out, int(total)
    except Exception as e:
        print(f"PG log recent failed: {e}")
        return [],0

def pg_log_vault_counts(guild_id=0):
    try:
        gid=int(guild_id or 0)
        with nm_pg_conn() as conn:
            total=conn.execute("SELECT COUNT(*) AS c FROM log_vault WHERE guild_id=%s",(gid,)).fetchone()["c"]
            deleted=conn.execute("SELECT COUNT(*) AS c FROM log_vault WHERE guild_id=%s AND deleted_from_discord=TRUE",(gid,)).fetchone()["c"]
            types=conn.execute("SELECT COUNT(DISTINCT log_type) AS c FROM log_vault WHERE guild_id=%s",(gid,)).fetchone()["c"]
            today=conn.execute("SELECT COUNT(*) AS c FROM log_vault WHERE guild_id=%s AND created_at >= %s",(gid,int(time.time())-86400)).fetchone()["c"]
        return int(total),int(deleted),int(types),int(today)
    except Exception: return 0,0,0,0

def pg_log_vault_channels(guild_id=0):
    try:
        with nm_pg_conn() as conn:
            rows=conn.execute("SELECT discord_channel_id,discord_channel_name,COUNT(*) AS c FROM log_vault WHERE guild_id=%s GROUP BY discord_channel_id,discord_channel_name ORDER BY c DESC",(int(guild_id or 0),)).fetchall()
            return [(r["discord_channel_id"],r["discord_channel_name"],r["c"]) for r in rows]
    except Exception: return []

def pg_log_vault_types(guild_id=0):
    try:
        with nm_pg_conn() as conn:
            rows=conn.execute("SELECT log_type,COUNT(*) AS c FROM log_vault WHERE guild_id=%s GROUP BY log_type ORDER BY c DESC",(int(guild_id or 0),)).fetchall()
            return [(r["log_type"],r["c"]) for r in rows]
    except Exception: return []

def pg_cc_record_event(event_type, user_id=0, user_name="", channel_id=0, channel_name="", amount=0, details="", guild_id=0):
    try:
        with nm_pg_conn() as conn:
            conn.execute("INSERT INTO command_center_events (guild_id,event_type,user_id,user_name,channel_id,channel_name,amount,details,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (int(guild_id or 0),str(event_type),int(user_id or 0),str(user_name or ""),int(channel_id or 0),str(channel_name or ""),int(amount or 0),str(details or ""),int(time.time())))
            conn.commit()
    except Exception as e:
        print(f"PG cc record failed: {e}")

def nm_pg_install_overrides():
    if not NM_V4_POSTGRES_ENABLED:
        return
    g=globals()
    g["get_guild_settings"]=pg_get_guild_settings
    g["save_guild_settings"]=pg_save_guild_settings
    g["v3_get_balance"]=pg_get_balance
    g["v3_add_money"]=pg_add_money
    g["v3_claim_salary"]=pg_claim_salary
    g["v3_get_level_data"]=pg_get_level_data
    g["get_guild_protection_settings"]=pg_get_protection_settings
    g["save_guild_protection_settings"]=pg_save_protection_settings
    g["log_vault_record"]=pg_log_vault_record
    g["log_vault_attach_discord_message"]=pg_log_vault_attach_discord_message
    g["log_vault_recent"]=pg_log_vault_recent
    g["log_vault_counts"]=pg_log_vault_counts
    g["log_vault_channels"]=pg_log_vault_channels
    g["log_vault_types"]=pg_log_vault_types
    g["cc_record_event"]=pg_cc_record_event
    print("✅ NM V4 Postgres overrides installed.")

def nm_pg_boot():
    if nm_pg_init():
        nm_pg_migrate_once()
        nm_pg_install_overrides()

@app.route("/dashboard/postgres-status")
def nm_pg_status_page():
    ok=bool(NM_V4_POSTGRES_ENABLED)
    counts={}
    if ok:
        try:
            with nm_pg_conn() as conn:
                for t in ["guild_settings","guild_channels","guild_protection_settings","economy","levels","warnings","log_vault","command_center_events","money_audit","salary_cooldowns","reward_locks"]:
                    try: counts[t]=int(conn.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"])
                    except Exception as e: counts[t]=f"ERR {type(e).__name__}"
        except Exception as e: counts["error"]=str(e)
    rows="".join(f"<tr><td>{dash_escape(str(k),100)}</td><td>{dash_escape(str(v),100)}</td></tr>" for k,v in counts.items())
    color = "#22c55e" if ok else "#ef4444"
    status = "ACTIVE" if ok else "NOT ACTIVE"
    dbtxt = "found" if NM_DATABASE_URL else "missing"
    return f"<div style='font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px'><h1>NM V4 PostgreSQL Status</h1><p>Status: <b style='color:{color}'>{status}</b></p><p>DATABASE_URL: {dbtxt}</p><table style='border-collapse:collapse;min-width:520px'><tr><th style='text-align:left;padding:8px;border-bottom:1px solid #334155'>Table</th><th style='text-align:left;padding:8px;border-bottom:1px solid #334155'>Rows</th></tr>{rows}</table><p><a style='color:#8b5cf6' href='/dashboard'>Back</a></p></div>"



# =========================
# NM V4 BRAND / COIN SYNC FIX
# يجعل اسم العملة والبراند يقرأ وينحفظ من PostgreSQL + fallback متوافق مع الداشبورد القديم.
# =========================

def nm_v4_selected_gid_for_settings():
    try:
        return int(
            request.args.get("guild_id")
            or request.form.get("guild_id")
            or session.get("selected_guild_id")
            or session.get("dashboard_active_guild_id")
            or GUILD_ID
        )
    except Exception:
        return int(globals().get("GUILD_ID", 0) or 0)

def nm_v4_normalize_settings_keys(settings):
    settings = dict(settings or {})

    # coin aliases
    coin = (
        settings.get("coin_name")
        or settings.get("currency_name")
        or settings.get("economy_coin_name")
        or settings.get("money_name")
        or settings.get("coin")
        or "NM Coin"
    )
    settings["coin_name"] = coin
    settings["currency_name"] = coin
    settings["economy_coin_name"] = coin

    # brand aliases
    brand = (
        settings.get("bot_brand")
        or settings.get("brand_name")
        or settings.get("bot_name")
        or "NM System"
    )
    settings["bot_brand"] = brand
    settings["brand_name"] = brand
    settings["bot_name"] = brand

    return settings

def nm_v4_get_settings(guild_id=None):
    gid = int(guild_id or nm_v4_selected_gid_for_settings())
    data = {}
    try:
        if NM_V4_POSTGRES_ENABLED:
            with nm_pg_conn() as conn:
                row = conn.execute("SELECT settings FROM guild_settings WHERE guild_id=%s", (gid,)).fetchone()
                if row:
                    data = nm_pg_unjson(row["settings"])
    except Exception as e:
        print(f"NM V4 settings get failed: {e}")

    # Fallback to old file/global only if PG has nothing useful.
    if not data:
        try:
            if "dashboard_settings" in globals() and isinstance(dashboard_settings, dict):
                data.update(dashboard_settings)
        except Exception:
            pass

    return nm_v4_normalize_settings_keys(data)

def nm_v4_save_settings(guild_id=None, settings=None):
    gid = int(guild_id or nm_v4_selected_gid_for_settings())
    settings = nm_v4_normalize_settings_keys(settings or {})
    try:
        if NM_V4_POSTGRES_ENABLED:
            with nm_pg_conn() as conn:
                conn.execute("""
                    INSERT INTO guild_settings (guild_id, settings, updated_at)
                    VALUES (%s,%s::jsonb,NOW())
                    ON CONFLICT (guild_id)
                    DO UPDATE SET settings = guild_settings.settings || EXCLUDED.settings, updated_at=NOW()
                """, (gid, nm_pg_json(settings)))
                conn.commit()
            return True
    except Exception as e:
        print(f"NM V4 settings save failed: {e}")

    try:
        if "dashboard_settings" in globals() and isinstance(dashboard_settings, dict):
            dashboard_settings.update(settings)
            if "save_dashboard_settings" in globals():
                save_dashboard_settings()
            return True
    except Exception:
        pass
    return False

# Override generic settings functions again after all old functions exist.
def get_guild_settings(guild_id):
    return nm_v4_get_settings(guild_id)

def save_guild_settings(guild_id, settings):
    return nm_v4_save_settings(guild_id, settings)

def nm_get_coin_name(guild_id=None):
    return nm_v4_get_settings(guild_id).get("coin_name", "NM Coin")

def nm_get_brand_name(guild_id=None):
    return nm_v4_get_settings(guild_id).get("bot_brand", "NM System")

@app.route("/dashboard/fix-brand-coin")
def nm_fix_brand_coin_route():
    gid = nm_v4_selected_gid_for_settings()
    settings = nm_v4_get_settings(gid)

    # If old dashboard imported NM Coin, replace it with NM Coin once.
    if str(settings.get("coin_name", "")).lower().strip() in {"retard coin", "retard", "retard coins"}:
        settings["coin_name"] = "NM Coin"
        settings["currency_name"] = "NM Coin"
        settings["economy_coin_name"] = "NM Coin"

    if not settings.get("bot_brand"):
        settings["bot_brand"] = "NM System"

    nm_v4_save_settings(gid, settings)

    return f"""
    <div style="font-family:Arial;background:#0b1020;color:white;min-height:100vh;padding:40px">
      <h1>Brand/Coin fixed</h1>
      <p>Guild: <b>{int(gid)}</b></p>
      <p>Brand: <b>{dash_escape(settings.get('bot_brand','NM System'),100)}</b></p>
      <p>Coin: <b>{dash_escape(settings.get('coin_name','NM Coin'),100)}</b></p>
      <p><a style="color:#8b5cf6" href="/dashboard?guild_id={int(gid)}">Back to Dashboard</a></p>
    </div>
    """



def nm_v4_boot_normalize_brand_coin():
    try:
        if not NM_V4_POSTGRES_ENABLED:
            return
        main_gid = int(globals().get("GUILD_ID", 0) or 0)
        if main_gid:
            s = nm_v4_get_settings(main_gid)
            if str(s.get("coin_name","")).lower().strip() in {"retard coin","retard","retard coins"}:
                s["coin_name"] = "NM Coin"
                s["currency_name"] = "NM Coin"
                s["economy_coin_name"] = "NM Coin"
            nm_v4_save_settings(main_gid, s)
            print("✅ NM V4 brand/coin normalized.")
    except Exception as e:
        print(f"NM V4 brand/coin normalize failed: {e}")


nm_pg_boot()
nm_v4_boot_normalize_brand_coin()

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
