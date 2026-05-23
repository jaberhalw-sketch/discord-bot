import time, random
from nmcore.db import db
from nmcore.config import XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX

_cooldowns={}

def get_level(guild_id:int,user_id:int):
    conn=db(); cur=conn.cursor()
    cur.execute("INSERT OR IGNORE INTO levels (guild_id,user_id,xp,level,updated_at) VALUES (?,?,0,1,?)", (int(guild_id),int(user_id),int(time.time())))
    conn.commit()
    cur.execute("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (int(guild_id),int(user_id)))
    row=cur.fetchone(); conn.close()
    return int(row["xp"]), int(row["level"])

def add_xp(guild_id:int,user_id:int,amount:int):
    xp,level=get_level(guild_id,user_id)
    xp+=int(amount)
    needed=level*100
    up=False
    while xp>=needed:
        xp-=needed; level+=1; needed=level*100; up=True
    conn=db(); cur=conn.cursor()
    cur.execute("UPDATE levels SET xp=?, level=?, updated_at=? WHERE guild_id=? AND user_id=?", (xp,level,int(time.time()),int(guild_id),int(user_id)))
    conn.commit(); conn.close()
    return xp,level,up

def message_xp(guild_id:int,user_id:int,cooldown:int):
    key=(int(guild_id),int(user_id)); now=time.time()
    if now-_cooldowns.get(key,0)<cooldown:
        return None
    _cooldowns[key]=now
    return add_xp(guild_id,user_id,random.randint(XP_PER_MESSAGE_MIN,XP_PER_MESSAGE_MAX))

def top_levels(guild_id:int,limit:int=10):
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT user_id,xp,level FROM levels WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT ?", (int(guild_id),int(limit)))
    rows=[(int(r["user_id"]),int(r["xp"]),int(r["level"])) for r in cur.fetchall()]
    conn.close(); return rows


VOICE_XP_PER_INTERVAL = 15
VOICE_XP_INTERVAL_SECONDS = 5 * 60

def voice_xp_interval():
    return VOICE_XP_INTERVAL_SECONDS

def voice_xp_amount():
    return VOICE_XP_PER_INTERVAL

def add_voice_xp(guild_id:int,user_id:int):
    return add_xp(guild_id,user_id,VOICE_XP_PER_INTERVAL)
