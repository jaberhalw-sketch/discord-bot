import re
import discord
from nmcore.ui import embed
from nmcore.services.activity import log_event
from nmcore.services.settings import get_lfg_settings


GAME_CATEGORY_NAME = "🎮 LFG Rooms"


def parse_lfg_args(args):
    text = " ".join(str(a) for a in args).strip()
    if not text:
        return None, None, ""

    parts = text.split()
    count = None
    count_index = None

    for i, p in enumerate(parts):
        cleaned = re.sub(r"[^\d]", "", p)
        if cleaned.isdigit():
            n = int(cleaned)
            if 2 <= n <= 20:
                count = n
                count_index = i
                break

    if not count:
        return None, None, ""

    left = parts[:count_index]
    right = parts[count_index + 1:]

    if count_index == 0:
        game_parts = right[:1] if right else ["Game"]
        note_parts = right[1:]
    else:
        game_parts = left
        note_parts = right

    game = " ".join(game_parts).strip() or "Game"
    note = " ".join(note_parts).strip() or "لا يوجد"
    return game[:60], count, note[:180]


def get_lfg_channel(guild):
    try:
        s = get_lfg_settings(guild.id)
        cid = int(s.get("lfg_channel_id") or 0)
        return guild.get_channel(cid) if cid else None
    except Exception:
        return None


def in_lfg_channel(ctx):
    ch = get_lfg_channel(ctx.guild)
    return bool(ch and int(ctx.channel.id) == int(ch.id))


def member_lines(view):
    if not view.members:
        return "لا يوجد أحد للحين."
    return "\n".join(f"• <@{uid}>" for uid in view.members)


def lfg_status_text(view):
    if view.cancelled:
        return "❌ تم إلغاء التجمع."
    if view.voice_channel_id:
        return "🔒 اكتمل العدد وتم فتح روم فويس خاص."
    return "🔓 التجمع مفتوح."


async def get_or_create_lfg_category(guild):
    s = get_lfg_settings(guild.id)
    category_id = int(s.get("lfg_category_id") or 0)
    if category_id:
        ch = guild.get_channel(category_id)
        if isinstance(ch, discord.CategoryChannel):
            return ch

    for ch in guild.categories:
        if ch.name == GAME_CATEGORY_NAME:
            return ch

    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False)}
    return await guild.create_category(GAME_CATEGORY_NAME, overwrites=overwrites, reason="NM System LFG category")


async def create_private_voice_for_lfg(interaction, view):
    guild = interaction.guild
    category = await get_or_create_lfg_category(guild)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True),
    }

    for uid in view.members:
        member = guild.get_member(int(uid))
        if member:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, stream=True)

    owner = guild.get_member(int(view.owner_id))
    if owner:
        overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, stream=True, manage_channels=True)

    safe_game = re.sub(r"[^A-Za-z0-9ء-ي _-]", "", view.game).strip()[:30] or "game"
    name = f"🎮 {safe_game} {len(view.members)}-{view.target_count}"

    voice = await guild.create_voice_channel(name=name, category=category, overwrites=overwrites, reason=f"LFG completed for {view.game}")
    view.voice_channel_id = int(voice.id)

    for uid in view.members:
        member = guild.get_member(int(uid))
        try:
            if member and member.voice and member.voice.channel:
                await member.move_to(voice, reason="LFG completed")
        except Exception:
            pass

    log_event(guild.id, "lfg_voice_created", view.owner_id, str(view.owner_id), voice.id, voice.name, "LFG voice created", f"Game={view.game}, Count={len(view.members)}/{view.target_count}")
    return voice


class LFGView(discord.ui.View):
    def __init__(self, owner_id, game, target_count, note="لا يوجد"):
        super().__init__(timeout=None)
        self.owner_id = int(owner_id)
        self.game = str(game or "Game")[:60]
        self.target_count = max(2, min(int(target_count or 2), 20))
        self.note = str(note or "لا يوجد")[:180]
        self.members = []
        self.voice_channel_id = 0
        self.cancelled = False

    def build_embed(self, author=None):
        e = embed("🎮 Looking For Game", f"تجمع على **{self.game}**", "ok" if self.voice_channel_id else "info", author)
        e.add_field(name="👤 صاحب التجمع", value=f"<@{self.owner_id}>", inline=True)
        e.add_field(name="👥 العدد", value=f"**{len(self.members)}/{self.target_count}**", inline=True)
        e.add_field(name="📝 ملاحظة", value=self.note or "لا يوجد", inline=False)
        e.add_field(name="👥 اللي بيدخلون", value=member_lines(self), inline=False)
        e.add_field(name="📌 الحالة", value=lfg_status_text(self), inline=False)
        if self.voice_channel_id:
            e.add_field(name="🔊 روم الفويس", value=f"<#{self.voice_channel_id}>", inline=False)
        e.set_footer(text="NM System | Looking For Game")
        return e

    def refresh_buttons(self):
        done = self.cancelled or bool(self.voice_channel_id) or len(self.members) >= self.target_count
        self.join_btn.disabled = done
        self.leave_btn.disabled = self.cancelled or bool(self.voice_channel_id)
        self.cancel_btn.disabled = self.cancelled
        self.join_btn.label = "مكتمل" if done and not self.cancelled else "يدخل"

    @discord.ui.button(label="يدخل", style=discord.ButtonStyle.success, emoji="🎮")
    async def join_btn(self, interaction, button):
        if self.cancelled:
            await interaction.response.send_message(embed=embed("❌ التجمع ملغي", "هذا التجمع تم إلغاؤه.", "bad", interaction.user), ephemeral=True)
            return
        if self.voice_channel_id:
            await interaction.response.send_message(embed=embed("✅ التجمع مكتمل", f"الروم: <#{self.voice_channel_id}>", "ok", interaction.user), ephemeral=True)
            return
        if interaction.user.id in self.members:
            await interaction.response.send_message(embed=embed("موجود", "أنت داخل التجمع بالفعل.", "warn", interaction.user), ephemeral=True)
            return
        if len(self.members) >= self.target_count:
            await interaction.response.send_message(embed=embed("مكتمل", "التجمع اكتمل خلاص.", "warn", interaction.user), ephemeral=True)
            return

        self.members.append(int(interaction.user.id))

        if len(self.members) >= self.target_count:
            await interaction.response.defer()
            voice = await create_private_voice_for_lfg(interaction, self)
            self.refresh_buttons()
            await interaction.edit_original_response(embed=self.build_embed(interaction.user), view=self)
            await interaction.followup.send(embed=embed("✅ اكتمل التجمع", f"تم فتح روم فويس خاص: <#{voice.id}>", "ok", interaction.user))
            return

        self.refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.user), view=self)

    @discord.ui.button(label="يطلع", style=discord.ButtonStyle.secondary, emoji="📜")
    async def leave_btn(self, interaction, button):
        if interaction.user.id not in self.members:
            await interaction.response.send_message(embed=embed("مو داخل", "أنت مو داخل التجمع.", "warn", interaction.user), ephemeral=True)
            return
        self.members.remove(int(interaction.user.id))
        self.refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.user), view=self)

    @discord.ui.button(label="إلغاء التجمع", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_btn(self, interaction, button):
        if interaction.user.id != self.owner_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(embed=embed("🚫 غير مسموح", "الإلغاء لصاحب التجمع أو الإدارة فقط.", "bad", interaction.user), ephemeral=True)
            return
        self.cancelled = True
        self.refresh_buttons()
        if self.voice_channel_id:
            ch = interaction.guild.get_channel(int(self.voice_channel_id))
            try:
                if ch:
                    await ch.delete(reason="LFG cancelled")
            except Exception:
                pass
        await interaction.response.edit_message(embed=self.build_embed(interaction.user), view=self)


def lfg_help_embed(member=None):
    e = embed("🎮 Looking For Game", "نظام التجمعات للعب. تكتب أمر، الناس تضغط يدخل، وإذا اكتمل العدد يفتح البوت روم فويس خاص للمسجلين.", "info", member)
    e.add_field(name="طريقة الاستخدام", value="`!لعب 5 Valorant نبي قيم سريع`\n`!لعب Valorant 5 نبي قيم سريع`\n`!لعب fort 4`", inline=False)
    e.add_field(name="الأزرار", value="🎮 يدخل\n📜 يطلع\n❌ إلغاء التجمع", inline=False)
    return e


def setup(bot):
    @bot.command(name="شرح_لعب", aliases=["شرح_lfg", "lfg_help"])
    async def lfg_help(ctx):
        ch = get_lfg_channel(ctx.guild)
        if not ch:
            await ctx.reply(embed=embed("❌ روم LFG غير محدد", "حدد روم Looking For Game من الداشبورد: LFG Dashboard.", "bad", ctx.author))
            return
        msg = await ch.send(embed=lfg_help_embed(ctx.author))
        if int(ctx.channel.id) != int(ch.id):
            await ctx.reply(embed=embed("✅ تم إرسال شرح اللعب", f"تم إرسال الشرح في {ch.mention}\n[اضغط هنا]({msg.jump_url})", "ok", ctx.author))

    @bot.command(name="لعب", aliases=["lfg", "قيم"])
    async def lfg(ctx, *args):
        ch = get_lfg_channel(ctx.guild)
        if ch and not in_lfg_channel(ctx):
            await ctx.reply(embed=embed("🎮 استخدم روم Looking For Game", f"أوامر التجمعات تشتغل في {ch.mention} فقط.", "warn", ctx.author))
            return

        game, count, note = parse_lfg_args(args)
        if not game or not count:
            await ctx.reply(embed=lfg_help_embed(ctx.author))
            return

        view = LFGView(ctx.author.id, game, count, note)
        view.members.append(int(ctx.author.id))
        await ctx.reply(embed=view.build_embed(ctx.author), view=view)
        log_event(ctx.guild.id, "lfg_created", ctx.author.id, ctx.author.display_name, ctx.channel.id, ctx.channel.name, "LFG created", f"Game={game}, Count={count}, Note={note}")
