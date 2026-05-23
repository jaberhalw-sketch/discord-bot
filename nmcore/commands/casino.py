import discord
from nmcore.services.casino import play
from nmcore.services.log_channels import get_log_channel
from nmcore.ui import embed, coin, money_delta


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


GAME_NAMES = {
    "luck": "حظ",
    "double": "دبل",
    "slot": "سلوت",
    "flip": "وجه",
    "blackjack": "بلاك جاك",
}


class CasinoView(discord.ui.View):
    def __init__(self, ctx, amount):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.amount = str(amount)

    async def play_game(self, interaction, game):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=embed("🚫 غير مسموح", "هذا الكازينو لصاحب الأمر فقط.", "bad", interaction.user), ephemeral=True)
            return

        res = play(interaction.guild.id, interaction.user.id, interaction.user.display_name, game, self.amount, interaction.channel.id, 0)

        if not res["ok"]:
            await interaction.response.send_message(embed=embed("🎰 فشل اللعب", res["error"], "bad", interaction.user), ephemeral=True)
            return

        color = "ok" if res["outcome"] == "win" else "warn" if res["outcome"] == "draw" else "bad"
        title = {"win": "🎉 فوز في الكازينو", "lose": "💀 خسارة في الكازينو", "draw": "🤝 تعادل في الكازينو"}[res["outcome"]]

        e = embed(title, f"**اللعبة:** `{GAME_NAMES.get(game, game)}`\n{res['detail']}", color, interaction.user)
        e.add_field(name="🎯 الرهان", value=coin(interaction.guild.id, res["bet"]), inline=True)
        e.add_field(name="💸 الصافي", value=money_delta(interaction.guild.id, res["net"]), inline=True)
        e.add_field(name="قبل", value=coin(interaction.guild.id, res["before"]), inline=True)
        e.add_field(name="بعد", value=coin(interaction.guild.id, res["after"]), inline=True)
        e.add_field(name="TX", value=f"`{str(res['bet_tx'])[:12]}`", inline=False)
        await interaction.response.send_message(embed=e)

        await send_action_log(self.ctx, "casino", f"🎰 Casino {res['outcome'].upper()}", f"User: {interaction.user.mention} (`{interaction.user.id}`)\nGame: `{game}`\nBet: **{res['bet']:,}**\nPayout: **{res['payout']:,}**\nNet: **{res['net']:,}**\nBefore: **{res['before']:,}**\nAfter: **{res['after']:,}**\nDetail: {res['detail']}\nBet TX: `{res['bet_tx']}`\nPayout TX: `{res['payout_tx'] or '-'}`", color)

    @discord.ui.button(label="حظ", style=discord.ButtonStyle.primary, emoji="🍀")
    async def luck(self, interaction, button):
        await self.play_game(interaction, "luck")

    @discord.ui.button(label="دبل", style=discord.ButtonStyle.success, emoji="✌️")
    async def double(self, interaction, button):
        await self.play_game(interaction, "double")

    @discord.ui.button(label="سلوت", style=discord.ButtonStyle.danger, emoji="🎰")
    async def slot(self, interaction, button):
        await self.play_game(interaction, "slot")

    @discord.ui.button(label="وجه", style=discord.ButtonStyle.secondary, emoji="🪙")
    async def flip(self, interaction, button):
        await self.play_game(interaction, "flip")

    @discord.ui.button(label="بلاك جاك", style=discord.ButtonStyle.primary, emoji="🃏")
    async def blackjack(self, interaction, button):
        await self.play_game(interaction, "blackjack")


def casino_menu_embed(ctx, amount):
    e = embed("🎰 كازينو NM", f"اختر اللعبة من الأزرار بالأسفل.\nالرهان الحالي: **{amount}**", "purple", ctx.author)
    e.add_field(name="الألعاب", value="🍀 حظ\n✌️ دبل\n🎰 سلوت\n🪙 وجه\n🃏 بلاك جاك", inline=True)
    e.add_field(name="ملاحظات", value="كل العمليات محفوظة في Money Tracker و Casino Dashboard.", inline=True)
    return e


def setup(bot):
    async def run(ctx, game, amount):
        res = play(ctx.guild.id, ctx.author.id, ctx.author.display_name, game, amount, ctx.channel.id, ctx.message.id)

        if not res["ok"]:
            await ctx.reply(embed=embed("🎰 Casino رفض العملية", f"**السبب:** {res['error']}", "bad", ctx.author))
            return

        color = "ok" if res["outcome"] == "win" else "warn" if res["outcome"] == "draw" else "bad"
        title = {"win": "🎉 فوز في الكازينو", "lose": "💀 خسارة في الكازينو", "draw": "🤝 تعادل في الكازينو"}[res["outcome"]]

        e = embed(title, f"**اللعبة:** `{GAME_NAMES.get(game, game)}`\n{res['detail']}", color, ctx.author)
        e.add_field(name="🎯 الرهان", value=coin(ctx.guild.id, res["bet"]), inline=True)
        e.add_field(name="💸 الصافي", value=money_delta(ctx.guild.id, res["net"]), inline=True)
        e.add_field(name="قبل", value=coin(ctx.guild.id, res["before"]), inline=True)
        e.add_field(name="بعد", value=coin(ctx.guild.id, res["after"]), inline=True)
        e.add_field(name="Audit TX", value=f"`{str(res['bet_tx'])[:12]}`", inline=False)
        await ctx.reply(embed=e)

        await send_action_log(ctx, "casino", f"🎰 Casino {res['outcome'].upper()}", f"User: {ctx.author.mention} (`{ctx.author.id}`)\nGame: `{game}`\nBet: **{res['bet']:,}**\nPayout: **{res['payout']:,}**\nNet: **{res['net']:,}**\nBefore: **{res['before']:,}**\nAfter: **{res['after']:,}**\nDetail: {res['detail']}\nBet TX: `{res['bet_tx']}`\nPayout TX: `{res['payout_tx'] or '-'}`", color)

    @bot.command(name="كازينو", aliases=["casino"])
    async def casino_menu(ctx, amount:str="100"):
        await ctx.reply(embed=casino_menu_embed(ctx, amount), view=CasinoView(ctx, amount))

    @bot.command(name="حظ", aliases=["luck"])
    async def luck(ctx, amount:str):
        await run(ctx, "luck", amount)

    @bot.command(name="دبل", aliases=["double"])
    async def double(ctx, amount:str):
        await run(ctx, "double", amount)

    @bot.command(name="سلوت", aliases=["slot"])
    async def slot(ctx, amount:str):
        await run(ctx, "slot", amount)

    @bot.command(name="وجه", aliases=["flip"])
    async def flip(ctx, amount:str):
        await run(ctx, "flip", amount)

    @bot.command(name="بلاكجاك", aliases=["bj", "blackjack"])
    async def blackjack(ctx, amount:str):
        await run(ctx, "blackjack", amount)
