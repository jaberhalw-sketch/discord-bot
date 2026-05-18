from nmcore.services.levels import get_level, top_levels
from nmcore.ui import embed

def setup(bot):
    @bot.command(name="لفلي", aliases=["لفل"])
    async def my_level(ctx, member=None):
        member=member or ctx.author
        xp,lvl=get_level(ctx.guild.id,member.id)
        e=embed("📊 Level Profile", f"{member.mention}", "info", member)
        e.add_field(name="Level", value=str(lvl), inline=True)
        e.add_field(name="XP", value=f"{xp:,}/{lvl*100:,}", inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="ترتيب")
    async def level_top(ctx):
        rows=top_levels(ctx.guild.id,10)
        lines=[f"**#{i}** <@{uid}> — Level **{lvl}** | XP `{xp}`" for i,(uid,xp,lvl) in enumerate(rows,1)]
        await ctx.reply(embed=embed("🏅 ترتيب اللفلات","\n".join(lines) if lines else "لا يوجد بيانات","info"))
