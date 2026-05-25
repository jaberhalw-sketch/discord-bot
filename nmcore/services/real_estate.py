import time, sqlite3
from nmcore.db import db
# NM System rule: every property rent becomes available every 3 hours.
RENT_COOLDOWN_SECONDS = 3 * 60 * 60
from nmcore.services.economy import debit, credit
from nmcore.services.activity import record

PROPERTY_TYPES = {
    "room":{"name":"Small Room","count":20,"price":25000,"rent":4000},
    "apartment":{"name":"Apartment","count":10,"price":100000,"rent":5000},
    "office":{"name":"Office","count":5,"price":300000,"rent":18000},
    "tower":{"name":"Tower","count":2,"price":1000000,"rent":75000},
    "palace":{"name":"Royal Palace","count":1,"price":3500000,"rent":250000},
}


def _retry(fn, retries=4, delay=0.1):
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


def seed(guild_id:int):
    def work():
        conn = db()
        cur = conn.cursor()
        now = int(time.time())
        for key,info in PROPERTY_TYPES.items():
            for unit in range(1,info["count"]+1):
                cur.execute("""INSERT OR IGNORE INTO properties
                (guild_id,type_key,unit_number,display_name,owner_id,owner_name,level,price,rent,created_at)
                VALUES (?,?,?,?,0,'',1,?,?,?)""", (int(guild_id),key,unit,f"{info['name']} #{unit}",info["price"],info["rent"],now))

        # Upgrade old Small Room rent from 1000 to 4000, keeps your requested change.
        cur.execute("UPDATE properties SET rent=4000 WHERE guild_id=? AND type_key='room' AND rent<4000", (int(guild_id),))
        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)


def rows(guild_id:int, only_available=False):
    seed(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        sql = "SELECT * FROM properties WHERE guild_id=?"
        params = [int(guild_id)]
        if only_available:
            sql += " AND owner_id=0"
        sql += " ORDER BY price ASC,id ASC"
        cur.execute(sql, params)
        data = cur.fetchall()
        conn.close()
        return data

    res = _retry(work)
    return res if not isinstance(res, dict) else []


def my_rows(guild_id:int,user_id:int):
    seed(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM properties WHERE guild_id=? AND owner_id=? ORDER BY id", (int(guild_id),int(user_id)))
        data = cur.fetchall()
        conn.close()
        return data

    res = _retry(work)
    return res if not isinstance(res, dict) else []


def prop_log(guild_id, property_id, action, **kw):
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO property_ledger
        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id),int(property_id),str(action),int(kw.get("old_owner_id",0) or 0),int(kw.get("new_owner_id",0) or 0),int(kw.get("actor_id",0) or 0),int(kw.get("amount",0) or 0),int(kw.get("level_before",0) or 0),int(kw.get("level_after",0) or 0),int(kw.get("price_before",0) or 0),int(kw.get("price_after",0) or 0),str(kw.get("reason","")),str(kw.get("money_tx_id","")),int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)


def buy(guild_id:int,user_id:int,user_name:str,property_id:int):
    seed(guild_id)

    def read_prop():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (int(guild_id),int(property_id)))
        p = cur.fetchone()
        conn.close()
        return p

    p = _retry(read_prop)
    if isinstance(p, dict) and not p.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}
    if not p:
        return {"ok":False,"error":"العقار غير موجود."}
    if int(p["owner_id"] or 0) != 0:
        return {"ok":False,"error":"العقار مملوك بالفعل."}

    price = int(p["price"])
    tx = debit(guild_id,user_id,price,"real_estate_buy",user_name=user_name,source_label=str(property_id),reference_type="property",reference_id=str(property_id),reason=f"Buy {p['display_name']}")
    if not tx.get("ok"):
        if tx.get("error") == "database_locked":
            return {"ok":False,"error":"قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}
        return {"ok":False,"error":"رصيدك ما يكفي."}

    def update_owner():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE properties SET owner_id=?, owner_name=? WHERE guild_id=? AND id=? AND owner_id=0", (int(user_id),str(user_name)[:120],int(guild_id),int(property_id)))
        changed = cur.rowcount
        conn.commit()
        conn.close()
        return changed

    changed = _retry(update_owner)
    if isinstance(changed, dict) and not changed.get("ok"):
        return {"ok":False,"error":"تم خصم المبلغ لكن قاعدة البيانات كانت مشغولة وقت تسجيل العقار. راجع Money Tracker."}

    prop_log(guild_id,property_id,"buy_from_system",old_owner_id=0,new_owner_id=user_id,actor_id=user_id,amount=price,price_before=price,price_after=price,reason="Bought from system",money_tx_id=tx["tx_id"])
    try:
        record(guild_id,user_id,user_name,"real_estate","Property bought",p["display_name"],-price)
    except Exception:
        pass
    return {"ok":True,"name":p["display_name"],"price":price,"tx_id":tx["tx_id"]}



def seconds_to_text(seconds:int):
    seconds = max(0, int(seconds or 0))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h > 0:
        return f"{h} ساعة و {m} دقيقة"
    if m > 0:
        return f"{m} دقيقة و {s} ثانية"
    return f"{s} ثانية"


def rent_status(guild_id:int, user_id:int):
    props = my_rows(guild_id, user_id)
    now = int(time.time())
    out = []

    for p in props:
        last = int(p["last_rent_claim"] or 0)
        elapsed = now - last if last else RENT_COOLDOWN_SECONDS
        remaining = max(0, RENT_COOLDOWN_SECONDS - elapsed)
        ready = remaining <= 0
        amount = int(p["rent"]) * int(p["level"])

        out.append({
            "id": int(p["id"]),
            "name": p["display_name"],
            "level": int(p["level"]),
            "rent": int(p["rent"]),
            "amount": amount,
            "ready": ready,
            "remaining": remaining,
            "remaining_text": seconds_to_text(remaining),
            "last_claim": last,
        })

    ready_count = sum(1 for x in out if x["ready"])
    ready_amount = sum(x["amount"] for x in out if x["ready"])
    next_remaining = min([x["remaining"] for x in out if not x["ready"]], default=0)

    return {
        "properties": out,
        "count": len(out),
        "ready_count": ready_count,
        "ready_amount": ready_amount,
        "next_remaining": next_remaining,
        "next_remaining_text": seconds_to_text(next_remaining),
        "cooldown": RENT_COOLDOWN_SECONDS,
    }


def collect_rent(guild_id:int,user_id:int,user_name:str):
    props = my_rows(guild_id,user_id)
    if not props:
        return {"ok":False,"error":"ما عندك عقارات."}

    now = int(time.time())
    eligible = [p for p in props if now - int(p["last_rent_claim"] or 0) >= RENT_COOLDOWN_SECONDS]

    if not eligible:
        status = rent_status(guild_id, user_id)
        return {
            "ok": False,
            "error": f"الإيجار تحت الكولداون. باقي على أقرب إيجار: {status['next_remaining_text']}.",
            "next_remaining": status["next_remaining"],
            "next_remaining_text": status["next_remaining_text"],
        }

    total = sum(int(p["rent"]) * int(p["level"]) for p in eligible)

    tx = credit(guild_id,user_id,total,"real_estate_rent",user_name=user_name,reason=f"Rent from {len(eligible)} properties")
    if not tx.get("ok"):
        if tx.get("error") == "database_locked":
            return {"ok": False, "error": "قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}
        return {"ok": False, "error": tx.get("error", "تعذر إضافة الإيجار.")}

    def update_claims():
        conn = db()
        cur = conn.cursor()
        for p in eligible:
            cur.execute("UPDATE properties SET last_rent_claim=? WHERE guild_id=? AND id=?", (now,int(guild_id),int(p["id"])))
        conn.commit()
        conn.close()
        return {"ok": True}

    updated = _retry(update_claims, retries=5, delay=0.12)
    if isinstance(updated, dict) and not updated.get("ok"):
        # Money was already credited; don't fail silently. Tell user it was paid.
        return {"ok": True, "count": len(eligible), "amount": total, "tx_id": tx["tx_id"], "warning": "تم دفع الإيجار لكن تحديث وقت الاستلام تأخر بسبب ضغط قاعدة البيانات."}

    # Log property ledger after claims; if locked, ignore ledger, not money.
    for p in eligible:
        prop_log(
            guild_id,
            int(p["id"]),
            "rent_collect",
            old_owner_id=user_id,
            new_owner_id=user_id,
            actor_id=user_id,
            amount=int(p["rent"])*int(p["level"]),
            level_before=int(p["level"]),
            level_after=int(p["level"]),
            money_tx_id=tx["tx_id"]
        )

    return {"ok":True,"count":len(eligible),"amount":total,"tx_id":tx["tx_id"]}



def get_property(guild_id:int, property_id:int):
    seed(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (int(guild_id), int(property_id)))
        row = cur.fetchone()
        conn.close()
        return row

    res = _retry(work)
    return None if isinstance(res, dict) else res


def transfer_property(guild_id:int, from_user_id:int, to_user_id:int, to_user_name:str, property_id:int, actor_id:int=0, reason:str="Transfer property"):
    seed(guild_id)
    p = get_property(guild_id, property_id)

    if not p:
        return {"ok": False, "error": "العقار غير موجود."}

    old_owner = int(p["owner_id"] or 0)
    if old_owner != int(from_user_id):
        return {"ok": False, "error": "ما تقدر تنقل عقار مو مملوك لك."}

    if int(to_user_id) == int(from_user_id):
        return {"ok": False, "error": "ما تقدر تنقل العقار لنفسك."}

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE properties
        SET owner_id=?, owner_name=?, last_rent_claim=?
        WHERE guild_id=? AND id=? AND owner_id=?""",
        (int(to_user_id), str(to_user_name)[:120], int(time.time()), int(guild_id), int(property_id), int(from_user_id)))
        changed = cur.rowcount
        conn.commit()
        conn.close()
        return changed

    changed = _retry(work, retries=5, delay=0.12)
    if isinstance(changed, dict) and not changed.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}

    if not changed:
        return {"ok": False, "error": "فشل نقل العقار، يمكن تغير المالك قبل العملية."}

    prop_log(
        guild_id, property_id, "transfer",
        old_owner_id=from_user_id,
        new_owner_id=to_user_id,
        actor_id=actor_id or from_user_id,
        amount=0,
        level_before=int(p["level"]),
        level_after=int(p["level"]),
        price_before=int(p["price"]),
        price_after=int(p["price"]),
        reason=reason,
        money_tx_id=""
    )

    return {
        "ok": True,
        "id": int(p["id"]),
        "name": p["display_name"],
        "old_owner_id": int(from_user_id),
        "new_owner_id": int(to_user_id),
        "new_owner_name": str(to_user_name),
    }


def admin_assign_property(guild_id:int, property_id:int, to_user_id:int, to_user_name:str, actor_id:int=0, reason:str="Admin property assign"):
    seed(guild_id)
    p = get_property(guild_id, property_id)

    if not p:
        return {"ok": False, "error": "العقار غير موجود."}

    old_owner = int(p["owner_id"] or 0)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE properties
        SET owner_id=?, owner_name=?, last_rent_claim=?
        WHERE guild_id=? AND id=?""",
        (int(to_user_id), str(to_user_name)[:120], int(time.time()), int(guild_id), int(property_id)))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work, retries=5, delay=0.12)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}

    prop_log(
        guild_id, property_id, "admin_assign",
        old_owner_id=old_owner,
        new_owner_id=to_user_id,
        actor_id=actor_id or 0,
        amount=0,
        level_before=int(p["level"]),
        level_after=int(p["level"]),
        price_before=int(p["price"]),
        price_after=int(p["price"]),
        reason=reason,
        money_tx_id=""
    )

    return {
        "ok": True,
        "id": int(p["id"]),
        "name": p["display_name"],
        "old_owner_id": old_owner,
        "new_owner_id": int(to_user_id),
        "new_owner_name": str(to_user_name),
    }


def admin_return_property(guild_id:int, property_id:int, actor_id:int=0, reason:str="Admin return property to market"):
    seed(guild_id)
    p = get_property(guild_id, property_id)

    if not p:
        return {"ok": False, "error": "العقار غير موجود."}

    old_owner = int(p["owner_id"] or 0)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""UPDATE properties
        SET owner_id=0, owner_name='', last_rent_claim=0
        WHERE guild_id=? AND id=?""", (int(guild_id), int(property_id)))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work, retries=5, delay=0.12)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة الآن، جرب بعد ثواني."}

    prop_log(
        guild_id, property_id, "admin_return_to_market",
        old_owner_id=old_owner,
        new_owner_id=0,
        actor_id=actor_id or 0,
        amount=0,
        level_before=int(p["level"]),
        level_after=int(p["level"]),
        price_before=int(p["price"]),
        price_after=int(p["price"]),
        reason=reason,
        money_tx_id=""
    )

    return {"ok": True, "id": int(p["id"]), "name": p["display_name"], "old_owner_id": old_owner}


def stock_summary(guild_id:int):
    seed(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT type_key,
        COUNT(*) total,
        SUM(CASE WHEN owner_id=0 THEN 1 ELSE 0 END) available,
        SUM(CASE WHEN owner_id!=0 THEN 1 ELSE 0 END) owned,
        MIN(price) min_price,
        MIN(rent) min_rent
        FROM properties WHERE guild_id=?
        GROUP BY type_key ORDER BY min_price ASC""", (int(guild_id),))
        rows = cur.fetchall()
        conn.close()
        return rows

    res = _retry(work)
    return res if not isinstance(res, dict) else []
