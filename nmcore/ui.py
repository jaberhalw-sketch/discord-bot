import os
import discord
from html import escape
from nmcore.config import BOT_BRAND
from nmcore.services.settings import get_coin_name

COLORS={"ok":0x22c55e,"bad":0xef4444,"info":0x3b82f6,"warn":0xf59e0b,"purple":0x7c3aed}


def dashboard_logo_url():
    """
    Set Railway variable:
    DASHBOARD_LOGO_URL=https://...
    Recommended: use the Discord bot avatar image link.
    """
    return os.getenv("DASHBOARD_LOGO_URL", "").strip()


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
    refresh_titles = {"Live Activity": 8, "Logs": 15, "Warnings": 20, "Money Tracker": 20, "Admin Audit": 20}
    refresh_meta = f"<meta http-equiv='refresh' content='{refresh_titles.get(str(title), 0)}'>" if str(title) in refresh_titles else ""
    logo_url = dashboard_logo_url()
    logo_html = f"<img class='brand-logo' src='{escape(logo_url)}' alt='NM logo'>" if logo_url else "<div class='brand-logo-fallback'>NM</div>"

    nav_groups=[
        ("Main", [
            ("🏠 Overview",f"/dashboard{q}"),
            ("📈 Analytics",f"/dashboard/analytics{q}"),
            ("🧪 Full Check",f"/dashboard/full-check{q}"),
            ("📘 Command Center",f"/dashboard/commands{q}"),
            ("🧩 Setup Status",f"/dashboard/setup{q}"),
            ("🪄 Setup Wizard",f"/dashboard/setup-wizard{q}"),
            ("🩺 Health",f"/dashboard/health{q}"),
        ]),
        ("Money / Economy", [
            ("💰 Economy",f"/dashboard/economy{q}"),
            ("🧾 Money Tracker",f"/dashboard/money-tracker{q}"),
            ("📝 Post Rewards",f"/dashboard/post-rewards{q}"),
            ("🚀 Boosts",f"/dashboard/boosts{q}"),
            ("🎰 Casino",f"/dashboard/casino{q}"),
            ("🎰 Casino Controls",f"/dashboard/casino-controls{q}"),
            ("🛒 Real Estate Shop",f"/dashboard/shop{q}"),
            ("🏘️ Real Estate Admin",f"/dashboard/real-estate{q}"),
            ("🏢 Companies",f"/dashboard/companies{q}"),
        ]),
        ("Community", [
            ("📊 Levels",f"/dashboard/levels{q}"),
            ("🎁 Giveaways",f"/dashboard/giveaways{q}"),
            ("👤 User Profile",f"/dashboard/user{q}"),
            ("🎭 Game Roles",f"/dashboard/game-roles{q}"),
            ("👑 Role Manager",f"/dashboard/roles{q}"),
        ]),
        ("Safety / Moderation", [
            ("⚠️ Warnings",f"/dashboard/warnings{q}"),
            ("🛡️ Protection",f"/dashboard/protection{q}"),
            ("🧨 Security",f"/dashboard/security{q}"),
            ("🛡️ Admin Audit",f"/dashboard/admin-audit{q}"),
            ("📜 Logs",f"/dashboard/logs{q}"),
            ("🟢 Live Activity",f"/dashboard/live{q}"),
        ]),
        ("Configuration", [
            ("⚙️ Settings",f"/dashboard/settings{q}"),
            ("🚪 Logout",f"/logout"),
        ]),
    ]

    links=""
    low_title = str(title or "").lower()
    for group, items in nav_groups:
        links += f"<div class='nav-group'>{escape(group)}</div>"
        for t,h in items:
            active = " active" if low_title and (low_title in t.lower() or t.lower().split(' ',1)[-1] in low_title) else ""
            links += f"<a class='nav-link{active}' href='{h}'>{escape(t)}</a>"

    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
{refresh_meta}
<style>
:root{{
  --bg:#060915;--panel:#0b1020;--panel2:#11182b;--card:#0f172a;--card2:#101827;--line:#243044;
  --text:#e5e7eb;--muted:#94a3b8;--brand:#8b5cf6;--brand2:#22d3ee;--pink:#ec4899;
  --ok:#4ade80;--bad:#fb7185;--warn:#fbbf24;--blue:#60a5fa;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:
  radial-gradient(circle at 12% 0%,rgba(139,92,246,.30),transparent 34%),
  radial-gradient(circle at 80% 10%,rgba(34,211,238,.16),transparent 30%),
  radial-gradient(circle at 55% 100%,rgba(236,72,153,.10),transparent 26%),
  var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,Segoe UI,Arial,sans-serif}}
.wrap{{display:flex;min-height:100vh}}
.side{{width:315px;background:rgba(8,13,28,.86);padding:18px;position:sticky;top:0;height:100vh;overflow:auto;border-right:1px solid rgba(148,163,184,.16);backdrop-filter:blur(18px)}}
.brandbox{{display:flex;align-items:center;gap:13px;border:1px solid rgba(139,92,246,.35);background:linear-gradient(135deg,rgba(139,92,246,.22),rgba(34,211,238,.08));border-radius:22px;padding:14px;margin-bottom:16px}}
.brand-logo{{width:54px;height:54px;border-radius:18px;object-fit:cover;border:1px solid rgba(255,255,255,.18);box-shadow:0 14px 35px rgba(0,0,0,.28)}}
.brand-logo-fallback{{width:54px;height:54px;border-radius:18px;display:grid;place-items:center;font-weight:950;background:linear-gradient(135deg,var(--brand),var(--brand2));box-shadow:0 14px 35px rgba(0,0,0,.28)}}
.brand{{font-size:24px;font-weight:950;letter-spacing:-.04em}}
.brand-sub{{font-size:12px;color:var(--muted);margin-top:4px}}
.nav-group{{color:#64748b;text-transform:uppercase;font-size:11px;font-weight:950;letter-spacing:.14em;margin:18px 0 7px}}
.side a{{display:flex;align-items:center;gap:10px;color:#cbd5e1;text-decoration:none;padding:10px 12px;border-radius:15px;margin:4px 0;border:1px solid transparent;transition:.15s ease}}
.side a:hover{{background:#172033;color:#fff;border-color:#334155;transform:translateX(3px)}}
.side a.active{{background:linear-gradient(135deg,rgba(139,92,246,.34),rgba(34,211,238,.14));color:#fff;border-color:#475569;box-shadow:0 12px 30px rgba(139,92,246,.10)}}
.main{{flex:1;padding:28px;min-width:0}}
.topbar{{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:20px}}
h1{{margin:0;font-size:31px;letter-spacing:-.055em}}
.card{{background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(10,15,29,.94));border:1px solid rgba(148,163,184,.16);border-radius:24px;padding:18px;margin-bottom:16px;box-shadow:0 22px 60px rgba(0,0,0,.30)}}
.card h3{{margin-top:0;margin-bottom:12px;letter-spacing:-.02em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}
.stat{{font-size:31px;font-weight:950;letter-spacing:-.055em}}
.muted{{color:var(--muted)}}
.pill{{display:inline-flex;align-items:center;gap:6px;border:1px solid #334155;background:#0b1220;border-radius:999px;padding:7px 11px;color:#cbd5e1;font-size:12px}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}.warn{{color:var(--warn)}}.info{{color:var(--blue)}}
.pill.ok{{border-color:rgba(74,222,128,.35);color:var(--ok)}}.pill.bad{{border-color:rgba(251,113,133,.35);color:var(--bad)}}.pill.warn{{border-color:rgba(251,191,36,.35);color:var(--warn)}}.pill.info{{border-color:rgba(96,165,250,.35);color:var(--blue)}}
table{{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:16px}}
th{{color:#cbd5e1;background:#090f1d;font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
td,th{{border-bottom:1px solid rgba(148,163,184,.12);padding:11px;text-align:left;vertical-align:top}}
tr:hover td{{background:rgba(148,163,184,.045)}}
input,select,button,textarea{{padding:11px;border-radius:14px;border:1px solid #334155;background:#020617;color:#fff;box-sizing:border-box}}
textarea{{font-family:inherit}}
button,.btn{{background:linear-gradient(135deg,var(--brand),#6d28d9);color:white;text-decoration:none;border:0;display:inline-block;padding:10px 14px;border-radius:14px;font-weight:850;cursor:pointer;box-shadow:0 12px 28px rgba(139,92,246,.18)}}
button:hover,.btn:hover{{filter:brightness(1.12)}}
code{{background:#020617;border:1px solid #1f2937;border-radius:9px;padding:2px 6px;color:#e2e8f0}}
.avatar{{width:38px;height:38px;border-radius:14px;object-fit:cover;border:1px solid #334155;background:#111827}}
.avatar-lg{{width:70px;height:70px;border-radius:22px;object-fit:cover;border:1px solid #334155;background:#111827}}
.userline{{display:flex;align-items:center;gap:10px}}
.server-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
.server-card{{display:flex;gap:12px;align-items:center;text-decoration:none;color:var(--text);background:linear-gradient(180deg,rgba(17,24,39,.96),rgba(11,18,32,.96));border:1px solid rgba(148,163,184,.16);border-radius:24px;padding:16px;box-shadow:0 18px 50px rgba(0,0,0,.24)}}
.server-card:hover{{border-color:rgba(139,92,246,.55);transform:translateY(-2px)}}
.kpi-good{{border-left:4px solid var(--ok)}}.kpi-warn{{border-left:4px solid var(--warn)}}.kpi-bad{{border-left:4px solid var(--bad)}}.kpi-info{{border-left:4px solid var(--blue)}}
@media(max-width:900px){{.wrap{{display:block}}.side{{width:100%;height:auto;position:relative}}.main{{padding:18px}}}}
</style></head><body><div class="wrap"><aside class="side"><div class="brandbox">{logo_html}<div><div class="brand">NM System V9</div><div class="brand-sub">Pro Control Dashboard</div></div></div>{links}</aside><main class="main"><div class="topbar"><h1>{escape(title)}</h1><span class="pill">Guild {int(guild_id) if guild_id else "Select Server"}</span></div>{body}</main></div></body></html>"""
