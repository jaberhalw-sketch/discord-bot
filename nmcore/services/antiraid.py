import time
import json
from collections import defaultdict, deque
from nmcore.db import db


_actions = defaultdict(deque)
_recent_action_keys = {}


DEFAULTS = {
    "enabled": 1,

    "anti_kick": 1,
    "anti_ban": 1,
    "anti_role_delete": 1,
    "anti_role_update": 1,
    "anti_member_role_update": 1,
    "anti_channel_create": 1,
    "anti_channel_delete": 1,
    "anti_channel_update": 1,
    "anti_webhook_create": 1,
    "anti_webhook_update": 1,
    "anti_webhook_delete": 1,
    "anti_bot_add": 1,

    "dangerous_role_protection": 1,

    "threshold": 3,
    "window": 60,
    "punish_action": "log_only",  # log_only / remove_roles
    "trusted_users": "",
    "trusted_roles": "",
}


DANGEROUS_PERMS = [
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "ban_members",
    "kick_members",
    "manage_webhooks",
    "manage_messages",
    "mention_everyone",
]


ACTION_RISK_POINTS = {
    "kick": 12,
    "ban": 18,
    "role_delete": 20,
    "role_update": 10,
    "dangerous_role_update": 28,
    "member_role_update": 8,
    "channel_create": 8,
    "channel_delete": 18,
    "channel_update": 8,
    "webhook_create": 22,
    "webhook_update": 14,
    "webhook_delete": 18,
    "bot_add": 30,
}


def ensure_schema():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS antiraid_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        anti_kick INTEGER DEFAULT 1,
        anti_ban INTEGER DEFAULT 1,
        anti_role_delete INTEGER DEFAULT 1,
        anti_role_update INTEGER DEFAULT 1,
        anti_member_role_update INTEGER DEFAULT 1,
        anti_channel_create INTEGER DEFAULT 1,
        anti_channel_delete INTEGER DEFAULT 1,
        anti_channel_update INTEGER DEFAULT 1,
        anti_webhook_create INTEGER DEFAULT 1,
        anti_webhook_update INTEGER DEFAULT 1,
        anti_webhook_delete INTEGER DEFAULT 1,
        anti_bot_add INTEGER DEFAULT 1,
        dangerous_role_protection INTEGER DEFAULT 1,
        threshold INTEGER DEFAULT 3,
        window INTEGER DEFAULT 60,
        punish_action TEXT DEFAULT 'log_only',
        trusted_users TEXT DEFAULT '',
        trusted_roles TEXT DEFAULT '',
        updated_at INTEGER DEFAULT 0
    )""")

    extra = {
        "anti_webhook_update": "INTEGER DEFAULT 1",
        "anti_webhook_delete": "INTEGER DEFAULT 1",
        "dangerous_role_protection": "INTEGER DEFAULT 1",
    }

    for col, sql in extra.items():
        try:
            cur.execute(f"ALTER TABLE antiraid_settings ADD COLUMN {col} {sql}")
        except Exception:
            pass

    cur.execute("""CREATE TABLE IF NOT EXISTS admin_audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        executor_id INTEGER DEFAULT 0,
        executor_name TEXT DEFAULT '',
        target_id INTEGER DEFAULT 0,
        target_text TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        count INTEGER DEFAULT 0,
        threshold INTEGER DEFAULT 0,
        window INTEGER DEFAULT 0,
        triggered INTEGER DEFAULT 0,
        duplicate INTEGER DEFAULT 0,
        trusted INTEGER DEFAULT 0,
        punishment TEXT DEFAULT '',
        risk_points INTEGER DEFAULT 0,
        metadata TEXT DEFAULT '',
        created_at INTEGER DEFAULT 0
    )""")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_guild_time ON admin_audit_events (guild_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_executor ON admin_audit_events (guild_id, executor_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_action ON admin_audit_events (guild_id, action_type, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_triggered ON admin_audit_events (guild_id, triggered, created_at)",
    ]

    for sql in indexes:
        try:
            cur.execute(sql)
        except Exception:
            pass

    conn.commit()
    conn.close()


def get_settings(guild_id:int) -> dict:
    ensure_schema()
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO antiraid_settings (guild_id,updated_at) VALUES (?,?)",
        (int(guild_id), int(time.time()))
    )
    conn.commit()
    cur.execute("SELECT * FROM antiraid_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()
    conn.close()

    data = dict(row) if row else {}
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data


def update_settings(guild_id:int, data:dict):
    ensure_schema()

    vals = {}
    for k in DEFAULTS.keys():
        if k in data:
            vals[k] = data[k]

    if not vals:
        return

    conn = db()
    cur = conn.cursor()
    sets = ", ".join([f"{k}=?" for k in vals]) + ", updated_at=?"
    params = list(vals.values()) + [int(time.time()), int(guild_id)]
    cur.execute(f"UPDATE antiraid_settings SET {sets} WHERE guild_id=?", params)
    conn.commit()
    conn.close()


def list_from_text(value):
    return [x.strip() for x in str(value or "").replace("\n", ",").split(",") if x.strip()]


def int_set(value):
    return {int(x) for x in list_from_text(value) if str(x).isdigit()}


def is_trusted(settings, member):
    if not member:
        return False

    if int(getattr(member, "id", 0)) in int_set(settings.get("trusted_users")):
        return True

    trusted_roles = int_set(settings.get("trusted_roles"))
    if trusted_roles and any(int(getattr(r, "id", 0)) in trusted_roles for r in getattr(member, "roles", [])):
        return True

    return False


def feature_enabled(settings, action_type):
    mapping = {
        "kick": "anti_kick",
        "ban": "anti_ban",
        "role_delete": "anti_role_delete",
        "role_update": "anti_role_update",
        "dangerous_role_update": "dangerous_role_protection",
        "member_role_update": "anti_member_role_update",
        "channel_create": "anti_channel_create",
        "channel_delete": "anti_channel_delete",
        "channel_update": "anti_channel_update",
        "webhook_create": "anti_webhook_create",
        "webhook_update": "anti_webhook_update",
        "webhook_delete": "anti_webhook_delete",
        "bot_add": "anti_bot_add",
    }

    key = mapping.get(action_type)
    if not key:
        return False

    return bool(int(settings.get("enabled", 1) or 0)) and bool(int(settings.get(key, 1) or 0))


def risk_points_for(action_type:str, triggered=False, duplicate=False, trusted=False):
    if duplicate:
        return 0

    base = int(ACTION_RISK_POINTS.get(str(action_type or ""), 5) or 5)

    if trusted:
        return max(1, base // 4)

    if triggered:
        return base + 35

    return base


def is_duplicate_action(guild_id:int, user_id:int, action_type:str, target_key:str="", seconds:int=10) -> bool:
    """
    Prevent the same Discord audit-log action from being counted twice.

    Example fixed case:
    - A ban can trigger on_member_remove and on_member_ban.
    - Without dedupe, one ban can become Count 1/2 then Count 2/2.

    Key format:
    guild + executor + action_type + target
    """
    now = time.time()
    seconds = max(3, int(seconds or 10))

    expire_after = seconds * 6
    for key, last in list(_recent_action_keys.items()):
        try:
            if now - float(last) > expire_after:
                _recent_action_keys.pop(key, None)
        except Exception:
            _recent_action_keys.pop(key, None)

    key = (
        int(guild_id or 0),
        int(user_id or 0),
        str(action_type or ""),
        str(target_key or ""),
    )

    last = _recent_action_keys.get(key)
    if last and now - float(last) <= seconds:
        return True

    _recent_action_keys[key] = now
    return False


def record_action(guild_id:int, user_id:int, action_type:str, settings:dict):
    threshold = max(1, int(settings.get("threshold", 3) or 3))
    window = max(5, int(settings.get("window", 60) or 60))
    now = time.time()
    key = (int(guild_id), int(user_id), str(action_type))
    q = _actions[key]
    q.append(now)

    while q and now - q[0] > window:
        q.popleft()

    return {
        "count": len(q),
        "threshold": threshold,
        "window": window,
        "triggered": len(q) >= threshold,
    }


def log_admin_event(
    guild_id:int,
    action_type:str,
    executor_id:int=0,
    executor_name:str="",
    target_id:int=0,
    target_text:str="",
    reason:str="",
    count:int=0,
    threshold:int=0,
    window:int=0,
    triggered=False,
    duplicate=False,
    trusted=False,
    punishment:str="",
    metadata=None,
):
    ensure_schema()

    try:
        meta_text = json.dumps(metadata or {}, ensure_ascii=False)[:4000]
    except Exception:
        meta_text = "{}"

    triggered_i = 1 if triggered else 0
    duplicate_i = 1 if duplicate else 0
    trusted_i = 1 if trusted else 0
    risk = risk_points_for(action_type, triggered=triggered_i, duplicate=duplicate_i, trusted=trusted_i)

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO admin_audit_events
    (guild_id, action_type, executor_id, executor_name, target_id, target_text, reason,
     count, threshold, window, triggered, duplicate, trusted, punishment, risk_points, metadata, created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        int(guild_id or 0),
        str(action_type or "")[:80],
        int(executor_id or 0),
        str(executor_name or "")[:160],
        int(target_id or 0),
        str(target_text or "")[:600],
        str(reason or "")[:800],
        int(count or 0),
        int(threshold or 0),
        int(window or 0),
        triggered_i,
        duplicate_i,
        trusted_i,
        str(punishment or "")[:160],
        int(risk or 0),
        meta_text,
        int(time.time()),
    ))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def dangerous_perms_added(before_perms, after_perms):
    added = []
    for name in DANGEROUS_PERMS:
        try:
            if not bool(getattr(before_perms, name, False)) and bool(getattr(after_perms, name, False)):
                added.append(name)
        except Exception:
            pass
    return added


async def punish_member(member, settings):
    action = str(settings.get("punish_action") or "log_only")

    if not member or action in {"log_only", "none"}:
        return "log_only"

    if action == "remove_roles":
        removed = 0
        reason = "NM Anti-Raid triggered"

        roles = [
            r for r in getattr(member, "roles", [])
            if getattr(r, "name", "") != "@everyone" and getattr(r, "managed", False) is False
        ]

        for role in roles:
            try:
                if member.guild.me.top_role > role:
                    await member.remove_roles(role, reason=reason)
                    removed += 1
            except Exception:
                pass

        return f"removed_roles:{removed}"

    return "none"


def settings_summary(guild_id:int):
    s = get_settings(guild_id)
    enabled_count = sum(1 for k in DEFAULTS if k.startswith("anti_") and int(s.get(k, 0) or 0))
    return {
        "enabled": bool(int(s.get("enabled", 1) or 0)),
        "enabled_features": enabled_count,
        "threshold": int(s.get("threshold", 3) or 3),
        "window": int(s.get("window", 60) or 60),
        "punish_action": str(s.get("punish_action") or "log_only"),
    }


def risk_label(score:int):
    score = int(score or 0)
    if score >= 180:
        return "Critical"
    if score >= 90:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def admin_audit_totals(guild_id:int):
    ensure_schema()
    conn = db()
    cur = conn.cursor()
    cur.execute("""SELECT
        COUNT(*) events,
        COUNT(DISTINCT executor_id) admins,
        COALESCE(SUM(CASE WHEN triggered=1 THEN 1 ELSE 0 END),0) triggered,
        COALESCE(SUM(CASE WHEN duplicate=1 THEN 1 ELSE 0 END),0) duplicates,
        COALESCE(SUM(CASE WHEN trusted=1 THEN 1 ELSE 0 END),0) trusted,
        COALESCE(SUM(risk_points),0) risk
    FROM admin_audit_events
    WHERE guild_id=?""", (int(guild_id),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {"events":0,"admins":0,"triggered":0,"duplicates":0,"trusted":0,"risk":0}


def admin_audit_summary(guild_id:int, limit:int=50):
    ensure_schema()
    conn = db()
    cur = conn.cursor()
    cur.execute("""SELECT
        executor_id,
        executor_name,
        COUNT(*) events,
        COALESCE(SUM(risk_points),0) risk,
        COALESCE(SUM(CASE WHEN triggered=1 THEN 1 ELSE 0 END),0) triggered,
        COALESCE(SUM(CASE WHEN duplicate=1 THEN 1 ELSE 0 END),0) duplicates,
        COALESCE(SUM(CASE WHEN trusted=1 THEN 1 ELSE 0 END),0) trusted,
        COALESCE(SUM(CASE WHEN created_at >= strftime('%s','now') - 86400 THEN 1 ELSE 0 END),0) last_24h,
        COALESCE(MAX(created_at),0) last_seen
    FROM admin_audit_events
    WHERE guild_id=? AND executor_id != 0
    GROUP BY executor_id, executor_name
    ORDER BY risk DESC, events DESC
    LIMIT ?""", (int(guild_id), max(1, min(int(limit or 50), 200))))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for row in rows:
        row["risk_label"] = risk_label(row.get("risk", 0))

    return rows
