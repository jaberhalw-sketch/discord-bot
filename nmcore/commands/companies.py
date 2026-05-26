import discord
from nmcore.ui import embed, coin
from nmcore.services import companies


def fmt(n):
    return f"{int(n or 0):,}"


def company_embed(ctx, c):
    sector = companies.sector_info(c["sector_key"])
    preview = companies.income_preview(c)
    cycles, remaining = companies.rent_like_remaining(c)
    members = companies.company_members(ctx.guild.id, c["id"])

    e = embed(f"{sector['emoji']} {c['name']}", f"قطاع: **{sector['name']}**\nالمالك: <@{int(c['owner_id'])}>", "purple", ctx.author)
    e.add_field(name="🏢 المستوى", value=str(int(c["level"] or 1)), inline=True)
    e.add_field(name="💼 رصيد الشركة", value=coin(ctx.guild.id, int(c["balance"] or 0)), inline=True)
    e.add_field(name="⭐ السمعة", value=str(int(c["reputation"] or 0)), inline=True)
    e.add_field(name="👥 الموظفين", value=f"{max(0, len(members)-1)}/8", inline=True)
    e.add_field(name="📈 دخل كل 6 ساعات", value=f"Gross `{fmt(preview['gross'])}`\nTax `{fmt(preview['tax'])}`\nPayroll `{fmt(preview['payroll_total'])}`\nRisk cost `{fmt(preview.get('operating_risk_cost',0))}`\nNet company `{fmt(preview['net_company'])}`", inline=True)
    e.add_field(name="🧠 نجاح الشركة", value=f"Success **{preview.get('success_score',0)}/100**\nStrategy: **{preview.get('strategy','Balanced')}**", inline=True)
    if cycles > 0:
        e.add_field(name="✅ دخل جاهز", value=f"دفعات جاهزة: **{cycles}**", inline=True)
    else:
        e.add_field(name="⏳ الدخل القادم", value=companies.seconds_to_text(remaining), inline=True)

    if members:
        e.add_field(name="👥 الفريق", value="\n".join(f"• <@{int(m['user_id'])}> — `{m['role']}`" for m in members[:10]), inline=False)

    e.set_footer(text="Companies System • income every 6 hours")
    return e


def setup(bot):
    @bot.command(name="قطاعات_الشركات", aliases=["company_sectors"])
    async def sectors(ctx):
        e = embed("🏢 قطاعات الشركات", companies.sectors_text(ctx.guild.id), "info", ctx.author)
        e.add_field(name="فتح شركة", value="`!شركة_فتح sector_name اسم الشركة`\nمثال: `!شركة_فتح tech Jaber Tech`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شركة_فتح", aliases=["فتح_شركة", "company_create"])
    async def create(ctx, sector_key: str = None, *, name: str = None):
        if not sector_key or not name:
            e = embed("🏢 فتح شركة", "الاستخدام:\n`!شركة_فتح tech Jaber Tech`\n\nالقطاعات:\n" + companies.sectors_text(ctx.guild.id), "info", ctx.author)
            await ctx.reply(embed=e)
            return

        res = companies.create_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, sector_key, name)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل فتح الشركة", res["error"], "bad", ctx.author))
            return

        e = embed("✅ تم فتح الشركة", f"**{res['name']}**\nالقطاع: {res['sector']['emoji']} **{res['sector']['name']}**", "ok", ctx.author)
        e.add_field(name="التكلفة", value=coin(ctx.guild.id, res["cost"]), inline=True)
        e.add_field(name="ID", value=f"`{res['id']}`", inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="شركتي", aliases=["company", "my_company"])
    async def my_company(ctx, company_id: int = None):
        c = companies.get_company_for_owner(ctx.guild.id, ctx.author.id, company_id)
        if not c:
            await ctx.reply(embed=embed("🏢 ما عندك شركة", "افتح شركة باستخدام:\n`!شركة_فتح tech اسم الشركة`", "warn", ctx.author))
            return
        await ctx.reply(embed=company_embed(ctx, c))

    @bot.command(name="شركاتي", aliases=["my_companies"])
    async def my_companies(ctx):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)
        if not rows:
            await ctx.reply(embed=embed("🏢 شركاتك", "ما عندك شركات. تقدر تفتح حتى 3 شركات.", "warn", ctx.author))
            return

        lines = []
        for c in rows:
            sec = companies.sector_info_for_guild(ctx.guild.id, c["sector_key"])
            preview = companies.income_preview(c)
            lines.append(f"`#{c['id']}` {sec['emoji']} **{c['name']}** — L{int(c['level'])} — Balance `{fmt(c['balance'])}` — Net/6h `{fmt(preview['net_company'])}`")
        e = embed("🏢 شركاتك", "\n".join(lines), "purple", ctx.author)
        e.add_field(name="ملاحظة", value="تقدر تملك حتى **3 شركات**. افتح شركة بـ `!شركة_فتح sector الاسم`.", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="الشركات", aliases=["top_companies", "توب_الشركات"])
    async def top(ctx):
        rows = companies.top_companies(ctx.guild.id, 10)
        if not rows:
            await ctx.reply(embed=embed("🏢 الشركات", "ما فيه شركات للحين.", "warn", ctx.author))
            return
        lines = []
        for i, c in enumerate(rows, 1):
            sec = companies.sector_info(c["sector_key"])
            lines.append(f"**#{i}** {sec['emoji']} **{c['name']}** — L{int(c['level'])} — Balance `{fmt(c['balance'])}` — <@{int(c['owner_id'])}>")
        await ctx.reply(embed=embed("🏆 توب الشركات", "\n".join(lines), "purple", ctx.author))

    @bot.command(name="شركة_دخل", aliases=["دخل_الشركة", "company_income"])
    async def collect_income(ctx):
        res = companies.collect_income(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        if not res["ok"]:
            await ctx.reply(embed=embed("📈 دخل الشركة", res["error"], "warn", ctx.author))
            return
        event = res.get("event", {})
        e = embed("📈 تم استلام دخل الشركة", f"دفعات متجمعة: **{res['cycles']}**\nدخل الشركة الصافي: {coin(ctx.guild.id, res['company_amount'])}\n\n**{event.get('label','Stable Operation')}**\n{event.get('details','')}", "ok", ctx.author)
        if int(res.get("event_delta", 0)):
            e.add_field(name="تأثير القرار/المخاطرة", value=coin(ctx.guild.id, res.get("event_delta", 0)), inline=False)
        if res["paid_employees"]:
            e.add_field(name="رواتب الموظفين", value=f"تم دفع **{res['paid_employees']}** موظف\nلكل موظف: {coin(ctx.guild.id, res['employee_each'])}", inline=False)
        e.add_field(name="رصيد الشركة بعد الاستلام", value=coin(ctx.guild.id, res["balance_after"]), inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شركة_ترقية", aliases=["ترقية_الشركة", "company_upgrade"])
    async def upgrade(ctx):
        res = companies.upgrade(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        if not res["ok"]:
            await ctx.reply(embed=embed("⬆️ فشل ترقية الشركة", res["error"], "bad", ctx.author))
            return
        await ctx.reply(embed=embed("⬆️ تمت ترقية الشركة", f"المستوى الجديد: **{res['level']}**\nالتكلفة: {coin(ctx.guild.id, res['cost'])}\nرصيد الشركة: {coin(ctx.guild.id, res['balance_after'])}", "ok", ctx.author))

    @bot.command(name="شركة_ايداع", aliases=["ايداع_شركة", "company_deposit"])
    async def deposit(ctx, amount: int = None):
        if not amount or amount <= 0:
            await ctx.reply(embed=embed("💼 إيداع للشركة", "استخدم: `!شركة_ايداع 50000`", "info", ctx.author))
            return
        res = companies.deposit(ctx.guild.id, ctx.author.id, ctx.author.display_name, amount)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل الإيداع", res["error"], "bad", ctx.author))
            return
        await ctx.reply(embed=embed("✅ تم الإيداع", f"المبلغ: {coin(ctx.guild.id, res['amount'])}\nرصيد الشركة: {coin(ctx.guild.id, res['balance_after'])}", "ok", ctx.author))

    @bot.command(name="شركة_سحب", aliases=["سحب_شركة", "company_withdraw"])
    async def withdraw(ctx, amount: int = None):
        if not amount or amount <= 0:
            await ctx.reply(embed=embed("💼 سحب من الشركة", "استخدم: `!شركة_سحب 50000`", "info", ctx.author))
            return
        res = companies.withdraw(ctx.guild.id, ctx.author.id, ctx.author.display_name, amount)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل السحب", res["error"], "bad", ctx.author))
            return
        await ctx.reply(embed=embed("✅ تم السحب", f"المبلغ: {coin(ctx.guild.id, res['amount'])}\nرصيد الشركة: {coin(ctx.guild.id, res['balance_after'])}", "ok", ctx.author))

    @bot.command(name="شركة_توظيف", aliases=["توظيف_شركة", "company_hire"])
    async def hire(ctx, member: discord.Member = None):
        if not member:
            await ctx.reply(embed=embed("👥 توظيف", "استخدم: `!شركة_توظيف @user`", "info", ctx.author))
            return
        if member.bot:
            await ctx.reply(embed=embed("❌ لا يمكن", "ما تقدر توظف بوت.", "bad", ctx.author))
            return
        res = companies.hire(ctx.guild.id, ctx.author.id, ctx.author.display_name, member.id, member.display_name)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل التوظيف", res["error"], "bad", ctx.author))
            return
        await ctx.reply(embed=embed("✅ تم التوظيف", f"{member.mention} صار موظف في شركتك.\nالموظفين يزيدون دخل الشركة ويأخذون راتب عند استلام الدخل.", "ok", ctx.author))

    @bot.command(name="شركة_طرد", aliases=["طرد_شركة", "company_fire"])
    async def fire(ctx, member: discord.Member = None):
        if not member:
            await ctx.reply(embed=embed("👥 طرد موظف", "استخدم: `!شركة_طرد @user`", "info", ctx.author))
            return
        res = companies.fire(ctx.guild.id, ctx.author.id, ctx.author.display_name, member.id)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل الطرد", res["error"], "bad", ctx.author))
            return
        await ctx.reply(embed=embed("✅ تم طرد الموظف", f"تم إخراج {member.mention} من شركتك.", "ok", ctx.author))

    @bot.command(name="قرارات_الشركة", aliases=["company_decisions"])
    async def company_decisions(ctx):
        e = embed("🧠 قرارات الشركة", companies.decision_options_text(), "info", ctx.author)
        e.add_field(name="استخدام", value="`!شركة_قرار marketing`\n`!شركة_قرار quality`\n`!شركة_قرار aggressive`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شركة_قرار", aliases=["قرار_شركة", "company_decision"])
    async def company_decision(ctx, decision_key: str = None):
        if not decision_key:
            await ctx.reply(embed=embed("🧠 قرار الشركة", "استخدم:\n`!قرارات_الشركة`\nثم:\n`!شركة_قرار marketing`", "info", ctx.author))
            return

        res = companies.make_decision(ctx.guild.id, ctx.author.id, ctx.author.display_name, decision_key)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل قرار الشركة", res["error"], "bad", ctx.author))
            return

        d = res["decision"]
        e = embed("🧠 تم تنفيذ قرار الشركة", f"{d['emoji']} **{d['name']}**\n{d['desc']}", "ok", ctx.author)
        e.add_field(name="التكلفة", value=coin(ctx.guild.id, res["cost"]), inline=True)
        e.add_field(name="رصيد الشركة", value=coin(ctx.guild.id, res["balance_after"]), inline=True)
        await ctx.reply(embed=e)

    @bot.command(name="شركة_تحليل", aliases=["تحليل_شركة", "company_report"])
    async def company_report(ctx):
        c = companies.get_company_by_owner(ctx.guild.id, ctx.author.id)
        if not c:
            await ctx.reply(embed=embed("🏢 ما عندك شركة", "افتح شركة أولًا.", "warn", ctx.author))
            return

        r = companies.decision_report(c)
        p = r["preview"]
        e = embed("📊 تحليل الشركة", f"**{c['name']}**\nStrategy: **{r['strategy']}**", "purple", ctx.author)
        e.add_field(name="Success Score", value=f"**{p['success_score']}/100**", inline=True)
        e.add_field(name="Risk", value=f"**{r['risk']}/100**", inline=True)
        e.add_field(name="Net / 6h", value=coin(ctx.guild.id, p["net_company"]), inline=True)
        e.add_field(name="Stats", value=f"Marketing `{r['marketing']}`\nQuality `{r['quality']}`\nAutomation `{r['automation']}`\nSecurity `{r['security']}`\nInnovation `{r['innovation']}`", inline=True)
        e.add_field(name="Costs", value=f"Tax `{fmt(p['tax'])}`\nPayroll `{fmt(p['payroll_total'])}`\nRisk Cost `{fmt(p.get('operating_risk_cost',0))}`", inline=True)
        e.add_field(name="توقع العملية القادمة", value=f"**{r['next_event_preview']['label']}**\n{r['next_event_preview']['details']}", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شركة_بيع", aliases=["بيع_شركة", "company_sell"])
    async def sell_company_cmd(ctx, company_id: int = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed("🏢 بيع شركة", "ما عندك شركات للبيع.", "warn", ctx.author))
            return

        if len(rows) > 1 and not company_id:
            lines = []
            for c in rows:
                sec = companies.sector_info_for_guild(ctx.guild.id, c["sector_key"])
                refund = int(sec["start_cost"] * companies.SELL_REFUND_BPS // 10000)
                lines.append(f"`#{c['id']}` {sec['emoji']} **{c['name']}** — بيع بخسارة: `{refund:,}` + رصيد الشركة `{int(c['balance']):,}`")
            await ctx.reply(embed=embed("🏢 اختر شركة للبيع", "\\n".join(lines) + "\\n\\nاستخدم: `!شركة_بيع COMPANY_ID`", "warn", ctx.author))
            return

        res = companies.sell_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id)
        if not res["ok"]:
            await ctx.reply(embed=embed("❌ فشل بيع الشركة", res["error"], "bad", ctx.author))
            return

        c = res["company"]
        e = embed("🏢 تم بيع الشركة", f"بعت **{c['name']}** بخسارة.", "ok", ctx.author)
        e.add_field(name="30% من سعر فتح الشركة", value=coin(ctx.guild.id, res["refund"]), inline=True)
        e.add_field(name="رصيد الشركة المتبقي", value=coin(ctx.guild.id, res["company_balance"]), inline=True)
        e.add_field(name="المجموع المستلم", value=coin(ctx.guild.id, res["payout"]), inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="شرح_الشركات", aliases=["companies_help"])
    async def help_companies(ctx):
        e = embed("🏢 نظام الشركات", "افتح شركة، وظف أعضاء، اجمع دخل كل 6 ساعات، طور الشركة، واسحب الأرباح.", "info", ctx.author)
        e.add_field(name="الأوامر", value="`!قطاعات_الشركات`\n`!شركة_فتح tech Jaber Tech`\n`!شركتي` أو `!شركاتي`\n`!شركة_دخل`\n`!شركة_ترقية`\n`!شركة_ايداع 50000`\n`!شركة_سحب 50000`\n`!شركة_بيع COMPANY_ID`\n`!شركة_توظيف @user`\n`!شركة_طرد @user`\n`!قرارات_الشركة`\n`!شركة_قرار marketing`\n`!شركة_تحليل`\n`!الشركات`", inline=False)
        await ctx.reply(embed=e)
