import random
import time
from nmcore.config import CASINO_COOLDOWN_SECONDS
from nmcore.services.economy import get_balance, debit, credit, clean_amount, MAX_TX_AMOUNT

_last_play = {}


def parse_bet(text, balance:int):
    s = str(text or "").strip().lower().replace(",", "")

    if s in {"all", "الكل", "فل"}:
        return int(balance)

    mult = 1
    if s.endswith("k"):
        mult = 1000
        s = s[:-1]
    elif s.endswith("m"):
        mult = 1000000
        s = s[:-1]

    try:
        if "." in s:
            val = float(s)
            if not val.is_integer():
                return None
            bet = int(val) * mult
        else:
            bet = int(s) * mult
    except Exception:
        return None

    return clean_amount(bet)


def play(guild_id:int, user_id:int, user_name:str, game:str, bet_text, channel_id=0, message_id=0):
    key = (int(guild_id), int(user_id))
    now = time.time()

    bal = get_balance(guild_id, user_id)
    bet = parse_bet(bet_text, bal)

    if bet is None or bet <= 0:
        return {"ok": False, "error": "اكتب مبلغ صحيح أكبر من 0."}

    if bet > bal:
        return {"ok": False, "error": f"رصيدك ما يكفي. رصيدك: {bal:,}"}

    if bet > MAX_TX_AMOUNT:
        return {"ok": False, "error": "المبلغ كبير جدًا."}

    if now - _last_play.get(key, 0) < CASINO_COOLDOWN_SECONDS:
        return {"ok": False, "error": f"انتظر {CASINO_COOLDOWN_SECONDS} ثواني بين اللعبات."}

    _last_play[key] = now

    before = bal

    bet_tx = debit(
        guild_id,
        user_id,
        bet,
        "casino_bet",
        user_name=user_name,
        source_label=game,
        reason=f"Bet on {game}",
        channel_id=channel_id,
        message_id=message_id,
        metadata={"game": game}
    )

    if not bet_tx["ok"]:
        return {"ok": False, "error": "رصيدك ما يكفي."}

    outcome = "lose"
    payout = 0
    detail = ""

    if game in {"luck", "حظ"}:
        win = random.random() < 0.48
        outcome = "win" if win else "lose"
        payout = bet * 2 if win else 0
        detail = "الحظ وقف معك" if win else "الحظ ضدك"

    elif game in {"double", "دبل"}:
        win = random.random() < 0.45
        outcome = "win" if win else "lose"
        payout = bet * 2 if win else 0
        detail = "الدبل نجح" if win else "الدبل فشل"

    elif game in {"flip", "وجه"}:
        win = random.random() < 0.50
        outcome = "win" if win else "lose"
        payout = bet * 2 if win else 0
        detail = "العملة معك" if win else "العملة ضدك"

    elif game in {"slot", "سلوت"}:
        icons = ["🍒", "🍋", "💎", "7️⃣", "⭐", "🍉"]
        roll = [random.choice(icons) for _ in range(3)]
        detail = " ".join(roll)

        if len(set(roll)) == 1:
            outcome = "win"
            payout = bet * 5
        elif len(set(roll)) == 2:
            outcome = "win"
            payout = bet * 2

    elif game in {"blackjack", "bj", "بلاكجاك"}:
        player = random.randint(16, 22)
        dealer = random.randint(16, 22)
        detail = f"أنت {player} | الديلر {dealer}"

        if player > 21:
            outcome = "lose"
        elif dealer > 21 or player > dealer:
            outcome = "win"
            payout = bet * 2
        elif player == dealer:
            outcome = "draw"
            payout = bet
        else:
            outcome = "lose"

    payout_tx = None
    if payout > 0:
        payout_tx = credit(
            guild_id,
            user_id,
            payout,
            "casino_payout",
            user_name=user_name,
            source_label=game,
            reason=f"{game} {outcome}",
            reference_id=bet_tx["tx_id"],
            channel_id=channel_id,
            message_id=message_id,
            metadata={"game": game, "outcome": outcome}
        )

        if not payout_tx.get("ok"):
            return {"ok": False, "error": "صار خطأ في دفع الجائزة. راجع Money Tracker."}

    after = get_balance(guild_id, user_id)

    return {
        "ok": True,
        "game": game,
        "bet": bet,
        "before": before,
        "after": after,
        "outcome": outcome,
        "payout": payout,
        "net": after - before,
        "detail": detail,
        "bet_tx": bet_tx.get("tx_id"),
        "payout_tx": payout_tx.get("tx_id") if payout_tx else ""
    }
