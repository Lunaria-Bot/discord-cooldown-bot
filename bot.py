# bot.py
import discord
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))   # set this to your server ID for instant sync
MAZOKU_BOT_ID = 1242388858897956906                # replace if different

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# per-command default cooldowns (seconds)
COOLDOWN_SECONDS = {
    "open-boxes": 60,
    "summer": 1800,
}

# (user_id, command) -> end_timestamp
cooldowns = {}

# ----------------------------
# Utility helpers
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    # compatibility: prefer message.interaction, fall back to interaction_metadata
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

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

    # DEBUG: always print what the bot sees (helps in Railway logs)
    print(f"[DEBUG] From {message.author} ({message.author.id}) content={repr(message.content)} embeds={len(message.embeds)} interaction={getattr(message,'interaction',None)} interaction_metadata={getattr(message,'interaction_metadata',None)}", flush=True)

    # only care about Mazoku bot messages for cooldown tracking
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            # nothing to do — sometimes older messages have no interaction metadata
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)

        # only handle known commands
        if cmd_name in COOLDOWN_SECONDS and user:
            now = time.time()
            key = (user.id, cmd_name)
            end = cooldowns.get(key, 0)

            if end > now:
                remaining = int(end - now)
                try:
                    await message.channel.send(f"⏳ {user.mention}, you're still on cooldown for `/{cmd_name}` ({remaining}s left).")
                except Exception:
                    pass
                return

            # start cooldown
            cd = COOLDOWN_SECONDS[cmd_name]
            cooldowns[key] = now + cd
            try:
                await message.channel.send(f"⚡ {user.mention}, cooldown started for `/{cmd_name}` — I'll remind you in {cd} seconds.")
            except Exception:
                pass

            # Sleep then clear and notify (attempt DM first)
            await asyncio.sleep(cd)
            if cooldowns.get(key, 0) <= time.time():
                cooldowns.pop(key, None)
                try:
                    await user.send(f"✅ Your cooldown for `/{cmd_name}` is over — you can use it again.")
                except discord.Forbidden:
                    # fallback to channel if DMs are blocked
                    try:
                        await message.channel.send(f"✅ {user.mention}, cooldown for `/{cmd_name}` is over! (Couldn't DM you.)")
                    except Exception:
                        pass

# ----------------------------
# Slash commands (app_commands)
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds). Admins only recommended.")
@discord.app_commands.describe(command="Command name (e.g. open-boxes, summer)", seconds="Seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    # NOTE: You can add permission checks here (e.g., check for manage_guild)
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return

    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for `/{command}` updated to {seconds} seconds.", ephemeral=True)


@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    active = []
    for (uid, cmd), end_time in list(cooldowns.items()):
        if uid == user_id and end_time > now:
            active.append(f"/{cmd}: {int(end_time - now)}s")

    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True)


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
