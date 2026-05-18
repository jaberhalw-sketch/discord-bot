import discord
from nmcore.services import shop as shopsvc
from nmcore.ui import embed, coin, money_delta

def setup(bot):
    @bot.command(name="متجر", aliases=["shop"])
    async def shop(ctx):
        shopsvc.ensure_tables()
        shopsvc.seed_defaults(ctx.guild.id)
        rows = shopsvc.items(ctx.guild.id, include_disabled=False)

        if not rows:
            await ctx.reply(embed=embed("🛒 المتجر", "المتجر فاضي حاليًا.", "warn", ctx.author))
            return

        lines = []
        for r in rows[:20]:
            lines.append(f"`{r['item_key']}` — **{r['name']}** | {coin(ctx.guild.id, r['price'])}")

        await ctx.reply(embed=embed(
            "🛒 متجر NM",
            "\n".join(lines) + "\n\nاستخدم: `!شراء item_key`",
            "purple",
            ctx.author
        ))

    @bot.command(name="شراء", aliases=["buy"])
    async def buy(ctx, item_key:str):
        res = shopsvc.buy_item(
            ctx.guild.id,
            ctx.author.id,
            ctx.author.display_name,
            item_key,
            ctx.channel.id,
            ctx.message.id
        )

        if not res["ok"]:
            await ctx.reply(embed=embed("🛒 فشل الشراء", res["error"], "bad", ctx.author))
            return

        role_id = int(res.get("role_id") or 0)
        role_given = False

        if role_id:
            role = ctx.guild.get_role(role_id)
            if role:
                try:
                    await ctx.author.add_roles(role, reason="NM Shop purchase")
                    role_given = True
                except Exception:
                    role_given = False

        e = embed("✅ تم الشراء", f"اشتريت: **{res['item']['name']}**", "ok", ctx.author)
        e.add_field(name="السعر", value=coin(ctx.guild.id, res["price"]), inline=True)
        e.add_field(name="TX", value=f"`{res['tx_id'][:12]}`", inline=True)
        if role_id:
            e.add_field(name="Role", value="✅ تم إعطاء الرتبة" if role_given else "⚠️ لم أقدر أعطي الرتبة", inline=False)

        await ctx.reply(embed=e)

    @bot.command(name="صندوق", aliases=["lootbox", "box"])
    async def lootbox(ctx, cost:str="1000"):
        try:
            cost_int = int(str(cost).replace(",", ""))
        except Exception:
            await ctx.reply(embed=embed("🎁 الصندوق", "اكتب مبلغ صحيح. مثال: `!صندوق 1000`", "bad", ctx.author))
            return

        res = shopsvc.lootbox(
            ctx.guild.id,
            ctx.author.id,
            ctx.author.display_name,
            cost_int,
            ctx.channel.id,
            ctx.message.id
        )

        if not res["ok"]:
            await ctx.reply(embed=embed("🎁 فشل فتح الصندوق", res["error"], "bad", ctx.author))
            return

        color = "ok" if res["net"] > 0 else "warn" if res["net"] == 0 else "bad"
        e = embed(f"🎁 صندوق {res['title']}", f"Roll: `{res['roll']}`", color, ctx.author)
        e.add_field(name="التكلفة", value=coin(ctx.guild.id, res["cost"]), inline=True)
        e.add_field(name="الجائزة", value=coin(ctx.guild.id, res["reward"]), inline=True)
        e.add_field(name="الصافي", value=money_delta(ctx.guild.id, res["net"]), inline=True)
        await ctx.reply(embed=e)
