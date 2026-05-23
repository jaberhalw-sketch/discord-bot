import os
from nmcore.config import DB_FILE
from nmcore.db import db
from nmcore.services.log_channels import LOG_CHANNELS, all_log_channels
from nmcore.services.settings import all_toggles, get_guild_settings
from nmcore.services import antiraid


CORE_TABLES = [
    "guild_settings",
    "balances",
    "money_ledger",
    "warnings",
    "levels",
    "properties",
    "property_ledger",
    "log_events",
    "live_activity",
    "protection_settings",
    "antiraid_settings",
    "log_channel_settings",
    "shop_items",
    "shop_purchases",
    "giveaways",
    "giveaway_entries",
    "giveaway_winners",
]


REQUIRED_PERMS = {
    "view_channel": "View Channel",
    "send_messages": "Send Messages",
    "embed_links": "Embed Links",
    "read_message_history": "Read Message History",
    "manage_messages": "Manage Messages",
    "manage_channels": "Manage Channels",
    "view_audit_log": "View Audit Log",
    "manage_roles": "Manage Roles",
}


def table_exists(table):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cur.fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def table_count(guild_id, table):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) c FROM {table} WHERE guild_id=?", (int(guild_id),))
        row = cur.fetchone()
        conn.close()
        return int(row["c"] or 0)
    except Exception:
        return 0


def db_file_ok():
    path = str(DB_FILE)
    exists = os.path.exists(path)
    persistent = path.startswith("/data/")
    size = os.path.getsize(path) if exists else 0

    return {
        "path": path,
        "exists": exists,
        "persistent": persistent,
        "size": size,
    }


def fmt_size(n):
    n = int(n or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}"
        n = n / 1024
    return f"{n:.1f} TB"


def permission_checks(guild):
    me = guild.me
    if not me:
        return {k: False for k in REQUIRED_PERMS}

    perms = me.guild_permissions
    return {k: bool(getattr(perms, k, False)) for k in REQUIRED_PERMS}


def feature_counts(guild_id):
    return {
        "balances": table_count(guild_id, "balances"),
        "ledger": table_count(guild_id, "money_ledger"),
        "warnings": table_count(guild_id, "warnings"),
        "levels": table_count(guild_id, "levels"),
        "properties": table_count(guild_id, "properties"),
        "logs": table_count(guild_id, "log_events"),
        "live": table_count(guild_id, "live_activity"),
        "shop_items": table_count(guild_id, "shop_items"),
        "shop_purchases": table_count(guild_id, "shop_purchases"),
        "giveaways": table_count(guild_id, "giveaways"),
    }


def run_full_check(guild):
    guild_id = int(guild.id)
    db_status = db_file_ok()
    table_status = {t: table_exists(t) for t in CORE_TABLES}
    perms = permission_checks(guild)
    log_map = all_log_channels(guild_id)
    mapped_logs = sum(1 for v in log_map.values() if int(v or 0))
    toggles = all_toggles(guild_id)
    settings = get_guild_settings(guild_id)
    ar = antiraid.get_settings(guild_id)
    counts = feature_counts(guild_id)

    checks = []

    def add(category, name, ok, detail="", weight=1):
        checks.append({
            "category": category,
            "name": name,
            "ok": bool(ok),
            "detail": str(detail or ""),
            "weight": int(weight or 1),
        })

    add("Memory", "DB file exists", db_status["exists"], db_status["path"], 3)
    add("Memory", "DB uses Railway volume /data", db_status["persistent"], db_status["path"], 5)

    for table, ok in table_status.items():
        add("Database", f"Table: {table}", ok, table, 1)

    add("Logs", "Organized log rooms mapped", mapped_logs == len(LOG_CHANNELS), f"{mapped_logs}/{len(LOG_CHANNELS)}", 4)

    for key, label in REQUIRED_PERMS.items():
        important = key in {"send_messages", "embed_links", "view_audit_log", "manage_roles"}
        add("Permissions", label, perms.get(key, False), key, 3 if important else 1)

    add("Settings", "Commands channel setting readable", "commands_channel_id" in settings.keys(), str(settings.get("commands_channel_id", 0)), 1)
    add("Settings", "Gambling channel setting readable", "gambling_channel_id" in settings.keys(), str(settings.get("gambling_channel_id", 0)), 1)
    add("Settings", "System toggles loaded", bool(toggles), f"{len(toggles)} toggles", 2)

    add("Protection", "Anti-Raid enabled", int(ar.get("enabled", 0) or 0) == 1, "dashboard/protection", 3)
    add("Protection", "Anti Kick enabled", int(ar.get("anti_kick", 0) or 0) == 1, "", 1)
    add("Protection", "Anti Ban enabled", int(ar.get("anti_ban", 0) or 0) == 1, "", 1)
    add("Protection", "Anti Channel Delete enabled", int(ar.get("anti_channel_delete", 0) or 0) == 1, "", 1)
    add("Protection", "Anti Role Edit enabled", int(ar.get("anti_role_update", 0) or 0) == 1, "", 1)

    # Feature readiness by tables; data can be 0 if not used yet, so this is informational and not a failure.
    add("Features", "Economy tables ready", table_status.get("balances") and table_status.get("money_ledger"), f"balances={counts['balances']} ledger={counts['ledger']}", 3)
    add("Features", "Warnings table ready", table_status.get("warnings"), f"warnings={counts['warnings']}", 2)
    add("Features", "Levels table ready", table_status.get("levels"), f"levels={counts['levels']}", 2)
    add("Features", "Real Estate tables ready", table_status.get("properties") and table_status.get("property_ledger"), f"properties={counts['properties']}", 2)
    add("Features", "Shop tables ready", table_status.get("shop_items") and table_status.get("shop_purchases"), f"items={counts['shop_items']}", 2)
    add("Features", "Giveaway tables ready", table_status.get("giveaways") and table_status.get("giveaway_entries"), f"giveaways={counts['giveaways']}", 2)

    total_weight = sum(c["weight"] for c in checks)
    ok_weight = sum(c["weight"] for c in checks if c["ok"])
    score = int((ok_weight / max(1, total_weight)) * 100)

    if score >= 90:
        label = "Ready"
    elif score >= 75:
        label = "Almost Ready"
    elif score >= 60:
        label = "Needs Fixes"
    else:
        label = "Not Ready"

    failed = [c for c in checks if not c["ok"]]
    passed = [c for c in checks if c["ok"]]

    return {
        "score": score,
        "label": label,
        "checks": checks,
        "failed": failed,
        "passed": passed,
        "counts": counts,
        "db": {
            **db_status,
            "size_text": fmt_size(db_status["size"]),
        },
        "logs": {
            "mapped": mapped_logs,
            "total": len(LOG_CHANNELS),
        },
        "permissions": perms,
    }
