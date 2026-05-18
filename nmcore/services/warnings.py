import time
from nmcore.db import db
from nmcore.services.activity import record

def add_warning(guild_id,user_id,user_name,moderator_id,moderator_name,reason,message=""):
    conn=db(); cur=conn.cursor()
    cur.execute("""INSERT INTO warnings (guild_id,user_id,user_name,moderator_id,moderator_name,reason,message,status,created_at)
    VALUES (?,?,?,?,?,?,?,?,?)""", (int(guild_id),int(user_id),str(user_name)[:120],int(moderator_id or 0),str(moderator_name)[:120],str(reason)[:500],str(message)[:1000],"active",int(time.time())))
    conn.commit(); conn.close()
    record(guild_id,moderator_id,moderator_name,"warning","Warning added",f"{user_id}: {reason}",0)

def clear_user(guild_id,user_id,cleared_by_id,cleared_by_name,reason=""):
    conn=db(); cur=conn.cursor()
    cur.execute("""UPDATE warnings SET status='cleared', cleared_at=?, cleared_by_id=?, cleared_by_name=?, clear_reason=?
    WHERE guild_id=? AND user_id=? AND status='active'""", (int(time.time()),int(cleared_by_id or 0),str(cleared_by_name)[:120],str(reason)[:500],int(guild_id),int(user_id)))
    count=cur.rowcount
    conn.commit(); conn.close()
    return count

def user_warnings(guild_id,user_id,active_only=True):
    conn=db(); cur=conn.cursor()
    if active_only:
        cur.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? AND status='active' ORDER BY id DESC", (int(guild_id),int(user_id)))
    else:
        cur.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC", (int(guild_id),int(user_id)))
    rows=cur.fetchall(); conn.close(); return rows

def summary(guild_id):
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM warnings WHERE guild_id=? AND status='active'", (int(guild_id),)); active=int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) AS c FROM warnings WHERE guild_id=? AND status='cleared'", (int(guild_id),)); cleared=int(cur.fetchone()["c"] or 0)
    conn.close(); return active, cleared
