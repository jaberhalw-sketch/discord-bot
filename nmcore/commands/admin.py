from nmcore.services.settings import set_system_enabled, all_toggles, set_coin_name
from nmcore.ui import embed, success, error

def setup(bot):
    @bot.command(name="بنق")
    async def ping(ctx):
        await ctx.reply(embed=embed("🏓 Pong", "NM System شغال وجاهز.", "ok", ctx.author))

    @bot.command(name="مساعدة")
    async def help_cmd(ctx):
        text = """
> استخدم الأوامر التالية لإدارة نظامك:

**💰 Economy**
`!رصيدي` `!راتب` `!تحويل @user amount` `!الغني`

**🎰 Casino**
`!حظ amount` `!دبل amount` `!سلوت amount` `!وجه amount` `!bj amount`

**📊 Levels**
`!لفلي` `!ترتيب`

**🏘️ Real Estate**
`!عقارات` `!شراء_عقار ID` `!ايجار` `!عقاراتي`

**🛡️ Moderation**
`!تحذير @user reason` `!تحذيرات @user` `!مسح_تحذيرات @user`

**⚙️ Admin**
`!قفل economy` `!فتح economy` `!اعداد_عملة NAME`
"""
        await ctx.reply(embed=embed("📘 NM System Command Center", text, "purple", ctx.author))

    @bot.command(name="قفل")
    async def disable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_system_enabled(ctx.guild.id, system_key, False)
        await ctx.reply(embed=embed("🔒 تم قفل النظام", f"النظام: `{system_key}`", "warn", ctx.author))

    @bot.command(name="فتح")
    async def enable(ctx, system_key:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_system_enabled(ctx.guild.id, system_key, True)
        await ctx.reply(embed=success("تم فتح النظام", f"النظام: `{system_key}`", ctx.author))

    @bot.command(name="الانظمة")
    async def systems(ctx):
        data = all_toggles(ctx.guild.id)
        lines = [f"{'✅' if v else '❌'} `{k}`" for k, v in data.items()]
        await ctx.reply(embed=embed("⚙️ حالة الأنظمة", "\n".join(lines), "info", ctx.author))

    @bot.command(name="اعداد_عملة")
    async def coin(ctx, *, name:str):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=error("صلاحية مرفوضة", "تحتاج صلاحية Administrator.", ctx.author))
            return
        set_coin_name(ctx.guild.id, name)
        await ctx.reply(embed=success("تم تغيير اسم العملة", f"الاسم الجديد: **{name}**", ctx.author))
