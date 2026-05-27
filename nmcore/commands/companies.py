import discord
from nmcore.ui import embed, coin
from nmcore.services import companies


def fmt(n):
    return f"{int(n or 0):,}"


def blocks(current, max_value=10, filled='█', empty='░'):
    current = max(0, min(max_value, int(current or 0)))
    return filled * current + empty * (max_value - current)


def yes_no(flag):
    return "✅ مفتوح" if int(flag or 0) else "⛔ مقفل"


def sector_field_value(guild_id, key):
    s = companies.sector_info_for_guild(guild_id, key)
    return (
        f"**المفتاح:** `{key}`\n"
        f"**الحالة:** {yes_no(s.get('enabled', 1))}\n"
        f"**سعر الفتح:** {coin(guild_id, s['start_cost'])}\n"
        f"**دخل كل 6 ساعات:** {coin(guild_id, s['base_income'])}\n"
        f"**أساس الترقية:** {coin(guild_id, s['upgrade_base'])}"
    )


def company_embed(ctx, c):
    sector = companies.sector_info_for_guild(ctx.guild.id, c["sector_key"])
    preview = companies.income_preview(c)
    report = companies.decision_report(c)
    cycles, remaining = companies.rent_like_remaining(c)
    members = companies.company_members(ctx.guild.id, c["id"])
    employees = [m for m in members if str(m.get('role')) != 'owner']

    e = embed(
        f"{sector['emoji']} {c['name']}",
        f"**القطاع:** {sector['name']} • `{c['sector_key']}`\n"
        f"**المالك:** <@{int(c['owner_id'])}>\n"
        f"**معرّف الشركة:** `{int(c['id'])}`",
        "purple",
        ctx.author,
    )

    e.add_field(
        name="🏢 نظرة عامة",
        value=(
            f"**المستوى:** `{int(c['level'] or 1)}`\n"
            f"**الاستراتيجية:** `{report['strategy']}`\n"
            f"**السمعة:** `{int(c['reputation'] or 0)}`\n"
            f"**القرارات المتخذة:** `{int(c.get('decisions', 0) or 0)}`"
        ),
        inline=True,
    )
    e.add_field(
        name="💰 المالية",
        value=(
            f"**رصيد الشركة:** {coin(ctx.guild.id, int(c['balance'] or 0))}\n"
            f"**الدخل الإجمالي:** `{fmt(preview['gross'])}`\n"
            f"**صافي دخل الشركة:** `{fmt(preview['net_company'])}`\n"
            f"**العائد للموظف:** `{fmt(preview['employee_bonus_each'])}`"
        ),
        inline=True,
    )
    e.add_field(
        name="👥 الفريق",
        value=(
            f"**الموظفون:** `{len(employees)}` / `8`\n"
            f"**المالك محسوب:** نعم\n"
            f"**رواتب الموظفين:** `{fmt(preview['payroll_total'])}`\n"
            f"**المخاطرة التشغيلية:** `{fmt(preview.get('operating_risk_cost', 0))}`"
        ),
        inline=True,
    )

    e.add_field(
        name="🧠 تطوير الشركة",
        value=(
            f"**Marketing:** `{report['marketing']}/10` {blocks(report['marketing'])}\n"
            f"**Quality:** `{report['quality']}/10` {blocks(report['quality'])}\n"
            f"**Automation:** `{report['automation']}/10` {blocks(report['automation'])}\n"
            f"**Security:** `{report['security']}/10` {blocks(report['security'])}\n"
            f"**Innovation:** `{report['innovation']}/10` {blocks(report['innovation'])}"
        ),
        inline=False,
    )

    e.add_field(
        name="📈 دورة الدخل",
        value=(
            f"**الضريبة:** `{fmt(preview['tax'])}`\n"
            f"**النجاح:** `{preview.get('success_score', 0)}/100`\n"
            f"**الحدث المتوقع:** **{report['next_event_preview']['label']}**\n"
            f"{report['next_event_preview']['details']}"
        ),
        inline=False,
    )

    if cycles > 0:
        timing = f"✅ **دفعات جاهزة الآن:** `{cycles}`"
    else:
        timing = f"⏳ **الدخل القادم بعد:** {companies.seconds_to_text(remaining)}"
    e.add_field(name="⏰ التوقيت", value=timing, inline=False)

    if members:
        team_lines = []
        for m in members[:10]:
            role = "المالك" if str(m.get('role')) == 'owner' else 'موظف'
            team_lines.append(f"• <@{int(m['user_id'])}> — `{role}`")
        e.add_field(name="📋 قائمة الفريق", value="\n".join(team_lines), inline=False)

    e.set_footer(text="NM System Companies • واضح ومرتب")
    return e


def list_companies_embed(ctx, rows, title='🏢 شركاتك'):
    e = embed(title, "ملخص واضح لكل شركاتك الحالية.", "purple", ctx.author)
    for c in rows[:10]:
        sector = companies.sector_info_for_guild(ctx.guild.id, c['sector_key'])
        preview = companies.income_preview(c)
        cycles, remaining = companies.rent_like_remaining(c)
        status = f"جاهز `{cycles}`" if cycles > 0 else f"بعد {companies.seconds_to_text(remaining)}"
        e.add_field(
            name=f"{sector['emoji']} #{int(c['id'])} • {c['name']}",
            value=(
                f"**القطاع:** `{c['sector_key']}`\n"
                f"**المستوى:** `{int(c['level'] or 1)}`\n"
                f"**الرصيد:** {coin(ctx.guild.id, int(c['balance'] or 0))}\n"
                f"**صافي / 6 ساعات:** `{fmt(preview['net_company'])}`\n"
                f"**الدخل:** {status}"
            ),
            inline=True,
        )
    e.add_field(name='ملاحظة', value='الحد الأقصى لكل عضو هو **3 شركات فعالة**.', inline=False)
    return e



# -------------------------
# Interactive Views / Buttons
# -------------------------

class OwnerOnlyView(discord.ui.View):
    def __init__(self, owner_id:int, timeout:int=180):
        super().__init__(timeout=timeout)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(interaction.user.id) != self.owner_id:
            await interaction.response.send_message("❌ هذا التحكم مو لك.", ephemeral=True)
            return False
        return True


class CompanyDecisionSelect(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        opts = []
        for key, d in companies.COMPANY_DECISIONS.items():
            opts.append(discord.SelectOption(label=d["name"][:100], value=key, description=d["desc"][:100], emoji=d["emoji"]))
        super().__init__(placeholder="اختر قرار للشركة", min_values=1, max_values=1, options=opts[:25])

    async def callback(self, interaction: discord.Interaction):
        company = self.parent_view.current_company()
        if not company:
            await interaction.response.send_message("❌ الشركة غير موجودة.", ephemeral=True)
            return

        res = companies.make_decision_for_company(
            interaction.guild.id,
            interaction.user.id,
            interaction.user.display_name,
            int(company["id"]),
            self.values[0],
        )

        if not res["ok"]:
            await interaction.response.send_message(res["error"], ephemeral=True)
            return

        refreshed = companies.get_company_for_owner(interaction.guild.id, interaction.user.id, int(company["id"]))
        e = company_embed(self.parent_view.ctx, refreshed)
        e.add_field(name="✅ آخر قرار", value=f"{res['decision']['emoji']} **{res['decision']['name']}**\nالتكلفة: {coin(interaction.guild.id, res['cost'])}", inline=False)
        await interaction.response.edit_message(embed=e, view=self.parent_view)


class CompanyPagerView(OwnerOnlyView):
    def __init__(self, ctx, rows, index:int=0):
        super().__init__(ctx.author.id, timeout=240)
        self.ctx = ctx
        self.rows = list(rows or [])
        self.index = max(0, min(index, len(self.rows)-1)) if self.rows else 0
        self.add_item(CompanyDecisionSelect(self))

    def current_company(self):
        rows = companies.user_companies(self.ctx.guild.id, self.ctx.author.id)
        if not rows:
            return None
        ids = [int(r["id"]) for r in rows]
        old_id = int(self.rows[self.index]["id"]) if self.rows and self.index < len(self.rows) else ids[0]
        self.rows = rows
        if old_id in ids:
            self.index = ids.index(old_id)
        else:
            self.index = min(self.index, len(rows)-1)
        return self.rows[self.index]

    def page_text(self):
        if not self.rows:
            return "0/0"
        return f"{self.index+1}/{len(self.rows)}"

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.rows:
            self.index = (self.index - 1) % len(self.rows)
        c = self.current_company()
        await interaction.response.edit_message(embed=company_embed(self.ctx, c), view=self)

    @discord.ui.button(label="التالي ▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.rows:
            self.index = (self.index + 1) % len(self.rows)
        c = self.current_company()
        await interaction.response.edit_message(embed=company_embed(self.ctx, c), view=self)

    @discord.ui.button(label="📈 استلام الدخل", style=discord.ButtonStyle.success, row=2)
    async def income_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = self.current_company()
        if not c:
            await interaction.response.send_message("❌ ما عندك شركة.", ephemeral=True)
            return

        res = companies.collect_income_for_company(interaction.guild.id, interaction.user.id, interaction.user.display_name, int(c["id"]))
        if not res["ok"]:
            await interaction.response.send_message(res["error"], ephemeral=True)
            return

        refreshed = companies.get_company_for_owner(interaction.guild.id, interaction.user.id, int(c["id"]))
        e = company_embed(self.ctx, refreshed)
        event = res.get("event", {})
        e.add_field(name="📈 تم استلام الدخل", value=f"دفعات: **{res['cycles']}**\nالمبلغ: {coin(interaction.guild.id, res['company_amount'])}\n**{event.get('label','Stable')}**\n{event.get('details','')}", inline=False)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="📊 تحليل", style=discord.ButtonStyle.primary, row=2)
    async def analyze_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = self.current_company()
        e = company_embed(self.ctx, c)
        logs = companies.ledger(interaction.guild.id, int(c["id"]), 5)
        if logs:
            e.add_field(name="🧾 آخر الحركات", value="\n".join(f"• `{r['action']}` — `{fmt(r['amount'])}`" for r in logs[:5]), inline=False)
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="🏪 متجر الشركات", style=discord.ButtonStyle.secondary, row=2)
    async def market_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CompanyMarketView(self.ctx)
        await interaction.response.edit_message(embed=view.embed(), view=view)

    @discord.ui.button(label="💸 بيع", style=discord.ButtonStyle.danger, row=2)
    async def sell_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = self.current_company()
        sec = companies.sector_info_for_guild(interaction.guild.id, c["sector_key"])
        refund = int(sec["start_cost"] * companies.SELL_REFUND_BPS // 10000)
        await interaction.response.send_message(
            f"بيع الشركة **{c['name']}** يعطيك 30% من سعر الفتح: `{refund:,}` + رصيد الشركة `{int(c['balance']):,}`.\nللتأكيد اكتب: `!شركة_بيع {int(c['id'])}`",
            ephemeral=True
        )


class CompanyNameModal(discord.ui.Modal):
    def __init__(self, ctx, sector_key):
        sector = companies.sector_info_for_guild(ctx.guild.id, sector_key)
        super().__init__(title=f"فتح شركة: {sector['name']}"[:45])
        self.ctx = ctx
        self.sector_key = sector_key
        self.company_name = discord.ui.TextInput(label="اسم الشركة", placeholder="مثال: Jaber Tech", min_length=2, max_length=40)
        self.add_item(self.company_name)

    async def on_submit(self, interaction: discord.Interaction):
        if int(interaction.user.id) != int(self.ctx.author.id):
            await interaction.response.send_message("❌ هذا المتجر مو لك.", ephemeral=True)
            return
        res = companies.create_company(interaction.guild.id, interaction.user.id, interaction.user.display_name, self.sector_key, str(self.company_name.value))
        if not res["ok"]:
            await interaction.response.send_message(res["error"], ephemeral=True)
            return
        e = embed("✅ تم فتح الشركة", f"**{res['name']}**\nالقطاع: {res['sector']['emoji']} **{res['sector']['name']}**\nالتكلفة: {coin(interaction.guild.id, res['cost'])}", "ok", interaction.user)
        await interaction.response.send_message(embed=e, ephemeral=True)


class CompanySectorSelect(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        opts = []
        for key in parent.page_keys():
            s = companies.sector_info_for_guild(parent.ctx.guild.id, key)
            if int(s.get("enabled", 1)):
                opts.append(discord.SelectOption(label=s["name"][:100], value=key, description=f"فتح {s['start_cost']:,} • دخل {s['base_income']:,}/6h", emoji=s["emoji"]))
        if not opts:
            opts = [discord.SelectOption(label="No enabled sectors", value="none", description="لا يوجد قطاعات مفتوحة")]
        super().__init__(placeholder="اختر قطاع لفتح شركة", min_values=1, max_values=1, options=opts[:25])

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]
        if key == "none":
            await interaction.response.send_message("ما فيه قطاعات متاحة.", ephemeral=True)
            return
        await interaction.response.send_modal(CompanyNameModal(self.parent_view.ctx, key))


class CompanyMarketView(OwnerOnlyView):
    PER_PAGE = 5

    def __init__(self, ctx, page:int=0):
        super().__init__(ctx.author.id, timeout=240)
        self.ctx = ctx
        self.page = int(page)
        self.refresh_select()

    def keys(self):
        return list(companies.SECTORS.keys())

    def page_keys(self):
        ks = self.keys()
        start = self.page * self.PER_PAGE
        return ks[start:start+self.PER_PAGE]

    def max_page(self):
        return max(0, (len(self.keys()) - 1) // self.PER_PAGE)

    def refresh_select(self):
        for item in list(self.children):
            if isinstance(item, CompanySectorSelect):
                self.remove_item(item)
        self.add_item(CompanySectorSelect(self))

    def embed(self):
        e = embed("🏪 متجر الشركات", "اختر قطاع من القائمة ثم اكتب اسم الشركة. الأسعار من الداشبورد ومحفوظة.", "info", self.ctx.author)
        for key in self.page_keys():
            s = companies.sector_info_for_guild(self.ctx.guild.id, key)
            status = "✅ متاح" if int(s.get("enabled", 1)) else "⛔ مقفل"
            e.add_field(
                name=f"{s['emoji']} {s['name']}",
                value=f"**المفتاح:** `{key}`\n**الحالة:** {status}\n**سعر الفتح:** {coin(self.ctx.guild.id, s['start_cost'])}\n**دخل / 6h:** {coin(self.ctx.guild.id, s['base_income'])}\n**المخاطرة:** `{int(s['risk_bps'])/100:.1f}%`",
                inline=True
            )
        e.set_footer(text=f"Page {self.page+1}/{self.max_page()+1} • كل عضو يملك حتى 3 شركات")
        return e

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary, row=1)
    async def prev_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % (self.max_page()+1)
        self.refresh_select()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary, row=1)
    async def next_market(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % (self.max_page()+1)
        self.refresh_select()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="🏢 شركاتي", style=discord.ButtonStyle.primary, row=1)
    async def my_companies_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = companies.user_companies(interaction.guild.id, interaction.user.id)
        if not rows:
            await interaction.response.send_message("ما عندك شركات بعد.", ephemeral=True)
            return
        view = CompanyPagerView(self.ctx, rows)
        await interaction.response.edit_message(embed=company_embed(self.ctx, rows[0]), view=view)


def setup(bot):
    @bot.command(name='قطاعات_الشركات', aliases=['company_sectors'])
    async def sectors(ctx):
        e = embed('🏢 قطاعات الشركات', 'هنا كل القطاعات بشكل واضح. اختر المفتاح واستخدمه في أمر فتح الشركة.', 'info', ctx.author)
        keys = list(companies.SECTORS.keys())
        for key in keys[:24]:
            s = companies.sector_info_for_guild(ctx.guild.id, key)
            e.add_field(name=f"{s['emoji']} {s['name']}", value=sector_field_value(ctx.guild.id, key), inline=True)
        e.add_field(
            name='🧾 طريقة فتح الشركة',
            value='`!شركة_فتح sector_name اسم الشركة`\nمثال: `!شركة_فتح tech Jaber Tech`',
            inline=False,
        )
        e.set_footer(text='تقدر تملك 3 شركات • الأسعار من الداشبورد إذا تم تعديلها')
        await ctx.reply(embed=e, view=CompanyMarketView(ctx))

    @bot.command(name='شركة_فتح', aliases=['فتح_شركة', 'company_create'])
    async def create(ctx, sector_key: str = None, *, name: str = None):
        if not sector_key or not name:
            e = embed('🏢 فتح شركة', 'لازم تحدد القطاع واسم الشركة.', 'info', ctx.author)
            e.add_field(name='الاستخدام', value='`!شركة_فتح tech Jaber Tech`', inline=False)
            e.add_field(name='عرض القطاعات', value='`!قطاعات_الشركات`', inline=False)
            await ctx.reply(embed=e)
            return

        res = companies.create_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, sector_key, name)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل فتح الشركة', res['error'], 'bad', ctx.author))
            return

        e = embed('✅ تم فتح الشركة', f"**{res['name']}**\nتم إنشاء الشركة بنجاح.", 'ok', ctx.author)
        e.add_field(name='القطاع', value=f"{res['sector']['emoji']} **{res['sector']['name']}**\n`{sector_key}`", inline=True)
        e.add_field(name='التكلفة', value=coin(ctx.guild.id, res['cost']), inline=True)
        e.add_field(name='ID الشركة', value=f"`{res['id']}`", inline=True)
        e.add_field(name='الخطوة التالية', value='شوف شركتك عبر `!شركتي` أو اجمع ملخصك عبر `!شركاتي`.', inline=False)
        await ctx.reply(embed=e)

    @bot.command(name='شركتي', aliases=['company', 'my_company'])
    async def my_company(ctx, company_id: int = None):
        c = companies.get_company_for_owner(ctx.guild.id, ctx.author.id, company_id)
        if not c:
            await ctx.reply(embed=embed('🏢 ما عندك شركة', 'افتح شركة باستخدام: `!شركة_فتح tech اسم الشركة`', 'warn', ctx.author))
            return
        await ctx.reply(embed=company_embed(ctx, c), view=CompanyPagerView(ctx, companies.user_companies(ctx.guild.id, ctx.author.id), 0))

    @bot.command(name='شركاتي', aliases=['my_companies'])
    async def my_companies(ctx):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)
        if not rows:
            await ctx.reply(embed=embed('🏢 شركاتك', 'ما عندك شركات. تقدر تفتح حتى 3 شركات.', 'warn', ctx.author))
            return
        await ctx.reply(embed=list_companies_embed(ctx, rows), view=CompanyPagerView(ctx, rows, 0))

    @bot.command(name='الشركات', aliases=['top_companies', 'توب_الشركات'])
    async def top(ctx):
        rows = companies.top_companies(ctx.guild.id, 10)
        if not rows:
            await ctx.reply(embed=embed('🏢 الشركات', 'ما فيه شركات للحين.', 'warn', ctx.author))
            return
        e = embed('🏆 توب الشركات', 'أفضل الشركات الحالية في السيرفر.', 'purple', ctx.author)
        for i, c in enumerate(rows, 1):
            sec = companies.sector_info_for_guild(ctx.guild.id, c['sector_key'])
            preview = companies.income_preview(c)
            e.add_field(
                name=f"#{i} • {sec['emoji']} {c['name']}",
                value=(
                    f"**المالك:** <@{int(c['owner_id'])}>\n"
                    f"**المستوى:** `{int(c['level'])}`\n"
                    f"**الرصيد:** {coin(ctx.guild.id, int(c['balance'] or 0))}\n"
                    f"**الصافي / 6 ساعات:** `{fmt(preview['net_company'])}`"
                ),
                inline=True,
            )
        await ctx.reply(embed=e)

    @bot.command(name='شركة_دخل', aliases=['دخل_الشركة', 'company_income'])
    async def collect_income(ctx):
        res = companies.collect_income(ctx.guild.id, ctx.author.id, ctx.author.display_name)
        if not res['ok']:
            await ctx.reply(embed=embed('📈 دخل الشركة', res['error'], 'warn', ctx.author))
            return
        event = res.get('event', {})
        e = embed('📈 تم استلام دخل الشركة', 'تمت إضافة دخل الشركة بنجاح.', 'ok', ctx.author)
        e.add_field(name='الدفعات المتجمعة', value=f"`{res['cycles']}`", inline=True)
        e.add_field(name='دخل الشركة الصافي', value=coin(ctx.guild.id, res['company_amount']), inline=True)
        e.add_field(name='الرصيد بعد الاستلام', value=coin(ctx.guild.id, res['balance_after']), inline=True)
        e.add_field(name='الحدث الحالي', value=f"**{event.get('label', 'Stable Operation')}**\n{event.get('details', '')}", inline=False)
        if int(res.get('event_delta', 0)):
            e.add_field(name='تأثير الحدث', value=coin(ctx.guild.id, res.get('event_delta', 0)), inline=True)
        if res.get('paid_employees'):
            e.add_field(name='رواتب الموظفين', value=f"الموظفون المدفوع لهم: `{res['paid_employees']}`\nلكل موظف: {coin(ctx.guild.id, res['employee_each'])}", inline=True)
        await ctx.reply(embed=e)

    @bot.command(name='شركة_ترقية', aliases=['ترقية_الشركة', 'company_upgrade'])
    async def upgrade(ctx, company_id: int = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)
        if not rows:
            await ctx.reply(embed=embed('⬆️ ترقية الشركة', 'ما عندك شركة.', 'warn', ctx.author))
            return

        if len(rows) > 1 and not company_id:
            lines = []
            for c in rows:
                sec = companies.sector_info_for_guild(ctx.guild.id, c['sector_key'])
                lines.append(f"`#{c['id']}` {sec['emoji']} **{c['name']}** — L{int(c['level'])} — Balance `{fmt(c['balance'])}`")
            await ctx.reply(embed=embed('⬆️ اختر الشركة اللي تبي تطورها', "\n".join(lines) + "\n\nاستخدم: `!شركة_ترقية COMPANY_ID`", 'info', ctx.author))
            return

        target_id = company_id or int(rows[0]['id'])
        res = companies.upgrade_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, target_id)
        if not res['ok']:
            await ctx.reply(embed=embed('⬆️ فشل ترقية الشركة', res['error'], 'bad', ctx.author))
            return

        e = embed('⬆️ تمت ترقية الشركة', f"الشركة: **{res['company']['name']}**", 'ok', ctx.author)
        e.add_field(name='المستوى الجديد', value=f"`{res['level']}`", inline=True)
        e.add_field(name='تكلفة الترقية', value=coin(ctx.guild.id, res['cost']), inline=True)
        e.add_field(name='رصيد الشركة', value=coin(ctx.guild.id, res['balance_after']), inline=True)
        await ctx.reply(embed=e)


    @bot.command(name='شركة_ايداع', aliases=['ايداع_شركة', 'company_deposit'])
    async def deposit(ctx, first: int = None, second: int = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed('💼 إيداع للشركة', 'ما عندك شركة.', 'warn', ctx.author))
            return

        if first is None or first <= 0:
            await ctx.reply(embed=embed('💼 إيداع للشركة', 'الاستخدام:\n`!شركة_ايداع AMOUNT`\nأو إذا عندك أكثر من شركة:\n`!شركة_ايداع COMPANY_ID AMOUNT`', 'info', ctx.author))
            return

        if second is None:
            if len(rows) > 1:
                lines = []
                for c in rows:
                    lines.append(f"`#{c['id']}` **{c['name']}** — Balance `{fmt(c['balance'])}`")
                await ctx.reply(embed=embed('💼 اختر شركة للإيداع', "\n".join(lines) + "\n\nاستخدم: `!شركة_ايداع COMPANY_ID AMOUNT`", 'info', ctx.author))
                return
            company_id = int(rows[0]['id'])
            amount = int(first)
        else:
            company_id = int(first)
            amount = int(second)

        res = companies.deposit_to_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id, amount)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل الإيداع', res['error'], 'bad', ctx.author))
            return

        e = embed('✅ تم الإيداع', f"الشركة: **{res['company']['name']}**", 'ok', ctx.author)
        e.add_field(name='المبلغ', value=coin(ctx.guild.id, res['amount']), inline=True)
        e.add_field(name='رصيد الشركة', value=coin(ctx.guild.id, res['balance_after']), inline=True)
        await ctx.reply(embed=e)


    @bot.command(name='شركة_سحب', aliases=['سحب_شركة', 'company_withdraw'])
    async def withdraw(ctx, first: int = None, second: int = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed('💼 سحب من الشركة', 'ما عندك شركة.', 'warn', ctx.author))
            return

        if first is None or first <= 0:
            await ctx.reply(embed=embed('💼 سحب من الشركة', 'الاستخدام:\n`!شركة_سحب AMOUNT`\nأو إذا عندك أكثر من شركة:\n`!شركة_سحب COMPANY_ID AMOUNT`', 'info', ctx.author))
            return

        if second is None:
            if len(rows) > 1:
                lines = []
                for c in rows:
                    lines.append(f"`#{c['id']}` **{c['name']}** — Balance `{fmt(c['balance'])}`")
                await ctx.reply(embed=embed('💼 اختر شركة للسحب', "\n".join(lines) + "\n\nاستخدم: `!شركة_سحب COMPANY_ID AMOUNT`", 'info', ctx.author))
                return
            company_id = int(rows[0]['id'])
            amount = int(first)
        else:
            company_id = int(first)
            amount = int(second)

        res = companies.withdraw_from_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id, amount)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل السحب', res['error'], 'bad', ctx.author))
            return

        e = embed('✅ تم السحب', f"الشركة: **{res['company']['name']}**", 'ok', ctx.author)
        e.add_field(name='المبلغ', value=coin(ctx.guild.id, res['amount']), inline=True)
        e.add_field(name='رصيد الشركة', value=coin(ctx.guild.id, res['balance_after']), inline=True)
        await ctx.reply(embed=e)


    @bot.command(name='شركة_توظيف', aliases=['توظيف_شركة', 'company_hire'])
    async def hire(ctx, company_id: int = None, member: discord.Member = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed('👥 توظيف', 'ما عندك شركة.', 'warn', ctx.author))
            return

        if member is None:
            # Backward compatibility: if only member was mentioned, company_id becomes missing.
            if ctx.message.mentions and len(rows) == 1:
                member = ctx.message.mentions[0]
                company_id = int(rows[0]['id'])
            else:
                lines = []
                for c in rows:
                    lines.append(f"`#{c['id']}` **{c['name']}**")
                await ctx.reply(embed=embed('👥 اختر شركة للتوظيف', "\n".join(lines) + "\n\nالاستخدام: `!شركة_توظيف COMPANY_ID @user`", 'info', ctx.author))
                return

        if member.bot:
            await ctx.reply(embed=embed('❌ لا يمكن', 'ما تقدر توظف بوت.', 'bad', ctx.author))
            return

        res = companies.hire_for_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id, member.id, member.display_name)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل التوظيف', res['error'], 'bad', ctx.author))
            return

        await ctx.reply(embed=embed('✅ تم التوظيف', f"{member.mention} صار موظف في شركة **{res['company']['name']}**.", 'ok', ctx.author))


    @bot.command(name='شركة_طرد', aliases=['طرد_شركة', 'company_fire'])
    async def fire(ctx, company_id: int = None, member: discord.Member = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed('👥 طرد موظف', 'ما عندك شركة.', 'warn', ctx.author))
            return

        if member is None:
            if ctx.message.mentions and len(rows) == 1:
                member = ctx.message.mentions[0]
                company_id = int(rows[0]['id'])
            else:
                lines = []
                for c in rows:
                    lines.append(f"`#{c['id']}` **{c['name']}**")
                await ctx.reply(embed=embed('👥 اختر شركة للطرد', "\n".join(lines) + "\n\nالاستخدام: `!شركة_طرد COMPANY_ID @user`", 'info', ctx.author))
                return

        res = companies.fire_from_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id, member.id)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل الطرد', res['error'], 'bad', ctx.author))
            return

        await ctx.reply(embed=embed('✅ تم طرد الموظف', f"تم إخراج {member.mention} من شركة **{res['company']['name']}**.", 'ok', ctx.author))


    @bot.command(name='قرارات_الشركة', aliases=['company_decisions'])
    async def company_decisions(ctx):
        e = embed('🧠 قرارات الشركة', 'القرارات التالية تطور الشركة وتغيّر أداءها.', 'info', ctx.author)
        for key, d in companies.COMPANY_DECISIONS.items():
            e.add_field(
                name=f"{d['emoji']} {d['name']}",
                value=(
                    f"**المفتاح:** `{key}`\n"
                    f"**التكلفة:** {coin(ctx.guild.id, d['cost'])}\n"
                    f"**التأثير:** {d['desc']}"
                ),
                inline=True,
            )
        e.add_field(name='الاستخدام', value='`!شركة_قرار marketing`\n`!شركة_قرار quality`\n`!شركة_قرار aggressive`', inline=False)
        await ctx.reply(embed=e)

    @bot.command(name='شركة_قرار', aliases=['قرار_شركة', 'company_decision'])
    async def company_decision(ctx, decision_key: str = None):
        if not decision_key:
            await ctx.reply(embed=embed('🧠 قرار شركة', 'استخدم: `!شركة_قرار marketing`\nلعرض القرارات: `!قرارات_الشركة`', 'info', ctx.author))
            return
        res = companies.make_decision(ctx.guild.id, ctx.author.id, ctx.author.display_name, decision_key)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل القرار', res['error'], 'bad', ctx.author))
            return
        c = companies.get_company_by_owner(ctx.guild.id, ctx.author.id)
        r = companies.decision_report(c)
        d = res['decision']
        e = embed('✅ تم تنفيذ القرار', f"**{d['name']}**\n{d['desc']}", 'ok', ctx.author)
        e.add_field(name='التكلفة', value=coin(ctx.guild.id, res['cost']), inline=True)
        e.add_field(name='الرصيد بعد القرار', value=coin(ctx.guild.id, res['balance_after']), inline=True)
        e.add_field(name='الاستراتيجية الحالية', value=f"`{r['strategy']}`", inline=True)
        e.add_field(
            name='التقييم بعد القرار',
            value=(
                f"Marketing `{r['marketing']}/10`\n"
                f"Quality `{r['quality']}/10`\n"
                f"Automation `{r['automation']}/10`\n"
                f"Security `{r['security']}/10`\n"
                f"Innovation `{r['innovation']}/10`\n"
                f"Risk `{r['risk']}`"
            ),
            inline=False,
        )
        e.add_field(name='توقع العملية القادمة', value=f"**{r['next_event_preview']['label']}**\n{r['next_event_preview']['details']}", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name='شركة_تحليل', aliases=['تحليل_شركة', 'company_report'])
    async def company_report(ctx, company_id: int = None):
        c = companies.get_company_for_owner(ctx.guild.id, ctx.author.id, company_id)
        if not c:
            await ctx.reply(embed=embed('🏢 تحليل الشركة', 'ما عندك شركة. استخدم `!شركة_فتح` أولًا.', 'warn', ctx.author))
            return
        report = companies.decision_report(c)
        logs = companies.ledger(ctx.guild.id, c['id'], 5)
        e = company_embed(ctx, c)
        e.title = f"📊 تحليل الشركة • {c['name']}"
        log_lines = []
        for row in logs[:5]:
            log_lines.append(f"• `{row['action']}` — `{fmt(row['amount'])}`")
        if log_lines:
            e.add_field(name='🧾 آخر الحركات', value='\n'.join(log_lines), inline=False)
        e.add_field(name='📌 ملخص سريع', value=f"النجاح الحالي: `{report['preview'].get('success_score', 0)}/100`\nالصافي المتوقع: `{fmt(report['preview']['net_company'])}`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name='شركة_بيع', aliases=['بيع_شركة', 'company_sell'])
    async def sell_company_cmd(ctx, company_id: int = None):
        rows = companies.user_companies(ctx.guild.id, ctx.author.id)
        if not rows:
            await ctx.reply(embed=embed('🏢 بيع شركة', 'ما عندك شركات للبيع.', 'warn', ctx.author))
            return
        if len(rows) > 1 and not company_id:
            e = embed('🏢 اختر شركة للبيع', 'بما أنك تملك أكثر من شركة، حدّد ID الشركة التي تريد بيعها.', 'warn', ctx.author)
            for c in rows:
                sec = companies.sector_info_for_guild(ctx.guild.id, c['sector_key'])
                refund = int(sec['start_cost'] * companies.SELL_REFUND_BPS // 10000)
                e.add_field(name=f"#{c['id']} • {c['name']}", value=f"**القطاع:** {sec['emoji']} {sec['name']}\n**استرداد 30%:** `{refund:,}`\n**رصيد الشركة:** `{int(c['balance']):,}`", inline=True)
            e.add_field(name='الاستخدام', value='`!شركة_بيع COMPANY_ID`', inline=False)
            await ctx.reply(embed=e)
            return
        res = companies.sell_company(ctx.guild.id, ctx.author.id, ctx.author.display_name, company_id)
        if not res['ok']:
            await ctx.reply(embed=embed('❌ فشل بيع الشركة', res['error'], 'bad', ctx.author))
            return
        c = res['company']
        e = embed('🏢 تم بيع الشركة', f"تم بيع **{c['name']}** بخسارة كما طلبت.", 'ok', ctx.author)
        e.add_field(name='30% من سعر الفتح', value=coin(ctx.guild.id, res['refund']), inline=True)
        e.add_field(name='رصيد الشركة المتبقي', value=coin(ctx.guild.id, res['company_balance']), inline=True)
        e.add_field(name='إجمالي المستلم', value=coin(ctx.guild.id, res['payout']), inline=True)
        await ctx.reply(embed=e)


    @bot.command(name='متجر_الشركات', aliases=['company_shop', 'companies_shop'])
    async def company_shop(ctx):
        view = CompanyMarketView(ctx)
        await ctx.reply(embed=view.embed(), view=view)

    @bot.command(name='شرح_الشركات', aliases=['companies_help'])
    async def help_companies(ctx):
        e = embed('🏢 شرح نظام الشركات', 'كل أوامر الشركات في مكان واحد بشكل مرتب وواضح.', 'info', ctx.author)
        e.add_field(name='1) البداية', value='`!قطاعات_الشركات`\n`!شركة_فتح tech Jaber Tech`', inline=True)
        e.add_field(name='2) متابعة شركاتك', value='`!شركتي`\n`!شركاتي`\n`!شركة_تحليل`', inline=True)
        e.add_field(name='3) الأرباح والتطوير', value='`!شركة_دخل`\n`!شركة_ترقية COMPANY_ID`\n`!شركة_ايداع COMPANY_ID 50000`\n`!شركة_سحب COMPANY_ID 50000`', inline=True)
        e.add_field(name='4) الموظفون', value='`!شركة_توظيف COMPANY_ID @user`\n`!شركة_طرد COMPANY_ID @user`', inline=True)
        e.add_field(name='5) القرارات', value='`!قرارات_الشركة`\n`!شركة_قرار marketing`', inline=True)
        e.add_field(name='6) البيع والترتيب', value='`!شركة_بيع COMPANY_ID`\n`!الشركات`', inline=True)
        e.add_field(name='معلومة', value='العضو يقدر يملك حتى **3 شركات**، والأسعار قابلة للتعديل من الداشبورد.', inline=False)
        await ctx.reply(embed=e)
