import os
import io
import time
import json
import base64
import urllib.request
import urllib.error

import discord
from discord.ext import commands

from nmcore.db import db
from nmcore.ui import embed
from nmcore.services.activity import log_event
from nmcore.services.protection import contains_bad, get_settings as get_protection_settings

BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", os.getenv("NM_BOT_OWNER_ID", "881722045031915521")))
OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"

DEFAULTS = {
    "enabled": 1,
    "image_channel_id": int(os.getenv("AI_IMAGE_CHANNEL_ID", "0") or 0),
    "log_channel_id": int(os.getenv("AI_IMAGE_LOG_CHANNEL_ID", "0") or 0),
    "daily_limit_per_user": int(os.getenv("AI_IMAGE_DAILY_LIMIT_PER_USER", "5") or 5),
    "daily_limit_server": int(os.getenv("AI_IMAGE_DAILY_LIMIT_SERVER", "30") or 30),
    "cooldown_seconds": int(os.getenv("AI_IMAGE_COOLDOWN_SECONDS", "60") or 60),
    "image_size": os.getenv("AI_IMAGE_SIZE", "1024x1024"),
    "image_quality": os.getenv("AI_IMAGE_QUALITY", "medium"),
    "image_model": os.getenv("AI_IMAGE_MODEL", "gpt-image-1"),
    "allowed_role_ids": os.getenv("AI_IMAGE_ALLOWED_ROLE_IDS", ""),
    "block_bad_prompts": int(os.getenv("AI_IMAGE_BLOCK_BAD_PROMPTS", "1") or 1),
}

_generation_cache = {}


def ensure_schema():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS ai_image_settings (
        guild_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        image_channel_id INTEGER DEFAULT 0,
        log_channel_id INTEGER DEFAULT 0,
        daily_limit_per_user INTEGER DEFAULT 5,
        daily_limit_server INTEGER DEFAULT 30,
        cooldown_seconds INTEGER DEFAULT 60,
        image_size TEXT DEFAULT '1024x1024',
        image_quality TEXT DEFAULT 'medium',
        image_model TEXT DEFAULT 'gpt-image-1',
        allowed_role_ids TEXT DEFAULT '',
        block_bad_prompts INTEGER DEFAULT 1,
        updated_at INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS ai_image_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        user_name TEXT DEFAULT '',
        channel_id INTEGER DEFAULT 0,
        prompt TEXT DEFAULT '',
        action_type TEXT DEFAULT 'generate',
        image_model TEXT DEFAULT 'gpt-image-1',
        image_size TEXT DEFAULT '1024x1024',
        image_quality TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'ok',
        error_message TEXT DEFAULT '',
        created_at INTEGER NOT NULL
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_image_logs_guild_time ON ai_image_logs(guild_id, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_image_logs_user_time ON ai_image_logs(guild_id, user_id, created_at DESC)")
    conn.commit()
    conn.close()


def get_ai_settings(guild_id: int) -> dict:
    ensure_schema()
    gid = int(guild_id)
    now = int(time.time())
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO ai_image_settings (guild_id, updated_at) VALUES (?,?)", (gid, now))
    conn.commit()
    cur.execute("SELECT * FROM ai_image_settings WHERE guild_id=?", (gid,))
    row = cur.fetchone()
    conn.close()
    data = dict(row) if row else {}
    for k, v in DEFAULTS.items():
        if data.get(k) in (None, ""):
            data[k] = v
    # If DB channel is 0 but env has channel, use env
    if int(data.get("image_channel_id") or 0) == 0 and int(DEFAULTS["image_channel_id"] or 0):
        data["image_channel_id"] = int(DEFAULTS["image_channel_id"])
    return data


def update_ai_settings(guild_id: int, **updates):
    ensure_schema()
    allowed = set(DEFAULTS.keys())
    vals = {k: v for k, v in updates.items() if k in allowed}
    if not vals:
        return
    conn = db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO ai_image_settings (guild_id, updated_at) VALUES (?,?)", (int(guild_id), int(time.time())))
    sets = ", ".join(f"{k}=?" for k in vals) + ", updated_at=?"
    cur.execute(f"UPDATE ai_image_settings SET {sets} WHERE guild_id=?", list(vals.values()) + [int(time.time()), int(guild_id)])
    conn.commit()
    conn.close()


def day_start_ts() -> int:
    now = int(time.time())
    return now - (now % 86400)


def int_csv(text: str) -> set[int]:
    out = set()
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def is_privileged(ctx) -> bool:
    return int(ctx.author.id) == BOT_OWNER_ID or int(ctx.author.id) == int(getattr(ctx.guild, "owner_id", 0) or 0)


def has_allowed_role(ctx, settings: dict) -> bool:
    allowed = int_csv(settings.get("allowed_role_ids", ""))
    if not allowed:
        return True
    return any(int(r.id) in allowed for r in getattr(ctx.author, "roles", []))


def usage_counts(guild_id: int, user_id: int):
    ensure_schema()
    start = day_start_ts()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM ai_image_logs WHERE guild_id=? AND user_id=? AND created_at>=? AND status='ok'", (int(guild_id), int(user_id), start))
    user_count = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT COUNT(*) c FROM ai_image_logs WHERE guild_id=? AND created_at>=? AND status='ok'", (int(guild_id), start))
    server_count = int(cur.fetchone()["c"] or 0)
    cur.execute("SELECT created_at FROM ai_image_logs WHERE guild_id=? AND user_id=? AND status='ok' ORDER BY id DESC LIMIT 1", (int(guild_id), int(user_id)))
    row = cur.fetchone()
    conn.close()
    last_ts = int(row["created_at"] or 0) if row else 0
    return user_count, server_count, last_ts


def log_ai(guild_id: int, user_id: int, user_name: str, channel_id: int, prompt: str, action_type: str, settings: dict, status: str, error_message: str = ""):
    ensure_schema()
    conn = db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO ai_image_logs
    (guild_id,user_id,user_name,channel_id,prompt,action_type,image_model,image_size,image_quality,status,error_message,created_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
        int(guild_id), int(user_id), str(user_name)[:120], int(channel_id or 0), str(prompt)[:4000],
        str(action_type)[:40], str(settings.get("image_model", "gpt-image-1"))[:80],
        str(settings.get("image_size", "1024x1024"))[:40], str(settings.get("image_quality", "medium"))[:40],
        str(status)[:20], str(error_message)[:700], int(time.time())
    ))
    conn.commit()
    conn.close()


def prompt_is_blocked(guild_id: int, prompt: str, settings: dict) -> bool:
    if not int(settings.get("block_bad_prompts", 1) or 0):
        return False
    try:
        prot = get_protection_settings(guild_id)
        words = [w.strip() for w in str(prot.get("bad_words") or "").split(",") if w.strip()]
        return bool(words and contains_bad(prompt, words))
    except Exception:
        return False


def openai_generate(prompt: str, settings: dict) -> bytes:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing in Railway Variables.")
    payload = {
        "model": str(settings.get("image_model") or "gpt-image-1"),
        "prompt": str(prompt),
        "size": str(settings.get("image_size") or "1024x1024"),
        "quality": str(settings.get("image_quality") or "medium"),
    }
    req = urllib.request.Request(
        OPENAI_IMAGES_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            detail = str(e)
        raise RuntimeError(f"OpenAI API error: {detail[:900]}")
    item = (data.get("data") or [{}])[0]
    b64 = item.get("b64_json")
    if not b64:
        raise RuntimeError("OpenAI did not return image data.")
    return base64.b64decode(b64)


class AIImageView(discord.ui.View):
    def __init__(self, request_id: str):
        super().__init__(timeout=1800)
        self.request_id = request_id

    async def rerun(self, interaction: discord.Interaction, action_type: str, hd: bool = False):
        meta = _generation_cache.get(self.request_id)
        if not meta:
            await interaction.response.send_message("❌ انتهت بيانات الطلب، اكتب الأمر من جديد.", ephemeral=True)
            return
        if int(interaction.user.id) not in {int(meta["user_id"]), BOT_OWNER_ID}:
            await interaction.response.send_message("❌ الزر لصاحب الطلب فقط.", ephemeral=True)
            return

        settings = dict(meta["settings"])
        if hd:
            settings["image_quality"] = "high"
        prompt = meta["prompt"]
        if action_type == "variant":
            prompt = "Create a new alternative variation of this image request: " + prompt

        await interaction.response.defer(thinking=True)
        try:
            raw = openai_generate(prompt, settings)
            file = discord.File(io.BytesIO(raw), filename="ai_image.png")
            e = embed(
                "🖼️ AI Image",
                f"**Generated for:** {interaction.user.mention}\n**Prompt:** {meta['prompt']}\n**Mode:** `{action_type}`",
                "purple",
                interaction.user
            )
            e.set_image(url="attachment://ai_image.png")
            await interaction.followup.send(embed=e, file=file, view=AIImageView(self.request_id))
            log_ai(meta["guild_id"], interaction.user.id, str(interaction.user), meta["channel_id"], meta["prompt"], action_type, settings, "ok")
        except Exception as ex:
            log_ai(meta["guild_id"], interaction.user.id, str(interaction.user), meta["channel_id"], meta["prompt"], action_type, settings, "error", str(ex))
            await interaction.followup.send(embed=embed("❌ AI Image Failed", str(ex), "bad", interaction.user), ephemeral=True)

    @discord.ui.button(label="🔁 إعادة توليد", style=discord.ButtonStyle.primary)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rerun(interaction, "regenerate")

    @discord.ui.button(label="🎨 نسخة ثانية", style=discord.ButtonStyle.secondary)
    async def variant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rerun(interaction, "variant")

    @discord.ui.button(label="📏 HD", style=discord.ButtonStyle.success)
    async def hd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.rerun(interaction, "hd", hd=True)


async def generate_image_command(ctx, prompt: str):
    if not ctx.guild:
        return
    settings = get_ai_settings(ctx.guild.id)

    if not int(settings.get("enabled", 1) or 0):
        await ctx.reply(embed=embed("🔒 AI Images Disabled", "نظام الصور مقفل.", "warn", ctx.author))
        return

    channel_id = int(settings.get("image_channel_id") or 0)
    if channel_id and int(ctx.channel.id) != channel_id:
        await ctx.reply(embed=embed("📍 الروم غير صحيح", f"استخدم الأمر هنا فقط: <#{channel_id}>", "warn", ctx.author))
        return

    if not has_allowed_role(ctx, settings):
        await ctx.reply(embed=embed("🔒 غير مسموح", "ما عندك الرتبة المسموح لها تستخدم صور AI.", "bad", ctx.author))
        return

    prompt = str(prompt or "").strip()
    if not prompt:
        await ctx.reply(embed=embed("⚠️ اكتب وصف الصورة", "مثال: `!صورة قطة لابسة شماغ بأسلوب واقعي`", "warn", ctx.author))
        return

    if prompt_is_blocked(ctx.guild.id, prompt, settings):
        await ctx.reply(embed=embed("🛡️ Prompt Blocked", "البرومبت مرفوض بسبب الحماية.", "bad", ctx.author))
        return

    privileged = is_privileged(ctx)
    user_count, server_count, last_ts = usage_counts(ctx.guild.id, ctx.author.id)

    if not privileged:
        cooldown = int(settings.get("cooldown_seconds") or 60)
        remaining = cooldown - (int(time.time()) - int(last_ts or 0))
        if last_ts and remaining > 0:
            await ctx.reply(embed=embed("⏳ Cooldown", f"انتظر **{remaining} ثانية** قبل طلب صورة جديدة.", "warn", ctx.author))
            return

        if user_count >= int(settings.get("daily_limit_per_user") or 5):
            await ctx.reply(embed=embed("📛 Daily Limit", "وصلت حدك اليومي لطلبات الصور.", "bad", ctx.author))
            return

        if server_count >= int(settings.get("daily_limit_server") or 30):
            await ctx.reply(embed=embed("📛 Server Limit", "السيرفر وصل الحد اليومي لطلبات الصور.", "bad", ctx.author))
            return

    loading_msg = None
    try:
        loading_msg = await ctx.reply(embed=embed(
            "⏳ جاري توليد الصورة...",
            "طلبك وصل. انتظر شوي، الصورة قاعدة تنولد الآن.",
            "warn",
            ctx.author
        ))
    except Exception:
        loading_msg = None

    try:
        raw = openai_generate(prompt, settings)
        file = discord.File(io.BytesIO(raw), filename="ai_image.png")
        e = embed(
            "🖼️ AI Image",
            f"**Generated for:** {ctx.author.mention}\n**Prompt:** {prompt}",
            "purple",
            ctx.author
        )
        e.add_field(name="Quality", value=str(settings.get("image_quality", "medium")), inline=True)
        e.add_field(name="Size", value=str(settings.get("image_size", "1024x1024")), inline=True)
        e.set_image(url="attachment://ai_image.png")

        request_id = f"{ctx.guild.id}:{ctx.author.id}:{int(time.time()*1000)}"
        _generation_cache[request_id] = {
            "guild_id": int(ctx.guild.id),
            "channel_id": int(ctx.channel.id),
            "user_id": int(ctx.author.id),
            "prompt": prompt,
            "settings": dict(settings),
        }

        await ctx.reply(embed=e, file=file, view=AIImageView(request_id))
        if loading_msg:
            try:
                await loading_msg.edit(embed=embed(
                    "✅ تم توليد الصورة",
                    "الصورة جاهزة تحت.",
                    "ok",
                    ctx.author
                ))
            except Exception:
                pass

        log_ai(ctx.guild.id, ctx.author.id, str(ctx.author), ctx.channel.id, prompt, "generate", settings, "ok")
        log_event(ctx.guild.id, "ai_image", ctx.author.id, ctx.author.display_name, ctx.channel.id, ctx.channel.name, "AI Image Generated", prompt[:600])

        log_channel_id = int(settings.get("log_channel_id") or 0)
        if log_channel_id:
            ch = ctx.guild.get_channel(log_channel_id)
            if ch:
                await ch.send(f"🖼️ AI Image | User: {ctx.author.mention} | Channel: {ctx.channel.mention}\nPrompt: `{prompt[:1500]}`")

    except Exception as ex:
        log_ai(ctx.guild.id, ctx.author.id, str(ctx.author), ctx.channel.id, prompt, "generate", settings, "error", str(ex))
        if loading_msg:
            try:
                await loading_msg.edit(embed=embed("❌ AI Image Failed", str(ex), "bad", ctx.author))
            except Exception:
                await ctx.reply(embed=embed("❌ AI Image Failed", str(ex), "bad", ctx.author))
        else:
            await ctx.reply(embed=embed("❌ AI Image Failed", str(ex), "bad", ctx.author))


async def _safe_generate_wrapper(ctx, prompt: str):
    try:
        await generate_image_command(ctx, prompt)
    except Exception as ex:
        msg = f"{type(ex).__name__}: {str(ex)[:1200]}"
        try:
            log_event(
                ctx.guild.id if ctx.guild else 0,
                "ai_image_command_error",
                ctx.author.id if ctx.author else 0,
                str(ctx.author) if ctx.author else "",
                ctx.channel.id if ctx.channel else 0,
                str(ctx.channel) if ctx.channel else "",
                "AI image command error",
                msg
            )
        except Exception:
            pass

        try:
            await ctx.reply(embed=embed(
                "❌ AI Image Error",
                f"طلع خطأ داخل أمر الصور:\n```text\n{msg}\n```\nارسل لي هذا الخطأ لو ما كان واضح.",
                "bad",
                ctx.author
            ))
        except Exception:
            try:
                await ctx.send(f"❌ AI Image Error: `{msg}`")
            except Exception:
                pass


def setup(bot: commands.Bot):
    ensure_schema()

    @bot.command(name="صورة")
    async def ai_image_ar(ctx, *, prompt: str = ""):
        await _safe_generate_wrapper(ctx, prompt)

    @bot.command(name="img")
    async def ai_image_en(ctx, *, prompt: str = ""):
        await _safe_generate_wrapper(ctx, prompt)

    @bot.command(name="ai_روم")
    async def ai_set_channel(ctx, channel_id: int = 0):
        if not ctx.author.guild_permissions.administrator and int(ctx.author.id) != BOT_OWNER_ID:
            await ctx.reply(embed=embed("❌ ممنوع", "تحتاج Administrator.", "bad", ctx.author))
            return
        update_ai_settings(ctx.guild.id, image_channel_id=int(channel_id or 0))
        await ctx.reply(embed=embed("✅ AI Channel Saved", f"AI Image Channel ID: `{int(channel_id or 0)}`", "ok", ctx.author))

    @bot.command(name="ai_تشغيل")
    async def ai_enable(ctx):
        if not ctx.author.guild_permissions.administrator and int(ctx.author.id) != BOT_OWNER_ID:
            await ctx.reply(embed=embed("❌ ممنوع", "تحتاج Administrator.", "bad", ctx.author))
            return
        update_ai_settings(ctx.guild.id, enabled=1)
        await ctx.reply(embed=embed("✅ AI Images Enabled", "تم تشغيل صور الـ AI.", "ok", ctx.author))

    @bot.command(name="ai_ايقاف")
    async def ai_disable(ctx):
        if not ctx.author.guild_permissions.administrator and int(ctx.author.id) != BOT_OWNER_ID:
            await ctx.reply(embed=embed("❌ ممنوع", "تحتاج Administrator.", "bad", ctx.author))
            return
        update_ai_settings(ctx.guild.id, enabled=0)
        await ctx.reply(embed=embed("🔒 AI Images Disabled", "تم إيقاف صور الـ AI.", "warn", ctx.author))

    @bot.command(name="ai_صور")
    async def ai_status(ctx):
        s = get_ai_settings(ctx.guild.id)
        desc = (
            f"Enabled: `{bool(int(s.get('enabled', 1) or 0))}`\n"
            f"Channel: <#{int(s.get('image_channel_id') or 0)}> (`{int(s.get('image_channel_id') or 0)}`)\n"
            f"Cooldown: `{int(s.get('cooldown_seconds') or 60)}s`\n"
            f"Daily/User: `{int(s.get('daily_limit_per_user') or 5)}`\n"
            f"Daily/Server: `{int(s.get('daily_limit_server') or 30)}`\n"
            f"Quality: `{s.get('image_quality')}`\n"
            f"Size: `{s.get('image_size')}`"
        )
        await ctx.reply(embed=embed("🖼️ AI Images Status", desc, "info", ctx.author))
