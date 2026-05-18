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

def page(title, body, guild_id=0):
    q=f"?guild_id={int(guild_id)}" if guild_id else ""
    nav=[
        ("🏠 Overview",f"/dashboard{q}"),("💰 Economy",f"/dashboard/economy{q}"),("🧾 Money Tracker",f"/dashboard/money-tracker{q}"),
        ("🎰 Casino",f"/dashboard/casino{q}"),("📊 Levels",f"/dashboard/levels{q}"),("🏘️ Real Estate",f"/dashboard/real-estate{q}"),
        ("⚠️ Warnings",f"/dashboard/warnings{q}"),("🛡️ Protection",f"/dashboard/protection{q}"),("📜 Logs",f"/dashboard/logs{q}"),
        ("🎁 Giveaways",f"/dashboard/giveaways{q}"),("🛒 Shop",f"/dashboard/shop{q}"),("🟢 Live",f"/dashboard/live{q}"),
        ("⚙️ Settings",f"/dashboard/settings{q}"),("🩺 Health",f"/dashboard/health{q}")
    ]
    links="".join(f"<a href='{h}'>{escape(t)}</a>" for t,h in nav)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body{{margin:0;background:#070b14;color:#e5e7eb;font-family:Arial,sans-serif}}
.wrap{{display:flex;min-height:100vh}}.side{{width:260px;background:#0f172a;padding:18px;box-sizing:border-box;position:sticky;top:0;height:100vh;overflow:auto}}
.brand{{font-size:22px;font-weight:900;margin-bottom:16px}}.side a{{display:block;color:#cbd5e1;text-decoration:none;padding:10px;border-radius:12px;margin:4px 0}}.side a:hover{{background:#1e293b;color:#fff}}
.main{{flex:1;padding:28px}}.card{{background:#111827;border:1px solid #263244;border-radius:18px;padding:18px;margin-bottom:16px;box-shadow:0 10px 30px rgba(0,0,0,.25)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
.stat{{font-size:28px;font-weight:900}}.muted{{color:#94a3b8}}table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #243044;padding:9px;text-align:left}}input,select,button{{padding:10px;border-radius:10px;border:1px solid #334155;background:#020617;color:#fff}}button,.btn{{background:#7c3aed;color:white;text-decoration:none;border:0;display:inline-block;padding:10px 14px;border-radius:12px}}.ok{{color:#4ade80}}.bad{{color:#f87171}}code{{background:#020617;border-radius:8px;padding:2px 6px}}
</style></head><body><div class="wrap"><aside class="side"><div class="brand">NM System V9</div>{links}</aside><main class="main"><h1>{escape(title)}</h1>{body}</main></div></body></html>"""
