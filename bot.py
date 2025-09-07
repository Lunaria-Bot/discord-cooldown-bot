# bot.py
import discord
import asyncio
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
MAZOKU_BOT_ID = 1242388858897956906  # Update if needed

DATA_FILE = "botdata.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# Persistence
# ----------------------------
data = {"cooldowns": {}, "user_settings": {}}

def load_data():
    global data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            print("❌ Failed to load botdata.json, starting fresh.")
            data = {"cooldowns": {}, "user_settings": {}}
    else:
        # Create file with defaults
        save_data()
        print("📂 Created new botdata.json with defaults.")

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_user_settings(user_id: int):
    return data["user_settings"].get(str(user_id), {"dm": True})

def set_user_settings(user_id: int, settings: dict):
    data["user_settings"][str(user_id)] = settings
    save_data()

# ----------------------------
# Cooldown setup
# ----------------------------
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium pack": 60,
}

ALIASES = {
    "open-boxes": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "premium-pack": "Premium pack",
}

def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

# ----------------------------
# Events
# ----------------------------
@client.event
async def on_ready():
    load_data()
    try:
        if GUILD_ID:
            synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
            print(f"📜 Slash commands synced instantly to guild {GUILD_ID}")
            for cmd in synced:
                print(f"   ⏺️ /{cmd.name}")
        else:
            synced = await tree.sync()
            print("📜 Slash commands synced globally (may take up to 1 hour).")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    print(f"✅ Logged in as {client.user} ({client.user.id})")

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)

        if cmd_name in ALIASES and user:
            display_name = ALIASES[cmd_name]
            now = time.time()
            key = f"{user.id}:{display_name}"
            end = data["cooldowns"].get(key, 0)

            if end > now:
                remaining = int(end - now)
                try:
                    await message.channel.send(
                        f"⏳ {user.mention}, you're still on cooldown for **{display_name}** ({remaining}s left)."
                    )
                except Exception:
                    pass
                return

            cd = COOLDOWN_SECONDS[display_name]
            data["cooldowns"][key] = now + cd
            save_data()

            user_settings = get_user_settings(user.id)
            if user_settings.get("dm", True):
                try:
                    await user.send(
                        f"⚡ Cooldown started for **{display_name}** — I'll remind you in {cd} seconds."
                    )
                except discord.Forbidden:
                    await message.channel.send(
                        f"⚡ {user.mention}, cooldown started for **{display_name}** — I'll remind you in {cd} seconds. (Couldn't DM you)"
                    )
            else:
                await message.channel.send(
                    f"⚡ {user.mention}, cooldown started for **{display_name}** — I'll remind you in {cd} seconds."
                )

            await asyncio.sleep(cd)
            if data["cooldowns"].get(key, 0) <= time.time():
                data["cooldowns"].pop(key, None)
                save_data()
                try:
                    if user_settings.get("dm", True):
                        await user.send(f"✅ Your cooldown for **{display_name}** is over!")
                    else:
                        await message.channel.send(
                            f"✅ {user.mention}, cooldown for **{display_name}** is over!"
                        )
                except discord.Forbidden:
                    await message.channel.send(
                        f"✅ {user.mention}, cooldown for **{display_name}** is over! (Couldn't DM you)"
                    )

# ----------------------------
# Slash Commands
# ----------------------------
@tree.command(
    name="setcooldown",
    description="Set a cooldown time for a command (seconds).",
    guild=discord.Object(id=GUILD_ID) if GUILD_ID else None,
)
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return
    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(
        f"✅ Cooldown for **{command}** updated to {seconds} seconds.", ephemeral=True
    )

@tree.command(
    name="checkcooldowns",
    description="Check your active cooldowns.",
    guild=discord.Object(id=GUILD_ID) if GUILD_ID else None,
)
async def check_cooldowns(interaction: discord.Interaction):
    now = time.time()
    active = []
    for key, end in data["cooldowns"].items():
        uid, cmd = key.split(":", 1)
        if uid == str(interaction.user.id) and end > now:
            active.append(f"{cmd}: {int(end - now)}s")
    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message(
            "⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True
        )

@tree.command(
    name="settings",
    description="Enable or disable DM reminders.",
    guild=discord.Object(id=GUILD_ID) if GUILD_ID else None,
)
@discord.app_commands.describe(dm="Enable (true) or disable (false) DMs")
async def settings(interaction: discord.Interaction, dm: bool):
    set_user_settings(interaction.user.id, {"dm": dm})
    state = "enabled" if dm else "disabled"
    await interaction.response.send_message(f"✅ DMs are now **{state}**.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!")
        raise SystemExit(1)
    print("🚀 Starting bot...")
    client.run(TOKEN)
