# Nyx - welcome bot with slash commands
# Greets new members, gives them a starter role, and has /commands.

import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load secrets from the .env file
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # your test server's ID (makes commands show up instantly)

# Settings - change these to match your server
WELCOME_CHANNEL = "welcome"
STARTER_ROLE = "Member"
EMBED_COLOR = discord.Color.purple()  # put your custom color back here

intents = discord.Intents.default()
intents.members = True  # needed to see people joining
# Slash commands don't need message_content, so we leave it off (less access = more trust)


class NyxBot(commands.Bot):
     async def setup_hook(self):
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.tickets")
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to your test server")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global slash commands (can take a while to appear)")


bot = NyxBot(command_prefix=commands.when_mentioned, intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild

    # 1. Send a welcome message
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL)
    if channel:
        embed = discord.Embed(
            title="Welcome to the server!",
            description=f"Hey {member.mention}, welcome to **{guild.name}**! Make yourself at home.",
            color=EMBED_COLOR,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"You're member #{guild.member_count}")
        await channel.send(embed=embed)
    else:
        print(f"Couldn't find a channel named '{WELCOME_CHANNEL}'")

    # 2. Give them the starter role
    role = discord.utils.get(guild.roles, name=STARTER_ROLE)
    if role:
        try:
            await member.add_roles(role, reason="Starter role for new member")
        except discord.Forbidden:
            print("Missing permission: move the bot's role above the starter role.")
    else:
        print(f"Couldn't find a role named '{STARTER_ROLE}'")


# ---------- Slash commands ----------

@bot.tree.command(name="ping", description="Check if Nyx is awake")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")


@bot.tree.command(name="userinfo", description="Show info about a member")
@app_commands.describe(member="Who to look up (leave empty for yourself)")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user

    embed = discord.Embed(title=member.display_name, color=EMBED_COLOR)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=str(member), inline=True)
    embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
    embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="Top Roles",value=member.top_role.mention,inline=True)

    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed.add_field(name="Roles", value=", ".join(roles) if roles else "None", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="testwelcome", description="Preview the welcome message (admins only)")
@app_commands.default_permissions(manage_guild=True)  # hides it from regular members
async def testwelcome(interaction: discord.Interaction):
    bot.dispatch("member_join", interaction.user)
    # ephemeral=True means only you can see this reply
    await interaction.response.send_message("Sent a test welcome!", ephemeral=True)


if not TOKEN:
    raise SystemExit("No token found. Check your .env file.")

bot.run(TOKEN)
