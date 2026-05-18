import os, time, html, json, urllib.parse, urllib.request, urllib.error
from flask import Flask, request, redirect, session
from nmcore.config import DASHBOARD_SECRET_KEY, DB_FILE
from nmcore.db import db, init_db
from nmcore.ui import page
from nmcore.services.settings import ensure_guild, get_coin_name, set_coin_name, all_toggles, set_system_enabled, get_guild_settings, update_channel
from nmcore.services import real_estate
from nmcore.services import shop as shop_service
from nmcore.services import giveaways as giveaway_service
from nmcore.services.warnings import summary as warn_summary
from nmcore.services.protection import get_settings as prot_get, update_settings as prot_update, get_default_bad_words

DISCORD_API = "https://discord.com/api/v10"
ADMINISTRATOR_BIT = 0x8


def esc(x):
    return html.escape(str(x or ""))


def oauth_config():
    return {
        "client_id": os.getenv("DISCORD_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET", "").strip(),
        "base_url": os.getenv("DASHBOARD_BASE_URL", "").rstrip("/"),
    }


def redirect_uri():
    cfg = oauth_config()
    return f"{cfg['base_url']}/auth/discord/callback"


def oauth_ready():
    cfg = oauth_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["base_url"])


def discord_api_get(path, token):
    req = urllib.request.Request(
        DISCORD_API + path,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "NM-System-V9-Dashboard"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def exchange_code_for_token(code):
    cfg = oauth_config()
    data = urllib.parse.urlencode({
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
    }).encode("utf-8")

    req = urllib.request.Request(
        DISCORD_API + "/oauth2/token",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "NM-System-V9-Dashboard"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_admin_guild(g):
    try:
        if bool(g.get("owner")):
            return True
        perms = int(g.get("permissions") or 0)
        return bool(perms & ADMINISTRATOR_BIT)
    except Exception:
        return False


def bot_guild_ids(bot=None):
    try:
        if bot and getattr(bot, "guilds", None):
            return {int(g.id) for g in bot.guilds}
    except Exception:
        pass
    return set()


def bot_guild_name(bot=None, guild_id=0):
    try:
        gid_int = int(guild_id or 0)
        if bot and getattr(bot, "guilds", None):
            for g in bot.guilds:
                if int(g.id) == gid_int:
                    return g.name
    except Exception:
        pass

    for g in session.get("discord_guilds", []):
        try:
            if int(g.get("id", 0)) == int(guild_id or 0):
                return g.get("name") or str(guild_id)
        except Exception:
            pass

    return str(guild_id or "")


def filter_manageable_to_bot_guilds(manageable, bot=None):
    ids = bot_guild_ids(bot)
    if not ids:
        return manageable
    return [g for g in manageable if str(g.get("id", "")).isdigit() and int(g["id"]) in ids]


def dashboard_access_denied_html():
    denied = session.pop("access_denied_gid", 0)
    if not denied:
        return ""
    return f"""
    <div class='card'>
      <h3 class='bad'>Dashboard access denied</h3>
      <p>You cannot open this server dashboard.</p>
      <p class='muted'>Reason: the bot is not in this guild, or you do not have Owner/Administrator permission.</p>
      <p>Requested Guild ID: <code>{esc(denied)}</code></p>
    </div>
    """


def dashboard_user():
    return session.get("discord_user") or {}


def allowed_guild_ids():
    return {
        int(g["id"])
        for g in session.get("discord_guilds", [])
        if str(g.get("id", "")).isdigit()
    }


def require_login():
    if session.get("discord_user") and session.get("discord_access_token"):
        return None

    session.clear()
    return redirect("/login")


def gid(bot=None):
    allowed = allowed_guild_ids()

    raw = (
        request.args.get("guild_id")
        or request.form.get("guild_id")
        or session.get("guild_id")
        or 0
    )

    try:
        selected = int(raw or 0)
    except Exception:
        selected = 0

    if selected and selected in allowed:
        session["guild_id"] = selected
        return selected

    if selected and selected not in allowed:
        session["access_denied_gid"] = selected
        session.pop("guild_id", None)
        return 0

    if allowed:
        first = sorted(allowed)[0]
        session["guild_id"] = first
        return first

    return 0


def guild_selector_html(active_gid):
    guilds = session.get("discord_guilds", [])

    if not guilds:
        return """
        <div class='card'>
          <b>No manageable Discord servers found.</b><br>
          You need Owner or Administrator permission, and the bot must be inside that server.
          <br><br>
          <a class='btn' href='/logout'>Logout</a>
        </div>
        """

    options = "".join(
        f"<option value='{esc(g['id'])}' {'selected' if int(g['id']) == int(active_gid or 0) else ''}>{esc(g.get('name', 'Unknown'))}</option>"
        for g in guilds
        if str(g.get("id", "")).isdigit()
    )

    return f"""
    <div class='card'>
      <form method='get' action='/dashboard'>
        <label>Server</label>
        <select name='guild_id'>{options}</select>
        <button>Open</button>
        <a class='btn' href='/logout' style='background:#334155;margin-left:8px'>Logout</a>
      </form>
    </div>
    """




def server_pill_html(active_gid, bot=None):
    if not active_gid:
        return ""
    name = bot_guild_name(bot, active_gid)
    return f"""
    <div style='display:flex;align-items:center;gap:10px;margin:-8px 0 18px;flex-wrap:wrap'>
      <span class='muted'>Server</span>
      <b>{esc(name)}</b>
      <code>{esc(active_gid)}</code>
      <a class='btn' style='background:#334155;padding:8px 11px;box-shadow:none' href='/dashboard'>Change</a>
    </div>
    """
def create_app(bot=None):
    app = Flask(__name__)
    app.secret_key = DASHBOARD_SECRET_KEY
    init_db()

    @app.before_request
    def refresh_bot_guilds():
        try:
            if bot and getattr(bot, "guilds", None):
                for g in bot.guilds:
                    ensure_guild(g.id, g.name)
        except Exception:
            pass

    @app.route("/")
    def root():
        return redirect("/dashboard")

    @app.route("/login")
    def login():
        if session.get("discord_user") and session.get("discord_access_token"):
            return redirect("/dashboard")

        if session.get("discord_user") or session.get("discord_access_token"):
            session.clear()

        if not oauth_ready():
            cfg = oauth_config()
            body = f"""
            <div class='card'>
              <h2 class='bad'>Discord Login is not configured</h2>
              <p>Add these Railway Variables:</p>
              <pre>DISCORD_CLIENT_ID
DISCORD_CLIENT_SECRET
DASHBOARD_BASE_URL</pre>
              <p>Current:</p>
              <ul>
                <li>DISCORD_CLIENT_ID: {'✅' if cfg['client_id'] else '❌'}</li>
                <li>DISCORD_CLIENT_SECRET: {'✅' if cfg['client_secret'] else '❌'}</li>
                <li>DASHBOARD_BASE_URL: {'✅' if cfg['base_url'] else '❌'}</li>
              </ul>
            </div>
            """
            return page("NM System Login", body, 0)

        body = """
        <div class='card' style='max-width:560px'>
          <h2>Login with Discord</h2>
          <p class='muted'>Only server Owners or Administrators can open their server dashboard.</p>
          <a class='btn' href='/auth/discord'>🔐 Continue with Discord</a>
        </div>
        """
        return page("NM System Login", body, 0)

    @app.route("/auth/discord")
    def auth_discord():
        if not oauth_ready():
            return redirect("/login")

        cfg = oauth_config()
        params = urllib.parse.urlencode({
            "client_id": cfg["client_id"],
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": "identify guilds",
            "prompt": "consent",
        })

        return redirect(f"{DISCORD_API}/oauth2/authorize?{params}")

    @app.route("/auth/discord/callback")
    def auth_callback():
        if not oauth_ready():
            return redirect("/login")

        code = request.args.get("code", "")
        if not code:
            return "Missing Discord OAuth code", 400

        try:
            token_data = exchange_code_for_token(code)
            access_token = token_data.get("access_token")

            if not access_token:
                session.clear()
                return "Discord OAuth did not return access token", 400

            user = discord_api_get("/users/@me", access_token)
            guilds = discord_api_get("/users/@me/guilds", access_token)
            manageable = filter_manageable_to_bot_guilds([g for g in guilds if is_admin_guild(g)], bot)

            session.clear()
            session["discord_access_token"] = access_token
            session["discord_user"] = {
                "id": user.get("id"),
                "username": user.get("username"),
                "global_name": user.get("global_name"),
                "avatar": user.get("avatar"),
            }
            session["discord_guilds"] = manageable

            if manageable:
                session["guild_id"] = int(manageable[0]["id"])

            session.modified = True
            return redirect("/dashboard")

        except urllib.error.HTTPError as e:
            session.clear()
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                detail = str(e)
            return f"Discord OAuth failed: {esc(detail)}", 400

        except Exception as e:
            session.clear()
            return f"Discord OAuth error: {esc(type(e).__name__)}: {esc(e)}", 500

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @app.route("/dashboard")
    def home():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        if not g:
            return page("Dashboard Overview", dashboard_access_denied_html() + guild_selector_html(0), 0)

        ensure_guild(g)

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) c, COALESCE(SUM(balance),0) total FROM balances WHERE guild_id=?", (g,))
        eco = cur.fetchone()
        cur.execute("SELECT COUNT(*) c FROM money_ledger WHERE guild_id=?", (g,))
        led = cur.fetchone()
        active, cleared = warn_summary(g)
        conn.close()

        user = dashboard_user()
        g_name = bot_guild_name(bot, g)
        body = guild_selector_html(g) + f"""
        <div class='card'>
          <div class='muted'>Logged in as</div>
          <b>{esc(user.get('global_name') or user.get('username'))}</b>
          <code>{esc(user.get('id'))}</code>
        </div>

        <div class='grid'>
          <div class='card'><div class='muted'>Guild</div><div class='stat'>{esc(g_name)}</div><div class='muted'><code>{g}</code></div></div>
          <div class='card'><div class='muted'>Coin</div><div class='stat'>{esc(get_coin_name(g))}</div></div>
          <div class='card'><div class='muted'>Economy Users</div><div class='stat'>{int(eco['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Total Money</div><div class='stat'>{int(eco['total'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Ledger Rows</div><div class='stat'>{int(led['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Warnings</div><div class='stat'>{active:,}</div></div>
        </div>
        """
        return page("Dashboard Overview", body, g)

    @app.route("/dashboard/economy")
    def economy_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT user_id,balance,updated_at FROM balances WHERE guild_id=? ORDER BY balance DESC LIMIT 100", (g,))
        rows = cur.fetchall()
        conn.close()

        trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['balance']):,}</td><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'>View</a></td></tr>"
            for r in rows
        )

        return page("Economy", server_pill_html(g, bot) + f"<div class='card'><table><tr><th>User ID</th><th>Balance</th><th></th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/money-tracker")
    def money_tracker():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        uid = request.args.get("user_id", "").strip()
        source = request.args.get("source", "").strip()
        limit_raw = request.args.get("limit", "250").strip()

        try:
            limit = max(25, min(int(limit_raw or 250), 1000))
        except Exception:
            limit = 250

        q = "SELECT * FROM money_ledger WHERE guild_id=?"
        params = [g]

        if uid.isdigit():
            q += " AND user_id=?"
            params.append(int(uid))

        if source:
            q += " AND source_type LIKE ?"
            params.append(f"{source}%")

        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        conn = db()
        cur = conn.cursor()

        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT source_type, COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took
        FROM money_ledger WHERE guild_id=? GROUP BY source_type ORDER BY c DESC LIMIT 20""", (g,))
        source_rows = cur.fetchall()

        conn.close()

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:#334155' href='/dashboard/money-tracker?guild_id={g}&source={esc(r['source_type'])}'>{esc(r['source_type'])} ({int(r['c'])})</a>"
            for r in source_rows
        )

        trs = "".join(
            f"<tr><td><code>{r['tx_id'][:10]}</code></td><td>{r['user_id']}</td><td>{int(r['amount']):,}</td><td>{int(r['balance_before']):,}</td><td>{int(r['balance_after']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['source_label'])}</td><td>{esc(r['reason'])}</td></tr>"
            for r in rows
        )

        form = f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <input name=source placeholder='source_type مثل casino / salary' value='{esc(source)}'>
            <input name=limit placeholder='Limit' value='{limit}' style='width:90px'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}'>Reset</a>
          </form>
        </div>
        """

        body = server_pill_html(g, bot) + form + f"<div class='card'><h3>Quick Filters</h3>{chips or '<span class=muted>No ledger yet.</span>'}</div>"
        body += f"<div class='card'><table><tr><th>TX</th><th>User</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Label</th><th>Reason</th></tr>{trs}</table></div>"

        return page("Money Tracker", body, g)

    @app.route("/dashboard/casino")
    def casino_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        conn = db()
        cur = conn.cursor()

        cur.execute("""SELECT source_label, COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid
        FROM money_ledger WHERE guild_id=? AND source_type LIKE 'casino_%'
        GROUP BY source_label ORDER BY c DESC""", (g,))
        game_rows = cur.fetchall()

        cur.execute("""SELECT user_id,
        COALESCE(SUM(amount),0) net,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) wagered,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows
        FROM money_ledger
        WHERE guild_id=? AND source_type LIKE 'casino_%'
        GROUP BY user_id
        ORDER BY net ASC
        LIMIT 10""", (g,))
        biggest_losers = cur.fetchall()

        cur.execute("""SELECT user_id,
        COALESCE(SUM(amount),0) net,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) wagered,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows
        FROM money_ledger
        WHERE guild_id=? AND source_type LIKE 'casino_%'
        GROUP BY user_id
        ORDER BY net DESC
        LIMIT 10""", (g,))
        biggest_winners = cur.fetchall()

        cur.execute("""SELECT
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows
        FROM money_ledger WHERE guild_id=? AND source_type LIKE 'casino_%'""", (g,))
        total = cur.fetchone()

        conn.close()

        game_trs = "".join(
            f"<tr><td>{esc(r['source_label'])}</td><td>{int(r['c']):,}</td><td>{int(r['took']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['took'] or 0)-int(r['paid'] or 0):,}</td></tr>"
            for r in game_rows
        )

        loser_trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['net']):,}</td><td>{int(r['wagered']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['rows']):,}</td></tr>"
            for r in biggest_losers
        )

        winner_trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['net']):,}</td><td>{int(r['wagered']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['rows']):,}</td></tr>"
            for r in biggest_winners
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Casino Rows</div><div class='stat'>{int(total['rows'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Casino Took</div><div class='stat'>{int(total['took'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Casino Paid</div><div class='stat'>{int(total['paid'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Casino Net</div><div class='stat'>{int(total['took'] or 0)-int(total['paid'] or 0):,}</div></div>
        </div>
        <div class='card'><h3>By Game</h3><table><tr><th>Game</th><th>Rows</th><th>Took</th><th>Paid</th><th>Net For Casino</th></tr>{game_trs}</table></div>
        <div class='card'><h3>Biggest Losers</h3><table><tr><th>User</th><th>Net</th><th>Wagered</th><th>Paid</th><th>Rows</th></tr>{loser_trs}</table></div>
        <div class='card'><h3>Biggest Winners</h3><table><tr><th>User</th><th>Net</th><th>Wagered</th><th>Paid</th><th>Rows</th></tr>{winner_trs}</table></div>
        """
        return page("Casino", body, g)

    @app.route("/dashboard/levels")
    def levels_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM levels WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT 100", (g,))
        rows = cur.fetchall()
        conn.close()

        trs = "".join(
            f"<tr><td>{r['user_id']}</td><td>{r['level']}</td><td>{r['xp']}</td></tr>"
            for r in rows
        )

        return page("Levels", server_pill_html(g, bot) + f"<div class='card'><table><tr><th>User</th><th>Level</th><th>XP</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/real-estate")
    def real_estate_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        real_estate.seed(g)
        rows = real_estate.rows(g)

        trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['display_name'])}</td><td>{r['owner_id'] or '-'}</td><td>{int(r['price']):,}</td><td>{int(r['rent']):,}</td><td>{r['level']}</td></tr>"
            for r in rows
        )

        return page("Real Estate", server_pill_html(g, bot) + f"<div class='card'><table><tr><th>ID</th><th>Name</th><th>Owner</th><th>Price</th><th>Rent</th><th>Level</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/warnings")
    def warnings_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        uid = request.args.get("user_id", "").strip()
        status = request.args.get("status", "active").strip()

        conn = db()
        cur = conn.cursor()

        q = "SELECT * FROM warnings WHERE guild_id=?"
        params = [g]

        if uid.isdigit():
            q += " AND user_id=?"
            params.append(int(uid))

        if status in {"active", "cleared"}:
            q += " AND status=?"
            params.append(status)

        q += " ORDER BY id DESC LIMIT 200"
        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT user_id, user_name,
        COUNT(*) total,
        SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active_count,
        MAX(id) last_id
        FROM warnings WHERE guild_id=?
        GROUP BY user_id, user_name
        ORDER BY active_count DESC, total DESC
        LIMIT 100""", (g,))
        grouped = cur.fetchall()

        conn.close()

        grouped_trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{esc(r['user_name'])}</td><td>{int(r['active_count'] or 0):,}</td><td>{int(r['total'] or 0):,}</td><td><a href='/dashboard/warnings?guild_id={g}&user_id={r['user_id']}'>View</a></td></tr>"
            for r in grouped
        )

        trs = "".join(
            f"<tr><td>{r['id']}</td><td><code>{r['user_id']}</code></td><td>{esc(r['user_name'])}</td><td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td><td>{esc(r['moderator_name'])}</td></tr>"
            for r in rows
        )

        form = f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <select name=status>
              <option value='active' {'selected' if status == 'active' else ''}>Active</option>
              <option value='cleared' {'selected' if status == 'cleared' else ''}>Cleared</option>
              <option value='all' {'selected' if status == 'all' else ''}>All</option>
            </select>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/warnings?guild_id={g}'>Reset</a>
          </form>
        </div>
        """

        body = server_pill_html(g, bot) + form
        body += f"<div class='card'><h3>Users Warning Summary</h3><table><tr><th>User ID</th><th>Name</th><th>Active</th><th>Total</th><th></th></tr>{grouped_trs}</table></div>"
        body += f"<div class='card'><h3>Warning Records</h3><table><tr><th>ID</th><th>User</th><th>Name</th><th>Reason</th><th>Status</th><th>By</th></tr>{trs}</table></div>"

        return page("Warnings", body, g)

    @app.route("/dashboard/protection", methods=["GET", "POST"])
    def protection_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            if request.form.get("action") == "reset_bad_words":
                prot_update(g, {"bad_words": get_default_bad_words()})
                return redirect(f"/dashboard/protection?guild_id={g}")

            data = {
                "enabled": 1 if request.form.get("enabled") else 0,
                "bad_words_enabled": 1 if request.form.get("bad_words_enabled") else 0,
                "links_enabled": 1 if request.form.get("links_enabled") else 0,
                "delete_messages": 1 if request.form.get("delete_messages") else 0,
                "bad_words": request.form.get("bad_words", "")
            }
            prot_update(g, data)
            return redirect(f"/dashboard/protection?guild_id={g}")

        s = prot_get(g)
        bad_words_raw = str(s.get("bad_words") or "")
        bad_count = len([w for w in bad_words_raw.split(",") if w.strip()])

        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT * FROM log_events
        WHERE guild_id=? AND event_type IN ('protection_warning','protection_link')
        ORDER BY id DESC LIMIT 50""", (g,))
        events = cur.fetchall()

        cur.execute("""SELECT * FROM warnings
        WHERE guild_id=? AND moderator_name LIKE '%NM System%'
        ORDER BY id DESC LIMIT 50""", (g,))
        auto_warnings = cur.fetchall()
        conn.close()

        event_trs = "".join(
            f"<tr><td>{esc(r['event_type'])}</td><td><code>{r['user_id']}</code></td><td>{esc(r['channel_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td></tr>"
            for r in events
        )

        warn_trs = "".join(
            f"<tr><td>{r['id']}</td><td><code>{r['user_id']}</code></td><td>{esc(r['user_name'])}</td><td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td></tr>"
            for r in auto_warnings
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Protection</div><div class='stat'>{'ON' if s.get('enabled') else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Bad Words</div><div class='stat'>{bad_count:,}</div></div>
          <div class='card'><div class='muted'>Delete Messages</div><div class='stat'>{'ON' if s.get('delete_messages') else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Auto Warnings</div><div class='stat'>{len(auto_warnings):,}</div></div>
        </div>

        <div class='card'>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>

            <label><input type=checkbox name=enabled {'checked' if s.get('enabled') else ''}> Enabled</label><br>
            <label><input type=checkbox name=bad_words_enabled {'checked' if s.get('bad_words_enabled') else ''}> Bad Words</label><br>
            <label><input type=checkbox name=links_enabled {'checked' if s.get('links_enabled') else ''}> Links</label><br>
            <label><input type=checkbox name=delete_messages {'checked' if s.get('delete_messages') else ''}> Delete Messages</label><br><br>

            <textarea name=bad_words style='width:100%;height:180px'>{esc(bad_words_raw)}</textarea><br><br>
            <button>Save</button>
            <button name='action' value='reset_bad_words' style='background:#334155;margin-left:8px'>Reset Default Bad Words</button>
          </form>
        </div>

        <div class='card'><h3>Recent Protection Events</h3><table><tr><th>Type</th><th>User</th><th>Channel</th><th>Title</th><th>Details</th></tr>{event_trs}</table></div>
        <div class='card'><h3>Recent Auto Warnings</h3><table><tr><th>ID</th><th>User</th><th>Name</th><th>Reason</th><th>Status</th></tr>{warn_trs}</table></div>
        """
        return page("Protection", body, g)

    @app.route("/dashboard/logs")
    def logs_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        event_type = request.args.get("event_type", "").strip()
        user_id = request.args.get("user_id", "").strip()
        limit_raw = request.args.get("limit", "200").strip()

        try:
            limit = max(25, min(int(limit_raw or 200), 1000))
        except Exception:
            limit = 200

        q = "SELECT * FROM log_events WHERE guild_id=?"
        params = [g]

        if event_type:
            q += " AND event_type=?"
            params.append(event_type)

        if user_id.isdigit():
            q += " AND user_id=?"
            params.append(int(user_id))

        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        conn = db()
        cur = conn.cursor()
        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT event_type, COUNT(*) c FROM log_events
        WHERE guild_id=? GROUP BY event_type ORDER BY c DESC LIMIT 30""", (g,))
        types = cur.fetchall()
        conn.close()

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:#334155' href='/dashboard/logs?guild_id={g}&event_type={esc(r['event_type'])}'>{esc(r['event_type'])} ({int(r['c'])})</a>"
            for r in types
        )

        form = f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=event_type placeholder='event_type' value='{esc(event_type)}'>
            <input name=user_id placeholder='User ID' value='{esc(user_id)}'>
            <input name=limit placeholder='Limit' value='{limit}' style='width:90px'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/logs?guild_id={g}'>Reset</a>
          </form>
        </div>
        """

        trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['event_type'])}</td><td><code>{r['user_id']}</code></td><td>{esc(r['user_name'])}</td><td>{esc(r['channel_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td></tr>"
            for r in rows
        )

        body = server_pill_html(g, bot) + form
        body += f"<div class='card'><h3>Event Types</h3>{chips or '<span class=muted>No logs yet.</span>'}</div>"
        body += f"<div class='card'><table><tr><th>ID</th><th>Type</th><th>User</th><th>Name</th><th>Channel</th><th>Title</th><th>Details</th></tr>{trs}</table></div>"
        return page("Logs", body, g)

    @app.route("/dashboard/live")
    def live_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        activity_type = request.args.get("activity_type", "").strip()

        conn = db()
        cur = conn.cursor()

        q = "SELECT * FROM live_activity WHERE guild_id=?"
        params = [g]
        if activity_type:
            q += " AND activity_type=?"
            params.append(activity_type)
        q += " ORDER BY id DESC LIMIT 250"

        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT activity_type, COUNT(*) c FROM live_activity
        WHERE guild_id=? GROUP BY activity_type ORDER BY c DESC LIMIT 20""", (g,))
        types = cur.fetchall()

        conn.close()

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:#334155' href='/dashboard/live?guild_id={g}&activity_type={esc(r['activity_type'])}'>{esc(r['activity_type'])} ({int(r['c'])})</a>"
            for r in types
        )

        trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['activity_type'])}</td><td><code>{r['actor_id']}</code></td><td>{esc(r['actor_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td><td>{int(r['amount']):,}</td></tr>"
            for r in rows
        )

        body = server_pill_html(g, bot)
        body += f"<div class='card'><h3>Live Filters</h3>{chips or '<span class=muted>No live activity yet.</span>'} <a class='btn' style='background:#334155;margin:4px' href='/dashboard/live?guild_id={g}'>Reset</a></div>"
        body += f"<div class='card'><table><tr><th>ID</th><th>Type</th><th>Actor</th><th>Name</th><th>Title</th><th>Details</th><th>Amount</th></tr>{trs}</table></div>"
        return page("Live Activity", body, g)

    @app.route("/dashboard/settings", methods=["GET", "POST"])
    def settings_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            if "coin_name" in request.form:
                set_coin_name(g, request.form.get("coin_name"))

            for key in ["commands_channel_id", "gambling_channel_id", "logs_channel_id"]:
                if key in request.form:
                    update_channel(g, key, int(request.form.get(key) or 0))

            for k, v in all_toggles(g).items():
                set_system_enabled(g, k, bool(request.form.get(f"toggle_{k}")))

            return redirect(f"/dashboard/settings?guild_id={g}")

        gs = get_guild_settings(g)
        toggles = all_toggles(g)

        commands_channel_id = int(gs.get("commands_channel_id") or 0)
        gambling_channel_id = int(gs.get("gambling_channel_id") or 0)
        logs_channel_id = int(gs.get("logs_channel_id") or 0)

        checks = "".join(
            f"<label><input type=checkbox name='toggle_{k}' {'checked' if v else ''}> {k}</label><br>"
            for k, v in toggles.items()
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Commands Room</div><div class='stat'>{f'<#{commands_channel_id}>' if commands_channel_id else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Gambling Room</div><div class='stat'>{f'<#{gambling_channel_id}>' if gambling_channel_id else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Logs Room</div><div class='stat'>{f'<#{logs_channel_id}>' if logs_channel_id else 'OFF'}</div></div>
        </div>

        <div class='card'>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>

            <h3>Guild Settings</h3>

            Coin Name<br>
            <input name=coin_name value='{esc(get_coin_name(g))}'><br><br>

            Commands Channel ID<br>
            <input name=commands_channel_id value='{commands_channel_id}'><br>
            <div class='muted'>If set, economy/levels/real-estate/utility commands only work there.</div><br>

            Gambling Channel ID<br>
            <input name=gambling_channel_id value='{gambling_channel_id}'><br>
            <div class='muted'>If set, casino commands only work there.</div><br>

            Logs Channel ID<br>
            <input name=logs_channel_id value='{logs_channel_id}'><br><br>

            <h3>System Toggles</h3>
            {checks}
            <br>
            <button>Save</button>
          </form>
        </div>
        """
        return page("Settings", body, g)

    @app.route("/dashboard/shop", methods=["GET", "POST"])
    def shop_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        shop_service.ensure_tables()

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "seed":
                shop_service.seed_defaults(g)
                return redirect(f"/dashboard/shop?guild_id={g}")

            if action == "add":
                item_key = request.form.get("item_key", "").strip()
                name = request.form.get("name", "").strip()
                description = request.form.get("description", "").strip()
                price = int(request.form.get("price") or 0)
                role_id = int(request.form.get("role_id") or 0)
                enabled = 1 if request.form.get("enabled") else 0
                shop_service.upsert_item(g, item_key, name, description, price, role_id, enabled)
                return redirect(f"/dashboard/shop?guild_id={g}")

            if action == "toggle":
                item_id = int(request.form.get("item_id") or 0)
                enabled = int(request.form.get("enabled") or 0)
                shop_service.set_enabled(g, item_id, enabled)
                return redirect(f"/dashboard/shop?guild_id={g}")

        items = shop_service.items(g, include_disabled=True)
        purchases = shop_service.recent_purchases(g, 100)

        item_trs = "".join(
            f"""<tr>
              <td>{r['id']}</td>
              <td><code>{esc(r['item_key'])}</code></td>
              <td>{esc(r['name'])}</td>
              <td>{int(r['price']):,}</td>
              <td>{'<code>'+esc(r['role_id'])+'</code>' if int(r['role_id'] or 0) else '-'}</td>
              <td>{'✅' if int(r['enabled']) else '❌'}</td>
              <td>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=action value='toggle'>
                  <input type=hidden name=item_id value='{r['id']}'>
                  <input type=hidden name=enabled value='{0 if int(r['enabled']) else 1}'>
                  <button>{'Disable' if int(r['enabled']) else 'Enable'}</button>
                </form>
              </td>
            </tr>"""
            for r in items
        )

        purchase_trs = "".join(
            f"<tr><td>{r['id']}</td><td><code>{r['user_id']}</code></td><td>{esc(r['item_key'])}</td><td>{int(r['price']):,}</td><td><code>{esc(r['money_tx_id'])[:12]}</code></td></tr>"
            for r in purchases
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Shop Items</div><div class='stat'>{len(items):,}</div></div>
          <div class='card'><div class='muted'>Recent Purchases</div><div class='stat'>{len(purchases):,}</div></div>
        </div>

        <div class='card'>
          <h3>Add / Update Item</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='add'>
            <input name=item_key placeholder='item_key مثل vip_day' required>
            <input name=name placeholder='Display name' required>
            <input name=price placeholder='Price' type=number min=0 required>
            <input name=role_id placeholder='Role ID optional' type=number min=0>
            <br><br>
            <textarea name=description placeholder='Description' style='width:100%;height:80px'></textarea><br><br>
            <label><input type=checkbox name=enabled checked> Enabled</label>
            <button>Save Item</button>
          </form>
          <form method=post style='margin-top:12px'>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='seed'>
            <button style='background:#334155'>Add Default Items</button>
          </form>
        </div>

        <div class='card'>
          <h3>Items</h3>
          <table><tr><th>ID</th><th>Key</th><th>Name</th><th>Price</th><th>Role ID</th><th>Enabled</th><th>Action</th></tr>{item_trs}</table>
        </div>

        <div class='card'>
          <h3>Recent Purchases</h3>
          <table><tr><th>ID</th><th>User</th><th>Item</th><th>Price</th><th>TX</th></tr>{purchase_trs}</table>
        </div>
        """
        return page("Shop", body, g)

    @app.route("/dashboard/giveaways", methods=["GET", "POST"])
    def giveaways_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        giveaway_service.ensure_tables()

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "create":
                prize = request.form.get("prize", "").strip()
                winner_count = int(request.form.get("winner_count") or 1)
                created_by_id = int((dashboard_user() or {}).get("id") or 0)
                created_by_name = dashboard_user().get("global_name") or dashboard_user().get("username") or "Dashboard"
                giveaway_service.create_giveaway(g, prize, winner_count, created_by_id, created_by_name)
                return redirect(f"/dashboard/giveaways?guild_id={g}")

            if action == "close":
                giveaway_id = int(request.form.get("giveaway_id") or 0)
                giveaway_service.close_giveaway(g, giveaway_id)
                return redirect(f"/dashboard/giveaways?guild_id={g}")

            if action == "pick":
                giveaway_id = int(request.form.get("giveaway_id") or 0)
                giveaway_service.pick_winners(g, giveaway_id)
                return redirect(f"/dashboard/giveaways?guild_id={g}")

        rows = giveaway_service.giveaways(g, 100)

        giveaway_trs = ""
        for r in rows:
            entries = giveaway_service.entry_count(g, int(r["id"]))
            winners = giveaway_service.winner_list(g, int(r["id"]))
            giveaway_trs += f"""<tr>
              <td>{r['id']}</td>
              <td>{esc(r['prize'])}</td>
              <td>{int(r['winner_count'])}</td>
              <td>{entries}</td>
              <td>{esc(r['status'])}</td>
              <td>{esc(', '.join(str(w) for w in winners)) or '-'}</td>
              <td>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=giveaway_id value='{r['id']}'>
                  <button name=action value='pick'>Pick</button>
                  <button name=action value='close' style='background:#334155'>Close</button>
                </form>
              </td>
            </tr>"""

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <h3>Create Giveaway</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='create'>
            <input name=prize placeholder='Prize' required>
            <input name=winner_count type=number min=1 value=1 style='width:120px'>
            <button>Create</button>
          </form>
        </div>

        <div class='card'>
          <h3>Giveaways</h3>
          <table><tr><th>ID</th><th>Prize</th><th>Winners</th><th>Entries</th><th>Status</th><th>Winner IDs</th><th>Action</th></tr>{giveaway_trs}</table>
        </div>
        """
        return page("Giveaways", body, g)

    @app.route("/dashboard/user")
    def user_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        uid = request.args.get("user_id", "").strip()

        if not uid.isdigit():
            return page("User Lookup", server_pill_html(g, bot) + f"<div class='card'><form><input type=hidden name=guild_id value='{g}'><input name=user_id placeholder='User ID'><button>Search</button></form></div>", g)

        uid = int(uid)

        conn = db()
        cur = conn.cursor()

        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (g, uid))
        bal = cur.fetchone()

        cur.execute("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (g, uid))
        lvl = cur.fetchone()

        cur.execute("SELECT * FROM money_ledger WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 50", (g, uid))
        ledger = cur.fetchall()

        cur.execute("SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 50", (g, uid))
        warns = cur.fetchall()

        cur.execute("SELECT * FROM properties WHERE guild_id=? AND owner_id=? ORDER BY id LIMIT 50", (g, uid))
        props = cur.fetchall()

        conn.close()

        ledger_trs = "".join(
            f"<tr><td>{r['tx_id'][:10]}</td><td>{int(r['amount']):,}</td><td>{r['balance_before']:,}</td><td>{r['balance_after']:,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['reason'])}</td></tr>"
            for r in ledger
        )

        warn_trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td><td>{esc(r['moderator_name'])}</td></tr>"
            for r in warns
        )

        prop_trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['display_name'])}</td><td>{int(r['level'])}</td><td>{int(r['rent']):,}</td></tr>"
            for r in props
        )

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id value='{uid}' placeholder='User ID'>
            <button>Search</button>
          </form>
        </div>

        <div class='grid'>
          <div class='card'><div class='muted'>User ID</div><div class='stat'><code>{uid}</code></div></div>
          <div class='card'><div class='muted'>Balance</div><div class='stat'>{int(bal['balance'] if bal else 0):,}</div></div>
          <div class='card'><div class='muted'>Level</div><div class='stat'>{int(lvl['level'] if lvl else 1)}</div></div>
          <div class='card'><div class='muted'>Warnings</div><div class='stat'>{len(warns):,}</div></div>
          <div class='card'><div class='muted'>Properties</div><div class='stat'>{len(props):,}</div></div>
        </div>

        <div class='card'><h3>Money History</h3><table><tr><th>TX</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Reason</th></tr>{ledger_trs}</table></div>
        <div class='card'><h3>Warnings</h3><table><tr><th>ID</th><th>Reason</th><th>Status</th><th>By</th></tr>{warn_trs}</table></div>
        <div class='card'><h3>Properties</h3><table><tr><th>ID</th><th>Name</th><th>Level</th><th>Rent</th></tr>{prop_trs}</table></div>
        """
        return page("User Lookup", body, g)

    @app.route("/dashboard/health")
    def health():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        cfg = oauth_config()
        bot_online = bool(bot and getattr(bot, "user", None))
        bot_name = str(bot.user) if bot_online else "Not ready"
        bot_ids = bot_guild_ids(bot)
        current_connected = int(g or 0) in bot_ids if g else False
        current_name = bot_guild_name(bot, g) if g else "None"

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <h2 class='ok'>V9 Unified + Discord Login OK</h2>
          <p>Bot Online: {'✅' if bot_online else '❌'}</p>
          <p>Bot Name: <code>{esc(bot_name)}</code></p>
          <p>Bot Guilds Count: <code>{len(bot_ids)}</code></p>
          <p>Current Guild Connected: {'✅' if current_connected else '❌'}</p>
          <p>Current Guild: <b>{esc(current_name)}</b> <code>{esc(g)}</code></p>
          <p>Commands Room: <code>{esc(get_guild_settings(g).get('commands_channel_id') if g else 0)}</code></p>
          <p>Gambling Room: <code>{esc(get_guild_settings(g).get('gambling_channel_id') if g else 0)}</code></p>
          <p>Logs Room: <code>{esc(get_guild_settings(g).get('logs_channel_id') if g else 0)}</code></p>
          <p>DB: <code>{esc(DB_FILE)}</code></p>
          <p>Discord Login: ✅</p>
          <p>Redirect URI: <code>{esc(redirect_uri())}</code></p>
          <p>Base URL: <code>{esc(cfg['base_url'])}</code></p>
        </div>
        """
        return page("Health", body, g)

    return app
