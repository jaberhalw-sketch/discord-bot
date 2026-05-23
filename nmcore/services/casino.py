import random, time
from nmcore.config import CASINO_COOLDOWN_SECONDS
from nmcore.db import db
from nmcore.services.economy import get_balance, debit, credit

_last_play = {}

DEFAULTS = {
    "luck_chance": 42,
    "double_chance": 38,
    "flip_chance": 47,
    "max_bet": 0,
    "enabled_games": "luck,double,slot,flip,blackjack",
}


def ensure_tables():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS casino_settings (
        guild_id INTEGER PRIMARY KEY,
        luck_chance INTEGER DEFAULT 42,
        double_chance INTEGER DEFAULT 38,
        flip_chance INTEGER DEFAULT 47,
        max_bet INTEGER DEFAULT 0,
        enabled_games TEXT DEFAULT 'luck,double,slot,flip,blackjack',
        updated_at INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()


def get_settings(guild_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT OR IGNORE INTO casino_settings
    (guild_id,luck_chance,double_chance,flip_chance,max_bet,enabled_games,updated_at)
    VALUES (?,?,?,?,?,?,?)""",
    (int(guild_id), DEFAULTS["luck_chance"], DEFAULTS["double_chance"], DEFAULTS["flip_chance"], DEFAULTS["max_bet"], DEFAULTS["enabled_games"], int(time.time())))
    conn.commit()
    cur.execute("SELECT * FROM casino_settings WHERE guild_id=?", (int(guild_id),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else dict(DEFAULTS)


def update_settings(guild_id:int, *, luck_chance=None, double_chance=None, flip_chance=None, max_bet=None, enabled_games=None):
    current = get_settings(guild_id)
    data = {
        "luck_chance": int(current.get("luck_chance") or DEFAULTS["luck_chance"]),
        "double_chance": int(current.get("double_chance") or DEFAULTS["double_chance"]),
        "flip_chance": int(current.get("flip_chance") or DEFAULTS["flip_chance"]),
        "max_bet": int(current.get("max_bet") or 0),
        "enabled_games": str(current.get("enabled_games") or DEFAULTS["enabled_games"]),
    }
    if luck_chance is not None:
        data["luck_chance"] = max(0, min(100, int(luck_chance)))
    if double_chance is not None:
        data["double_chance"] = max(0, min(100, int(double_chance)))
    if flip_chance is not None:
        data["flip_chance"] = max(0, min(100, int(flip_chance)))
    if max_bet is not None:
        data["max_bet"] = max(0, int(max_bet or 0))
    if enabled_games is not None:
        data["enabled_games"] = ",".join([x.strip() for x in str(enabled_games).split(",") if x.strip()])

    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO casino_settings
    (guild_id,luck_chance,double_chance,flip_chance,max_bet,enabled_games,updated_at)
    VALUES (?,?,?,?,?,?,?)
    ON CONFLICT(guild_id) DO UPDATE SET
      luck_chance=excluded.luck_chance,
      double_chance=excluded.double_chance,
      flip_chance=excluded.flip_chance,
      max_bet=excluded.max_bet,
      enabled_games=excluded.enabled_games,
      updated_at=excluded.updated_at""",
    (int(guild_id), data["luck_chance"], data["double_chance"], data["flip_chance"], data["max_bet"], data["enabled_games"], int(time.time())))
    conn.commit()
    conn.close()


def _enabled(settings, game):
    aliases = {
        "حظ": "luck", "دبل": "double", "سلوت": "slot", "وجه": "flip", "بلاكجاك": "blackjack", "bj": "blackjack"
    }
    key = aliases.get(game, game)
    enabled = {x.strip() for x in str(settings.get("enabled_games") or "").split(",")}
    return key in enabled


def parse_bet(text, balance:int):
    s=str(text).strip().lower().replace(",","")
    if s in {"all","الكل","فل"}:
        return int(balance)
    mult=1
    if s.endswith("k"):
        mult=1000; s=s[:-1]
    elif s.endswith("m"):
        mult=1000000; s=s[:-1]
    try:
        return int(float(s)*mult)
    except Exception:
        return None


def _cooldown_ok(guild_id:int,user_id:int):
    key=(int(guild_id),int(user_id))
    now=time.time()
    if now-_last_play.get(key,0) < CASINO_COOLDOWN_SECONDS:
        return False
    _last_play[key]=now
    return True


def play(guild_id:int,user_id:int,user_name:str,game:str,bet_text,channel_id=0,message_id=0):
    settings = get_settings(guild_id)

    if not _enabled(settings, game):
        return {"ok":False,"error":"هذه اللعبة مقفلة من الداشبورد."}

    if not _cooldown_ok(guild_id,user_id):
        return {"ok":False,"error":f"انتظر {CASINO_COOLDOWN_SECONDS} ثواني بين اللعبات."}

    bal=get_balance(guild_id,user_id)
    bet=parse_bet(bet_text,bal)

    if bet is None or bet<=0:
        return {"ok":False,"error":"اكتب مبلغ صحيح."}
    if bet>bal:
        return {"ok":False,"error":f"رصيدك ما يكفي. رصيدك: {bal:,}"}

    max_bet = int(settings.get("max_bet") or 0)
    if max_bet and bet > max_bet:
        return {"ok":False,"error":f"الحد الأعلى للرهان هو {max_bet:,}."}

    before=bal
    bet_tx=debit(guild_id,user_id,bet,"casino_bet",user_name=user_name,source_label=game,reason=f"Bet on {game}",channel_id=channel_id,message_id=message_id,metadata={"game":game})

    if not bet_tx["ok"]:
        return {"ok":False,"error":"رصيدك ما يكفي."}

    outcome="lose"
    payout=0
    detail=""

    if game in {"luck","حظ"}:
        win=random.random() < (int(settings.get("luck_chance") or 42) / 100)
        outcome="win" if win else "lose"
        payout=bet*2 if win else 0
        detail="الحظ وقف معك" if win else "الحظ ضدك"

    elif game in {"double","دبل"}:
        win=random.random() < (int(settings.get("double_chance") or 38) / 100)
        outcome="win" if win else "lose"
        payout=bet*2 if win else 0
        detail="الدبل نجح" if win else "الدبل فشل"

    elif game in {"flip","وجه"}:
        win=random.random() < (int(settings.get("flip_chance") or 47) / 100)
        outcome="win" if win else "lose"
        payout=bet*2 if win else 0
        detail="العملة معك" if win else "العملة ضدك"

    elif game in {"slot","سلوت"}:
        icons=["🍒","🍋","💎","7️⃣","⭐","🍉"]
        roll=[random.choice(icons) for _ in range(3)]
        detail=" ".join(roll)
        if len(set(roll))==1:
            outcome="win"; payout=bet*4
        elif len(set(roll))==2:
            outcome="win"; payout=max(1, int(bet*1.5))
        else:
            outcome="lose"; payout=0

    elif game in {"blackjack","bj","بلاكجاك"}:
        player=random.randint(15,23); dealer=random.randint(16,22)
        detail=f"أنت {player} | الديلر {dealer}"
        if player>21:
            outcome="lose"
        elif dealer>21 or player>dealer:
            outcome="win"; payout=bet*2
        elif player==dealer:
            outcome="draw"; payout=bet
        else:
            outcome="lose"
    else:
        outcome="lose"; payout=0; detail="لعبة غير معروفة"

    payout_tx=None
    if payout>0:
        payout_tx=credit(guild_id,user_id,payout,"casino_payout",user_name=user_name,source_label=game,reason=f"{game} {outcome}",reference_id=bet_tx["tx_id"],channel_id=channel_id,message_id=message_id,metadata={"game":game,"outcome":outcome})

    after=get_balance(guild_id,user_id)
    return {"ok":True,"game":game,"bet":bet,"before":before,"after":after,"outcome":outcome,"payout":payout,"net":after-before,"detail":detail,"bet_tx":bet_tx.get("tx_id"),"payout_tx":payout_tx.get("tx_id") if payout_tx else ""}
