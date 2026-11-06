# Leveling: members earn XP for chatting and level up over time.
#
# How it works:
#   1. Every message a member sends can earn a little random XP...
#   2. ...but only once per cooldown window, so spamming doesn't count.
#   3. XP is saved in a local SQLite database file (nyx.db), so it survives restarts.
#   4. When someone crosses into a new level, Nyx posts a level-up message.
#   5. /rank shows one member's level, /leaderboard shows the top 10.
#
# Note: we DON'T need the "message content" intent. Nyx only needs to know
# THAT someone talked, not WHAT they said.

import random
import sqlite3
import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

# ---------- Settings - change these to match your server ----------
XP_MIN = 15                 # smallest XP a message can give
XP_MAX = 25                 # biggest XP a message can give
COOLDOWN_SECONDS = 60       # a member can only earn XP once per this many seconds
LEVELUP_CHANNEL = None      # e.g. "level-ups" - or None to announce in the same channel
EMBED_COLOR = discord.Color.purple()

# The database file sits next to bot.py. It's in .gitignore so it never gets uploaded.
DB_PATH = Path(__file__).resolve().parent.parent / "nyx.db"


# ---------- level math ----------

def xp_for_next_level(level: int) -> int:
    """How much XP it takes to go from `level` to `level + 1`.
    Each level needs a bit more than the last: 100, 155, 220, 295..."""
    return 5 * level ** 2 + 50 * level + 100


def level_from_xp(total_xp: int):
    """Turn a total XP number into (level, xp into this level, xp needed for next level)."""
    level = 0
    while total_xp >= xp_for_next_level(level):
        total_xp -= xp_for_next_level(level)
        level += 1
    return level, total_xp, xp_for_next_level(level)


# ---------- the cog ----------

class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = None
        # Remembers when each member last earned XP: {(guild_id, user_id): timestamp}
        # This lives in memory only - it resets on restart, which is fine.
        self.cooldowns = {}

    async def cog_load(self):
        # Open (or create) the database and make sure our table exists.
        # sqlite3 comes built into Python, so there's nothing to install.
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS xp (
                guild_id INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                xp       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )
        self.db.commit()

    async def cog_unload(self):
        # Close the database cleanly when the cog is unloaded / the bot stops
        if self.db:
            self.db.close()

    # ---------- database helpers ----------

    def get_xp(self, guild_id: int, user_id: int) -> int:
        row = self.db.execute(
            "SELECT xp FROM xp WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        ).fetchone()
        return row[0] if row else 0

    def add_xp(self, guild_id: int, user_id: int, amount: int) -> int:
        """Add XP and return the member's new total.
        The ? marks are placeholders - never paste values straight into SQL text."""
        self.db.execute(
            """
            INSERT INTO xp (guild_id, user_id, xp) VALUES (?, ?, ?)
            ON CONFLICT (guild_id, user_id) DO UPDATE SET xp = xp + excluded.xp
            """,
            (guild_id, user_id, amount),
        )
        self.db.commit()
        return self.get_xp(guild_id, user_id)

    # ---------- earning XP ----------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots (including Nyx) and DMs
        if message.author.bot or message.guild is None:
            return

        # Cooldown check: has this member earned XP too recently?
        key = (message.guild.id, message.author.id)
        now = time.monotonic()
        if now - self.cooldowns.get(key, 0) < COOLDOWN_SECONDS:
            return
        self.cooldowns[key] = now

        # Give XP and see if they crossed into a new level
        old_level = level_from_xp(self.get_xp(*key))[0]
        new_total = self.add_xp(*key, random.randint(XP_MIN, XP_MAX))
        new_level = level_from_xp(new_total)[0]

        if new_level > old_level:
            await self.announce_level_up(message, new_level)

    async def announce_level_up(self, message: discord.Message, level: int):
        channel = message.channel
        if LEVELUP_CHANNEL:
            channel = discord.utils.get(message.guild.text_channels, name=LEVELUP_CHANNEL) or channel
        try:
            await channel.send(f"🎉 {message.author.mention} just reached **level {level}**!")
        except discord.Forbidden:
            pass  # Nyx can't talk in that channel - not worth crashing over

    # ---------- commands ----------

    @app_commands.command(name="rank", description="Show a member's level and XP")
    @app_commands.describe(member="Who to check (leave empty for yourself)")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        total = self.get_xp(interaction.guild.id, member.id)
        level, current, needed = level_from_xp(total)

        # Position = how many people in this server have MORE xp, plus one
        position = self.db.execute(
            "SELECT COUNT(*) FROM xp WHERE guild_id = ? AND xp > ?", (interaction.guild.id, total)
        ).fetchone()[0] + 1

        # A simple text progress bar, 10 blocks wide
        filled = int(current / needed * 10)
        bar = "▰" * filled + "▱" * (10 - filled)

        embed = discord.Embed(title=f"{member.display_name}'s rank", color=EMBED_COLOR)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="Rank", value=f"#{position}" if total else "Unranked", inline=True)
        embed.add_field(name="Total XP", value=str(total), inline=True)
        embed.add_field(name="Progress", value=f"{bar}  {current}/{needed} XP", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Show the top 10 members by XP")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = self.db.execute(
            "SELECT user_id, xp FROM xp WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
            (interaction.guild.id,),
        ).fetchall()

        if not rows:
            await interaction.response.send_message("Nobody has earned XP yet. Start chatting!",
                                                    ephemeral=True)
            return

        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = []
        for place, (user_id, xp) in enumerate(rows, start=1):
            level = level_from_xp(xp)[0]
            badge = medals.get(place, f"`#{place}`")
            # <@id> becomes a mention, but it won't ping anyone inside an embed
            lines.append(f"{badge} <@{user_id}> - Level {level} ({xp} XP)")

        embed = discord.Embed(title=f"🏆 {interaction.guild.name} leaderboard",
                              description="\n".join(lines), color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
