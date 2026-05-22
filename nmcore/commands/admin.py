import discord
from nmcore.services.settings import set_system_enabled, all_toggles, set_coin_name, update_channel
from nmcore.services.activity import log_event
from nmcore.services.log_channels import LOG_CHANNELS, set_log_channel
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
`!تجهيز_اللوقات`
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
