import random
import discord

from nmcore.services.casino import play, parse_bet
from nmcore.services.economy import get_balance, debit, credit
from nmcore.services.log_channels import get_log_channel
from nmcore.ui import embed, coin, money_delta


GAME_NAMES = {
    "luck": "حظ",
    "double": "دبل",
    "slot": "سلوت",
    "flip": "وجه",
    "blackjack": "بلاك جاك",
}

CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


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


def new_shoe(decks: int = 6):
    shoe = []
    for _ in range(int(decks)):
        for rank in CARD_RANKS:
            shoe.extend([rank] * 4)
    random.shuffle(shoe)
    return shoe


def hand_value(cards):
    total = 0
    aces = 0

    for c in cards:
        if c == "A":
            aces += 1
            total += 11
        elif c in {"J", "Q", "K"}:
            total += 10
        else:
            total += int(c)

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total


def is_soft_17(cards):
    total = 0
    aces_as_eleven = 0

    for c in cards:
        if c == "A":
            total += 11
            aces_as_eleven += 1
        elif c in {"J", "Q", "K"}:
            total += 10
        else:
            total += int(c)

    while total > 21 and aces_as_eleven:
        total -= 10
        aces_as_eleven -= 1

    return total == 17 and aces_as_eleven > 0


def is_blackjack(cards):
    return len(cards) == 2 and hand_value(cards) == 21


def fmt_hand(cards, hide_second=False):
    if hide_second and len(cards) > 1:
        return f"`{cards[0]}` `?`"
    return " ".join(f"`{c}`" for c in cards)


def casino_lobby_embed(ctx, amount="100"):
    bal = get_balance(ctx.guild.id, ctx.author.id)
    e = embed(
        "🎰 NM Casino",
        "لوبي القمار المطوّر. اختر اللعبة من الأزرار، وكل عملية محفوظة في Money Tracker و Casino Dashboard.",
        "purple",
        ctx.author
    )
    e.add_field(name="💰 رصيدك", value=coin(ctx.guild.id, bal), inline=True)
    e.add_field(name="🎯 الرهان", value=f"`{amount}`", inline=True)
    e.add_field(
        name="🎮 الألعاب",
        value="🍀 **حظ** — سريع ومباشر\n"
        "✌️ **دبل** — مخاطرة أعلى\n"
        "🎰 **سلوت** — رموز وجوائز\n"
        "🪙 **وجه** — Coin flip\n"
        "🃏 **بلاك جاك** — Hit / Stand تفاعلي",
        inline=False
    )
    e.add_field(
        name="🛡️ قواعد مهمة",
        value="الرهان ينخصم أولًا.\n"
        "التعادل في بلاك جاك يرجع الرهان.\n"
        "إذا انتهى وقت اللعبة بدون اختيار، يرجع الرهان تلقائيًا.",
        inline=False
    )
    return e


def simulate_blackjack_round(strategy="stand17"):
    shoe = new_shoe(6)

    def draw():
        nonlocal shoe
        if not shoe:
            shoe = new_shoe(6)
        return shoe.pop()

    player = [draw(), draw()]
    dealer = [draw(), draw()]

    if is_blackjack(player) or is_blackjack(dealer):
        if is_blackjack(player) and is_blackjack(dealer):
            return "draw"
        if is_blackjack(player):
            return "win"
        return "lose"

    threshold = 17 if strategy == "stand17" else 16

    while hand_value(player) < threshold:
        player.append(draw())

    pv = hand_value(player)
    if pv > 21:
        return "lose"

    while hand_value(dealer) < 17 or is_soft_17(dealer):
        dealer.append(draw())

    dv = hand_value(dealer)
    if dv > 21:
        return "win"
    if pv > dv:
        return "win"
    if pv == dv:
        return "draw"
    return "lose"


class BlackjackGameView(discord.ui.View):
    def __init__(self, ctx, amount):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.amount_text = str(amount)
        self.finished = False
        self.processing = False
        self.bet = 0
        self.before = 0
        self.bet_tx = ""
        self.payout_tx = ""
        self.player = []
        self.dealer = []
        self.shoe = []
        self.final_embed = None
        self.message = None

    def draw_card(self):
        if not self.shoe:
            self.shoe = new_shoe(6)
        return self.shoe.pop()

    async def start(self):
        bal = get_balance(self.ctx.guild.id, self.ctx.author.id)
        bet = parse_bet(self.amount_text, bal)

        if bet is None or bet <= 0:
            return False, embed("🃏 بلاك جاك", "اكتب مبلغ صحيح.", "bad", self.ctx.author)

        if bet > bal:
            return False, embed("🃏 بلاك جاك", f"رصيدك ما يكفي. رصيدك: {bal:,}", "bad", self.ctx.author)

        self.before = bal
        self.bet = int(bet)
        self.shoe = new_shoe(6)

        tx = debit(
            self.ctx.guild.id,
            self.ctx.author.id,
            self.bet,
            "casino_bet",
            user_name=self.ctx.author.display_name,
            source_label="blackjack",
            reason="Interactive blackjack bet",
            channel_id=self.ctx.channel.id,
            message_id=getattr(self.ctx.message, "id", 0),
            metadata={"game": "blackjack", "mode": "interactive", "rules": "tie_refund_dealer_hits_soft_17_timeout_refund"}
        )

        if not tx.get("ok"):
            return False, embed("🃏 بلاك جاك", "رصيدك ما يكفي.", "bad", self.ctx.author)

        self.bet_tx = tx["tx_id"]
        self.player = [self.draw_card(), self.draw_card()]
        self.dealer = [self.draw_card(), self.draw_card()]

        if is_blackjack(self.player) or is_blackjack(self.dealer):
            if is_blackjack(self.player) and is_blackjack(self.dealer):
                await self.finish("draw")
            elif is_blackjack(self.player):
                await self.finish("blackjack")
            else:
                await self.finish("lose")
            return True, self.final_embed

        return True, self.build_embed()

    def build_embed(self, title="🃏 بلاك جاك", color="purple", reveal_dealer=False, footer_note="اختر Hit أو Stand من الأزرار."):
        player_value = hand_value(self.player)
        dealer_value = hand_value(self.dealer) if reveal_dealer else hand_value(self.dealer[:1])

        e = embed(
            title,
            f"الرهان: {coin(self.ctx.guild.id, self.bet)}\n{footer_note}",
            color,
            self.ctx.author
        )
        e.add_field(name=f"يدك — {player_value}", value=fmt_hand(self.player), inline=False)
        e.add_field(
            name=f"الديلر — {dealer_value if reveal_dealer else '?'}",
            value=fmt_hand(self.dealer, hide_second=not reveal_dealer),
            inline=False
        )
        e.add_field(name="القواعد", value="الديلر يسحب على Soft 17. أي تعادل = رجوع الرهان. انتهاء الوقت = رجوع الرهان.", inline=False)
        e.add_field(name="Bet TX", value=f"`{self.bet_tx[:12]}`", inline=True)
        return e

    async def finish(self, outcome):
        if self.finished:
            return

        self.finished = True

        if outcome == "stand":
            while hand_value(self.dealer) < 17 or is_soft_17(self.dealer):
                self.dealer.append(self.draw_card())

            pv = hand_value(self.player)
            dv = hand_value(self.dealer)

            if dv > 21:
                outcome = "win"
            elif pv > dv:
                outcome = "win"
            elif pv == dv:
                outcome = "draw"
            else:
                outcome = "lose"

        pv = hand_value(self.player)
        dv = hand_value(self.dealer)
        payout = 0

        if outcome == "blackjack":
            payout = self.bet * 2
            title = "🃏 Blackjack! فوز"
            color = "ok"
            detail = "Blackjack طبيعي."
        elif outcome == "win":
            payout = self.bet * 2
            title = "🎉 فوز في بلاك جاك"
            color = "ok"
            detail = "فزت على الديلر."
        elif outcome == "draw":
            payout = self.bet
            title = "🤝 Push / تعادل"
            color = "warn"
            detail = "تعادل، رجعنا لك الرهان."
        elif outcome == "timeout_refund":
            payout = self.bet
            title = "⏳ انتهى وقت بلاك جاك"
            color = "warn"
            detail = "انتهى وقت الاختيار، رجعنا لك الرهان تلقائيًا."
        else:
            payout = 0
            title = "💀 خسارة في بلاك جاك"
            color = "bad"
            detail = "الديلر فاز أو تعديت 21."

        if payout > 0:
            tx = credit(
                self.ctx.guild.id,
                self.ctx.author.id,
                payout,
                "casino_payout",
                user_name=self.ctx.author.display_name,
                source_label="blackjack",
                reason=f"Interactive blackjack {outcome}",
                reference_id=self.bet_tx,
                channel_id=self.ctx.channel.id,
                message_id=getattr(self.ctx.message, "id", 0),
                metadata={"game": "blackjack", "mode": "interactive", "outcome": outcome}
            )
            if tx.get("ok"):
                self.payout_tx = tx["tx_id"]

        after = get_balance(self.ctx.guild.id, self.ctx.author.id)
        net = after - self.before

        for item in self.children:
            item.disabled = True

        self.final_embed = embed(title, detail, color, self.ctx.author)
        self.final_embed.add_field(name=f"يدك — {pv}", value=fmt_hand(self.player), inline=False)
        self.final_embed.add_field(name=f"الديلر — {dv}", value=fmt_hand(self.dealer), inline=False)
        self.final_embed.add_field(name="🎯 الرهان", value=coin(self.ctx.guild.id, self.bet), inline=True)
        self.final_embed.add_field(name="💸 الصافي", value=money_delta(self.ctx.guild.id, net), inline=True)
        self.final_embed.add_field(name="قبل", value=coin(self.ctx.guild.id, self.before), inline=True)
        self.final_embed.add_field(name="بعد", value=coin(self.ctx.guild.id, after), inline=True)
        self.final_embed.add_field(name="Bet TX", value=f"`{self.bet_tx[:12]}`", inline=True)
        self.final_embed.add_field(name="Payout TX", value=f"`{self.payout_tx[:12] if self.payout_tx else '-'}`", inline=True)

        await send_action_log(
            self.ctx,
            "casino",
            f"🃏 Blackjack {outcome.upper()}",
            f"User: {self.ctx.author.mention} (`{self.ctx.author.id}`)\n"
            f"Bet: **{self.bet:,}**\nPayout: **{payout:,}**\nNet: **{net:,}**\n"
            f"Player: {self.player} = {pv}\nDealer: {self.dealer} = {dv}\n"
            f"Rules: tie_refund=true, dealer_hits_soft_17=true, timeout_refund=true\n"
            f"Bet TX: `{self.bet_tx}`\nPayout TX: `{self.payout_tx or '-'}`",
            color
        )

    async def on_timeout(self):
        if not self.finished and self.bet > 0 and self.bet_tx:
            await self.finish("timeout_refund")
            try:
                if self.message:
                    await self.message.edit(embed=self.final_embed, view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                embed=embed("🚫 غير مسموح", "هذه لعبة بلاك جاك لصاحب الأمر فقط.", "bad", interaction.user),
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Hit / اسحب", style=discord.ButtonStyle.success, emoji="➕")
    async def hit_btn(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(embed=embed("🃏 اللعبة منتهية", "ابدأ لعبة جديدة بأمر `!بلاكجاك amount`.", "warn", interaction.user), ephemeral=True)
            return
        if self.processing:
            await interaction.response.send_message(embed=embed("⏳ انتظر", "جاري تنفيذ الحركة السابقة.", "warn", interaction.user), ephemeral=True)
            return

        self.processing = True
        try:
            self.player.append(self.draw_card())
            if hand_value(self.player) > 21:
                await self.finish("lose")
                await interaction.response.edit_message(embed=self.final_embed, view=self)
                return

            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        finally:
            self.processing = False

    @discord.ui.button(label="Stand / وقف", style=discord.ButtonStyle.primary, emoji="✋")
    async def stand_btn(self, interaction, button):
        if self.finished:
            await interaction.response.send_message(embed=embed("🃏 اللعبة منتهية", "ابدأ لعبة جديدة بأمر `!بلاكجاك amount`.", "warn", interaction.user), ephemeral=True)
            return
        if self.processing:
            await interaction.response.send_message(embed=embed("⏳ انتظر", "جاري تنفيذ الحركة السابقة.", "warn", interaction.user), ephemeral=True)
            return

        self.processing = True
        try:
            await self.finish("stand")
            await interaction.response.edit_message(embed=self.final_embed, view=self)
        finally:
            self.processing = False

    @discord.ui.button(label="Rules", style=discord.ButtonStyle.secondary, emoji="📘")
    async def rules_btn(self, interaction, button):
        e = embed(
            "📘 شرح بلاك جاك",
            "اضغط **Hit** عشان تسحب ورقة.\n"
            "اضغط **Stand** عشان توقف وتخلي الديلر يلعب.\n"
            "الديلر يسحب على Soft 17.\n"
            "أي تعادل يرجع الرهان.\n"
            "إذا تعديت 21 تخسر.\n"
            "إذا انتهى الوقت بدون اختيار، يرجع الرهان.",
            "info",
            interaction.user
        )
        await interaction.response.send_message(embed=e, ephemeral=True)


class CasinoView(discord.ui.View):
    def __init__(self, ctx, amount):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.amount = str(amount)

    async def play_game(self, interaction, game):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=embed("🚫 غير مسموح", "هذا الكازينو لصاحب الأمر فقط.", "bad", interaction.user), ephemeral=True)
            return

        if game == "blackjack":
            bj = BlackjackGameView(self.ctx, self.amount)
            ok, e = await bj.start()
            if not ok:
                await interaction.response.send_message(embed=e, ephemeral=True)
                return
            await interaction.response.send_message(embed=e, view=bj)
            try:
                bj.message = await interaction.original_response()
            except Exception:
                pass
            return

        res = play(interaction.guild.id, interaction.user.id, interaction.user.display_name, game, self.amount, interaction.channel.id, 0)
        if not res["ok"]:
            await interaction.response.send_message(embed=embed("🎰 فشل اللعب", res["error"], "bad", interaction.user), ephemeral=True)
            return

        await send_casino_result(interaction, self.ctx, res, game)

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


async def send_casino_result(interaction, ctx, res, game):
    color = "ok" if res["outcome"] == "win" else "warn" if res["outcome"] == "draw" else "bad"
    title = {"win": "🎉 فوز في الكازينو", "lose": "💀 خسارة في الكازينو", "draw": "🤝 تعادل في الكازينو"}[res["outcome"]]

    e = embed(title, f"**اللعبة:** `{GAME_NAMES.get(game, game)}`\n{res['detail']}", color, interaction.user)
    e.add_field(name="🎯 الرهان", value=coin(interaction.guild.id, res["bet"]), inline=True)
    e.add_field(name="💸 الصافي", value=money_delta(interaction.guild.id, res["net"]), inline=True)
    e.add_field(name="قبل", value=coin(interaction.guild.id, res["before"]), inline=True)
    e.add_field(name="بعد", value=coin(interaction.guild.id, res["after"]), inline=True)
    e.add_field(name="TX", value=f"`{str(res['bet_tx'])[:12]}`", inline=False)
    await interaction.response.send_message(embed=e)

    await send_action_log(
        ctx,
        "casino",
        f"🎰 Casino {res['outcome'].upper()}",
        f"User: {interaction.user.mention} (`{interaction.user.id}`)\n"
        f"Game: `{game}`\nBet: **{res['bet']:,}**\nPayout: **{res['payout']:,}**\nNet: **{res['net']:,}**\n"
        f"Before: **{res['before']:,}**\nAfter: **{res['after']:,}**\nDetail: {res['detail']}\n"
        f"Bet TX: `{res['bet_tx']}`\nPayout TX: `{res['payout_tx'] or '-'}`",
        color
    )


def setup(bot):
    async def run(ctx, game, amount):
        if game == "blackjack":
            view = BlackjackGameView(ctx, amount)
            ok, e = await view.start()
            if not ok:
                await ctx.reply(embed=e)
                return
            msg = await ctx.reply(embed=e, view=view)
            view.message = msg
            return

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

        await send_action_log(
            ctx,
            "casino",
            f"🎰 Casino {res['outcome'].upper()}",
            f"User: {ctx.author.mention} (`{ctx.author.id}`)\nGame: `{game}`\nBet: **{res['bet']:,}**\n"
            f"Payout: **{res['payout']:,}**\nNet: **{res['net']:,}**\nBefore: **{res['before']:,}**\nAfter: **{res['after']:,}**\n"
            f"Detail: {res['detail']}\nBet TX: `{res['bet_tx']}`\nPayout TX: `{res['payout_tx'] or '-'}`",
            color
        )

    @bot.command(name="كازينو", aliases=["casino"])
    async def casino_menu(ctx, amount: str = "100"):
        await ctx.reply(embed=casino_lobby_embed(ctx, amount), view=CasinoView(ctx, amount))

    @bot.command(name="حظ", aliases=["luck"])
    async def luck(ctx, amount: str):
        await run(ctx, "luck", amount)

    @bot.command(name="دبل", aliases=["double"])
    async def double(ctx, amount: str):
        await run(ctx, "double", amount)

    @bot.command(name="سلوت", aliases=["slot"])
    async def slot(ctx, amount: str):
        await run(ctx, "slot", amount)

    @bot.command(name="وجه", aliases=["flip"])
    async def flip(ctx, amount: str):
        await run(ctx, "flip", amount)

    @bot.command(name="بلاكجاك", aliases=["bj", "blackjack"])
    async def blackjack(ctx, amount: str):
        await run(ctx, "blackjack", amount)

    @bot.command(name="اختبار_بلاكجاك", aliases=["bj_test", "blackjack_test"])
    async def blackjack_test(ctx, rounds: int = 5000):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return

        rounds = max(100, min(int(rounds or 5000), 50000))
        counts = {"win": 0, "lose": 0, "draw": 0}

        for _ in range(rounds):
            counts[simulate_blackjack_round("stand17")] += 1

        win_pct = counts["win"] / rounds * 100
        lose_pct = counts["lose"] / rounds * 100
        draw_pct = counts["draw"] / rounds * 100

        e = embed("🧪 اختبار بلاك جاك", f"تم اختبار **{rounds:,}** جولة بدون لمس الفلوس.", "info", ctx.author)
        e.add_field(name="Win", value=f"{counts['win']:,} ({win_pct:.1f}%)", inline=True)
        e.add_field(name="Lose", value=f"{counts['lose']:,} ({lose_pct:.1f}%)", inline=True)
        e.add_field(name="Draw", value=f"{counts['draw']:,} ({draw_pct:.1f}%)", inline=True)
        e.add_field(name="القواعد", value="6-deck shoe, dealer hits soft 17, ties refund.", inline=False)
        await ctx.reply(embed=e)
