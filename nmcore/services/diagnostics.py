import os
from nmcore.config import DB_FILE
from nmcore.db import db
from nmcore.services.settings import get_guild_settings, all_toggles
from nmcore.services.log_channels import LOG_CHANNELS, all_log_channels


REQUIRED_BOT_PERMISSIONS = [
    "view_channel",
    "send_messages",
    "embed_links",
    "read_message_history",
    "manage_messages",
    "manage_channels",
    "view_audit_log",
]


def file_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def fmt_size(n:int):
    n = int(n or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def db_counts(guild_id:int):
    conn = db()
    cur = conn.cursor()
    tables = {
        "balances": "balances",
        "money_ledger": "money_ledger",
        "warnings": "warnings",
        "log_events": "log_events",
        "live_activity": "live_activity",
        "properties": "properties",
        "shop_purchases": "shop_purchases",
        "giveaways": "giveaways",
    }

    out = {}

    for label, table in tables.items():
        try:
            cur.execute(f"SELECT COUNT(*) c FROM {table} WHERE guild_id=?", (int(guild_id),))
            out[label] = int(cur.fetchone()["c"] or 0)
        except Exception:
            out[label] = 0

    conn.close()
    return out


def memory_status(guild_id:int):
    counts = db_counts(guild_id)
    data_path_ok = str(DB_FILE).startswith("/data/")

    return {
        "db_file": str(DB_FILE),
        "db_size": file_size(DB_FILE),
        "db_size_text": fmt_size(file_size(DB_FILE)),
        "persistent_path": data_path_ok,
        "counts": counts,
    }


def log_mapping_status(guild_id:int):
    mapping = all_log_channels(guild_id)
    total = len(LOG_CHANNELS)
    mapped = sum(1 for v in mapping.values() if int(v or 0))

    return {
        "mapped": mapped,
        "total": total,
        "mapping": mapping,
    }


def permission_status(guild):
    me = guild.me
    perms = me.guild_permissions if me else None
    result = {}

    for p in REQUIRED_BOT_PERMISSIONS:
        result[p] = bool(getattr(perms, p, False)) if perms else False

    return result


def system_status(guild):
    guild_id = guild.id
    gs = get_guild_settings(guild_id)
    toggles = all_toggles(guild_id)
    mem = memory_status(guild_id)
    logs = log_mapping_status(guild_id)
    perms = permission_status(guild)

    return {
        "guild_settings": gs,
        "toggles": toggles,
        "memory": mem,
        "logs": logs,
        "permissions": perms,
    }
