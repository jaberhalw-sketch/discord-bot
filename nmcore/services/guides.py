import time
from nmcore.db import db
from nmcore.services.settings import get_guild_settings, get_coin_name
from nmcore.ui import embed


GUIDE_INTERVAL_SECONDS = 7 * 60 * 60


def ensure_tables():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS guide_state (
        guild_id INTEGER NOT NULL,
        guide_key TEXT NOT NULL,
        last_sent INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, guide_key)
    )""")
    conn.commit()
    conn.close()


def last_sent(guild_id:int, guide_key:str)->int:
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO guide_state (guild_id,guide_key,last_sent) VALUES (?,?,0)", (int(guild_id), str(guide_key)))
    conn.commit()
    cur.execute("SELECT last_sent FROM guide_state WHERE guild_id=? AND guide_key=?", (int(guild_id), str(guide_key)))
    row = cur.fetchone()
    conn.close()
    return int(row["last_sent"] or 0) if row else 0


def mark_sent(guild_id:int, guide_key:str):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO guide_state (guild_id,guide_key,last_sent) VALUES (?,?,?)
    ON CONFLICT(guild_id,guide_key) DO UPDATE SET last_sent=excluded.last_sent""", (int(guild_id), str(guide_key), int(time.time())))
    conn.commit()
    conn.close()


def due(guild_id:int, guide_key:str)->bool:
    return int(time.time()) - last_sent(guild_id, guide_key) >= GUIDE_INTERVAL_SECONDS


def economy_guide_embed(guild_id:int):
    coin_name = get_coin_name(guild_id)
    e = embed(
        "💰 شرح نظام الاقتصاد",
        f"هنا أوامر الاقتصاد الأساسية في السيرفر. العملة الحالية: **{coin_name}**",
        "info"
    )
    e.add_field(name="رصيدك", value="`!رصيدي`\nيعرض كم معك فلوس.", inline=False)
    e.add_field(name="الراتب", value="`!راتب`\nاستلم راتبك إذا كان متاح.", inline=False)
    e.add_field(name="التحويل", value="`!تحويل @user amount`\nحوّل فلوس لعضو ثاني.", inline=False)
    e.add_field(name="الأغنى", value="`!الغني`\nيعرض أغنى الأعضاء.", inline=False)
    e.add_field(name="العقارات", value="`!متجر`\nيعرض سوق العقارات.\n`!شراء ID`\nشراء عقار.\n`!ايجار`\nاستلام الإيجار المتجمع كل 3 ساعات.\n`!مشترياتي`\nيعرض عقاراتك.", inline=False)
    e.add_field(name="ملاحظة", value="كل العمليات محفوظة في Money Tracker واللوقات.", inline=False)
    return e


def gambling_guide_embed(guild_id:int):
    e = embed(
        "🎰 شرح نظام القمار",
        "العب بمسؤولية. كل عملية محفوظة في Money Tracker و Casino Dashboard.",
        "purple"
    )
    e.add_field(name="حظ", value="`!حظ amount`\nفرصة ربح أو خسارة.", inline=False)
    e.add_field(name="دبل", value="`!دبل amount`\nمحاولة تدبيل المبلغ.", inline=False)
    e.add_field(name="سلوت", value="`!سلوت amount`\nلعبة السلوت.", inline=False)
    e.add_field(name="وجه", value="`!وجه amount`\nاختبار الحظ بالعملة.", inline=False)
    e.add_field(name="بلاك جاك", value="`!بلاكجاك amount` أو `!bj amount`\nلعبة بلاك جاك.", inline=False)
    e.add_field(name="All-in", value="تقدر تستخدم `all` بدل المبلغ في الألعاب المدعومة.", inline=False)
    e.add_field(name="ملاحظة", value="الخسارة تنخصم فعليًا، والتعادل في بلاك جاك يرجع الرهان.", inline=False)
    return e


async def send_economy_guide(guild, force=False):
    gs = get_guild_settings(guild.id)
    channel_id = int(gs.get("commands_channel_id") or 0)
    if not channel_id:
        return False

    if not force and not due(guild.id, "economy"):
        return False

    ch = guild.get_channel(channel_id)
    if not ch:
        return False

    await ch.send(embed=economy_guide_embed(guild.id))
    mark_sent(guild.id, "economy")
    return True


async def send_gambling_guide(guild, force=False):
    gs = get_guild_settings(guild.id)
    channel_id = int(gs.get("gambling_channel_id") or 0)
    if not channel_id:
        return False

    if not force and not due(guild.id, "gambling"):
        return False

    ch = guild.get_channel(channel_id)
    if not ch:
        return False

    await ch.send(embed=gambling_guide_embed(guild.id))
    mark_sent(guild.id, "gambling")
    return True


async def send_all_due_guides(bot, force=False):
    sent = 0
    for guild in getattr(bot, "guilds", []):
        try:
            if await send_economy_guide(guild, force=force):
                sent += 1
            if await send_gambling_guide(guild, force=force):
                sent += 1
        except Exception:
            pass
    return sent
