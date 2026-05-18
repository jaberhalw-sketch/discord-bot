import os
import discord
from nmcore.services.settings import ensure_guild, command_system, is_system_enabled, channel_restriction_for_system
from nmcore.services.levels import message_xp
from nmcore.services.protection import get_settings, contains_bad, has_link, matched_bad_word
from nmcore.services.activity import log_event
from nmcore.services import warnings as warnsvc
from nmcore.config import LEVEL_COOLDOWN_SECONDS
from nmcore.commands import economy, casino, levels, real_estate, moderation, admin, shop, giveaways
from nmcore.ui import embed


DEFAULT_DEV_OWNER_IDS = {"881722045031915521"}


def dev_mode_enabled() -> bool:
    return os.getenv("NM_DEV_MODE", "1").strip().lower() not in {"0", "false", "off", "no"}


def dev_owner_ids() -> set[int]:
    raw = os.getenv("NM_OWNER_IDS", "").strip()
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()] if raw else []
    ids = set()

    for p in parts:
        if p.isdigit():
            ids.add(int(p))

    if not ids:
        ids = {int(x) for x in DEFAULT_DEV_OWNER_IDS if x.isdigit()}

    return ids


def is_dev_owner(user_id:int) -> bool:
    return int(user_id or 0) in dev_owner_ids()


def setup_bot(bot):
    economy.setup(bot)
    casino.setup(bot)
    levels.setup(bot)
    real_estate.setup(bot)
    moderation.setup(bot)
    admin.setup(bot)
    shop.setup(bot)
    giveaways.setup(bot)

    @bot.check
    async def global_toggle_check(ctx):
        if not ctx.guild or not ctx.command:
            return True

        ensure_guild(ctx.guild.id, ctx.guild.name)

        if dev_mode_enabled() and not is_dev_owner(ctx.author.id):
            await ctx.reply(embed=embed(
                "🚧 البوت قيد التطوير",
                "حاليًا أوامر NM System مقفلة للتجربة والتطوير. بتشتغل للجميع بعد ما يجهز النظام.",
                "warn",
                ctx.author
            ))
            return False

        sys = command_system(ctx.command.name)

        if not is_system_enabled(ctx.guild.id, sys):
            await ctx.reply(embed=embed(
                "🔒 النظام مقفل",
                f"نظام `{sys}` مقفل من الداشبورد.",
                "warn",
                ctx.author
            ))
            return False

        required_channel_id = channel_restriction_for_system(ctx.guild.id, sys)
        if required_channel_id and int(ctx.channel.id) != int(required_channel_id):
            await ctx.reply(embed=embed(
                "📍 الروم غير صحيح",
                f"هذا الأمر مخصص للروم الصحيح فقط: <#{required_channel_id}>",
                "warn",
                ctx.author
            ))
            return False

        return True

    @bot.event
    async def on_message(message):
        if not message.guild or message.author.bot:
            await bot.process_commands(message)
            return

        ensure_guild(message.guild.id, message.guild.name)

        try:
            s = get_settings(message.guild.id)

            if s.get("enabled") and is_system_enabled(message.guild.id, "protection"):
                words = [w.strip() for w in str(s.get("bad_words") or "").split(",") if w.strip()]

                bad_word = ""
                bad = False

                if bool(s.get("bad_words_enabled")):
                    bad_word = matched_bad_word(message.content, words)
                    bad = bool(bad_word) or contains_bad(message.content, words)

                link = bool(s.get("links_enabled")) and has_link(message.content)

                if bad or link:
                    if bool(s.get("delete_messages")):
                        try:
                            await message.delete()
                        except Exception:
                            pass

                    if bad:
                        reason = "استخدام كلمة ممنوعة في السيرفر"

                        warnsvc.add_warning(
                            message.guild.id,
                            message.author.id,
                            message.author.display_name,
                            bot.user.id if bot.user else 0,
                            str(bot.user) if bot.user else "NM System",
                            reason,
                            message.content[:1000]
                        )

                        log_event(
                            message.guild.id,
                            "protection_warning",
                            message.author.id,
                            message.author.display_name,
                            message.channel.id,
                            message.channel.name,
                            "Bad word blocked + warning issued",
                            message.content[:500],
                            {"matched": bad_word}
                        )

                        try:
                            e = embed(
                                "🛡️ رسالة ممنوعة",
                                f"{message.author.mention}\nتم حذف الرسالة وإعطاؤك **تحذير** بسبب استخدام كلام ممنوع.",
                                "bad",
                                message.author
                            )
                            e.add_field(name="الإجراء", value="حذف الرسالة + تحذير", inline=True)
                            e.add_field(name="النظام", value="Protection", inline=True)
                            await message.channel.send(embed=e, delete_after=8)
                        except Exception:
                            pass

                    else:
                        log_event(
                            message.guild.id,
                            "protection_link",
                            message.author.id,
                            message.author.display_name,
                            message.channel.id,
                            message.channel.name,
                            "Link blocked",
                            message.content[:500]
                        )

                        try:
                            await message.channel.send(
                                embed=embed(
                                    "🔗 رابط ممنوع",
                                    f"{message.author.mention}\nتم حذف الرابط حسب إعدادات الحماية.",
                                    "warn",
                                    message.author
                                ),
                                delete_after=7
                            )
                        except Exception:
                            pass

                    return

        except Exception as e:
            try:
                log_event(
                    message.guild.id,
                    "runtime_error",
                    message.author.id,
                    message.author.display_name,
                    message.channel.id,
                    message.channel.name,
                    "Protection error",
                    f"{type(e).__name__}: {e}"
                )
            except Exception:
                pass

        try:
            if is_system_enabled(message.guild.id, "levels"):
                res = message_xp(message.guild.id, message.author.id, LEVEL_COOLDOWN_SECONDS)
                if res and res[2]:
                    await message.channel.send(embed=embed(
                        "🎉 Level Up!",
                        f"{message.author.mention} وصل إلى لفل **{res[1]}**!",
                        "purple",
                        message.author
                    ))
        except Exception:
            pass

        await bot.process_commands(message)

    @bot.event
    async def on_member_join(member):
        ensure_guild(member.guild.id, member.guild.name)
        log_event(member.guild.id, "member_join", member.id, member.display_name, title="Member joined")

    @bot.event
    async def on_member_remove(member):
        log_event(member.guild.id, "member_leave", member.id, member.display_name, title="Member left")
