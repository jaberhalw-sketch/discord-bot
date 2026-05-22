import discord
from discord.ext import commands
from nmcore.services import warnings as warnsvc
from nmcore.services.activity import log_event
from nmcore.services.log_channels import get_log_channel
from nmcore.ui import embed, success, error


async def send_mod_log(ctx, title, description, color="warn"):
    try:
        ch_id = get_log_channel(ctx.guild.id, "warnings")
        if not ch_id:
            return

        ch = ctx.guild.get_channel(int(ch_id))
        if not ch:
            return

        await ch.send(embed=embed(title, description, color, ctx.author))
    except Exception:
        pass


def setup(bot):
    @bot.command(name="تحذير")
    @commands.has_permissions(manage_messages=True)
    async def warn(ctx, member:discord.Member, *, reason="بدون سبب"):
        if member.bot:
            await ctx.reply(embed=error("تحذير مرفوض", "ما تقدر تعطي تحذير لبوت.", ctx.author))
            return

        if member.id == ctx.author.id:
            await ctx.reply(embed=error("تحذير مرفوض", "ما تقدر تعطي تحذير لنفسك.", ctx.author))
            return

        warnsvc.add_warning(
            ctx.guild.id,
            member.id,
            member.display_name,
            ctx.author.id,
            ctx.author.display_name,
            reason
        )

        log_event(
            ctx.guild.id,
            "manual_warning",
            member.id,
            member.display_name,
            ctx.channel.id,
            ctx.channel.name,
            "Manual warning added",
            f"By {ctx.author.id}: {reason}"
        )

        e = embed("⚠️ تم إعطاء تحذير", f"{member.mention}\n**السبب:** {reason}", "warn", member)
        await ctx.reply(embed=e)

        await send_mod_log(
            ctx,
            "⚠️ Manual Warning",
            f"User: {member.mention} (`{member.id}`)\nBy: {ctx.author.mention} (`{ctx.author.id}`)\nReason: {reason}",
            "warn"
        )

    @bot.command(name="تحذيرات")
    async def warnings(ctx, member:discord.Member=None):
        member = member or ctx.author
        rows = warnsvc.user_warnings(ctx.guild.id, member.id, True)

        lines = [f"`#{r['id']}` {r['reason']}" for r in rows[:10]]

        e = embed(
            "⚠️ التحذيرات النشطة",
            "\n".join(lines) if lines else "لا توجد تحذيرات نشطة.",
            "warn",
            member
        )
        e.add_field(name="العدد", value=str(len(rows)), inline=True)

        await ctx.reply(embed=e)

    @bot.command(name="مسح_تحذيرات")
    @commands.has_permissions(manage_messages=True)
    async def clear(ctx, member:discord.Member, *, reason="cleared"):
        count = warnsvc.clear_user(ctx.guild.id, member.id, ctx.author.id, ctx.author.display_name, reason)

        log_event(
            ctx.guild.id,
            "warnings_cleared",
            member.id,
            member.display_name,
            ctx.channel.id,
            ctx.channel.name,
            "Warnings cleared",
            f"Count={count}, By={ctx.author.id}, Reason={reason}"
        )

        await ctx.reply(embed=success("تم مسح التحذيرات", f"تم مسح **{count}** تحذير من {member.mention}", ctx.author))

        await send_mod_log(
            ctx,
            "✅ Warnings Cleared",
            f"User: {member.mention} (`{member.id}`)\nBy: {ctx.author.mention} (`{ctx.author.id}`)\nCount: **{count}**\nReason: {reason}",
            "ok"
        )
