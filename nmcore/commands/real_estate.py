from nmcore.services import real_estate
from nmcore.ui import embed, coin

def setup(bot):
    @bot.command(name="عقارات")
    async def props(ctx):
        rows = real_estate.rows(ctx.guild.id, True)[:10]
        lines = [
            f"`{r['id']}` — **{r['display_name']}** | {r['price']:,} | rent {r['rent']:,}"
            for r in rows
        ]

        await ctx.reply(embed=embed(
            "🏘️ العقارات المتاحة",
            "\n".join(lines) if lines else "لا يوجد عقارات متاحة.",
            "purple",
            ctx.author
        ))

    @bot.command(name="شراء_عقار")
    async def buy(ctx, property_id:int):
        res = real_estate.buy(ctx.guild.id, ctx.author.id, ctx.author.display_name, property_id)

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل شراء العقار", res["error"], "bad", ctx.author))
            return

        e = embed("🏠 تم شراء العقار", res["name"], "ok", ctx.author)
        e.add_field(name="السعر", value=coin(ctx.guild.id, res["price"]), inline=True)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="ايجار")
    async def rent(ctx):
        res = real_estate.collect_rent(ctx.guild.id, ctx.author.id, ctx.author.display_name)

        if not res["ok"]:
            await ctx.reply(embed=embed("💵 لا يمكن جمع الإيجار", res["error"], "warn", ctx.author))
            return

        await ctx.reply(embed=embed(
            "💵 تم جمع الإيجار",
            f"عدد العقارات: **{res['count']}**\nالمبلغ: {coin(ctx.guild.id, res['amount'])}",
            "ok",
            ctx.author
        ))

    @bot.command(name="عقاراتي")
    async def mine(ctx):
        rows = real_estate.my_rows(ctx.guild.id, ctx.author.id)
        lines = [
            f"`{r['id']}` — **{r['display_name']}** | L{r['level']} | rent {r['rent']:,}"
            for r in rows
        ]

        await ctx.reply(embed=embed(
            "🏘️ عقاراتك",
            "\n".join(lines) if lines else "ما عندك عقارات.",
            "purple",
            ctx.author
        ))
