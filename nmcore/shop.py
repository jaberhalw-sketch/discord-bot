import time
from nmcore.db import db
from nmcore.services.economy import debit, credit
from nmcore.services.activity import record, log_event

DEFAULT_ITEMS = [
    ("vip_day", "VIP Day", "شراء VIP لمدة يوم واحد. يحتاج Role ID إذا تبيه يعطي رتبة.", 5000, 0),
    ("nickname_pass", "Nickname Pass", "شراء تصريح تغيير لقب.", 1500, 0),
    ("loot_token", "Loot Token", "رمز خاص للصناديق والفعاليات.", 2500, 0),
]

def ensure_tables():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price INTEGER NOT NULL DEFAULT 0,
        role_id INTEGER NOT NULL DEFAULT 0,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        UNIQUE(guild_id, item_key)
    )""")

    conn.commit()
    conn.close()

def seed_defaults(guild_id:int):
    ensure_tables()
    for key, name, desc, price, role_id in DEFAULT_ITEMS:
        upsert_item(guild_id, key, name, desc, price, role_id, 1)

def upsert_item(guild_id:int, item_key:str, name:str, description:str, price:int, role_id:int=0, enabled:int=1):
    ensure_tables()
    now = int(time.time())
    key = str(item_key or "").strip().lower().replace(" ", "_")[:60]
    name = str(name or key).strip()[:120]
    description = str(description or "").strip()[:500]
    price = max(0, int(price or 0))
    role_id = int(role_id or 0)
    enabled = 1 if enabled else 0

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO shop_items
    (guild_id,item_key,name,description,price,role_id,enabled,created_at,updated_at)
    VALUES (?,?,?,?,?,?,?,?,?)
    ON CONFLICT(guild_id,item_key) DO UPDATE SET
      name=excluded.name,
      description=excluded.description,
      price=excluded.price,
      role_id=excluded.role_id,
      enabled=excluded.enabled,
      updated_at=excluded.updated_at""",
    (int(guild_id), key, name, description, price, role_id, enabled, now, now))
    conn.commit()
    conn.close()

def set_enabled(guild_id:int, item_id:int, enabled:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE shop_items SET enabled=?, updated_at=? WHERE guild_id=? AND id=?",
                (1 if enabled else 0, int(time.time()), int(guild_id), int(item_id)))
    conn.commit()
    conn.close()

def items(guild_id:int, include_disabled=False):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    if include_disabled:
        cur.execute("SELECT * FROM shop_items WHERE guild_id=? ORDER BY id", (int(guild_id),))
    else:
        cur.execute("SELECT * FROM shop_items WHERE guild_id=? AND enabled=1 ORDER BY price ASC,id ASC", (int(guild_id),))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_item(guild_id:int, key_or_id):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    s = str(key_or_id).strip()
    if s.isdigit():
        cur.execute("SELECT * FROM shop_items WHERE guild_id=? AND id=?", (int(guild_id), int(s)))
    else:
        cur.execute("SELECT * FROM shop_items WHERE guild_id=? AND item_key=?", (int(guild_id), s.lower()))
    row = cur.fetchone()
    conn.close()
    return row

def recent_purchases(guild_id:int, limit:int=100):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM shop_purchases WHERE guild_id=? ORDER BY id DESC LIMIT ?", (int(guild_id), int(limit)))
    rows = cur.fetchall()
    conn.close()
    return rows

def buy_item(guild_id:int, user_id:int, user_name:str, item_key_or_id, channel_id=0, message_id=0):
    item = get_item(guild_id, item_key_or_id)
    if not item:
        return {"ok": False, "error": "العنصر غير موجود."}
    if not int(item["enabled"]):
        return {"ok": False, "error": "العنصر مقفل حاليًا."}

    price = int(item["price"] or 0)
    tx = debit(
        guild_id,
        user_id,
        price,
        "shop_buy",
        user_name=user_name,
        actor_id=user_id,
        actor_name=user_name,
        source_label=str(item["item_key"]),
        reference_type="shop_item",
        reference_id=str(item["id"]),
        reason=f"Shop purchase: {item['name']}",
        channel_id=channel_id,
        message_id=message_id
    )

    if not tx["ok"]:
        return {"ok": False, "error": "رصيدك ما يكفي."}

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO shop_purchases
    (guild_id,user_id,item_key,price,money_tx_id,created_at)
    VALUES (?,?,?,?,?,?)""",
    (int(guild_id), int(user_id), str(item["item_key"]), price, tx["tx_id"], int(time.time())))
    conn.commit()
    conn.close()

    record(guild_id, user_id, user_name, "shop", f"Bought {item['name']}", f"{price:,}", -price)
    log_event(guild_id, "shop_buy", user_id, user_name, channel_id, "", "Shop purchase", f"{item['name']} for {price:,}")

    return {
        "ok": True,
        "item": dict(item),
        "price": price,
        "tx_id": tx["tx_id"],
        "role_id": int(item["role_id"] or 0)
    }

def lootbox(guild_id:int, user_id:int, user_name:str, cost:int=1000, channel_id=0, message_id=0):
    import random

    cost = int(cost or 1000)
    pay = debit(
        guild_id,
        user_id,
        cost,
        "lootbox_cost",
        user_name=user_name,
        actor_id=user_id,
        actor_name=user_name,
        source_label="lootbox",
        reason="Lootbox cost",
        channel_id=channel_id,
        message_id=message_id
    )

    if not pay["ok"]:
        return {"ok": False, "error": "رصيدك ما يكفي للصندوق."}

    roll = random.randint(1, 100)
    reward = 0
    title = "صندوق عادي"

    if roll <= 5:
        reward = cost * 8
        title = "أسطوري"
    elif roll <= 20:
        reward = cost * 3
        title = "نادر"
    elif roll <= 55:
        reward = cost * 2
        title = "ربح"
    elif roll <= 80:
        reward = cost
        title = "استرجاع"
    else:
        reward = 0
        title = "خسارة"

    reward_tx = None
    if reward > 0:
        reward_tx = credit(
            guild_id,
            user_id,
            reward,
            "lootbox_reward",
            user_name=user_name,
            actor_id=user_id,
            actor_name=user_name,
            source_label=title,
            reference_id=pay["tx_id"],
            reason=f"Lootbox reward: {title}",
            channel_id=channel_id,
            message_id=message_id
        )

    record(guild_id, user_id, user_name, "lootbox", title, f"cost={cost}, reward={reward}", reward - cost)
    log_event(guild_id, "lootbox", user_id, user_name, channel_id, "", title, f"cost={cost}, reward={reward}")

    return {
        "ok": True,
        "title": title,
        "cost": cost,
        "reward": reward,
        "net": reward - cost,
        "roll": roll,
        "cost_tx": pay["tx_id"],
        "reward_tx": reward_tx["tx_id"] if reward_tx else ""
    }
