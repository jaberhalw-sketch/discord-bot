import discord
from html import escape
from nmcore.config import BOT_BRAND
from nmcore.services.settings import get_coin_name

COLORS = {
    "ok": 0x22c55e,
    "bad": 0xef4444,
    "info": 0x3b82f6,
    "warn": 0xf59e0b,
    "purple": 0x8b5cf6,
    "money": 0x10b981,
    "casino": 0xf97316,
    "dark": 0x111827,
}

def coin(guild_id, amount):
    return f"**{int(amount):,}** {get_coin_name(guild_id)}"

def money_delta(guild_id, amount):
    amount = int(amount)
    sign = "+" if amount >= 0 else ""
    return f"**{sign}{amount:,}** {get_coin_name(guild_id)}"

def embed(title, desc="", color="info", member=None):
    e = discord.Embed(
        title=title,
        description=desc or "",
        color=COLORS.get(color, COLORS["info"]),
        timestamp=discord.utils.utcnow()
    )
    if member:
        e.set_author(name=f"{member.display_name}", icon_url=member.display_avatar.url)
        e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text=f"{BOT_BRAND} • V9 Unified")
    return e

def success(title, desc="", member=None):
    return embed(f"✅ {title}", desc, "ok", member)

def error(title, desc="", member=None):
    return embed(f"❌ {title}", desc, "bad", member)

def warning(title, desc="", member=None):
    return embed(f"⚠️ {title}", desc, "warn", member)

def page(title, body, guild_id=0):
    q = f"?guild_id={int(guild_id)}" if guild_id else ""
    nav = [
        ("🏠 Overview", f"/dashboard{q}"),
        ("💰 Economy", f"/dashboard/economy{q}"),
        ("🧾 Money Tracker", f"/dashboard/money-tracker{q}"),
        ("🎰 Casino", f"/dashboard/casino{q}"),
        ("📊 Levels", f"/dashboard/levels{q}"),
        ("🏘️ Real Estate", f"/dashboard/real-estate{q}"),
        ("⚠️ Warnings", f"/dashboard/warnings{q}"),
        ("🛡️ Protection", f"/dashboard/protection{q}"),
        ("📜 Logs", f"/dashboard/logs{q}"),
        ("🎁 Giveaways", f"/dashboard/giveaways{q}"),
        ("🛒 Shop", f"/dashboard/shop{q}"),
        ("🟢 Live", f"/dashboard/live{q}"),
        ("⚙️ Settings", f"/dashboard/settings{q}"),
        ("🩺 Health", f"/dashboard/health{q}")
    ]
    links = "".join(f"<a href='{h}'>{escape(t)}</a>" for t, h in nav)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
:root {{
  --bg:#050814;
  --panel:#0f172a;
  --panel2:#111827;
  --panel3:#020617;
  --line:#263244;
  --text:#f8fafc;
  --muted:#94a3b8;
  --purple:#7c3aed;
  --purple2:#a855f7;
  --green:#22c55e;
  --red:#ef4444;
  --orange:#f59e0b;
}}
*{{box-sizing:border-box}}
body{{
  margin:0;
  background:
    radial-gradient(circle at 20% 0%, rgba(124,58,237,.22), transparent 30%),
    radial-gradient(circle at 90% 10%, rgba(59,130,246,.12), transparent 30%),
    var(--bg);
  color:var(--text);
  font-family:Inter, Arial, sans-serif;
}}
.wrap{{display:flex;min-height:100vh}}
.side{{
  width:278px;
  background:linear-gradient(180deg,#101827,#0b1220);
  padding:20px 16px;
  position:sticky;
  top:0;
  height:100vh;
  overflow:auto;
  border-right:1px solid rgba(148,163,184,.14);
}}
.brand{{
  font-size:23px;
  font-weight:950;
  letter-spacing:.3px;
  margin:6px 4px 22px;
  text-shadow:0 0 20px rgba(124,58,237,.35);
}}
.side a{{
  display:block;
  color:#dbeafe;
  text-decoration:none;
  padding:12px 13px;
  border-radius:14px;
  margin:6px 0;
  transition:.16s ease;
  font-weight:650;
}}
.side a:hover{{
  background:linear-gradient(90deg,rgba(124,58,237,.28),rgba(59,130,246,.12));
  color:#fff;
  transform:translateX(3px);
}}
.main{{flex:1;padding:32px;min-width:0}}
h1{{font-size:34px;margin:0 0 22px;font-weight:950}}
h2,h3{{margin-top:0}}
.card{{
  background:linear-gradient(180deg,rgba(17,24,39,.96),rgba(15,23,42,.96));
  border:1px solid rgba(148,163,184,.18);
  border-radius:22px;
  padding:20px;
  margin-bottom:18px;
  box-shadow:0 18px 55px rgba(0,0,0,.28);
  overflow:auto;
}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.stat{{font-size:30px;font-weight:950;line-height:1.1}}
.muted{{color:var(--muted);font-weight:650}}
table{{width:100%;border-collapse:collapse;border-radius:14px;overflow:hidden}}
td,th{{border-bottom:1px solid rgba(148,163,184,.14);padding:12px;text-align:left;white-space:nowrap}}
th{{color:#c4b5fd;background:rgba(2,6,23,.35)}}
input,select,textarea{{
  padding:11px 12px;
  border-radius:12px;
  border:1px solid rgba(148,163,184,.24);
  background:#030712;
  color:#fff;
  outline:none;
}}
input:focus,select:focus,textarea:focus{{border-color:var(--purple2);box-shadow:0 0 0 3px rgba(124,58,237,.18)}}
button,.btn{{
  background:linear-gradient(135deg,var(--purple),var(--purple2));
  color:white!important;
  text-decoration:none;
  border:0;
  display:inline-block;
  padding:11px 16px;
  border-radius:13px;
  font-weight:850;
  cursor:pointer;
  box-shadow:0 10px 25px rgba(124,58,237,.25);
}}
button:hover,.btn:hover{{filter:brightness(1.08);transform:translateY(-1px)}}
.ok{{color:#4ade80}}.bad{{color:#f87171}}.warn{{color:#fbbf24}}
code{{background:#020617;border:1px solid rgba(148,163,184,.14);border-radius:8px;padding:3px 7px;color:#c4b5fd}}
@media (max-width:850px){{
  .wrap{{display:block}}
  .side{{position:relative;width:100%;height:auto}}
  .main{{padding:20px}}
}}
</style>
</head>
<body>
<div class="wrap">
  <aside class="side"><div class="brand">NM System V9</div>{links}</aside>
  <main class="main"><h1>{escape(title)}</h1>{body}</main>
</div>
</body>
</html>"""
