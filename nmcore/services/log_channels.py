import time
from nmcore.db import db
from nmcore.services.settings import get_logs_channel_id

LOG_CHANNELS = {
    "general": ("nm-logs", "اللوق العام للنظام"),
    "protection": ("protection-logs", "لوقات الحماية والكلام الممنوع والروابط"),
    "economy": ("economy-logs", "لوقات الاقتصاد والتحويلات والرواتب"),
    "casino": ("casino-logs", "لوقات القمار والكازينو"),
    "warnings": ("warnings-logs", "لوقات التحذيرات والمخالفات"),
    "join_leave": ("join-leave-logs", "لوقات الدخول والخروج والطرد والباند"),
    "messages": ("message-logs", "لوقات حذف وتعديل الرسائل"),
    "roles": ("role-logs", "لوقات الرتب وتغييرات الأعضاء"),
    "voice": ("voice-logs", "لوقات دخول وخروج الرومات الصوتية"),
    "server": ("server-logs", "لوقات الرومات والسيرفر"),
    "commands": ("command-logs", "لوقات استخدام أوامر البوت"),
}


def ensure_table():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS log_channel_settings (
        guild_id INTEGER NOT NULL,
        log_key TEXT NOT NULL,
        channel_id INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, log_key)
    )""")
    conn.commit()
    conn.close()


def set_log_channel(guild_id:int, log_key:str, channel_id:int):
    ensure_table()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO log_channel_settings (guild_id,log_key,channel_id,updated_at)
    VALUES (?,?,?,?)
    ON CONFLICT(guild_id,log_key) DO UPDATE SET
      channel_id=excluded.channel_id,
      updated_at=excluded.updated_at""",
    (int(guild_id), str(log_key), int(channel_id or 0), int(time.time())))
    conn.commit()
    conn.close()


def get_log_channel(guild_id:int, log_key:str) -> int:
    ensure_table()
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT channel_id FROM log_channel_settings WHERE guild_id=? AND log_key=?", (int(guild_id), str(log_key)))
    row = cur.fetchone()

    if row and int(row["channel_id"] or 0):
        conn.close()
        return int(row["channel_id"])

    if log_key != "general":
        cur.execute("SELECT channel_id FROM log_channel_settings WHERE guild_id=? AND log_key='general'", (int(guild_id),))
        row = cur.fetchone()
        if row and int(row["channel_id"] or 0):
            conn.close()
            return int(row["channel_id"])

    conn.close()

    # Backward compatible fallback to old guild_settings.logs_channel_id
    return int(get_logs_channel_id(guild_id) or 0)


def all_log_channels(guild_id:int) -> dict:
    ensure_table()
    data = {k: 0 for k in LOG_CHANNELS}

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT log_key,channel_id FROM log_channel_settings WHERE guild_id=?", (int(guild_id),))
    for r in cur.fetchall():
        data[str(r["log_key"])] = int(r["channel_id"] or 0)
    conn.close()

    return data
