import discord
from nmcore.services import real_estate
from nmcore.services.log_channels import get_log_channel
from nmcore.ui import embed, coin


async def send_action_log(ctx, log_key, title, description, color="info"):
    try:
        ch_id = get_log_channel(ctx.guild.id, log_key)
        if not ch_id:
            return
        ch = ctx.guild.get_channel(int(ch_id))
        if not ch:
            return
        await ch.send(embed=embed(title, description, color, ctx.author))
    except Exception:
        pass


def property_line(ctx, p):
    owner = "Available" if int(p["owner_id"] or 0) == 0 else f"Owned by {p['owner_name'] or p['owner_id']}"
    return (
        f"`#{p['id']}` **{p['display_name']}**\n"
        f"السعر: {coin(ctx.guild.id, p['price'])} • الإيجار: **{int(p['rent']):,}** • Level **{int(p['level'])}**\n"
        f"الحالة: `{owner}`"
    )


class RealEstateShopView(discord.ui.View):
    def __init__(self, ctx, rows, page=0):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.rows = list(rows)
        self.page = int(page or 0)
        self.per_page = 5
        self.refresh_buttons()

    def max_page(self):
        if not self.rows:
            return 0
        return max(0, (len(self.rows) - 1) // self.per_page)

    def current_rows(self):
        start = self.page * self.per_page
        return self.rows[start:start + self.per_page]

    def build_embed(self):
        if not self.rows:
            return embed("🏘️ متجر العقارات", "ما فيه عقارات متاحة حاليًا.", "warn", self.ctx.author)

        lines = [property_line(self.ctx, p) for p in self.current_rows()]
        e = embed("🏘️ متجر العقارات", "\n\n".join(lines), "purple", self.ctx.author)
        e.add_field(name="الصفحة", value=f"{self.page + 1}/{self.max_page() + 1}", inline=True)
        e.add_field(name="المتاح", value=str(len(self.rows)), inline=True)
        e.add_field(name="طريقة الشراء", value="اضغط زر **شراء** بالأسفل أو اكتب `!شراء ID`", inline=False)
        return e

    def refresh_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.max_page()

        current = self.current_rows()
        buttons = [self.buy1, self.buy2, self.buy3, self.buy4, self.buy5]
        for i, btn in enumerate(buttons):
            if i < len(current):
                btn.disabled = False
                btn.label = f"شراء #{current[i]['id']}"
            else:
                btn.disabled = True
                btn.label = "-"

    async def update_message(self, interaction):
        self.refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def buy_property(self, interaction, index):
        if interaction.user.id != self.ctx.author.id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("هذا المتجر مفتوح لصاحب الأمر فقط.", ephemeral=True)
            return

        current = self.current_rows()
        if index >= len(current):
            await interaction.response.send_message("العقار غير موجود في هذه الصفحة.", ephemeral=True)
            return

        p = current[index]
        res = real_estate.buy(interaction.guild.id, interaction.user.id, interaction.user.display_name, int(p["id"]))

        if not res["ok"]:
            await interaction.response.send_message(res["error"], ephemeral=True)
            return

        e = embed("✅ تم شراء العقار", f"العقار: **{res['name']}**", "ok", interaction.user)
        e.add_field(name="السعر", value=coin(interaction.guild.id, res["price"]), inline=True)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        e.add_field(name="الإيجار", value="يتجمع كل 3 ساعات وتستلمه بأمر `!ايجار`", inline=False)
        await interaction.response.send_message(embed=e)

        try:
            await send_action_log(
                self.ctx,
                "economy",
                "🏘️ Real Estate Shop Purchase",
                f"User: {interaction.user.mention} (`{interaction.user.id}`)\nProperty: **{res['name']}** (`{p['id']}`)\nPrice: **{int(res['price']):,}**\nTX: `{res['tx_id']}`",
                "money"
            )
        except Exception:
            pass

    @discord.ui.button(label="السابق", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_btn(self, interaction, button):
        self.page = max(0, self.page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="التالي", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_btn(self, interaction, button):
        self.page = min(self.max_page(), self.page + 1)
        await self.update_message(interaction)

    @discord.ui.button(label="شراء #1", style=discord.ButtonStyle.success, emoji="🏠", row=1)
    async def buy1(self, interaction, button):
        await self.buy_property(interaction, 0)

    @discord.ui.button(label="شراء #2", style=discord.ButtonStyle.success, emoji="🏠", row=1)
    async def buy2(self, interaction, button):
        await self.buy_property(interaction, 1)

    @discord.ui.button(label="شراء #3", style=discord.ButtonStyle.success, emoji="🏠", row=1)
    async def buy3(self, interaction, button):
        await self.buy_property(interaction, 2)

    @discord.ui.button(label="شراء #4", style=discord.ButtonStyle.success, emoji="🏠", row=2)
    async def buy4(self, interaction, button):
        await self.buy_property(interaction, 3)

    @discord.ui.button(label="شراء #5", style=discord.ButtonStyle.success, emoji="🏠", row=2)
    async def buy5(self, interaction, button):
        await self.buy_property(interaction, 4)


def setup(bot):
    @bot.command(name="متجر", aliases=["shop"])
    async def shop(ctx, page:int=1):
        rows = real_estate.rows(ctx.guild.id, only_available=True)
        view = RealEstateShopView(ctx, rows, max(0, int(page or 1) - 1))
        await ctx.reply(embed=view.build_embed(), view=view)

    @bot.command(name="شراء", aliases=["buy"])
    async def buy(ctx, property_id:int):
        res = real_estate.buy(ctx.guild.id, ctx.author.id, ctx.author.display_name, int(property_id))

        if not res["ok"]:
            await ctx.reply(embed=embed("🏘️ فشل شراء العقار", res["error"], "bad", ctx.author))
            return

        e = embed("✅ تم شراء العقار", f"العقار: **{res['name']}**", "ok", ctx.author)
        e.add_field(name="السعر", value=coin(ctx.guild.id, res["price"]), inline=True)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        e.add_field(name="الإيجار", value="يتجمع كل 3 ساعات وتستلمه بأمر `!ايجار`", inline=False)
        await ctx.reply(embed=e)

    @bot.command(name="مشترياتي", aliases=["my_purchases", "عقاراتي_من_المتجر"])
    async def my_purchases(ctx):
        rows = real_estate.my_rows(ctx.guild.id, ctx.author.id)

        if not rows:
            await ctx.reply(embed=embed("🏘️ مشترياتك", "ما عندك عقارات حاليًا.", "warn", ctx.author))
            return

        lines = [f"`#{r['id']}` **{r['display_name']}** • Rent **{int(r['rent']):,}** • L{int(r['level'])}" for r in rows[:20]]
        e = embed("🏘️ عقاراتك / مشترياتك", "\n".join(lines), "purple", ctx.author)
        e.add_field(name="استلام الإيجار", value="اكتب `!ايجار`، الإيجار يتجمع كل 3 ساعات.", inline=False)
        await ctx.reply(embed=e)
