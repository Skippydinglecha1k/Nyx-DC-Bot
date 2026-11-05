# Moderation: /kick, /timeout, /clear, plus a mod log channel.

from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

MOD_LOG_CHANNEL = "mod-log"  # actions get recorded here (make it private!)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- helpers ----------

    async def log_action(self, guild: discord.Guild, title: str, target, moderator, reason: str):
        channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL)
        if channel is None:
            return
        embed = discord.Embed(title=title, color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Member", value=f"{target} ({target.mention})", inline=False)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        await channel.send(embed=embed)

    def check_hierarchy(self, interaction: discord.Interaction, member: discord.Member):
        # Returns an error message if the action isn't allowed, otherwise None
        guild = interaction.guild
        if member == interaction.user:
            return "You can't do that to yourself."
        if member == guild.owner:
            return "You can't do that to the server owner."
        if interaction.user != guild.owner and member.top_role >= interaction.user.top_role:
            return "That member's top role is equal to or higher than yours."
        if member.top_role >= guild.me.top_role:
            return "My role isn't high enough. Move it up in Server Settings."
        return None

    # ---------- commands ----------

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Who to kick", reason="Why (shows in the mod log)")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason given"):
        problem = self.check_hierarchy(interaction, member)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        await member.kick(reason=reason)
        await interaction.response.send_message(f"Kicked **{member}**.", ephemeral=True)
        await self.log_action(interaction.guild, "Member kicked", member, interaction.user, reason)

    @app_commands.command(name="timeout", description="Temporarily mute a member")
    @app_commands.describe(member="Who to time out", minutes="How long (max 40320 = 28 days)", reason="Why")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "No reason given",
    ):
        problem = self.check_hierarchy(interaction, member)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return

        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"Timed out **{member}** for {minutes} min.", ephemeral=True)
        await self.log_action(interaction.guild, f"Member timed out ({minutes} min)", member, interaction.user, reason)

    @app_commands.command(name="clear", description="Delete recent messages in this channel")
    @app_commands.describe(amount="How many messages to delete (1-100)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def clear(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        # Deleting can take a moment, so tell Discord we're working on it
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)
        await self.log_action(
            interaction.guild, f"Cleared {len(deleted)} messages in #{interaction.channel.name}",
            interaction.user, interaction.user, "Bulk delete",
        )

    # ---------- error handling ----------

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions).replace("_", " ")
            message = f"I'm missing these permissions: {missing}"
        else:
            message = "Something went wrong. Check the terminal for details."
            print(f"Error in /{interaction.command.name if interaction.command else '?'}: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
