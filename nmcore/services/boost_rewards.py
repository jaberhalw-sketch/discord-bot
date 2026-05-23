import time
from nmcore.db import db
from nmcore.services.economy import credit
from nmcore.services.activity import record, log_event


DEFAULT_BOOST_REWARD_AMOUNT = 5000


def ensure_tables():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS boost_reward_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 0,
        amount INTEGER DEFAULT 5000,
        updated_at INTEGER DEFAULT 0
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS boost_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        message_id INTEGER NOT NULL DEFAULT 0,
        channel_id INTEGER NOT NULL DEFAULT 0,
        event_type TEXT DEFAULT 'boost',
        amount INTEGER DEFAULT 0,
        money_tx_id TEXT DEFAULT '',
        created_at INTEGER NOT NULL DEFAULT 0,
        UNIQUE(guild_id, message_id)
    )""")

    try:
        cur.execute("ALTER TABLE boost_events ADD COLUMN amount INTEGER DEFAULT 0")
    except Exception:
        pass

    try:
        cur.execute("ALTER TABLE boost_events ADD COLUMN money_tx_id TEXT DEFAULT ''")
    except Exception:
        pass

    cur.execute("""CREATE TABLE IF NOT EXISTS boosters (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        boost_count INTEGER DEFAULT 0,
        reward_total INTEGER DEFAULT 0,
        active INTEGER DEFAULT 0,
        first_boost_at INTEGER DEFAULT 0,
        last_boost_at INTEGER DEFAULT 0,
        premium_since INTEGER DEFAULT 0,
        updated_at INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")

    try:
        cur.execute("ALTER TABLE boosters ADD COLUMN reward_total INTEGER DEFAULT 0")
    except Exception:
        pass

    conn.commit()
    conn.close()


def get_settings(guild_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO boost_reward_settings
    (guild_id, enabled, amount, updated_at)
    VALUES (?,?,?,?)""", (int(guild_id), 0, DEFAULT_BOOST_REWARD_AMOUNT, int(time.time())))
    conn.commit()
    cur.execute("SELECT * FROM boost_reward_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {"guild_id": int(guild_id), "enabled": 0, "amount": DEFAULT_BOOST_REWARD_AMOUNT}


def update_settings(guild_id:int, *, enabled=None, amount=None):
    current = get_settings(guild_id)
    enabled_v = int(current.get("enabled") or 0) if enabled is None else (1 if enabled else 0)
    amount_v = int(current.get("amount") or DEFAULT_BOOST_REWARD_AMOUNT) if amount is None else max(0, int(amount or 0))

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO boost_reward_settings
    (guild_id, enabled, amount, updated_at)
    VALUES (?,?,?,?)
    ON CONFLICT(guild_id) DO UPDATE SET
      enabled=excluded.enabled,
      amount=excluded.amount,
      updated_at=excluded.updated_at""",
    (int(guild_id), enabled_v, amount_v, int(time.time())))
    conn.commit()
    conn.close()


def _upsert_booster(guild_id:int, user_id:int, user_name:str, *, active=None, premium_since=0, add_count=0, add_reward=0):
    ensure_tables()
    now = int(time.time())

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM boosters WHERE guild_id=? AND user_id=?", (int(guild_id), int(user_id)))
    row = cur.fetchone()

    if row:
        old_count = int(row["boost_count"] or 0)
        old_reward = int(row["reward_total"] or 0)
        new_count = max(0, old_count + int(add_count or 0))
        new_reward = max(0, old_reward + int(add_reward or 0))
        first = int(row["first_boost_at"] or 0) or (now if add_count else 0)
        last = now if add_count else int(row["last_boost_at"] or 0)
        new_active = int(row["active"] or 0) if active is None else (1 if active else 0)
        prem = int(premium_since or row["premium_since"] or 0)

        cur.execute("""UPDATE boosters SET
        user_name=?, boost_count=?, reward_total=?, active=?, first_boost_at=?, last_boost_at=?,
        premium_since=?, updated_at=?
        WHERE guild_id=? AND user_id=?""",
        (str(user_name or user_id)[:120], new_count, new_reward, new_active, first, last, prem, now, int(guild_id), int(user_id)))
    else:
        first = now if add_count else 0
        last = now if add_count else 0
        cur.execute("""INSERT INTO boosters
        (guild_id,user_id,user_name,boost_count,reward_total,active,first_boost_at,last_boost_at,premium_since,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(user_id), str(user_name or user_id)[:120], max(0, int(add_count or 0)), max(0, int(add_reward or 0)),
         1 if active else 0, first, last, int(premium_since or 0), now))

    conn.commit()
    conn.close()


def record_boost_message(message):
    if not getattr(message, "guild", None) or not getattr(message, "author", None):
        return {"ok": False, "reason": "no guild/author"}

    ensure_tables()
    settings = get_settings(message.guild.id)
    now = int(time.time())
    event_type = str(getattr(message, "type", "boost"))

    amount = int(settings.get("amount") or 0) if int(settings.get("enabled") or 0) else 0
    tx_id = ""

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM boost_events WHERE guild_id=? AND message_id=?", (int(message.guild.id), int(message.id)))
    exists = cur.fetchone()
    conn.close()

    if exists:
        return {"ok": False, "reason": "already tracked"}

    if amount > 0:
        tx = credit(
            message.guild.id,
            message.author.id,
            amount,
            "boost_reward",
            user_name=message.author.display_name,
            actor_id=message.author.id,
            actor_name=message.author.display_name,
            source_label="server_boost",
            reference_type="message",
            reference_id=str(message.id),
            reason="Server boost reward",
            channel_id=message.channel.id,
            message_id=message.id
        )
        if tx.get("ok"):
            tx_id = tx.get("tx_id") or ""
        else:
            amount = 0

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO boost_events
    (guild_id,user_id,user_name,message_id,channel_id,event_type,amount,money_tx_id,created_at)
    VALUES (?,?,?,?,?,?,?,?,?)""",
    (int(message.guild.id), int(message.author.id), str(message.author.display_name)[:120],
     int(message.id), int(getattr(message.channel, "id", 0) or 0), event_type, int(amount), tx_id, now))
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
            add_count=1,
            add_reward=amount
        )

        record(message.guild.id, message.author.id, message.author.display_name, "server_boost", "Server Boost", f"Boost reward {amount:,}", amount)
        log_event(message.guild.id, "server_boost", message.author.id, message.author.display_name, message.channel.id, message.channel.name, "Server boost detected", f"Amount={amount:,}, TX={tx_id or '-'}")

    return {"ok": bool(inserted), "inserted": bool(inserted), "amount": amount, "tx_id": tx_id}


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

    _upsert_booster(member.guild.id, member.id, member.display_name, active=active, premium_since=premium_since, add_count=0)


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
    COUNT(DISTINCT user_id) unique_boosters,
    COALESCE(SUM(amount),0) total_rewards
    FROM boost_events WHERE guild_id=?""", (int(guild_id),))
    totals = dict(cur.fetchone() or {})

    cur.execute("""SELECT COUNT(*) active_boosters
    FROM boosters WHERE guild_id=? AND active=1""", (int(guild_id),))
    totals.update(dict(cur.fetchone() or {}))

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



def sync_guild_boosters(guild):
    """
    Best-effort full sync for active boosters.

    Sources:
    1. guild.premium_subscribers, if available from discord.py.
    2. member.premium_since from the member cache.
    3. The managed Server Booster role, if Discord exposes it in role tags.

    Notes:
    - This finds ACTIVE boosters.
    - Exact historical number of boosts cannot be recovered from Server Settings/API.
      Exact boost_count is counted from boost system messages after tracking is installed.
    """
    ensure_tables()

    guild_id = int(guild.id)
    now = int(time.time())
    active_ids = set()
    scanned = 0

    # 1) Official cached list if available.
    try:
        for member in getattr(guild, "premium_subscribers", []) or []:
            if member:
                active_ids.add(int(member.id))
                _upsert_booster(
                    guild_id,
                    member.id,
                    member.display_name,
                    active=True,
                    premium_since=int(member.premium_since.timestamp()) if getattr(member, "premium_since", None) else 0,
                    add_count=0,
                    add_reward=0
                )
                scanned += 1
    except Exception:
        pass

    # 2) Any cached member with premium_since.
    try:
        for member in getattr(guild, "members", []) or []:
            if getattr(member, "premium_since", None):
                active_ids.add(int(member.id))
                _upsert_booster(
                    guild_id,
                    member.id,
                    member.display_name,
                    active=True,
                    premium_since=int(member.premium_since.timestamp()),
                    add_count=0,
                    add_reward=0
                )
                scanned += 1
    except Exception:
        pass

    # 3) Managed booster role fallback.
    booster_role = None
    try:
        for role in getattr(guild, "roles", []) or []:
            tags = getattr(role, "tags", None)
            if tags and getattr(tags, "premium_subscriber", False):
                booster_role = role
                break
            # fallback by common name, only if managed role tags are unavailable
            if str(getattr(role, "name", "")).lower() in {"server booster", "nitro booster"}:
                booster_role = role
    except Exception:
        booster_role = None

    if booster_role:
        try:
            for member in getattr(booster_role, "members", []) or []:
                active_ids.add(int(member.id))
                _upsert_booster(
                    guild_id,
                    member.id,
                    member.display_name,
                    active=True,
                    premium_since=int(member.premium_since.timestamp()) if getattr(member, "premium_since", None) else 0,
                    add_count=0,
                    add_reward=0
                )
                scanned += 1
        except Exception:
            pass

    # Mark previously known boosters inactive if they are no longer active.
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM boosters WHERE guild_id=?", (guild_id,))
    known = [int(r["user_id"]) for r in cur.fetchall()]
    for uid in known:
        if uid not in active_ids:
            cur.execute("UPDATE boosters SET active=0, updated_at=? WHERE guild_id=? AND user_id=?", (now, guild_id, uid))
    conn.commit()
    conn.close()

    log_event(guild_id, "boosters_synced", 0, "NM System", 0, "", "Boosters synced", f"Active={len(active_ids)}, Scanned={scanned}")
    return {"active_count": len(active_ids), "scanned": scanned, "booster_role_id": int(getattr(booster_role, "id", 0) or 0)}


# Backward-compatible alias.
def sync_guild(guild):
    return sync_guild_boosters(guild)
