import discord
from nmcore.services import profile as profile_service
from nmcore.ui import embed, coin


def money(v):
    return f"{int(v or 0):,}"


def achievement_line(a):
    return f"{a['emoji']} **{a['title']}** — {a['desc']}"


def setup(bot):
    @bot.command(name="بروفايل", aliases=["profile", "ملفي", "حسابي"])
    async def profile(ctx, member: discord.Member = None):
        member = member or ctx.author
        p = profile_service.get_user_profile(ctx.guild.id, member.id)
        title = profile_service.profile_title(p)
        risk = profile_service.risk_score(p)

        e = embed(
            f"👤 Profile — {member.display_name}",
            f"{member.mention}\n**Title:** {title}",
            "purple",
            member
        )
        e.set_thumbnail(url=member.display_avatar.url)

        e.add_field(name="💰 الرصيد", value=coin(ctx.guild.id, p["balance"]), inline=True)
        e.add_field(name="📊 Level", value=f"Level **{p['level']}**\nXP `{money(p['xp'])}`", inline=True)
        e.add_field(name="⚠️ Risk", value=f"**{risk['score']}/100**\n{', '.join(risk['reasons'][:2])}", inline=True)

        e.add_field(
            name="📈 المال",
            value=f"Gained: `{money(p['money'].get('gained'))}`\nSpent/Lost: `{money(p['money'].get('spent'))}`\nNet: `{money(p['money'].get('net'))}`",
            inline=True
        )

        e.add_field(
            name="🎰 Casino",
            value=f"Plays: `{money(p['casino'].get('plays'))}`\nWagered: `{money(p['casino'].get('wagered'))}`\nNet: `{money(p['casino'].get('net'))}`",
            inline=True
        )

        e.add_field(
            name="🏘️ العقارات",
            value=f"Count: `{money(p['props_summary'].get('count'))}`\nRent: `{money(p['props_summary'].get('rent_total'))}`\nValue: `{money(p['props_summary'].get('property_value'))}`",
            inline=True
        )

        e.add_field(
            name="🚀 Boosts / Posts",
            value=f"Boosts: `{money(p['booster_profile'].get('boost_count') or p['boosts'].get('c'))}`\nBoost Rewards: `{money(p['booster_profile'].get('reward_total'))}`\nPost Rewards: `{money(p['post_rewards'].get('posts'))}`",
            inline=True
        )

        e.add_field(
            name="⚠️ التحذيرات",
            value=f"Active: `{money(p['warnings'].get('active'))}`\nTotal: `{money(p['warnings'].get('total'))}`",
            inline=True
        )

        achievements = p.get("achievements") or []
        if achievements:
            e.add_field(
                name="🏆 Achievements",
                value="\n".join(achievement_line(a) for a in achievements[:8])[:1000],
                inline=False
            )
        else:
            e.add_field(name="🏆 Achievements", value="ما عنده إنجازات للحين.", inline=False)

        e.add_field(
            name="Dashboard",
            value=f"`/dashboard/user?guild_id={ctx.guild.id}&user_id={member.id}`",
            inline=False
        )

        await ctx.reply(embed=e)
