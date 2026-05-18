import os, time, html
from flask import Flask, request, redirect, session
from nmcore.config import DASHBOARD_PASSWORD, DASHBOARD_SECRET_KEY, DB_FILE
from nmcore.db import db, init_db
from nmcore.ui import page
from nmcore.services.settings import ensure_guild, get_coin_name, set_coin_name, all_toggles, set_system_enabled, get_guild_settings, update_channel
from nmcore.services import real_estate
from nmcore.services.warnings import summary as warn_summary
from nmcore.services.protection import get_settings as prot_get, update_settings as prot_update

def esc(x): return html.escape(str(x or ""))

def gid(bot=None):
    try:
        v=int(request.args.get("guild_id") or request.form.get("guild_id") or session.get("guild_id") or 0)
        if v: session["guild_id"]=v; return v
    except Exception: pass
    try:
        if bot and bot.guilds:
            session["guild_id"]=int(bot.guilds[0].id)
            return int(bot.guilds[0].id)
    except Exception: pass
    return 0

def require_login():
    if session.get("ok"): return None
    return redirect("/login")

def create_app(bot=None):
    app=Flask(__name__)
    app.secret_key=DASHBOARD_SECRET_KEY
    init_db()

    @app.route("/")
    def root(): return redirect("/dashboard")

    @app.route("/login", methods=["GET","POST"])
    def login():
        if request.method=="POST":
            if request.form.get("password")==DASHBOARD_PASSWORD:
                session["ok"]=True; return redirect("/dashboard")
            return "Wrong password", 403
        return """<body style="background:#070b14;color:white;font-family:Arial;padding:40px"><h1>NM System Login</h1><form method=post><input name=password type=password style="padding:12px"><button style="padding:12px">Login</button></form></body>"""

    @app.route("/logout")
    def logout():
        session.clear(); return redirect("/login")

    @app.route("/dashboard")
    def home():
        d=require_login()
        if d: return d
        g=gid(bot); ensure_guild(g)
        conn=db(); cur=conn.cursor()
        cur.execute("SELECT COUNT(*) c, COALESCE(SUM(balance),0) total FROM balances WHERE guild_id=?", (g,)); eco=cur.fetchone()
        cur.execute("SELECT COUNT(*) c FROM money_ledger WHERE guild_id=?", (g,)); led=cur.fetchone()
        cur.execute("SELECT COUNT(*) c FROM log_events WHERE guild_id=?", (g,)); logs=cur.fetchone()
        active,cleared=warn_summary(g)
        conn.close()
        body=f"""<div class='grid'>
        <div class='card'><div class='muted'>Guild</div><div class='stat'>{g}</div></div>
        <div class='card'><div class='muted'>Coin</div><div class='stat'>{esc(get_coin_name(g))}</div></div>
        <div class='card'><div class='muted'>Economy Users</div><div class='stat'>{int(eco['c'] or 0):,}</div></div>
        <div class='card'><div class='muted'>Total Money</div><div class='stat'>{int(eco['total'] or 0):,}</div></div>
        <div class='card'><div class='muted'>Ledger Rows</div><div class='stat'>{int(led['c'] or 0):,}</div></div>
        <div class='card'><div class='muted'>Warnings</div><div class='stat'>{active:,}</div></div>
        </div>"""
        return page("Dashboard Overview", body, g)

    @app.route("/dashboard/economy")
    def economy_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("SELECT user_id,balance,updated_at FROM balances WHERE guild_id=? ORDER BY balance DESC LIMIT 100", (g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td><code>{r['user_id']}</code></td><td>{int(r['balance']):,}</td><td><a href='/dashboard/user?guild_id={g}&user_id={r['user_id']}'>View</a></td></tr>" for r in rows)
        return page("Economy", f"<div class='card'><table><tr><th>User ID</th><th>Balance</th><th></th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/money-tracker")
    def money_tracker():
        d=require_login()
        if d: return d
        g=gid(bot); uid=request.args.get("user_id","").strip()
        q="SELECT * FROM money_ledger WHERE guild_id=?"; params=[g]
        if uid.isdigit(): q+=" AND user_id=?"; params.append(int(uid))
        q+=" ORDER BY id DESC LIMIT 250"
        conn=db(); cur=conn.cursor(); cur.execute(q,params); rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td><code>{r['tx_id'][:10]}</code></td><td>{r['user_id']}</td><td>{int(r['amount']):,}</td><td>{int(r['balance_before']):,}</td><td>{int(r['balance_after']):,}</td><td>{esc(r['source_type'])}</td><td>{esc(r['reason'])}</td></tr>" for r in rows)
        form=f"<div class='card'><form><input type=hidden name=guild_id value='{g}'><input name=user_id placeholder='User ID' value='{esc(uid)}'><button>Filter</button></form></div>"
        return page("Money Tracker", form+f"<div class='card'><table><tr><th>TX</th><th>User</th><th>Amount</th><th>Before</th><th>After</th><th>Source</th><th>Reason</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/casino")
    def casino_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("""SELECT source_label, COUNT(*) c, COALESCE(SUM(CASE WHEN amount<0 THEN -amount ELSE 0 END),0) took, COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) paid
        FROM money_ledger WHERE guild_id=? AND source_type LIKE 'casino_%' GROUP BY source_label""",(g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td>{esc(r['source_label'])}</td><td>{r['c']}</td><td>{int(r['took']):,}</td><td>{int(r['paid']):,}</td></tr>" for r in rows)
        return page("Casino", f"<div class='card'><p>No max bet. User can only bet available balance. Bet is deducted first.</p><table><tr><th>Game</th><th>Rows</th><th>Took</th><th>Paid</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/levels")
    def levels_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("SELECT * FROM levels WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT 100",(g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td>{r['user_id']}</td><td>{r['level']}</td><td>{r['xp']}</td></tr>" for r in rows)
        return page("Levels", f"<div class='card'><table><tr><th>User</th><th>Level</th><th>XP</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/real-estate")
    def real_estate_page():
        d=require_login()
        if d: return d
        g=gid(bot); real_estate.seed(g); rows=real_estate.rows(g)
        trs="".join(f"<tr><td>{r['id']}</td><td>{esc(r['display_name'])}</td><td>{r['owner_id'] or '-'}</td><td>{int(r['price']):,}</td><td>{int(r['rent']):,}</td><td>{r['level']}</td></tr>" for r in rows)
        return page("Real Estate", f"<div class='card'><table><tr><th>ID</th><th>Name</th><th>Owner</th><th>Price</th><th>Rent</th><th>Level</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/warnings")
    def warnings_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("SELECT * FROM warnings WHERE guild_id=? ORDER BY id DESC LIMIT 150",(g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td>{r['id']}</td><td>{r['user_id']}</td><td>{esc(r['reason'])}</td><td>{esc(r['status'])}</td></tr>" for r in rows)
        return page("Warnings", f"<div class='card'><table><tr><th>ID</th><th>User</th><th>Reason</th><th>Status</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/protection", methods=["GET","POST"])
    def protection_page():
        d=require_login()
        if d: return d
        g=gid(bot)
        if request.method=="POST":
            data={
                "enabled":1 if request.form.get("enabled") else 0,
                "bad_words_enabled":1 if request.form.get("bad_words_enabled") else 0,
                "links_enabled":1 if request.form.get("links_enabled") else 0,
                "delete_messages":1 if request.form.get("delete_messages") else 0,
                "bad_words":request.form.get("bad_words","")
            }
            prot_update(g,data); return redirect(f"/dashboard/protection?guild_id={g}")
        s=prot_get(g)
        body=f"""<div class='card'><form method=post>
        <input type=hidden name=guild_id value='{g}'>
        <label><input type=checkbox name=enabled {'checked' if s.get('enabled') else ''}> Enabled</label><br>
        <label><input type=checkbox name=bad_words_enabled {'checked' if s.get('bad_words_enabled') else ''}> Bad Words</label><br>
        <label><input type=checkbox name=links_enabled {'checked' if s.get('links_enabled') else ''}> Links</label><br>
        <label><input type=checkbox name=delete_messages {'checked' if s.get('delete_messages') else ''}> Delete Messages</label><br><br>
        <textarea name=bad_words style='width:100%;height:120px'>{esc(s.get('bad_words'))}</textarea><br><br><button>Save</button>
        </form></div>"""
        return page("Protection", body, g)

    @app.route("/dashboard/logs")
    def logs_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("SELECT * FROM log_events WHERE guild_id=? ORDER BY id DESC LIMIT 200",(g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td>{esc(r['event_type'])}</td><td>{r['user_id']}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td></tr>" for r in rows)
        return page("Logs", f"<div class='card'><table><tr><th>Type</th><th>User</th><th>Title</th><th>Details</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/live")
    def live_page():
        d=require_login()
        if d: return d
        g=gid(bot); conn=db(); cur=conn.cursor()
        cur.execute("SELECT * FROM live_activity WHERE guild_id=? ORDER BY id DESC LIMIT 200",(g,))
        rows=cur.fetchall(); conn.close()
        trs="".join(f"<tr><td>{esc(r['activity_type'])}</td><td>{esc(r['actor_name'])}</td><td>{esc(r['title'])}</td><td>{esc(r['details'])}</td><td>{int(r['amount']):,}</td></tr>" for r in rows)
        return page("Live Activity", f"<div class='card'><table><tr><th>Type</th><th>Actor</th><th>Title</th><th>Details</th><th>Amount</th></tr>{trs}</table></div>", g)

    @app.route("/dashboard/settings", methods=["GET","POST"])
    def settings_page():
        d=require_login()
        if d: return d
        g=gid(bot)
        if request.method=="POST":
            if "coin_name" in request.form: set_coin_name(g,request.form.get("coin_name"))
            for key in ["commands_channel_id","gambling_channel_id","logs_channel_id"]:
                if key in request.form: update_channel(g,key,int(request.form.get(key) or 0))
            for k,v in all_toggles(g).items():
                set_system_enabled(g,k, bool(request.form.get(f"toggle_{k}")))
            return redirect(f"/dashboard/settings?guild_id={g}")
        gs=get_guild_settings(g); toggles=all_toggles(g)
        checks="".join(f"<label><input type=checkbox name='toggle_{k}' {'checked' if v else ''}> {k}</label><br>" for k,v in toggles.items())
        body=f"""<div class='card'><form method=post><input type=hidden name=guild_id value='{g}'>
        <h3>Guild Settings</h3>
        Coin Name<br><input name=coin_name value='{esc(get_coin_name(g))}'><br><br>
        Commands Channel ID<br><input name=commands_channel_id value='{int(gs.get('commands_channel_id') or 0)}'><br>
        Gambling Channel ID<br><input name=gambling_channel_id value='{int(gs.get('gambling_channel_id') or 0)}'><br>
        Logs Channel ID<br><input name=logs_channel_id value='{int(gs.get('logs_channel_id') or 0)}'><br><br>
        <h3>System Toggles</h3>{checks}<br><button>Save</button></form></div>"""
        return page("Settings", body, g)

    @app.route("/dashboard/shop")
    def shop_page():
        d=require_login()
        if d: return d
        return page("Shop", "<div class='card'><p>Shop core is ready. Add custom items next.</p></div>", gid(bot))

    @app.route("/dashboard/giveaways")
    def giveaways_page():
        d=require_login()
        if d: return d
        return page("Giveaways", "<div class='card'><p>Giveaway storage is ready. Discord commands can be expanded next.</p></div>", gid(bot))

    @app.route("/dashboard/user")
    def user_page():
        d=require_login()
        if d: return d
        g=gid(bot); uid=request.args.get("user_id","").strip()
        if not uid.isdigit():
            return page("User Lookup", f"<div class='card'><form><input type=hidden name=guild_id value='{g}'><input name=user_id placeholder='User ID'><button>Search</button></form></div>", g)
        uid=int(uid); conn=db(); cur=conn.cursor()
        cur.execute("SELECT balance FROM balances WHERE guild_id=? AND user_id=?", (g,uid)); bal=cur.fetchone()
        cur.execute("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (g,uid)); lvl=cur.fetchone()
        cur.execute("SELECT * FROM money_ledger WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 50", (g,uid)); ledger=cur.fetchall()
        conn.close()
        trs="".join(f"<tr><td>{r['tx_id'][:10]}</td><td>{int(r['amount']):,}</td><td>{r['source_type']}</td><td>{esc(r['reason'])}</td></tr>" for r in ledger)
        body=f"<div class='grid'><div class='card'><div class='muted'>Balance</div><div class='stat'>{int(bal['balance'] if bal else 0):,}</div></div><div class='card'><div class='muted'>Level</div><div class='stat'>{int(lvl['level'] if lvl else 1)}</div></div></div><div class='card'><table><tr><th>TX</th><th>Amount</th><th>Source</th><th>Reason</th></tr>{trs}</table></div>"
        return page("User Lookup", body, g)

    @app.route("/dashboard/health")
    def health():
        d=require_login()
        if d: return d
        g=gid(bot)
        body=f"""<div class='card'><h2 class='ok'>V9 Unified OK</h2>
        <p>DB: <code>{esc(DB_FILE)}</code></p>
        <p>Old memory files are not required.</p>
        <p>Use <code>/dashboard/settings?guild_id={g}</code> to control systems.</p></div>"""
        return page("Health", body, g)

    return app
