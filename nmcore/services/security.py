from nmcore.db import db
from nmcore.services import antiraid


DANGEROUS_PERMS = [
    ("administrator", "Administrator"),
    ("manage_guild", "Manage Server"),
    ("manage_roles", "Manage Roles"),
    ("manage_channels", "Manage Channels"),
    ("ban_members", "Ban Members"),
    ("kick_members", "Kick Members"),
    ("manage_webhooks", "Manage Webhooks"),
    ("manage_messages", "Manage Messages"),
    ("mention_everyone", "Mention Everyone"),
]


def dangerous_roles(guild):
    rows = []

    for role in getattr(guild, "roles", []):
        if getattr(role, "name", "") == "@everyone":
            continue

        perms = []
        for attr, label in DANGEROUS_PERMS:
            try:
                if bool(getattr(role.permissions, attr, False)):
                    perms.append(label)
            except Exception:
                pass

        if perms:
            rows.append({
                "id": int(role.id),
                "name": role.name,
                "position": int(role.position),
                "members": len(getattr(role, "members", []) or []),
                "permissions": perms,
                "managed": bool(getattr(role, "managed", False)),
            })

    rows.sort(key=lambda x: x["position"], reverse=True)
    return rows


def bot_permission_status(guild):
    me = guild.me
    if not me:
        return {}

    perms = me.guild_permissions

    needed = {
        "view_audit_log": "View Audit Log",
        "manage_roles": "Manage Roles",
        "manage_channels": "Manage Channels",
        "manage_messages": "Manage Messages",
        "send_messages": "Send Messages",
        "embed_links": "Embed Links",
        "read_message_history": "Read Message History",
    }

    return {key: {"label": label, "ok": bool(getattr(perms, key, False))} for key, label in needed.items()}


def recent_security_events(guild_id:int, limit:int=100):
    conn = db()
    cur = conn.cursor()
    cur.execute("""SELECT * FROM log_events
    WHERE guild_id=? AND (
        event_type LIKE 'antiraid_%'
        OR event_type LIKE 'protection_%'
        OR event_type IN ('member_kick','member_ban','member_roles_update','channel_delete','channel_create','channel_update')
    )
    ORDER BY id DESC LIMIT ?""", (int(guild_id), int(limit)))
    rows = cur.fetchall()
    conn.close()
    return rows


def warning_security_counts(guild_id:int):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) c FROM warnings WHERE guild_id=? AND status='active'", (int(guild_id),))
    active_warnings = int(cur.fetchone()["c"] or 0)

    cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=? AND event_type LIKE 'antiraid_%'", (int(guild_id),))
    antiraid_events = int(cur.fetchone()["c"] or 0)

    cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=? AND event_type LIKE 'protection_%'", (int(guild_id),))
    protection_events = int(cur.fetchone()["c"] or 0)

    conn.close()

    return {
        "active_warnings": active_warnings,
        "antiraid_events": antiraid_events,
        "protection_events": protection_events,
    }


def risk_report(guild):
    guild_id = int(guild.id)
    ar = antiraid.get_settings(guild_id)
    perms = bot_permission_status(guild)
    roles = dangerous_roles(guild)
    counts = warning_security_counts(guild_id)

    issues = []
    score = 100

    if not int(ar.get("enabled", 1) or 0):
        issues.append("Anti-Raid is OFF")
        score -= 25

    if str(ar.get("punish_action") or "log_only") == "log_only":
        issues.append("Anti-Raid punishment is Log Only")
        score -= 8

    for key in ["view_audit_log", "manage_roles", "send_messages", "embed_links"]:
        if not perms.get(key, {}).get("ok"):
            issues.append(f"Bot missing permission: {perms.get(key, {}).get('label', key)}")
            score -= 12

    high_roles = [r for r in roles if "Administrator" in r["permissions"]]
    if len(high_roles) >= 3:
        issues.append(f"Many Administrator roles: {len(high_roles)}")
        score -= 10

    if counts["active_warnings"] >= 10:
        issues.append(f"Many active warnings: {counts['active_warnings']}")
        score -= 5

    score = max(0, min(100, score))

    if score >= 85:
        label = "Good"
    elif score >= 65:
        label = "Medium"
    else:
        label = "Risky"

    return {
        "score": score,
        "label": label,
        "issues": issues,
        "roles": roles,
        "permissions": perms,
        "counts": counts,
        "antiraid": ar,
    }
