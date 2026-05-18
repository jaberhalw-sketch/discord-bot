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
        e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
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
body {{
  margin:0;
  background:#050814;
  color:#f8fafc;
  font-family:Arial,sans-serif;
}}
.wrap {{
  display:flex;
  min-height:100vh;
}}
.side {{
  width:275px;
  background:#0f172a;
  padding:20px 16px;
  position:sticky;
  top:0;
  height:100vh;
  overflow:auto;
  border-right:1px solid #263244;
}}
.brand {{
  font-size:23px;
  font-weight:900;
  margin-bottom:22px;
}}
.side a {{
  display:block;
  color:#dbeafe;
  text-decoration:none;
  padding:12px 13px;
  border-radius:14px;
  margin:6px 0;
  font-weight:650;
}}
.side a:hover {{
  background:#1e293b;
  color:#fff;
}}
.main {{
  flex:1;
  padding:32px;
  min-width:0;
}}
h1 {{
  font-size:34px;
  margin:0 0 22px;
  font-weight:900;
}}
.card {{
  background:#111827;
  border:1px solid #263244;
  border-radius:22px;
  padding:20px;
  margin-bottom:18px;
  box-shadow:0 18px 55px rgba(0,0,0,.28);
  overflow:auto;
}}
.grid {{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  gap:16px;
}}
.stat {{
  font-size:30px;
  font-weight:900;
}}
.muted {{
  color:#94a3b8;
}}
table {{
  width:100%;
  border-collapse:collapse;
}}
td,th {{
  border-bottom:1px solid #263244;
  padding:12px;
  text-align:left;
  white-space:nowrap;
}}
th {{
  color:#c4b5fd;
}}
input,select,textarea {{
  padding:11px 12px;
  border-radius:12px;
  border:1px solid #334155;
  background:#020617;
  color:#fff;
}}
button,.btn {{
  background:#7c3aed;
  color:white!important;
  text-decoration:none;
  border:0;
  display:inline-block;
  padding:11px 16px;
  border-radius:13px;
  font-weight:800;
  cursor:pointer;
}}
.ok {{ color:#4ade80; }}
.bad {{ color:#f87171; }}
.warn {{ color:#fbbf24; }}
code {{
  background:#020617;
  border-radius:8px;
  padding:3px 7px;
  color:#c4b5fd;
}}
@media (max-width:850px) {{
  .wrap {{ display:block; }}
  .side {{ position:relative;width:100%;height:auto; }}
  .main {{ padding:20px; }}
}}
</style>
</head>
<body>
<div class="wrap">
  <aside class="side">
    <div class="brand">NM System V9</div>
    {links}
  </aside>
  <main class="main">
    <h1>{escape(title)}</h1>
    {body}
  </main>
</div>
</body>
</html>"""
