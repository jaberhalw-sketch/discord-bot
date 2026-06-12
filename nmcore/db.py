import sqlite3
import threading
import time
from .config import DB_FILE, DEFAULT_COIN_NAME


_WRITE_LOCK = threading.RLock()


def _is_write_sql(sql: str) -> bool:
    s = str(sql or "").lstrip().upper()
    return s.startswith((
        "INSERT", "UPDATE", "DELETE", "REPLACE",
        "CREATE", "ALTER", "DROP", "BEGIN", "COMMIT", "ROLLBACK"
    ))


class SafeCursor:
    def __init__(self, conn, cursor):
        self._safe_conn = conn
        self._cursor = cursor

    def execute(self, sql, params=()):
        if _is_write_sql(sql):
            self._safe_conn._acquire_write()
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        if _is_write_sql(sql):
            self._safe_conn._acquire_write()
        return self._cursor.executemany(sql, seq_of_params)

    def executescript(self, sql_script):
        self._safe_conn._acquire_write()
        return self._cursor.executescript(sql_script)

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class SafeConnection:
    def __init__(self, raw):
        self._raw = raw
        self._lock_acquired = False

    def _acquire_write(self):
        if not self._lock_acquired:
            # Never block Discord heartbeat forever.
            acquired = _WRITE_LOCK.acquire(timeout=1)
            if not acquired:
                raise sqlite3.OperationalError("database is locked: python write lock timeout")
            self._lock_acquired = True

    def _release_write(self):
        if self._lock_acquired:
            self._lock_acquired = False
            try:
                _WRITE_LOCK.release()
            except RuntimeError:
                pass

    def cursor(self, *args, **kwargs):
        return SafeCursor(self, self._raw.cursor(*args, **kwargs))

    def execute(self, sql, params=()):
        if _is_write_sql(sql):
            self._acquire_write()
        return self._raw.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        if _is_write_sql(sql):
            self._acquire_write()
        return self._raw.executemany(sql, seq_of_params)

    def executescript(self, sql_script):
        self._acquire_write()
        return self._raw.executescript(sql_script)

    def commit(self):
        try:
            return self._raw.commit()
        finally:
            self._release_write()

    def rollback(self):
        try:
            return self._raw.rollback()
        finally:
            self._release_write()

    def close(self):
        try:
            return self._raw.close()
        finally:
            self._release_write()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

    def __getattr__(self, name):
        return getattr(self._raw, name)


def db():
    raw = sqlite3.connect(DB_FILE, timeout=1, check_same_thread=False)
    raw.row_factory = sqlite3.Row

    try:
        raw.execute("PRAGMA busy_timeout = 1000")
        raw.execute("PRAGMA journal_mode = WAL")
        raw.execute("PRAGMA synchronous = NORMAL")
        raw.execute("PRAGMA temp_store = MEMORY")
        raw.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass

    return SafeConnection(raw)


def execute_with_retry(fn, retries=3, delay=0.08):
    last = None
    for attempt in range(int(retries)):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(delay * (attempt + 1))
    raise last

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id INTEGER PRIMARY KEY,
        guild_name TEXT DEFAULT '',
        coin_name TEXT DEFAULT 'NM Coin',
        commands_channel_id INTEGER DEFAULT 0,
        gambling_channel_id INTEGER DEFAULT 0,
        logs_channel_id INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0,
        updated_at INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS system_toggles (
        guild_id INTEGER NOT NULL,
        system_key TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, system_key)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS balances (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        balance INTEGER NOT NULL DEFAULT 0,
        last_salary INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS money_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_id TEXT UNIQUE NOT NULL,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        actor_id INTEGER DEFAULT 0,
        actor_name TEXT DEFAULT '',
        amount INTEGER NOT NULL,
        balance_before INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        source_type TEXT NOT NULL,
        source_label TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        reference_type TEXT DEFAULT '',
        reference_id TEXT DEFAULT '',
        related_user_id INTEGER DEFAULT 0,
        channel_id INTEGER DEFAULT 0,
        message_id INTEGER DEFAULT 0,
        metadata_json TEXT DEFAULT '{}',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS levels (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        xp INTEGER NOT NULL DEFAULT 0,
        level INTEGER NOT NULL DEFAULT 1,
        updated_at INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        moderator_id INTEGER DEFAULT 0,
        moderator_name TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        message TEXT DEFAULT '',
        status TEXT DEFAULT 'active',
        created_at INTEGER NOT NULL,
        cleared_at INTEGER DEFAULT 0,
        cleared_by_id INTEGER DEFAULT 0,
        cleared_by_name TEXT DEFAULT '',
        clear_reason TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS protection_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        bad_words_enabled INTEGER DEFAULT 1,
        links_enabled INTEGER DEFAULT 1,
        spam_enabled INTEGER DEFAULT 1,
        mass_mention_enabled INTEGER DEFAULT 1,
        delete_messages INTEGER DEFAULT 1,
        timeout_enabled INTEGER DEFAULT 0,
        bad_words TEXT DEFAULT "قواد,خنيث,قحبه,قحبة,شرموط,شرموطه,شرموطة,سالب,كس,كس امك,كس اختك,كس اخوك,كس والديك,كسمك,كسمكم,كسمه,كسم,كسختك,كسامك,كساختك,كساخوك,كسابوك,كسس,كسي,كسى,كىس,كءس,طيزي,طيزك,طيز,انيكك,انيك,انيككك,انيك ابوك,انيك اختك,انيك اخوك,انيك امك,ازغب,جرار,معرس,اعرسك,ممحون,ممحونه,ممحونة,ممحونهه,محنه,محنة,العقه,العقة,قضي,زبي,زب,زبك,زبه,زبري,زنى,زاني,زانيه,زنوه,فقحة,فقحه,عيري,عيرك,عير,منيكه,منيوك,منيوكه,منيك,متناك,متناكه,مفتوحه,مقحب,مقحبه,ناك,نيك,مص,مصه,مصي,مصزبي,مص لين تغص,مص لين تنام,الحس,الحسيه,لحس,العق,خول,ديوث,عرص,عرصه,ياعرص,ياعرصه,قحب,قحبة*,قحبه في قحبه,يقحبه,ياقحبة,ياقحبه,بنت القحبه,يابن القحبه,يابن القحب,يابن القحاب,يابن الستين قحبه,يابن الشرموطه,يابن الشراميط,يابن المتناك,يابن المتناكه,يابن المتانيك,يابن الحرام,يبن الحرام,ابن حرام,ابن قحب,ابن قحبه,ابن الزاني,ابن الزانيه,يابن الزانيه,يا خول,يخول,يابن الخول,يابن الديوث,يابن الديوثه,ياشرموط,ياشرموطه,يازانيه,يزبي,يا ابن زبي,ياكسمك,ياكسختك,يكسمك,يامتناك,يامتناكه,يامهان,يامهانه,مهان,مهانه,جلخ,جلخت,اجلخ,اجلخ عليك,اركب عليه,اركبه,اركبي عليه,اركب على زبي,اركب علي زبي,اركب على الغالي,اركب علي الغالي,تعال اركب على زبي,على زبي,عض الغالي,تبي تتناك,تبي تمص,سكس,سكىس,سىكىس,سىكس,كلزب,كل زق يبن الشرمطه,نظام مقحبه,fuck,fucking,fucked,fucker,motherfucker,shit,bullshit,bitch,bitches,asshole,dick,cock,pussy,cunt,slut,whore,sex,suck my dick,smd,stfu,kys,3leh,3r9,3r9h,5alk,5altk,87bh,a5ok,a5tk,abok,aft7k,agl5,ajl5,al3a'le,al3'aly,al87bh,amk,anek,anekk,arkb,arkb 3leh,arkbe,arkbh,arkby,bzne,bzny,g7bh,ghbh,jtle5,ks,ks a5tk,ks-mk,ks5tk,kse,ksmk,ksy,lanek,m3r9,m7nh,m87bh,m9,mfto7,mfto7h,mhan,mhanh,mm7on,mm7onh,mnyok,mtnak,mtnakh,sharmo6h,shrame6,shrm6h,shrmo6h,shrmoth,sks,tjl5,tm9,tm9en,y87bh,ya87bh,yabn,ybn,zane,zaneh,zany,zanyh,zbe,zbo,zby,zpe,zpo,kos,kosk,kosmk,kosomk,kos omk,kos amk,zob,zeb,zebi,zebak,ayri,ayrk,eeri,3air,neek,nek,anik,aneek,aneekk,sharmoot,sharmoota,sharmouta,qahba,gahba,8ahba,9ahba,khaneeth,khaneth,5aneeth,teez,teezak,teezy,6eez,mamhon,mamhoon",
        ignored_channels TEXT DEFAULT '',
        whitelist_roles TEXT DEFAULT '',
        updated_at INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS log_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        user_id INTEGER DEFAULT 0,
        user_name TEXT DEFAULT '',
        channel_id INTEGER DEFAULT 0,
        channel_name TEXT DEFAULT '',
        title TEXT DEFAULT '',
        details TEXT DEFAULT '',
        metadata_json TEXT DEFAULT '{}',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        type_key TEXT NOT NULL,
        unit_number INTEGER NOT NULL,
        display_name TEXT NOT NULL,
        owner_id INTEGER NOT NULL DEFAULT 0,
        owner_name TEXT DEFAULT '',
        level INTEGER NOT NULL DEFAULT 1,
        price INTEGER NOT NULL,
        rent INTEGER NOT NULL,
        for_sale_price INTEGER NOT NULL DEFAULT 0,
        last_rent_claim INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        UNIQUE(guild_id, type_key, unit_number)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS property_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        property_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        old_owner_id INTEGER DEFAULT 0,
        new_owner_id INTEGER DEFAULT 0,
        actor_id INTEGER DEFAULT 0,
        amount INTEGER DEFAULT 0,
        level_before INTEGER DEFAULT 0,
        level_after INTEGER DEFAULT 0,
        price_before INTEGER DEFAULT 0,
        price_after INTEGER DEFAULT 0,
        reason TEXT DEFAULT '',
        money_tx_id TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        prize TEXT NOT NULL,
        winner_count INTEGER DEFAULT 1,
        created_by_id INTEGER DEFAULT 0,
        created_by_name TEXT DEFAULT '',
        status TEXT DEFAULT 'open',
        created_at INTEGER NOT NULL,
        ended_at INTEGER DEFAULT 0
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS shop_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        price INTEGER NOT NULL,
        money_tx_id TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS live_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        actor_id INTEGER DEFAULT 0,
        actor_name TEXT DEFAULT '',
        activity_type TEXT NOT NULL,
        title TEXT DEFAULT '',
        details TEXT DEFAULT '',
        amount INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ai_image_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        image_channel_id INTEGER DEFAULT 0,
        log_channel_id INTEGER DEFAULT 0,
        daily_limit_per_user INTEGER DEFAULT 5,
        daily_limit_server INTEGER DEFAULT 30,
        cooldown_seconds INTEGER DEFAULT 60,
        image_size TEXT DEFAULT '1024x1024',
        image_quality TEXT DEFAULT 'medium',
        image_model TEXT DEFAULT 'gpt-image-1',
        allowed_role_ids TEXT DEFAULT '',
        block_bad_prompts INTEGER DEFAULT 1,
        updated_at INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ai_image_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        channel_id INTEGER DEFAULT 0,
        prompt TEXT DEFAULT '',
        action_type TEXT DEFAULT 'generate',
        image_model TEXT DEFAULT 'gpt-image-1',
        image_size TEXT DEFAULT '1024x1024',
        image_quality TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'ok',
        error_message TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS runtime_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT DEFAULT '',
        error_type TEXT DEFAULT '',
        message TEXT DEFAULT '',
        traceback TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_balances_guild_balance ON balances(guild_id, balance DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_guild_user_time ON money_ledger(guild_id, user_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_money_guild_time ON money_ledger(guild_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_levels_guild_level ON levels(guild_id, level DESC, xp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_guild_time ON log_events(guild_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_live_guild_time ON live_activity(guild_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_image_logs_guild_time ON ai_image_logs(guild_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_image_logs_user_time ON ai_image_logs(guild_id, user_id, created_at DESC)")
    conn.commit()
    conn.close()
