import time, sqlite3
from nmcore.db import db
from nmcore.services.economy import credit, debit, get_balance
from nmcore.services.activity import record, log_event

INCOME_COOLDOWN_SECONDS = 6 * 60 * 60
MAX_ACCUMULATED_CYCLES = 12

COMPANY_DECISIONS = {
    "marketing": {
        "name": "Marketing Campaign",
        "emoji": "📣",
        "cost": 50000,
        "field": "marketing",
        "amount": 1,
        "risk": 2,
        "rep": 1,
        "desc": "يزيد المبيعات والدخل، لكن يرفع المخاطرة شوي."
    },
    "quality": {
        "name": "Product Quality",
        "emoji": "⭐",
        "cost": 70000,
        "field": "product_quality",
        "amount": 1,
        "risk": -1,
        "rep": 3,
        "desc": "يرفع جودة الشركة والسمعة ويخلي نجاحها ثابت."
    },
    "automation": {
        "name": "Automation Upgrade",
        "emoji": "🤖",
        "cost": 100000,
        "field": "automation",
        "amount": 1,
        "risk": 1,
        "rep": 1,
        "desc": "يقلل ضغط الرواتب ويرفع صافي الربح."
    },
    "security": {
        "name": "Security & Compliance",
        "emoji": "🛡️",
        "cost": 60000,
        "field": "security_level",
        "amount": 1,
        "risk": -6,
        "rep": 1,
        "desc": "يقلل الفشل والمخاطر والضربات المفاجئة."
    },
    "innovation": {
        "name": "Innovation Lab",
        "emoji": "🧪",
        "cost": 120000,
        "field": "innovation",
        "amount": 1,
        "risk": 4,
        "rep": 2,
        "desc": "يزيد النمو والدخل، لكنه يخلي الشركة أكثر مخاطرة."
    },
    "safe": {
        "name": "Safe Strategy",
        "emoji": "🧘",
        "cost": 30000,
        "strategy": "safe",
        "risk": -4,
        "rep": 1,
        "desc": "دخل أهدأ ومخاطر أقل."
    },
    "balanced": {
        "name": "Balanced Strategy",
        "emoji": "⚖️",
        "cost": 15000,
        "strategy": "balanced",
        "risk": -1,
        "rep": 0,
        "desc": "توازن بين الربح والمخاطرة."
    },
    "aggressive": {
        "name": "Aggressive Expansion",
        "emoji": "🚀",
        "cost": 30000,
        "strategy": "aggressive",
        "risk": 8,
        "rep": 1,
        "desc": "دخل أعلى لكن احتمال الفشل والخسائر أعلى."
    },
}


SECTORS = {
    "tech": {
        "name": "Tech Startup",
        "emoji": "💻",
        "start_cost": 150000,
        "base_income": 9000,
        "upgrade_base": 100000,
        "tax_bps": 1200,
        "payroll_bps": 600,
        "risk_bps": 700,
        "desc": "دخل جيد ونمو ثابت."
    },
    "real_estate": {
        "name": "Real Estate Agency",
        "emoji": "🏢",
        "start_cost": 250000,
        "base_income": 16000,
        "upgrade_base": 160000,
        "tax_bps": 1400,
        "payroll_bps": 500,
        "risk_bps": 500,
        "desc": "دخل عالي لكن رأس المال كبير."
    },
    "logistics": {
        "name": "Logistics Company",
        "emoji": "🚚",
        "start_cost": 120000,
        "base_income": 7500,
        "upgrade_base": 85000,
        "tax_bps": 1000,
        "payroll_bps": 700,
        "risk_bps": 600,
        "desc": "شركة متوازنة ومناسبة للبداية."
    },
    "security": {
        "name": "Security Firm",
        "emoji": "🛡️",
        "start_cost": 180000,
        "base_income": 11000,
        "upgrade_base": 120000,
        "tax_bps": 1100,
        "payroll_bps": 650,
        "risk_bps": 400,
        "desc": "دخل ثابت ومخاطر قليلة."
    },
    "media": {
        "name": "Media Studio",
        "emoji": "🎬",
        "start_cost": 90000,
        "base_income": 5500,
        "upgrade_base": 65000,
        "tax_bps": 900,
        "payroll_bps": 550,
        "risk_bps": 800,
        "desc": "رخيص ومناسب للأعضاء الجدد."
    },
    "finance": {
        "name": "Investment Office",
        "emoji": "📈",
        "start_cost": 350000,
        "base_income": 24000,
        "upgrade_base": 230000,
        "tax_bps": 1800,
        "payroll_bps": 450,
        "risk_bps": 1200,
        "desc": "دخل ضخم لكن مخاطره أعلى."
    },
    "food": {
        "name": "Restaurant Chain",
        "emoji": "🍔",
        "start_cost": 110000,
        "base_income": 6500,
        "upgrade_base": 75000,
        "tax_bps": 950,
        "payroll_bps": 800,
        "risk_bps": 500,
        "desc": "دخل متوسط وتوظيف مفيد."
    },
    "casino": {
        "name": "Entertainment Group",
        "emoji": "🎰",
        "start_cost": 300000,
        "base_income": 19000,
        "upgrade_base": 200000,
        "tax_bps": 2000,
        "payroll_bps": 500,
        "risk_bps": 1500,
        "desc": "دخل عالي لكن ضريبة ومخاطر عالية."
    },
}


def _retry(fn, retries=4, delay=0.1):
    for i in range(int(retries)):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            time.sleep(delay * (i + 1))
    return {"ok": False, "error": "database_locked"}


def ensure_tables():
    def work():
        conn = db()
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            owner_name TEXT DEFAULT '',
            name TEXT NOT NULL,
            sector_key TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0,
            reputation INTEGER DEFAULT 0,
            last_income_claim INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at INTEGER NOT NULL DEFAULT 0
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS company_members (
            guild_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            user_name TEXT DEFAULT '',
            role TEXT DEFAULT 'employee',
            joined_at INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, company_id, user_id)
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS company_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            company_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            actor_id INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT 0,
            amount INTEGER DEFAULT 0,
            balance_before INTEGER DEFAULT 0,
            balance_after INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            money_tx_id TEXT DEFAULT '',
            created_at INTEGER NOT NULL DEFAULT 0
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS company_sector_settings (
            guild_id INTEGER NOT NULL,
            sector_key TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            start_cost INTEGER DEFAULT 0,
            base_income INTEGER DEFAULT 0,
            upgrade_base INTEGER DEFAULT 0,
            tax_bps INTEGER DEFAULT 0,
            payroll_bps INTEGER DEFAULT 0,
            risk_bps INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, sector_key)
        )""")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_guild_owner ON companies(guild_id, owner_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_company_ledger_company ON company_ledger(guild_id, company_id, id)")

        # Patch 56 migrations: decision-based company stats.
        migrations = [
            "ALTER TABLE companies ADD COLUMN strategy TEXT DEFAULT 'balanced'",
            "ALTER TABLE companies ADD COLUMN marketing INTEGER DEFAULT 1",
            "ALTER TABLE companies ADD COLUMN product_quality INTEGER DEFAULT 1",
            "ALTER TABLE companies ADD COLUMN automation INTEGER DEFAULT 1",
            "ALTER TABLE companies ADD COLUMN security_level INTEGER DEFAULT 1",
            "ALTER TABLE companies ADD COLUMN innovation INTEGER DEFAULT 1",
            "ALTER TABLE companies ADD COLUMN risk INTEGER DEFAULT 10",
            "ALTER TABLE companies ADD COLUMN decisions INTEGER DEFAULT 0",
            "ALTER TABLE companies ADD COLUMN failures INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                cur.execute(sql)
            except Exception:
                pass

        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)



def seed_sector_settings(guild_id:int):
    ensure_tables()

    def work():
        conn = db()
        cur = conn.cursor()
        now = int(time.time())
        for key, s in SECTORS.items():
            cur.execute("""INSERT OR IGNORE INTO company_sector_settings
            (guild_id,sector_key,enabled,start_cost,base_income,upgrade_base,tax_bps,payroll_bps,risk_bps,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (int(guild_id), key, 1, int(s["start_cost"]), int(s["base_income"]), int(s["upgrade_base"]), int(s["tax_bps"]), int(s["payroll_bps"]), int(s["risk_bps"]), now))
        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)


def sector_settings(guild_id:int):
    seed_sector_settings(guild_id)

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM company_sector_settings WHERE guild_id=?", (int(guild_id),))
        rows = {str(r["sector_key"]): dict(r) for r in cur.fetchall()}
        conn.close()
        return rows

    res = _retry(work)
    return {} if isinstance(res, dict) and not res.get("ok") else res


def sector_info_for_guild(guild_id:int, sector_key:str):
    key = str(sector_key)
    base = dict(SECTORS.get(key, SECTORS["logistics"]))
    settings = sector_settings(guild_id).get(key)

    if settings:
        base["enabled"] = int(settings.get("enabled") or 0)
        base["start_cost"] = int(settings.get("start_cost") or base["start_cost"])
        base["base_income"] = int(settings.get("base_income") or base["base_income"])
        base["upgrade_base"] = int(settings.get("upgrade_base") or base["upgrade_base"])
        base["tax_bps"] = int(settings.get("tax_bps") or base["tax_bps"])
        base["payroll_bps"] = int(settings.get("payroll_bps") or base["payroll_bps"])
        base["risk_bps"] = int(settings.get("risk_bps") or base["risk_bps"])
    else:
        base["enabled"] = 1

    return base


def update_sector_settings(guild_id:int, sector_key:str, *, enabled=None, start_cost=None, base_income=None, upgrade_base=None, tax_bps=None, payroll_bps=None, risk_bps=None):
    key = str(sector_key)
    if key not in SECTORS:
        return {"ok": False, "error": "sector not found"}

    seed_sector_settings(guild_id)
    current = sector_info_for_guild(guild_id, key)

    data = {
        "enabled": int(current.get("enabled", 1) if enabled is None else (1 if enabled else 0)),
        "start_cost": max(0, int(current["start_cost"] if start_cost is None else start_cost)),
        "base_income": max(0, int(current["base_income"] if base_income is None else base_income)),
        "upgrade_base": max(0, int(current["upgrade_base"] if upgrade_base is None else upgrade_base)),
        "tax_bps": max(0, min(10000, int(current["tax_bps"] if tax_bps is None else tax_bps))),
        "payroll_bps": max(0, min(10000, int(current["payroll_bps"] if payroll_bps is None else payroll_bps))),
        "risk_bps": max(0, min(10000, int(current["risk_bps"] if risk_bps is None else risk_bps))),
    }

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO company_sector_settings
        (guild_id,sector_key,enabled,start_cost,base_income,upgrade_base,tax_bps,payroll_bps,risk_bps,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(guild_id, sector_key) DO UPDATE SET
            enabled=excluded.enabled,
            start_cost=excluded.start_cost,
            base_income=excluded.base_income,
            upgrade_base=excluded.upgrade_base,
            tax_bps=excluded.tax_bps,
            payroll_bps=excluded.payroll_bps,
            risk_bps=excluded.risk_bps,
            updated_at=excluded.updated_at
        """, (int(guild_id), key, data["enabled"], data["start_cost"], data["base_income"], data["upgrade_base"], data["tax_bps"], data["payroll_bps"], data["risk_bps"], int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work)
    return res if isinstance(res, dict) else {"ok": True}


def active_company_count(guild_id:int, owner_id:int):
    ensure_tables()

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) c FROM companies WHERE guild_id=? AND owner_id=? AND active=1", (int(guild_id), int(owner_id)))
        row = cur.fetchone()
        conn.close()
        return int(row["c"] or 0) if row else 0

    res = _retry(work)
    return 0 if isinstance(res, dict) else int(res)


def sector_info(sector_key):
    return SECTORS.get(str(sector_key), SECTORS["logistics"])


def sectors_text(guild_id:int=None):
    lines = []
    keys = list(SECTORS.keys())
    settings = sector_settings(guild_id) if guild_id else {}

    for key in keys:
        s = sector_info_for_guild(guild_id, key) if guild_id else dict(SECTORS[key])
        enabled = "✅" if int(s.get("enabled", 1)) else "⛔"
        lines.append(f"{enabled} `{key}` {s['emoji']} **{s['name']}** — فتح: **{s['start_cost']:,}** — دخل كل 6h: **{s['base_income']:,}**")
    return "\n".join(lines)


def create_company(guild_id:int, owner_id:int, owner_name:str, sector_key:str, name:str):
    ensure_tables()
    sector_key = str(sector_key or "").lower().strip()
    if sector_key not in SECTORS:
        return {"ok": False, "error": f"القطاع غير موجود. القطاعات:\n{sectors_text(guild_id)}"}

    sector_cfg = sector_info_for_guild(guild_id, sector_key)
    if not int(sector_cfg.get("enabled", 1)):
        return {"ok": False, "error": "هذا القطاع مقفل من الداشبورد حاليًا."}

    name = str(name or "").strip()
    if len(name) < 2:
        return {"ok": False, "error": "اكتب اسم شركة صحيح."}
    if len(name) > 40:
        name = name[:40]

    if active_company_count(guild_id, owner_id) >= MAX_COMPANIES_PER_USER:
        return {"ok": False, "error": f"وصلت الحد الأقصى: {MAX_COMPANIES_PER_USER} شركات فعالة لكل عضو."}

    cost = int(sector_cfg["start_cost"])
    tx = debit(guild_id, owner_id, cost, "company_startup", user_name=owner_name, actor_id=owner_id, actor_name=owner_name, source_label=sector_key, reason=f"Start company {name}")
    if not tx.get("ok"):
        return {"ok": False, "error": "رصيدك ما يكفي لفتح الشركة."}

    now = int(time.time())

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO companies
        (guild_id,owner_id,owner_name,name,sector_key,level,balance,reputation,last_income_claim,active,created_at)
        VALUES (?,?,?,?,?,1,0,0,?,?,?)""",
        (int(guild_id), int(owner_id), str(owner_name)[:120], name, sector_key, now, 1, now))
        company_id = cur.lastrowid
        cur.execute("""INSERT OR IGNORE INTO company_members
        (guild_id,company_id,user_id,user_name,role,joined_at)
        VALUES (?,?,?,?,?,?)""", (int(guild_id), int(company_id), int(owner_id), str(owner_name)[:120], "owner", now))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company_id), "create", int(owner_id), int(owner_id), -cost, 0, 0, f"Created {name}", tx.get("tx_id",""), now))
        conn.commit()
        conn.close()
        return company_id

    company_id = _retry(work)
    if isinstance(company_id, dict):
        return {"ok": False, "error": "قاعدة البيانات مشغولة، جرب بعد ثواني."}

    record(guild_id, owner_id, owner_name, "company", "Company created", f"{name} / {sector_key}", -cost)
    log_event(guild_id, "company_create", owner_id, owner_name, 0, "", "Company created", f"{name} ({sector_key})")
    return {"ok": True, "id": int(company_id), "name": name, "sector": sector_cfg, "cost": cost}


def get_company_by_owner(guild_id:int, owner_id:int):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE guild_id=? AND owner_id=? AND active=1 ORDER BY id DESC LIMIT 1", (int(guild_id), int(owner_id)))
        row = cur.fetchone()
        conn.close()
        return row
    res = _retry(work)
    return None if isinstance(res, dict) else res


def get_company(guild_id:int, company_id:int):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE guild_id=? AND id=?", (int(guild_id), int(company_id)))
        row = cur.fetchone()
        conn.close()
        return row
    res = _retry(work)
    return None if isinstance(res, dict) else res


def company_members(guild_id:int, company_id:int):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM company_members WHERE guild_id=? AND company_id=? ORDER BY role DESC, joined_at ASC", (int(guild_id), int(company_id)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    res = _retry(work)
    return [] if isinstance(res, dict) else res


def employee_count(guild_id:int, company_id:int):
    return max(0, len([m for m in company_members(guild_id, company_id) if m.get("role") != "owner"]))


def company_stat(company, key, default=1):
    try:
        return int(company[key] or default)
    except Exception:
        return int(default)


def decision_options_text():
    lines = []
    for key, d in COMPANY_DECISIONS.items():
        lines.append(f"`{key}` {d['emoji']} **{d['name']}** — Cost **{d['cost']:,}** — {d['desc']}")
    return "\n".join(lines)


def strategy_name(company):
    s = str(company["strategy"] or "balanced")
    if s == "safe":
        return "🧘 Safe"
    if s == "aggressive":
        return "🚀 Aggressive"
    return "⚖️ Balanced"


def success_score(company):
    level = int(company["level"] or 1)
    reputation = int(company["reputation"] or 0)
    failures = int(company["failures"] or 0)
    risk = company_stat(company, "risk", 10)

    marketing = company_stat(company, "marketing", 1)
    quality = company_stat(company, "product_quality", 1)
    automation = company_stat(company, "automation", 1)
    security = company_stat(company, "security_level", 1)
    innovation = company_stat(company, "innovation", 1)
    employees = employee_count(company["guild_id"], company["id"])

    score = 35
    score += level * 3
    score += min(25, reputation // 4)
    score += min(16, employees * 2)
    score += min(18, quality * 3)
    score += min(14, security * 3)
    score += min(10, automation * 2)
    score += min(10, marketing)
    score += min(10, innovation * 2)
    score -= min(25, risk // 2)
    score -= min(20, failures * 3)

    strategy = str(company["strategy"] or "balanced")
    if strategy == "safe":
        score += 8
    elif strategy == "aggressive":
        score -= 8

    return max(5, min(98, int(score)))


def business_event(company, cycles:int=1):
    """
    A light event system. Good decisions reduce bad events; aggressive/risky choices
    increase possible profit but also increase failure chance.
    """
    risk = company_stat(company, "risk", 10)
    security = company_stat(company, "security_level", 1)
    quality = company_stat(company, "product_quality", 1)
    strategy = str(company["strategy"] or "balanced")
    score = success_score(company)

    bad_threshold = max(4, min(45, risk - security * 3 + (10 if strategy == "aggressive" else 0) - (8 if strategy == "safe" else 0)))
    good_threshold = max(6, min(45, score // 3 + quality + (8 if strategy == "aggressive" else 0)))

    seed = (int(time.time()) // INCOME_COOLDOWN_SECONDS) + int(company["id"]) * 31 + int(cycles) * 7
    roll = seed % 100

    if roll < bad_threshold:
        severity = 10 + min(35, (bad_threshold - roll))
        return {
            "type": "bad",
            "label": "Operational Problem",
            "impact_bps": -severity * 100,
            "details": "قرارك/مخاطرتك سببت مشكلة تشغيلية وانخفض الربح."
        }

    if roll > 100 - good_threshold:
        bonus = 8 + min(30, (roll - (100 - good_threshold)))
        return {
            "type": "good",
            "label": "Business Breakthrough",
            "impact_bps": bonus * 100,
            "details": "قراراتك الجيدة رفعت الأداء وجابت فرصة ربح أعلى."
        }

    return {
        "type": "normal",
        "label": "Stable Operation",
        "impact_bps": 0,
        "details": "الشركة اشتغلت بشكل طبيعي."
    }


def income_preview(company):
    sector = sector_info_for_guild(company["guild_id"], company["sector_key"])
    level = int(company["level"] or 1)
    employees = employee_count(company["guild_id"], company["id"])

    marketing = company_stat(company, "marketing", 1)
    quality = company_stat(company, "product_quality", 1)
    automation = company_stat(company, "automation", 1)
    security = company_stat(company, "security_level", 1)
    innovation = company_stat(company, "innovation", 1)
    risk = company_stat(company, "risk", 10)
    strategy = str(company["strategy"] or "balanced")

    # Multipliers from decisions. This is what makes success depend on work/choices.
    growth_bps = 10000
    growth_bps += min(3500, marketing * 250)
    growth_bps += min(4000, quality * 300)
    growth_bps += min(2800, automation * 220)
    growth_bps += min(4200, innovation * 320)
    growth_bps += min(2200, employees * 800)

    if strategy == "safe":
        growth_bps -= 600
    elif strategy == "aggressive":
        growth_bps += 1500

    gross = int(sector["base_income"] * level * growth_bps / 10000)

    tax_bps = int(sector["tax_bps"])
    if strategy == "aggressive":
        tax_bps += 250
    if strategy == "safe":
        tax_bps -= 100

    # Automation lowers payroll pressure.
    payroll_bps = max(100, int(sector["payroll_bps"]) - automation * 35)
    payroll_total = gross * min(employees, 8) * payroll_bps // 10000
    tax = gross * max(0, tax_bps) // 10000

    # Security/quality reduce operating cost from risk.
    operating_risk_cost = max(0, (risk - security * 2 - quality) * gross // 10000)

    net_company = max(0, gross - tax - payroll_total - operating_risk_cost)

    return {
        "gross": gross,
        "tax": tax,
        "payroll_total": payroll_total,
        "employee_bonus_each": (payroll_total // employees) if employees else 0,
        "operating_risk_cost": operating_risk_cost,
        "net_company": net_company,
        "employees": employees,
        "success_score": success_score(company),
        "strategy": strategy_name(company),
    }


def rent_like_remaining(company):
    now = int(time.time())
    last = int(company["last_income_claim"] or company["created_at"] or now)
    elapsed = max(0, now - last)
    cycles = elapsed // INCOME_COOLDOWN_SECONDS
    remaining = 0 if cycles > 0 else max(0, INCOME_COOLDOWN_SECONDS - elapsed)
    return int(cycles), int(remaining)


def seconds_to_text(seconds:int):
    seconds = max(0, int(seconds or 0))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h} ساعة و {m} دقيقة"
    if m:
        return f"{m} دقيقة"
    return f"{seconds} ثانية"


def collect_income(guild_id:int, owner_id:int, owner_name:str):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}

    cycles, remaining = rent_like_remaining(company)
    if cycles <= 0:
        return {"ok": False, "error": f"دخل الشركة غير جاهز. باقي: {seconds_to_text(remaining)}"}

    cycles = min(int(cycles), MAX_ACCUMULATED_CYCLES)
    preview = income_preview(company)
    event = business_event(company, cycles)
    base_total_company = preview["net_company"] * cycles
    event_delta = base_total_company * int(event["impact_bps"]) // 10000
    total_company = max(0, base_total_company + event_delta)
    employee_each = preview["employee_bonus_each"] * cycles
    employees = [m for m in company_members(guild_id, company["id"]) if m.get("role") != "owner"]

    before = int(company["balance"] or 0)
    after = before + total_company
    now = int(time.time())
    last = int(company["last_income_claim"] or company["created_at"] or now)
    new_last = last + cycles * INCOME_COOLDOWN_SECONDS

    def work():
        conn = db()
        cur = conn.cursor()
        rep_delta = cycles + (2 if event["type"] == "good" else 0)
        fail_delta = 1 if event["type"] == "bad" else 0
        cur.execute("UPDATE companies SET balance=?, last_income_claim=?, reputation=reputation+?, failures=failures+? WHERE guild_id=? AND id=?",
                    (after, new_last, rep_delta, fail_delta, int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "income_collect", int(owner_id), int(owner_id), int(total_company), before, after, f"{cycles} cycles gross={preview['gross']:,} tax={preview['tax']:,} payroll={preview['payroll_total']:,} event={event['label']} impact={event_delta:,}", "", now))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة، جرب بعد ثواني."}

    paid_employees = 0
    if employee_each > 0:
        for m in employees:
            tx = credit(guild_id, int(m["user_id"]), employee_each, "company_salary", user_name=m.get("user_name",""), actor_id=owner_id, actor_name=owner_name, source_label=str(company["id"]), reason=f"Salary from {company['name']}")
            if tx.get("ok"):
                paid_employees += 1

    record(guild_id, owner_id, owner_name, "company_income", "Company income collected", f"{company['name']} +{total_company:,}", total_company)
    return {
        "ok": True,
        "company": dict(company),
        "cycles": cycles,
        "company_amount": total_company,
        "employee_each": employee_each,
        "paid_employees": paid_employees,
        "balance_after": after,
        "preview": preview,
        "event": event,
        "event_delta": event_delta,
    }


def deposit(guild_id:int, owner_id:int, owner_name:str, amount:int):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}
    amount = max(1, int(amount))
    tx = debit(guild_id, owner_id, amount, "company_deposit", user_name=owner_name, actor_id=owner_id, actor_name=owner_name, source_label=str(company["id"]), reason=f"Deposit to {company['name']}")
    if not tx.get("ok"):
        return {"ok": False, "error": "رصيدك ما يكفي."}

    before = int(company["balance"] or 0)
    after = before + amount

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE companies SET balance=? WHERE guild_id=? AND id=?", (after, int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "deposit", int(owner_id), int(owner_id), amount, before, after, "Owner deposit", tx.get("tx_id",""), int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    _retry(work)
    return {"ok": True, "amount": amount, "balance_after": after}


def withdraw(guild_id:int, owner_id:int, owner_name:str, amount:int):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}
    amount = max(1, int(amount))
    before = int(company["balance"] or 0)
    if amount > before:
        return {"ok": False, "error": "رصيد الشركة ما يكفي."}

    after = before - amount

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE companies SET balance=? WHERE guild_id=? AND id=?", (after, int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "withdraw", int(owner_id), int(owner_id), -amount, before, after, "Owner withdraw", "", int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة."}

    tx = credit(guild_id, owner_id, amount, "company_withdraw", user_name=owner_name, actor_id=owner_id, actor_name=owner_name, source_label=str(company["id"]), reason=f"Withdraw from {company['name']}")
    return {"ok": True, "amount": amount, "balance_after": after, "tx_id": tx.get("tx_id","")}


def upgrade(guild_id:int, owner_id:int, owner_name:str):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}

    sector = sector_info_for_guild(company["guild_id"], company["sector_key"])
    level = int(company["level"] or 1)
    if level >= 10:
        return {"ok": False, "error": "الشركة وصلت أعلى مستوى 10."}

    cost = int(sector["upgrade_base"] * (level ** 1.35))
    before = int(company["balance"] or 0)
    if before < cost:
        return {"ok": False, "error": f"رصيد الشركة ما يكفي. تكلفة الترقية: {cost:,}"}

    after = before - cost
    new_level = level + 1

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE companies SET balance=?, level=? WHERE guild_id=? AND id=?", (after, new_level, int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "upgrade", int(owner_id), int(owner_id), -cost, before, after, f"Level {level} -> {new_level}", "", int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    _retry(work)
    return {"ok": True, "cost": cost, "level": new_level, "balance_after": after}


def hire(guild_id:int, owner_id:int, owner_name:str, member_id:int, member_name:str):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}
    if int(member_id) == int(owner_id):
        return {"ok": False, "error": "مالك الشركة موجود تلقائيًا."}

    members = company_members(guild_id, company["id"])
    if len(members) >= 9:
        return {"ok": False, "error": "الحد الأقصى 8 موظفين + المالك."}

    now = int(time.time())

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""INSERT OR IGNORE INTO company_members
        (guild_id,company_id,user_id,user_name,role,joined_at)
        VALUES (?,?,?,?,?,?)""", (int(guild_id), int(company["id"]), int(member_id), str(member_name)[:120], "employee", now))
        changed = cur.rowcount
        conn.commit()
        conn.close()
        return changed

    changed = _retry(work)
    if isinstance(changed, dict):
        return {"ok": False, "error": "قاعدة البيانات مشغولة."}
    if not changed:
        return {"ok": False, "error": "هذا العضو موظف بالفعل."}
    return {"ok": True, "company": dict(company), "member_id": int(member_id), "member_name": member_name}


def fire(guild_id:int, owner_id:int, owner_name:str, member_id:int):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}
    if int(member_id) == int(owner_id):
        return {"ok": False, "error": "ما تقدر تطرد المالك."}

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM company_members WHERE guild_id=? AND company_id=? AND user_id=? AND role!='owner'",
                    (int(guild_id), int(company["id"]), int(member_id)))
        changed = cur.rowcount
        conn.commit()
        conn.close()
        return changed

    changed = _retry(work)
    if isinstance(changed, dict):
        return {"ok": False, "error": "قاعدة البيانات مشغولة."}
    if not changed:
        return {"ok": False, "error": "العضو مو موظف في شركتك."}
    return {"ok": True, "company": dict(company), "member_id": int(member_id)}



def make_decision(guild_id:int, owner_id:int, owner_name:str, decision_key:str):
    company = get_company_by_owner(guild_id, owner_id)
    if not company:
        return {"ok": False, "error": "ما عندك شركة."}

    key = str(decision_key or "").lower().strip()
    if key not in COMPANY_DECISIONS:
        return {"ok": False, "error": "القرار غير موجود.\n" + decision_options_text()}

    d = COMPANY_DECISIONS[key]
    cost = int(d["cost"])
    before = int(company["balance"] or 0)

    if before < cost:
        return {"ok": False, "error": f"رصيد الشركة ما يكفي. تكلفة القرار: {cost:,}. استخدم `!شركة_ايداع` إذا تحتاج تمويل."}

    field = d.get("field")
    strategy = d.get("strategy")
    after = before - cost

    def work():
        conn = db()
        cur = conn.cursor()

        if field:
            cur.execute(f"""UPDATE companies
            SET balance=?, {field}=MIN(10,{field}+?), risk=MAX(0,MIN(100,risk+?)), reputation=reputation+?, decisions=decisions+1
            WHERE guild_id=? AND id=?""",
            (after, int(d.get("amount", 1)), int(d.get("risk", 0)), int(d.get("rep", 0)), int(guild_id), int(company["id"])))
        elif strategy:
            cur.execute("""UPDATE companies
            SET balance=?, strategy=?, risk=MAX(0,MIN(100,risk+?)), reputation=reputation+?, decisions=decisions+1
            WHERE guild_id=? AND id=?""",
            (after, str(strategy), int(d.get("risk", 0)), int(d.get("rep", 0)), int(guild_id), int(company["id"])))

        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "decision", int(owner_id), int(owner_id), -cost, before, after, f"{key}: {d['name']}", "", int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة."}

    return {"ok": True, "decision": d, "key": key, "cost": cost, "balance_after": after}


def decision_report(company):
    preview = income_preview(company)
    event = business_event(company, 1)
    return {
        "company": dict(company),
        "preview": preview,
        "next_event_preview": event,
        "risk": company_stat(company, "risk", 10),
        "marketing": company_stat(company, "marketing", 1),
        "quality": company_stat(company, "product_quality", 1),
        "automation": company_stat(company, "automation", 1),
        "security": company_stat(company, "security_level", 1),
        "innovation": company_stat(company, "innovation", 1),
        "strategy": strategy_name(company),
    }



def user_companies(guild_id:int, owner_id:int):
    ensure_tables()

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE guild_id=? AND owner_id=? AND active=1 ORDER BY id DESC", (int(guild_id), int(owner_id)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    res = _retry(work)
    return [] if isinstance(res, dict) else res


def get_company_for_owner(guild_id:int, owner_id:int, company_id:int=None):
    rows = user_companies(guild_id, owner_id)
    if not rows:
        return None

    if company_id:
        for r in rows:
            if int(r["id"]) == int(company_id):
                return r
        return None

    return rows[0]


def sell_company(guild_id:int, owner_id:int, owner_name:str, company_id:int=None):
    company = get_company_for_owner(guild_id, owner_id, company_id)
    if not company:
        return {"ok": False, "error": "الشركة غير موجودة أو ليست ملكك."}

    sector = sector_info_for_guild(guild_id, company["sector_key"])
    refund = int(int(sector["start_cost"]) * SELL_REFUND_BPS // 10000)
    company_balance = int(company["balance"] or 0)
    payout = refund + company_balance

    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE companies SET active=0, balance=0 WHERE guild_id=? AND id=? AND owner_id=?",
                    (int(guild_id), int(company["id"]), int(owner_id)))
        cur.execute("""DELETE FROM company_members
        WHERE guild_id=? AND company_id=?""", (int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "sell_company", int(owner_id), int(owner_id), int(payout), company_balance, 0, f"Sold company refund={refund:,} company_balance={company_balance:,}", "", int(time.time())))
        conn.commit()
        conn.close()
        return {"ok": True}

    res = _retry(work)
    if isinstance(res, dict) and not res.get("ok"):
        return {"ok": False, "error": "قاعدة البيانات مشغولة."}

    tx = credit(guild_id, owner_id, payout, "company_sell", user_name=owner_name, actor_id=owner_id, actor_name=owner_name, source_label=str(company["id"]), reason=f"Sold company {company['name']}")

    return {
        "ok": True,
        "company": dict(company),
        "refund": refund,
        "company_balance": company_balance,
        "payout": payout,
        "tx_id": tx.get("tx_id", ""),
    }


def top_companies(guild_id:int, limit:int=10):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT * FROM companies
        WHERE guild_id=? AND active=1
        ORDER BY level DESC, balance DESC, reputation DESC
        LIMIT ?""", (int(guild_id), int(limit)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    res = _retry(work)
    return [] if isinstance(res, dict) else res


def all_companies(guild_id:int, limit:int=200):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM companies WHERE guild_id=? ORDER BY id DESC LIMIT ?", (int(guild_id), int(limit)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    res = _retry(work)
    return [] if isinstance(res, dict) else res


def ledger(guild_id:int, company_id:int, limit:int=25):
    ensure_tables()
    def work():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM company_ledger WHERE guild_id=? AND company_id=? ORDER BY id DESC LIMIT ?", (int(guild_id), int(company_id), int(limit)))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    res = _retry(work)
    return [] if isinstance(res, dict) else res
