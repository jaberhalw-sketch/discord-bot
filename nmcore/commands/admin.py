import os
import discord
from nmcore.config import DB_FILE
from nmcore.services.settings import set_system_enabled, all_toggles, set_coin_name, update_channel
from nmcore.services.activity import log_event
from nmcore.services.log_channels import LOG_CHANNELS, set_log_channel, get_log_channel, all_log_channels
from nmcore.services.diagnostics import system_status
from nmcore.services import antiraid
from nmcore.services import security, memory_status, log_mapping_status
from nmcore.ui import embed, success, error


async def find_or_create_category(guild, name="NM LOGS"):
    for cat in guild.categories:
        if cat.name.lower() == name.lower():
            return cat, False

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            read_message_history=True,
            manage_channels=True
        ),
    }

    return await guild.create_category(name, overwrites=overwrites, reason="NM System logs setup"), True


async def find_or_create_text_channel(guild, category, name, topic):
    for ch in guild.text_channels:
        if ch.name.lower() == name.lower():
            if ch.category_id != category.id:
                try:
                    await ch.edit(category=category, reason="NM System logs setup")
                except Exception:
                    pass
            return ch, False

    ch = await guild.create_text_channel(
        name,
        category=category,
        topic=topic,
        reason="NM System logs setup"
    )
    return ch, True


async def send_to_log(ctx, log_key, title, description, color="info"):
    try:
        ch_id = get_log_channel(ctx.guild.id, log_key)
        if not ch_id:
            return False

        ch = ctx.guild.get_channel(int(ch_id))
        if not ch:
            return False

        await ch.send(embed=embed(title, description, color, ctx.author))
        return True
    except Exception:
        return False


def yes_no(v):
    return "✅" if v else "❌"


def setup(bot):
    @bot.command(name="بنق")
    async def ping(ctx):
        await ctx.reply(embed=embed("🏓 Pong", "NM System شغال وجاهز.", "ok", ctx.author))

    @bot.command(name="مساعدة")
    async def help_cmd(ctx):
        text = """
> استخدم الأوامر التالية لإدارة نظامك:

**💰 Economy**
`!رصيدي` `!راتب` `!تحويل @user amount` `!الغني`

**🎰 Casino**
`!حظ amount` `!دبل amount` `!سلوت amount` `!وجه amount` `!bj amount`

**📊 Levels**
`!لفلي` `!ترتيب`

**🏘️ Real Estate**
`!عقارات` `!شراء_عقار ID` `!ايجار` `!عقاراتي`

**🛒 Shop**
`!متجر` `!شراء item_key` `!صندوق 1000`

**🎁 Giveaways**
`!قيف` `!دخول_قيف ID` `!انشاء_قيف 1 Nitro` `!سحب_فائز ID`

**🛡️ Moderation**
`!تحذير @user reason` `!تحذيرات @user` `!مسح_تحذيرات @user`

**⚙️ Admin**
`!قفل economy` `!فتح economy` `!اعداد_عملة NAME`
`!تجهيز_اللوقات` `!حالة_الحماية` `!تقرير_الأمان` `!حالة_الإعداد` `!حالة_النظام` `!فحص_الصلاحيات` `!اختبار_اللوقات` `!داشبورد`
"""
        await ctx.reply(embed=embed("📘 NM System Command Center", text, "purple", ctx.author))

    @bot.command(name="قفل")
    async def disable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_system_enabled(ctx.guild.id, system_key, False)
        await ctx.reply(embed=embed("🔒 تم قفل النظام", f"النظام: `{system_key}`", "warn", ctx.author))

    @bot.command(name="فتح")
    async def enable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_system_enabled(ctx.guild.id, system_key, True)
        await ctx.reply(embed=success("تم فتح النظام", f"النظام: `{system_key}`", ctx.author))

    @bot.command(name="الانظمة")
    async def systems(ctx):
        data = all_toggles(ctx.guild.id)
        lines = [f"{'✅' if v else '❌'} `{k}`" for k, v in data.items()]
        await ctx.reply(embed=embed("⚙️ حالة الأنظمة", "\n".join(lines), "info", ctx.author))

    @bot.command(name="اعداد_عملة")
    async def coin(ctx, *, name:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_coin_name(ctx.guild.id, name)
        await ctx.reply(embed=success("تم تغيير اسم العملة", f"الاسم الجديد: **{name}**", ctx.author))


    @bot.command(name="داشبورد", aliases=["dashboard", "لوحة"])
    async def dashboard_link(ctx):
        base = (os.getenv("DASHBOARD_BASE_URL", "") or "").rstrip("/")
        if not base:
            await ctx.reply(embed=error("رابط الداشبورد غير مضبوط", "تأكد من متغير DASHBOARD_BASE_URL في Railway.", ctx.author))
            return

        g = ctx.guild.id
        text = (
            f"**Dashboard:** {base}/dashboard?guild_id={g}\n"
            f"**Settings:** {base}/dashboard/settings?guild_id={g}\n"
            f"**Logs:** {base}/dashboard/logs?guild_id={g}\n"
            f"**Money Tracker:** {base}/dashboard/money-tracker?guild_id={g}"
        )
        await ctx.reply(embed=embed("🌐 روابط الداشبورد", text, "info", ctx.author))

    @bot.command(name="حالة_الإعداد", aliases=["setup_status", "setup"])
    async def setup_status(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        s = system_status(ctx.guild)
        mem = s["memory"]
        logs = s["logs"]
        gs = s["guild_settings"]
        perms = s["permissions"]

        checks = []
        checks.append(f"{yes_no(mem['persistent_path'])} Memory path `/data`")
        checks.append(f"{yes_no(logs['mapped'] == logs['total'])} Organized log rooms `{logs['mapped']}/{logs['total']}`")
        checks.append(f"{yes_no(bool(gs.get('commands_channel_id')))} Commands channel set")
        checks.append(f"{yes_no(bool(gs.get('gambling_channel_id')))} Gambling channel set")
        checks.append(f"{yes_no(perms.get('view_audit_log'))} View Audit Log")
        checks.append(f"{yes_no(perms.get('manage_channels'))} Manage Channels")
        checks.append(f"{yes_no(perms.get('manage_messages'))} Manage Messages")
        checks.append(f"{yes_no(perms.get('embed_links'))} Embed Links")

        base = (os.getenv("DASHBOARD_BASE_URL", "") or "").rstrip("/")
        dash_link = f"{base}/dashboard/settings?guild_id={ctx.guild.id}" if base else "DASHBOARD_BASE_URL not set"

        e = embed(
            "🧩 حالة إعداد NM System",
            "\n".join(checks),
            "ok" if all(("✅" in c) for c in checks) else "warn",
            ctx.author
        )
        e.add_field(name="Dashboard Settings", value=dash_link, inline=False)
        e.add_field(name="DB", value=f"`{mem['db_file']}`\nSize: `{mem['db_size_text']}`", inline=False)

        await ctx.reply(embed=e)




    @bot.command(name="تقرير_الأمان", aliases=["security_report", "risk"])
    async def security_report(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        report = security.risk_report(ctx.guild)

        issues = report["issues"][:8]
        issue_text = "\n".join(f"- {x}" for x in issues) if issues else "ما فيه مشاكل كبيرة واضحة."

        e = embed(
            "🛡️ Security Report",
            f"Score: **{report['score']}/100**\nRisk: **{report['label']}**\n\n{issue_text}",
            "ok" if report["score"] >= 85 else "warn" if report["score"] >= 65 else "bad",
            ctx.author
        )

        e.add_field(name="Active Warnings", value=str(report["counts"]["active_warnings"]), inline=True)
        e.add_field(name="Anti-Raid Events", value=str(report["counts"]["antiraid_events"]), inline=True)
        e.add_field(name="Protection Events", value=str(report["counts"]["protection_events"]), inline=True)
        e.add_field(name="Dangerous Roles", value=str(len(report["roles"])), inline=True)

        await ctx.reply(embed=e)


    @bot.command(name="حالة_الحماية", aliases=["protection_status", "antiraid_status"])
    async def protection_status(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        ar = antiraid.get_settings(ctx.guild.id)
        summary = antiraid.settings_summary(ctx.guild.id)

        lines = [
            f"{yes_no(ar.get('enabled'))} Anti-Raid Enabled",
            f"{yes_no(ar.get('anti_kick'))} Anti Kick",
            f"{yes_no(ar.get('anti_ban'))} Anti Ban",
            f"{yes_no(ar.get('anti_role_delete'))} Anti Role Delete",
            f"{yes_no(ar.get('anti_role_update'))} Anti Role Edit",
            f"{yes_no(ar.get('dangerous_role_protection'))} Dangerous Role Permissions",
            f"{yes_no(ar.get('anti_member_role_update'))} Anti Member Role Edit",
            f"{yes_no(ar.get('anti_channel_create'))} Anti Channel Create",
            f"{yes_no(ar.get('anti_channel_delete'))} Anti Channel Delete",
            f"{yes_no(ar.get('anti_channel_update'))} Anti Channel Edit",
            f"{yes_no(ar.get('anti_webhook_create'))} Anti Webhook Create",
            f"{yes_no(ar.get('anti_webhook_update'))} Anti Webhook Update",
            f"{yes_no(ar.get('anti_webhook_delete'))} Anti Webhook Delete",
            f"{yes_no(ar.get('anti_bot_add'))} Anti Bot Add",
        ]

        e = embed("🛡️ حالة الحماية / Anti-Raid", "\n".join(lines), "info", ctx.author)
        e.add_field(name="Threshold", value=f"{summary['threshold']} actions / {summary['window']}s", inline=True)
        e.add_field(name="Punish", value=str(summary["punish_action"]), inline=True)
        await ctx.reply(embed=e)


    @bot.command(name="تجهيز_اللوقات", aliases=["setup_logs", "لوقات"])
    async def setup_logs(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        me = ctx.guild.me
        missing = []

        if not me.guild_permissions.manage_channels:
            missing.append("Manage Channels")
        if not me.guild_permissions.view_audit_log:
            missing.append("View Audit Log")
        if not me.guild_permissions.embed_links:
            missing.append("Embed Links")

        if missing:
            await ctx.reply(embed=embed(
                "⚠️ صلاحيات ناقصة",
                "يفضل تعطي البوت:\n" + "\n".join(f"- {m}" for m in missing) + "\n\nيقدر يكمل إذا عنده Manage Channels، لكن بعض التفاصيل مثل سبب الطرد تحتاج View Audit Log.",
                "warn",
                ctx.author
            ))

            if not me.guild_permissions.manage_channels:
                return

        status = await ctx.reply(embed=embed(
            "🛠️ جاري تجهيز اللوقات",
            "بنشئ Category ورومات اللوقات المنظمة إذا مو موجودة...",
            "warn",
            ctx.author
        ))

        try:
            category, cat_created = await find_or_create_category(ctx.guild, "NM LOGS")
            created = []
            existing = []
            channel_map = {}

            for key, (name, topic) in LOG_CHANNELS.items():
                ch, was_created = await find_or_create_text_channel(ctx.guild, category, name, topic)
                channel_map[key] = ch
                set_log_channel(ctx.guild.id, key, ch.id)

                if was_created:
                    created.append(f"{ch.mention} `({key})`")
                else:
                    existing.append(f"{ch.mention} `({key})`")

            main_log_channel = channel_map.get("general")
            if main_log_channel:
                update_channel(ctx.guild.id, "logs_channel_id", main_log_channel.id)

            log_event(
                ctx.guild.id,
                "setup_logs",
                ctx.author.id,
                ctx.author.display_name,
                ctx.channel.id,
                ctx.channel.name,
                "Advanced logs setup completed",
                f"Category={category.id}, MainLog={main_log_channel.id if main_log_channel else 0}"
            )

            e = success(
                "تم تجهيز رومات اللوقات",
                f"Category: **{category.name}**\nMain Logs Channel: {main_log_channel.mention if main_log_channel else 'None'}",
                ctx.author
            )

            e.add_field(
                name="تم إنشاؤها",
                value="\n".join(created[:15]) if created else "ما فيه جديد، كلها موجودة.",
                inline=False
            )
            e.add_field(
                name="كانت موجودة",
                value="\n".join(existing[:15]) if existing else "ولا روم كان موجود قبل.",
                inline=False
            )
            e.add_field(
                name="Dashboard Setting",
                value=f"`logs_channel_id` تم ضبطه على {main_log_channel.mention if main_log_channel else 'None'}",
                inline=False
            )

            try:
                await status.edit(embed=e)
            except Exception:
                await ctx.send(embed=e)

            if main_log_channel:
                await main_log_channel.send(embed=embed(
                    "✅ NM Advanced Logs Ready",
                    f"تم تجهيز اللوقات بواسطة {ctx.author.mention}.\nكل نوع لوق صار له روم مرتب.",
                    "ok",
                    ctx.author
                ))

        except discord.Forbidden:
            await ctx.reply(embed=error(
                "فشل تجهيز اللوقات",
                "البوت ما عنده صلاحيات كافية. عطه Manage Channels و Send Messages و Embed Links.",
                ctx.author
            ))
        except Exception as e:
            await ctx.reply(embed=error(
                "فشل تجهيز اللوقات",
                f"`{type(e).__name__}: {e}`",
                ctx.author
            ))

    @bot.command(name="حالة_النظام", aliases=["system_status", "status"])
    async def system_status_cmd(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        s = system_status(ctx.guild)
        mem = s["memory"]
        logs = s["logs"]
        counts = mem["counts"]

        e = embed("🩺 حالة NM System", "فحص سريع للذاكرة واللوقات والأنظمة.", "info", ctx.author)

        e.add_field(
            name="Memory",
            value=(
                f"Persistent Path: {yes_no(mem['persistent_path'])}\n"
                f"DB Size: `{mem['db_size_text']}`\n"
                f"DB File: `{mem['db_file']}`"
            ),
            inline=False
        )

        e.add_field(
            name="Records",
            value=(
                f"Balances: `{counts.get('balances', 0)}`\n"
                f"Ledger: `{counts.get('money_ledger', 0)}`\n"
                f"Warnings: `{counts.get('warnings', 0)}`\n"
                f"Logs: `{counts.get('log_events', 0)}`\n"
                f"Live: `{counts.get('live_activity', 0)}`"
            ),
            inline=True
        )

        e.add_field(
            name="Log Rooms",
            value=f"`{logs['mapped']}/{logs['total']}` mapped",
            inline=True
        )

        toggles = s["toggles"]
        e.add_field(
            name="Systems",
            value="\n".join([f"{yes_no(v)} `{k}`" for k, v in toggles.items()])[:1000],
            inline=False
        )

        await ctx.reply(embed=e)

    @bot.command(name="فحص_الصلاحيات", aliases=["check_perms", "perms"])
    async def check_permissions(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        s = system_status(ctx.guild)
        perms = s["permissions"]

        lines = [f"{yes_no(v)} `{k}`" for k, v in perms.items()]
        await ctx.reply(embed=embed(
            "🔐 فحص صلاحيات البوت",
            "\n".join(lines),
            "ok" if all(perms.values()) else "warn",
            ctx.author
        ))

    @bot.command(name="اختبار_اللوقات", aliases=["test_logs"])
    async def test_logs(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return

        sent = []
        failed = []

        for key, (name, topic) in LOG_CHANNELS.items():
            ok = await send_to_log(
                ctx,
                key,
                f"🧪 Test Log: {key}",
                f"تم اختبار روم `{name}` بواسطة {ctx.author.mention}.",
                "info"
            )

            if ok:
                sent.append(key)
            else:
                failed.append(key)

        e = embed("🧪 اختبار اللوقات", "تم إرسال رسائل اختبار للرومات المربوطة.", "info", ctx.author)
        e.add_field(name="نجح", value=", ".join(sent) if sent else "None", inline=False)
        e.add_field(name="فشل", value=", ".join(failed) if failed else "None", inline=False)

        await ctx.reply(embed=e)
