import discord
from nmcore.services import warnings as warnsvc
from nmcore.ui import embed

def setup(bot):
    @bot.command(name="تحذير")
    @discord.ext.commands.has_permissions(manage_messages=True)
    async def warn(ctx, member:discord.Member, *, reason="بدون سبب"):
        warnsvc.add_warning(ctx.guild.id,member.id,member.display_name,ctx.author.id,ctx.author.display_name,reason)
        await ctx.reply(embed=embed("⚠️ تم إعطاء تحذير", f"{member.mention}\n**السبب:** {reason}", "warn", member))

    @bot.command(name="تحذيرات")
    async def warnings(ctx, member:discord.Member=None):
        member=member or ctx.author
        rows=warnsvc.user_warnings(ctx.guild.id,member.id,True)
        lines=[f"`#{r['id']}` {r['reason']}" for r in rows[:10]]
        await ctx.reply(embed=embed("⚠️ التحذيرات", "\n".join(lines) if lines else "لا توجد تحذيرات نشطة.", "warn", member))

    @bot.command(name="مسح_تحذيرات")
    @discord.ext.commands.has_permissions(manage_messages=True)
    async def clear(ctx, member:discord.Member, *, reason="cleared"):
        count=warnsvc.clear_user(ctx.guild.id,member.id,ctx.author.id,ctx.author.display_name,reason)
        await ctx.reply(f"✅ تم مسح {count} تحذير من {member.mention}")
