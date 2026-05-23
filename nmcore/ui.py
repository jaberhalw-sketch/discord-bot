import discord
from html import escape
from nmcore.config import BOT_BRAND
from nmcore.services.settings import get_coin_name

COLORS={"ok":0x22c55e,"bad":0xef4444,"info":0x3b82f6,"warn":0xf59e0b,"purple":0x7c3aed}

def coin(guild_id, amount):
    return f"**{int(amount):,}** {get_coin_name(guild_id)}"

def money_delta(guild_id, amount):
    sign="+" if int(amount)>=0 else ""
    return f"**{sign}{int(amount):,}** {get_coin_name(guild_id)}"

def embed(title, desc="", color="info", member=None):
    e=discord.Embed(title=title, description=desc, color=COLORS.get(color, COLORS["info"]), timestamp=discord.utils.utcnow())
    if member:
        e.set_author(name=f"{member.display_name} • {BOT_BRAND}", icon_url=member.display_avatar.url)
        e.set_thumbnail(url=member.display_avatar.url)
    e.set_footer(text=f"{BOT_BRAND} • V9 Unified")
    return e

def success(title, desc="", member=None):
    return embed(title, desc, "ok", member)


def error(title, desc="", member=None):
    return embed(title, desc, "bad", member)


def page(title, body, guild_id=0):
    q=f"?guild_id={int(guild_id)}" if guild_id else ""

    nav_groups=[
        ("Main", [
            ("🏠 Overview",f"/dashboard{q}"),
            ("📈 Analytics",f"/dashboard/analytics{q}"),
            ("🧪 Full Check",f"/dashboard/full-check{q}"),
            ("📘 Command Center",f"/dashboard/commands{q}"),
        ]),
        ("Money", [
            ("💰 Economy",f"/dashboard/economy{q}"),
            ("🧾 Money Tracker",f"/dashboard/money-tracker{q}"),
            ("🎰 Casino",f"/dashboard/casino{q}"),
            ("🛒 Shop",f"/dashboard/shop{q}"),
            ("🏘️ Real Estate",f"/dashboard/real-estate{q}"),
        ]),
        ("Community", [
            ("📊 Levels",f"/dashboard/levels{q}"),
            ("🎁 Giveaways",f"/dashboard/giveaways{q}"),
            ("👤 User Lookup",f"/dashboard/user{q}"),
        ]),
        ("Safety", [
            ("⚠️ Warnings",f"/dashboard/warnings{q}"),
            ("🛡️ Protection",f"/dashboard/protection{q}"),
            ("🧨 Security",f"/dashboard/security{q}"),
            ("📜 Logs",f"/dashboard/logs{q}"),
            ("🟢 Live",f"/dashboard/live{q}"),
        ]),
        ("System", [
            ("🧩 Setup",f"/dashboard/setup{q}"),
            ("⚙️ Settings",f"/dashboard/settings{q}"),
            ("🩺 Health",f"/dashboard/health{q}"),
        ]),
    ]

    links=""
    for group, items in nav_groups:
        links += f"<div class='nav-group'>{escape(group)}</div>"
        for t,h in items:
            links += f"<a href='{h}'>{escape(t)}</a>"

    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>
:root{{
  --bg:#070b14;--panel:#0f172a;--card:#111827;--card2:#0b1220;--line:#253044;
  --text:#e5e7eb;--muted:#94a3b8;--brand:#8b5cf6;--brand2:#22d3ee;
  --ok:#4ade80;--bad:#fb7185;--warn:#fbbf24;--blue:#60a5fa;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:
  radial-gradient(circle at top left,rgba(139,92,246,.18),transparent 32%),
  radial-gradient(circle at top right,rgba(34,211,238,.12),transparent 28%),
  var(--bg);color:var(--text);font-family:Inter,Arial,sans-serif}}
.wrap{{display:flex;min-height:100vh}}
.side{{width:285px;background:rgba(15,23,42,.92);padding:18px;position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid var(--line);backdrop-filter:blur(10px)}}
.brand{{font-size:23px;font-weight:950;margin-bottom:6px;letter-spacing:.2px}}
.brand-sub{{font-size:12px;color:var(--muted);margin-bottom:18px}}
.nav-group{{color:#64748b;text-transform:uppercase;font-size:11px;font-weight:900;letter-spacing:.12em;margin:18px 0 7px}}
.side a{{display:flex;align-items:center;gap:8px;color:#cbd5e1;text-decoration:none;padding:10px 12px;border-radius:14px;margin:4px 0;border:1px solid transparent}}
.side a:hover{{background:#1e293b;color:#fff;border-color:#334155;transform:translateX(2px)}}
.main{{flex:1;padding:28px;min-width:0}}
.topbar{{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:20px}}
h1{{margin:0;font-size:30px;letter-spacing:-.03em}}
.card{{background:linear-gradient(180deg,rgba(17,24,39,.96),rgba(11,18,32,.96));border:1px solid var(--line);border-radius:22px;padding:18px;margin-bottom:16px;box-shadow:0 18px 50px rgba(0,0,0,.26)}}
.card h3{{margin-top:0;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.stat{{font-size:30px;font-weight:950;letter-spacing:-.04em}}
.muted{{color:var(--muted)}}
.pill{{display:inline-flex;align-items:center;gap:6px;border:1px solid #334155;background:#0b1220;border-radius:999px;padding:6px 10px;color:#cbd5e1;font-size:12px}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}.warn{{color:var(--warn)}}.info{{color:var(--blue)}}
table{{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:14px}}
th{{color:#cbd5e1;background:#0b1220;font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
td,th{{border-bottom:1px solid var(--line);padding:10px;text-align:left;vertical-align:top}}
tr:hover td{{background:rgba(148,163,184,.04)}}
input,select,button,textarea{{padding:10px;border-radius:12px;border:1px solid #334155;background:#020617;color:#fff;box-sizing:border-box}}
textarea{{font-family:inherit}}
button,.btn{{background:linear-gradient(135deg,var(--brand),#6d28d9);color:white;text-decoration:none;border:0;display:inline-block;padding:10px 14px;border-radius:13px;font-weight:800;cursor:pointer}}
button:hover,.btn:hover{{filter:brightness(1.12)}}
code{{background:#020617;border:1px solid #1f2937;border-radius:8px;padding:2px 6px;color:#e2e8f0}}
.kpi-good{{border-left:4px solid var(--ok)}}.kpi-warn{{border-left:4px solid var(--warn)}}.kpi-bad{{border-left:4px solid var(--bad)}}.kpi-info{{border-left:4px solid var(--blue)}}
@media(max-width:900px){{.wrap{{display:block}}.side{{width:100%;height:auto;position:relative}}.main{{padding:18px}}}}
</style></head><body><div class="wrap"><aside class="side"><div class="brand">NM System V9</div><div class="brand-sub">Unified Control Dashboard</div>{links}</aside><main class="main"><div class="topbar"><h1>{escape(title)}</h1><span class="pill">Guild {int(guild_id) if guild_id else "Default"}</span></div>{body}</main></div></body></html>"""
