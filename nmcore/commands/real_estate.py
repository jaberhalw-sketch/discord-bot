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

        res = real_estate.collect_rent(interaction.guild.id, interaction.user.id, interaction.user.display_name)
        if not res["ok"]:
            await interaction.response.send_message(res["error"], ephemeral=True)
            return

        e = embed("💵 تم جمع الإيجار", f"عدد العقارات: **{res['count']}**\nالمبلغ: {coin(interaction.guild.id, res['amount'])}", "ok", interaction.user)
        await interaction.response.send_message(embed=e)

    @discord.ui.button(label="فتح المتجر", style=discord.ButtonStyle.secondary, emoji="🏘️")
    async def open_shop(self, interaction, button):
        await interaction.response.send_message("اكتب `!متجر` لفتح سوق العقارات بالأزرار.", ephemeral=True)


def property_line(ctx, r):
    return f"`#{r['id']}` **{r['display_name']}** • {coin(ctx.guild.id, r['price'])} • Rent **{int(r['rent']):,}** • L{int(r['level'])}"


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

        e = embed("💵 تم جمع الإيجار", f"عدد العقارات: **{res['count']}**\nالمبلغ: {coin(ctx.guild.id, res['amount'])}", "ok", ctx.author)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        await ctx.reply(embed=e)

        await send_action_log(ctx, "economy", "🏘️ Rent Collected", f"User: {ctx.author.mention} (`{ctx.author.id}`)\nProperties: **{res['count']}**\nAmount: **{res['amount']:,}**\nTX: `{res['tx_id']}`", "money")

    @bot.command(name="عقاراتي")
    async def mine(ctx):
        rows = real_estate.my_rows(ctx.guild.id, ctx.author.id)
        lines = [f"`#{r['id']}` **{r['display_name']}** • L{r['level']} • Rent **{int(r['rent']):,}**" for r in rows[:20]]

        e = embed("🏘️ عقاراتك", "\n".join(lines) if lines else "ما عندك عقارات.", "purple", ctx.author)
        e.add_field(name="الإيجار", value="اضغط الزر أو اكتب `!ايجار`.", inline=False)
        await ctx.reply(embed=e, view=MyPropertiesView(ctx) if rows else None)
