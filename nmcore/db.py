import sqlite3
from .config import DB_FILE, DEFAULT_COIN_NAME

def db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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
        bad_words TEXT DEFAULT 'قحبه,قحبة,كس,كسمك,fuck,shit,bitch',
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
    conn.commit()
    conn.close()
