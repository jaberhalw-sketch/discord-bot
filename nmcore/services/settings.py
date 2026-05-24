import time, sqlite3
from nmcore.db import db
from nmcore.config import DEFAULT_COIN_NAME

SYSTEM_DEFAULTS = {
    "utility": True, "admin": True, "economy": True, "levels": True,
    "gambling": True, "protection": True, "logs": True, "real_estate": True,
    "shop": True, "giveaway": True, "memory": True
}
COMMAND_SYSTEM = {
    "رصيدي":"economy","رصيد":"economy","راتب":"economy","تحويل":"economy","الغني":"economy","اغنى":"economy",
    "اعطاءفلوس":"economy","سحبفلوس":"economy","تصفيرفلوس":"economy",
    "حظ":"gambling","luck":"gambling","دبل":"gambling","double":"gambling","سلوت":"gambling","slot":"gambling",
    "وجه":"gambling","flip":"gambling","بلاكجاك":"gambling","bj":"gambling","blackjack":"gambling",
    "لفلي":"levels","لفل":"levels","ترتيب":"levels",
    "عقارات":"real_estate","شراء_عقار":"real_estate","ايجار":"real_estate","عقاراتي":"real_estate",
    "تحذير":"protection","تحذيرات":"protection","مسح_تحذيرات":"protection",
    "متجر":"shop","شراء":"shop","صندوق":"shop",
    "سحب":"giveaway","فعالية":"giveaway",
    "مساعدة":"utility","بنق":"utility","شرح_الاقتصاد":"utility","شرح_القمار":"utility","شرح_البوت":"utility","شرح_لعب":"utility","لعب":"utility","lfg":"utility","قيم":"utility","ارسال_الشروحات":"admin","اعداد":"admin","لوحة":"admin","قفل":"admin","فتح":"admin","مسح":"admin"
}


def _settings_write_retry(fn, retries=1, delay=0.0):
    try:
        return fn()
    except sqlite3.OperationalError as e:
        if "locked" not in str(e).lower():
            raise
        return None
    except Exception:
        return None


def ensure_guild(guild_id:int, guild_name:str=""):
    def work():
        conn = db()
        cur = conn.cursor()

        cur.execute("""INSERT OR IGNORE INTO guild_settings
        (guild_id,guild_name,coin_name,created_at,updated_at)
        VALUES (?,?,?,?,?)""", (int(guild_id), str(guild_name or "")[:120], DEFAULT_COIN_NAME, int(time.time()), int(time.time())))

        if guild_name:
            cur.execute("UPDATE guild_settings SET guild_name=?, updated_at=? WHERE guild_id=?", (str(guild_name)[:120], int(time.time()), int(guild_id)))

        for key, enabled in SYSTEM_DEFAULTS.items():
            cur.execute("""INSERT OR IGNORE INTO system_toggles
            (guild_id,system_key,enabled,updated_at)
            VALUES (?,?,?,?)""", (int(guild_id), key, 1 if enabled else 0, int(time.time())))

        # Safe migrations. These are repeated but cheap, and ignore if column exists.
        migrations = [
            "ALTER TABLE guild_settings ADD COLUMN dev_mode_enabled INTEGER DEFAULT 0",
            "ALTER TABLE guild_settings ADD COLUMN lfg_channel_id INTEGER DEFAULT 0",
            "ALTER TABLE guild_settings ADD COLUMN lfg_category_id INTEGER DEFAULT 0",
            "ALTER TABLE guild_settings ADD COLUMN lfg_delete_empty_minutes INTEGER DEFAULT 10",
        ]
        for sql in migrations:
            try:
                cur.execute(sql)
            except Exception:
                pass

        conn.commit()
        conn.close()

    return _settings_write_retry(work)


def get_coin_name(guild_id:int)->str:
    ensure_guild(guild_id)
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT coin_name FROM guild_settings WHERE guild_id=?", (int(guild_id),))
        row = cur.fetchone()
        conn.close()
        return row["coin_name"] if row and row["coin_name"] else DEFAULT_COIN_NAME
    res = _settings_write_retry(work)
    return res or DEFAULT_COIN_NAME


def set_coin_name(guild_id:int, coin_name:str):
    ensure_guild(guild_id)
    val = str(coin_name or DEFAULT_COIN_NAME).strip()[:40] or DEFAULT_COIN_NAME

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE guild_settings SET coin_name=?, updated_at=? WHERE guild_id=?", (val, int(time.time()), int(guild_id)))
        conn.commit()
        conn.close()

    return _settings_write_retry(work)


def is_system_enabled(guild_id:int, system_key:str)->bool:
    ensure_guild(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT enabled FROM system_toggles WHERE guild_id=? AND system_key=?", (int(guild_id), str(system_key)))
        row = cur.fetchone()
        conn.close()
        return True if not row else bool(row["enabled"])

    res = _settings_write_retry(work)
    return True if res is None else bool(res)


def set_system_enabled(guild_id:int, system_key:str, enabled:bool):
    ensure_guild(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO system_toggles (guild_id,system_key,enabled,updated_at)
        VALUES (?,?,?,?)
        ON CONFLICT(guild_id,system_key) DO UPDATE SET
          enabled=excluded.enabled,
          updated_at=excluded.updated_at""",
        (int(guild_id), str(system_key), 1 if enabled else 0, int(time.time())))
        conn.commit()
        conn.close()

    return _settings_write_retry(work)


def all_toggles(guild_id:int)->dict:
    ensure_guild(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT system_key, enabled FROM system_toggles WHERE guild_id=?", (int(guild_id),))
        rows = cur.fetchall()
        conn.close()
        out = {k: v for k, v in SYSTEM_DEFAULTS.items()}
        for r in rows:
            out[str(r["system_key"])] = bool(r["enabled"])
        return out

    res = _settings_write_retry(work)
    return res or {k: v for k, v in SYSTEM_DEFAULTS.items()}


def get_guild_settings(guild_id:int)->dict:
    ensure_guild(guild_id)
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT * FROM guild_settings WHERE guild_id=?", (int(guild_id),))
    row=cur.fetchone(); conn.close()
    return dict(row) if row else {}

def update_channel(guild_id:int, key:str, value:int):
    if key not in {"commands_channel_id","gambling_channel_id","logs_channel_id","lfg_channel_id","lfg_category_id","lfg_delete_empty_minutes"}:
        return
    ensure_guild(guild_id)
    conn=db(); cur=conn.cursor()
    cur.execute(f"UPDATE guild_settings SET {key}=?, updated_at=? WHERE guild_id=?", (int(value or 0),int(time.time()),int(guild_id)))
    conn.commit(); conn.close()

def command_system(command_name:str)->str:
    return COMMAND_SYSTEM.get(str(command_name or "").lower(), COMMAND_SYSTEM.get(str(command_name or ""), "utility"))


def get_command_channel_id(guild_id:int)->int:
    gs = get_guild_settings(guild_id)
    return int(gs.get("commands_channel_id") or 0)

def get_gambling_channel_id(guild_id:int)->int:
    gs = get_guild_settings(guild_id)
    return int(gs.get("gambling_channel_id") or 0)

def get_logs_channel_id(guild_id:int)->int:
    gs = get_guild_settings(guild_id)
    return int(gs.get("logs_channel_id") or 0)

def channel_restriction_for_system(guild_id:int, system_key:str)->int:
    system_key = str(system_key or "")
    if system_key == "gambling":
        return get_gambling_channel_id(guild_id)
    if system_key in {"economy", "levels", "real_estate", "shop", "giveaway", "utility"}:
        return get_command_channel_id(guild_id)
    return 0


def is_dev_mode_enabled(guild_id:int)->bool:
    ensure_guild(guild_id)
    conn=db(); cur=conn.cursor()
    try:
        cur.execute("SELECT dev_mode_enabled FROM guild_settings WHERE guild_id=?", (int(guild_id),))
        row=cur.fetchone()
        conn.close()
        return bool(row and int(row["dev_mode_enabled"] or 0))
    except Exception:
        conn.close()
        return False

def set_dev_mode_enabled(guild_id:int, enabled:bool):
    ensure_guild(guild_id)
    conn=db(); cur=conn.cursor()
    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN dev_mode_enabled INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN lfg_channel_id INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN lfg_category_id INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN lfg_delete_empty_minutes INTEGER DEFAULT 10")
    except Exception:
        pass
    cur.execute("UPDATE guild_settings SET dev_mode_enabled=?, updated_at=? WHERE guild_id=?", (1 if enabled else 0,int(time.time()),int(guild_id)))
    conn.commit(); conn.close()


def get_lfg_channel_id(guild_id:int)->int:
    ensure_guild(guild_id)
    gs = get_guild_settings(guild_id)
    return int(gs.get("lfg_channel_id") or 0)

def set_lfg_channel_id(guild_id:int, channel_id:int):
    update_channel(guild_id, "lfg_channel_id", int(channel_id or 0))


def get_lfg_settings(guild_id:int)->dict:
    ensure_guild(guild_id)
    gs = get_guild_settings(guild_id)
    return {
        "lfg_channel_id": int(gs.get("lfg_channel_id") or 0),
        "lfg_category_id": int(gs.get("lfg_category_id") or 0),
        "lfg_delete_empty_minutes": int(gs.get("lfg_delete_empty_minutes") or 10),
    }

def update_lfg_settings(guild_id:int, *, channel_id=None, category_id=None, delete_empty_minutes=None):
    if channel_id is not None:
        update_channel(guild_id, "lfg_channel_id", int(channel_id or 0))
    if category_id is not None:
        update_channel(guild_id, "lfg_category_id", int(category_id or 0))
    if delete_empty_minutes is not None:
        update_channel(guild_id, "lfg_delete_empty_minutes", max(0, int(delete_empty_minutes or 0)))
