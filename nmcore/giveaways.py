import random, time
from nmcore.db import db
from nmcore.services.activity import record, log_event

def ensure_tables():
    conn = db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS giveaway_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        giveaway_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        created_at INTEGER NOT NULL,
        UNIQUE(giveaway_id, user_id)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS giveaway_winners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        giveaway_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        picked_at INTEGER NOT NULL
    )""")

    conn.commit()
    conn.close()

def create_giveaway(guild_id:int, prize:str, winner_count:int, created_by_id:int=0, created_by_name:str=""):
    ensure_tables()
    prize = str(prize or "Prize").strip()[:300]
    winner_count = max(1, min(int(winner_count or 1), 20))

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO giveaways
    (guild_id,prize,winner_count,created_by_id,created_by_name,status,created_at,ended_at)
    VALUES (?,?,?,?,?,'open',?,0)""",
    (int(guild_id), prize, winner_count, int(created_by_id or 0), str(created_by_name)[:120], int(time.time())))
    giveaway_id = cur.lastrowid
    conn.commit()
    conn.close()

    record(guild_id, created_by_id, created_by_name, "giveaway", "Giveaway created", prize, 0)
    log_event(guild_id, "giveaway_create", created_by_id, created_by_name, title="Giveaway created", details=prize)
    return giveaway_id

def giveaways(guild_id:int, limit:int=100):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM giveaways WHERE guild_id=? ORDER BY id DESC LIMIT ?", (int(guild_id), int(limit)))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_giveaway(guild_id:int, giveaway_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM giveaways WHERE guild_id=? AND id=?", (int(guild_id), int(giveaway_id)))
    row = cur.fetchone()
    conn.close()
    return row

def join(guild_id:int, giveaway_id:int, user_id:int, user_name:str):
    ensure_tables()
    g = get_giveaway(guild_id, giveaway_id)
    if not g:
        return {"ok": False, "error": "القيف أواي غير موجود."}
    if str(g["status"]) != "open":
        return {"ok": False, "error": "القيف أواي مقفل."}

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""INSERT INTO giveaway_entries
        (giveaway_id,guild_id,user_id,user_name,created_at)
        VALUES (?,?,?,?,?)""",
        (int(giveaway_id), int(guild_id), int(user_id), str(user_name)[:120], int(time.time())))
        conn.commit()
        ok = True
    except Exception:
        ok = False
    finally:
        conn.close()

    if not ok:
        return {"ok": False, "error": "أنت داخل القيف أواي من قبل."}

    record(guild_id, user_id, user_name, "giveaway", "Joined giveaway", f"#{giveaway_id}", 0)
    return {"ok": True}

def entry_count(guild_id:int, giveaway_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM giveaway_entries WHERE guild_id=? AND giveaway_id=?", (int(guild_id), int(giveaway_id)))
    c = int(cur.fetchone()["c"] or 0)
    conn.close()
    return c

def entries(guild_id:int, giveaway_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM giveaway_entries WHERE guild_id=? AND giveaway_id=? ORDER BY id", (int(guild_id), int(giveaway_id)))
    rows = cur.fetchall()
    conn.close()
    return rows

def close_giveaway(guild_id:int, giveaway_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE giveaways SET status='closed', ended_at=? WHERE guild_id=? AND id=?", (int(time.time()), int(guild_id), int(giveaway_id)))
    conn.commit()
    conn.close()

def pick_winners(guild_id:int, giveaway_id:int):
    ensure_tables()
    g = get_giveaway(guild_id, giveaway_id)
    if not g:
        return []

    rows = entries(guild_id, giveaway_id)
    if not rows:
        return []

    winner_count = max(1, int(g["winner_count"] or 1))
    chosen = random.sample(rows, min(winner_count, len(rows)))

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM giveaway_winners WHERE guild_id=? AND giveaway_id=?", (int(guild_id), int(giveaway_id)))
    for r in chosen:
        cur.execute("""INSERT INTO giveaway_winners (giveaway_id,guild_id,user_id,picked_at)
        VALUES (?,?,?,?)""", (int(giveaway_id), int(guild_id), int(r["user_id"]), int(time.time())))
    cur.execute("UPDATE giveaways SET status='ended', ended_at=? WHERE guild_id=? AND id=?", (int(time.time()), int(guild_id), int(giveaway_id)))
    conn.commit()
    conn.close()

    log_event(guild_id, "giveaway_winners", title="Giveaway winners picked", details=",".join(str(r["user_id"]) for r in chosen))
    return [int(r["user_id"]) for r in chosen]

def winner_list(guild_id:int, giveaway_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM giveaway_winners WHERE guild_id=? AND giveaway_id=? ORDER BY id", (int(guild_id), int(giveaway_id)))
    rows = [int(r["user_id"]) for r in cur.fetchall()]
    conn.close()
    return rows
