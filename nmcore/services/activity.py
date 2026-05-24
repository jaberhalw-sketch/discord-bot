import time, json, sqlite3
from nmcore.db import db
from nmcore.config import LIVE_ACTIVITY_LIMIT


def _write_retry(fn, retries=5, delay=0.12):
    last = None
    for attempt in range(int(retries)):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(delay * (attempt + 1))
        except Exception:
            # Logs should never kill bot events.
            return None
    # If still locked, drop the log instead of crashing on_message/on_voice.
    return None


def record(guild_id:int, actor_id:int, actor_name:str, activity_type:str, title:str, details:str="", amount:int=0):
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO live_activity (guild_id,actor_id,actor_name,activity_type,title,details,amount,created_at)
        VALUES (?,?,?,?,?,?,?,?)""", (
            int(guild_id),
            int(actor_id or 0),
            str(actor_name or "")[:120],
            str(activity_type),
            str(title)[:200],
            str(details)[:1200],
            int(amount or 0),
            int(time.time())
        ))
        cur.execute("""DELETE FROM live_activity
        WHERE id NOT IN (SELECT id FROM live_activity ORDER BY id DESC LIMIT ?)""", (LIVE_ACTIVITY_LIMIT,))
        conn.commit()
        conn.close()

    return _write_retry(work)


def log_event(guild_id:int, event_type:str, user_id:int=0, user_name:str="", channel_id:int=0, channel_name:str="", title:str="", details:str="", metadata=None):
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO log_events
        (guild_id,event_type,user_id,user_name,channel_id,channel_name,title,details,metadata_json,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", (
            int(guild_id),
            str(event_type),
            int(user_id or 0),
            str(user_name)[:120],
            int(channel_id or 0),
            str(channel_name)[:120],
            str(title)[:200],
            str(details)[:2000],
            json.dumps(metadata or {}, ensure_ascii=False),
            int(time.time())
        ))
        conn.commit()
        conn.close()

    return _write_retry(work)
