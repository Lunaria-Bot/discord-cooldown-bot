# bot.py
import discord
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))   # optional: force-sync to one guild
MAZOKU_BOT_ID = 1242388858897956906                # replace if different

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# Aliases & cooldowns
# ----------------------------
COMMAND_ALIASES = {
    "Refreshing Box": "open-boxes",
    "Summer": "summer",
}

COOLDOWN_SECONDS = {
    "open-boxes": 60,
    "summer": 1800,
}

# (user_id, cmd_name) -> end_timestamp
cooldowns = {}

# ----------------------------
# Utility helpers
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

def get_display_name(cmd_name: str) -> str:
    for pretty, actual in COMMAND_ALIASES.items():
        if actual == cmd_name:
            return pretty
    return cmd_name


async def safe_dm(user: discord.User, fallback_channel: discord.TextChannel, text: str):
    """Try to DM, fall back to channel if DMs blocked"""
    try:
        await user.send(text)
    except discord.Forbidden:
        try:
            await fallback_channel.send(f"{user.mention} {text}")
        except Exception:
            print(f"⚠️ Could not DM or send in channel for {user}", flush=True)


# ----------------------------
# Events
# ----------------------------
@client.event
async def on_ready():
    try:
        if GUILD_ID:
            await tree.sync(guild=discord.Object(id=GUILD_ID))
            print(f"📜 Slash commands synced to guild {GUILD_ID}", flush=True)
        else:
            await tree.sync()
            print("📜 Slash commands synced globally (may take up to 1 hour).", flush=True)
    except Exception as e:
        print(f"❌ Error syncing commands: {e}", flush=True)

    print(f"✅ Logged in as {client.user} ({client.user.id})", flush=True)


@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    # DEBUG log
    print(
        f"[DEBUG] From {message.author} ({message.author.id}) "
        f"content={repr(message.content)} embeds={len(message.embeds)} "
        f"interaction={getattr(message,'interaction',None)} "
        f"interaction_metadata={getattr(message,'interaction_metadata',None)}",
        flush=True,
    )

    # Only care about Mazoku bot messages
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)

        if cmd_name in COOLDOWN_SECONDS and user:
            now = time.time()
            key = (user.id, cmd_name)
            end = cooldowns.get(key, 0)

            if end > now:
                remaining = int(end - now)
                await safe_dm(
                    user,
                    message.channel,
                    f"⏳ You're still on cooldown for `{get_display_name(cmd_name)}` ({remaining}s left)."
                )
                return

            # Start cooldown
            cd = COOLDOWN_SECONDS[cmd_name]
            cooldowns[key] = now + cd
            await safe_dm(
                user,
                message.channel,
                f"⚡ Cooldown started for `{get_display_name(cmd_name)}` — I'll remind you in {cd} seconds."
            )

            # Sleep then notify
            await asyncio.sleep(cd)
            if cooldowns.get(key, 0) <= time.time():
                cooldowns.pop(key, None)
                await safe_dm(
                    user,
                    message.channel,
                    f"✅ Your cooldown for `{get_display_name(cmd_name)}` is over — you can use it again."
                )


# ----------------------------
# Slash commands
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds). Admins only recommended.")
@discord.app_commands.describe(command="Command name (e.g. open-boxes, summer)", seconds="Seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return

    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(
        f"✅ Cooldown for `{command}` updated to {seconds} seconds.",
        ephemeral=True
    )


@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    active = []
    for (uid, cmd), end_time in list(cooldowns.items()):
        if uid == user_id and end_time > now:
            active.append(f"{get_display_name(cmd)}: {int(end_time - now)}s")

    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message(
            "⏳ Your active cooldowns:\n" + "\n".join(active),
            ephemeral=True
        )


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
