import os, time, html, json, urllib.parse, urllib.request, urllib.error
from flask import Flask, request, redirect, session
from nmcore.config import DASHBOARD_SECRET_KEY, DB_FILE
from nmcore.db import db, init_db
from nmcore.ui import page
from nmcore.services.settings import ensure_guild, get_coin_name, set_coin_name, all_toggles, set_system_enabled, get_guild_settings, update_channel
from nmcore.services import real_estate
from nmcore.services import economy as economy_service
from nmcore.services import antiraid
from nmcore.services import shop as shop_service
from nmcore.services import giveaways as giveaway_service
from nmcore.services.log_channels import LOG_CHANNELS, get_log_channel, set_log_channel, all_log_channels
from nmcore.services.diagnostics import system_status
from nmcore.services.warnings import summary as warn_summary
from nmcore.services.protection import get_settings as prot_get, update_settings as prot_update, get_default_bad_words, matched_bad_word, contains_bad, has_link, check_message
from nmcore.services.activity import log_event, record

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


def dashboard_actor():
    u = dashboard_user()
    try:
        actor_id = int(u.get("id") or 0)
    except Exception:
        actor_id = 0
    actor_name = u.get("global_name") or u.get("username") or "Dashboard"
    return actor_id, actor_name


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

    @app.route("/dashboard/economy", methods=["GET", "POST"])
    def economy_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                target_user_id = int(request.form.get("user_id") or 0)
            except Exception:
                target_user_id = 0

            try:
                amount = int(str(request.form.get("amount") or "0").replace(",", ""))
            except Exception:
                amount = 0

            reason = request.form.get("reason", "").strip() or f"Dashboard {action}"

            if action in {"give", "take", "set"} and target_user_id and amount >= 0:
                if action == "give" and amount > 0:
                    tx = economy_service.credit(
                        g,
                        target_user_id,
                        amount,
                        "dashboard_give",
                        user_name=str(target_user_id),
                        actor_id=actor_id,
                        actor_name=actor_name,
                        source_label="dashboard",
                        reason=reason
                    )
                elif action == "take" and amount > 0:
                    tx = economy_service.debit(
                        g,
                        target_user_id,
                        amount,
                        "dashboard_take",
                        user_name=str(target_user_id),
                        actor_id=actor_id,
                        actor_name=actor_name,
                        source_label="dashboard",
                        reason=reason
                    )
                elif action == "set":
                    tx = economy_service.set_balance(
                        g,
                        target_user_id,
                        amount,
                        "dashboard_set_balance",
                        user_name=str(target_user_id),
                        actor_id=actor_id,
                        actor_name=actor_name,
                        source_label="dashboard",
                        reason=reason
                    )
                else:
                    tx = {"ok": False, "error": "invalid_amount"}

                log_event(
                    g,
                    f"dashboard_{action}_money",
                    target_user_id,
                    str(target_user_id),
                    0,
                    "",
                    f"Dashboard {action} money",
                    f"Actor={actor_id}, Amount={amount}, OK={tx.get('ok')}, Reason={reason}"
                )

                return redirect(f"/dashboard/economy?guild_id={g}")

            if action in {"give_all", "take_all"} and amount > 0:
                conn = db()
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM balances WHERE guild_id=?", (g,))
                users = [int(r["user_id"]) for r in cur.fetchall()]
                conn.close()

                ok_count = 0
                fail_count = 0

                for uid in users:
                    if action == "give_all":
                        tx = economy_service.credit(
                            g,
                            uid,
                            amount,
                            "dashboard_give_all",
                            user_name=str(uid),
                            actor_id=actor_id,
                            actor_name=actor_name,
                            source_label="dashboard",
                            reason=reason
                        )
                    else:
                        tx = economy_service.debit(
                            g,
                            uid,
                            amount,
                            "dashboard_take_all",
                            user_name=str(uid),
                            actor_id=actor_id,
                            actor_name=actor_name,
                            source_label="dashboard",
                            reason=reason
                        )

                    if tx.get("ok"):
                        ok_count += 1
                    else:
                        fail_count += 1

                log_event(
                    g,
                    f"dashboard_{action}",
                    actor_id,
                    actor_name,
                    0,
                    "",
                    f"Dashboard bulk money action",
                    f"Action={action}, Amount={amount}, OK={ok_count}, Failed={fail_count}, Reason={reason}"
                )

                return redirect(f"/dashboard/economy?guild_id={g}")

        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT user_id,balance,updated_at FROM balances WHERE guild_id=? ORDER BY balance DESC LIMIT 100", (g,))
        rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) c, COALESCE(SUM(balance),0) total FROM balances WHERE guild_id=?", (g,))
        stats = cur.fetchone()
        conn.close()

        trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['balance']):,}</td><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'>View</a></td></tr>"
            for r in rows
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Economy Users</div><div class='stat'>{int(stats['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Total Money</div><div class='stat'>{int(stats['total'] or 0):,}</div></div>
        </div>

        <div class='card'>
          <h3>Dashboard Money Control</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID'>
            <input name=amount type=number min=0 placeholder='Amount'>
            <input name=reason placeholder='Reason' style='min-width:260px'>
            <button name=action value='give'>Give</button>
            <button name=action value='take' style='background:#dc2626'>Take</button>
            <button name=action value='set' style='background:#334155'>Set Balance</button>
          </form>
        </div>

        <div class='card'>
          <h3>Bulk Money Control</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input name=amount type=number min=1 placeholder='Amount'>
            <input name=reason placeholder='Reason' style='min-width:260px'>
            <button name=action value='give_all'>Give All</button>
            <button name=action value='take_all' style='background:#dc2626'>Take All</button>
          </form>
          <p class='muted'>Bulk applies only to users already in the balances table.</p>
        </div>

        <div class='card'>
          <h3>Top Balances</h3>
          <table><tr><th>User ID</th><th>Balance</th><th></th></tr>{trs}</table>
        </div>
        """

        return page("Economy", body, g)

    @app.route("/dashboard/money-tracker")
    def money_tracker():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        uid = request.args.get("user_id", "").strip()
        source = request.args.get("source", "").strip()
        actor_id = request.args.get("actor_id", "").strip()
        min_amount = request.args.get("min_amount", "").strip()
        max_amount = request.args.get("max_amount", "").strip()
        direction = request.args.get("direction", "").strip()
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

        if actor_id.isdigit():
            q += " AND actor_id=?"
            params.append(int(actor_id))

        if source:
            q += " AND source_type LIKE ?"
            params.append(f"{source}%")

        if direction == "in":
            q += " AND amount > 0"
        elif direction == "out":
            q += " AND amount < 0"

        if min_amount.lstrip("-").isdigit():
            q += " AND ABS(amount) >= ?"
            params.append(abs(int(min_amount)))

        if max_amount.lstrip("-").isdigit():
            q += " AND ABS(amount) <= ?"
            params.append(abs(int(max_amount)))

        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        conn = db()
        cur = conn.cursor()

        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT source_type, COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(amount),0) net
        FROM money_ledger WHERE guild_id=? GROUP BY source_type ORDER BY c DESC LIMIT 30""", (g,))
        source_rows = cur.fetchall()

        cur.execute("""SELECT
        COUNT(*) rows,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) money_in,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) money_out,
        COALESCE(SUM(amount),0) net
        FROM money_ledger WHERE guild_id=?""", (g,))
        totals = cur.fetchone()

        cur.execute("""SELECT user_id,
        COALESCE(SUM(amount),0) net,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) received,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) spent,
        COUNT(*) rows
        FROM money_ledger WHERE guild_id=?
        GROUP BY user_id ORDER BY received DESC LIMIT 10""", (g,))
        top_received = cur.fetchall()

        cur.execute("""SELECT actor_id, actor_name, COUNT(*) c,
        COALESCE(SUM(ABS(amount)),0) volume
        FROM money_ledger WHERE guild_id=? AND actor_id != 0
        GROUP BY actor_id, actor_name ORDER BY volume DESC LIMIT 10""", (g,))
        top_actors = cur.fetchall()

        conn.close()

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:#334155' href='/dashboard/money-tracker?guild_id={g}&source={esc(r['source_type'])}'>{esc(r['source_type'])} ({int(r['c'])})</a>"
            for r in source_rows
        )

        source_trs = "".join(
            f"<tr><td>{esc(r['source_type'])}</td><td>{int(r['c']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['took']):,}</td><td>{int(r['net']):,}</td></tr>"
            for r in source_rows
        )

        received_trs = "".join(
            f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['received']):,}</td><td>{int(r['spent']):,}</td><td>{int(r['net']):,}</td><td>{int(r['rows']):,}</td><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'>View</a></td></tr>"
            for r in top_received
        )

        actor_trs = "".join(
            f"<tr><td><code>{r['actor_id']}</code></td><td>{esc(r['actor_name'])}</td><td>{int(r['volume']):,}</td><td>{int(r['c']):,}</td></tr>"
            for r in top_actors
        )

        trs = "".join(
            f"<tr><td><code>{r['tx_id'][:10]}</code></td><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'><code>{r['user_id']}</code></a></td><td>{int(r['amount']):,}</td><td>{int(r['balance_before']):,}</td><td>{int(r['balance_after']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['source_label'])}</td><td>{esc(r['reason'])}</td><td><code>{r['actor_id']}</code></td></tr>"
            for r in rows
        )

        form = f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <input name=actor_id placeholder='Actor ID' value='{esc(actor_id)}'>
            <input name=source placeholder='source_type مثل casino / salary' value='{esc(source)}'>
            <select name=direction>
              <option value='' {'selected' if direction == '' else ''}>All</option>
              <option value='in' {'selected' if direction == 'in' else ''}>Money In</option>
              <option value='out' {'selected' if direction == 'out' else ''}>Money Out</option>
            </select>
            <input name=min_amount placeholder='Min abs' value='{esc(min_amount)}' style='width:90px'>
            <input name=max_amount placeholder='Max abs' value='{esc(max_amount)}' style='width:90px'>
            <input name=limit placeholder='Limit' value='{limit}' style='width:90px'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}'>Reset</a>
          </form>
        </div>
        """

        body = server_pill_html(g, bot) + form
        body += f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Ledger Rows</div><div class='stat'>{int(totals['rows'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Money In</div><div class='stat'>{int(totals['money_in'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Money Out</div><div class='stat'>{int(totals['money_out'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Net</div><div class='stat'>{int(totals['net'] or 0):,}</div></div>
        </div>
        """
        body += f"<div class='card'><h3>Quick Source Filters</h3>{chips}</div>"
        body += f"<div class='card'><h3>Source Summary</h3><table><tr><th>Source</th><th>Rows</th><th>In</th><th>Out</th><th>Net</th></tr>{source_trs}</table></div>"
        body += f"<div class='grid'><div class='card'><h3>Top Received</h3><table><tr><th>User</th><th>In</th><th>Out</th><th>Net</th><th>Rows</th><th></th></tr>{received_trs}</table></div><div class='card'><h3>Top Actors</h3><table><tr><th>Actor</th><th>Name</th><th>Volume</th><th>Rows</th></tr>{actor_trs}</table></div></div>"
        body += f"<div class='card'><h3>Ledger Rows</h3><table><tr><th>TX</th><th>User</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Label</th><th>Reason</th><th>Actor</th></tr>{trs}</table></div>"
        return page("Money Tracker", body, g)

    @app.route("/dashboard/casino")
    def casino_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        user_filter = request.args.get("user_id", "").strip()
        game_filter = request.args.get("game", "").strip()

        conn = db()
        cur = conn.cursor()

        where = "WHERE guild_id=? AND source_type LIKE 'casino_%'"
        params = [g]

        if user_filter.isdigit():
            where += " AND user_id=?"
            params.append(int(user_filter))

        if game_filter:
            where += " AND source_label=?"
            params.append(game_filter)

        cur.execute(f"""SELECT source_label, COUNT(*) c,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COALESCE(SUM(amount),0) net
        FROM money_ledger {where}
        GROUP BY source_label ORDER BY c DESC""", params)
        game_rows = cur.fetchall()

        cur.execute(f"""SELECT user_id,
        COALESCE(SUM(amount),0) net,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) wagered,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows
        FROM money_ledger
        {where}
        GROUP BY user_id
        ORDER BY net ASC
        LIMIT 10""", params)
        biggest_losers = cur.fetchall()

        cur.execute(f"""SELECT user_id,
        COALESCE(SUM(amount),0) net,
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) wagered,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows
        FROM money_ledger
        {where}
        GROUP BY user_id
        ORDER BY net DESC
        LIMIT 10""", params)
        biggest_winners = cur.fetchall()

        cur.execute(f"""SELECT
        COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took,
        COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid,
        COUNT(*) rows,
        COUNT(DISTINCT user_id) users
        FROM money_ledger {where}""", params)
        total = cur.fetchone()

        cur.execute(f"""SELECT * FROM money_ledger {where}
        ORDER BY id DESC LIMIT 100""", params)
        recent = cur.fetchall()

        conn.close()

        took = int(total["took"] or 0)
        paid = int(total["paid"] or 0)
        net = took - paid

        game_trs = "".join(
            f"<tr><td><a href='/dashboard/casino?guild_id={g}&game={esc(r['source_label'])}'>{esc(r['source_label'])}</a></td><td>{int(r['c']):,}</td><td>{int(r['took']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['took'] or 0)-int(r['paid'] or 0):,}</td></tr>"
            for r in game_rows
        )

        loser_trs = "".join(
            f"<tr><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'><code>{r['user_id']}</code></a></td><td>{int(r['net']):,}</td><td>{int(r['wagered']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['rows']):,}</td></tr>"
            for r in biggest_losers
        )

        winner_trs = "".join(
            f"<tr><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'><code>{r['user_id']}</code></a></td><td>{int(r['net']):,}</td><td>{int(r['wagered']):,}</td><td>{int(r['paid']):,}</td><td>{int(r['rows']):,}</td></tr>"
            for r in biggest_winners
        )

        recent_trs = "".join(
            f"<tr><td><code>{r['tx_id'][:10]}</code></td><td><code>{r['user_id']}</code></td><td>{esc(r['source_label'])}</td><td>{int(r['amount']):,}</td><td>{int(r['balance_after']):,}</td><td>{esc(r['reason'])}</td></tr>"
            for r in recent
        )

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(user_filter)}'>
            <input name=game placeholder='Game/source_label' value='{esc(game_filter)}'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/casino?guild_id={g}'>Reset</a>
          </form>
        </div>
        <div class='grid'>
          <div class='card'><div class='muted'>Casino Took</div><div class='stat'>{took:,}</div></div>
          <div class='card'><div class='muted'>Casino Paid</div><div class='stat'>{paid:,}</div></div>
          <div class='card'><div class='muted'>Casino Net</div><div class='stat'>{net:,}</div></div>
          <div class='card'><div class='muted'>Players</div><div class='stat'>{int(total['users'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Rows</div><div class='stat'>{int(total['rows'] or 0):,}</div></div>
        </div>
        <div class='card'><h3>By Game</h3><table><tr><th>Game</th><th>Rows</th><th>Took</th><th>Paid</th><th>House Net</th></tr>{game_trs}</table></div>
        <div class='grid'>
          <div class='card'><h3>Biggest Winners</h3><table><tr><th>User</th><th>Net</th><th>Wagered</th><th>Paid</th><th>Rows</th></tr>{winner_trs}</table></div>
          <div class='card'><h3>Biggest Losers</h3><table><tr><th>User</th><th>Net</th><th>Wagered</th><th>Paid</th><th>Rows</th></tr>{loser_trs}</table></div>
        </div>
        <div class='card'><h3>Recent Casino Ledger</h3><table><tr><th>TX</th><th>User</th><th>Game</th><th>Amount</th><th>Balance After</th><th>Reason</th></tr>{recent_trs}</table></div>
        """
        return page("Casino", body, g)

    @app.route("/dashboard/levels", methods=["GET", "POST"])
    def levels_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                user_id = int(request.form.get("user_id") or 0)
            except Exception:
                user_id = 0

            try:
                xp = int(request.form.get("xp") or 0)
            except Exception:
                xp = 0

            try:
                level = int(request.form.get("level") or 1)
            except Exception:
                level = 1

            if user_id and action in {"set", "add_xp", "reset"}:
                conn = db()
                cur = conn.cursor()

                cur.execute("INSERT OR IGNORE INTO levels (guild_id,user_id,xp,level,updated_at) VALUES (?,?,0,1,strftime('%s','now'))", (g, user_id))

                if action == "set":
                    cur.execute("UPDATE levels SET xp=?, level=?, updated_at=strftime('%s','now') WHERE guild_id=? AND user_id=?", (max(0, xp), max(1, level), g, user_id))
                elif action == "add_xp":
                    cur.execute("UPDATE levels SET xp=xp+?, updated_at=strftime('%s','now') WHERE guild_id=? AND user_id=?", (max(0, xp), g, user_id))
                elif action == "reset":
                    cur.execute("UPDATE levels SET xp=0, level=1, updated_at=strftime('%s','now') WHERE guild_id=? AND user_id=?", (g, user_id))

                conn.commit()
                conn.close()

                log_event(g, f"dashboard_levels_{action}", user_id, str(user_id), 0, "", f"Dashboard levels {action}", f"Actor={actor_id}, XP={xp}, Level={level}")

            return redirect(f"/dashboard/levels?guild_id={g}")

        uid = request.args.get("user_id", "").strip()

        conn = db()
        cur = conn.cursor()

        q = "SELECT * FROM levels WHERE guild_id=?"
        params = [g]

        if uid.isdigit():
            q += " AND user_id=?"
            params.append(int(uid))

        q += " ORDER BY level DESC,xp DESC LIMIT 150"

        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) c, COALESCE(SUM(xp),0) total_xp, COALESCE(AVG(level),0) avg_level, COALESCE(MAX(level),1) max_level FROM levels WHERE guild_id=?", (g,))
        stats = cur.fetchone()

        conn.close()

        trs = "".join(
            f"""<tr>
              <td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'><code>{r['user_id']}</code></a></td>
              <td>{int(r['level'])}</td>
              <td>{int(r['xp']):,}</td>
              <td>
                <form method='post' style='display:inline-grid;grid-template-columns:120px 80px 80px 70px 80px;gap:6px'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=user_id value='{r['user_id']}'>
                  <input name=xp value='{int(r['xp'])}' type=number min=0>
                  <input name=level value='{int(r['level'])}' type=number min=1>
                  <button name=action value='set'>Set</button>
                  <button name=action value='add_xp' style='background:#334155'>Add XP</button>
                  <button name=action value='reset' style='background:#dc2626'>Reset</button>
                </form>
              </td>
            </tr>"""
            for r in rows
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Level Users</div><div class='stat'>{int(stats['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Total XP</div><div class='stat'>{int(stats['total_xp'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Average Level</div><div class='stat'>{float(stats['avg_level'] or 0):.1f}</div></div>
          <div class='card'><div class='muted'>Max Level</div><div class='stat'>{int(stats['max_level'] or 1):,}</div></div>
        </div>

        <div class='card'>
          <h3>Level Admin Control</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' required>
            <input name=xp type=number min=0 placeholder='XP'>
            <input name=level type=number min=1 placeholder='Level'>
            <button name=action value='set'>Set XP/Level</button>
            <button name=action value='add_xp' style='background:#334155'>Add XP</button>
            <button name=action value='reset' style='background:#dc2626'>Reset</button>
          </form>
        </div>

        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/levels?guild_id={g}'>Reset</a>
          </form>
        </div>

        <div class='card'><h3>Levels</h3><table><tr><th>User</th><th>Level</th><th>XP</th><th>Actions</th></tr>{trs}</table></div>
        """
        return page("Levels", body, g)

    @app.route("/dashboard/real-estate", methods=["GET", "POST"])
    def real_estate_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        real_estate.seed(g)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                property_id = int(request.form.get("property_id") or 0)
            except Exception:
                property_id = 0

            try:
                owner_id = int(request.form.get("owner_id") or 0)
            except Exception:
                owner_id = 0

            owner_name = request.form.get("owner_name", "").strip() or str(owner_id or "")
            reason = request.form.get("reason", "").strip() or f"Dashboard real estate {action}"

            conn = db()
            cur = conn.cursor()

            if action in {"set_owner", "clear_owner", "edit_property"} and property_id:
                cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (g, property_id))
                prop = cur.fetchone()

                if prop:
                    if action == "set_owner":
                        cur.execute(
                            "UPDATE properties SET owner_id=?, owner_name=? WHERE guild_id=? AND id=?",
                            (owner_id, owner_name[:120], g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_set_owner", int(prop["owner_id"] or 0), owner_id, actor_id, 0, int(prop["level"]), int(prop["level"]), int(prop["price"]), int(prop["price"]), reason, ""))

                    elif action == "clear_owner":
                        cur.execute(
                            "UPDATE properties SET owner_id=0, owner_name='' WHERE guild_id=? AND id=?",
                            (g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_clear_owner", int(prop["owner_id"] or 0), 0, actor_id, 0, int(prop["level"]), int(prop["level"]), int(prop["price"]), int(prop["price"]), reason, ""))

                    elif action == "edit_property":
                        try:
                            price = max(0, int(request.form.get("price") or prop["price"]))
                            rent = max(0, int(request.form.get("rent") or prop["rent"]))
                            level = max(1, int(request.form.get("level") or prop["level"]))
                        except Exception:
                            price, rent, level = int(prop["price"]), int(prop["rent"]), int(prop["level"])

                        cur.execute(
                            "UPDATE properties SET price=?, rent=?, level=? WHERE guild_id=? AND id=?",
                            (price, rent, level, g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_edit_property", int(prop["owner_id"] or 0), int(prop["owner_id"] or 0), actor_id, 0, int(prop["level"]), level, int(prop["price"]), price, reason, ""))

                    conn.commit()

                    log_event(
                        g,
                        f"dashboard_real_estate_{action}",
                        owner_id or int(prop["owner_id"] or 0),
                        owner_name,
                        0,
                        "",
                        f"Dashboard real estate {action}",
                        f"Actor={actor_id}, Property={property_id}, Reason={reason}"
                    )

            conn.close()
            return redirect(f"/dashboard/real-estate?guild_id={g}")

        owner_filter = request.args.get("owner_id", "").strip()
        only_available = request.args.get("available", "").strip() == "1"

        rows = real_estate.rows(g)

        if owner_filter.isdigit():
            rows = [r for r in rows if int(r["owner_id"] or 0) == int(owner_filter)]

        if only_available:
            rows = [r for r in rows if int(r["owner_id"] or 0) == 0]

        rows = rows[:300]

        trs = "".join(
            f"""<tr>
              <td>{r['id']}</td>
              <td>{esc(r['display_name'])}</td>
              <td>{r['owner_id'] or '-'}</td>
              <td>{esc(r['owner_name'] or '')}</td>
              <td>{int(r['price']):,}</td>
              <td>{int(r['rent']):,}</td>
              <td>{r['level']}</td>
              <td>
                <form method='post' style='display:grid;grid-template-columns:110px 110px 80px 80px 70px 120px;gap:6px;min-width:620px'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=property_id value='{r['id']}'>
                  <input name=owner_id placeholder='Owner ID'>
                  <input name=owner_name placeholder='Name'>
                  <input name=price value='{int(r['price'])}' type=number min=0>
                  <input name=rent value='{int(r['rent'])}' type=number min=0>
                  <input name=level value='{int(r['level'])}' type=number min=1>
                  <input name=reason placeholder='Reason'>
                  <button name=action value='set_owner'>Set Owner</button>
                  <button name=action value='clear_owner' style='background:#dc2626'>Clear</button>
                  <button name=action value='edit_property' style='background:#334155'>Edit</button>
                </form>
              </td>
            </tr>"""
            for r in rows
        )

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=owner_id placeholder='Owner ID' value='{esc(owner_filter)}'>
            <label><input type=checkbox name=available value=1 {'checked' if only_available else ''}> Available only</label>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/real-estate?guild_id={g}'>Reset</a>
          </form>
        </div>
        <div class='card'>
          <h3>Real Estate Admin Control</h3>
          <table>
            <tr><th>ID</th><th>Name</th><th>Owner</th><th>Owner Name</th><th>Price</th><th>Rent</th><th>Level</th><th>Actions</th></tr>
            {trs}
          </table>
        </div>
        """
        return page("Real Estate", body, g)

    @app.route("/dashboard/warnings", methods=["GET", "POST"])
    def warnings_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                user_id = int(request.form.get("user_id") or 0)
            except Exception:
                user_id = 0

            user_name = request.form.get("user_name", "").strip() or str(user_id or "")
            reason = request.form.get("reason", "").strip() or "Dashboard action"

            if action == "add_warning" and user_id:
                from nmcore.services import warnings as warnsvc
                warnsvc.add_warning(g, user_id, user_name, actor_id, actor_name, reason, "Added from dashboard")

                log_event(
                    g,
                    "dashboard_add_warning",
                    user_id,
                    user_name,
                    0,
                    "",
                    "Dashboard added warning",
                    f"Actor={actor_id}, Reason={reason}"
                )

                return redirect(f"/dashboard/warnings?guild_id={g}&user_id={user_id}&status=all")

            if action == "clear_user" and user_id:
                from nmcore.services import warnings as warnsvc
                count = warnsvc.clear_user(g, user_id, actor_id, actor_name, reason)

                log_event(
                    g,
                    "dashboard_clear_warnings",
                    user_id,
                    str(user_id),
                    0,
                    "",
                    "Dashboard cleared warnings",
                    f"Actor={actor_id}, Count={count}, Reason={reason}"
                )

                return redirect(f"/dashboard/warnings?guild_id={g}&user_id={user_id}&status=all")

            if action == "clear_warning":
                try:
                    warning_id = int(request.form.get("warning_id") or 0)
                except Exception:
                    warning_id = 0

                if warning_id:
                    conn = db()
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM warnings WHERE guild_id=? AND id=?", (g, warning_id))
                    row = cur.fetchone()

                    if row and str(row["status"]) == "active":
                        cur.execute("""UPDATE warnings SET status='cleared', cleared_at=strftime('%s','now'),
                        cleared_by_id=?, cleared_by_name=?, clear_reason=? WHERE guild_id=? AND id=?""",
                        (actor_id, actor_name, reason, g, warning_id))
                        conn.commit()

                        log_event(
                            g,
                            "dashboard_clear_warning",
                            int(row["user_id"]),
                            str(row["user_name"]),
                            0,
                            "",
                            "Dashboard cleared one warning",
                            f"Actor={actor_id}, WarningID={warning_id}, Reason={reason}"
                        )

                    conn.close()

                return redirect(f"/dashboard/warnings?guild_id={g}&status=all")

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
            f"""<tr>
              <td><code>{r['user_id']}</code></td>
              <td>{esc(r['user_name'])}</td>
              <td>{int(r['active_count'] or 0):,}</td>
              <td>{int(r['total'] or 0):,}</td>
              <td><a href='/dashboard/warnings?guild_id={g}&user_id={r['user_id']}'>View</a></td>
              <td>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=action value='clear_user'>
                  <input type=hidden name=user_id value='{r['user_id']}'>
                  <input type=hidden name=reason value='Cleared from dashboard'>
                  <button style='background:#334155'>Clear Active</button>
                </form>
              </td>
            </tr>"""
            for r in grouped
        )

        trs = "".join(
            f"""<tr>
              <td>{r['id']}</td>
              <td><code>{r['user_id']}</code></td>
              <td>{esc(r['user_name'])}</td>
              <td>{esc(r['reason'])}</td>
              <td>{esc(r['status'])}</td>
              <td>{esc(r['moderator_name'])}</td>
              <td>
                {f"<form method='post' style='display:inline'><input type=hidden name=guild_id value='{g}'><input type=hidden name=action value='clear_warning'><input type=hidden name=warning_id value='{r['id']}'><input type=hidden name=reason value='Cleared one warning from dashboard'><button style='background:#334155'>Clear One</button></form>" if str(r['status']) == 'active' else ''}
              </td>
            </tr>"""
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

        <div class='card'>
          <h3>Add Warning From Dashboard</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='add_warning'>
            <input name=user_id placeholder='User ID' required>
            <input name=user_name placeholder='Name optional'>
            <input name=reason placeholder='Reason' style='min-width:320px' required>
            <button>Add Warning</button>
          </form>
        </div>
        """

        body = server_pill_html(g, bot) + form
        body += f"<div class='card'><h3>Users Warning Summary</h3><table><tr><th>User ID</th><th>Name</th><th>Active</th><th>Total</th><th></th><th>Action</th></tr>{grouped_trs}</table></div>"
        body += f"<div class='card'><h3>Warning Records</h3><table><tr><th>ID</th><th>User</th><th>Name</th><th>Reason</th><th>Status</th><th>By</th><th>Action</th></tr>{trs}</table></div>"

        return page("Warnings", body, g)

    @app.route("/dashboard/protection", methods=["GET", "POST"])
    def protection_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        test_result = ""

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "reset_bad_words":
                prot_update(g, {"bad_words": get_default_bad_words()})
                return redirect(f"/dashboard/protection?guild_id={g}")

            if action == "save_antiraid":
                def as_int(name, default=0):
                    try:
                        return int(request.form.get(name) or default)
                    except Exception:
                        return default

                antiraid.update_settings(g, {
                    "enabled": 1 if request.form.get("ar_enabled") else 0,
                    "anti_kick": 1 if request.form.get("anti_kick") else 0,
                    "anti_ban": 1 if request.form.get("anti_ban") else 0,
                    "anti_role_delete": 1 if request.form.get("anti_role_delete") else 0,
                    "anti_role_update": 1 if request.form.get("anti_role_update") else 0,
                    "anti_member_role_update": 1 if request.form.get("anti_member_role_update") else 0,
                    "anti_channel_create": 1 if request.form.get("anti_channel_create") else 0,
                    "anti_channel_delete": 1 if request.form.get("anti_channel_delete") else 0,
                    "anti_channel_update": 1 if request.form.get("anti_channel_update") else 0,
                    "anti_webhook_create": 1 if request.form.get("anti_webhook_create") else 0,
                    "anti_bot_add": 1 if request.form.get("anti_bot_add") else 0,
                    "threshold": as_int("ar_threshold", 3),
                    "window": as_int("ar_window", 60),
                    "punish_action": request.form.get("punish_action", "remove_roles"),
                    "trusted_users": request.form.get("trusted_users", ""),
                    "trusted_roles": request.form.get("trusted_roles", ""),
                })
                return redirect(f"/dashboard/protection?guild_id={g}")

            if action == "test_message":
                s_test = prot_get(g)
                raw = request.form.get("test_text", "")

                class DummyAuthor:
                    id = 0
                    display_name = "Dashboard Test"
                    roles = []

                class DummyChannel:
                    id = 0
                    name = "dashboard-test"

                class DummyGuild:
                    id = g

                class DummyMessage:
                    content = raw
                    author = DummyAuthor()
                    channel = DummyChannel()
                    guild = DummyGuild()
                    mentions = []
                    role_mentions = []

                result = check_message(DummyMessage(), s_test)
                test_result = f"""
                <div class='card'>
                  <h3>Protection Test Result</h3>
                  <p>Blocked: <b class='{'bad' if result.get('blocked') else 'ok'}'>{'YES' if result.get('blocked') else 'NO'}</b></p>
                  <p>Warning: <b class='{'warn' if result.get('warning') else 'ok'}'>{'YES' if result.get('warning') else 'NO'}</b></p>
                  <p>Kind: <code>{esc(result.get('kind') or '-')}</code></p>
                  <p>Reason: <code>{esc(result.get('reason') or '-')}</code></p>
                  <p>Matched: <code>{esc(result.get('matched') or '-')}</code></p>
                  <p>Details: <code>{esc(result.get('details') or '-')}</code></p>
                </div>
                """
            else:
                def as_int(name, default=0):
                    try:
                        return int(request.form.get(name) or default)
                    except Exception:
                        return default

                data = {
                    "enabled": 1 if request.form.get("enabled") else 0,
                    "bad_words_enabled": 1 if request.form.get("bad_words_enabled") else 0,
                    "links_enabled": 1 if request.form.get("links_enabled") else 0,
                    "spam_enabled": 1 if request.form.get("spam_enabled") else 0,
                    "mass_mention_enabled": 1 if request.form.get("mass_mention_enabled") else 0,
                    "delete_messages": 1 if request.form.get("delete_messages") else 0,
                    "caps_enabled": 1 if request.form.get("caps_enabled") else 0,
                    "duplicate_enabled": 1 if request.form.get("duplicate_enabled") else 0,
                    "invite_block_enabled": 1 if request.form.get("invite_block_enabled") else 0,
                    "max_newlines_enabled": 1 if request.form.get("max_newlines_enabled") else 0,
                    "bad_words": request.form.get("bad_words", ""),
                    "ignored_channels": request.form.get("ignored_channels", ""),
                    "whitelist_roles": request.form.get("whitelist_roles", ""),
                    "link_whitelist": request.form.get("link_whitelist", ""),
                    "spam_threshold": as_int("spam_threshold", 6),
                    "spam_window": as_int("spam_window", 8),
                    "mention_threshold": as_int("mention_threshold", 6),
                    "caps_percent": as_int("caps_percent", 85),
                    "caps_min_length": as_int("caps_min_length", 18),
                    "duplicate_threshold": as_int("duplicate_threshold", 4),
                    "duplicate_window": as_int("duplicate_window", 15),
                    "max_newlines": as_int("max_newlines", 12),
                }
                prot_update(g, data)
                return redirect(f"/dashboard/protection?guild_id={g}")

        s = prot_get(g)
        ar = antiraid.get_settings(g)

        bad_words_raw = str(s.get("bad_words") or "")
        bad_count = len([w for w in bad_words_raw.split(",") if w.strip()])
        ignored_count = len([w for w in str(s.get("ignored_channels") or "").replace("\n", ",").split(",") if w.strip()])
        whitelist_count = len([w for w in str(s.get("whitelist_roles") or "").replace("\n", ",").split(",") if w.strip()])

        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT * FROM log_events
        WHERE guild_id=? AND (event_type LIKE 'protection_%' OR event_type LIKE 'antiraid_%')
        ORDER BY id DESC LIMIT 100""", (g,))
        events = cur.fetchall()

        cur.execute("""SELECT * FROM warnings
        WHERE guild_id=? AND moderator_name LIKE '%NM System%'
        ORDER BY id DESC LIMIT 80""", (g,))
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

        def checked(v):
            return "checked" if int(v or 0) else ""

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Protection</div><div class='stat'>{'ON' if s.get('enabled') else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Anti-Raid</div><div class='stat'>{'ON' if ar.get('enabled') else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Bad Words</div><div class='stat'>{bad_count:,}</div></div>
          <div class='card'><div class='muted'>Ignored Channels</div><div class='stat'>{ignored_count:,}</div></div>
          <div class='card'><div class='muted'>Whitelist Roles</div><div class='stat'>{whitelist_count:,}</div></div>
          <div class='card'><div class='muted'>Auto Warnings</div><div class='stat'>{len(auto_warnings):,}</div></div>
        </div>

        {test_result}

        <div class='card'>
          <h3>Test Chat Protection</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='test_message'>
            <textarea name=test_text placeholder='اكتب رسالة تجربة هنا' style='width:100%;height:70px'></textarea><br><br>
            <button>Test Only</button>
          </form>
        </div>

        <div class='card'>
          <h3>Anti-Raid / Admin Abuse Protection</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_antiraid'>

            <div class='grid'>
              <label><input type=checkbox name=ar_enabled {checked(ar.get('enabled'))}> Anti-Raid Enabled</label>
              <label><input type=checkbox name=anti_kick {checked(ar.get('anti_kick'))}> Anti Kick</label>
              <label><input type=checkbox name=anti_ban {checked(ar.get('anti_ban'))}> Anti Ban</label>
              <label><input type=checkbox name=anti_role_delete {checked(ar.get('anti_role_delete'))}> Anti Role Delete</label>
              <label><input type=checkbox name=anti_role_update {checked(ar.get('anti_role_update'))}> Anti Role Edit</label>
              <label><input type=checkbox name=anti_member_role_update {checked(ar.get('anti_member_role_update'))}> Anti Member Role Edit</label>
              <label><input type=checkbox name=anti_channel_create {checked(ar.get('anti_channel_create'))}> Anti Channel Create</label>
              <label><input type=checkbox name=anti_channel_delete {checked(ar.get('anti_channel_delete'))}> Anti Channel Delete</label>
              <label><input type=checkbox name=anti_channel_update {checked(ar.get('anti_channel_update'))}> Anti Channel Edit</label>
              <label><input type=checkbox name=anti_webhook_create {checked(ar.get('anti_webhook_create'))}> Anti Webhook Create</label>
              <label><input type=checkbox name=anti_bot_add {checked(ar.get('anti_bot_add'))}> Anti Bot Add</label>
            </div>

            <br>
            Threshold<br>
            <input name=ar_threshold type=number min=1 value='{int(ar.get('threshold') or 3)}'>
            Window seconds<br>
            <input name=ar_window type=number min=5 value='{int(ar.get('window') or 60)}'>
            Punish Action<br>
            <select name=punish_action>
              <option value='remove_roles' {'selected' if ar.get('punish_action') == 'remove_roles' else ''}>Remove Roles</option>
              <option value='none' {'selected' if ar.get('punish_action') == 'none' else ''}>Log Only</option>
            </select>

            <br><br>
            Trusted User IDs<br>
            <textarea name=trusted_users style='width:100%;height:65px' placeholder='Owner/Admin IDs separated by comma'>{esc(ar.get('trusted_users') or '')}</textarea><br><br>

            Trusted Role IDs<br>
            <textarea name=trusted_roles style='width:100%;height:65px' placeholder='Trusted role IDs separated by comma'>{esc(ar.get('trusted_roles') or '')}</textarea><br><br>

            <button>Save Anti-Raid</button>
          </form>
        </div>

        <div class='card'>
          <h3>Chat Protection Control</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>

            <div class='grid'>
              <label><input type=checkbox name=enabled {checked(s.get('enabled'))}> Enabled</label>
              <label><input type=checkbox name=delete_messages {checked(s.get('delete_messages'))}> Delete Messages</label>
              <label><input type=checkbox name=bad_words_enabled {checked(s.get('bad_words_enabled'))}> Bad Words</label>
              <label><input type=checkbox name=links_enabled {checked(s.get('links_enabled'))}> Links</label>
              <label><input type=checkbox name=invite_block_enabled {checked(s.get('invite_block_enabled'))}> Discord Invites</label>
              <label><input type=checkbox name=spam_enabled {checked(s.get('spam_enabled'))}> Anti Spam</label>
              <label><input type=checkbox name=duplicate_enabled {checked(s.get('duplicate_enabled'))}> Anti Duplicate</label>
              <label><input type=checkbox name=mass_mention_enabled {checked(s.get('mass_mention_enabled'))}> Anti Mass Mention</label>
              <label><input type=checkbox name=caps_enabled {checked(s.get('caps_enabled'))}> Anti Caps</label>
              <label><input type=checkbox name=max_newlines_enabled {checked(s.get('max_newlines_enabled'))}> Anti Long Newlines</label>
            </div>

            <h3>Thresholds</h3>
            <div class='grid'>
              <div>Spam Threshold<br><input name=spam_threshold type=number min=2 value='{int(s.get('spam_threshold') or 6)}'></div>
              <div>Spam Window<br><input name=spam_window type=number min=2 value='{int(s.get('spam_window') or 8)}'></div>
              <div>Mention Threshold<br><input name=mention_threshold type=number min=1 value='{int(s.get('mention_threshold') or 6)}'></div>
              <div>Duplicate Threshold<br><input name=duplicate_threshold type=number min=2 value='{int(s.get('duplicate_threshold') or 4)}'></div>
              <div>Duplicate Window<br><input name=duplicate_window type=number min=2 value='{int(s.get('duplicate_window') or 15)}'></div>
              <div>Caps Percent<br><input name=caps_percent type=number min=1 max=100 value='{int(s.get('caps_percent') or 85)}'></div>
              <div>Caps Min Length<br><input name=caps_min_length type=number min=1 value='{int(s.get('caps_min_length') or 18)}'></div>
              <div>Max Newlines<br><input name=max_newlines type=number min=1 value='{int(s.get('max_newlines') or 12)}'></div>
            </div>

            <h3>Bad Words / Phrases</h3>
            <textarea name=bad_words style='width:100%;height:170px'>{esc(bad_words_raw)}</textarea><br><br>

            Ignored Channel IDs<br>
            <textarea name=ignored_channels style='width:100%;height:60px'>{esc(s.get('ignored_channels') or '')}</textarea><br><br>

            Whitelist Role IDs<br>
            <textarea name=whitelist_roles style='width:100%;height:60px'>{esc(s.get('whitelist_roles') or '')}</textarea><br><br>

            Link Whitelist<br>
            <textarea name=link_whitelist style='width:100%;height:60px' placeholder='youtube.com, twitch.tv'>{esc(s.get('link_whitelist') or '')}</textarea><br><br>

            <button>Save Chat Protection</button>
            <button name='action' value='reset_bad_words' style='background:#334155;margin-left:8px'>Reset Bad Words</button>
          </form>
        </div>

        <div class='card'><h3>Recent Protection / Anti-Raid Events</h3><table><tr><th>Type</th><th>User</th><th>Channel</th><th>Title</th><th>Details</th></tr>{event_trs}</table></div>
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

        cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=?", (g,))
        total_logs = int(cur.fetchone()["c"] or 0)

        conn.close()

        log_map = all_log_channels(g)
        log_channel_rows = ""
        for key, (name, topic) in LOG_CHANNELS.items():
            cid = int(log_map.get(key) or 0)
            log_channel_rows += f"<tr><td><code>{esc(key)}</code></td><td>{esc(name)}</td><td>{f'<#{cid}>' if cid else '<span class=muted>Not set</span>'}</td><td><code>{cid}</code></td></tr>"

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

        body = server_pill_html(g, bot)
        body += f"<div class='grid'><div class='card'><div class='muted'>Total DB Logs</div><div class='stat'>{total_logs:,}</div></div><div class='card'><div class='muted'>Mapped Log Rooms</div><div class='stat'>{sum(1 for x in log_map.values() if int(x or 0)):,}/{len(LOG_CHANNELS)}</div></div></div>"
        body += f"<div class='card'><h3>Discord Log Rooms Mapping</h3><table><tr><th>Key</th><th>Room Name</th><th>Current</th><th>ID</th></tr>{log_channel_rows}</table><br><a class='btn' href='/dashboard/settings?guild_id={g}'>Edit Mapping</a></div>"
        body += form
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
        actor_id = request.args.get("actor_id", "").strip()
        limit_raw = request.args.get("limit", "250").strip()

        try:
            limit = max(25, min(int(limit_raw or 250), 1000))
        except Exception:
            limit = 250

        conn = db()
        cur = conn.cursor()

        q = "SELECT * FROM live_activity WHERE guild_id=?"
        params = [g]

        if activity_type:
            q += " AND activity_type=?"
            params.append(activity_type)

        if actor_id.isdigit():
            q += " AND actor_id=?"
            params.append(int(actor_id))

        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT activity_type, COUNT(*) c, COALESCE(SUM(amount),0) amount
        FROM live_activity
        WHERE guild_id=? GROUP BY activity_type ORDER BY c DESC LIMIT 30""", (g,))
        types = cur.fetchall()

        cur.execute("""SELECT actor_id, actor_name, COUNT(*) c, COALESCE(SUM(amount),0) amount
        FROM live_activity WHERE guild_id=?
        GROUP BY actor_id, actor_name ORDER BY c DESC LIMIT 15""", (g,))
        actors = cur.fetchall()

        cur.execute("SELECT COUNT(*) c FROM live_activity WHERE guild_id=?", (g,))
        total = cur.fetchone()

        conn.close()

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:#334155' href='/dashboard/live?guild_id={g}&activity_type={esc(r['activity_type'])}'>{esc(r['activity_type'])} ({int(r['c'])})</a>"
            for r in types
        )

        type_trs = "".join(
            f"<tr><td>{esc(r['activity_type'])}</td><td>{int(r['c']):,}</td><td>{int(r['amount'] or 0):,}</td></tr>"
            for r in types
        )

        actor_trs = "".join(
            f"<tr><td><code>{r['actor_id']}</code></td><td>{esc(r['actor_name'])}</td><td>{int(r['c']):,}</td><td>{int(r['amount'] or 0):,}</td></tr>"
            for r in actors
        )

        trs = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['activity_type'])}</td><td><code>{r['actor_id']}</code></td><td>{esc(r['actor_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td><td>{int(r['amount']):,}</td></tr>"
            for r in rows
        )

        body = server_pill_html(g, bot)
        body += f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=activity_type placeholder='activity_type' value='{esc(activity_type)}'>
            <input name=actor_id placeholder='Actor ID' value='{esc(actor_id)}'>
            <input name=limit placeholder='Limit' value='{limit}' style='width:90px'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/live?guild_id={g}'>Reset</a>
          </form>
        </div>
        <div class='grid'>
          <div class='card'><div class='muted'>Live Rows</div><div class='stat'>{int(total['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Activity Types</div><div class='stat'>{len(types):,}</div></div>
        </div>
        """
        body += f"<div class='card'><h3>Live Filters</h3>{chips or '<span class=muted>No live activity yet.</span>'}</div>"
        body += f"<div class='grid'><div class='card'><h3>Activity Summary</h3><table><tr><th>Type</th><th>Rows</th><th>Amount</th></tr>{type_trs}</table></div><div class='card'><h3>Top Actors</h3><table><tr><th>Actor</th><th>Name</th><th>Rows</th><th>Amount</th></tr>{actor_trs}</table></div></div>"
        body += f"<div class='card'><table><tr><th>ID</th><th>Type</th><th>Actor</th><th>Name</th><th>Title</th><th>Details</th><th>Amount</th></tr>{trs}</table></div>"
        return page("Live Activity", body, g)

    @app.route("/dashboard/settings", methods=["GET", "POST"])
    def settings_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "save_log_channels":
                for key in LOG_CHANNELS.keys():
                    raw = request.form.get(f"log_{key}", "0")
                    try:
                        channel_id = int(raw or 0)
                    except Exception:
                        channel_id = 0
                    set_log_channel(g, key, channel_id)

                general_id = int(request.form.get("log_general") or 0)
                if general_id:
                    update_channel(g, "logs_channel_id", general_id)

                return redirect(f"/dashboard/settings?guild_id={g}")

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
        log_map = all_log_channels(g)

        checks = "".join(
            f"<label><input type=checkbox name='toggle_{k}' {'checked' if v else ''}> {k}</label><br>"
            for k, v in toggles.items()
        )

        log_rows = ""
        for key, (name, topic) in LOG_CHANNELS.items():
            current = int(log_map.get(key) or 0)
            mention = f"<#{current}>" if current else "<span class='muted'>Not set</span>"
            log_rows += f"""
            <tr>
              <td><code>{esc(key)}</code></td>
              <td>{esc(name)}</td>
              <td>{mention}</td>
              <td><input name='log_{esc(key)}' value='{current}' style='width:210px'></td>
            </tr>
            """

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Commands Room</div><div class='stat'>{f'<#{commands_channel_id}>' if commands_channel_id else 'OFF'}</div></div>
          <div class='card'><div class='muted'>Gambling Room</div><div class='stat'>{f'<#{gambling_channel_id}>' if gambling_channel_id else 'OFF'}</div></div>
          <div class='card'><div class='muted'>General Logs</div><div class='stat'>{f'<#{logs_channel_id}>' if logs_channel_id else 'OFF'}</div></div>
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

            Old General Logs Channel ID<br>
            <input name=logs_channel_id value='{logs_channel_id}'><br><br>

            <h3>System Toggles</h3>
            {checks}
            <br>
            <button>Save</button>
          </form>
        </div>

        <div class='card'>
          <h3>Organized Discord Log Channels</h3>
          <p class='muted'>Run <code>!تجهيز_اللوقات</code> to auto-create and map these rooms. You can also edit IDs manually here.</p>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_log_channels'>
            <table>
              <tr><th>Key</th><th>Channel Name</th><th>Current</th><th>Channel ID</th></tr>
              {log_rows}
            </table>
            <br>
            <button>Save Log Channels</button>
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

            if action in {"add", "update"}:
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

        user_filter = request.args.get("user_id", "").strip()
        items = shop_service.items(g, include_disabled=True)

        if user_filter.isdigit():
            conn = db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM shop_purchases WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 100", (g, int(user_filter)))
            purchases = cur.fetchall()
            conn.close()
        else:
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
                <form method='post' style='display:grid;grid-template-columns:120px 120px 90px 120px 70px;gap:6px;min-width:560px'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=action value='update'>
                  <input type=hidden name=item_key value='{esc(r['item_key'])}'>
                  <input name=name value='{esc(r['name'])}'>
                  <input name=price value='{int(r['price'])}' type=number min=0>
                  <input name=role_id value='{int(r['role_id'] or 0)}' type=number min=0>
                  <label><input type=checkbox name=enabled {'checked' if int(r['enabled']) else ''}> On</label>
                  <button>Update</button>
                </form>
              </td>
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
          <table><tr><th>ID</th><th>Key</th><th>Name</th><th>Price</th><th>Role ID</th><th>Enabled</th><th>Edit</th><th>Toggle</th></tr>{item_trs}</table>
        </div>

        <div class='card'>
          <h3>Purchases</h3>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(user_filter)}'>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/shop?guild_id={g}'>Reset</a>
          </form>
          <br>
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

            if action == "reopen":
                giveaway_id = int(request.form.get("giveaway_id") or 0)
                conn = db()
                cur = conn.cursor()
                cur.execute("UPDATE giveaways SET status='open', ended_at=0 WHERE guild_id=? AND id=?", (g, giveaway_id))
                conn.commit()
                conn.close()
                return redirect(f"/dashboard/giveaways?guild_id={g}")

            if action == "pick":
                giveaway_id = int(request.form.get("giveaway_id") or 0)
                giveaway_service.pick_winners(g, giveaway_id)
                return redirect(f"/dashboard/giveaways?guild_id={g}&view_id={giveaway_id}")

            if action == "add_entry":
                giveaway_id = int(request.form.get("giveaway_id") or 0)
                user_id = int(request.form.get("user_id") or 0)
                user_name = request.form.get("user_name", "").strip() or str(user_id)
                giveaway_service.join(g, giveaway_id, user_id, user_name)
                return redirect(f"/dashboard/giveaways?guild_id={g}&view_id={giveaway_id}")

        view_id = request.args.get("view_id", "").strip()
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
              <td><a href='/dashboard/giveaways?guild_id={g}&view_id={r['id']}'>Entries</a></td>
              <td>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=giveaway_id value='{r['id']}'>
                  <button name=action value='pick'>Pick</button>
                  <button name=action value='close' style='background:#334155'>Close</button>
                  <button name=action value='reopen' style='background:#16a34a'>Reopen</button>
                </form>
              </td>
            </tr>"""

        entries_card = ""
        if view_id.isdigit():
            entries = giveaway_service.entries(g, int(view_id))
            entry_trs = "".join(
                f"<tr><td>{e['id']}</td><td><code>{e['user_id']}</code></td><td>{esc(e['user_name'])}</td></tr>"
                for e in entries
            )
            entries_card = f"""
            <div class='card'>
              <h3>Entries for Giveaway #{view_id}</h3>
              <form method=post>
                <input type=hidden name=guild_id value='{g}'>
                <input type=hidden name=action value='add_entry'>
                <input type=hidden name=giveaway_id value='{view_id}'>
                <input name=user_id placeholder='User ID' required>
                <input name=user_name placeholder='Name optional'>
                <button>Add Entry</button>
              </form>
              <br>
              <table><tr><th>ID</th><th>User ID</th><th>Name</th></tr>{entry_trs}</table>
            </div>
            """

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

        {entries_card}

        <div class='card'>
          <h3>Giveaways</h3>
          <table><tr><th>ID</th><th>Prize</th><th>Winners</th><th>Entries</th><th>Status</th><th>Winner IDs</th><th>Entries</th><th>Action</th></tr>{giveaway_trs}</table>
        </div>
        """
        return page("Giveaways", body, g)

    @app.route("/dashboard/user", methods=["GET", "POST"])
    def user_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                uid_int = int(request.form.get("user_id") or 0)
            except Exception:
                uid_int = 0

            try:
                amount = int(str(request.form.get("amount") or "0").replace(",", ""))
            except Exception:
                amount = 0

            reason = request.form.get("reason", "").strip() or f"Dashboard user action {action}"

            if uid_int and action in {"give", "take", "set"}:
                if action == "give" and amount > 0:
                    economy_service.credit(g, uid_int, amount, "dashboard_user_give", user_name=str(uid_int), actor_id=actor_id, actor_name=actor_name, reason=reason)
                elif action == "take" and amount > 0:
                    economy_service.debit(g, uid_int, amount, "dashboard_user_take", user_name=str(uid_int), actor_id=actor_id, actor_name=actor_name, reason=reason)
                elif action == "set" and amount >= 0:
                    economy_service.set_balance(g, uid_int, amount, "dashboard_user_set_balance", user_name=str(uid_int), actor_id=actor_id, actor_name=actor_name, reason=reason)

                log_event(g, f"dashboard_user_{action}", uid_int, str(uid_int), 0, "", f"Dashboard user {action}", f"Actor={actor_id}, Amount={amount}, Reason={reason}")

            return redirect(f"/dashboard/user?guild_id={g}&user_id={uid_int}")

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
            f"<tr><td>{r['tx_id'][:10]}</td><td>{int(r['amount']):,}</td><td>{int(r['balance_before']):,}</td><td>{int(r['balance_after']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['reason'])}</td></tr>"
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

        <div class='card'>
          <h3>User Money Control</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=user_id value='{uid}'>
            <input name=amount type=number min=0 placeholder='Amount'>
            <input name=reason placeholder='Reason' style='min-width:260px'>
            <button name=action value='give'>Give</button>
            <button name=action value='take' style='background:#dc2626'>Take</button>
            <button name=action value='set' style='background:#334155'>Set Balance</button>
          </form>
        </div>

        <div class='card'><h3>Money History</h3><table><tr><th>TX</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Reason</th></tr>{ledger_trs}</table></div>
        <div class='card'><h3>Warnings</h3><table><tr><th>ID</th><th>Reason</th><th>Status</th><th>By</th></tr>{warn_trs}</table></div>
        <div class='card'><h3>Properties</h3><table><tr><th>ID</th><th>Name</th><th>Level</th><th>Rent</th></tr>{prop_trs}</table></div>
        """
        return page("User Lookup", body, g)

    @app.route("/dashboard/setup")
    def setup_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        guild_obj = None
        try:
            for bg in bot.guilds:
                if int(bg.id) == int(g):
                    guild_obj = bg
                    break
        except Exception:
            guild_obj = None

        if not guild_obj:
            return page("Setup Status", server_pill_html(g, bot) + "<div class='card'><h3 class='bad'>Bot is not connected to this guild.</h3></div>", g)

        s = system_status(guild_obj)
        mem = s["memory"]
        logs = s["logs"]
        gs = s["guild_settings"]
        perms = s["permissions"]

        def yn(v):
            return "✅" if v else "❌"

        rows = [
            ("Persistent memory path", yn(mem["persistent_path"]), f"<code>{esc(mem['db_file'])}</code>"),
            ("Database size", "ℹ️", f"<code>{esc(mem['db_size_text'])}</code>"),
            ("Organized log rooms", yn(logs["mapped"] == logs["total"]), f"<code>{logs['mapped']}/{logs['total']}</code>"),
            ("Commands channel", yn(bool(gs.get("commands_channel_id"))), f"<code>{esc(gs.get('commands_channel_id') or 0)}</code>"),
            ("Gambling channel", yn(bool(gs.get("gambling_channel_id"))), f"<code>{esc(gs.get('gambling_channel_id') or 0)}</code>"),
            ("View Audit Log", yn(perms.get("view_audit_log")), ""),
            ("Manage Channels", yn(perms.get("manage_channels")), ""),
            ("Manage Messages", yn(perms.get("manage_messages")), ""),
            ("Embed Links", yn(perms.get("embed_links")), ""),
        ]

        trs = "".join(f"<tr><td>{name}</td><td>{status}</td><td>{detail}</td></tr>" for name, status, detail in rows)

        log_map = all_log_channels(g)
        log_trs = ""
        for key, (name, topic) in LOG_CHANNELS.items():
            cid = int(log_map.get(key) or 0)
            log_trs += f"<tr><td><code>{esc(key)}</code></td><td>{esc(name)}</td><td>{f'<#{cid}>' if cid else '<span class=bad>Not set</span>'}</td></tr>"

        body = server_pill_html(g, bot)
        body += f"""
        <div class='card'>
          <h3>Setup Checklist</h3>
          <table><tr><th>Check</th><th>Status</th><th>Details</th></tr>{trs}</table>
          <br>
          <p class='muted'>From Discord run: <code>!تجهيز_اللوقات</code>, <code>!فحص_الصلاحيات</code>, <code>!اختبار_اللوقات</code></p>
        </div>
        <div class='card'>
          <h3>Log Rooms</h3>
          <table><tr><th>Key</th><th>Name</th><th>Channel</th></tr>{log_trs}</table>
        </div>
        """
        return page("Setup Status", body, g)


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
          <p>Organized Log Rooms: <code>{sum(1 for x in all_log_channels(g).values() if int(x or 0)) if g else 0}/{len(LOG_CHANNELS)}</code></p>
          <p>DB: <code>{esc(DB_FILE)}</code></p>
          <p>Discord Login: ✅</p>
          <p>Redirect URI: <code>{esc(redirect_uri())}</code></p>
          <p>Base URL: <code>{esc(cfg['base_url'])}</code></p>
        </div>
        """
        return page("Health", body, g)

    return app
