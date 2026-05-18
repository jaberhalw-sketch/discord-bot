import time
from nmcore.db import db
from nmcore.config import REAL_ESTATE_RENT_COOLDOWN_SECONDS
from nmcore.services.economy import debit, credit
from nmcore.services.activity import record

PROPERTY_TYPES={
    "room":{"name":"Small Room","count":20,"price":25000,"rent":1000},
    "apartment":{"name":"Apartment","count":10,"price":100000,"rent":5000},
    "office":{"name":"Office","count":5,"price":300000,"rent":18000},
    "tower":{"name":"Tower","count":2,"price":1000000,"rent":75000},
    "palace":{"name":"Royal Palace","count":1,"price":3500000,"rent":250000},
}

def seed(guild_id:int):
    conn=db(); cur=conn.cursor(); now=int(time.time())
    for key,info in PROPERTY_TYPES.items():
        for unit in range(1,info["count"]+1):
            cur.execute("""INSERT OR IGNORE INTO properties
            (guild_id,type_key,unit_number,display_name,owner_id,owner_name,level,price,rent,created_at)
            VALUES (?,?,?,?,0,'',1,?,?,?)""", (int(guild_id),key,unit,f"{info['name']} #{unit}",info["price"],info["rent"],now))
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
    cur.execute("UPDATE properties SET owner_id=?, owner_name=? WHERE guild_id=? AND id=?", (int(user_id),str(user_name)[:120],int(guild_id),int(property_id)))
    conn.commit(); conn.close()
    prop_log(guild_id,property_id,"buy_from_system",old_owner_id=0,new_owner_id=user_id,actor_id=user_id,amount=price,price_before=price,price_after=price,reason="Bought from system",money_tx_id=tx["tx_id"])
    record(guild_id,user_id,user_name,"real_estate","Property bought",p["display_name"],-price)
    return {"ok":True,"name":p["display_name"],"price":price,"tx_id":tx["tx_id"]}

def collect_rent(guild_id:int,user_id:int,user_name:str):
    props=my_rows(guild_id,user_id)
    if not props: return {"ok":False,"error":"ما عندك عقارات."}
    now=int(time.time())
    eligible=[p for p in props if now-int(p["last_rent_claim"] or 0)>=REAL_ESTATE_RENT_COOLDOWN_SECONDS]
    if not eligible: return {"ok":False,"error":"الإيجار تحت الكولداون."}
    total=sum(int(p["rent"])*int(p["level"]) for p in eligible)
    tx=credit(guild_id,user_id,total,"real_estate_rent",user_name=user_name,reason=f"Rent from {len(eligible)} properties")
    conn=db(); cur=conn.cursor()
    for p in eligible:
        cur.execute("UPDATE properties SET last_rent_claim=? WHERE guild_id=? AND id=?", (now,int(guild_id),int(p["id"])))
        prop_log(guild_id,int(p["id"]),"rent_collect",old_owner_id=user_id,new_owner_id=user_id,actor_id=user_id,amount=int(p["rent"])*int(p["level"]),level_before=int(p["level"]),level_after=int(p["level"]),money_tx_id=tx["tx_id"])
    conn.commit(); conn.close()
    return {"ok":True,"count":len(eligible),"amount":total,"tx_id":tx["tx_id"]}
