import discord
import asyncio
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
MAZOKU_BOT_ID = 1242388858897956906

DATA_FILE = "botdata.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# Data storage
# ----------------------------
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}

# (user_id, command) -> end_timestamp
cooldowns = {}
# user_id -> settings
user_settings = {}

def load_data():
    global cooldowns, user_settings
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                cooldowns = data.get("cooldowns", {})
                user_settings = data.get("user_settings", {})
            print("📂 Loaded data from disk.", flush=True)
        except Exception as e:
            print(f"⚠️ Failed to load data: {e}", flush=True)

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({"cooldowns": cooldowns, "user_settings": user_settings}, f)
        print("💾 Data saved to disk.", flush=True)
    except Exception as e:
        print(f"⚠️ Failed to save data: {e}", flush=True)

# ----------------------------
# Utility helpers
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    return getattr(message, "interaction", None) or getattr(message, "interaction_metadata", None)

async def send_dm_or_channel(user: discord.User, channel: discord.TextChannel, msg: str):
    """Try to DM user, fallback to channel if DMs blocked. Logs success/fail."""
    # DM preference: default True
    dm_enabled = user_settings.get(str(user.id), {}).get("dm", True)

    if dm_enabled:
        try:
            await user.send(msg)
            print(f"[DM SUCCESS] Sent DM to {user} ({user.id}) -> {msg}", flush=True)
            return
        except discord.Forbidden:
            print(f"[DM FAIL] Cannot DM {user} ({user.id}), falling back.", flush=True)

    # fallback
    try:
        await channel.send(f"{user.mention} {msg}")
        print(f"[CHANNEL NOTICE] Sent in channel for {user} ({user.id}) -> {msg}", flush=True)
    except Exception as e:
        print(f"[ERROR] Could not send fallback message: {e}", flush=True)

# ----------------------------
# Events
# ----------------------------
@client.event
async def on_ready():
    load_data()
    try:
        if GUILD_ID:
            await tree.sync(guild=discord.Object(id=GUILD_ID))
            print(f"📜 Slash commands synced to guild {GUILD_ID}", flush=True)
        else:
            await tree.sync()
            print("📜 Slash commands synced globally.", flush=True)
    except Exception as e:
        print(f"❌ Error syncing commands: {e}", flush=True)

    print(f"✅ Logged in as {client.user} ({client.user.id})", flush=True)

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    # Debug logging for everything bot sees
    print(f"[DEBUG] From {message.author} ({message.author.id}) content={repr(message.content)}", flush=True)

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)

        # Map aliases
        if cmd_name == "open-boxes":
            display_name = "Refreshing Box"
        elif cmd_name == "summer":
            display_name = "summer"
        elif cmd_name == "summon":
            display_name = "summon"
        elif cmd_name == "premium-pack":
            display_name = "Premium Pack"
        else:
            return

        if not user:
            return

        now = time.time()
        key = (str(user.id), display_name)
        end = cooldowns.get(str(key), 0)

        if end > now:
            remaining = int(end - now)
            await send_dm_or_channel(user, message.channel, f"⏳ You’re still on cooldown for {display_name} ({remaining}s left).")
            return

        cd = COOLDOWN_SECONDS[display_name]
        cooldowns[str(key)] = now + cd
        save_data()

        await send_dm_or_channel(user, message.channel, f"⚡ Cooldown started for {display_name} — I’ll remind you in {cd} seconds.")

        async def clear_later():
            await asyncio.sleep(cd)
            if cooldowns.get(str(key), 0) <= time.time():
                cooldowns.pop(str(key), None)
                save_data()
                await send_dm_or_channel(user, message.channel, f"✅ Cooldown for {display_name} is over — you can use it again.")

        client.loop.create_task(clear_later())

# ----------------------------
# Slash Commands
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds).")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if command not in COOLDOWN_SECONDS:
        await interaction.response.send_message(f"❌ Unknown command `{command}`", ephemeral=True)
        return
    COOLDOWN_SECONDS[command] = seconds
    save_data()
    await interaction.response.send_message(f"✅ Cooldown for {command} updated to {seconds} seconds.", ephemeral=True)

@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    active = []
    for key, end_time in list(cooldowns.items()):
        uid, cmd = eval(key)  # stored as str((user_id, cmd))
        if uid == user_id and end_time > now:
            active.append(f"{cmd}: {int(end_time - now)}s")

    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True)

@tree.command(name="settings", description="Change your bot settings")
async def settings(interaction: discord.Interaction, dm: bool):
    uid = str(interaction.user.id)
    if uid not in user_settings:
        user_settings[uid] = {}
    user_settings[uid]["dm"] = dm
    save_data()
    await interaction.response.send_message(f"✅ DM reminders set to {dm}.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
