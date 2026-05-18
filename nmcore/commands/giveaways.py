from nmcore.services import giveaways as gsvc
from nmcore.ui import embed

def setup(bot):
    @bot.command(name="قيف", aliases=["giveaway"])
    async def list_giveaways(ctx):
        gsvc.ensure_tables()
        rows = [r for r in gsvc.giveaways(ctx.guild.id, 20) if str(r["status"]) == "open"]

        if not rows:
            await ctx.reply(embed=embed("🎁 القيف أواي", "ما فيه قيف أواي مفتوح حاليًا.", "warn", ctx.author))
            return

        lines = [
            f"`{r['id']}` — **{r['prize']}** | winners: {r['winner_count']} | entries: {gsvc.entry_count(ctx.guild.id, r['id'])}"
            for r in rows
        ]

        await ctx.reply(embed=embed(
            "🎁 القيف أواي المفتوحة",
            "\n".join(lines) + "\n\nللدخول: `!دخول_قيف ID`",
            "purple",
            ctx.author
        ))

    @bot.command(name="دخول_قيف", aliases=["join_giveaway"])
    async def join_giveaway(ctx, giveaway_id:int):
        res = gsvc.join(ctx.guild.id, giveaway_id, ctx.author.id, ctx.author.display_name)

        if not res["ok"]:
            await ctx.reply(embed=embed("🎁 لم تدخل القيف أواي", res["error"], "bad", ctx.author))
            return

        await ctx.reply(embed=embed("🎁 تم دخول القيف أواي", f"{ctx.author.mention} دخل القيف أواي `#{giveaway_id}`", "ok", ctx.author))

    @bot.command(name="انشاء_قيف")
    async def create_giveaway(ctx, winner_count:int, *, prize:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("❌ صلاحية مرفوضة", "تحتاج Administrator.", "bad", ctx.author))
            return

        giveaway_id = gsvc.create_giveaway(
            ctx.guild.id,
            prize,
            winner_count,
            ctx.author.id,
            ctx.author.display_name
        )

        await ctx.reply(embed=embed(
            "🎁 تم إنشاء قيف أواي",
            f"ID: `{giveaway_id}`\nPrize: **{prize}**\nللدخول: `!دخول_قيف {giveaway_id}`",
            "ok",
            ctx.author
        ))

    @bot.command(name="سحب_فائز")
    async def pick_winner(ctx, giveaway_id:int):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("❌ صلاحية مرفوضة", "تحتاج Administrator.", "bad", ctx.author))
            return

        winners = gsvc.pick_winners(ctx.guild.id, giveaway_id)

        if not winners:
            await ctx.reply(embed=embed("🎁 لا يوجد فائز", "ما فيه مشاركين أو القيف أواي غير موجود.", "warn", ctx.author))
            return

        mentions = " ".join(f"<@{uid}>" for uid in winners)
        await ctx.reply(embed=embed("🏆 فائز القيف أواي", mentions, "ok", ctx.author))
