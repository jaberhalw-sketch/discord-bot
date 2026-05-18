import re, time
from nmcore.db import db
from nmcore.services.activity import log_event

def get_settings(guild_id:int)->dict:
    conn=db(); cur=conn.cursor()
    cur.execute("INSERT OR IGNORE INTO protection_settings (guild_id,updated_at) VALUES (?,?)", (int(guild_id),int(time.time())))
    conn.commit()
    cur.execute("SELECT * FROM protection_settings WHERE guild_id=?", (int(guild_id),))
    row=cur.fetchone(); conn.close()
    return dict(row) if row else {}

def update_settings(guild_id:int, data:dict):
    old=get_settings(guild_id)
    keys=["enabled","bad_words_enabled","links_enabled","spam_enabled","mass_mention_enabled","delete_messages","timeout_enabled","bad_words","ignored_channels","whitelist_roles"]
    vals={}
    for k in keys:
        if k in data:
            vals[k]=data[k]
    if not vals: return
    conn=db(); cur=conn.cursor()
    sets=", ".join([f"{k}=?" for k in vals]) + ", updated_at=?"
    params=list(vals.values())+[int(time.time()),int(guild_id)]
    cur.execute(f"UPDATE protection_settings SET {sets} WHERE guild_id=?", params)
    conn.commit(); conn.close()

def normalize(text):
    text=str(text or "").lower()
    repl={"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ؤ":"و","ئ":"ي","ـ":""}
    for a,b in repl.items(): text=text.replace(a,b)
    text=re.sub(r"[^a-z0-9\u0600-\u06FF]+"," ",text)
    text=re.sub(r"(.)\1{2,}",r"\1",text)
    return re.sub(r"\s+"," ",text).strip()

def contains_bad(text, words):
    msg=normalize(text); tokens=set(msg.split())
    for raw in words:
        w=normalize(raw)
        if not w: continue
        parts=w.split()
        if len(parts)==1:
            if parts[0] in tokens: return True
        else:
            pat=r"(?<![\w\u0600-\u06FF])"+r"\s+".join(re.escape(p) for p in parts)+r"(?![\w\u0600-\u06FF])"
            if re.search(pat,msg): return True
    return False

def has_link(text):
    return bool(re.search(r"https?://|discord\.gg/|www\.", str(text or ""), re.I))
