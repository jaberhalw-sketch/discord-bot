import time
from nmcore.db import db
from nmcore.services.activity import record, log_event


def ensure_tables():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS boost_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        message_id INTEGER NOT NULL DEFAULT 0,
        channel_id INTEGER NOT NULL DEFAULT 0,
        event_type TEXT DEFAULT 'boost',
        created_at INTEGER NOT NULL DEFAULT 0,
        UNIQUE(guild_id, message_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS boosters (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        boost_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 0,
        first_boost_at INTEGER DEFAULT 0,
        last_boost_at INTEGER DEFAULT 0,
        premium_since INTEGER DEFAULT 0,
        updated_at INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")

    conn.commit()
    conn.close()


def _upsert_booster(guild_id:int, user_id:int, user_name:str, *, active=None, premium_since=0, add_count=0):
    ensure_tables()
    now = int(time.time())

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM boosters WHERE guild_id=? AND user_id=?", (int(guild_id), int(user_id)))
    row = cur.fetchone()

    if row:
        old_count = int(row["boost_count"] or 0)
        new_count = max(0, old_count + int(add_count or 0))
        first = int(row["first_boost_at"] or 0) or (now if add_count else 0)
        last = now if add_count else int(row["last_boost_at"] or 0)
        new_active = int(row["active"] or 0) if active is None else (1 if active else 0)
        prem = int(premium_since or row["premium_since"] or 0)

        cur.execute("""UPDATE boosters SET
        user_name=?, boost_count=?, active=?, first_boost_at=?, last_boost_at=?,
        premium_since=?, updated_at=?
        WHERE guild_id=? AND user_id=?""",
        (str(user_name or user_id)[:120], new_count, new_active, first, last, prem, now, int(guild_id), int(user_id)))
    else:
        first = now if add_count else 0
        last = now if add_count else 0
        cur.execute("""INSERT INTO boosters
        (guild_id,user_id,user_name,boost_count,active,first_boost_at,last_boost_at,premium_since,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(user_id), str(user_name or user_id)[:120], max(0, int(add_count or 0)),
         1 if active else 0, first, last, int(premium_since or 0), now))

    conn.commit()
    conn.close()


def record_boost_message(message):
    """
    Tracks Discord system boost messages. This is the most reliable way to count
    how many boost events happened, because Member.premium_since only says active/not active.
    """
    if not getattr(message, "guild", None) or not getattr(message, "author", None):
        return {"ok": False, "reason": "no guild/author"}

    ensure_tables()
    now = int(time.time())
    event_type = str(getattr(message, "type", "boost"))

    conn = db()
    cur = conn.cursor()

    cur.execute("""INSERT OR IGNORE INTO boost_events
    (guild_id,user_id,user_name,message_id,channel_id,event_type,created_at)
    VALUES (?,?,?,?,?,?,?)""",
    (int(message.guild.id), int(message.author.id), str(message.author.display_name)[:120],
     int(message.id), int(getattr(message.channel, "id", 0) or 0), event_type, now))

    inserted = cur.rowcount > 0
    conn.commit()
    conn.close()

    if inserted:
        premium_since = 0
        try:
            if getattr(message.author, "premium_since", None):
                premium_since = int(message.author.premium_since.timestamp())
        except Exception:
            premium_since = 0

        _upsert_booster(
            message.guild.id,
            message.author.id,
            message.author.display_name,
            active=True,
            premium_since=premium_since,
            add_count=1
        )

        record(message.guild.id, message.author.id, message.author.display_name, "server_boost", "Server Boost", "Boost detected", 0)
        log_event(message.guild.id, "server_boost", message.author.id, message.author.display_name, message.channel.id, message.channel.name, "Server boost detected", f"Message={message.id}, Type={event_type}")

    return {"ok": bool(inserted), "inserted": bool(inserted)}


def sync_member(member):
    if not getattr(member, "guild", None):
        return

    active = bool(getattr(member, "premium_since", None))
    premium_since = 0
    try:
        if member.premium_since:
            premium_since = int(member.premium_since.timestamp())
    except Exception:
        premium_since = 0

    _upsert_booster(
        member.guild.id,
        member.id,
        member.display_name,
        active=active,
        premium_since=premium_since,
        add_count=0
    )


def sync_guild(guild):
    ensure_tables()
    for member in getattr(guild, "members", []) or []:
        if getattr(member, "premium_since", None):
            sync_member(member)


def summary(guild_id:int, limit:int=100):
    ensure_tables()
    conn = db()
    cur = conn.cursor()

    cur.execute("""SELECT
    COUNT(*) total_events,
    COUNT(DISTINCT user_id) unique_boosters
    FROM boost_events WHERE guild_id=?""", (int(guild_id),))
    totals = dict(cur.fetchone() or {})

    cur.execute("""SELECT COUNT(*) active_boosters
    FROM boosters WHERE guild_id=? AND active=1""", (int(guild_id),))
    active = dict(cur.fetchone() or {})
    totals.update(active)

    cur.execute("""SELECT * FROM boosters
    WHERE guild_id=?
    ORDER BY active DESC, boost_count DESC, last_boost_at DESC
    LIMIT ?""", (int(guild_id), int(limit)))
    boosters = [dict(r) for r in cur.fetchall()]

    cur.execute("""SELECT * FROM boost_events
    WHERE guild_id=?
    ORDER BY id DESC LIMIT ?""", (int(guild_id), int(limit)))
    recent = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"totals": totals, "boosters": boosters, "recent": recent}
