import time, discord
from discord.ext import commands
from nmcore.config import SALARY_BASE, SALARY_COOLDOWN_SECONDS
from nmcore.services import economy
from nmcore.services.settings import get_coin_name
from nmcore.ui import embed, coin, success, error

def setup(bot):
    @bot.command(name="رصيدي", aliases=["رصيد", "balance"])
    async def balance(ctx, member:discord.Member=None):
        member = member or ctx.author
        gid = ctx.guild.id
        bal = economy.get_balance(gid, member.id)
        rank = economy.user_rank(gid, member.id)

        e = embed("💰 المحفظة", f"محفظة {member.mention}", "money", member)
        e.add_field(name="الرصيد", value=coin(gid, bal), inline=True)
        e.add_field(name="الترتيب", value=f"#{rank}", inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="راتب", aliases=["salary", "daily"])
    async def salary(ctx):
        gid = ctx.guild.id
        uid = ctx.author.id
        economy.ensure_balance(gid, uid)

        from nmcore.db import db
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT last_salary FROM balances WHERE guild_id=? AND user_id=?", (gid, uid))
        row = cur.fetchone()

        last = int(row["last_salary"] or 0) if row else 0
        now = int(time.time())

        if now - last < SALARY_COOLDOWN_SECONDS:
            remain = SALARY_COOLDOWN_SECONDS - (now - last)
            conn.close()
            await ctx.reply(embed=embed(
                "⏳ الراتب تحت الانتظار",
                f"باقي تقريبًا **{remain//60} دقيقة** على الراتب القادم.",
                "warn",
                ctx.author
            ))
            return

        tx = economy.credit(
            gid, uid, SALARY_BASE, "salary",
            user_name=ctx.author.display_name,
            actor_id=uid,
            actor_name=ctx.author.display_name,
            channel_id=ctx.channel.id,
            message_id=ctx.message.id,
            reason="Salary claim"
        )
        cur.execute("UPDATE balances SET last_salary=? WHERE guild_id=? AND user_id=?", (now, gid, uid))
        conn.commit()
        conn.close()

        e = success("تم استلام الراتب", "دخلت الفلوس في محفظتك.", ctx.author)
        e.add_field(name="المبلغ", value=coin(gid, SALARY_BASE), inline=True)
        e.add_field(name="رصيدك الآن", value=coin(gid, tx["after"]), inline=True)
        e.add_field(name="TX", value=f"`{tx['tx_id'][:12]}`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="تحويل", aliases=["transfer"])
    async def transfer(ctx, member:discord.Member, amount:int):
        res = economy.transfer(
            ctx.guild.id,
            ctx.author.id,
            member.id,
            amount,
            ctx.author.display_name,
            member.display_name,
            ctx.channel.id,
            ctx.message.id
        )

        if not res["ok"]:
            await ctx.reply(embed=error("فشل التحويل", "رصيدك ما يكفي.", ctx.author))
            return

        e = success("تحويل ناجح", f"{ctx.author.mention} ➜ {member.mention}", ctx.author)
        e.add_field(name="المبلغ", value=coin(ctx.guild.id, amount), inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="الغني", aliases=["اغنى", "rich", "topmoney"])
    async def richest(ctx):
        rows = economy.top_balances(ctx.guild.id, 10)

        if not rows:
            await ctx.reply(embed=embed("🏆 أغنى اللاعبين", "ما فيه بيانات اقتصاد للحين.", "warn", ctx.author))
            return

        lines = [
            f"**#{i}** <@{uid}> — **{bal:,}** {get_coin_name(ctx.guild.id)}"
            for i, (uid, bal) in enumerate(rows, 1)
        ]

        await ctx.reply(embed=embed("🏆 أغنى اللاعبين", "\n".join(lines), "warn", ctx.author))

    @bot.command(name="اعطاءفلوس")
    @commands.has_permissions(administrator=True)
    async def give_money(ctx, member:discord.Member, amount:int):
        tx = economy.credit(
            ctx.guild.id,
            member.id,
            amount,
            "admin_give",
            user_name=member.display_name,
            actor_id=ctx.author.id,
            actor_name=ctx.author.display_name,
            reason="Admin give",
            channel_id=ctx.channel.id,
            message_id=ctx.message.id
        )
        e = success("تم إعطاء فلوس", f"المستلم: {member.mention}", ctx.author)
        e.add_field(name="المبلغ", value=coin(ctx.guild.id, amount), inline=True)
        e.add_field(name="رصيده الآن", value=coin(ctx.guild.id, tx["after"]), inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="سحبفلوس")
    @commands.has_permissions(administrator=True)
    async def take_money(ctx, member:discord.Member, amount:int):
        tx = economy.debit(
            ctx.guild.id,
            member.id,
            amount,
            "admin_take",
            user_name=member.display_name,
            actor_id=ctx.author.id,
            actor_name=ctx.author.display_name,
            reason="Admin take",
            channel_id=ctx.channel.id,
            message_id=ctx.message.id
        )

        if not tx["ok"]:
            await ctx.reply(embed=error("فشل السحب", "رصيده ما يكفي للسحب.", ctx.author))
            return

        e = success("تم سحب فلوس", f"من: {member.mention}", ctx.author)
        e.add_field(name="المبلغ", value=coin(ctx.guild.id, amount), inline=True)
        e.add_field(name="رصيده الآن", value=coin(ctx.guild.id, tx["after"]), inline=True)
        await ctx.reply(embed=e)
