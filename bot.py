# bot.py
import discord
import asyncio
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
MAZOKU_BOT_ID = 1242388858897956906  # Mazoku bot ID

DATA_FILE = "botdata.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# -----------------------------------
# Cooldown and user settings storage
# -----------------------------------
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}

ALIASES = {
    "open-boxes": "Refreshing Box",
    "Refreshing Box": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "open": "Premium Pack",
    "Premium Pack": "Premium Pack",
}

# (user_id, command) -> end_timestamp
cooldowns = {}
# user_id -> { "dm": True/False }
user_settings = {}


# ----------------------------
# Persistence helpers
# ----------------------------
def load_data():
    global cooldowns, user_settings
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                cooldowns = {tuple(map(int, k.split(":"))): v for k, v in data.get("cooldowns", {}).items()}
                user_settings = {int(k): v for k, v in data.get("user_settings", {}).items()}
        except Exception as e:
            print(f"❌ Failed to load data: {e}", flush=True)


def save_data():
    try:
        data = {
            "cooldowns": {f"{uid}:{cmd}": ts for (uid, cmd), ts in cooldowns.items()},
            "user_settings": user_settings,
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Failed to save data: {e}", flush=True)


# ----------------------------
# Utility
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)


async def notify_user(user: discord.User, channel: discord.TextChannel, text: str):
    """Try DM first, fallback to channel if disabled or blocked."""
    dm_enabled = user_settings.get(user.id, {}).get("dm", True)
    if dm_enabled:
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
    load_data()
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            await tree.sync(guild=guild)
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

    # Only track Mazoku bot
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_alias = getattr(inter, "name", None)
        user = getattr(inter, "user", None)
        if not cmd_alias or not user:
            return

        # Resolve alias
        cmd_name = ALIASES.get(cmd_alias)
        if not cmd_name:
            return

        # Special case: don't start cooldown if "No boxes available to open"
        if cmd_alias == "open-boxes" and message.embeds:
            if any("No boxes available" in (embed.description or "") for embed in message.embeds):
                return

        now = time.time()
        key = (user.id, cmd_name)
        end = cooldowns.get(key, 0)

        if end > now:
            remaining = int(end - now)
            await notify_user(user, message.channel, f"⏳ cooldown for **{cmd_name}** still active ({remaining}s left).")
            return

        cd = COOLDOWN_SECONDS.get(cmd_name, 60)
        cooldowns[key] = now + cd
        save_data()

        await notify_user(user, message.channel, f"⚡ cooldown started for **{cmd_name}** — {cd}s")

        async def reminder():
            await asyncio.sleep(cd)
            if cooldowns.get(key, 0) <= time.time():
                cooldowns.pop(key, None)
                save_data()
                await notify_user(user, message.channel, f"✅ cooldown for **{cmd_name}** is over!")

        client.loop.create_task(reminder())


# ----------------------------
# Slash commands
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds). Admins only recommended.")
@discord.app_commands.describe(command="Command name", seconds="Cooldown time in seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    COOLDOWN_SECONDS[command] = seconds
    save_data()
    await interaction.response.send_message(f"✅ Cooldown for **{command}** set to {seconds}s.", ephemeral=True)


@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    now = time.time()
    active = []
    for (uid, cmd), end_time in cooldowns.items():
        if uid == interaction.user.id and end_time > now:
            active.append(f"**{cmd}**: {int(end_time - now)}s")
    if not active:
        await interaction.response.send_message("✅ No active cooldowns.", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Active cooldowns:\n" + "\n".join(active), ephemeral=True)


@tree.command(name="settings", description="Change your personal settings")
@discord.app_commands.describe(dm="Enable or disable DM notifications")
async def settings(interaction: discord.Interaction, dm: bool):
    user_settings.setdefault(interaction.user.id, {})["dm"] = dm
    save_data()
    state = "enabled" if dm else "disabled"
    await interaction.response.send_message(f"✅ DM notifications {state}.", ephemeral=True)


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
