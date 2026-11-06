# Nyx

A multi-purpose Discord bot built with Python and discord.py.

## Features

- **Welcome messages** – greets new members with a custom embed
- **Auto-roles** – gives new members a starter role automatically
- **Button roles** – members click buttons to add or remove roles, and the buttons keep working after restarts
- **Moderation** – `/kick`, `/timeout`, and `/clear`, with role-hierarchy safety checks
- **Mod log** – every moderation action is recorded in a private channel
- **Tickets** – members open private support channels with a button; staff close them, and everything is logged
- **Leveling** – members earn XP for chatting (with an anti-spam cooldown), get level-up messages, and can check `/rank` and `/leaderboard`
- **Slash commands** – modern `/` commands, with admin-only commands hidden from regular members

## Commands

| Command | What it does | Who can use it |
|---|---|---|
| `/ping` | Checks if the bot is online | Everyone |
| `/userinfo` | Shows a member's roles, join date, and account age | Everyone |
| `/rolemenu` | Posts the role picker buttons | Manage Roles |
| `/testwelcome` | Previews the welcome message | Manage Server |
| `/kick` | Kicks a member | Kick Members |
| `/timeout` | Temporarily mutes a member | Timeout Members |
| `/clear` | Deletes recent messages | Manage Messages |
| `/ticketpanel` | Posts the "Open ticket" button | Administrator |
| `/rank` | Shows a member's level, XP, and server rank | Everyone |
| `/leaderboard` | Shows the top 10 members by XP | Everyone |

## Setup

1. Install Python 3.10 or newer.
2. Install the requirements:
   ```
   python -m pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your bot token and server ID.
4. In your server, create a `#welcome` channel, a `#mod-log` channel, a `Member` role, a `Staff` role (for tickets), and the roles listed in `cogs/roles.py`. Nyx needs the **Manage Channels** permission to create tickets. Keep the bot's role above all of them.
5. Run the bot:
   ```
   python bot.py
   ```

## Project structure

```
bot.py              main bot, welcome messages, general commands
cogs/roles.py       button roles
cogs/moderation.py  moderation commands and mod log
cogs/tickets.py     ticket panel, private ticket channels, close button
cogs/leveling.py    XP, levels, /rank and /leaderboard (saved in nyx.db)
```

## How it's built

Nyx is written in Python with [discord.py](https://discordpy.readthedocs.io/). Each feature lives in its own cog, so features can be added, removed, or customized for a server without touching the rest of the bot.

Some technical choices:

- **Buttons that survive restarts.** Every button has a fixed `custom_id`, and its view is registered again with `bot.add_view()` on startup, so old role menus, ticket panels, and close buttons keep working.
- **No database needed for tickets.** Each ticket channel's topic stores its owner's ID, so Nyx can still tell whose ticket it is after a restart.
- **Leveling with SQLite.** XP is saved per server in a local SQLite file using Python's built-in `sqlite3`, so one bot can run in several servers without mixing their data. Levels are calculated from total XP instead of being stored.
- **Minimal permissions.** Nyx doesn't use the privileged message content intent, because leveling only needs to know *that* someone sent a message, not what it says.

I develop with AI pair-programming tools. I design, test, and maintain every feature myself, and I can explain how each part works.
