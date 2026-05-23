import os
from nmcore.db import db
from nmcore.config import DB_FILE
from nmcore.services.log_channels import LOG_CHANNELS, all_log_channels
from nmcore.services.settings import all_toggles, get_guild_settings, get_coin_name
from nmcore.services import antiraid


def fmt_size(n:int):
    n = int(n or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def db_size():
    try:
        return os.path.getsize(DB_FILE)
    except Exception:
        return 0


def count_table(guild_id:int, table:str):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) c FROM {table} WHERE guild_id=?", (int(guild_id),))
        row = cur.fetchone()
        conn.close()
        return int(row["c"] or 0)
    except Exception:
        return 0


def money_summary(guild_id:int):
    conn = db()
    cur = conn.cursor()

    out = {
        "balances": 0,
        "total_balance": 0,
        "ledger_rows": 0,
        "money_in": 0,
        "money_out": 0,
        "net": 0,
        "salary_rows": 0,
        "transfer_rows": 0,
        "admin_rows": 0,
    }

    try:
        cur.execute("SELECT COUNT(*) c, COALESCE(SUM(balance),0) total FROM balances WHERE guild_id=?", (int(guild_id),))
        r = cur.fetchone()
        out["balances"] = int(r["c"] or 0)
        out["total_balance"] = int(r["total"] or 0)
    except Exception:
        pass

    try:
        cur.execute("""SELECT COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) money_in,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) money_out,
        COALESCE(SUM(amount),0) net
        FROM money_ledger WHERE guild_id=?""", (int(guild_id),))
        r = cur.fetchone()
        out["ledger_rows"] = int(r["c"] or 0)
        out["money_in"] = int(r["money_in"] or 0)
        out["money_out"] = int(r["money_out"] or 0)
        out["net"] = int(r["net"] or 0)
    except Exception:
        pass

    try:
        cur.execute("SELECT COUNT(*) c FROM money_ledger WHERE guild_id=? AND source_type='salary'", (int(guild_id),))
        out["salary_rows"] = int(cur.fetchone()["c"] or 0)

        cur.execute("SELECT COUNT(*) c FROM money_ledger WHERE guild_id=? AND source_type LIKE 'transfer%'", (int(guild_id),))
        out["transfer_rows"] = int(cur.fetchone()["c"] or 0)

        cur.execute("SELECT COUNT(*) c FROM money_ledger WHERE guild_id=? AND source_type LIKE 'admin%'", (int(guild_id),))
        out["admin_rows"] = int(cur.fetchone()["c"] or 0)
    except Exception:
        pass

    conn.close()
    return out


def casino_summary(guild_id:int):
    conn = db()
    cur = conn.cursor()

    out = {
        "rows": 0,
        "players": 0,
        "casino_took": 0,
        "casino_paid": 0,
        "house_net": 0,
        "games": [],
    }

    try:
        cur.execute("""SELECT COUNT(*) rows,
        COUNT(DISTINCT user_id) players,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid
        FROM money_ledger WHERE guild_id=? AND source_type LIKE 'casino_%'""", (int(guild_id),))
        r = cur.fetchone()
        out["rows"] = int(r["rows"] or 0)
        out["players"] = int(r["players"] or 0)
        out["casino_took"] = int(r["took"] or 0)
        out["casino_paid"] = int(r["paid"] or 0)
        out["house_net"] = out["casino_took"] - out["casino_paid"]

        cur.execute("""SELECT source_label, COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid
        FROM money_ledger
        WHERE guild_id=? AND source_type LIKE 'casino_%'
        GROUP BY source_label ORDER BY c DESC LIMIT 8""", (int(guild_id),))
        out["games"] = [dict(x) for x in cur.fetchall()]
    except Exception:
        pass

    conn.close()
    return out


def protection_summary(guild_id:int):
    conn = db()
    cur = conn.cursor()

    out = {
        "warnings_active": 0,
        "warnings_total": 0,
        "protection_events": 0,
        "antiraid_events": 0,
        "recent_types": [],
    }

    try:
        cur.execute("SELECT COUNT(*) c FROM warnings WHERE guild_id=? AND status='active'", (int(guild_id),))
        out["warnings_active"] = int(cur.fetchone()["c"] or 0)

        cur.execute("SELECT COUNT(*) c FROM warnings WHERE guild_id=?", (int(guild_id),))
        out["warnings_total"] = int(cur.fetchone()["c"] or 0)

        cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=? AND event_type LIKE 'protection_%'", (int(guild_id),))
        out["protection_events"] = int(cur.fetchone()["c"] or 0)

        cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=? AND event_type LIKE 'antiraid_%'", (int(guild_id),))
        out["antiraid_events"] = int(cur.fetchone()["c"] or 0)

        cur.execute("""SELECT event_type, COUNT(*) c FROM log_events
        WHERE guild_id=? AND (event_type LIKE 'protection_%' OR event_type LIKE 'antiraid_%')
        GROUP BY event_type ORDER BY c DESC LIMIT 10""", (int(guild_id),))
        out["recent_types"] = [dict(x) for x in cur.fetchall()]
    except Exception:
        pass

    conn.close()
    return out


def system_overview(guild_id:int):
    mapping = all_log_channels(guild_id)
    mapped = sum(1 for v in mapping.values() if int(v or 0))
    settings = get_guild_settings(guild_id)
    toggles = all_toggles(guild_id)
    ar = antiraid.get_settings(guild_id)

    return {
        "db_file": str(DB_FILE),
        "db_size": fmt_size(db_size()),
        "coin_name": get_coin_name(guild_id),
        "logs_mapped": mapped,
        "logs_total": len(LOG_CHANNELS),
        "settings": dict(settings),
        "toggles": toggles,
        "antiraid_enabled": bool(int(ar.get("enabled", 0) or 0)),
        "antiraid_punish": str(ar.get("punish_action") or "log_only"),
        "commands_channel_id": int(settings.get("commands_channel_id") or 0),
        "gambling_channel_id": int(settings.get("gambling_channel_id") or 0),
    }
