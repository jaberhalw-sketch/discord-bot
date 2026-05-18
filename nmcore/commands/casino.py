from nmcore.services.casino import play
from nmcore.ui import embed, coin, money_delta

def setup(bot):
    async def run(ctx, game, amount):
        res = play(ctx.guild.id, ctx.author.id, ctx.author.display_name, game, amount, ctx.channel.id, ctx.message.id)

        if not res["ok"]:
            await ctx.reply(embed=embed("🎰 Casino رفض العملية", f"**السبب:** {res['error']}", "bad", ctx.author))
            return

        color = "ok" if res["outcome"] == "win" else "warn" if res["outcome"] == "draw" else "bad"
        title = {
            "win": "🎉 فوز في الكازينو",
            "lose": "💀 خسارة في الكازينو",
            "draw": "🤝 تعادل في الكازينو"
        }[res["outcome"]]

        e = embed(title, f"**اللعبة:** `{game}`\n{res['detail']}", color, ctx.author)
        e.add_field(name="🎯 الرهان", value=coin(ctx.guild.id, res["bet"]), inline=True)
        e.add_field(name="💸 الصافي", value=money_delta(ctx.guild.id, res["net"]), inline=True)
        e.add_field(name="قبل", value=coin(ctx.guild.id, res["before"]), inline=True)
        e.add_field(name="بعد", value=coin(ctx.guild.id, res["after"]), inline=True)
        e.add_field(name="Audit TX", value=f"`{str(res['bet_tx'])[:12]}`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="حظ", aliases=["luck"])
    async def luck(ctx, amount:str):
        await run(ctx, "luck", amount)

    @bot.command(name="دبل", aliases=["double"])
    async def double(ctx, amount:str):
        await run(ctx, "double", amount)

    @bot.command(name="سلوت", aliases=["slot"])
    async def slot(ctx, amount:str):
        await run(ctx, "slot", amount)

    @bot.command(name="وجه", aliases=["flip"])
    async def flip(ctx, amount:str):
        await run(ctx, "flip", amount)

    @bot.command(name="بلاكجاك", aliases=["bj", "blackjack"])
    async def blackjack(ctx, amount:str):
        await run(ctx, "blackjack", amount)
