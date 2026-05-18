import discord
from nmcore.services.settings import ensure_guild, command_system, is_system_enabled
from nmcore.services.levels import message_xp
from nmcore.services.protection import get_settings, contains_bad, has_link
from nmcore.services.activity import log_event
from nmcore.config import LEVEL_COOLDOWN_SECONDS
from nmcore.commands import economy, casino, levels, real_estate, moderation, admin

def setup_bot(bot):
    economy.setup(bot)
    casino.setup(bot)
    levels.setup(bot)
    real_estate.setup(bot)
    moderation.setup(bot)
    admin.setup(bot)

    @bot.check
    async def global_toggle_check(ctx):
        if not ctx.guild or not ctx.command:
            return True
        ensure_guild(ctx.guild.id, ctx.guild.name)
        sys = command_system(ctx.command.name)
        if not is_system_enabled(ctx.guild.id, sys):
            await ctx.reply(f"🔒 نظام `{sys}` مقفل من الداشبورد.")
            return False
        return True

    @bot.event
    async def on_message(message):
        if not message.guild or message.author.bot:
            await bot.process_commands(message)
            return
        ensure_guild(message.guild.id, message.guild.name)
        try:
            s=get_settings(message.guild.id)
            if s.get("enabled") and is_system_enabled(message.guild.id, "protection"):
                words=[w.strip() for w in str(s.get("bad_words") or "").split(",") if w.strip()]
                bad = bool(s.get("bad_words_enabled")) and contains_bad(message.content, words)
                link = bool(s.get("links_enabled")) and has_link(message.content)
                if bad or link:
                    if bool(s.get("delete_messages")):
                        try: await message.delete()
                        except Exception: pass
                    log_event(message.guild.id,"protection",message.author.id,message.author.display_name,message.channel.id,message.channel.name,"Message blocked",message.content[:500])
                    return
        except Exception:
            pass
        try:
            if is_system_enabled(message.guild.id,"levels"):
                res=message_xp(message.guild.id,message.author.id,LEVEL_COOLDOWN_SECONDS)
                if res and res[2]:
                    await message.channel.send(f"🎉 {message.author.mention} وصل لفل **{res[1]}**!")
        except Exception:
            pass
        await bot.process_commands(message)

    @bot.event
    async def on_member_join(member):
        ensure_guild(member.guild.id, member.guild.name)
        log_event(member.guild.id,"member_join",member.id,member.display_name,title="Member joined")

    @bot.event
    async def on_member_remove(member):
        log_event(member.guild.id,"member_leave",member.id,member.display_name,title="Member left")
