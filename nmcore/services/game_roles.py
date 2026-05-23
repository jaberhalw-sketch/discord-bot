from nmcore.db import db

DEFAULT_GAMES = [
    ("gta", "🚗", "GTA", "gta,grand theft auto"),
    ("valorant", "🎯", "Valorant", "valorant,فالورانت"),
    ("fortnite", "🏗️", "Fortnite", "fortnite,fort"),
    ("roblox", "🧱", "Roblox", "roblox"),
    ("minecraft", "⛏️", "Minecraft", "minecraft"),
    ("counter_strike", "🔫", "Counter Strike", "counter strike,counter-strike,cs,cs2"),
    ("dead_by_daylight", "💀", "Dead by Daylight", "dead by daylight,dbd"),
    ("overwatch", "🛡️", "Overwatch", "overwatch"),
    ("arc_raiders", "🚀", "ARC Raiders", "arc raiders,arc"),
    ("rocket_league", "⚽", "Rocket League", "rocket league"),
    ("apex_legends", "🏹", "Apex Legends", "apex legends,apex"),
    ("warzone", "🪖", "Warzone", "warzone"),
    ("rainbow_six", "🏢", "Rainbow Six Siege", "rainbow six siege,rainbow,r6"),
    ("ea_fc", "⚽", "EA FC", "ea fc,fifa"),
    ("rust", "🔨", "Rust", "rust"),
    ("league_of_legends", "⚔️", "League of Legends", "league of legends,lol"),
    ("call_of_duty", "🏅", "Call of Duty", "call of duty,cod"),
    ("among_us", "♣️", "Among Us", "among us"),
    ("the_finals", "💥", "The Finals", "the finals"),
    ("helldivers_2", "🌌", "Helldivers 2", "helldivers 2,helldivers"),
]


def ensure_tables():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS game_role_settings (
        guild_id INTEGER NOT NULL,
        game_key TEXT NOT NULL,
        emoji TEXT DEFAULT '',
        label TEXT DEFAULT '',
        aliases TEXT DEFAULT '',
        role_id INTEGER DEFAULT 0,
        enabled INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, game_key)
    )""")
    conn.commit()
    conn.close()


def seed(guild_id:int):
    ensure_tables()
    conn = db()
    cur = conn.cursor()
    for i, (key, emoji, label, aliases) in enumerate(DEFAULT_GAMES):
        cur.execute("""INSERT OR IGNORE INTO game_role_settings
        (guild_id, game_key, emoji, label, aliases, role_id, enabled, sort_order)
        VALUES (?,?,?,?,?,?,?,?)""", (int(guild_id), key, emoji, label, aliases, 0, 1, i))
    conn.commit()
    conn.close()


def rows(guild_id:int, enabled_only=False):
    seed(guild_id)
    conn = db()
    cur = conn.cursor()
    if enabled_only:
        cur.execute("SELECT * FROM game_role_settings WHERE guild_id=? AND enabled=1 ORDER BY sort_order, label", (int(guild_id),))
    else:
        cur.execute("SELECT * FROM game_role_settings WHERE guild_id=? ORDER BY sort_order, label", (int(guild_id),))
    out = [dict(r) for r in cur.fetchall()]
    conn.close()
    return out


def update_row(guild_id:int, game_key:str, *, label=None, emoji=None, aliases=None, role_id=None, enabled=None, sort_order=None):
    seed(guild_id)
    current = None
    for r in rows(guild_id):
        if r["game_key"] == game_key:
            current = r
            break
    if not current:
        return False

    data = {
        "label": current["label"],
        "emoji": current["emoji"],
        "aliases": current["aliases"],
        "role_id": int(current["role_id"] or 0),
        "enabled": int(current["enabled"] or 0),
        "sort_order": int(current["sort_order"] or 0),
    }
    if label is not None:
        data["label"] = str(label)[:80]
    if emoji is not None:
        data["emoji"] = str(emoji)[:16]
    if aliases is not None:
        data["aliases"] = str(aliases)[:300]
    if role_id is not None:
        data["role_id"] = int(role_id or 0)
    if enabled is not None:
        data["enabled"] = 1 if enabled else 0
    if sort_order is not None:
        data["sort_order"] = int(sort_order or 0)

    conn = db()
    cur = conn.cursor()
    cur.execute("""UPDATE game_role_settings
    SET label=?, emoji=?, aliases=?, role_id=?, enabled=?, sort_order=?
    WHERE guild_id=? AND game_key=?""",
    (data["label"], data["emoji"], data["aliases"], data["role_id"], data["enabled"], data["sort_order"], int(guild_id), str(game_key)))
    conn.commit()
    conn.close()
    return True
