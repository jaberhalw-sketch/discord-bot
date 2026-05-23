import time
from nmcore.db import db
from nmcore.services.economy import debit, credit
from nmcore.services.activity import record

PROPERTY_TYPES={
    "room":{"name":"Small Room","count":20,"price":25000,"rent":4000},
    "apartment":{"name":"Apartment","count":10,"price":100000,"rent":8000},
    "office":{"name":"Office","count":6,"price":250000,"rent":15000},
    "tower":{"name":"Tower","count":3,"price":750000,"rent":35000},
    "palace":{"name":"Palace","count":1,"price":2000000,"rent":100000},
}

def seed(guild_id:int):
    conn=db(); cur=conn.cursor(); now=int(time.time())
    for key,info in PROPERTY_TYPES.items():
        for unit in range(1,info["count"]+1):
            cur.execute("""INSERT OR IGNORE INTO properties
            (guild_id,type_key,unit_number,display_name,owner_id,owner_name,level,price,rent,created_at)
            VALUES (?,?,?,?,0,'',1,?,?,?)""", (int(guild_id),key,unit,f"{info['name']} #{unit}",info["price"],info["rent"],now))

    # Keep all property rents synced with the new economy setting.
    # This also migrates old properties that were created with low rent such as Small Room = 1,000.
    for key, info in PROPERTY_TYPES.items():
        cur.execute("UPDATE properties SET rent=? WHERE guild_id=? AND type_key=?", (int(info["rent"]), int(guild_id), key))

    conn.commit(); conn.close()

def rows(guild_id:int, only_available=False):
    seed(guild_id)
    conn=db(); cur=conn.cursor()
    sql="SELECT * FROM properties WHERE guild_id=?"; params=[int(guild_id)]
    if only_available:
        sql+=" AND owner_id=0"
    sql+=" ORDER BY price ASC,id ASC"
    cur.execute(sql,params); data=cur.fetchall(); conn.close(); return data

def my_rows(guild_id:int,user_id:int):
    seed(guild_id); conn=db(); cur=conn.cursor()
    cur.execute("SELECT * FROM properties WHERE guild_id=? AND owner_id=? ORDER BY id", (int(guild_id),int(user_id)))
    data=cur.fetchall(); conn.close(); return data

def prop_log(guild_id, property_id, action, **kw):
    conn=db(); cur=conn.cursor()
    cur.execute("""INSERT INTO property_ledger
    (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (int(guild_id),int(property_id),str(action),int(kw.get("old_owner_id",0) or 0),int(kw.get("new_owner_id",0) or 0),int(kw.get("actor_id",0) or 0),int(kw.get("amount",0) or 0),int(kw.get("level_before",0) or 0),int(kw.get("level_after",0) or 0),int(kw.get("price_before",0) or 0),int(kw.get("price_after",0) or 0),str(kw.get("reason","")),str(kw.get("money_tx_id","")),int(time.time())))
    conn.commit(); conn.close()

def buy(guild_id:int,user_id:int,user_name:str,property_id:int):
    seed(guild_id)
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (int(guild_id),int(property_id)))
    p=cur.fetchone(); conn.close()
    if not p: return {"ok":False,"error":"العقار غير موجود."}
    if int(p["owner_id"] or 0)!=0: return {"ok":False,"error":"العقار مملوك بالفعل."}
    price=int(p["price"])
    tx=debit(guild_id,user_id,price,"real_estate_buy",user_name=user_name,source_label=str(property_id),reference_type="property",reference_id=str(property_id),reason=f"Buy {p['display_name']}")
    if not tx["ok"]: return {"ok":False,"error":"رصيدك ما يكفي."}
    conn=db(); cur=conn.cursor()
    cur.execute("UPDATE properties SET owner_id=?, owner_name=?, last_rent_claim=? WHERE guild_id=? AND id=?", (int(user_id),str(user_name)[:120],int(time.time()),int(guild_id),int(property_id)))
    conn.commit(); conn.close()
    prop_log(guild_id,property_id,"buy_from_system",old_owner_id=0,new_owner_id=user_id,actor_id=user_id,amount=price,price_before=price,price_after=price,reason="Bought from system",money_tx_id=tx["tx_id"])
    record(guild_id,user_id,user_name,"real_estate","Property bought",p["display_name"],-price)
    return {"ok":True,"name":p["display_name"],"price":price,"tx_id":tx["tx_id"]}

def collect_rent(guild_id:int,user_id:int,user_name:str):
    """
    Rent accrues every 3 hours. User can claim whenever they want.
    Each property pays: rent * level * completed 3-hour periods.
    """
    props=my_rows(guild_id,user_id)
    if not props: return {"ok":False,"error":"ما عندك عقارات."}

    now=int(time.time())
    eligible=[]
    total=0

    # Legacy safety: old properties with last_rent_claim=0 start counting from now,
    # to avoid accidental huge payouts after migration.
    conn=db(); cur=conn.cursor()
    for p in props:
        last=int(p["last_rent_claim"] or 0)
        if last <= 0:
            cur.execute("UPDATE properties SET last_rent_claim=? WHERE guild_id=? AND id=?", (now,int(guild_id),int(p["id"])))
            continue

        periods=(now-last)//RENT_COOLDOWN_SECONDS
        if periods <= 0:
            continue

        amount=int(p["rent"])*int(p["level"])*int(periods)
        total += amount
        eligible.append((p, periods, amount))

    conn.commit(); conn.close()

    if not eligible:
        return {"ok":False,"error":"ما تجمع لك إيجار للحين. الإيجار يتجمع كل 3 ساعات."}

    tx=credit(guild_id,user_id,total,"real_estate_rent",user_name=user_name,reason=f"Accumulated rent from {len(eligible)} properties")

    conn=db(); cur=conn.cursor()
    for p, periods, amount in eligible:
        last=int(p["last_rent_claim"] or now)
        new_last=last + (int(periods)*RENT_COOLDOWN_SECONDS)
        cur.execute("UPDATE properties SET last_rent_claim=? WHERE guild_id=? AND id=?", (new_last,int(guild_id),int(p["id"])))
        prop_log(guild_id,int(p["id"]),"rent_collect",old_owner_id=user_id,new_owner_id=user_id,actor_id=user_id,amount=amount,level_before=int(p["level"]),level_after=int(p["level"]),reason=f"{periods} rent periods",money_tx_id=tx["tx_id"])
    conn.commit(); conn.close()

    record(guild_id,user_id,user_name,"real_estate","Accumulated rent",f"{len(eligible)} properties",total)
    return {"ok":True,"count":len(eligible),"amount":total,"tx_id":tx["tx_id"]}



def stock_summary(guild_id:int):
    """
    Returns limited property stock by type:
    total / available / owned / base price / base rent.
    """
    seed(guild_id)
    conn=db(); cur=conn.cursor()
    cur.execute("""SELECT type_key,
    COUNT(*) AS total,
    SUM(CASE WHEN owner_id=0 THEN 1 ELSE 0 END) AS available,
    SUM(CASE WHEN owner_id!=0 THEN 1 ELSE 0 END) AS owned,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    MIN(rent) AS min_rent,
    MAX(rent) AS max_rent
    FROM properties
    WHERE guild_id=?
    GROUP BY type_key
    ORDER BY MIN(price) ASC""", (int(guild_id),))
    rows=[dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def assign_property(guild_id:int, property_id:int, owner_id:int, owner_name:str, actor_id:int=0, reason:str="Dashboard assign"):
    """
    Assigns an existing limited property to a user safely.
    This is for dashboard/manual grants and starts rent timer correctly.
    """
    seed(guild_id)
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (int(guild_id), int(property_id)))
    p=cur.fetchone()
    if not p:
        conn.close()
        return {"ok":False,"error":"العقار غير موجود."}

    now=int(time.time())
    cur.execute("UPDATE properties SET owner_id=?, owner_name=?, last_rent_claim=? WHERE guild_id=? AND id=?",
                (int(owner_id), str(owner_name or owner_id)[:120], now, int(guild_id), int(property_id)))
    conn.commit(); conn.close()

    prop_log(guild_id, property_id, "dashboard_assign", old_owner_id=int(p["owner_id"] or 0), new_owner_id=int(owner_id),
             actor_id=int(actor_id or 0), amount=0, level_before=int(p["level"]), level_after=int(p["level"]),
             price_before=int(p["price"]), price_after=int(p["price"]), reason=reason, money_tx_id="")
    return {"ok":True,"name":p["display_name"],"owner_id":int(owner_id),"owner_name":str(owner_name or owner_id)}


def rent_status(guild_id:int, user_id:int):
    """
    Returns a clear rent status for the user's properties:
    - ready properties
    - total claimable amount
    - seconds until next rent period
    """
    props = my_rows(guild_id, user_id)
    now = int(time.time())

    if not props:
        return {
            "has_properties": False,
            "ready_count": 0,
            "total_amount": 0,
            "next_seconds": None,
            "properties_count": 0,
        }

    ready_count = 0
    total_amount = 0
    next_seconds = None

    for p in props:
        last = int(p["last_rent_claim"] or 0)

        # If old dashboard assignment never started timer, start it safely now.
        if last <= 0:
            last = now

        elapsed = max(0, now - last)
        periods = elapsed // RENT_COOLDOWN_SECONDS

        if periods > 0:
            ready_count += 1
            total_amount += int(p["rent"]) * int(p["level"]) * int(periods)
        else:
            remaining = RENT_COOLDOWN_SECONDS - elapsed
            if next_seconds is None or remaining < next_seconds:
                next_seconds = remaining

    return {
        "has_properties": True,
        "ready_count": ready_count,
        "total_amount": total_amount,
        "next_seconds": next_seconds,
        "properties_count": len(props),
    }


def format_duration(seconds:int):
    seconds = max(0, int(seconds or 0))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours and minutes:
        return f"{hours} ساعة و {minutes} دقيقة"
    if hours:
        return f"{hours} ساعة"
    if minutes:
        return f"{minutes} دقيقة"
    return "أقل من دقيقة"
