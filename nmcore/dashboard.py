import os, time, html, json, urllib.parse, urllib.request, urllib.error, asyncio
from flask import Flask, request, redirect, session
from nmcore.config import DASHBOARD_SECRET_KEY, DB_FILE
from nmcore.db import db, init_db
from nmcore.ui import page
from nmcore.services.settings import ensure_guild, get_coin_name, set_coin_name, all_toggles, set_system_enabled, get_guild_settings, update_channel, set_dev_mode_enabled, is_dev_mode_enabled
from nmcore.services import real_estate
from nmcore.services import economy as economy_service
from nmcore.services import antiraid
from nmcore.services import security
from nmcore.services import full_check
from nmcore.services import reports
from nmcore.services import post_rewards
from nmcore.services import boost_rewards
from nmcore.services import game_roles as game_roles_service
from nmcore.services import casino as casino_service
from nmcore.services import profile as profile_service
from nmcore.services import shop as shop_service
from nmcore.services import companies as companies_service
from nmcore.services import giveaways as giveaway_service
from nmcore.services.log_channels import LOG_CHANNELS, get_log_channel, set_log_channel, all_log_channels
from nmcore.services.diagnostics import system_status
from nmcore.services.warnings import summary as warn_summary
from nmcore.services.protection import get_settings as prot_get, update_settings as prot_update, get_default_bad_words, matched_bad_word, contains_bad, has_link, check_message
from nmcore.services.activity import log_event, record

DISCORD_API = "https://discord.com/api/v10"
ADMINISTRATOR_BIT = 0x8
BOT_OWNER_ID = 881722045031915521


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



def is_bot_owner_dashboard():
    try:
        u = session.get("discord_user") or {}
        return int(u.get("id") or 0) == int(BOT_OWNER_ID)
    except Exception:
        return False


def bot_guilds_for_owner(bot=None):
    out = []
    try:
        for guild in getattr(bot, "guilds", []) or []:
            icon = ""
            try:
                icon = guild.icon.url if getattr(guild, "icon", None) else ""
            except Exception:
                icon = ""

            out.append({
                "id": str(guild.id),
                "name": guild.name,
                "icon": icon,
                "owner": True,
                "bot_owner_access": True,
                "member_count": int(getattr(guild, "member_count", 0) or 0),
            })
    except Exception:
        pass

    return sorted(out, key=lambda x: str(x.get("name") or "").lower())


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


def discord_user_avatar(user, size=128):
    try:
        uid = str(user.get("id") or "")
        avatar = user.get("avatar")
        if uid and avatar:
            ext = "gif" if str(avatar).startswith("a_") else "png"
            return f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.{ext}?size={int(size)}"
    except Exception:
        pass
    return "https://cdn.discordapp.com/embed/avatars/0.png"


def discord_guild_icon(g, size=128):
    try:
        # Bot owner synthetic guild entries already include full icon URL.
        direct = g.get("icon_url") or g.get("icon")
        if isinstance(direct, str) and direct.startswith("http"):
            return direct

        gid = str(g.get("id") or "")
        icon = g.get("icon")
        if gid and icon:
            ext = "gif" if str(icon).startswith("a_") else "png"
            return f"https://cdn.discordapp.com/icons/{gid}/{icon}.{ext}?size={int(size)}"
    except Exception:
        pass
    return ""


def bot_guild_icon(bot=None, guild_id=0):
    try:
        gid_int = int(guild_id or 0)
        if bot and getattr(bot, "guilds", None):
            for g in bot.guilds:
                if int(g.id) == gid_int and getattr(g, "icon", None):
                    return g.icon.url
    except Exception:
        pass

    for g in session.get("discord_guilds", []):
        try:
            if int(g.get("id", 0)) == int(guild_id or 0):
                return discord_guild_icon(g)
        except Exception:
            pass

    return ""


def member_info(bot=None, guild_id=0, user_id=0):
    """
    Best-effort display info for dashboard tables:
    name + avatar if member is cached in the bot guild.
    """
    uid = int(user_id or 0)
    data = {
        "id": uid,
        "name": str(uid) if uid else "-",
        "avatar": "https://cdn.discordapp.com/embed/avatars/0.png",
        "mention": f"<@{uid}>" if uid else "-",
    }

    try:
        gid_int = int(guild_id or 0)
        if bot and getattr(bot, "guilds", None):
            guild = None
            for g in bot.guilds:
                if int(g.id) == gid_int:
                    guild = g
                    break

            if guild:
                m = guild.get_member(uid)
                if m:
                    data["name"] = m.display_name
                    data["avatar"] = m.display_avatar.url
    except Exception:
        pass

    return data


def user_chip(bot, guild_id, user_id, name_hint=""):
    uid = int(user_id or 0)
    if not uid:
        return "<span class='muted'>System</span>"

    info = member_info(bot, guild_id, uid)
    name = info["name"]

    if name == str(uid) and name_hint:
        name = str(name_hint)

    return f"""
    <div class='userline'>
      <img class='avatar' src='{esc(info["avatar"])}'>
      <div style='min-width:0'>
        <b style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block;max-width:210px'>{esc(name)}</b>
        <a href='/dashboard/user?guild_id={int(guild_id)}&user_id={uid}'><code>{uid}</code></a>
      </div>
    </div>
    """


def status_badge(text):
    val = str(text or "").lower()
    cls = "ok" if val in {"active", "ok", "win", "enabled"} else "warn" if val in {"cleared", "draw", "pending"} else "bad" if val in {"lose", "disabled", "bad"} else "info"
    return f"<span class='pill {cls}'>{esc(text)}</span>"


def refresh_session_manageable_guilds(bot=None, force=False):
    """
    Refresh Discord guild permissions so old sessions cannot keep dashboard access.

    Special rule:
    BOT_OWNER_ID can see and control every server where the bot is installed,
    even if his Discord account is not Administrator in that guild.
    """
    token = session.get("discord_access_token")
    if not token:
        return

    now = int(time.time())
    last = int(session.get("guilds_refreshed_at") or 0)

    if not force and now - last < 60:
        return

    try:
        if is_bot_owner_dashboard():
            manageable = bot_guilds_for_owner(bot)
            session["discord_guilds"] = manageable
            session["guilds_refreshed_at"] = now
            session["bot_owner_mode"] = True

            current = session.get("guild_id")
            allowed = {int(g["id"]) for g in manageable if str(g.get("id", "")).isdigit()}

            if current and int(current) not in allowed:
                session.pop("guild_id", None)

            session.modified = True
            return

        session["bot_owner_mode"] = False
        guilds = discord_api_get("/users/@me/guilds", token)
        manageable = filter_manageable_to_bot_guilds([g for g in guilds if is_admin_guild(g)], bot)
        session["discord_guilds"] = manageable
        session["guilds_refreshed_at"] = now

        current = session.get("guild_id")
        allowed = {int(g["id"]) for g in manageable if str(g.get("id", "")).isdigit()}

        if current and int(current) not in allowed:
            session.pop("guild_id", None)

        session.modified = True
    except Exception:
        pass


def has_dashboard_access(bot=None, guild_id=0):
    try:
        gid_int = int(guild_id or 0)
    except Exception:
        return False

    if not gid_int:
        return False

    # Bot owner can access every guild where the bot is installed.
    if is_bot_owner_dashboard():
        ids = bot_guild_ids(bot)
        return bool(gid_int in ids) if ids else True

    allowed = {
        int(g["id"])
        for g in session.get("discord_guilds", [])
        if str(g.get("id", "")).isdigit()
    }

    if gid_int not in allowed:
        return False

    ids = bot_guild_ids(bot)
    if ids and gid_int not in ids:
        return False

    return True


def dashboard_access_denied_html():
    denied = session.pop("access_denied_gid", 0)
    if not denied:
        return ""
    return f"""
    <div class='card'>
      <h3 class='bad'>Dashboard access denied</h3>
      <p>You cannot open this server dashboard.</p>
      <p class='muted'>Reason: the bot is not in this guild, or you do not have permission. Bot owner can access all bot guilds.</p>
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
    refresh_session_manageable_guilds(bot)

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

    if selected and selected in allowed and has_dashboard_access(bot, selected):
        session["guild_id"] = selected
        return selected

    if selected:
        session["access_denied_gid"] = selected
        session.pop("guild_id", None)
        return 0

    for candidate in sorted(allowed):
        if has_dashboard_access(bot, candidate):
            session["guild_id"] = candidate
            return candidate

    session.pop("guild_id", None)
    return 0


def guild_selector_html(active_gid):
    guilds = session.get("discord_guilds", [])

    if not guilds:
        return """
        <div class='card'>
          <h3 class='bad'>No accessible servers</h3>
          <p>You need Owner or Administrator permission, and the bot must be inside that server.</p>
          <a class='btn' href='/logout'>Logout</a>
        </div>
        """

    cards = ""
    for g in guilds:
        if not str(g.get("id", "")).isdigit():
            continue

        gid_raw = int(g["id"])
        icon = discord_guild_icon(g)
        icon_html = f"<img class='avatar-lg' src='{esc(icon)}'>" if icon else "<div class='avatar-lg' style='display:grid;place-items:center;font-size:28px'>🛡️</div>"
        owner_badge = "Bot Owner" if g.get("bot_owner_access") else ("Owner" if g.get("owner") else "Administrator")

        cards += f"""
        <a class='server-card' href='/dashboard?guild_id={gid_raw}'>
          {icon_html}
          <div style='min-width:0'>
            <div style='font-size:18px;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{esc(g.get('name','Unknown'))}</div>
            <div class='muted'>{owner_badge} • <code>{gid_raw}</code></div>
            <div style='margin-top:8px'><span class='pill'>Open Dashboard</span></div>
          </div>
        </a>
        """

    return f"""
    <div class='card'>
      <h3>Servers you can manage</h3>
      <p class='muted'>Bot Owner mode: you can see every server where the bot is installed. Normal admins only see servers they administer.</p>
      <div class='server-grid'>{cards}</div>
      <br>
      <a class='btn' style='background:#334155' href='/logout'>Logout</a>
    </div>
    """

def server_pill_html(active_gid, bot=None):
    if not active_gid:
        return ""

    name = bot_guild_name(bot, active_gid)
    icon = bot_guild_icon(bot, active_gid)
    icon_html = f"<img class='avatar' src='{esc(icon)}'>" if icon else "<div class='avatar' style='display:grid;place-items:center'>🛡️</div>"

    return f"""
    <div class='card' style='display:flex;justify-content:space-between;align-items:center;gap:12px;margin:-8px 0 18px;flex-wrap:wrap'>
      <div class='userline'>
        {icon_html}
        <div>
          <div class='muted'>Current Server</div>
          <b>{esc(name)}</b> <code>{esc(active_gid)}</code>
        </div>
      </div>
      <div style='display:flex;gap:8px;flex-wrap:wrap'>
        <a class='btn' style='background:#334155;box-shadow:none' href='/dashboard'>Switch Server</a>
        <a class='btn' style='background:#334155;box-shadow:none' href='/dashboard/full-check?guild_id={int(active_gid)}'>Full Check</a>
      </div>
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
        user_avatar = discord_user_avatar(user)
        user_name = user.get('global_name') or user.get('username') or 'Dashboard User'

        body = f"""
        <div class='card' style='display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap'>
          <div class='userline'>
            <img class='avatar-lg' src='{esc(user_avatar)}'>
            <div>
              <div class='muted'>Logged in as</div>
              <div style='font-size:24px;font-weight:950'>{esc(user_name)}</div>
              <code>{esc(user.get('id'))}</code>
            </div>
          </div>
          <div>
            <a class='btn' href='/dashboard/money-tracker?guild_id={g}'>Open Money Tracker</a>
            <a class='btn' style='background:#334155' href='/dashboard/security?guild_id={g}'>Security</a>
          </div>
        </div>
        """ + guild_selector_html(g) + f"""

        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Guild</div><div class='stat'>{esc(g_name)}</div><div class='muted'><code>{g}</code></div></div>
          <div class='card'><div class='muted'>Coin</div><div class='stat'>{esc(get_coin_name(g))}</div></div>
          <div class='card'><div class='muted'>Economy Users</div><div class='stat'>{int(eco['c'] or 0):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Total Money</div><div class='stat'>{int(eco['total'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Ledger Rows</div><div class='stat'>{int(led['c'] or 0):,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Warnings</div><div class='stat'>{active:,}</div></div>
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
        q_text = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        limit_raw = request.args.get("limit", "300").strip()

        try:
            limit = max(25, min(int(limit_raw or 300), 1500))
        except Exception:
            limit = 300

        def safe_int(value, default=0):
            try:
                return int(value or default)
            except Exception:
                return default

        def tx_time(ts):
            try:
                return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts or 0)))
            except Exception:
                return "-"

        def money_category(src):
            s = str(src or "").lower()

            if s.startswith("dashboard"):
                return "Dashboard"

            if (
                s.startswith("casino")
                or s in {"blackjack", "bj", "gamble"}
                or "blackjack" in s
                or "_bj" in s
                or "bj_" in s
            ):
                return "Casino"

            if s.startswith("company"):
                return "Companies"

            if (
                s.startswith("real_estate")
                or "real_estate" in s
                or "rent" in s
                or "property" in s
            ):
                return "Real Estate"

            if "salary" in s or "daily" in s:
                return "Salary"

            if "boost" in s or "post" in s or "reward" in s:
                return "Rewards"

            if "transfer" in s:
                return "Transfers"

            if "admin" in s:
                return "Admin"

            return "Other"

        def amount_html(amount):
            amount = safe_int(amount)
            if amount >= 0:
                return f"<b style='color:#22c55e'>+{amount:,}</b>"
            return f"<b style='color:#ef4444'>{amount:,}</b>"

        def ledger_table(rows_list, show_user=True):
            head_user = "<th>User</th>" if show_user else ""
            out = ""

            for r in rows_list:
                user_cell = ""
                if show_user:
                    user_cell = f"<td>{user_chip(bot, g, r['user_id'], r['user_name'])}</td>"

                out += f"""
                <tr>
                    <td>
                        <code>{esc(str(r["tx_id"])[:10])}</code>
                        <br>
                        <span class='muted'>{tx_time(r["created_at"])}</span>
                    </td>
                    {user_cell}
                    <td>{amount_html(r["amount"])}</td>
                    <td>{safe_int(r["balance_before"]):,}</td>
                    <td>{safe_int(r["balance_after"]):,}</td>
                    <td>
                        {esc(money_category(r["source_type"]))}
                        <br>
                        <code>{esc(r["source_type"])}</code>
                    </td>
                    <td>{esc(r["source_label"])}</td>
                    <td>{esc(r["reason"])}</td>
                    <td>{user_chip(bot, g, r["actor_id"], r["actor_name"]) if safe_int(r["actor_id"]) else "-"}</td>
                    <td>
                        <code>{esc(r["reference_type"])}</code>
                        <br>
                        {esc(r["reference_id"])}
                    </td>
                </tr>
                """

            if not out:
                colspan = 10 if show_user else 9
                out = f"<tr><td colspan='{colspan}'>No transactions found.</td></tr>"

            return f"""
            <table>
                <tr>
                    <th>TX / Time</th>
                    {head_user}
                    <th>Amount</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>Category / Source</th>
                    <th>Label</th>
                    <th>Reason</th>
                    <th>Actor</th>
                    <th>Reference</th>
                </tr>
                {out}
            </table>
            """

        def totals_cards(title, totals):
            return f"""
            <div class='card'>
                <h3>{esc(title)}</h3>
                <div class='grid'>
                    <div class='card kpi-info'>
                        <div class='muted'>Rows</div>
                        <div class='stat'>{safe_int(totals["rows"]):,}</div>
                    </div>
                    <div class='card kpi-good'>
                        <div class='muted'>Money In</div>
                        <div class='stat'>{safe_int(totals["money_in"]):,}</div>
                    </div>
                    <div class='card kpi-bad'>
                        <div class='muted'>Money Out</div>
                        <div class='stat'>{safe_int(totals["money_out"]):,}</div>
                    </div>
                    <div class='card kpi-warn'>
                        <div class='muted'>Net</div>
                        <div class='stat'>{safe_int(totals["net"]):,}</div>
                    </div>
                </div>
            </div>
            """

        where = "WHERE guild_id=?"
        params = [g]

        if uid.isdigit():
            where += " AND user_id=?"
            params.append(int(uid))

        if actor_id.isdigit():
            where += " AND actor_id=?"
            params.append(int(actor_id))

        if source:
            where += " AND source_type LIKE ?"
            params.append(f"{source}%")

        if category:
            if category == "Dashboard":
                where += " AND source_type LIKE 'dashboard%'"

            elif category == "Casino":
                where += " AND (source_type LIKE 'casino%' OR source_type LIKE '%blackjack%' OR source_type LIKE '%bj%')"

            elif category == "Companies":
                where += " AND source_type LIKE 'company%'"

            elif category == "Real Estate":
                where += " AND (source_type LIKE 'real_estate%' OR source_type LIKE 'property%' OR source_type LIKE '%rent%')"

            elif category == "Salary":
                where += " AND (source_type LIKE '%salary%' OR source_type LIKE '%daily%')"

            elif category == "Rewards":
                where += " AND (source_type LIKE '%boost%' OR source_type LIKE '%post%' OR source_type LIKE '%reward%')"

            elif category == "Transfers":
                where += " AND source_type LIKE '%transfer%'"

            elif category == "Admin":
                where += " AND source_type LIKE '%admin%'"

        if direction == "in":
            where += " AND amount > 0"

        elif direction == "out":
            where += " AND amount < 0"

        if min_amount.lstrip("-").isdigit():
            where += " AND ABS(amount) >= ?"
            params.append(abs(int(min_amount)))

        if max_amount.lstrip("-").isdigit():
            where += " AND ABS(amount) <= ?"
            params.append(abs(int(max_amount)))

        if q_text:
            where += """
            AND (
                source_type LIKE ?
                OR source_label LIKE ?
                OR reason LIKE ?
                OR user_name LIKE ?
                OR actor_name LIKE ?
                OR tx_id LIKE ?
                OR reference_type LIKE ?
                OR reference_id LIKE ?
            )
            """
            like = f"%{q_text}%"
            params += [like, like, like, like, like, like, like, like]

        conn = db()
        cur = conn.cursor()

        cur.execute(f"""
            SELECT *
            FROM money_ledger
            {where}
            ORDER BY id DESC
            LIMIT ?
        """, params + [limit])
        rows = cur.fetchall()

        cur.execute(f"""
            SELECT
                COUNT(*) rows,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                COALESCE(SUM(amount), 0) net
            FROM money_ledger
            {where}
        """, params)
        filtered_totals = cur.fetchone()

        cur.execute("""
            SELECT
                COUNT(*) rows,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                COALESCE(SUM(amount), 0) net
            FROM money_ledger
            WHERE guild_id=?
        """, (g,))
        totals = cur.fetchone()

        cur.execute("""
            SELECT
                source_type,
                COUNT(*) rows,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                COALESCE(SUM(amount), 0) net
            FROM money_ledger
            WHERE guild_id=?
            GROUP BY source_type
            ORDER BY rows DESC
            LIMIT 100
        """, (g,))
        source_rows = cur.fetchall()

        cat = {}
        for r in source_rows:
            c_name = money_category(r["source_type"])
            cat.setdefault(c_name, {"rows": 0, "money_in": 0, "money_out": 0, "net": 0})
            cat[c_name]["rows"] += safe_int(r["rows"])
            cat[c_name]["money_in"] += safe_int(r["money_in"])
            cat[c_name]["money_out"] += safe_int(r["money_out"])
            cat[c_name]["net"] += safe_int(r["net"])

        selected_source_stats = None
        selected_source_users = []
        selected_source_recent = []
        selected_source_actors = []

        if source:
            cur.execute("""
                SELECT
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                    COALESCE(SUM(amount), 0) net
                FROM money_ledger
                WHERE guild_id=? AND source_type LIKE ?
            """, (g, f"{source}%"))
            selected_source_stats = cur.fetchone()

            cur.execute("""
                SELECT
                    user_id,
                    user_name,
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                    COALESCE(SUM(amount), 0) net,
                    COALESCE(SUM(ABS(amount)), 0) volume,
                    COALESCE(MAX(created_at), 0) last_tx
                FROM money_ledger
                WHERE guild_id=? AND source_type LIKE ?
                GROUP BY user_id, user_name
                ORDER BY volume DESC
                LIMIT 80
            """, (g, f"{source}%"))
            selected_source_users = cur.fetchall()

            cur.execute("""
                SELECT
                    actor_id,
                    actor_name,
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) gave,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) took,
                    COALESCE(SUM(ABS(amount)), 0) volume
                FROM money_ledger
                WHERE guild_id=? AND source_type LIKE ? AND actor_id != 0
                GROUP BY actor_id, actor_name
                ORDER BY volume DESC
                LIMIT 30
            """, (g, f"{source}%"))
            selected_source_actors = cur.fetchall()

            cur.execute("""
                SELECT *
                FROM money_ledger
                WHERE guild_id=? AND source_type LIKE ?
                ORDER BY id DESC
                LIMIT 200
            """, (g, f"{source}%"))
            selected_source_recent = cur.fetchall()

        profile = None
        profile_sources = []
        profile_recent = []
        profile_balance = 0
        profile_actors = []
        profile_biggest_in = []
        profile_biggest_out = []

        if uid.isdigit():
            user_id_int = int(uid)

            cur.execute(
                "SELECT balance FROM balances WHERE guild_id=? AND user_id=?",
                (g, user_id_int)
            )
            balrow = cur.fetchone()
            profile_balance = safe_int(balrow["balance"]) if balrow else 0

            cur.execute("""
                SELECT
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                    COALESCE(SUM(amount), 0) net,
                    COALESCE(MAX(created_at), 0) last_tx
                FROM money_ledger
                WHERE guild_id=? AND user_id=?
            """, (g, user_id_int))
            profile = cur.fetchone()

            cur.execute("""
                SELECT
                    source_type,
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) money_in,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) money_out,
                    COALESCE(SUM(amount), 0) net,
                    COALESCE(MAX(created_at), 0) last_tx
                FROM money_ledger
                WHERE guild_id=? AND user_id=?
                GROUP BY source_type
                ORDER BY rows DESC
                LIMIT 80
            """, (g, user_id_int))
            profile_sources = cur.fetchall()

            cur.execute("""
                SELECT
                    actor_id,
                    actor_name,
                    COUNT(*) rows,
                    COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) gave,
                    COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) took,
                    COALESCE(SUM(ABS(amount)), 0) volume
                FROM money_ledger
                WHERE guild_id=? AND user_id=? AND actor_id != 0
                GROUP BY actor_id, actor_name
                ORDER BY volume DESC
                LIMIT 30
            """, (g, user_id_int))
            profile_actors = cur.fetchall()

            cur.execute("""
                SELECT *
                FROM money_ledger
                WHERE guild_id=? AND user_id=? AND amount > 0
                ORDER BY amount DESC
                LIMIT 15
            """, (g, user_id_int))
            profile_biggest_in = cur.fetchall()

            cur.execute("""
                SELECT *
                FROM money_ledger
                WHERE guild_id=? AND user_id=? AND amount < 0
                ORDER BY amount ASC
                LIMIT 15
            """, (g, user_id_int))
            profile_biggest_out = cur.fetchall()

            cur.execute("""
                SELECT *
                FROM money_ledger
                WHERE guild_id=? AND user_id=?
                ORDER BY id DESC
                LIMIT 150
            """, (g, user_id_int))
            profile_recent = cur.fetchall()

        cur.execute("""
            SELECT
                user_id,
                COALESCE(SUM(amount), 0) net,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) received,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) spent,
                COUNT(*) rows
            FROM money_ledger
            WHERE guild_id=?
            GROUP BY user_id
            ORDER BY received DESC
            LIMIT 15
        """, (g,))
        top_received = cur.fetchall()

        cur.execute("""
            SELECT
                user_id,
                COALESCE(SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END), 0) spent,
                COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) received,
                COALESCE(SUM(amount), 0) net,
                COUNT(*) rows
            FROM money_ledger
            WHERE guild_id=?
            GROUP BY user_id
            ORDER BY spent DESC
            LIMIT 15
        """, (g,))
        top_spent = cur.fetchall()

        cur.execute("""
            SELECT
                actor_id,
                actor_name,
                COUNT(*) rows,
                COALESCE(SUM(ABS(amount)), 0) volume
            FROM money_ledger
            WHERE guild_id=? AND actor_id != 0
            GROUP BY actor_id, actor_name
            ORDER BY volume DESC
            LIMIT 15
        """, (g,))
        top_actors = cur.fetchall()

        conn.close()

        category_buttons = "".join(
            f"<a class='btn' style='margin:4px;background:{'#2563eb' if category == c_name else '#334155'}' href='/dashboard/money-tracker?guild_id={g}&category={urllib.parse.quote(c_name)}'>{esc(c_name)} ({safe_int(v['rows']):,})</a>"
            for c_name, v in sorted(cat.items(), key=lambda kv: kv[1]["rows"], reverse=True)
        )

        chips = "".join(
            f"<a class='btn' style='margin:4px;background:{'#7c3aed' if source == str(r['source_type']) else '#334155'}' href='/dashboard/money-tracker?guild_id={g}&source={urllib.parse.quote(str(r['source_type']))}#selected-source'>{esc(r['source_type'])} ({safe_int(r['rows']):,})</a>"
            for r in source_rows[:80]
        )

        cat_trs = "".join(
            f"<tr><td>{esc(c_name)}</td><td>{safe_int(v['rows']):,}</td><td>{safe_int(v['money_in']):,}</td><td>{safe_int(v['money_out']):,}</td><td>{safe_int(v['net']):,}</td><td><a class='btn' href='/dashboard/money-tracker?guild_id={g}&category={urllib.parse.quote(c_name)}'>Open</a></td></tr>"
            for c_name, v in sorted(cat.items(), key=lambda kv: kv[1]["rows"], reverse=True)
        )

        source_trs = "".join(
            f"<tr><td>{esc(r['source_type'])}</td><td>{esc(money_category(r['source_type']))}</td><td>{safe_int(r['rows']):,}</td><td>{safe_int(r['money_in']):,}</td><td>{safe_int(r['money_out']):,}</td><td>{safe_int(r['net']):,}</td><td><a class='btn' href='/dashboard/money-tracker?guild_id={g}&source={urllib.parse.quote(str(r['source_type']))}#selected-source'>Open</a></td></tr>"
            for r in source_rows
        )

        received_trs = "".join(
            f"<tr><td>{user_chip(bot, g, r['user_id'])}</td><td>{safe_int(r['received']):,}</td><td>{safe_int(r['spent']):,}</td><td>{safe_int(r['net']):,}</td><td>{safe_int(r['rows']):,}</td></tr>"
            for r in top_received
        )

        spent_trs = "".join(
            f"<tr><td>{user_chip(bot, g, r['user_id'])}</td><td>{safe_int(r['spent']):,}</td><td>{safe_int(r['received']):,}</td><td>{safe_int(r['net']):,}</td><td>{safe_int(r['rows']):,}</td></tr>"
            for r in top_spent
        )

        actor_trs = "".join(
            f"<tr><td>{user_chip(bot, g, r['actor_id'], r['actor_name'])}</td><td>{safe_int(r['volume']):,}</td><td>{safe_int(r['rows']):,}</td></tr>"
            for r in top_actors
        )

        form = f"""
        <div class='card'>
          <h3>Advanced Money Search</h3>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <input name=actor_id placeholder='Actor/Admin ID' value='{esc(actor_id)}'>
            <input name=source placeholder='source_type مثل dashboard_give / casino_bet' value='{esc(source)}'>
            <input name=q placeholder='Search reason / label / tx' value='{esc(q_text)}'>
            <select name=category>
              <option value='' {'selected' if category == '' else ''}>All categories</option>
              {''.join(f"<option value='{esc(c)}' {'selected' if category == c else ''}>{esc(c)}</option>" for c in sorted(cat.keys()))}
            </select>
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
          <p class='muted'>تقدر تعرف كم مرة الشخص أخذ من الداشبورد، كم ربح/خسر من الكازينو، كم دخل من الشركات، وكل عملية من أعطاه أو أخذ منه.</p>
        </div>
        """

        body = server_pill_html(g, bot) + form

        body += f"""
        <div class='grid'>
          <div class='card'><div class='muted'>All Ledger Rows</div><div class='stat'>{safe_int(totals['rows']):,}</div></div>
          <div class='card kpi-good'><div class='muted'>All Money In</div><div class='stat'>{safe_int(totals['money_in']):,}</div></div>
          <div class='card kpi-bad'><div class='muted'>All Money Out</div><div class='stat'>{safe_int(totals['money_out']):,}</div></div>
          <div class='card kpi-warn'><div class='muted'>All Net</div><div class='stat'>{safe_int(totals['net']):,}</div></div>
        </div>

        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Filtered Rows</div><div class='stat'>{safe_int(filtered_totals['rows']):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Filtered In</div><div class='stat'>{safe_int(filtered_totals['money_in']):,}</div></div>
          <div class='card kpi-bad'><div class='muted'>Filtered Out</div><div class='stat'>{safe_int(filtered_totals['money_out']):,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Filtered Net</div><div class='stat'>{safe_int(filtered_totals['net']):,}</div></div>
        </div>
        """

        body += f"<div class='card'><h3>Quick Source Filters</h3>{chips}</div>"

        if source and selected_source_stats:
            source_user_rows = "".join(
                f"""
                <tr>
                  <td>{user_chip(bot, g, r['user_id'], r['user_name'])}</td>
                  <td>{safe_int(r['rows']):,}</td>
                  <td>{safe_int(r['money_in']):,}</td>
                  <td>{safe_int(r['money_out']):,}</td>
                  <td>{safe_int(r['net']):,}</td>
                  <td>{tx_time(r['last_tx'])}</td>
                  <td><a class='btn' href='/dashboard/money-tracker?guild_id={g}&user_id={safe_int(r['user_id'])}&source={urllib.parse.quote(source)}#selected-source'>Open User</a></td>
                </tr>
                """
                for r in selected_source_users
            ) or "<tr><td colspan='7'>No users found.</td></tr>"

            source_actor_rows = "".join(
                f"""
                <tr>
                  <td>{user_chip(bot, g, r['actor_id'], r['actor_name'])}</td>
                  <td>{safe_int(r['rows']):,}</td>
                  <td>{safe_int(r['gave']):,}</td>
                  <td>{safe_int(r['took']):,}</td>
                  <td>{safe_int(r['volume']):,}</td>
                </tr>
                """
                for r in selected_source_actors
            ) or "<tr><td colspan='5'>No actor/admin data.</td></tr>"

            body += f"""
            <div id='selected-source' class='card' style='border:1px solid #7c3aed'>
              <h3>🔎 Selected Source: <code>{esc(source)}</code></h3>
              <p class='muted'>هذا ملخص المصدر اللي ضغطت عليه. هنا تشوف من أخذ، من خسر، ومن الأدمن اللي عطى أو أخذ.</p>

              <div class='grid'>
                <div class='card kpi-info'><div class='muted'>Times</div><div class='stat'>{safe_int(selected_source_stats['rows']):,}</div></div>
                <div class='card kpi-good'><div class='muted'>Money In</div><div class='stat'>{safe_int(selected_source_stats['money_in']):,}</div></div>
                <div class='card kpi-bad'><div class='muted'>Money Out</div><div class='stat'>{safe_int(selected_source_stats['money_out']):,}</div></div>
                <div class='card kpi-warn'><div class='muted'>Net</div><div class='stat'>{safe_int(selected_source_stats['net']):,}</div></div>
              </div>

              <h3>Users in this source</h3>
              <table>
                <tr><th>User</th><th>Times</th><th>Money In</th><th>Money Out</th><th>Net</th><th>Last</th><th></th></tr>
                {source_user_rows}
              </table>

              <br>
              <h3>Actors/Admins in this source</h3>
              <table>
                <tr><th>Actor</th><th>Times</th><th>Gave</th><th>Took</th><th>Volume</th></tr>
                {source_actor_rows}
              </table>

              <br>
              <h3>Recent source transactions</h3>
              {ledger_table(selected_source_recent, show_user=True)}
            </div>
            """

        body += f"<div class='card'><h3>Category Filters</h3>{category_buttons}</div>"

        if profile and uid.isdigit():
            info = member_info(bot, g, int(uid))

            profile_source_trs = "".join(
                f"<tr><td>{esc(r['source_type'])}</td><td>{esc(money_category(r['source_type']))}</td><td>{safe_int(r['rows']):,}</td><td>{safe_int(r['money_in']):,}</td><td>{safe_int(r['money_out']):,}</td><td>{safe_int(r['net']):,}</td><td>{tx_time(r['last_tx'])}</td><td><a class='btn' href='/dashboard/money-tracker?guild_id={g}&user_id={int(uid)}&source={urllib.parse.quote(str(r['source_type']))}#selected-source'>Details</a></td></tr>"
                for r in profile_sources
            ) or "<tr><td colspan='8'>No data.</td></tr>"

            profile_actor_trs = "".join(
                f"<tr><td>{user_chip(bot, g, r['actor_id'], r['actor_name'])}</td><td>{safe_int(r['rows']):,}</td><td>{safe_int(r['gave']):,}</td><td>{safe_int(r['took']):,}</td><td>{safe_int(r['volume']):,}</td></tr>"
                for r in profile_actors
            ) or "<tr><td colspan='5'>No actor data.</td></tr>"

            biggest_in_trs = "".join(
                f"<tr><td><code>{r['tx_id'][:10]}</code></td><td>{safe_int(r['amount']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['reason'])}</td><td>{tx_time(r['created_at'])}</td></tr>"
                for r in profile_biggest_in
            ) or "<tr><td colspan='5'>No data.</td></tr>"

            biggest_out_trs = "".join(
                f"<tr><td><code>{r['tx_id'][:10]}</code></td><td>{safe_int(r['amount']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['reason'])}</td><td>{tx_time(r['created_at'])}</td></tr>"
                for r in profile_biggest_out
            ) or "<tr><td colspan='5'>No data.</td></tr>"

            body += f"""
            <div class='card' style='display:flex;justify-content:space-between;gap:18px;align-items:center;flex-wrap:wrap'>
              <div class='userline'>
                <img class='avatar-lg' src='{esc(info["avatar"])}'>
                <div>
                  <div class='muted'>Advanced Money Profile</div>
                  <div style='font-size:25px;font-weight:950'>{esc(info["name"])}</div>
                  <code>{int(uid)}</code>
                </div>
              </div>
              <div>
                <a class='btn' href='/dashboard/user?guild_id={g}&user_id={int(uid)}'>Open Full User Lookup</a>
                <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}&user_id={int(uid)}&category=Dashboard'>Dashboard Money</a>
                <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}&user_id={int(uid)}&category=Casino'>Casino</a>
                <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}&user_id={int(uid)}&category=Companies'>Companies</a>
              </div>
            </div>

            <div class='grid'>
              <div class='card kpi-info'><div class='muted'>Current Balance</div><div class='stat'>{profile_balance:,}</div></div>
              <div class='card kpi-good'><div class='muted'>Total Money In</div><div class='stat'>{safe_int(profile['money_in']):,}</div></div>
              <div class='card kpi-bad'><div class='muted'>Total Money Out</div><div class='stat'>{safe_int(profile['money_out']):,}</div></div>
              <div class='card kpi-warn'><div class='muted'>Net</div><div class='stat'>{safe_int(profile['net']):,}</div></div>
              <div class='card'><div class='muted'>Transactions</div><div class='stat'>{safe_int(profile['rows']):,}</div></div>
            </div>

            <div class='card'>
              <h3>طرق دخول/خروج الفلوس لهذا الشخص</h3>
              <table><tr><th>Source</th><th>Category</th><th>Times</th><th>Money In</th><th>Money Out</th><th>Net</th><th>Last</th><th></th></tr>{profile_source_trs}</table>
            </div>

            <div class='card'>
              <h3>من عطاه أو أخذ منه</h3>
              <table><tr><th>Actor</th><th>Times</th><th>Gave</th><th>Took</th><th>Volume</th></tr>{profile_actor_trs}</table>
            </div>

            <div class='grid'>
              <div class='card'><h3>Biggest Money In</h3><table><tr><th>TX</th><th>Amount</th><th>Source</th><th>Reason</th><th>Time</th></tr>{biggest_in_trs}</table></div>
              <div class='card'><h3>Biggest Money Out</h3><table><tr><th>TX</th><th>Amount</th><th>Source</th><th>Reason</th><th>Time</th></tr>{biggest_out_trs}</table></div>
            </div>

            <div class='card'>
              <h3>كل عمليات هذا الشخص</h3>
              {ledger_table(profile_recent, show_user=False)}
            </div>
            """

        body += f"<div class='card'><h3>Category Summary</h3><table><tr><th>Category</th><th>Times</th><th>Money In</th><th>Money Out</th><th>Net</th><th></th></tr>{cat_trs}</table></div>"
        body += f"<div class='card'><h3>Source Summary</h3><table><tr><th>Source</th><th>Category</th><th>Times</th><th>In</th><th>Out</th><th>Net</th><th></th></tr>{source_trs}</table></div>"
        body += f"<div class='grid'><div class='card'><h3>Top Received</h3><table><tr><th>User</th><th>In</th><th>Out</th><th>Net</th><th>Rows</th></tr>{received_trs}</table></div><div class='card'><h3>Top Spent / Lost</h3><table><tr><th>User</th><th>Spent</th><th>Received</th><th>Net</th><th>Rows</th></tr>{spent_trs}</table></div></div>"
        body += f"<div class='card'><h3>Top Actors / Admins</h3><table><tr><th>Actor</th><th>Volume</th><th>Rows</th></tr>{actor_trs}</table></div>"
        body += f"<div class='card'><h3>Detailed Ledger Rows</h3>{ledger_table(rows, show_user=True)}</div>"

        return page("Advanced Money Tracker", body, g)
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
                            "UPDATE properties SET owner_id=?, owner_name=?, last_rent_claim=? WHERE guild_id=? AND id=?",
                            (owner_id, owner_name[:120], int(time.time()), g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_set_owner", int(prop["owner_id"] or 0), owner_id, actor_id, 0, int(prop["level"]), int(prop["level"]), int(prop["price"]), int(prop["price"]), reason, ""))

                    elif action == "clear_owner":
                        cur.execute(
                            "UPDATE properties SET owner_id=0, owner_name='', last_rent_claim=0 WHERE guild_id=? AND id=?",
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
                log_event(g, "dashboard_add_warning", user_id, user_name, 0, "", "Dashboard added warning", f"Actor={actor_id}, Reason={reason}")
                return redirect(f"/dashboard/warnings?guild_id={g}&user_id={user_id}&status=all")

            if action == "clear_user" and user_id:
                from nmcore.services import warnings as warnsvc
                count = warnsvc.clear_user(g, user_id, actor_id, actor_name, reason)
                log_event(g, "dashboard_clear_warnings", user_id, str(user_id), 0, "", "Dashboard cleared warnings", f"Actor={actor_id}, Count={count}, Reason={reason}")
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
                        log_event(g, "dashboard_clear_warning", int(row["user_id"]), str(row["user_name"]), 0, "", "Dashboard cleared one warning", f"Actor={actor_id}, WarningID={warning_id}, Reason={reason}")

                    conn.close()

                return redirect(f"/dashboard/warnings?guild_id={g}&status=all")

        uid = request.args.get("user_id", "").strip()
        status = request.args.get("status", "active").strip()
        reason_q = request.args.get("q", "").strip()

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

        if reason_q:
            q += " AND reason LIKE ?"
            params.append(f"%{reason_q}%")

        q += " ORDER BY id DESC LIMIT 350"
        cur.execute(q, params)
        rows = cur.fetchall()

        cur.execute("""SELECT
        COUNT(*) total,
        SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active,
        SUM(CASE WHEN status='cleared' THEN 1 ELSE 0 END) cleared
        FROM warnings WHERE guild_id=?""", (g,))
        totals = cur.fetchone()

        cur.execute("""SELECT user_id, user_name,
        COUNT(*) total,
        SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active_count,
        SUM(CASE WHEN status='cleared' THEN 1 ELSE 0 END) cleared_count,
        MAX(id) last_id
        FROM warnings WHERE guild_id=?
        GROUP BY user_id, user_name
        ORDER BY active_count DESC, total DESC
        LIMIT 100""", (g,))
        grouped = cur.fetchall()

        cur.execute("""SELECT moderator_id, moderator_name, COUNT(*) c
        FROM warnings WHERE guild_id=? AND moderator_id != 0
        GROUP BY moderator_id, moderator_name
        ORDER BY c DESC LIMIT 10""", (g,))
        mods = cur.fetchall()

        conn.close()

        grouped_trs = "".join(
            f"""<tr>
              <td>{user_chip(bot, g, r['user_id'], r['user_name'])}</td>
              <td><span class='pill bad'>{int(r['active_count'] or 0):,}</span></td>
              <td>{int(r['cleared_count'] or 0):,}</td>
              <td>{int(r['total'] or 0):,}</td>
              <td><a class='btn' style='background:#334155;box-shadow:none' href='/dashboard/warnings?guild_id={g}&user_id={r['user_id']}&status=all'>Open</a></td>
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
        ) or "<tr><td colspan='6'>No warnings.</td></tr>"

        trs = "".join(
            f"""<tr>
              <td><code>{r['id']}</code></td>
              <td>{user_chip(bot, g, r['user_id'], r['user_name'])}</td>
              <td>{esc(r['reason'])}</td>
              <td>{status_badge(r['status'])}</td>
              <td>{user_chip(bot, g, r['moderator_id'], r['moderator_name'])}</td>
              <td>{esc(r['clear_reason'] or '')}</td>
              <td>
                {f"<form method='post' style='display:inline'><input type=hidden name=guild_id value='{g}'><input type=hidden name=action value='clear_warning'><input type=hidden name=warning_id value='{r['id']}'><input type=hidden name=reason value='Cleared one warning from dashboard'><button style='background:#334155'>Clear One</button></form>" if str(r['status']) == 'active' else ''}
              </td>
            </tr>"""
            for r in rows
        ) or "<tr><td colspan='7'>No records.</td></tr>"

        mod_trs = "".join(
            f"<tr><td>{user_chip(bot,g,r['moderator_id'],r['moderator_name'])}</td><td>{int(r['c']):,}</td></tr>"
            for r in mods
        ) or "<tr><td colspan='2'>No moderators yet.</td></tr>"

        form = f"""
        <div class='card'>
          <h3>Warnings Control</h3>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(uid)}'>
            <input name=q placeholder='Search reason' value='{esc(reason_q)}'>
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

        body = server_pill_html(g, bot)
        body += f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Total Warnings</div><div class='stat'>{int(totals['total'] or 0):,}</div></div>
          <div class='card kpi-bad'><div class='muted'>Active</div><div class='stat'>{int(totals['active'] or 0):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Cleared</div><div class='stat'>{int(totals['cleared'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Users Listed</div><div class='stat'>{len(grouped):,}</div></div>
        </div>
        """
        body += form
        body += f"<div class='grid'><div class='card'><h3>Users Warning Summary</h3><table><tr><th>User</th><th>Active</th><th>Cleared</th><th>Total</th><th>Open</th><th>Action</th></tr>{grouped_trs}</table></div><div class='card'><h3>Top Moderators</h3><table><tr><th>Moderator</th><th>Warnings</th></tr>{mod_trs}</table></div></div>"
        body += f"<div class='card'><h3>Warning Records</h3><table><tr><th>ID</th><th>User</th><th>Reason</th><th>Status</th><th>By</th><th>Clear Reason</th><th>Action</th></tr>{trs}</table></div>"

        return page("Warnings", body, g)

    @app.route("/dashboard/analytics")
    def analytics_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        money = reports.money_summary(g)
        casino = reports.casino_summary(g)
        shop = reports.shop_summary(g)
        pnl = reports.profit_loss_summary(g)
        users = reports.user_finance_summary(g, 12)

        def money_fmt(v):
            return f"{int(v or 0):,}"

        game_rows = "".join(
            f"<tr><td>{esc(r.get('source_label') or 'unknown')}</td><td>{int(r.get('c') or 0):,}</td><td>{int(r.get('took') or 0):,}</td><td>{int(r.get('paid') or 0):,}</td><td>{int(r.get('took') or 0)-int(r.get('paid') or 0):,}</td></tr>"
            for r in casino.get("games", [])
        ) or "<tr><td colspan='5'>No casino data yet.</td></tr>"

        item_rows = "".join(
            f"<tr><td><code>{esc(r.get('item_key') or '')}</code></td><td>{int(r.get('c') or 0):,}</td><td>{int(r.get('total') or 0):,}</td></tr>"
            for r in shop.get("top_items", [])
        ) or "<tr><td colspan='3'>No shop purchases yet.</td></tr>"

        buyer_rows = "".join(
            f"<tr><td>{user_chip(bot,g,r.get('user_id') or 0,r.get('user_name') or '')}</td><td>{int(r.get('c') or 0):,}</td><td>{int(r.get('total') or 0):,}</td></tr>"
            for r in shop.get("top_buyers", [])
        ) or "<tr><td colspan='3'>No buyers yet.</td></tr>"

        spender_rows = "".join(
            f"<tr><td>{user_chip(bot,g,r.get('user_id') or 0)}</td><td>{int(r.get('spent') or 0):,}</td><td>{int(r.get('received') or 0):,}</td><td>{int(r.get('net') or 0):,}</td></tr>"
            for r in users.get("top_spenders", [])
        ) or "<tr><td colspan='4'>No ledger data yet.</td></tr>"

        recent_purchase_rows = "".join(
            f"<tr><td>{r.get('id')}</td><td><a href='/dashboard/user?guild_id={g}&user_id={r.get('user_id')}'><code>{r.get('user_id')}</code></a></td><td>{esc(r.get('item_key') or '')}</td><td>{int(r.get('price') or 0):,}</td><td><code>{esc(str(r.get('money_tx_id') or ''))[:12]}</code></td></tr>"
            for r in shop.get("recent", [])
        ) or "<tr><td colspan='5'>No recent purchases.</td></tr>"

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Total Balances</div><div class='stat'>{money_fmt(money.get('total_balance'))}</div></div>
          <div class='card kpi-good'><div class='muted'>Money In</div><div class='stat'>{money_fmt(money.get('money_in'))}</div></div>
          <div class='card kpi-bad'><div class='muted'>Money Out</div><div class='stat'>{money_fmt(money.get('money_out'))}</div></div>
          <div class='card kpi-warn'><div class='muted'>Ledger Net</div><div class='stat'>{money_fmt(money.get('net'))}</div></div>
        </div>

        <div class='grid'>
          <div class='card kpi-good'><div class='muted'>Tracked Server Profit</div><div class='stat'>{money_fmt(pnl.get('server_profit'))}</div><p class='muted'>Casino house net + shop sales</p></div>
          <div class='card'><div class='muted'>Casino House Net</div><div class='stat'>{money_fmt(pnl.get('casino_house_net'))}</div></div>
          <div class='card'><div class='muted'>Shop Sales</div><div class='stat'>{money_fmt(pnl.get('shop_sales'))}</div></div>
          <div class='card'><div class='muted'>Shop Purchases</div><div class='stat'>{money_fmt(shop.get('purchases'))}</div></div>
        </div>

        <div class='grid'>
          <div class='card'>
            <h3>Casino Profit / Loss by Game</h3>
            <table><tr><th>Game</th><th>Rows</th><th>Took</th><th>Paid</th><th>House Net</th></tr>{game_rows}</table>
          </div>

          <div class='card'>
            <h3>Top Shop Items</h3>
            <table><tr><th>Item</th><th>Purchases</th><th>Total Sales</th></tr>{item_rows}</table>
          </div>
        </div>

        <div class='grid'>
          <div class='card'>
            <h3>Top Spenders</h3>
            <table><tr><th>User</th><th>Spent</th><th>Received</th><th>Net</th></tr>{spender_rows}</table>
          </div>

          <div class='card'>
            <h3>Top Shop Buyers</h3>
            <table><tr><th>User</th><th>Purchases</th><th>Total</th></tr>{buyer_rows}</table>
          </div>
        </div>

        <div class='card'>
          <h3>Recent Purchases</h3>
          <table><tr><th>ID</th><th>User</th><th>Item</th><th>Price</th><th>TX</th></tr>{recent_purchase_rows}</table>
        </div>
        """
        return page("Analytics", body, g)



    @app.route("/dashboard/full-check")
    def full_check_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        guild_obj = None
        for bg in bot.guilds:
            if int(bg.id) == int(g):
                guild_obj = bg
                break

        if not guild_obj:
            return page("Full Check", server_pill_html(g, bot) + "<div class='card'><h3>Bot is not connected to this guild.</h3></div>", g)

        report = full_check.run_full_check(guild_obj)

        check_rows = "".join(
            f"<tr><td>{'✅' if c['ok'] else '❌'}</td><td>{esc(c['category'])}</td><td>{esc(c['name'])}</td><td><code>{esc(c['detail'])}</code></td></tr>"
            for c in report["checks"]
        )

        fail_rows = "".join(
            f"<tr><td>{esc(c['category'])}</td><td>{esc(c['name'])}</td><td><code>{esc(c['detail'])}</code></td></tr>"
            for c in report["failed"]
        ) or "<tr><td colspan='3'>✅ No core issues detected.</td></tr>"

        color_class = "ok" if report["score"] >= 90 else "warn" if report["score"] >= 75 else "bad"

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Score</div><div class='stat {color_class}'>{report['score']}/100</div></div>
          <div class='card'><div class='muted'>Status</div><div class='stat {color_class}'>{esc(report['label'])}</div></div>
          <div class='card'><div class='muted'>Passed</div><div class='stat'>{len(report['passed'])}/{len(report['checks'])}</div></div>
          <div class='card'><div class='muted'>Logs Mapping</div><div class='stat'>{report['logs']['mapped']}/{report['logs']['total']}</div></div>
        </div>

        <div class='card'>
          <h3>Needs Fix</h3>
          <table><tr><th>Category</th><th>Check</th><th>Details</th></tr>{fail_rows}</table>
        </div>

        <div class='card'>
          <h3>Database</h3>
          <p>Path: <code>{esc(report['db']['path'])}</code></p>
          <p>Size: <code>{esc(report['db']['size_text'])}</code></p>
          <p>Persistent /data: <b>{'✅' if report['db']['persistent'] else '❌'}</b></p>
        </div>

        <div class='card'>
          <h3>All Checks</h3>
          <table><tr><th>Status</th><th>Category</th><th>Check</th><th>Details</th></tr>{check_rows}</table>
        </div>
        """
        return page("Full Check", body, g)



    @app.route("/dashboard/commands")
    def commands_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'>
            <h3>Admin Reports</h3>
            <p><code>!تقرير_النظام</code></p>
            <p><code>!تقرير_الاقتصاد</code></p>
            <p><code>!تقرير_الكازينو</code></p>
            <p><code>!تقرير_الحماية</code></p>
            <p><code>!تقرير_الأمان</code></p>
            <p><code>!جاهزية_البوت</code></p>
          </div>

          <div class='card'>
            <h3>Setup / Logs</h3>
            <p><code>!تجهيز_اللوقات</code></p>
            <p><code>!اختبار_اللوقات</code></p>
            <p><code>!فحص_الصلاحيات</code></p>
            <p><code>!حالة_الإعداد</code></p>
            <p><code>!حالة_الحماية</code></p>
          </div>

          <div class='card'>
            <h3>Economy</h3>
            <p><code>!رصيدي</code></p>
            <p><code>!راتب</code></p>
            <p><code>!تحويل @user amount</code></p>
            <p><code>!الغني</code></p>
            <p><code>!اعطاءفلوس @user amount</code></p>
            <p><code>!سحبفلوس @user amount</code></p>
          </div>

          <div class='card'>
            <h3>Casino</h3>
            <p><code>!حظ amount</code></p>
            <p><code>!دبل amount</code></p>
            <p><code>!سلوت amount</code></p>
            <p><code>!وجه amount</code></p>
            <p><code>!بلاكجاك amount</code></p>
          </div>

          <div class='card'>
            <h3>Warnings</h3>
            <p><code>!تحذير @user reason</code></p>
            <p><code>!تحذيرات @user</code></p>
            <p><code>!مسح_تحذير ID</code></p>
            <p><code>!مسح_تحذيرات @user</code></p>
          </div>

          <div class='card'>
            <h3>Other Systems</h3>
            <p><code>!لفلي</code> / <code>!ترتيب</code></p>
            <p><code>!عقارات</code> / <code>!شراء_عقار ID</code> / <code>!ايجار</code></p>
            <p><code>!متجر</code> / <code>!شراء item_key</code> / <code>!صندوق 1000</code></p>
            <p><code>!قيف</code> / <code>!دخول_قيف ID</code></p>
          </div>
        </div>
        """
        return page("Command Center", body, g)



    @app.route("/dashboard/security")
    def security_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        guild_obj = None
        for bg in bot.guilds:
            if int(bg.id) == int(g):
                guild_obj = bg
                break

        if not guild_obj:
            return page("Security", server_pill_html(g, bot) + "<div class='card'><h3>Bot is not connected to this guild.</h3></div>", g)

        report = security.risk_report(guild_obj)
        events = security.recent_security_events(g, 120)

        def ok_bad(v):
            return "✅" if v else "❌"

        perm_rows = "".join(
            f"<tr><td>{esc(v['label'])}</td><td>{ok_bad(v['ok'])}</td></tr>"
            for k, v in report["permissions"].items()
        )

        role_rows = "".join(
            f"<tr><td><code>{r['id']}</code></td><td>{esc(r['name'])}</td><td>{r['members']}</td><td>{'✅' if r['managed'] else '❌'}</td><td>{esc(', '.join(r['permissions']))}</td></tr>"
            for r in report["roles"][:80]
        )

        event_rows = "".join(
            f"<tr><td>{r['id']}</td><td>{esc(r['event_type'])}</td><td><code>{r['user_id']}</code></td><td>{esc(r['user_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td></tr>"
            for r in events
        )

        issues = "".join(f"<li>{esc(x)}</li>" for x in report["issues"]) or "<li>No major issues detected.</li>"

        color_class = "ok" if report["score"] >= 85 else "warn" if report["score"] >= 65 else "bad"

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card'><div class='muted'>Security Score</div><div class='stat {color_class}'>{report['score']}/100</div></div>
          <div class='card'><div class='muted'>Risk Level</div><div class='stat {color_class}'>{esc(report['label'])}</div></div>
          <div class='card'><div class='muted'>Active Warnings</div><div class='stat'>{report['counts']['active_warnings']:,}</div></div>
          <div class='card'><div class='muted'>Anti-Raid Events</div><div class='stat'>{report['counts']['antiraid_events']:,}</div></div>
          <div class='card'><div class='muted'>Protection Events</div><div class='stat'>{report['counts']['protection_events']:,}</div></div>
        </div>

        <div class='card'>
          <h3>Security Issues / Recommendations</h3>
          <ul>{issues}</ul>
          <a class='btn' href='/dashboard/protection?guild_id={g}'>Open Protection Controls</a>
          <a class='btn' style='background:#334155' href='/dashboard/logs?guild_id={g}'>Open Logs</a>
        </div>

        <div class='grid'>
          <div class='card'>
            <h3>Bot Permissions</h3>
            <table><tr><th>Permission</th><th>Status</th></tr>{perm_rows}</table>
          </div>

          <div class='card'>
            <h3>Anti-Raid Settings</h3>
            <p>Enabled: <b>{ok_bad(report['antiraid'].get('enabled'))}</b></p>
            <p>Threshold: <code>{int(report['antiraid'].get('threshold') or 3)} actions / {int(report['antiraid'].get('window') or 60)}s</code></p>
            <p>Punishment: <code>{esc(report['antiraid'].get('punish_action') or 'log_only')}</code></p>
            <p>Trusted Users: <code>{esc(report['antiraid'].get('trusted_users') or '-')}</code></p>
            <p>Trusted Roles: <code>{esc(report['antiraid'].get('trusted_roles') or '-')}</code></p>
          </div>
        </div>

        <div class='card'>
          <h3>Dangerous Roles</h3>
          <p class='muted'>Roles with high-risk permissions. This helps you know which roles should be trusted carefully.</p>
          <table><tr><th>ID</th><th>Name</th><th>Members</th><th>Managed</th><th>Dangerous Permissions</th></tr>{role_rows}</table>
        </div>

        <div class='card'>
          <h3>Recent Security Events</h3>
          <table><tr><th>ID</th><th>Type</th><th>User</th><th>Name</th><th>Title</th><th>Details</th></tr>{event_rows}</table>
        </div>
        """
        return page("Security", body, g)



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
          <h3>Logs Filter</h3>
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
            f"<tr><td><code>{r['id']}</code></td><td>{status_badge(r['event_type'])}</td><td>{user_chip(bot,g,r['user_id'],r['user_name'])}</td><td>{esc(r['channel_name'])}<br><code>{int(r['channel_id'] or 0)}</code></td><td><b>{esc(r['title'])}</b><br><span class='muted'>{esc(r['details'])}</span></td></tr>"
            for r in rows
        ) or "<tr><td colspan='5'>No logs.</td></tr>"

        body = server_pill_html(g, bot)
        body += f"<div class='grid'><div class='card kpi-info'><div class='muted'>Total DB Logs</div><div class='stat'>{total_logs:,}</div></div><div class='card'><div class='muted'>Mapped Log Rooms</div><div class='stat'>{sum(1 for x in log_map.values() if int(x or 0)):,}/{len(LOG_CHANNELS)}</div></div><div class='card kpi-good'><div class='muted'>Auto Refresh</div><div class='stat'>15s</div></div></div>"
        body += f"<div class='card'><h3>Discord Log Rooms Mapping</h3><table><tr><th>Key</th><th>Room Name</th><th>Current</th><th>ID</th></tr>{log_channel_rows}</table><br><a class='btn' href='/dashboard/settings?guild_id={g}'>Edit Mapping</a></div>"
        body += form
        body += f"<div class='card'><h3>Event Types</h3>{chips or '<span class=muted>No logs yet.</span>'}</div>"
        body += f"<div class='card'><h3>Recent Logs</h3><table><tr><th>ID</th><th>Type</th><th>User</th><th>Channel</th><th>Event</th></tr>{trs}</table></div>"
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
            f"<tr><td>{status_badge(r['activity_type'])}</td><td>{int(r['c']):,}</td><td>{int(r['amount'] or 0):,}</td></tr>"
            for r in types
        ) or "<tr><td colspan='3'>No activity.</td></tr>"

        actor_trs = "".join(
            f"<tr><td>{user_chip(bot,g,r['actor_id'],r['actor_name'])}</td><td>{int(r['c']):,}</td><td>{int(r['amount'] or 0):,}</td></tr>"
            for r in actors
        ) or "<tr><td colspan='3'>No actors.</td></tr>"

        trs = "".join(
            f"<tr><td><code>{r['id']}</code></td><td>{status_badge(r['activity_type'])}</td><td>{user_chip(bot,g,r['actor_id'],r['actor_name'])}</td><td><b>{esc(r['title'])}</b><br><span class='muted'>{esc(r['details'])}</span></td><td>{int(r['amount']):,}</td></tr>"
            for r in rows
        ) or "<tr><td colspan='5'>No live activity.</td></tr>"

        body = server_pill_html(g, bot)
        body += f"""
        <div class='card'>
          <h3>Live Activity Filter</h3>
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
          <div class='card kpi-info'><div class='muted'>Live Rows</div><div class='stat'>{int(total['c'] or 0):,}</div></div>
          <div class='card'><div class='muted'>Activity Types</div><div class='stat'>{len(types):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Auto Refresh</div><div class='stat'>8s</div></div>
        </div>
        """
        body += f"<div class='card'><h3>Quick Filters</h3>{chips or '<span class=muted>No live activity yet.</span>'}</div>"
        body += f"<div class='grid'><div class='card'><h3>Activity Summary</h3><table><tr><th>Type</th><th>Rows</th><th>Amount</th></tr>{type_trs}</table></div><div class='card'><h3>Top Actors</h3><table><tr><th>Actor</th><th>Rows</th><th>Amount</th></tr>{actor_trs}</table></div></div>"
        body += f"<div class='card'><h3>Live Feed</h3><table><tr><th>ID</th><th>Type</th><th>Actor</th><th>Event</th><th>Amount</th></tr>{trs}</table></div>"
        return page("Live Activity", body, g)

    @app.route("/dashboard/game-roles", methods=["GET", "POST"])
    def game_roles_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        game_roles_service.seed(g)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "save_game_roles":
                for r in game_roles_service.rows(g):
                    key = r["game_key"]
                    game_roles_service.update_row(
                        g,
                        key,
                        label=request.form.get(f"label_{key}") or r["label"],
                        emoji=request.form.get(f"emoji_{key}") or r["emoji"],
                        aliases=request.form.get(f"aliases_{key}") or r["aliases"],
                        role_id=int(request.form.get(f"role_{key}") or 0),
                        enabled=bool(request.form.get(f"enabled_{key}")),
                        sort_order=int(request.form.get(f"sort_{key}") or r["sort_order"] or 0)
                    )
                return redirect(f"/dashboard/game-roles?guild_id={g}")

        rows = game_roles_service.rows(g)
        trs = ""
        for r in rows:
            role_id = int(r.get("role_id") or 0)
            role_text = f"<@&{role_id}>" if role_id else "<span class='muted'>Auto by name</span>"
            trs += f"""
            <tr>
              <td><input name='sort_{r['game_key']}' value='{int(r['sort_order'] or 0)}' style='width:60px'></td>
              <td><label><input type=checkbox name='enabled_{r['game_key']}' {'checked' if int(r['enabled'] or 0) else ''}> Enabled</label></td>
              <td><input name='emoji_{r['game_key']}' value='{esc(r['emoji'])}' style='width:70px'></td>
              <td><input name='label_{r['game_key']}' value='{esc(r['label'])}'></td>
              <td><input name='role_{r['game_key']}' value='{role_id}' placeholder='Role ID'></td>
              <td>{role_text}</td>
              <td><input name='aliases_{r['game_key']}' value='{esc(r['aliases'])}' style='width:260px'></td>
            </tr>
            """

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <h3>Game Roles Dashboard</h3>
          <p class='muted'>عدّل الألعاب والرتب من هنا بدل ما تكون ثابتة في الكود. بعدها استخدم <code>!رتب_الألعاب</code>.</p>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_game_roles'>
            <table><tr><th>Sort</th><th>Enabled</th><th>Emoji</th><th>Label</th><th>Role ID</th><th>Current</th><th>Aliases</th></tr>{trs}</table>
            <br><button>Save Game Roles</button>
          </form>
        </div>
        """
        return page("Game Roles", body, g)

    @app.route("/dashboard/casino-controls", methods=["GET", "POST"])
    def casino_controls_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            enabled_games = []
            for key in ["luck", "double", "slot", "flip", "blackjack"]:
                if request.form.get(f"game_{key}"):
                    enabled_games.append(key)

            casino_service.update_settings(
                g,
                luck_chance=int(request.form.get("luck_chance") or 42),
                double_chance=int(request.form.get("double_chance") or 38),
                flip_chance=int(request.form.get("flip_chance") or 47),
                max_bet=int(request.form.get("max_bet") or 0),
                enabled_games=",".join(enabled_games)
            )
            return redirect(f"/dashboard/casino-controls?guild_id={g}")

        s = casino_service.get_settings(g)
        enabled = set(str(s.get("enabled_games") or "").split(","))

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <h3>Casino Controls</h3>
          <p class='muted'>تحكم في احتمالات الألعاب والحد الأعلى للرهان بدون تعديل الكود.</p>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            Luck win chance %<br>
            <input name=luck_chance type=number min=0 max=100 value='{int(s.get('luck_chance') or 42)}'><br><br>
            Double win chance %<br>
            <input name=double_chance type=number min=0 max=100 value='{int(s.get('double_chance') or 38)}'><br><br>
            Flip win chance %<br>
            <input name=flip_chance type=number min=0 max=100 value='{int(s.get('flip_chance') or 47)}'><br><br>
            Max bet — 0 means no limit<br>
            <input name=max_bet type=number min=0 value='{int(s.get('max_bet') or 0)}'><br><br>
            <h3>Enabled Games</h3>
            <label><input type=checkbox name=game_luck {'checked' if 'luck' in enabled else ''}> Luck</label><br>
            <label><input type=checkbox name=game_double {'checked' if 'double' in enabled else ''}> Double</label><br>
            <label><input type=checkbox name=game_slot {'checked' if 'slot' in enabled else ''}> Slot</label><br>
            <label><input type=checkbox name=game_flip {'checked' if 'flip' in enabled else ''}> Flip</label><br>
            <label><input type=checkbox name=game_blackjack {'checked' if 'blackjack' in enabled else ''}> Blackjack</label><br><br>
            <button>Save Casino Controls</button>
          </form>
        </div>
        """
        return page("Casino Controls", body, g)

    @app.route("/dashboard/setup-wizard")
    def setup_wizard_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        gs = get_guild_settings(g)
        log_map = all_log_channels(g)
        pr = post_rewards.get_settings(g)
        bs = boost_rewards.get_settings(g)
        cs = casino_service.get_settings(g)
        from nmcore.services.settings import get_lfg_settings
        lfg = get_lfg_settings(g)

        def yes(v):
            return "✅" if v else "❌"

        rows = f"""
        <tr><td>Commands Channel</td><td>{yes(int(gs.get('commands_channel_id') or 0))}</td><td><code>{int(gs.get('commands_channel_id') or 0)}</code></td></tr>
        <tr><td>Gambling Channel</td><td>{yes(int(gs.get('gambling_channel_id') or 0))}</td><td><code>{int(gs.get('gambling_channel_id') or 0)}</code></td></tr>
        <tr><td>LFG Channel</td><td>{yes(int(lfg.get('lfg_channel_id') or 0))}</td><td><code>{int(lfg.get('lfg_channel_id') or 0)}</code></td></tr>
        <tr><td>LFG Category</td><td>{yes(int(lfg.get('lfg_category_id') or 0))}</td><td><code>{int(lfg.get('lfg_category_id') or 0)}</code></td></tr>
        <tr><td>Post Rewards</td><td>{yes(int(pr.get('enabled') or 0))}</td><td>{int(pr.get('amount') or 0):,}</td></tr>
        <tr><td>Boost Rewards</td><td>{yes(int(bs.get('enabled') or 0))}</td><td>{int(bs.get('amount') or 0):,}</td></tr>
        <tr><td>Casino Max Bet</td><td>{'♾️' if not int(cs.get('max_bet') or 0) else '✅'}</td><td>{int(cs.get('max_bet') or 0):,}</td></tr>
        <tr><td>Log Channels</td><td>{sum(1 for x in log_map.values() if int(x or 0))}/{len(LOG_CHANNELS)}</td><td><a href='/dashboard/settings?guild_id={g}'>Edit</a></td></tr>
        """

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <h3>Setup Wizard</h3>
          <p class='muted'>صفحة فحص سريعة لكل الأنظمة المهمة.</p>
          <table><tr><th>System</th><th>Status</th><th>Value</th></tr>{rows}</table>
        </div>
        <div class='grid'>
          <a class='server-card' href='/dashboard/settings?guild_id={g}'>⚙️ Settings</a>
          <a class='server-card' href='/dashboard/game-roles?guild_id={g}'>🎭 Game Roles</a>
          <a class='server-card' href='/dashboard/casino-controls?guild_id={g}'>🎰 Casino Controls</a>
          <a class='server-card' href='/dashboard/boosts?guild_id={g}'>🚀 Boosts</a>
        </div>
        """
        return page("Setup Wizard", body, g)


    @app.route("/dashboard/roles", methods=["GET", "POST"])
    def role_manager_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        def get_guild_obj():
            try:
                for guild in bot.guilds:
                    if int(guild.id) == int(g):
                        return guild
            except Exception:
                pass
            return None

        def run_discord(coro, timeout=8):
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                return fut.result(timeout=timeout)
            except Exception as e:
                return e

        def fetch_member_sync(guild, user_id):
            try:
                m = guild.get_member(int(user_id))
                if m:
                    return m
                res = run_discord(guild.fetch_member(int(user_id)), timeout=8)
                if isinstance(res, Exception):
                    return None
                return res
            except Exception:
                return None

        def can_manage_role(guild, role):
            try:
                me = guild.me
                if not me:
                    return False, "Bot member not loaded"
                if role.is_default():
                    return False, "Cannot manage @everyone"
                if getattr(role, "managed", False):
                    return False, "Managed/integration role"
                if role >= me.top_role:
                    return False, "Role is above/equal bot top role"
                if not me.guild_permissions.manage_roles:
                    return False, "Bot missing Manage Roles"
                return True, "OK"
            except Exception as e:
                return False, str(e)

        guild = get_guild_obj()
        if not guild:
            return page("Role Manager", server_pill_html(g, bot) + "<div class='card'><h3>Guild not found</h3><p class='muted'>البوت مو شايف هذا السيرفر الآن.</p></div>", g)

        msg = ""
        msg_color = "info"

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            actor_id, actor_name = dashboard_actor()

            try:
                user_id = int(request.form.get("user_id") or 0)
                role_id = int(request.form.get("role_id") or 0)
            except Exception:
                user_id = 0
                role_id = 0

            member = fetch_member_sync(guild, user_id) if user_id else None
            role = guild.get_role(role_id) if role_id else None

            if not member:
                msg = "❌ العضو غير موجود أو البوت ما قدر يجيبه من Discord."
                msg_color = "bad"
            elif not role:
                msg = "❌ الرتبة غير موجودة."
                msg_color = "bad"
            else:
                ok, reason = can_manage_role(guild, role)
                if not ok:
                    msg = f"❌ البوت ما يقدر يتحكم في هذه الرتبة: {esc(reason)}"
                    msg_color = "bad"
                elif action == "add_role":
                    async def do_add():
                        await member.add_roles(role, reason=f"Dashboard role add by {actor_name} ({actor_id})")
                    res = run_discord(do_add(), timeout=8)
                    if isinstance(res, Exception):
                        msg = f"❌ فشل إعطاء الرتبة: {esc(type(res).__name__)}: {esc(str(res)[:300])}"
                        msg_color = "bad"
                    else:
                        msg = f"✅ تم إعطاء {role.mention} إلى {member.mention}"
                        msg_color = "ok"
                        log_event(g, "dashboard_role_add", member.id, member.display_name, 0, "", "Dashboard role added", f"Role={role.name} ({role.id}), Actor={actor_id}")
                elif action == "remove_role":
                    async def do_remove():
                        await member.remove_roles(role, reason=f"Dashboard role remove by {actor_name} ({actor_id})")
                    res = run_discord(do_remove(), timeout=8)
                    if isinstance(res, Exception):
                        msg = f"❌ فشل سحب الرتبة: {esc(type(res).__name__)}: {esc(str(res)[:300])}"
                        msg_color = "bad"
                    else:
                        msg = f"✅ تم سحب {role.mention} من {member.mention}"
                        msg_color = "ok"
                        log_event(g, "dashboard_role_remove", member.id, member.display_name, 0, "", "Dashboard role removed", f"Role={role.name} ({role.id}), Actor={actor_id}")

            return redirect(f"/dashboard/roles?guild_id={g}&user_id={user_id}&msg={urllib.parse.quote(msg)}&color={msg_color}")

        selected_uid = request.args.get("user_id", "").strip()
        msg = request.args.get("msg", "").strip()
        msg_color = request.args.get("color", "info").strip()

        target_member = None
        if selected_uid.isdigit():
            target_member = fetch_member_sync(guild, int(selected_uid))

        roles = sorted([r for r in guild.roles if not r.is_default()], key=lambda r: r.position, reverse=True)
        manageable = []
        locked = []

        for r in roles:
            ok, reason = can_manage_role(guild, r)
            item = (r, reason)
            if ok:
                manageable.append(item)
            else:
                locked.append(item)

        target_roles = set()
        if target_member:
            target_roles = {int(r.id) for r in target_member.roles}

        role_rows = ""
        for role, reason in manageable[:250]:
            has_role = int(role.id) in target_roles
            role_rows += f"""
            <tr>
              <td><span class='pill'>{esc(role.name)}</span><br><code>{role.id}</code></td>
              <td>{int(role.position)}</td>
              <td>{'✅ معه الرتبة' if has_role else '—'}</td>
              <td>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=user_id value='{esc(selected_uid)}'>
                  <input type=hidden name=role_id value='{role.id}'>
                  <button name=action value='add_role' {'disabled' if not target_member or has_role else ''}>Give</button>
                </form>
                <form method='post' style='display:inline'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=user_id value='{esc(selected_uid)}'>
                  <input type=hidden name=role_id value='{role.id}'>
                  <button name=action value='remove_role' style='background:#dc2626' {'disabled' if not target_member or not has_role else ''}>Remove</button>
                </form>
              </td>
            </tr>
            """

        if not role_rows:
            role_rows = "<tr><td colspan='4'>No manageable roles. ارفع رتبة البوت فوق الرتب وعطه Manage Roles.</td></tr>"

        locked_rows = "".join(
            f"<tr><td>{esc(role.name)}<br><code>{role.id}</code></td><td>{esc(reason)}</td></tr>"
            for role, reason in locked[:120]
        ) or "<tr><td colspan='2'>No locked roles.</td></tr>"

        member_card = ""
        if target_member:
            member_card = f"""
            <div class='card'>
              <h3>Target Member</h3>
              <div class='userline'>
                <img class='avatar-lg' src='{target_member.display_avatar.url}'>
                <div>
                  <b style='font-size:22px'>{esc(target_member.display_name)}</b><br>
                  <code>{target_member.id}</code><br>
                  <span class='muted'>Current roles: {max(0, len(target_member.roles)-1)}</span>
                </div>
              </div>
            </div>
            """
        elif selected_uid:
            member_card = "<div class='card kpi-bad'><h3>Member not found</h3><p class='muted'>تأكد من User ID وأن العضو داخل السيرفر.</p></div>"

        alert = f"<div class='card kpi-{msg_color}'><h3>Result</h3><p>{esc(msg)}</p></div>" if msg else ""

        body = server_pill_html(g, bot)
        body += alert
        body += f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Manageable Roles</div><div class='stat'>{len(manageable):,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Locked Roles</div><div class='stat'>{len(locked):,}</div></div>
          <div class='card'><div class='muted'>Bot Top Role</div><div class='stat' style='font-size:18px'>{esc(guild.me.top_role.name if guild.me else 'Unknown')}</div></div>
        </div>

        <div class='card'>
          <h3>Role Manager</h3>
          <p class='muted'>اختر عضو بالـ User ID، بعدها تقدر تعطيه أو تسحب منه أي رتبة يقدر البوت يتحكم فيها.</p>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(selected_uid)}' style='min-width:260px'>
            <button>Open Member</button>
          </form>
        </div>

        {member_card}

        <div class='card'>
          <h3>Quick Role Action</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id placeholder='User ID' value='{esc(selected_uid)}'>
            <input name=role_id placeholder='Role ID'>
            <button name=action value='add_role'>Give Role</button>
            <button name=action value='remove_role' style='background:#dc2626'>Remove Role</button>
          </form>
        </div>

        <div class='card'>
          <h3>Manageable Roles</h3>
          <table><tr><th>Role</th><th>Position</th><th>Status</th><th>Action</th></tr>{role_rows}</table>
        </div>

        <div class='card'>
          <h3>Locked / Not Manageable Roles</h3>
          <p class='muted'>هذه الرتب ما يقدر البوت يتحكم فيها لأنها أعلى من رتبة البوت أو managed من Discord.</p>
          <table><tr><th>Role</th><th>Reason</th></tr>{locked_rows}</table>
        </div>
        """
        return page("Role Manager", body, g)


    @app.route("/dashboard/companies", methods=["GET", "POST"])
    def companies_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        companies_service.seed_sector_settings(g)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            sector_key = request.form.get("sector_key", "").strip()

            if action == "update_sector" and sector_key:
                try:
                    enabled = request.form.get("enabled") == "1"
                    start_cost = int(request.form.get("start_cost") or 0)
                    base_income = int(request.form.get("base_income") or 0)
                    upgrade_base = int(request.form.get("upgrade_base") or 0)
                    tax_bps = int(float(request.form.get("tax_percent") or 0) * 100)
                    payroll_bps = int(float(request.form.get("payroll_percent") or 0) * 100)
                    risk_bps = int(float(request.form.get("risk_percent") or 0) * 100)
                    companies_service.update_sector_settings(
                        g,
                        sector_key,
                        enabled=enabled,
                        start_cost=start_cost,
                        base_income=base_income,
                        upgrade_base=upgrade_base,
                        tax_bps=tax_bps,
                        payroll_bps=payroll_bps,
                        risk_bps=risk_bps,
                    )
                except Exception:
                    pass

            return redirect(f"/dashboard/companies?guild_id={g}")

        rows = companies_service.all_companies(g, 300)
        settings = companies_service.sector_settings(g)

        total_balance = sum(int(c.get("balance") or 0) for c in rows)
        active = sum(1 for c in rows if int(c.get("active") or 0))
        avg_level = round(sum(int(c.get("level") or 1) for c in rows) / max(1, len(rows)), 2)

        sector_rows = ""
        for key in companies_service.SECTORS.keys():
            s = companies_service.sector_info_for_guild(g, key)
            sector_rows += f"""
            <tr>
              <td>{s['emoji']} <b>{esc(s['name'])}</b><br><code>{esc(key)}</code><br><span class='muted'>{esc(s['desc'])}</span></td>
              <td>
                <form method='post' style='display:grid;grid-template-columns:75px 120px 120px 120px 90px 90px 90px 90px;gap:6px;min-width:820px'>
                  <input type=hidden name=guild_id value='{g}'>
                  <input type=hidden name=sector_key value='{esc(key)}'>
                  <label style='display:flex;align-items:center;gap:5px'><input type=checkbox name=enabled value=1 {'checked' if int(s.get('enabled',1)) else ''}> Enabled</label>
                  <input name=start_cost type=number min=0 value='{int(s['start_cost'])}' title='Start Cost'>
                  <input name=base_income type=number min=0 value='{int(s['base_income'])}' title='Base Income'>
                  <input name=upgrade_base type=number min=0 value='{int(s['upgrade_base'])}' title='Upgrade Base'>
                  <input name=tax_percent type=number step=.1 min=0 max=100 value='{int(s['tax_bps'])/100}' title='Tax %'>
                  <input name=payroll_percent type=number step=.1 min=0 max=100 value='{int(s['payroll_bps'])/100}' title='Payroll %'>
                  <input name=risk_percent type=number step=.1 min=0 max=100 value='{int(s['risk_bps'])/100}' title='Risk %'>
                  <button name=action value='update_sector'>Save</button>
                </form>
              </td>
            </tr>
            """

        company_rows = ""
        for c in rows:
            sector = companies_service.sector_info_for_guild(g, c["sector_key"])
            preview = companies_service.income_preview(c)
            cycles, remaining = companies_service.rent_like_remaining(c)
            company_rows += f"""
            <tr>
              <td><code>{int(c['id'])}</code></td>
              <td>{sector['emoji']} <b>{esc(c['name'])}</b><br><span class='muted'>{esc(sector['name'])}</span></td>
              <td>{user_chip(bot,g,c['owner_id'],c['owner_name'])}</td>
              <td>{int(c['level'])}</td>
              <td>{int(c['balance']):,}</td>
              <td>{preview['success_score']}/100</td>
              <td>{preview['net_company']:,}</td>
              <td>{'✅ '+str(cycles)+' ready' if cycles else '⏳ '+companies_service.seconds_to_text(remaining)}</td>
            </tr>
            """

        if not company_rows:
            company_rows = "<tr><td colspan='8'>No companies yet.</td></tr>"

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Companies</div><div class='stat'>{len(rows):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Active</div><div class='stat'>{active:,}</div></div>
          <div class='card'><div class='muted'>Company Balances</div><div class='stat'>{total_balance:,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Average Level</div><div class='stat'>{avg_level}</div></div>
        </div>

        <div class='card'>
          <h3>🏢 Pro Company Control Center</h3>
          <p class='muted'>لوحة تحكم الشركات الاحترافية: تعديل الأسعار، الدخل، الضرائب، الرواتب، المخاطرة، فتح/إغلاق القطاعات، ومراقبة الشركات. كل تغيير محفوظ في قاعدة البيانات ويبقى بعد الريستارت.</p>
          <p>Balance safety: <b>{companies_service.MAX_COMPANIES_PER_USER}</b> شركات كحد أقصى لكل عضو • البيع يرجع <b>30%</b> فقط + رصيد الشركة • القرارات تؤثر على النجاح والمخاطرة.</p>
        </div>

        <div class='card'>
          <h3>Sector Prices / Income Editor</h3>
          <table><tr><th>Sector</th><th>Settings</th></tr>{sector_rows}</table>
        </div>

        <div class='card'>
          <h3>Companies</h3>
          <table><tr><th>ID</th><th>Company</th><th>Owner</th><th>Level</th><th>Balance</th><th>Success</th><th>Net / 6h</th><th>Income</th></tr>{company_rows}</table>
        </div>
        """
        return page("Companies", body, g)

    @app.route("/dashboard/settings", methods=["GET", "POST"])
    def settings_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "save_post_rewards":
                post_rewards.update_settings(
                    g,
                    enabled=bool(request.form.get("post_reward_enabled")),
                    amount=int(request.form.get("post_reward_amount") or 5000),
                    channel_ids=request.form.get("post_reward_channels", ""),
                    min_length=int(request.form.get("post_reward_min_length") or 5),
                    cooldown_seconds=int(request.form.get("post_reward_cooldown") or 0)
                )
                return redirect(f"/dashboard/settings?guild_id={g}")

            if action == "save_dev_mode":
                set_dev_mode_enabled(g, bool(request.form.get("dev_mode_enabled")))
                return redirect(f"/dashboard/settings?guild_id={g}")

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
        pr = post_rewards.get_settings(g)
        from nmcore.services.settings import get_lfg_settings
        lfg = get_lfg_settings(g)

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

        <div class='card kpi-good'>
          <h3>Post Reward / مكافأة البوست</h3>
          <p class='muted'>يعطي العضو مبلغ تلقائيًا لكل بوست في الرومات المحددة.</p>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_post_rewards'>
            <label><input type=checkbox name=post_reward_enabled {'checked' if int(pr.get('enabled') or 0) else ''}> Enabled</label><br><br>
            Amount per post<br>
            <input name=post_reward_amount type=number min=0 value='{int(pr.get('amount') or 5000)}'><br><br>
            Channel IDs<br>
            <textarea name=post_reward_channels style='width:100%;height:70px' placeholder='Channel IDs separated by comma'>{esc(pr.get('channel_ids') or '')}</textarea><br><br>
            Minimum text length<br>
            <input name=post_reward_min_length type=number min=0 value='{int(pr.get('min_length') or 5)}'><br><br>
            Cooldown seconds per user<br>
            <input name=post_reward_cooldown type=number min=0 value='{int(pr.get('cooldown_seconds') or 0)}'><br><br>
            <button>Save Post Reward</button>
          </form>
          <p class='muted'><a href='/dashboard/post-rewards?guild_id={g}'>Open Post Rewards Report</a></p>
        </div>

        <div class='card kpi-info'>
          <h3>Looking For Game Settings</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_lfg_settings'>
            LFG Text Channel ID<br>
            <input name=lfg_channel_id value='{int(lfg.get('lfg_channel_id') or 0)}'><br><br>
            LFG Voice Category ID<br>
            <input name=lfg_category_id value='{int(lfg.get('lfg_category_id') or 0)}'><br><br>
            Delete empty voice after minutes<br>
            <input name=lfg_delete_empty_minutes type=number min=0 value='{int(lfg.get('lfg_delete_empty_minutes') or 10)}'><br><br>
            <button>Save LFG Settings</button>
          </form>
          <p class='muted'>بعد الحفظ: <code>!شرح_لعب</code> يرسل الشرح للروم، و <code>!لعب</code> يشتغل هناك فقط.</p>
        </div>

        <div class='card kpi-warn'>
          <h3>Bot Access / Development Mode</h3>
          <p class='muted'>Dev Mode يقفل الأوامر على الناس ويخليها لصاحب البوت فقط. الآن الافتراضي OFF عشان البوت مفتوح للجميع.</p>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_dev_mode'>
            <label><input type=checkbox name=dev_mode_enabled {'checked' if is_dev_mode_enabled(g) else ''}> Dev Mode ON / البوت قيد التطوير</label>
            <br><br>
            <button>Save Dev Mode</button>
          </form>
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


    @app.route("/dashboard/post-rewards")
    def post_rewards_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)
        data = post_rewards.summary(g, 150)
        totals = data.get("totals", {})
        top = data.get("top", [])
        recent = data.get("recent", [])

        top_rows = "".join(
            f"<tr><td>{user_chip(bot,g,r.get('user_id') or 0,r.get('user_name') or '')}</td><td>{int(r.get('posts') or 0):,}</td><td>{int(r.get('total') or 0):,}</td></tr>"
            for r in top
        ) or "<tr><td colspan='3'>No rewarded posts yet.</td></tr>"

        recent_rows = "".join(
            f"<tr><td><code>{r.get('id')}</code></td><td>{user_chip(bot,g,r.get('user_id') or 0,r.get('user_name') or '')}</td><td><code>{r.get('channel_id')}</code></td><td><code>{r.get('message_id')}</code></td><td>{int(r.get('amount') or 0):,}</td><td><code>{esc(str(r.get('money_tx_id') or ''))[:12]}</code></td></tr>"
            for r in recent
        ) or "<tr><td colspan='6'>No recent rewards.</td></tr>"

        body = server_pill_html(g, bot)
        body += f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Rewarded Posts</div><div class='stat'>{int(totals.get('c') or 0):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Total Paid</div><div class='stat'>{int(totals.get('total') or 0):,}</div></div>
          <div class='card'><div class='muted'>Top Users</div><div class='stat'>{len(top):,}</div></div>
        </div>
        <div class='card'>
          <h3>Post Reward Report</h3>
          <p class='muted'>هذا للبوستات العادية في الرومات المحددة من Settings.</p>
          <a class='btn' href='/dashboard/settings?guild_id={g}'>Edit Post Reward Settings</a>
          <a class='btn' style='background:#334155' href='/dashboard/boosts?guild_id={g}'>Open Boosts Page</a>
        </div>
        <div class='card'><h3>Top Paid Users</h3><table><tr><th>User</th><th>Posts</th><th>Total Paid</th></tr>{top_rows}</table></div>
        <div class='card'><h3>Recent Rewards</h3><table><tr><th>ID</th><th>User</th><th>Channel</th><th>Message</th><th>Amount</th><th>TX</th></tr>{recent_rows}</table></div>
        """
        return page("Post Rewards", body, g)

    @app.route("/dashboard/boosts", methods=["GET", "POST"])
    def boosts_page():
        d = require_login()
        if d:
            return d

        g = gid(bot)

        if request.method == "POST":
            action = request.form.get("action", "").strip()

            if action == "save_boost_settings":
                boost_rewards.update_settings(
                    g,
                    enabled=bool(request.form.get("boost_reward_enabled")),
                    amount=int(request.form.get("boost_reward_amount") or 0)
                )
                return redirect(f"/dashboard/boosts?guild_id={g}")

            if action == "sync_boosters":
                try:
                    guild_obj = None
                    for bg in bot.guilds:
                        if int(bg.id) == int(g):
                            guild_obj = bg
                            break
                    if guild_obj:
                        boost_rewards.sync_guild_boosters(guild_obj)
                except Exception:
                    pass
                return redirect(f"/dashboard/boosts?guild_id={g}")

        try:
            guild_obj = None
            for bg in bot.guilds:
                if int(bg.id) == int(g):
                    guild_obj = bg
                    break
            if guild_obj:
                boost_rewards.sync_guild_boosters(guild_obj)
        except Exception:
            pass

        settings = boost_rewards.get_settings(g)
        data = boost_rewards.summary(g, 200)
        totals = data.get("totals", {})
        boosters = data.get("boosters", [])
        recent = data.get("recent", [])

        booster_rows = "".join(
            f"<tr><td>{user_chip(bot,g,r.get('user_id') or 0,r.get('user_name') or '')}</td><td>{status_badge('active' if int(r.get('active') or 0) else 'inactive')}</td><td>{int(r.get('boost_count') or 0):,}</td><td>{int(r.get('reward_total') or 0):,}</td><td>{int(r.get('first_boost_at') or 0)}</td><td>{int(r.get('last_boost_at') or 0)}</td></tr>"
            for r in boosters
        ) or "<tr><td colspan='6'>No boosters tracked yet.</td></tr>"

        recent_rows = "".join(
            f"<tr><td><code>{r.get('id')}</code></td><td>{user_chip(bot,g,r.get('user_id') or 0,r.get('user_name') or '')}</td><td>{int(r.get('amount') or 0):,}</td><td><code>{esc(str(r.get('money_tx_id') or ''))[:12]}</code></td><td><code>{r.get('message_id')}</code></td><td>{esc(r.get('event_type') or 'boost')}</td></tr>"
            for r in recent
        ) or "<tr><td colspan='6'>No boost events yet.</td></tr>"

        body = server_pill_html(g, bot)
        body += f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Boost Events</div><div class='stat'>{int(totals.get('total_events') or 0):,}</div></div>
          <div class='card kpi-good'><div class='muted'>Unique Boosters</div><div class='stat'>{int(totals.get('unique_boosters') or 0):,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Active Boosters</div><div class='stat'>{int(totals.get('active_boosters') or 0):,}</div></div>
          <div class='card'><div class='muted'>Rewards Paid</div><div class='stat'>{int(totals.get('total_rewards') or 0):,}</div></div>
        </div>
        <div class='card'>
          <h3>Boost Reward Settings</h3>
          <form method=post>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='save_boost_settings'>
            <label><input type=checkbox name=boost_reward_enabled {'checked' if int(settings.get('enabled') or 0) else ''}> Enable boost reward</label><br><br>
            Amount per boost<br>
            <input name=boost_reward_amount type=number min=0 value='{int(settings.get('amount') or 5000)}'><br><br>
            <button>Save Boost Settings</button>
          </form>
          <form method=post style='margin-top:12px'>
            <input type=hidden name=guild_id value='{g}'>
            <input type=hidden name=action value='sync_boosters'>
            <button style='background:#334155'>Sync Active Boosters From Discord</button>
          </form>
          <p class='muted'>Active boosters are synced from Discord Server Boost data/member premium_since. Exact historical boost counts start from boost messages detected after installing tracking.</p>
        </div>
        <div class='card'><h3>Boosters</h3><table><tr><th>User</th><th>Status</th><th>Boost Count</th><th>Rewards</th><th>First</th><th>Last</th></tr>{booster_rows}</table></div>
        <div class='card'><h3>Recent Boost Events</h3><table><tr><th>ID</th><th>User</th><th>Reward</th><th>TX</th><th>Message</th><th>Type</th></tr>{recent_rows}</table></div>
        """
        return page("Boosts", body, g)

    @app.route("/dashboard/shop", methods=["GET", "POST"])
    def shop_page():
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
            reason = request.form.get("reason", "").strip() or f"Dashboard real estate shop {action}"

            conn = db()
            cur = conn.cursor()

            if action in {"set_owner", "clear_owner", "edit_property"} and property_id:
                cur.execute("SELECT * FROM properties WHERE guild_id=? AND id=?", (g, property_id))
                prop = cur.fetchone()

                if prop:
                    if action == "set_owner":
                        cur.execute(
                            "UPDATE properties SET owner_id=?, owner_name=?, last_rent_claim=strftime('%s','now') WHERE guild_id=? AND id=?",
                            (owner_id, owner_name[:120], int(time.time()), g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_shop_set_owner", int(prop["owner_id"] or 0), owner_id, actor_id, 0, int(prop["level"]), int(prop["level"]), int(prop["price"]), int(prop["price"]), reason, ""))

                    elif action == "clear_owner":
                        cur.execute(
                            "UPDATE properties SET owner_id=0, owner_name='' WHERE guild_id=? AND id=?",
                            (g, property_id)
                        )
                        cur.execute("""INSERT INTO property_ledger
                        (guild_id,property_id,action,old_owner_id,new_owner_id,actor_id,amount,level_before,level_after,price_before,price_after,reason,money_tx_id,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))""",
                        (g, property_id, "dashboard_shop_clear_owner", int(prop["owner_id"] or 0), 0, actor_id, 0, int(prop["level"]), int(prop["level"]), int(prop["price"]), int(prop["price"]), reason, ""))

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
                        (g, property_id, "dashboard_shop_edit_property", int(prop["owner_id"] or 0), int(prop["owner_id"] or 0), actor_id, 0, int(prop["level"]), level, int(prop["price"]), price, reason, ""))

                    conn.commit()

                    log_event(
                        g,
                        f"dashboard_real_estate_shop_{action}",
                        owner_id or int(prop["owner_id"] or 0),
                        owner_name,
                        0,
                        "",
                        f"Dashboard real estate shop {action}",
                        f"Actor={actor_id}, Property={property_id}, Reason={reason}"
                    )

            conn.close()
            return redirect(f"/dashboard/shop?guild_id={g}")

        owner_filter = request.args.get("owner_id", "").strip()
        property_type = request.args.get("type", "").strip()
        only_available = request.args.get("available", "1").strip() == "1"

        rows = real_estate.rows(g, only_available=only_available)

        if owner_filter.isdigit():
            rows = [r for r in rows if int(r["owner_id"] or 0) == int(owner_filter)]

        if property_type:
            rows = [r for r in rows if str(r["type_key"]) == property_type]

        all_rows = real_estate.rows(g)
        available_count = sum(1 for r in all_rows if int(r["owner_id"] or 0) == 0)
        sold_count = len(all_rows) - available_count

        conn = db()
        cur = conn.cursor()
        cur.execute("""SELECT p.*, l.created_at, l.money_tx_id, l.amount
        FROM property_ledger l
        JOIN properties p ON p.guild_id=l.guild_id AND p.id=l.property_id
        WHERE l.guild_id=? AND l.action IN ('buy_from_system','dashboard_shop_set_owner')
        ORDER BY l.id DESC LIMIT 40""", (g,))
        purchases = cur.fetchall()

        cur.execute("""SELECT type_key, COUNT(*) c,
        SUM(CASE WHEN owner_id=0 THEN 1 ELSE 0 END) available,
        COALESCE(SUM(CASE WHEN owner_id!=0 THEN price ELSE 0 END),0) sold_value
        FROM properties WHERE guild_id=? GROUP BY type_key ORDER BY sold_value DESC""", (g,))
        type_summary = cur.fetchall()
        conn.close()

        summary_trs = "".join(
            f"<tr><td>{esc(r['type_key'])}</td><td>{int(r['c']):,}</td><td>{int(r['available'] or 0):,}</td><td>{int(r['sold_value'] or 0):,}</td></tr>"
            for r in type_summary
        )

        trs = "".join(
            f"""<tr>
              <td>{r['id']}</td>
              <td>{esc(r['display_name'])}</td>
              <td>{esc(r['type_key'])}</td>
              <td>{r['owner_id'] or '-'}</td>
              <td>{esc(r['owner_name'] or '')}</td>
              <td>{int(r['price']):,}</td>
              <td>{int(r['rent']):,}</td>
              <td>{int(r['level'])}</td>
              <td>
                <form method='post' style='display:grid;grid-template-columns:110px 110px 85px 85px 70px 120px;gap:6px;min-width:640px'>
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
            for r in rows[:250]
        )

        purchase_trs = "".join(
            f"<tr><td>{p['id']}</td><td>{esc(p['display_name'])}</td><td>{esc(p['type_key'])}</td><td><code>{p['owner_id']}</code></td><td>{esc(p['owner_name'])}</td><td>{int(p['amount'] or p['price'] or 0):,}</td><td><code>{esc(p['money_tx_id'])[:12]}</code></td></tr>"
            for p in purchases
        )

        body = server_pill_html(g, bot) + f"""
        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Shop Mode</div><div class='stat'>Real Estate</div></div>
          <div class='card kpi-good'><div class='muted'>Available</div><div class='stat'>{available_count:,}</div></div>
          <div class='card kpi-warn'><div class='muted'>Sold / Owned</div><div class='stat'>{sold_count:,}</div></div>
          <div class='card'><div class='muted'>Total Properties</div><div class='stat'>{len(all_rows):,}</div></div>
        </div>

        <div class='card'>
          <h3>Real Estate Shop Filters</h3>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=owner_id placeholder='Owner ID' value='{esc(owner_filter)}'>
            <input name=type placeholder='type_key مثل room/apartment' value='{esc(property_type)}'>
            <label><input type=checkbox name=available value=1 {'checked' if only_available else ''}> Available only</label>
            <button>Filter</button>
            <a class='btn' style='background:#334155' href='/dashboard/shop?guild_id={g}'>Reset</a>
          </form>
          <p class='muted'>المتجر حاليًا مخصص للعقارات فقط. أمر الشراء في الديسكورد: <code>!شراء ID</code></p>
        </div>

        <div class='card'>
          <h3>Property Type Summary</h3>
          <table><tr><th>Type</th><th>Total</th><th>Available</th><th>Sold Value</th></tr>{summary_trs}</table>
        </div>

        <div class='card'>
          <h3>Properties Shop</h3>
          <table><tr><th>ID</th><th>Name</th><th>Type</th><th>Owner</th><th>Owner Name</th><th>Price</th><th>Rent</th><th>Level</th><th>Actions</th></tr>{trs}</table>
        </div>

        <div class='card'>
          <h3>Recent Property Purchases</h3>
          <table><tr><th>ID</th><th>Property</th><th>Type</th><th>Buyer</th><th>Name</th><th>Amount</th><th>TX</th></tr>{purchase_trs}</table>
        </div>
        """
        return page("Real Estate Shop", body, g)


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

            reason = request.form.get("reason").strip() if request.form.get("reason") else f"Dashboard user action {action}"

            if uid_int and action in {"give", "take", "set"}:
                info = member_info(bot, g, uid_int)
                uname = info["name"] if info["name"] != str(uid_int) else str(uid_int)

                if action == "give" and amount > 0:
                    economy_service.credit(g, uid_int, amount, "dashboard_user_give", user_name=uname, actor_id=actor_id, actor_name=actor_name, reason=reason)
                elif action == "take" and amount > 0:
                    economy_service.debit(g, uid_int, amount, "dashboard_user_take", user_name=uname, actor_id=actor_id, actor_name=actor_name, reason=reason)
                elif action == "set" and amount >= 0:
                    economy_service.set_balance(g, uid_int, amount, "dashboard_user_set_balance", user_name=uname, actor_id=actor_id, actor_name=actor_name, reason=reason)

                log_event(g, f"dashboard_user_{action}", uid_int, uname, 0, "", f"Dashboard user {action}", f"Actor={actor_id}, Amount={amount}, Reason={reason}")

            return redirect(f"/dashboard/user?guild_id={g}&user_id={uid_int}")

        uid = request.args.get("user_id", "").strip()

        if not uid.isdigit():
            return page("User Lookup", server_pill_html(g, bot) + f"""
            <div class='card'>
              <h3>Advanced User Profile</h3>
              <form>
                <input type=hidden name=guild_id value='{g}'>
                <input name=user_id placeholder='User ID'>
                <button>Search</button>
              </form>
            </div>
            """, g)

        uid = int(uid)
        info = member_info(bot, g, uid)
        p = profile_service.get_user_profile(g, uid)
        risk = profile_service.risk_score(p)
        title = profile_service.profile_title(p)

        def n(v):
            return f"{int(v or 0):,}"

        achievement_cards = "".join(
            f"<div class='card'><div style='font-size:28px'>{esc(a['emoji'])}</div><h3>{esc(a['title'])}</h3><p class='muted'>{esc(a['desc'])}</p></div>"
            for a in p.get("achievements", [])
        ) or "<div class='card'><h3>No achievements yet</h3><p class='muted'>الإنجازات تظهر تلقائيًا حسب نشاط العضو.</p></div>"

        source_trs = "".join(
            f"<tr><td>{status_badge(r['source_type'])}</td><td>{n(r['rows'])}</td><td>{n(r['gained'])}</td><td>{n(r['spent'])}</td><td>{n(r['net'])}</td></tr>"
            for r in p["money_sources"]
        ) or "<tr><td colspan='5'>No source data.</td></tr>"

        ledger_trs = "".join(
            f"<tr><td><code>{esc(str(r['tx_id'])[:10])}</code></td><td>{n(r['amount'])}</td><td>{n(r['balance_before'])}</td><td>{n(r['balance_after'])}</td><td>{status_badge(r['source_type'])}</td><td>{esc(r['reason'])}</td></tr>"
            for r in p["recent_money"]
        ) or "<tr><td colspan='6'>No money history.</td></tr>"

        warn_trs = "".join(
            f"<tr><td><code>{r['id']}</code></td><td>{esc(r['reason'])}</td><td>{status_badge(r['status'])}</td><td>{user_chip(bot,g,r['moderator_id'],r['moderator_name'])}</td></tr>"
            for r in p["recent_warnings"]
        ) or "<tr><td colspan='4'>No warnings.</td></tr>"

        prop_trs = "".join(
            f"<tr><td><code>{r['id']}</code></td><td>{esc(r['display_name'])}</td><td>{int(r['level'])}</td><td>{n(r['rent'])}</td><td>{n(r['price'])}</td></tr>"
            for r in p["properties"]
        ) or "<tr><td colspan='5'>No properties.</td></tr>"

        risk_reasons = "<br>".join(esc(x) for x in risk["reasons"])

        body = server_pill_html(g, bot) + f"""
        <div class='card'>
          <form>
            <input type=hidden name=guild_id value='{g}'>
            <input name=user_id value='{uid}' placeholder='User ID'>
            <button>Search</button>
            <a class='btn' style='background:#334155' href='/dashboard/money-tracker?guild_id={g}&user_id={uid}'>Money Tracker</a>
            <a class='btn' style='background:#334155' href='/dashboard/warnings?guild_id={g}&user_id={uid}&status=all'>Warnings</a>
          </form>
        </div>

        <div class='card' style='display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap'>
          <div class='userline'>
            <img class='avatar-lg' src='{esc(info["avatar"])}'>
            <div>
              <div class='muted'>Advanced User Profile</div>
              <div style='font-size:28px;font-weight:950'>{esc(info["name"])}</div>
              <code>{uid}</code>
              <div style='margin-top:8px'><span class='pill'>{esc(title)}</span></div>
            </div>
          </div>
          <div class='card' style='margin:0;min-width:220px'>
            <div class='muted'>Risk Score</div>
            <div class='stat'>{risk['score']}/100</div>
            <div class='muted'>{risk_reasons}</div>
          </div>
        </div>

        <div class='grid'>
          <div class='card kpi-info'><div class='muted'>Balance</div><div class='stat'>{n(p['balance'])}</div></div>
          <div class='card'><div class='muted'>Level</div><div class='stat'>{int(p['level'])}</div><div class='muted'>XP {n(p['xp'])}</div></div>
          <div class='card kpi-good'><div class='muted'>Gained</div><div class='stat'>{n(p['money'].get('gained'))}</div></div>
          <div class='card kpi-bad'><div class='muted'>Spent/Lost</div><div class='stat'>{n(p['money'].get('spent'))}</div></div>
          <div class='card kpi-warn'><div class='muted'>Net</div><div class='stat'>{n(p['money'].get('net'))}</div></div>
          <div class='card'><div class='muted'>Achievements</div><div class='stat'>{len(p.get('achievements', []))}</div></div>
        </div>

        <div class='grid'>
          <div class='card'><h3>🎰 Casino</h3><div class='stat'>{n(p['casino'].get('plays'))}</div><p class='muted'>Plays</p><p>Wagered: <b>{n(p['casino'].get('wagered'))}</b><br>Paid: <b>{n(p['casino'].get('paid'))}</b><br>Net: <b>{n(p['casino'].get('net'))}</b></p></div>
          <div class='card'><h3>🏘️ Real Estate</h3><div class='stat'>{n(p['props_summary'].get('count'))}</div><p class='muted'>Properties</p><p>Rent Total: <b>{n(p['props_summary'].get('rent_total'))}</b><br>Value: <b>{n(p['props_summary'].get('property_value'))}</b></p></div>
          <div class='card'><h3>🚀 Boosts</h3><div class='stat'>{n(p['booster_profile'].get('boost_count') or p['boosts'].get('c'))}</div><p class='muted'>Boost events</p><p>Rewards: <b>{n(p['booster_profile'].get('reward_total'))}</b><br>Active: <b>{'Yes' if int(p['booster_profile'].get('active') or 0) else 'No'}</b></p></div>
          <div class='card'><h3>📝 Posts</h3><div class='stat'>{n(p['post_rewards'].get('posts'))}</div><p class='muted'>Rewarded posts</p><p>Total Paid: <b>{n(p['post_rewards'].get('total'))}</b></p></div>
          <div class='card'><h3>⚠️ Warnings</h3><div class='stat'>{n(p['warnings'].get('active'))}</div><p class='muted'>Active</p><p>Total: <b>{n(p['warnings'].get('total'))}</b><br>Cleared: <b>{n(p['warnings'].get('cleared'))}</b></p></div>
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

        <div class='grid'>{achievement_cards}</div>
        <div class='card'><h3>Money Sources</h3><table><tr><th>Source</th><th>Rows</th><th>Gained</th><th>Spent</th><th>Net</th></tr>{source_trs}</table></div>
        <div class='card'><h3>Money History</h3><table><tr><th>TX</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Reason</th></tr>{ledger_trs}</table></div>
        <div class='card'><h3>Warnings</h3><table><tr><th>ID</th><th>Reason</th><th>Status</th><th>By</th></tr>{warn_trs}</table></div>
        <div class='card'><h3>Properties</h3><table><tr><th>ID</th><th>Name</th><th>Level</th><th>Rent</th><th>Value</th></tr>{prop_trs}</table></div>
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
