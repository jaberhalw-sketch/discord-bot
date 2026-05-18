import os
from pathlib import Path

TOKEN = os.getenv("TOKEN", "")
PREFIX = os.getenv("PREFIX", "!")
BOT_BRAND = os.getenv("BOT_BRAND", "NM System")
DEFAULT_COIN_NAME = os.getenv("DEFAULT_COIN_NAME", "NM Coin")

DATA_DIR = Path(os.getenv("NM_DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = Path(".")
DB_FILE = str(DATA_DIR / "nm_system_v9.db")
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DASHBOARD_SECRET_KEY = os.getenv("DASHBOARD_SECRET_KEY", "change-this-secret")

SALARY_BASE = int(os.getenv("SALARY_BASE", "250"))
SALARY_COOLDOWN_SECONDS = int(os.getenv("SALARY_COOLDOWN_SECONDS", "3600"))
LEVEL_COOLDOWN_SECONDS = int(os.getenv("LEVEL_COOLDOWN_SECONDS", "25"))
XP_PER_MESSAGE_MIN = int(os.getenv("XP_PER_MESSAGE_MIN", "5"))
XP_PER_MESSAGE_MAX = int(os.getenv("XP_PER_MESSAGE_MAX", "15"))
CASINO_COOLDOWN_SECONDS = int(os.getenv("CASINO_COOLDOWN_SECONDS", "2"))
REAL_ESTATE_RENT_COOLDOWN_SECONDS = int(os.getenv("REAL_ESTATE_RENT_COOLDOWN_SECONDS", str(6*60*60)))
RUNTIME_ERROR_LIMIT = 500
LIVE_ACTIVITY_LIMIT = 1000
