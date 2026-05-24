import time, uuid, json, sqlite3
from nmcore.db import db
from nmcore.services.activity import record


def _retry(fn, retries=3, delay=0.08):
    last = None
    for i in range(int(retries)):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(delay * (i + 1))
    return {"ok": False, "error": "database_locked"}


def ensure_balance(guild_id:int, user_id:int):
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT OR IGNORE INTO balances (guild_id,user_id,balance,last_salary,updated_at)
        VALUES (?,?,0,0,?)""", (int(guild_id), int(user_id), int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)


def get_balance(guild_id:int, user_id:int)->int:
    ensure_balance(guild_id,user_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (int(guild_id),int(user_id)))
        row = cur.fetchone()
        conn.close()
        return int(row["balance"] or 0) if row else 0

    res = _retry(work)
    if isinstance(res, dict) and not res.get("ok"):
        return 0
    return int(res or 0)


def tx(guild_id:int, user_id:int, amount:int, source_type:str, user_name="", actor_id=0, actor_name="", source_label="", reason="", reference_type="", reference_id="", related_user_id=0, channel_id=0, message_id=0, metadata=None):
    gid = int(guild_id)
    uid = int(user_id)
    amount = int(amount)
    ensure_balance(gid, uid)

    def work():
        conn = db()
        cur = conn.cursor()

        # BEGIN IMMEDIATE can fail when another writer is active.
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (gid,uid))
        row = cur.fetchone()
        before = int(row["balance"] or 0) if row else 0
        after = before + amount

        if after < 0:
            conn.rollback()
            conn.close()
            return {"ok":False,"error":"insufficient_funds","before":before,"after":before,"amount":amount}

        cur.execute("UPDATE balances SET balance=?, updated_at=? WHERE guild_id=? AND user_id=?", (after,int(time.time()),gid,uid))

        tx_id = uuid.uuid4().hex
        cur.execute("""INSERT INTO money_ledger
        (tx_id,guild_id,user_id,user_name,actor_id,actor_name,amount,balance_before,balance_after,source_type,source_label,reason,reference_type,reference_id,related_user_id,channel_id,message_id,metadata_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tx_id,gid,uid,str(user_name)[:120],int(actor_id or 0),str(actor_name)[:120],amount,before,after,str(source_type),str(source_label)[:80],str(reason)[:500],str(reference_type)[:80],str(reference_id)[:120],int(related_user_id or 0),int(channel_id or 0),int(message_id or 0),json.dumps(metadata or {},ensure_ascii=False),int(time.time())))

        conn.commit()
        conn.close()

        try:
            record(gid, actor_id or uid, actor_name or user_name, "money", f"{source_type}: {amount:+,}", reason, amount)
        except Exception:
            pass

        return {"ok":True,"tx_id":tx_id,"before":before,"after":after,"amount":amount}

    res = _retry(work, retries=6, delay=0.12)
    if isinstance(res, dict):
        return res
    return {"ok": False, "error": "database_locked"}


def credit(guild_id,user_id,amount,source_type="credit",**kw):
    return tx(guild_id,user_id,abs(int(amount)),source_type,**kw)


def debit(guild_id,user_id,amount,source_type="debit",**kw):
    return tx(guild_id,user_id,-abs(int(amount)),source_type,**kw)


def set_balance(guild_id,user_id,new_balance,source_type="set_balance",**kw):
    old = get_balance(guild_id,user_id)
    return tx(guild_id,user_id,int(new_balance)-old,source_type,**kw)


def transfer(guild_id,from_user_id,to_user_id,amount,from_name="",to_name="",channel_id=0,message_id=0):
    amount = abs(int(amount))
    out = debit(guild_id,from_user_id,amount,"transfer_out",user_name=from_name,actor_id=from_user_id,actor_name=from_name,related_user_id=to_user_id,channel_id=channel_id,message_id=message_id,reason=f"Transfer to {to_user_id}")
    if not out["ok"]:
        return out
    inn = credit(guild_id,to_user_id,amount,"transfer_in",user_name=to_name,actor_id=from_user_id,actor_name=from_name,related_user_id=from_user_id,reference_id=out["tx_id"],channel_id=channel_id,message_id=message_id,reason=f"Transfer from {from_user_id}")
    if not inn.get("ok"):
        return {"ok": False, "error": inn.get("error", "transfer_in_failed")}
    return {"ok":True,"out":out,"in":inn}


def top_balances(guild_id:int, limit:int=10):
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT user_id,balance FROM balances WHERE guild_id=? ORDER BY balance DESC LIMIT ?", (int(guild_id),int(limit)))
        rows = [(int(r["user_id"]), int(r["balance"])) for r in cur.fetchall()]
        conn.close()
        return rows

    res = _retry(work)
    return res if isinstance(res, list) else []


def user_rank(guild_id:int,user_id:int)->int:
    bal = get_balance(guild_id,user_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*)+1 AS r FROM balances WHERE guild_id=? AND balance>?", (int(guild_id),bal))
        row = cur.fetchone()
        conn.close()
        return int(row["r"] or 1)

    res = _retry(work)
    return int(res or 1) if not isinstance(res, dict) else 1
