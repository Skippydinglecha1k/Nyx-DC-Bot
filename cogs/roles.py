# Button roles: members click buttons to add or remove roles.

import discord
from discord import app_commands
from discord.ext import commands

# Edit this list to match your server: (role name, emoji)
# Each role must already exist in your server, and sit BELOW Nyx's role.
ROLE_OPTIONS = [
    ("Rocket League", "🚗"),
    ("Valorant", "🎯"),
    ("Minecraft", "⛏️"),
]


class RoleButton(discord.ui.Button):
    def __init__(self, role_name: str, emoji: str):
        super().__init__(
            label=role_name,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            # custom_id lets the button keep working after the bot restarts
            custom_id=f"rolebtn:{role_name}",
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        # Runs when someone clicks this button
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if role is None:
            await interaction.response.send_message(
                f"The role **{self.role_name}** doesn't exist yet. Ask an admin to create it.",
                ephemeral=True,
            )
            return

        member = interaction.user
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Button role removed")
                message = f"Removed {role.mention}."
            else:
                await member.add_roles(role, reason="Button role added")
                message = f"Gave you {role.mention}!"
        except discord.Forbidden:
            message = "I can't manage that role. Move my role above it in Server Settings."

        await interaction.response.send_message(message, ephemeral=True)


class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # buttons never expire
        for name, emoji in ROLE_OPTIONS:
            self.add_item(RoleButton(name, emoji))


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Re-attach the buttons on startup so old role menus keep working
        self.bot.add_view(RoleView())

    @app_commands.command(name="rolemenu", description="Post the role picker in this channel (admins only)")
    @app_commands.default_permissions(manage_roles=True)
    async def rolemenu(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pick your roles",
            description="Click a button to add a role. Click it again to remove it.",
            color=discord.Color.purple(),
        )
        await interaction.channel.send(embed=embed, view=RoleView())
        await interaction.response.send_message("Role menu posted!", ephemeral=True)


async def setup(bot: commands.Bot):
    # discord.py calls this when the bot loads this file
    await bot.add_cog(Roles(bot))
