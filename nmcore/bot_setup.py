import os
import asyncio
import discord
from discord.ext import commands
from nmcore.services.settings import ensure_guild, command_system, is_system_enabled, channel_restriction_for_system, is_dev_mode_enabled
from nmcore.services.levels import message_xp, add_voice_xp, voice_xp_interval
from nmcore.services.protection import get_settings, check_message, is_ignored_channel, is_whitelisted_member
from nmcore.services.activity import log_event
from nmcore.services import warnings as warnsvc
from nmcore.services.log_channels import get_log_channel
from nmcore.services import antiraid
from nmcore.services import guides
from nmcore.config import LEVEL_COOLDOWN_SECONDS
from nmcore.commands import economy, casino, levels, real_estate, moderation, admin, shop, giveaways, lfg, game_roles, profile, boosts, companies
from nmcore.ui import embed
from nmcore.services import boost_rewards
from nmcore.services import post_rewards


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


def fmt_dt(dt):
    try:
        return f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)"
    except Exception:
        return "Unknown"


def role_list(member):
    try:
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        return "\n".join(roles[:30]) if roles else "No roles"
    except Exception:
        return "Unknown"


async def send_log(bot, guild, log_key, title, description="", color="info", member=None):
    try:
        ch_id = get_log_channel(guild.id, log_key)
        if not ch_id:
            return

        ch = guild.get_channel(int(ch_id))
        if not ch:
            return

        await ch.send(embed=embed(title, description, color, member))
    except Exception:
        pass


async def audit_reason(guild, action, target_id):
    try:
        async for entry in guild.audit_logs(limit=8, action=action):
            if entry.target and int(getattr(entry.target, "id", 0)) == int(target_id):
                return entry.user, entry.reason or "No reason"
    except Exception:
        pass
    return None, "Unknown / No audit permission"


async def detect_leave_type(member):
    # Ban check first
    try:
        async for entry in member.guild.audit_logs(limit=8, action=discord.AuditLogAction.ban):
            if entry.target and int(getattr(entry.target, "id", 0)) == int(member.id):
                return "ban", entry.user, entry.reason or "No reason"
    except Exception:
        pass

    # Kick check
    try:
        async for entry in member.guild.audit_logs(limit=8, action=discord.AuditLogAction.kick):
            if entry.target and int(getattr(entry.target, "id", 0)) == int(member.id):
                return "kick", entry.user, entry.reason or "No reason"
    except Exception:
        pass

    return "left", None, "Left by themselves"



async def get_latest_audit(guild, action, target_id=None):
    try:
        async for entry in guild.audit_logs(limit=6, action=action):
            if target_id is None:
                return entry
            if entry.target and int(getattr(entry.target, "id", 0)) == int(target_id):
                return entry
    except Exception:
        return None
    return None


async def handle_antiraid_action(bot, guild, action_type, executor, target_text, reason=""):
    try:
        settings = antiraid.get_settings(guild.id)

        if not antiraid.feature_enabled(settings, action_type):
            return

        if not executor or executor.bot:
            return

        member = guild.get_member(int(executor.id))
        if antiraid.is_trusted(settings, member):
            return

        state = antiraid.record_action(guild.id, executor.id, action_type, settings)

        log_event(
            guild.id,
            f"antiraid_{action_type}",
            executor.id,
            str(executor),
            0,
            "",
            f"Anti-Raid watched: {action_type}",
            f"Target={target_text}, Count={state['count']}/{state['threshold']}, Reason={reason}"
        )

        await send_log(
            bot,
            guild,
            "server",
            f"🛡️ Anti-Raid: {action_type}",
            f"Executor: {executor.mention if hasattr(executor, 'mention') else executor} (`{executor.id}`)\n"
            f"Target: {target_text}\n"
            f"Count: `{state['count']}/{state['threshold']}` in `{state['window']}s`\n"
            f"Reason: `{reason or '-'}`",
            "warn"
        )

        if state.get("triggered"):
            punishment = await antiraid.punish_member(member, settings)

            log_event(
                guild.id,
                f"antiraid_triggered_{action_type}",
                executor.id,
                str(executor),
                0,
                "",
                f"Anti-Raid triggered: {action_type}",
                f"Target={target_text}, Punishment={punishment}"
            )

            await send_log(
                bot,
                guild,
                "server",
                f"🚨 Anti-Raid Triggered: {action_type}",
                f"Executor: {executor.mention if hasattr(executor, 'mention') else executor} (`{executor.id}`)\n"
                f"Target: {target_text}\n"
                f"Punishment: `{punishment}`",
                "bad"
            )
    except Exception as e:
        try:
            log_event(guild.id, "antiraid_error", 0, "", 0, "", "Anti-Raid error", f"{type(e).__name__}: {e}")
        except Exception:
            pass




_GUIDE_LOOP_STARTED = False

async def guide_background_loop(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await guides.send_all_due_guides(bot, force=False)
        except Exception:
            pass
        await asyncio.sleep(10 * 60)





async def voice_xp_background_loop(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            for guild in list(bot.guilds):
                if not is_system_enabled(guild.id, "levels"):
                    continue

                for channel in getattr(guild, "voice_channels", []):
                    for member in getattr(channel, "members", []):
                        if member.bot:
                            continue
                        if not getattr(member, "voice", None):
                            continue
                        if member.voice.self_deaf or member.voice.deaf:
                            continue

                        res = add_voice_xp(guild.id, member.id)
                        if res and res[2]:
                            try:
                                log_event(guild.id, "voice_level_up", member.id, member.display_name, channel.id, channel.name, "Voice level up", f"Level {res[1]}")
                            except Exception:
                                pass
        except Exception:
            pass

        await asyncio.sleep(voice_xp_interval())




_ENSURED_GUILD_CACHE = {}


def safe_ensure_guild_once(guild):
    if not guild:
        return

    now = int(asyncio.get_event_loop().time())
    gid = int(guild.id)
    last = int(_ENSURED_GUILD_CACHE.get(gid, 0) or 0)

    if now - last < 600:
        return

    try:
        ensure_guild(guild.id, guild.name)
        _ENSURED_GUILD_CACHE[gid] = now
    except Exception:
        pass


def setup_bot(bot):
    global _GUIDE_LOOP_STARTED
    if not _GUIDE_LOOP_STARTED:
        _GUIDE_LOOP_STARTED = True
        try:
            bot.loop.create_task(guide_background_loop(bot))
            bot.loop.create_task(voice_xp_background_loop(bot))
        except Exception:
            pass

    economy.setup(bot)
    casino.setup(bot)
    levels.setup(bot)
    real_estate.setup(bot)
    moderation.setup(bot)
    admin.setup(bot)
    shop.setup(bot)
    giveaways.setup(bot)
    lfg.setup(bot)
    game_roles.setup(bot)
    profile.setup(bot)
    boosts.setup(bot)
    companies.setup(bot)

    @bot.check
    async def global_toggle_check(ctx):
        if not ctx.guild or not ctx.command:
            return True

        safe_ensure_guild_once(ctx.guild)

        # Bot owner bypass:
        # Owner can use every command in any room even if dev mode, system toggles,
        # or channel restrictions would block normal users.
        if is_dev_owner(ctx.author.id):
            return True

        if is_dev_mode_enabled(ctx.guild.id) and not is_dev_owner(ctx.author.id):
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
    async def on_command_error(ctx, error):
        if not ctx.guild:
            return

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.CheckFailure):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=embed(
                "⚠️ الأمر ناقص",
                f"ناقص باراميتر: `{error.param.name}`\nاكتب `!مساعدة` للأوامر.",
                "warn",
                ctx.author
            ))
            return

        if isinstance(error, commands.BadArgument):
            await ctx.reply(embed=embed(
                "⚠️ صيغة غلط",
                "تأكد من المنشن أو الرقم أو طريقة كتابة الأمر.",
                "warn",
                ctx.author
            ))
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(embed=embed(
                "🔒 صلاحية ناقصة",
                "ما عندك صلاحية تستخدم هذا الأمر.",
                "bad",
                ctx.author
            ))
            return

        try:
            log_event(
                ctx.guild.id,
                "command_error",
                ctx.author.id,
                ctx.author.display_name,
                ctx.channel.id,
                ctx.channel.name,
                "Command error",
                f"{type(error).__name__}: {error}"
            )

            await send_log(
                bot,
                ctx.guild,
                "commands",
                "❌ Command Error",
                f"User: {ctx.author.mention} (`{ctx.author.id}`)\nChannel: {ctx.channel.mention}\nCommand: `{ctx.command}`\nError: `{type(error).__name__}: {str(error)[:900]}`",
                "bad",
                ctx.author
            )
        except Exception:
            pass

        await ctx.reply(embed=embed(
            "❌ خطأ في الأمر",
            f"صار خطأ وتم تسجيله في اللوقات.\n`{type(error).__name__}`",
            "bad",
            ctx.author
        ))

    @bot.event
    async def on_command_completion(ctx):
        if ctx.guild and ctx.command:
            log_event(ctx.guild.id, "command_used", ctx.author.id, ctx.author.display_name, ctx.channel.id, ctx.channel.name, ctx.command.name, ctx.message.content[:500])
            await send_log(
                bot,
                ctx.guild,
                "commands",
                "⌨️ Command Used",
                f"User: {ctx.author.mention} (`{ctx.author.id}`)\nChannel: {ctx.channel.mention}\nCommand: `{ctx.command.name}`\nContent: `{ctx.message.content[:800]}`",
                "info",
                ctx.author
            )

    @bot.event
    async def on_message(message):
        if not message.guild or message.author.bot:
            await bot.process_commands(message)
            return

        safe_ensure_guild_once(message.guild)

        # Track Discord server boosts and post rewards before other processing.
        try:
            msg_type = str(getattr(message, "type", "")).lower()
            if "premium" in msg_type or "boost" in msg_type:
                boost_rewards.record_boost_message(message)
        except Exception:
            pass

        try:
            post_rewards.reward_message(message)
        except Exception:
            pass

        try:
            s = get_settings(message.guild.id)

            if s.get("enabled") and is_system_enabled(message.guild.id, "protection"):
                if is_ignored_channel(s, message.channel.id):
                    await bot.process_commands(message)
                    return

                if is_whitelisted_member(s, message.author):
                    await bot.process_commands(message)
                    return

                result = check_message(message, s)

                if result.get("blocked"):
                    if bool(s.get("delete_messages")):
                        try:
                            await message.delete()
                        except Exception:
                            pass

                    kind = result.get("kind") or "protection"
                    reason = result.get("reason") or "Protection violation"
                    matched = result.get("matched") or ""
                    details = result.get("details") or ""

                    if result.get("warning"):
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
                        f"protection_{kind}",
                        message.author.id,
                        message.author.display_name,
                        message.channel.id,
                        message.channel.name,
                        f"Protection blocked: {kind}",
                        message.content[:500],
                        {"matched": matched, "details": details, "warning": bool(result.get("warning"))}
                    )

                    await send_log(
                        bot,
                        message.guild,
                        "protection",
                        f"🛡️ Protection Blocked: {kind}",
                        f"User: {message.author.mention} (`{message.author.id}`)\n"
                        f"Channel: {message.channel.mention}\n"
                        f"Action: {'deleted + warning' if result.get('warning') else 'deleted'}\n"
                        f"Reason: `{reason}`\n"
                        f"Matched: `{matched or '-'}`\n"
                        f"Details: `{details or '-'}`\n"
                        f"Message: `{message.content[:800]}`",
                        "bad" if result.get("warning") else "warn",
                        message.author
                    )

                    try:
                        e = embed(
                            "🛡️ حماية السيرفر",
                            f"{message.author.mention}\nتم حذف الرسالة.\n**السبب:** {reason}",
                            "bad" if result.get("warning") else "warn",
                            message.author
                        )
                        e.add_field(name="الإجراء", value="حذف الرسالة + تحذير" if result.get("warning") else "حذف الرسالة", inline=True)
                        e.add_field(name="النظام", value=f"Protection / {kind}", inline=True)
                        await message.channel.send(embed=e, delete_after=8)
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
    async def on_message_delete(message):
        if not message.guild or message.author.bot:
            return

        attachments = "\n".join(a.url for a in getattr(message, "attachments", [])[:5]) or "None"
        content = message.content or "[No text]"

        log_event(message.guild.id, "message_delete", message.author.id, message.author.display_name, message.channel.id, message.channel.name, "Message deleted", content[:1000])
        await send_log(
            bot,
            message.guild,
            "messages",
            "🗑️ Message Deleted",
            f"User: {message.author.mention} (`{message.author.id}`)\nChannel: {message.channel.mention}\nContent: `{content[:900]}`\nAttachments: {attachments}",
            "warn",
            message.author
        )

    @bot.event
    async def on_message_edit(before, after):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return

        log_event(before.guild.id, "message_edit", before.author.id, before.author.display_name, before.channel.id, before.channel.name, "Message edited", f"Before: {before.content[:500]} | After: {after.content[:500]}")
        await send_log(
            bot,
            before.guild,
            "messages",
            "✏️ Message Edited",
            f"User: {before.author.mention} (`{before.author.id}`)\nChannel: {before.channel.mention}\nBefore: `{before.content[:700]}`\nAfter: `{after.content[:700]}`",
            "info",
            before.author
        )

    @bot.event
    async def on_member_join(member):
        safe_ensure_guild_once(member.guild)
        log_event(member.guild.id, "member_join", member.id, member.display_name, title="Member joined")

        await send_log(
            bot,
            member.guild,
            "join_leave",
            "📥 Member Joined",
            f"User: {member.mention} (`{member.id}`)\nAccount Created: {fmt_dt(member.created_at)}\nBot: `{member.bot}`",
            "ok",
            member
        )

        if member.bot:
            entry = await get_latest_audit(member.guild, discord.AuditLogAction.bot_add, member.id)
            if entry:
                await handle_antiraid_action(bot, member.guild, "bot_add", entry.user, f"Bot `{member}` (`{member.id}`)", entry.reason or "")

    @bot.event
    async def on_member_remove(member):
        leave_type, moderator, reason = await detect_leave_type(member)
        if leave_type in {"kick", "ban"} and moderator:
            await handle_antiraid_action(bot, member.guild, leave_type, moderator, f"Member `{member}` (`{member.id}`)", reason)
        title = "📤 Member Left"
        color = "warn"

        if leave_type == "kick":
            title = "👢 Member Kicked"
            color = "bad"
        elif leave_type == "ban":
            title = "🔨 Member Banned"
            color = "bad"

        mod_text = f"{moderator.mention} (`{moderator.id}`)" if moderator else "None"

        details = (
            f"User: **{member}** (`{member.id}`)\n"
            f"Type: `{leave_type}`\n"
            f"Moderator: {mod_text}\n"
            f"Reason: `{reason}`\n"
            f"Account Created: {fmt_dt(member.created_at)}\n"
            f"Joined Server: {fmt_dt(member.joined_at) if member.joined_at else 'Unknown'}\n"
            f"Roles Before Leaving:\n{role_list(member)}"
        )

        log_event(member.guild.id, f"member_{leave_type}", member.id, member.display_name, title=title, details=details[:1900])
        await send_log(bot, member.guild, "join_leave", title, details, color, member)

    @bot.event
    async def on_member_ban(guild, user):
        moderator, reason = await audit_reason(guild, discord.AuditLogAction.ban, user.id)
        if moderator:
            await handle_antiraid_action(bot, guild, "ban", moderator, f"User `{user}` (`{user.id}`)", reason)
        mod_text = f"{moderator.mention} (`{moderator.id}`)" if moderator else "Unknown"

        log_event(guild.id, "member_ban", user.id, str(user), title="Member banned", details=f"By={mod_text}, Reason={reason}")
        await send_log(
            bot,
            guild,
            "join_leave",
            "🔨 Member Banned",
            f"User: **{user}** (`{user.id}`)\nModerator: {mod_text}\nReason: `{reason}`\nAccount Created: {fmt_dt(user.created_at)}",
            "bad"
        )

    @bot.event
    async def on_member_unban(guild, user):
        moderator, reason = await audit_reason(guild, discord.AuditLogAction.unban, user.id)
        mod_text = f"{moderator.mention} (`{moderator.id}`)" if moderator else "Unknown"

        log_event(guild.id, "member_unban", user.id, str(user), title="Member unbanned", details=f"By={mod_text}, Reason={reason}")
        await send_log(
            bot,
            guild,
            "join_leave",
            "🔓 Member Unbanned",
            f"User: **{user}** (`{user.id}`)\nModerator: {mod_text}\nReason: `{reason}`",
            "ok"
        )

    @bot.event
    async def on_member_update(before, after):
        if before.roles != after.roles:
            before_ids = {r.id for r in before.roles}
            after_ids = {r.id for r in after.roles}

            added = [r.mention for r in after.roles if r.id not in before_ids and r.name != "@everyone"]
            removed = [r.mention for r in before.roles if r.id not in after_ids and r.name != "@everyone"]

            details = f"User: {after.mention} (`{after.id}`)\nAdded: {', '.join(added) if added else 'None'}\nRemoved: {', '.join(removed) if removed else 'None'}"
            action = getattr(discord.AuditLogAction, "member_role_update", None)
            if action:
                entry = await get_latest_audit(after.guild, action, after.id)
                if entry:
                    await handle_antiraid_action(bot, after.guild, "member_role_update", entry.user, f"Member `{after}` (`{after.id}`)", entry.reason or "")
            log_event(after.guild.id, "member_roles_update", after.id, after.display_name, title="Roles changed", details=details)
            await send_log(bot, after.guild, "roles", "🎭 Roles Updated", details, "info", after)

        if before.nick != after.nick:
            details = f"User: {after.mention} (`{after.id}`)\nBefore: `{before.nick}`\nAfter: `{after.nick}`"
            log_event(after.guild.id, "member_nick_update", after.id, after.display_name, title="Nickname changed", details=details)
            await send_log(bot, after.guild, "roles", "🏷️ Nickname Updated", details, "info", after)


    @bot.event
    async def on_guild_role_delete(role):
        entry = await get_latest_audit(role.guild, discord.AuditLogAction.role_delete, role.id)
        if entry:
            await handle_antiraid_action(bot, role.guild, "role_delete", entry.user, f"Role `{role.name}` (`{role.id}`)", entry.reason or "")

    @bot.event
    async def on_guild_role_update(before, after):
        entry = await get_latest_audit(after.guild, discord.AuditLogAction.role_update, after.id)
        added_perms = antiraid.dangerous_perms_added(before.permissions, after.permissions)
        if entry:
            if added_perms:
                await handle_antiraid_action(
                    bot,
                    after.guild,
                    "dangerous_role_update",
                    entry.user,
                    f"Role `{after.name}` (`{after.id}`) added dangerous perms: {', '.join(added_perms)}",
                    entry.reason or ""
                )
            await handle_antiraid_action(bot, after.guild, "role_update", entry.user, f"Role `{after.name}` (`{after.id}`)", entry.reason or "")

    @bot.event
    async def on_guild_channel_create(channel):
        log_event(channel.guild.id, "channel_create", channel.id, channel.name, channel.id, channel.name, "Channel created", str(channel))
        await send_log(bot, channel.guild, "server", "➕ Channel Created", f"Channel: {channel.mention if hasattr(channel, 'mention') else channel.name}\nID: `{channel.id}`\nType: `{channel.type}`", "ok")

        entry = await get_latest_audit(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if entry:
            await handle_antiraid_action(bot, channel.guild, "channel_create", entry.user, f"Channel `{channel.name}` (`{channel.id}`)", entry.reason or "")

    @bot.event
    async def on_guild_channel_delete(channel):
        log_event(channel.guild.id, "channel_delete", channel.id, channel.name, 0, channel.name, "Channel deleted", str(channel))
        await send_log(bot, channel.guild, "server", "➖ Channel Deleted", f"Name: **{channel.name}**\nID: `{channel.id}`\nType: `{channel.type}`", "bad")

        entry = await get_latest_audit(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if entry:
            await handle_antiraid_action(bot, channel.guild, "channel_delete", entry.user, f"Channel `{channel.name}` (`{channel.id}`)", entry.reason or "")

    @bot.event
    async def on_guild_channel_update(before, after):
        entry = await get_latest_audit(after.guild, discord.AuditLogAction.channel_update, after.id)
        if entry:
            await handle_antiraid_action(bot, after.guild, "channel_update", entry.user, f"Channel `{after.name}` (`{after.id}`)", entry.reason or "")

    @bot.event
    async def on_webhooks_update(channel):
        for action_type, audit_action in [
            ("webhook_create", discord.AuditLogAction.webhook_create),
            ("webhook_update", discord.AuditLogAction.webhook_update),
            ("webhook_delete", discord.AuditLogAction.webhook_delete),
        ]:
            entry = await get_latest_audit(channel.guild, audit_action, None)
            if entry:
                await handle_antiraid_action(bot, channel.guild, action_type, entry.user, f"Channel `{channel.name}` (`{channel.id}`)", entry.reason or "")
                break


    @bot.event
    async def on_voice_state_update(member, before, after):
        if before.channel == after.channel:
            return

        if before.channel and after.channel:
            title = "🔀 Voice Moved"
            details = f"User: {member.mention} (`{member.id}`)\nFrom: **{before.channel.name}**\nTo: **{after.channel.name}**"
        elif after.channel:
            title = "🔊 Voice Joined"
            details = f"User: {member.mention} (`{member.id}`)\nChannel: **{after.channel.name}**"
        else:
            title = "🔇 Voice Left"
            details = f"User: {member.mention} (`{member.id}`)\nChannel: **{before.channel.name}**"

        try:
            log_event(member.guild.id, "voice_state", member.id, member.display_name, (after.channel.id if after.channel else before.channel.id), (after.channel.name if after.channel else before.channel.name), title, details)
        except Exception:
            pass
        await send_log(bot, member.guild, "voice", title, details, "info", member)
