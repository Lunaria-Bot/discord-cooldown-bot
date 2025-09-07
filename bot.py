# bot.py
import discord
from discord.ext import commands
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

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# Persistence
# ----------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "cooldowns": {},
        "settings": {},
        "default_cooldowns": {
            "Refreshing Box": 60,
            "Premium Pack": 60,
            "Summon": 1800,
        },
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

def get_user_settings(user_id):
    uid = str(user_id)
    if uid not in data["settings"]:
        data["settings"][uid] = {"dm_enabled": True}
        save_data()
    return data["settings"][uid]

# ----------------------------
# Utility
# ----------------------------
async def start_cooldown(user, cmd_name, cd_seconds, channel):
    key = f"{user.id}:{cmd_name}"
    now = time.time()
    end = now + cd_seconds

    # already on cooldown
    if key in data["cooldowns"] and data["cooldowns"][key] > now:
        return

    data["cooldowns"][key] = end
    save_data()

    settings = get_user_settings(user.id)
    msg = f"⚡ Cooldown started for {cmd_name} — I'll remind you in {cd_seconds} seconds."

    try:
        if settings.get("dm_enabled", True):
            await user.send(msg)
        else:
            await channel.send(f"{user.mention} {msg}")
    except discord.Forbidden:
        await channel.send(f"{user.mention} {msg}")

    async def reminder():
        await asyncio.sleep(cd_seconds)
        if data["cooldowns"].get(key, 0) <= time.time():
            data["cooldowns"].pop(key, None)
            save_data()
            try:
                if settings.get("dm_enabled", True):
                    await user.send(f"✅ Your cooldown for {cmd_name} is over.")
                else:
                    await channel.send(f"✅ {user.mention}, your cooldown for {cmd_name} is over.")
            except discord.Forbidden:
                await channel.send(f"✅ {user.mention}, your cooldown for {cmd_name} is over.")

    asyncio.create_task(reminder())

# ----------------------------
# Events
# ----------------------------
@bot.event
async def on_ready():
    global data
    data = load_data()  # ensure fresh load at startup

    guild = None
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print(f"📜 Slash commands synced instantly to guild {GUILD_ID}", flush=True)
    else:
        await bot.tree.sync()
        print("📜 Slash commands synced globally (may take up to 1h).", flush=True)

    print("✅ Registered Slash Commands:")
    for cmd in bot.tree.get_commands(guild=guild):
        print(f" - /{cmd.name}")
    print(f"✅ Logged in as {bot.user} ({bot.user.id})", flush=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter_meta = getattr(message, "interaction_metadata", None)
        if not inter_meta or not inter_meta.user:
            return

        if message.embeds:
            embed = message.embeds[0]
            desc = (embed.description or "").lower()

            # Refreshing Box
            if inter_meta.name == "open-boxes":
                if "no boxes available to open" in desc:
                    return
                await start_cooldown(
                    inter_meta.user,
                    "Refreshing Box",
                    data["default_cooldowns"]["Refreshing Box"],
                    message.channel,
                )

            # Premium Pack
            elif inter_meta.name == "premium-pack":
                if "no premium packs available to open" in desc:
                    return
                await start_cooldown(
                    inter_meta.user,
                    "Premium Pack",
                    data["default_cooldowns"]["Premium Pack"],
                    message.channel,
                )

            # Summon
            elif inter_meta.name == "summon":
                if "you can summon again in" in desc:
                    return
                await start_cooldown(
                    inter_meta.user,
                    "Summon",
                    data["default_cooldowns"]["Summon"],
                    message.channel,
                )

    await bot.process_commands(message)

# ----------------------------
# Slash commands
# ----------------------------
@bot.tree.command(name="settings", description="View or change your DM reminder settings")
@discord.app_commands.describe(dm="Enable or disable DM reminders (true/false). Leave empty to view current setting.")
async def settings(interaction: discord.Interaction, dm: bool = None):
    uid = str(interaction.user.id)
    current_settings = get_user_settings(uid)

    if dm is None:
        await interaction.response.send_message(
            f"🔧 Your DM reminders are currently **{'enabled' if current_settings['dm_enabled'] else 'disabled'}**.",
            ephemeral=True
        )
    else:
        data["settings"][uid]["dm_enabled"] = dm
        save_data()
        await interaction.response.send_message(
            f"✅ DM reminders are now {'enabled' if dm else 'disabled'}.",
            ephemeral=True
        )

@bot.tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def checkcooldowns(interaction: discord.Interaction):
    now = time.time()
    active = []
    for key, end in data["cooldowns"].items():
        uid, cmd = key.split(":", 1)
        if uid == str(interaction.user.id) and end > now:
            active.append(f"{cmd}: {int(end - now)}s")
    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Active cooldowns:\n" + "\n".join(active), ephemeral=True)

@bot.tree.command(name="setcooldown", description="Set a cooldown time for a command (admin only)")
@discord.app_commands.describe(command="Command name", seconds="Cooldown duration in seconds")
async def setcooldown(interaction: discord.Interaction, command: str, seconds: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    data["default_cooldowns"][command] = seconds
    save_data()
    await interaction.response.send_message(f"✅ Default cooldown for {command} set to {seconds}s.", ephemeral=True)

@bot.tree.command(name="reload", description="Reload bot data (admin only)")
async def reload(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only.", ephemeral=True)
        return
    global data
    data = load_data()
    await interaction.response.send_message("✅ Data reloaded from disk.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    bot.run(TOKEN)
