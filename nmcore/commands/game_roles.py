import re
import discord
from nmcore.ui import embed
from nmcore.services.activity import log_event
from nmcore.services import game_roles as grsvc


def norm(text):
    text = str(text or "").lower()
    text = re.sub(r"[^\w\sء-ي]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_role(guild, row):
    role_id = int(row.get("role_id") or 0)
    if role_id:
        role = guild.get_role(role_id)
        if role:
            return role

    wanted = [norm(row.get("label"))] + [norm(x) for x in str(row.get("aliases") or "").split(",") if x.strip()]
    for role in guild.roles:
        rn = norm(role.name)
        if rn in wanted:
            return role

    for role in guild.roles:
        rn = norm(role.name)
        for w in wanted:
            if w and (w in rn or rn in w):
                return role
    return None


class GameRolesView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        rows = grsvc.rows(guild_id, enabled_only=True)[:25]
        for i, row in enumerate(rows):
            label = str(row.get("label") or row.get("game_key"))[:80]
            emoji = str(row.get("emoji") or "")[:16] or None
            btn = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=f"nm_game_role:{row['game_key']}", row=i // 5)

            async def callback(interaction, row=row):
                await self.handle_role(interaction, row)

            btn.callback = callback
            self.add_item(btn)

    async def handle_role(self, interaction, row):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            role = find_role(interaction.guild, row)
            if not role:
                await interaction.followup.send(embed=embed("❌ الرتبة غير موجودة", f"ما لقيت رتبة للعبة **{row.get('label')}**.\nحدد Role ID من الداشبورد.", "bad", interaction.user), ephemeral=True)
                return

            bot_member = interaction.guild.me
            if role >= bot_member.top_role:
                await interaction.followup.send(embed=embed("❌ ما أقدر أعطي الرتبة", f"رتبة {role.mention} أعلى من رتبة البوت أو بنفس مستواها.", "bad", interaction.user), ephemeral=True)
                return

            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Game role panel toggle off")
                action = "removed"
                e = embed("✅ تم سحب الرتبة", f"انشالت منك رتبة {role.mention}", "warn", interaction.user)
            else:
                await interaction.user.add_roles(role, reason="Game role panel toggle on")
                action = "added"
                e = embed("✅ تم إعطاء الرتبة", f"أخذت رتبة {role.mention}", "ok", interaction.user)

            log_event(interaction.guild.id, "game_role_toggle", interaction.user.id, interaction.user.display_name, interaction.channel.id, interaction.channel.name, "Game role toggled", f"{action} role={role.name} ({role.id})")
            await interaction.followup.send(embed=e, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(embed=embed("❌ صلاحيات ناقصة", "البوت ما عنده Manage Roles أو رتبته تحت رتبة اللعبة.", "bad", interaction.user), ephemeral=True)
        except Exception as ex:
            await interaction.followup.send(embed=embed("❌ خطأ في زر الرتبة", f"`{type(ex).__name__}: {str(ex)[:500]}`", "bad", interaction.user), ephemeral=True)


def roles_embed(guild, member=None):
    rows = grsvc.rows(guild.id, enabled_only=True)
    lines = []
    for r in rows:
        role = find_role(guild, r)
        label = str(r.get("label") or r.get("game_key"))
        emoji = str(r.get("emoji") or "🎮")
        lines.append(f"{emoji} {role.mention if role else '`' + label + '` — ❌'}")
    e = embed("🎭 Roles", "هذا الروم مخصص لاختيار رتب الألعاب.\nاضغط على الزر حتى تأخذ الرتبة، واضغط مرة ثانية حتى تنشال.", "purple", member)
    e.add_field(name="🎮 الألعاب المتوفرة", value="\n".join(lines)[:3900] or "لا يوجد ألعاب مفعلة.", inline=False)
    e.set_footer(text="NM System | Game Roles")
    return e


def panel_embed(member=None):
    e = embed("🎮 اختر رتب الألعاب", "اضغط على الزر عشان تأخذ رتبة اللعبة.\nاضغط مرة ثانية عشان تشيلها من نفسك.", "info", member)
    e.set_footer(text="NM System | Role Panel")
    return e


def setup(bot):
    @bot.command(name="رتب_الألعاب", aliases=["game_roles", "roles_games", "رتب_العاب"])
    async def game_roles(ctx):
        await ctx.reply(embed=roles_embed(ctx.guild, ctx.author))
        await ctx.send(embed=panel_embed(ctx.author), view=GameRolesView(ctx.guild.id))

    @bot.command(name="فحص_رتب_الألعاب", aliases=["check_game_roles"])
    async def check_game_roles(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return
        rows = grsvc.rows(ctx.guild.id)
        lines = []
        for r in rows:
            role = find_role(ctx.guild, r)
            lines.append(f"{r.get('emoji') or '🎮'} **{r.get('label')}** — {role.mention if role else '❌ not found'}")
        await ctx.reply(embed=embed("🔎 فحص رتب الألعاب", "\n".join(lines)[:3900], "info", ctx.author))
