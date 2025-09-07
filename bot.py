import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import os

INTENTS = discord.Intents.default()
INTENTS.messages = True
INTENTS.message_content = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "botdata.json"

# ---------------- Persistence ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"cooldowns": {}, "settings": {}, "default_cooldowns": {
        "Refreshing Box": 60,
        "Summon": 1800,
        "Premium Pack": 60
    }}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

# ---------------- Helper ----------------
async def start_cooldown(user, command, duration, channel):
    user_id = str(user.id)
    if user_id not in data["cooldowns"]:
        data["cooldowns"][user_id] = {}

    # Save expiry timestamp
    expires_at = discord.utils.utcnow().timestamp() + duration
    data["cooldowns"][user_id][command] = expires_at
    save_data()

    # DM or fallback to channel
    dm_enabled = data["settings"].get(user_id, {}).get("dm_enabled", True)
    reminder_msg = f"⚡ {user.mention}, cooldown started for **{command}** — I’ll remind you in {duration} seconds."

    try:
        if dm_enabled:
            await user.send(reminder_msg)
        else:
            await channel.send(reminder_msg)
    except discord.Forbidden:
        await channel.send(reminder_msg)

    # Wait and remind
    await asyncio.sleep(duration)
    try:
        if dm_enabled:
            await user.send(f"⏰ {command} cooldown expired — you can use it again!")
        else:
            await channel.send(f"⏰ {user.mention}, {command} cooldown expired — you can use it again!")
    except discord.Forbidden:
        await channel.send(f"⏰ {user.mention}, {command} cooldown expired — you can use it again!")

# ---------------- Events ----------------
@bot.event
async def on_ready():
    guild = discord.Object(id=1399784437440319508)  # your test guild
    await bot.tree.sync(guild=guild)
    print(f"📜 Slash commands synced instantly to guild {guild.id}")
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")

@bot.event
async def on_message(message: discord.Message):
    # Only check Mazoku bot messages
    if message.author.bot and message.author.name == "Mazoku":
        if message.embeds:
            embed = message.embeds[0]
            # ❌ Ignore cooldown if no box was opened
            if embed.description and "No boxes available to open" in embed.description:
                return  

        if message.interaction and message.interaction.user:
            user = message.interaction.user
            await start_cooldown(user, "Refreshing Box", 60, message.channel)

    await bot.process_commands(message)

# ---------------- Slash Commands ----------------
@bot.tree.command(description="Check your active cooldowns")
async def checkcooldowns(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = discord.utils.utcnow().timestamp()
    cooldowns = data["cooldowns"].get(user_id, {})

    if not cooldowns:
        await interaction.response.send_message("✅ You have no active cooldowns.", ephemeral=True)
        return

    msg_lines = []
    for cmd, expiry in cooldowns.items():
        remaining = int(expiry - now)
        if remaining > 0:
            msg_lines.append(f"⏳ **{cmd}**: {remaining}s remaining")
    if not msg_lines:
        msg_lines = ["✅ You have no active cooldowns."]

    await interaction.response.send_message("\n".join(msg_lines), ephemeral=True)

@bot.tree.command(description="Set a cooldown time for a command (seconds). Admins only.")
@app_commands.describe(command="Command name", seconds="Cooldown time in seconds")
async def setcooldown(interaction: discord.Interaction, command: str, seconds: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return

    data["default_cooldowns"][command] = seconds
    save_data()
    await interaction.response.send_message(f"✅ Default cooldown for **{command}** set to {seconds} seconds.")

@bot.tree.command(description="Change your personal settings")
@app_commands.describe(dm="Enable or disable DM reminders (true/false)")
async def settings(interaction: discord.Interaction, dm: bool):
    user_id = str(interaction.user.id)
    if user_id not in data["settings"]:
        data["settings"][user_id] = {}
    data["settings"][user_id]["dm_enabled"] = dm
    save_data()
    await interaction.response.send_message(f"✅ DM reminders {'enabled' if dm else 'disabled'}.", ephemeral=True)

@bot.tree.command(description="Reload bot settings from file (Admin only)")
async def reload(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return
    global data
    data = load_data()
    await interaction.response.send_message("🔄 Settings reloaded from file.", ephemeral=True)

# ---------------- Run ----------------
bot.run("YOUR_BOT_TOKEN")
