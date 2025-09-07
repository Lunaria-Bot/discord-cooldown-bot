# bot.py
import discord
import asyncio
import os
import time
import json
from pathlib import Path

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))   # set this to your server ID
MAZOKU_BOT_ID = 1242388858897956906                # Mazoku bot ID

DATA_FILE = Path("data.json")

# ----------------------------
# Persistence Helpers
# ----------------------------
def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"cooldowns": {}, "settings": {}}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"cooldowns": cooldowns, "settings": user_settings}, f)

data = load_data()
cooldowns = data["cooldowns"]          # (user_id, cmd) → end_timestamp
user_settings = data["settings"]       # user_id → {"dm": True/False}

# ----------------------------
# Bot Setup
# ----------------------------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# Aliases and default cooldowns
COMMAND_ALIASES = {
    "open-boxes": "Refreshing Box",
    "summon": "Summon",
    "summer": "Summer",
    "open": "Premium Pack",
}
DEFAULT_COOLDOWNS = {
    "Refreshing Box": 60,
    "Summon": 1800,
    "Summer": 1800,
    "Premium Pack": 60,
}

# ----------------------------
# Utils
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

def user_wants_dm(user_id: int) -> bool:
    return user_settings.get(str(user_id), {}).get("dm", True)

async def notify_user(user: discord.User, channel: discord.TextChannel, text: str):
    """Try DM first, fallback to channel if disabled or blocked."""
    if user_wants_dm(user.id):
        try:
            await user.send(text)
            return
        except discord.Forbidden:
            pass
    try:
        await channel.send(f"{user.mention} {text}")
    except Exception:
        pass

# ----------------------------
# Events
# ----------------------------
@client.event
async def on_ready():
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild)
            print(f"📜 Slash commands synced to guild {GUILD_ID}", flush=True)
        else:
            print("⚠️ No GUILD_ID set, skipping guild sync.", flush=True)
    except Exception as e:
        print(f"❌ Error syncing commands: {e}", flush=True)

    print(f"✅ Logged in as {client.user} ({client.user.id})", flush=True)


@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = COMMAND_ALIASES.get(getattr(inter, "name", None))
        user = getattr(inter, "user", None)
        if not cmd_name or not user:
            return

        # Skip cooldown if "No boxes available to open"
        if "No boxes available" in (message.content or ""):
            return

        now = time.time()
        key = (str(user.id), cmd_name)
        end = cooldowns.get(str(key), 0)

        if end > now:
            remaining = int(end - now)
            await notify_user(user, message.channel, f"⏳ cooldown still active for {cmd_name} ({remaining}s left).")
            return

        # Start cooldown
        cd = DEFAULT_COOLDOWNS.get(cmd_name, 60)
        cooldowns[str(key)] = now + cd
        save_data()
        await notify_user(user, message.channel, f"⚡ cooldown started for {cmd_name} — reminder in {cd} seconds.")

        # Reminder
        async def clear_after():
            await asyncio.sleep(cd)
            if cooldowns.get(str(key), 0) <= time.time():
                cooldowns.pop(str(key), None)
                save_data()
                await notify_user(user, message.channel, f"✅ cooldown for {cmd_name} is over!")

        asyncio.create_task(clear_after())

# ----------------------------
# Slash Commands
# ----------------------------
@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    active = []
    for key, end_time in cooldowns.items():
        uid, cmd = eval(key)
        if uid == user_id and end_time > now:
            active.append(f"{cmd}: {int(end_time - now)}s")
    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Active cooldowns:\n" + "\n".join(active), ephemeral=True)


@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds).")
@discord.app_commands.describe(command="Command name", seconds="Seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return
    DEFAULT_COOLDOWNS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for {command} set to {seconds}s.", ephemeral=True)


@tree.command(name="settings", description="Configure your personal settings")
@discord.app_commands.describe(dm="Enable or disable DM reminders")
async def settings(interaction: discord.Interaction, dm: bool):
    user_settings[str(interaction.user.id)] = {"dm": dm}
    save_data()
    await interaction.response.send_message(f"✅ DM reminders {'enabled' if dm else 'disabled'}.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
