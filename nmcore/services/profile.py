from nmcore.db import db


def _fetchone_dict(cur):
    row = cur.fetchone()
    return dict(row) if row else {}


def _fetchall_dict(cur):
    return [dict(r) for r in cur.fetchall()]


def get_user_profile(guild_id:int, user_id:int):
    gid = int(guild_id)
    uid = int(user_id)

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (gid, uid))
    balance = _fetchone_dict(cur).get("balance", 0) or 0

    cur.execute("SELECT xp, level FROM levels WHERE guild_id=? AND user_id=?", (gid, uid))
    level_row = _fetchone_dict(cur)
    xp = int(level_row.get("xp") or 0)
    level = int(level_row.get("level") or 1)

    cur.execute("""SELECT
    COUNT(*) rows,
    COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) gained,
    COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) spent,
    COALESCE(SUM(amount),0) net,
    COALESCE(MAX(created_at),0) last_tx
    FROM money_ledger WHERE guild_id=? AND user_id=?""", (gid, uid))
    money = _fetchone_dict(cur)

    cur.execute("""SELECT source_type, COUNT(*) rows,
    COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) gained,
    COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) spent,
    COALESCE(SUM(amount),0) net
    FROM money_ledger
    WHERE guild_id=? AND user_id=?
    GROUP BY source_type
    ORDER BY rows DESC LIMIT 20""", (gid, uid))
    money_sources = _fetchall_dict(cur)

    cur.execute("SELECT * FROM money_ledger WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 20", (gid, uid))
    recent_money = _fetchall_dict(cur)

    cur.execute("""SELECT
    COUNT(*) total,
    SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active,
    SUM(CASE WHEN status='cleared' THEN 1 ELSE 0 END) cleared
    FROM warnings WHERE guild_id=? AND user_id=?""", (gid, uid))
    warnings = _fetchone_dict(cur)

    cur.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 10", (gid, uid))
    recent_warnings = _fetchall_dict(cur)

    cur.execute("""SELECT COUNT(*) count,
    COALESCE(SUM(rent * level),0) rent_total,
    COALESCE(SUM(price),0) property_value
    FROM properties WHERE guild_id=? AND owner_id=?""", (gid, uid))
    props_summary = _fetchone_dict(cur)

    cur.execute("SELECT * FROM properties WHERE guild_id=? AND owner_id=? ORDER BY price DESC, id ASC LIMIT 10", (gid, uid))
    properties = _fetchall_dict(cur)

    cur.execute("""SELECT COUNT(*) c, COALESCE(SUM(amount),0) total
    FROM boost_events WHERE guild_id=? AND user_id=?""", (gid, uid))
    boosts = _fetchone_dict(cur)

    cur.execute("""SELECT active, boost_count, reward_total, premium_since, first_boost_at, last_boost_at
    FROM boosters WHERE guild_id=? AND user_id=?""", (gid, uid))
    booster_profile = _fetchone_dict(cur)

    cur.execute("""SELECT COUNT(*) posts, COALESCE(SUM(amount),0) total
    FROM post_rewards WHERE guild_id=? AND user_id=?""", (gid, uid))
    post_rewards = _fetchone_dict(cur)

    cur.execute("""SELECT COUNT(*) plays,
    COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) wagered,
    COALESCE(SUM(CASE WHEN source_type='casino_payout' THEN amount ELSE 0 END),0) paid,
    COALESCE(SUM(amount),0) net
    FROM money_ledger
    WHERE guild_id=? AND user_id=? AND source_type IN ('casino_bet','casino_payout')""", (gid, uid))
    casino = _fetchone_dict(cur)

    conn.close()

    achievements = build_achievements(
        balance=int(balance or 0),
        level=level,
        xp=xp,
        money=money,
        warnings=warnings,
        props_summary=props_summary,
        boosts=boosts,
        booster_profile=booster_profile,
        post_rewards=post_rewards,
        casino=casino,
    )

    return {
        "guild_id": gid,
        "user_id": uid,
        "balance": int(balance or 0),
        "xp": xp,
        "level": level,
        "money": money,
        "money_sources": money_sources,
        "recent_money": recent_money,
        "warnings": warnings,
        "recent_warnings": recent_warnings,
        "props_summary": props_summary,
        "properties": properties,
        "boosts": boosts,
        "booster_profile": booster_profile,
        "post_rewards": post_rewards,
        "casino": casino,
        "achievements": achievements,
    }


def build_achievements(*, balance, level, xp, money, warnings, props_summary, boosts, booster_profile, post_rewards, casino):
    out = []

    def add(key, title, emoji, desc, unlocked=True):
        if unlocked:
            out.append({"key": key, "title": title, "emoji": emoji, "desc": desc})

    gained = int(money.get("gained") or 0)
    spent = int(money.get("spent") or 0)
    net = int(money.get("net") or 0)
    active_warnings = int(warnings.get("active") or 0)
    property_count = int(props_summary.get("count") or 0)
    boost_count = int(booster_profile.get("boost_count") or boosts.get("c") or 0)
    post_count = int(post_rewards.get("posts") or 0)
    casino_plays = int(casino.get("plays") or 0)
    casino_net = int(casino.get("net") or 0)

    add("rich_100k", "Rich Boy", "💰", "وصل 100k رصيد.", balance >= 100_000)
    add("millionaire", "Millionaire", "👑", "وصل مليون رصيد.", balance >= 1_000_000)
    add("level_10", "Active Member", "📊", "وصل Level 10.", level >= 10)
    add("level_25", "Grinder", "🔥", "وصل Level 25.", level >= 25)
    add("clean_record", "Clean Record", "🛡️", "ما عنده تحذيرات فعالة.", active_warnings == 0)
    add("landlord", "Landlord", "🏘️", "يمتلك 3 عقارات أو أكثر.", property_count >= 3)
    add("tycoon", "Tycoon", "🏙️", "يمتلك 5 عقارات أو أكثر.", property_count >= 5)
    add("booster", "Booster", "🚀", "سوّى Server Boost.", boost_count >= 1)
    add("super_booster", "Super Booster", "💎", "عنده 3 Boost Events أو أكثر.", boost_count >= 3)
    add("poster", "Poster", "📝", "أخذ مكافآت بوست 10 مرات.", post_count >= 10)
    add("casino_player", "Casino Player", "🎰", "لعب كازينو 25 مرة.", casino_plays >= 25)
    add("casino_winner", "Casino Winner", "🍀", "صافي القمار عنده موجب.", casino_net > 0)
    add("big_spender", "Big Spender", "💸", "صرف أو خسر أكثر من 100k.", spent >= 100_000)
    add("earner", "Earner", "📈", "جمع أكثر من 250k من المصادر المختلفة.", gained >= 250_000)
    add("positive_net", "Positive Net", "✅", "الصافي المالي موجب.", net > 0)

    return out


def profile_title(profile):
    balance = int(profile.get("balance") or 0)
    level = int(profile.get("level") or 1)
    props = int(profile.get("props_summary", {}).get("count") or 0)
    casino_net = int(profile.get("casino", {}).get("net") or 0)
    active_warnings = int(profile.get("warnings", {}).get("active") or 0)

    if active_warnings >= 5:
        return "⚠️ Trouble Maker"
    if balance >= 1_000_000:
        return "👑 Millionaire"
    if props >= 5:
        return "🏙️ Real Estate Tycoon"
    if casino_net > 0 and casino_net >= 100_000:
        return "🍀 Casino Winner"
    if level >= 25:
        return "🔥 Server Grinder"
    if balance >= 100_000:
        return "💰 Rich Boy"
    return "👤 Member"


def risk_score(profile):
    score = 0
    reasons = []

    active_warnings = int(profile.get("warnings", {}).get("active") or 0)
    spent = int(profile.get("money", {}).get("spent") or 0)
    gained = int(profile.get("money", {}).get("gained") or 0)
    casino_plays = int(profile.get("casino", {}).get("plays") or 0)
    casino_net = int(profile.get("casino", {}).get("net") or 0)

    if active_warnings >= 3:
        score += 30
        reasons.append("تحذيرات فعالة كثيرة")
    elif active_warnings:
        score += 10
        reasons.append("عنده تحذيرات فعالة")

    if casino_plays >= 100:
        score += 20
        reasons.append("نشاط قمار عالي")
    elif casino_plays >= 30:
        score += 10
        reasons.append("يلعب قمار كثير")

    if spent >= 500_000:
        score += 15
        reasons.append("صرف/خسارة عالية")

    if gained >= 1_000_000:
        score += 10
        reasons.append("دخل عالي جدًا يحتاج متابعة")

    if casino_net >= 500_000:
        score += 20
        reasons.append("ربح قمار عالي جدًا")

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("طبيعي")

    return {"score": score, "reasons": reasons}
