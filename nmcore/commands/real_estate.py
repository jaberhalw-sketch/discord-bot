import discord
from nmcore.services import real_estate
from nmcore.services.log_channels import get_log_channel
from nmcore.ui import embed, coin


async def send_action_log(ctx, log_key, title, description, color="info"):
    try:
        ch_id = get_log_channel(ctx.guild.id, log_key)
        if not ch_id:
            return
        ch = ctx.guild.get_channel(int(ch_id))
        if not ch:
            return
        await ch.send(embed=embed(title, description, color, ctx.author))
    except Exception:
        pass


class MyPropertiesView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=120)
        self.ctx = ctx

    @discord.ui.button(label="استلام الإيجار", style=discord.ButtonStyle.success, emoji="💵")
    async def collect_rent(self, interaction, button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("هذا الزر لصاحب العقارات فقط.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        res = real_estate.collect_rent(interaction.guild.id, interaction.user.id, interaction.user.display_name)
        if not res["ok"]:
            await interaction.followup.send(embed=embed("❌ خطأ في رد الإيجار", res["error"], "bad", interaction.user), ephemeral=True)
            return

        desc = f"عدد العقارات: **{res['count']}**\nالمبلغ: {coin(interaction.guild.id, res['amount'])}\nالإيجار الجاي بعد: **3 ساعات**"
        if res.get("warning"):
            desc += f"\n\n⚠️ {res['warning']}"
        e = embed("💵 تم جمع الإيجار", desc, "ok", interaction.user)
        await interaction.followup.send(embed=e, ephemeral=True)

    @discord.ui.button(label="فتح المتجر", style=discord.ButtonStyle.secondary, emoji="🏘️")
    async def open_shop(self, interaction, button):
        await interaction.response.send_message("اكتب `!متجر` لفتح سوق العقارات بالأزرار.", ephemeral=True)


def property_line(ctx, r):
    return f"`#{r['id']}` **{r['display_name']}** • {coin(ctx.guild.id, r['price'])} • Rent **{int(r['rent']):,}** • L{int(r['level'])}"



def rent_status_lines(ctx, rows):
    if not rows:
        return "ما عندك عقارات."

    lines = []
    for r in rows[:20]:
        status = "✅ جاهز للاستلام" if r["ready"] else f"⏳ باقي {r['remaining_text']}"
        lines.append(
            f"`#{r['id']}` **{r['name']}** • L{r['level']} • Rent **{int(r['amount']):,}** • {status}"
        )
    return "\n".join(lines)



def setup(bot):
    @bot.command(name="عقارات")
    async def props(ctx):
        rows = real_estate.rows(ctx.guild.id, True)[:10]
        lines = [property_line(ctx, r) for r in rows]

        e = embed("🏘️ العقارات المتاحة", "\n".join(lines) if lines else "لا يوجد عقارات متاحة.", "purple", ctx.author)
        e.add_field(name="شراء سريع", value="استخدم `!متجر` عشان تشتري بالأزرار أو `!شراء_عقار ID`.", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شراء_عقار")
    async def buy(ctx, property_id:int):
        res = real_estate.buy(ctx.guild.id, ctx.author.id, ctx.author.display_name, property_id)

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل شراء العقار", res["error"], "bad", ctx.author))
            return

        e = embed("🏠 تم شراء العقار", f"**{res['name']}**", "ok", ctx.author)
        e.add_field(name="السعر", value=coin(ctx.guild.id, res["price"]), inline=True)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        e.add_field(name="الإيجار", value="يتجمع كل 3 ساعات.", inline=False)
        await ctx.reply(embed=e)

        await send_action_log(ctx, "economy", "🏠 Property Bought", f"User: {ctx.author.mention} (`{ctx.author.id}`)\nProperty: **{res['name']}** (`{property_id}`)\nPrice: **{res['price']:,}**\nTX: `{res['tx_id']}`", "money")

    @bot.command(name="ايجار")
    async def rent(ctx):
        res = real_estate.collect_rent(ctx.guild.id, ctx.author.id, ctx.author.display_name)

        if not res["ok"]:
            await ctx.reply(embed=embed("💵 لا يمكن جمع الإيجار", res["error"], "warn", ctx.author))
            return

        desc = f"عدد العقارات: **{res['count']}**\nالمبلغ: {coin(ctx.guild.id, res['amount'])}\nالإيجار الجاي بعد: **3 ساعات**"
        if res.get("warning"):
            desc += f"\n\n⚠️ {res['warning']}"
        e = embed("💵 تم جمع الإيجار", desc, "ok", ctx.author)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        await ctx.reply(embed=e)

        await send_action_log(ctx, "economy", "🏘️ Rent Collected", f"User: {ctx.author.mention} (`{ctx.author.id}`)\nProperties: **{res['count']}**\nAmount: **{res['amount']:,}**\nTX: `{res['tx_id']}`", "money")

    @bot.command(name="عقاراتي")
    async def mine(ctx):
        status = real_estate.rent_status(ctx.guild.id, ctx.author.id)
        props = status["properties"]

        e = embed("🏘️ عقاراتك", rent_status_lines(ctx, props), "purple", ctx.author)

        if props:
            if status["ready_count"] > 0:
                e.add_field(
                    name="💵 جاهز للاستلام",
                    value=f"عندك **{status['ready_count']}** عقار جاهز\nالمبلغ الجاهز: {coin(ctx.guild.id, status['ready_amount'])}",
                    inline=False
                )
            else:
                e.add_field(
                    name="⏳ الإيجار القادم",
                    value=f"باقي على أقرب إيجار: **{status['next_remaining_text']}**",
                    inline=False
                )

            e.add_field(name="طريقة الاستلام", value="كل عقار يعطي إيجار كل **3 ساعات**. اضغط زر **استلام الإيجار** أو اكتب `!ايجار`.", inline=False)

        await ctx.reply(embed=e, view=MyPropertiesView(ctx) if props else None)


    @bot.command(name="نقل_عقار", aliases=["تحويل_عقار", "property_transfer"])
    async def transfer_property_cmd(ctx, member: discord.Member, property_id: int):
        if member.bot:
            await ctx.reply(embed=embed("🏘️ لا يمكن النقل", "ما تقدر تنقل عقار لبوت.", "bad", ctx.author))
            return

        res = real_estate.transfer_property(
            ctx.guild.id,
            ctx.author.id,
            member.id,
            member.display_name,
            property_id,
            actor_id=ctx.author.id,
            reason=f"Owner transfer from {ctx.author.id} to {member.id}"
        )

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل نقل العقار", res["error"], "bad", ctx.author))
            return

        e = embed(
            "🏘️ تم نقل العقار",
            f"**{res['name']}**\n\nمن: {ctx.author.mention}\nإلى: {member.mention}",
            "ok",
            ctx.author
        )
        e.add_field(name="ملاحظة", value="الإيجار يبدأ يحسب للمالك الجديد من الآن، ويصير جاهز بعد 3 ساعات.", inline=False)
        await ctx.reply(embed=e)

        await send_action_log(
            ctx,
            "economy",
            "🏘️ Property Transferred",
            f"From: {ctx.author.mention} (`{ctx.author.id}`)\nTo: {member.mention} (`{member.id}`)\nProperty: **{res['name']}** (`{property_id}`)",
            "money"
        )

    @bot.command(name="اعطاء_عقار", aliases=["admin_property_give"])
    async def admin_give_property_cmd(ctx, member: discord.Member, property_id: int):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return

        if member.bot:
            await ctx.reply(embed=embed("🏘️ لا يمكن النقل", "ما تقدر تعطي عقار لبوت.", "bad", ctx.author))
            return

        res = real_estate.admin_assign_property(
            ctx.guild.id,
            property_id,
            member.id,
            member.display_name,
            actor_id=ctx.author.id,
            reason=f"Admin assign by {ctx.author.id} to {member.id}"
        )

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل إعطاء العقار", res["error"], "bad", ctx.author))
            return

        e = embed(
            "🏘️ تم إعطاء العقار",
            f"**{res['name']}**\n\nالمالك الجديد: {member.mention}",
            "ok",
            ctx.author
        )
        e.add_field(name="ملاحظة", value="الإيجار يبدأ يحسب للمالك الجديد من الآن، ويصير جاهز بعد 3 ساعات.", inline=False)
        await ctx.reply(embed=e)

        await send_action_log(
            ctx,
            "economy",
            "🏘️ Admin Property Assigned",
            f"Actor: {ctx.author.mention} (`{ctx.author.id}`)\nTo: {member.mention} (`{member.id}`)\nProperty: **{res['name']}** (`{property_id}`)",
            "money"
        )

    @bot.command(name="ارجاع_عقار", aliases=["سحب_عقار", "admin_property_return"])
    async def admin_return_property_cmd(ctx, property_id: int):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return

        res = real_estate.admin_return_property(
            ctx.guild.id,
            property_id,
            actor_id=ctx.author.id,
            reason=f"Admin return by {ctx.author.id}"
        )

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل إرجاع العقار", res["error"], "bad", ctx.author))
            return

        e = embed("🏘️ تم إرجاع العقار للسوق", f"**{res['name']}** صار متاح للبيع من جديد.", "ok", ctx.author)
        await ctx.reply(embed=e)

        await send_action_log(
            ctx,
            "economy",
            "🏘️ Property Returned To Market",
            f"Actor: {ctx.author.mention} (`{ctx.author.id}`)\nProperty: **{res['name']}** (`{property_id}`)\nOld owner: `{res['old_owner_id']}`",
            "money"
        )

