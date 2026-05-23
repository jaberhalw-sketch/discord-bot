import time
from collections import defaultdict, deque
from nmcore.db import db


_actions = defaultdict(deque)


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
    "anti_bot_add": 1,
    "threshold": 3,
    "window": 60,
    "punish_action": "remove_roles",  # none / remove_roles
    "trusted_users": "",
    "trusted_roles": "",
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
        anti_bot_add INTEGER DEFAULT 1,
        threshold INTEGER DEFAULT 3,
        window INTEGER DEFAULT 60,
        punish_action TEXT DEFAULT 'remove_roles',
        trusted_users TEXT DEFAULT '',
        trusted_roles TEXT DEFAULT '',
        updated_at INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()


def get_settings(guild_id:int) -> dict:
    ensure_schema()
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO antiraid_settings (guild_id,updated_at) VALUES (?,?)", (int(guild_id), int(time.time())))
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
        return True

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
        "member_role_update": "anti_member_role_update",
        "channel_create": "anti_channel_create",
        "channel_delete": "anti_channel_delete",
        "channel_update": "anti_channel_update",
        "webhook_create": "anti_webhook_create",
        "bot_add": "anti_bot_add",
    }
    key = mapping.get(action_type)
    if not key:
        return False
    return bool(int(settings.get("enabled", 1) or 0)) and bool(int(settings.get(key, 1) or 0))


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


async def punish_member(member, settings):
    action = str(settings.get("punish_action") or "none")

    if not member or action == "none":
        return "none"

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
