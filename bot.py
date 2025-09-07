import discord
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))  # Optional for faster syncing
MAZOKU_BOT_ID = 1242388858897956906  # Mazoku bot's ID

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# Default cooldowns (seconds)
COOLDOWN_SECONDS = {
    "open-boxes": 60,   # 1 minute
    "summer": 1800,     # 30 minutes
}

# Track cooldowns: (user_id, command) -> end_time
cooldowns = {}


@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID)) if GUILD_ID else tree.sync()
    print(f"✅ Logged in as {client.user} ({client.user.id})")
    print("📜 Slash commands synced!")


@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        if message.interaction:
            cmd = message.interaction.name
            user = message.interaction.user

            if cmd in COOLDOWN_SECONDS:
                cooldown_key = (user.id, cmd)
                print(f"🎯 Detected /{cmd} by {user} ({user.id})")

                now = time.time()
                if cooldown_key in cooldowns and cooldowns[cooldown_key] > now:
                    remaining = int(cooldowns[cooldown_key] - now)
                    await message.channel.send(
                        f"⏳ {user.mention}, you are still on cooldown for `/{cmd}` "
                        f"({remaining}s remaining)."
                    )
                    return

                cd_time = COOLDOWN_SECONDS[cmd]
                cooldowns[cooldown_key] = now + cd_time

                await message.channel.send(
                    f"⚡ {user.mention}, cooldown started for `/{cmd}`! "
                    f"I’ll remind you in {cd_time} seconds."
                )

                await asyncio.sleep(cd_time)
                if cooldown_key in cooldowns and cooldowns[cooldown_key] <= time.time():
                    del cooldowns[cooldown_key]
                    await message.channel.send(
                        f"✅ {user.mention}, cooldown for `/{cmd}` is over!"
                    )


# 🔧 Slash command: /setcooldown
@tree.command(name="setcooldown", description="Set a cooldown time for a command")
@discord.app_commands.describe(command="The command name (e.g., open-boxes, summer)",
                               seconds="Cooldown time in seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return

    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(
        f"✅ Cooldown for `/{command}` updated to {seconds} seconds."
    )


# 🔍 Slash command: /checkcooldowns
@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()

    active = []
    for (uid, cmd), end_time in cooldowns.items():
        if uid == user_id and end_time > now:
            remaining = int(end_time - now)
            active.append(f"`/{cmd}`: {remaining}s remaining")

    if not active:
        await interaction.response.send_message(
            "✅ You have no active cooldowns!", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True
        )


client.run(TOKEN)
