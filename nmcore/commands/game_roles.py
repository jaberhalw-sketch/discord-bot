import re
import discord
from nmcore.ui import embed
from nmcore.services.activity import log_event


GAME_ROLES = [
    ("🚗", "GTA", ["gta", "grand theft auto"]),
    ("🎯", "Valorant", ["valorant", "فالورانت"]),
    ("🏗️", "Fortnite", ["fortnite", "فورت نايت", "fort"]),
    ("🧱", "Roblox", ["roblox", "روبلوكس"]),
    ("⛏️", "Minecraft", ["minecraft", "ماينكرافت"]),
    ("🔫", "Counter Strike", ["counter strike", "counter-strike", "cs", "cs2"]),
    ("💀", "Dead by Daylight", ["dead by daylight", "dbd"]),
    ("🛡️", "Overwatch", ["overwatch"]),
    ("🚀", "ARC Raiders", ["arc raiders", "arc-raiders", "arc"]),
    ("⚽", "Rocket League", ["rocket league"]),
    ("🏹", "Apex Legends", ["apex legends", "apex"]),
    ("🪖", "Warzone", ["warzone"]),
    ("🏢", "Rainbow Six Siege", ["rainbow six siege", "rainbow", "r6"]),
    ("⚽", "EA FC", ["ea fc", "fifa"]),
    ("🔨", "Rust", ["rust"]),
    ("⚔️", "League of Legends", ["league of legends", "lol"]),
    ("🏅", "Call of Duty", ["call of duty", "cod"]),
    ("♣️", "Among Us", ["among us"]),
    ("💥", "The Finals", ["the finals"]),
    ("🌌", "Helldivers 2", ["helldivers 2", "helldivers"]),
]


def norm(text):
    text = str(text or "").lower()
    text = re.sub(r"[^\w\sء-ي]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_role(guild, label, aliases):
    """
    Finds existing roles only. Does not create new roles.
    This keeps the same roles already in the server.
    """
    wanted = [norm(label)] + [norm(a) for a in aliases]

    # Exact normalized match first.
    for role in guild.roles:
        rn = norm(role.name)
        if rn in wanted:
            return role

    # Contains match second, useful when role has emojis in the name.
    for role in guild.roles:
        rn = norm(role.name)
        for w in wanted:
            if w and (w in rn or rn in w):
                return role

    return None


def roles_status_lines(guild):
    lines = []
    for emoji, label, aliases in GAME_ROLES:
        role = find_role(guild, label, aliases)
        if role:
            lines.append(f"{emoji} {role.mention}")
        else:
            lines.append(f"{emoji} `{label}` — ❌ role not found")
    return "\n".join(lines)


class GameRolesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        for i, (emoji, label, aliases) in enumerate(GAME_ROLES):
            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
                custom_id=f"nm_game_role:{label.lower().replace(' ', '_')}",
                row=i // 5
            )

            async def callback(interaction, label=label, aliases=aliases):
                await self.handle_role(interaction, label, aliases)

            btn.callback = callback
            self.add_item(btn)

    async def handle_role(self, interaction, label, aliases):
        # Important: defer first so Discord never shows "This interaction failed".
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            role = find_role(interaction.guild, label, aliases)

            if not role:
                await interaction.followup.send(
                    embed=embed(
                        "❌ الرتبة غير موجودة",
                        f"ما لقيت رتبة باسم **{label}**.\nتأكد إن الرتبة موجودة في السيرفر بنفس الاسم أو فيها اسم اللعبة.",
                        "bad",
                        interaction.user
                    ),
                    ephemeral=True
                )
                return

            bot_member = interaction.guild.me
            if role >= bot_member.top_role:
                await interaction.followup.send(
                    embed=embed(
                        "❌ ما أقدر أعطي الرتبة",
                        f"رتبة {role.mention} أعلى من رتبة البوت أو بنفس مستواها.\nارفع رتبة البوت فوق رتب الألعاب.",
                        "bad",
                        interaction.user
                    ),
                    ephemeral=True
                )
                return

            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Game role panel toggle off")
                action = "removed"
                e = embed("✅ تم سحب الرتبة", f"انشالت منك رتبة {role.mention}", "warn", interaction.user)
            else:
                await interaction.user.add_roles(role, reason="Game role panel toggle on")
                action = "added"
                e = embed("✅ تم إعطاء الرتبة", f"أخذت رتبة {role.mention}", "ok", interaction.user)

            try:
                log_event(
                    interaction.guild.id,
                    "game_role_toggle",
                    interaction.user.id,
                    interaction.user.display_name,
                    interaction.channel.id,
                    interaction.channel.name,
                    "Game role toggled",
                    f"{action} role={role.name} ({role.id})"
                )
            except Exception:
                pass

            await interaction.followup.send(embed=e, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                embed=embed(
                    "❌ صلاحيات ناقصة",
                    "البوت ما عنده صلاحية Manage Roles أو رتبة البوت تحت رتبة اللعبة.",
                    "bad",
                    interaction.user
                ),
                ephemeral=True
            )
        except Exception as ex:
            await interaction.followup.send(
                embed=embed(
                    "❌ خطأ في زر الرتبة",
                    f"`{type(ex).__name__}: {str(ex)[:500]}`",
                    "bad",
                    interaction.user
                ),
                ephemeral=True
            )


def roles_embed(member=None):
    e = embed(
        "🎭 Roles",
        "هذا الروم مخصص لاختيار رتب الألعاب.\n\nاضغط على زر اللعبة حتى تأخذ الرتبة، وإذا ضغطت مرة ثانية تنشال منك الرتبة.",
        "purple",
        member
    )
    e.add_field(
        name="🎮 الألعاب المتوفرة",
        value="🚗 GTA\n🎯 Valorant\n🏗️ Fortnite\n🧱 Roblox\n⛏️ Minecraft\n🔫 Counter Strike\n💀 Dead by Daylight\n🛡️ Overwatch\n🚀 ARC Raiders\n⚽ Rocket League\n🏹 Apex Legends\n🪖 Warzone\n🏢 Rainbow Six Siege\n⚽ EA FC\n🔨 Rust\n⚔️ League of Legends\n🏅 Call of Duty\n♣️ Among Us\n💥 The Finals\n🌌 Helldivers 2",
        inline=False
    )
    e.set_footer(text="NM System | Game Roles")
    return e


def panel_embed(member=None):
    e = embed(
        "🎮 اختر رتب الألعاب",
        "اضغط على الزر عشان تأخذ رتبة اللعبة.\nاضغط مرة ثانية عشان تشيل الرتبة من نفسك.",
        "info",
        member
    )
    e.set_footer(text="NM System | Role Panel")
    return e


def setup(bot):
    @bot.command(name="رتب_الألعاب", aliases=["game_roles", "roles_games", "رتب_العاب"])
    async def game_roles(ctx):
        await ctx.reply(embed=roles_embed(ctx.author))
        await ctx.send(embed=panel_embed(ctx.author), view=GameRolesView())

    @bot.command(name="فحص_رتب_الألعاب", aliases=["check_game_roles"])
    async def check_game_roles(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.reply(embed=embed("صلاحية مرفوضة", "هذا الأمر للإدارة فقط.", "bad", ctx.author))
            return

        e = embed("🔎 فحص رتب الألعاب", roles_status_lines(ctx.guild), "info", ctx.author)
        e.add_field(
            name="ملاحظة",
            value="إذا رتبة تطلع not found، أنشئ رتبة في السيرفر بنفس اسم اللعبة أو خلي اسم اللعبة داخل اسم الرتبة.",
            inline=False
        )
        await ctx.reply(embed=e)
