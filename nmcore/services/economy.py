import os
import time
import uuid
import json
from nmcore.db import db
from nmcore.services.activity import record

MAX_TX_AMOUNT = int(os.getenv("MAX_TX_AMOUNT", "1000000000000"))  # 1 trillion default


def now_ts() -> int:
    return int(time.time())


def clean_amount(amount):
    try:
        amount = int(amount)
    except Exception:
        return None

    if amount <= 0:
        return None

    if amount > MAX_TX_AMOUNT:
        return None

    return amount


def ensure_balance(guild_id:int, user_id:int):
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO balances (guild_id,user_id,balance,last_salary,updated_at)
    VALUES (?,?,0,0,?)""", (int(guild_id), int(user_id), now_ts()))
    conn.commit()
    conn.close()


def get_balance(guild_id:int, user_id:int) -> int:
    ensure_balance(guild_id, user_id)

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (int(guild_id), int(user_id)))
    row = cur.fetchone()
    conn.close()

    return int(row["balance"] or 0) if row else 0


def _insert_ledger_row(
    cur,
    tx_id,
    guild_id,
    user_id,
    user_name,
    actor_id,
    actor_name,
    amount,
    before,
    after,
    source_type,
    source_label="",
    reason="",
    reference_type="",
    reference_id="",
    related_user_id=0,
    channel_id=0,
    message_id=0,
    metadata=None
):
    cur.execute("""INSERT INTO money_ledger
    (tx_id,guild_id,user_id,user_name,actor_id,actor_name,amount,balance_before,balance_after,source_type,source_label,reason,reference_type,reference_id,related_user_id,channel_id,message_id,metadata_json,created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        str(tx_id),
        int(guild_id),
        int(user_id),
        str(user_name or "")[:120],
        int(actor_id or 0),
        str(actor_name or "")[:120],
        int(amount),
        int(before),
        int(after),
        str(source_type)[:80],
        str(source_label or "")[:80],
        str(reason or "")[:500],
        str(reference_type or "")[:80],
        str(reference_id or "")[:120],
        int(related_user_id or 0),
        int(channel_id or 0),
        int(message_id or 0),
        json.dumps(metadata or {}, ensure_ascii=False),
        now_ts()
    ))


def tx(
    guild_id:int,
    user_id:int,
    amount:int,
    source_type:str,
    user_name="",
    actor_id=0,
    actor_name="",
    source_label="",
    reason="",
    reference_type="",
    reference_id="",
    related_user_id=0,
    channel_id=0,
    message_id=0,
    metadata=None
):
    gid = int(guild_id)
    uid = int(user_id)

    try:
        amount = int(amount)
    except Exception:
        return {"ok": False, "error": "invalid_amount", "before": 0, "after": 0, "amount": 0}

    if amount == 0:
        return {"ok": False, "error": "zero_amount", "before": get_balance(gid, uid), "after": get_balance(gid, uid), "amount": 0}

    if abs(amount) > MAX_TX_AMOUNT:
        before = get_balance(gid, uid)
        return {"ok": False, "error": "amount_too_large", "before": before, "after": before, "amount": amount}

    ensure_balance(gid, uid)

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (gid, uid))
        row = cur.fetchone()
        before = int(row["balance"] or 0) if row else 0
        after = before + amount

        if after < 0:
            conn.rollback()
            conn.close()
            return {"ok": False, "error": "insufficient_funds", "before": before, "after": before, "amount": amount}

        cur.execute(
            "UPDATE balances SET balance=?, updated_at=? WHERE guild_id=? AND user_id=?",
            (after, now_ts(), gid, uid)
        )

        tx_id = uuid.uuid4().hex
        _insert_ledger_row(
            cur, tx_id, gid, uid, user_name, actor_id, actor_name, amount, before, after,
            source_type, source_label, reason, reference_type, reference_id, related_user_id,
            channel_id, message_id, metadata
        )

        conn.commit()
        conn.close()

        record(gid, actor_id or uid, actor_name or user_name, "money", f"{source_type}: {amount:+,}", reason, amount)
        return {"ok": True, "tx_id": tx_id, "before": before, "after": after, "amount": amount}

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "before": 0, "after": 0, "amount": amount}


def credit(guild_id, user_id, amount, source_type="credit", **kw):
    amount = clean_amount(amount)
    if amount is None:
        return {"ok": False, "error": "invalid_amount", "before": get_balance(guild_id, user_id), "after": get_balance(guild_id, user_id), "amount": 0}
    return tx(guild_id, user_id, amount, source_type, **kw)


def debit(guild_id, user_id, amount, source_type="debit", **kw):
    amount = clean_amount(amount)
    if amount is None:
        return {"ok": False, "error": "invalid_amount", "before": get_balance(guild_id, user_id), "after": get_balance(guild_id, user_id), "amount": 0}
    return tx(guild_id, user_id, -amount, source_type, **kw)


def set_balance(guild_id, user_id, new_balance, source_type="set_balance", **kw):
    try:
        new_balance = int(new_balance)
    except Exception:
        return {"ok": False, "error": "invalid_amount", "before": get_balance(guild_id, user_id), "after": get_balance(guild_id, user_id), "amount": 0}

    if new_balance < 0 or new_balance > MAX_TX_AMOUNT:
        return {"ok": False, "error": "invalid_amount", "before": get_balance(guild_id, user_id), "after": get_balance(guild_id, user_id), "amount": 0}

    old = get_balance(guild_id, user_id)
    return tx(guild_id, user_id, int(new_balance) - old, source_type, **kw)


def transfer(guild_id, from_user_id, to_user_id, amount, from_name="", to_name="", channel_id=0, message_id=0):
    amount = clean_amount(amount)
    if amount is None:
        return {"ok": False, "error": "invalid_amount"}

    gid = int(guild_id)
    from_uid = int(from_user_id)
    to_uid = int(to_user_id)

    if from_uid == to_uid:
        return {"ok": False, "error": "same_user"}

    ensure_balance(gid, from_uid)
    ensure_balance(gid, to_uid)

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (gid, from_uid))
        from_row = cur.fetchone()
        from_before = int(from_row["balance"] or 0) if from_row else 0

        if from_before < amount:
            conn.rollback()
            conn.close()
            return {"ok": False, "error": "insufficient_funds", "before": from_before, "after": from_before, "amount": amount}

        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (gid, to_uid))
        to_row = cur.fetchone()
        to_before = int(to_row["balance"] or 0) if to_row else 0

        from_after = from_before - amount
        to_after = to_before + amount

        if to_after > MAX_TX_AMOUNT:
            conn.rollback()
            conn.close()
            return {"ok": False, "error": "receiver_balance_too_large"}

        ts = now_ts()
        cur.execute("UPDATE balances SET balance=?, updated_at=? WHERE guild_id=? AND user_id=?", (from_after, ts, gid, from_uid))
        cur.execute("UPDATE balances SET balance=?, updated_at=? WHERE guild_id=? AND user_id=?", (to_after, ts, gid, to_uid))

        out_tx = uuid.uuid4().hex
        in_tx = uuid.uuid4().hex

        _insert_ledger_row(
            cur, out_tx, gid, from_uid, from_name, from_uid, from_name, -amount, from_before, from_after,
            "transfer_out", "transfer", f"Transfer to {to_uid}", "transfer", in_tx, to_uid, channel_id, message_id,
            {"paired_tx_id": in_tx}
        )

        _insert_ledger_row(
            cur, in_tx, gid, to_uid, to_name, from_uid, from_name, amount, to_before, to_after,
            "transfer_in", "transfer", f"Transfer from {from_uid}", "transfer", out_tx, from_uid, channel_id, message_id,
            {"paired_tx_id": out_tx}
        )

        conn.commit()
        conn.close()

        record(gid, from_uid, from_name, "money", f"transfer: -{amount:,}", f"to {to_uid}", -amount)
        record(gid, to_uid, to_name, "money", f"transfer: +{amount:,}", f"from {from_uid}", amount)

        return {
            "ok": True,
            "out": {"ok": True, "tx_id": out_tx, "before": from_before, "after": from_after, "amount": -amount},
            "in": {"ok": True, "tx_id": in_tx, "before": to_before, "after": to_after, "amount": amount}
        }

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def top_balances(guild_id:int, limit:int=10):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id,balance FROM balances WHERE guild_id=? ORDER BY balance DESC LIMIT ?", (int(guild_id), int(limit)))
    rows = [(int(r["user_id"]), int(r["balance"])) for r in cur.fetchall()]
    conn.close()
    return rows


def user_rank(guild_id:int, user_id:int) -> int:
    bal = get_balance(guild_id, user_id)
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*)+1 AS r FROM balances WHERE guild_id=? AND balance>?", (int(guild_id), bal))
    row = cur.fetchone()
    conn.close()
    return int(row["r"] or 1)
