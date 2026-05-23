from nmcore.db import db
from nmcore.config import DB_FILE
from nmcore.services.log_channels import LOG_CHANNELS, all_log_channels
from nmcore.services import antiraid


def table_count(guild_id:int, table:str):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) c FROM {table} WHERE guild_id=?", (int(guild_id),))
        row = cur.fetchone()
        conn.close()
        return int(row["c"] or 0)
    except Exception:
        return 0


def has_table(table:str):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cur.fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def bot_perms(guild):
    me = guild.me
    if not me:
        return {}

    perms = me.guild_permissions
    required = {
        "view_audit_log": "View Audit Log",
        "manage_roles": "Manage Roles",
        "manage_channels": "Manage Channels",
        "manage_messages": "Manage Messages",
        "send_messages": "Send Messages",
        "embed_links": "Embed Links",
        "read_message_history": "Read Message History",
    }

    return {key: bool(getattr(perms, key, False)) for key in required}


def readiness_report(guild):
    gid = int(guild.id)
    mapping = all_log_channels(gid)
    mapped_logs = sum(1 for v in mapping.values() if int(v or 0))
    total_logs = len(LOG_CHANNELS)
    perms = bot_perms(guild)
    ar = antiraid.get_settings(gid)

    checks = []

    def add(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("Database path uses /data", str(DB_FILE).startswith("/data/"), str(DB_FILE))
    add("Money ledger table exists", has_table("money_ledger"), "money_ledger")
    add("Warnings table exists", has_table("warnings"), "warnings")
    add("Log events table exists", has_table("log_events"), "log_events")
    add("Protection settings table exists", has_table("protection_settings"), "protection_settings")
    add("Anti-Raid settings table exists", has_table("antiraid_settings"), "antiraid_settings")
    add("Organized log rooms mapped", mapped_logs == total_logs, f"{mapped_logs}/{total_logs}")
    add("Anti-Raid enabled", int(ar.get("enabled", 0) or 0) == 1, "dashboard/protection")
    add("View Audit Log permission", perms.get("view_audit_log", False), "")
    add("Manage Roles permission", perms.get("manage_roles", False), "")
    add("Embed Links permission", perms.get("embed_links", False), "")
    add("Send Messages permission", perms.get("send_messages", False), "")

    score = int((sum(1 for c in checks if c["ok"]) / max(1, len(checks))) * 100)

    counts = {
        "balances": table_count(gid, "balances"),
        "money_ledger": table_count(gid, "money_ledger"),
        "warnings": table_count(gid, "warnings"),
        "log_events": table_count(gid, "log_events"),
        "live_activity": table_count(gid, "live_activity"),
        "properties": table_count(gid, "properties"),
        "shop_items": table_count(gid, "shop_items"),
        "giveaways": table_count(gid, "giveaways"),
    }

    return {
        "score": score,
        "checks": checks,
        "counts": counts,
        "mapped_logs": mapped_logs,
        "total_logs": total_logs,
        "permissions": perms,
    }
