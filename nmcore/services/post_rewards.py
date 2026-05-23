import time
from nmcore.db import db
from nmcore.services.economy import credit
from nmcore.services.activity import record, log_event


DEFAULT_AMOUNT = 5000
DEFAULT_MIN_LENGTH = 5
DEFAULT_COOLDOWN_SECONDS = 0


def ensure_tables():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS post_reward_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 0,
        amount INTEGER DEFAULT 5000,
        channel_ids TEXT DEFAULT '',
        min_length INTEGER DEFAULT 5,
        cooldown_seconds INTEGER DEFAULT 0,
        updated_at INTEGER DEFAULT 0
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS post_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        channel_id INTEGER NOT NULL DEFAULT 0,
        message_id INTEGER NOT NULL DEFAULT 0,
        amount INTEGER NOT NULL DEFAULT 0,
        money_tx_id TEXT DEFAULT '',
        created_at INTEGER NOT NULL DEFAULT 0,
        UNIQUE(guild_id, message_id)
    )""")

    conn.commit()
    conn.close()


def get_settings(guild_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO post_reward_settings
    (guild_id,enabled,amount,channel_ids,min_length,cooldown_seconds,updated_at)
    VALUES (?,?,?,?,?,?,?)""", (int(guild_id), 0, DEFAULT_AMOUNT, "", DEFAULT_MIN_LENGTH, DEFAULT_COOLDOWN_SECONDS, int(time.time())))
    conn.commit()
    cur.execute("SELECT * FROM post_reward_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {
        "guild_id": int(guild_id),
        "enabled": 0,
        "amount": DEFAULT_AMOUNT,
        "channel_ids": "",
        "min_length": DEFAULT_MIN_LENGTH,
        "cooldown_seconds": DEFAULT_COOLDOWN_SECONDS,
    }


def update_settings(guild_id:int, *, enabled=None, amount=None, channel_ids=None, min_length=None, cooldown_seconds=None):
    ensure_tables()
    current = get_settings(guild_id)

    data = {
        "enabled": int(current.get("enabled") or 0),
        "amount": int(current.get("amount") or DEFAULT_AMOUNT),
        "channel_ids": str(current.get("channel_ids") or ""),
        "min_length": int(current.get("min_length") or DEFAULT_MIN_LENGTH),
        "cooldown_seconds": int(current.get("cooldown_seconds") or DEFAULT_COOLDOWN_SECONDS),
    }

    if enabled is not None:
        data["enabled"] = 1 if enabled else 0
    if amount is not None:
        data["amount"] = max(0, int(amount or DEFAULT_AMOUNT))
    if channel_ids is not None:
        data["channel_ids"] = str(channel_ids or "").strip()
    if min_length is not None:
        data["min_length"] = max(0, int(min_length or 0))
    if cooldown_seconds is not None:
        data["cooldown_seconds"] = max(0, int(cooldown_seconds or 0))

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO post_reward_settings
    (guild_id,enabled,amount,channel_ids,min_length,cooldown_seconds,updated_at)
    VALUES (?,?,?,?,?,?,?)
    ON CONFLICT(guild_id) DO UPDATE SET
      enabled=excluded.enabled,
      amount=excluded.amount,
      channel_ids=excluded.channel_ids,
      min_length=excluded.min_length,
      cooldown_seconds=excluded.cooldown_seconds,
      updated_at=excluded.updated_at""",
    (int(guild_id), data["enabled"], data["amount"], data["channel_ids"], data["min_length"], data["cooldown_seconds"], int(time.time())))
    conn.commit()
    conn.close()


def _ids(text):
    out = set()
    for part in str(text or "").replace("\n", ",").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def configured_channel_ids(guild_id:int):
    return _ids(get_settings(guild_id).get("channel_ids"))


def already_rewarded(guild_id:int, message_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM post_rewards WHERE guild_id=? AND message_id=?", (int(guild_id), int(message_id)))
    row = cur.fetchone()
    conn.close()
    return bool(row)


def last_user_reward_at(guild_id:int, user_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""SELECT created_at FROM post_rewards
    WHERE guild_id=? AND user_id=?
    ORDER BY id DESC LIMIT 1""", (int(guild_id), int(user_id)))
    row = cur.fetchone()
    conn.close()
    return int(row["created_at"] or 0) if row else 0


def should_reward_message(message):
    if not message.guild or message.author.bot:
        return False, "bot/no guild"

    settings = get_settings(message.guild.id)

    if not int(settings.get("enabled") or 0):
        return False, "disabled"

    channels = _ids(settings.get("channel_ids"))
    if channels and int(message.channel.id) not in channels:
        return False, "wrong channel"

    content = str(getattr(message, "content", "") or "").strip()
    attachments = list(getattr(message, "attachments", []) or [])
    min_length = int(settings.get("min_length") or 0)

    if len(content) < min_length and not attachments:
        return False, "too short"

    if already_rewarded(message.guild.id, message.id):
        return False, "already rewarded"

    cooldown = int(settings.get("cooldown_seconds") or 0)
    if cooldown > 0:
        last = last_user_reward_at(message.guild.id, message.author.id)
        if last and int(time.time()) - last < cooldown:
            return False, "cooldown"

    return True, "ok"


def reward_message(message):
    ok, reason = should_reward_message(message)
    if not ok:
        return {"ok": False, "reason": reason}

    settings = get_settings(message.guild.id)
    amount = int(settings.get("amount") or DEFAULT_AMOUNT)

    tx = credit(
        message.guild.id,
        message.author.id,
        amount,
        "post_reward",
        user_name=message.author.display_name,
        actor_id=message.author.id,
        actor_name=message.author.display_name,
        source_label="post",
        reference_type="message",
        reference_id=str(message.id),
        reason="Post reward",
        channel_id=message.channel.id,
        message_id=message.id
    )

    if not tx.get("ok"):
        return {"ok": False, "reason": "credit failed"}

    now = int(time.time())
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO post_rewards
    (guild_id,user_id,user_name,channel_id,message_id,amount,money_tx_id,created_at)
    VALUES (?,?,?,?,?,?,?,?)""",
    (int(message.guild.id), int(message.author.id), str(message.author.display_name)[:120], int(message.channel.id), int(message.id), amount, tx["tx_id"], now))
    conn.commit()
    conn.close()

    record(message.guild.id, message.author.id, message.author.display_name, "post_reward", "Post reward", f"{amount:,}", amount)
    log_event(message.guild.id, "post_reward", message.author.id, message.author.display_name, message.channel.id, message.channel.name, "Post reward", f"+{amount:,} for message {message.id}")

    return {"ok": True, "amount": amount, "tx_id": tx["tx_id"]}


def summary(guild_id:int, limit:int=50):
    ensure_tables()
    conn = db()
    cur = conn.cursor()

    cur.execute("""SELECT COUNT(*) c, COALESCE(SUM(amount),0) total
    FROM post_rewards WHERE guild_id=?""", (int(guild_id),))
    totals = dict(cur.fetchone() or {})

    cur.execute("""SELECT user_id,user_name,COUNT(*) posts,COALESCE(SUM(amount),0) total
    FROM post_rewards WHERE guild_id=?
    GROUP BY user_id,user_name ORDER BY total DESC LIMIT ?""", (int(guild_id), int(limit)))
    top = [dict(x) for x in cur.fetchall()]

    cur.execute("""SELECT * FROM post_rewards
    WHERE guild_id=? ORDER BY id DESC LIMIT ?""", (int(guild_id), int(limit)))
    recent = [dict(x) for x in cur.fetchall()]

    conn.close()
    return {"totals": totals, "top": top, "recent": recent}
