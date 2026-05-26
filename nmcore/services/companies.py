import time, sqlite3
from nmcore.db import db
from nmcore.services.economy import credit, debit, get_balance
from nmcore.services.activity import record, log_event

INCOME_COOLDOWN_SECONDS = 6 * 60 * 60
MAX_ACCUMULATED_CYCLES = 12

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

        cur.execute("CREATE INDEX IF NOT EXISTS idx_companies_guild_owner ON companies(guild_id, owner_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_company_ledger_company ON company_ledger(guild_id, company_id, id)")

        conn.commit()
        conn.close()
        return {"ok": True}

    return _retry(work)


def sector_info(sector_key):
    return SECTORS.get(str(sector_key), SECTORS["logistics"])


def sectors_text():
    lines = []
    for key, s in SECTORS.items():
        lines.append(f"`{key}` {s['emoji']} **{s['name']}** — فتح: **{s['start_cost']:,}** — دخل كل 6h: **{s['base_income']:,}**")
    return "\n".join(lines)


def create_company(guild_id:int, owner_id:int, owner_name:str, sector_key:str, name:str):
    ensure_tables()
    sector_key = str(sector_key or "").lower().strip()
    if sector_key not in SECTORS:
        return {"ok": False, "error": f"القطاع غير موجود. القطاعات:\n{sectors_text()}"}

    name = str(name or "").strip()
    if len(name) < 2:
        return {"ok": False, "error": "اكتب اسم شركة صحيح."}
    if len(name) > 40:
        name = name[:40]

    def read_existing():
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies WHERE guild_id=? AND owner_id=? AND active=1", (int(guild_id), int(owner_id)))
        row = cur.fetchone()
        conn.close()
        return row

    if _retry(read_existing):
        return {"ok": False, "error": "عندك شركة فعالة بالفعل. تقدر تملك شركة واحدة فقط حاليًا."}

    cost = int(SECTORS[sector_key]["start_cost"])
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
    return {"ok": True, "id": int(company_id), "name": name, "sector": SECTORS[sector_key], "cost": cost}


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


def income_preview(company):
    sector = sector_info(company["sector_key"])
    level = int(company["level"] or 1)
    employees = employee_count(company["guild_id"], company["id"])

    gross = int(sector["base_income"] * level * (1 + min(employees, 8) * 0.08))
    tax = gross * int(sector["tax_bps"]) // 10000
    payroll_total = gross * min(employees, 8) * int(sector["payroll_bps"]) // 10000
    net_company = max(0, gross - tax - payroll_total)

    return {
        "gross": gross,
        "tax": tax,
        "payroll_total": payroll_total,
        "employee_bonus_each": (payroll_total // employees) if employees else 0,
        "net_company": net_company,
        "employees": employees,
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
    total_company = preview["net_company"] * cycles
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
        cur.execute("UPDATE companies SET balance=?, last_income_claim=?, reputation=reputation+? WHERE guild_id=? AND id=?",
                    (after, new_last, cycles, int(guild_id), int(company["id"])))
        cur.execute("""INSERT INTO company_ledger
        (guild_id,company_id,action,actor_id,user_id,amount,balance_before,balance_after,details,money_tx_id,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (int(guild_id), int(company["id"]), "income_collect", int(owner_id), int(owner_id), int(total_company), before, after, f"{cycles} cycles gross={preview['gross']:,} tax={preview['tax']:,} payroll={preview['payroll_total']:,}", "", now))
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

    sector = sector_info(company["sector_key"])
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
