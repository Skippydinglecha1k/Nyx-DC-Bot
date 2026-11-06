# Ticket system: members click a button to open a private support channel.
#
# How it works:
#   1. An admin runs /ticketpanel. Nyx posts an embed with an "Open ticket" button.
#   2. A member clicks it. Nyx makes a private channel only they + staff can see.
#   3. Inside the ticket there's a "Close ticket" button that deletes the channel.
#   4. Opening and closing both get logged in #mod-log.
#
# The buttons keep working after a restart because each one has a fixed
# custom_id, and we re-register the views with bot.add_view() on startup
# (same trick as cogs/roles.py).

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

# ---------- Settings - change these to match your server ----------
STAFF_ROLE = "Staff"            # role that can see and close every ticket
TICKET_CATEGORY = "Tickets"     # category the ticket channels go in (created if missing)
MOD_LOG_CHANNEL = "mod-log"     # where open/close events are logged
EMBED_COLOR = discord.Color.purple()
CLOSE_DELAY_SECONDS = 5         # small pause so people can see the "closing" message

# We save the ticket owner's ID in the channel topic, like a little sticky note.
# That way Nyx can still tell whose ticket it is after a restart, with no database.
OWNER_TAG = "ticket-owner:"


# ---------- helpers ----------

def get_ticket_owner_id(channel: discord.abc.GuildChannel):
    """Read the owner's ID back out of the channel topic. Returns None if it isn't a ticket."""
    topic = getattr(channel, "topic", None) or ""
    if topic.startswith(OWNER_TAG):
        try:
            return int(topic[len(OWNER_TAG):].split()[0])
        except (ValueError, IndexError):
            return None
    return None


async def log_ticket(guild: discord.Guild, title: str, color: discord.Color, **fields):
    """Post a small embed in #mod-log. Silently skips if the channel doesn't exist."""
    channel = discord.utils.get(guild.text_channels, name=MOD_LOG_CHANNEL)
    if channel is None:
        return
    embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=True)
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        print(f"Can't post in #{MOD_LOG_CHANNEL} - check Nyx's permissions there.")


# ---------- buttons ----------

class OpenTicketView(discord.ui.View):
    """The panel button that everyone sees."""

    def __init__(self):
        super().__init__(timeout=None)  # never expires

    # custom_id must be unique and never change, or old panels stop working
    @discord.ui.button(label="Open ticket", emoji="🎫", style=discord.ButtonStyle.primary,
                       custom_id="nyx:ticket:open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        # 1. Don't let one member open a pile of tickets
        for channel in guild.text_channels:
            if get_ticket_owner_id(channel) == member.id:
                await interaction.response.send_message(
                    f"You already have a ticket open: {channel.mention}", ephemeral=True
                )
                return

        # 2. Make sure the staff role exists
        staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE)
        if staff_role is None:
            await interaction.response.send_message(
                f"There's no **{STAFF_ROLE}** role yet. Ask an admin to create it.", ephemeral=True
            )
            return

        # Creating channels can take a second, so tell Discord we're on it
        await interaction.response.defer(ephemeral=True)

        # 3. Find (or create) the Tickets category
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        try:
            if category is None:
                category = await guild.create_category(TICKET_CATEGORY, reason="Ticket system setup")

            # 4. Permission overwrites = who can see the channel.
            #    Everyone: hidden. The member, staff, and Nyx: can see and talk.
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                    attach_files=True, read_message_history=True),
                staff_role: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                        read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                      manage_channels=True),
            }

            channel = await guild.create_text_channel(
                name=f"ticket-{member.name}",
                category=category,
                overwrites=overwrites,
                topic=f"{OWNER_TAG}{member.id}",  # the sticky note - see get_ticket_owner_id()
                reason=f"Ticket opened by {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "I need the **Manage Channels** permission to open tickets.", ephemeral=True
            )
            return

        # 5. Greet them inside the ticket, with the Close button attached
        embed = discord.Embed(
            title="Ticket opened",
            description=(
                f"Hey {member.mention}, thanks for reaching out! "
                f"Tell us what you need and a {staff_role.mention} member will help soon.\n\n"
                "Click **Close ticket** when you're done."
            ),
            color=EMBED_COLOR,
        )
        await channel.send(content=f"{member.mention} {staff_role.mention}", embed=embed,
                           view=CloseTicketView())

        await interaction.followup.send(f"Your ticket is ready: {channel.mention}", ephemeral=True)
        await log_ticket(guild, "Ticket opened", discord.Color.green(),
                         Member=member.mention, Channel=channel.mention)


class CloseTicketView(discord.ui.View):
    """The button inside each ticket channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close ticket", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="nyx:ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        owner_id = get_ticket_owner_id(channel)

        # Safety check: only works inside real ticket channels
        if owner_id is None:
            await interaction.response.send_message("This isn't a ticket channel.", ephemeral=True)
            return

        # Only the ticket owner or staff can close it
        staff_role = discord.utils.get(interaction.guild.roles, name=STAFF_ROLE)
        is_staff = staff_role is not None and staff_role in interaction.user.roles
        if interaction.user.id != owner_id and not is_staff:
            await interaction.response.send_message("Only the ticket owner or staff can close this.",
                                                    ephemeral=True)
            return

        await interaction.response.send_message(
            f"🔒 Closing this ticket in {CLOSE_DELAY_SECONDS} seconds..."
        )

        # Log BEFORE deleting, while we still know the channel's name
        await log_ticket(interaction.guild, "Ticket closed", discord.Color.red(),
                         Owner=f"<@{owner_id}>", **{"Closed by": interaction.user.mention},
                         Channel=f"#{channel.name}")

        await asyncio.sleep(CLOSE_DELAY_SECONDS)
        try:
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.Forbidden:
            await channel.send("I couldn't delete this channel. I need **Manage Channels**.")
        except discord.NotFound:
            pass  # someone already deleted it by hand - nothing to do


# ---------- the cog ----------

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Re-attach both button types on startup so old panels and tickets keep working
        self.bot.add_view(OpenTicketView())
        self.bot.add_view(CloseTicketView())

    @app_commands.command(name="ticketpanel", description="Post the 'Open ticket' panel here (admins only)")
    @app_commands.default_permissions(administrator=True)  # hides it from regular members
    async def ticketpanel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Need help?",
            description="Click the button below to open a private ticket with the staff team.",
            color=EMBED_COLOR,
        )
        await interaction.channel.send(embed=embed, view=OpenTicketView())
        await interaction.response.send_message("Ticket panel posted!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
