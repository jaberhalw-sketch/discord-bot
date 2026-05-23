import discord
from nmcore.ui import embed
from nmcore.services import boost_rewards


def setup(bot):
    @bot.command(name="مزامنة_البوستات", aliases=["sync_boosts", "sync_boosters"])
    async def sync_boosts(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return

        res = boost_rewards.sync_guild_boosters(ctx.guild)

        e = embed(
            "🚀 تم تحديث البوستات",
            "تمت مزامنة الـ Active Boosters من Discord.",
            "ok",
            ctx.author
        )
        e.add_field(name="Active Boosters", value=str(res.get("active_count", 0)), inline=True)
        e.add_field(name="Scanned", value=str(res.get("scanned", 0)), inline=True)
        e.add_field(name="Booster Role", value=f"`{res.get('booster_role_id', 0)}`", inline=True)
        e.add_field(
            name="ملاحظة مهمة",
            value="Discord يعطينا مين عنده Boost نشط الآن. أما عدد البوستات التاريخي الحقيقي ما يجي من الإعدادات، ينحسب من رسائل البوست بعد تركيب النظام.",
            inline=False
        )
        await ctx.reply(embed=e)

    @bot.command(name="البوستات", aliases=["boosters", "boosts"])
    async def boosters(ctx):
        data = boost_rewards.summary(ctx.guild.id, 15)
        totals = data.get("totals", {})
        boosters_rows = data.get("boosters", [])[:10]

        lines = []
        for i, row in enumerate(boosters_rows, 1):
            active = "✅" if int(row.get("active") or 0) else "❌"
            lines.append(
                f"**#{i}** {active} <@{int(row.get('user_id') or 0)}> — "
                f"Boost Count `{int(row.get('boost_count') or 0)}` | "
                f"Rewards `{int(row.get('reward_total') or 0):,}`"
            )

        e = embed(
            "🚀 Server Boosters",
            "\n".join(lines) if lines else "مافي بيانات Boosters للحين. جرّب `!مزامنة_البوستات`.",
            "purple",
            ctx.author
        )
        e.add_field(name="Active Boosters", value=str(int(totals.get("active_boosters") or 0)), inline=True)
        e.add_field(name="Boost Events", value=str(int(totals.get("total_events") or 0)), inline=True)
        e.add_field(name="Rewards Paid", value=f"{int(totals.get('total_rewards') or 0):,}", inline=True)
        await ctx.reply(embed=e)
