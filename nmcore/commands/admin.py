from nmcore.services.settings import set_system_enabled, all_toggles, set_coin_name, update_channel
from nmcore.ui import embed

def setup(bot):
    @bot.command(name="بنق")
    async def ping(ctx):
        await ctx.reply("🏓 Pong")

    @bot.command(name="مساعدة")
    async def help_cmd(ctx):
        text = """
**Economy:** `!رصيدي` `!راتب` `!تحويل @user amount` `!الغني`
**Casino:** `!حظ amount` `!دبل amount` `!سلوت amount` `!وجه amount` `!bj amount`
**Levels:** `!لفلي` `!ترتيب`
**Real Estate:** `!عقارات` `!شراء_عقار ID` `!ايجار` `!عقاراتي`
**Admin:** `!قفل economy` `!فتح economy` `!اعداد_عملة NAME`
"""
        await ctx.reply(embed=embed("📘 NM System Help", text, "info"))

    @bot.command(name="قفل")
    async def disable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("❌ تحتاج Administrator."); return
        set_system_enabled(ctx.guild.id,system_key,False)
        await ctx.reply(f"🔒 تم قفل نظام `{system_key}`")

    @bot.command(name="فتح")
    async def enable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("❌ تحتاج Administrator."); return
        set_system_enabled(ctx.guild.id,system_key,True)
        await ctx.reply(f"🔓 تم فتح نظام `{system_key}`")

    @bot.command(name="الانظمة")
    async def systems(ctx):
        data=all_toggles(ctx.guild.id)
        lines=[f"{'✅' if v else '❌'} `{k}`" for k,v in data.items()]
        await ctx.reply(embed=embed("⚙️ الأنظمة", "\n".join(lines), "info"))

    @bot.command(name="اعداد_عملة")
    async def coin(ctx, *, name:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply("❌ تحتاج Administrator."); return
        set_coin_name(ctx.guild.id,name)
        await ctx.reply(f"✅ تم تغيير اسم العملة إلى: **{name}**")
