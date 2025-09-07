import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import os

# ---------------- Discord Setup ----------------
INTENTS = discord.Intents.default()
INTENTS.messages = True
INTENTS.message_content = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "botdata.json"
GUILD_ID = 1399784437440319508   # replace with your server ID

# ---------------- Persistence ----------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            d = json.load(f)
    else:
        d = {
            "cooldowns": {},
            "settings": {},
            "default_cooldowns": {
                "Refreshing Box": 60,
                "Summon": 1800,
                "Premium Pack": 60,
            }
        }
        save_data(d)

    # Cleanup expired cooldowns
    now = discord.utils.utcnow().timestamp()
    for uid in list(d["cooldowns"].keys()):
        for cmd, expiry in list(d["cooldowns"][uid].items()):
            if expiry <= now:
                del d["cooldowns"][uid][cmd]
        if not d["cooldowns"][uid]:
            del d["cooldowns"][uid]

    return d

def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=4)

data = load_data()

# ---------------- Helper ----------------
async def start_cooldown(user: discord.User, command: str, duration: int, channel: discord.TextChannel):
    user_id = str(user.id)
    if user_id not in data["cooldowns"]:
        data["cooldowns"][user_id] = {}

    expires_at = discord.utils.utcnow().timestamp() + duration
    data["cooldowns"][user_id][command] = expires_at
    save_data(data)

    dm_enabled = data["settings"].get(user_id, {}).get("dm_enabled", True)
    reminder_msg = f"⚡ {user.mention}, cooldown started for **{command}** — I’ll remind you in {duration} seconds."

    try:
        if dm_enabled:
            await user.send(reminder_msg)
        else:
            await channel.send(reminder_msg)
    except discord.Forbidden:
        await channel.send(reminder_msg)

    await asyncio.sleep(duration)

    # Cleanup after expiry
    if user_id in data["cooldowns"] and command in data["cooldowns"][user_id]:
        if data["cooldowns"][user_id][command] <= discord.utils.utcnow().timestamp():
            del data["cooldowns"][user_id][command]
            if not data["cooldowns"][user_id]:
                del data["cooldowns"][user_id]
            save_data(data)

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
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"📜 Slash commands synced instantly to guild {guild.id}", flush=True)
    print(f"✅ Logged in as {bot.user} ({bot.user.id})", flush=True)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot and message.author.name == "Mazoku":
        # Ignore "No boxes available to open"
        if message.embeds:
            embed = message.embeds[0]
            if embed.description and "No boxes available to open" in embed.description:
                return  

        inter_meta = getattr(message, "interaction_metadata", None)
        if inter_meta and inter_meta.user:
            await start_cooldown(inter_meta.user, "Refreshing Box", data["default_cooldowns"]["Refreshing Box"], message.channel)

    await bot.process_commands(message)

# ---------------- Slash Commands ----------------
@bot.tree.command(description="Check your active cooldowns", guild=discord.Object(id=GUILD_ID))
async def checkcooldowns(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = discord.utils.utcnow().timestamp()
    cooldowns = data["cooldowns"].get(user_id, {})

    msg_lines = []
    for cmd, expiry in list(cooldowns.items()):
        remaining = int(expiry - now)
        if remaining > 0:
            msg_lines.append(f"⏳ **{cmd}**: {remaining}s remaining")
        else:
            del data["cooldowns"][user_id][cmd]
    if user_id in data["cooldowns"] and not data["cooldowns"][user_id]:
        del data["cooldowns"][user_id]
    save_data(data)

    if not msg_lines:
        msg_lines = ["✅ You have no active cooldowns."]

    await interaction.response.send_message("\n".join(msg_lines), ephemeral=True)

@bot.tree.command(description="Set a cooldown time for a command (seconds). Admins only.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(command="Command name", seconds="Cooldown time in seconds")
async def setcooldown(interaction: discord.Interaction, command: str, seconds: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return

    data["default_cooldowns"][command] = seconds
    save_data(data)
    await interaction.response.send_message(f"✅ Default cooldown for **{command}** set to {seconds} seconds.")

@bot.tree.command(description="Change your personal settings", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(dm="Enable or disable DM reminders (true/false)")
async def settings(interaction: discord.Interaction, dm: bool):
    user_id = str(interaction.user.id)
    if user_id not in data["settings"]:
        data["settings"][user_id] = {}
    data["settings"][user_id]["dm_enabled"] = dm
    save_data(data)
    await interaction.response.send_message(f"✅ DM reminders {'enabled' if dm else 'disabled'}.", ephemeral=True)

@bot.tree.command(description="Reload bot settings from file (Admin only)", guild=discord.Object(id=GUILD_ID))
async def reload(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin only command.", ephemeral=True)
        return
    global data
    data = load_data()
    save_data(data)
    await interaction.response.send_message("🔄 Settings reloaded & expired cooldowns cleaned.", ephemeral=True)

# ---------------- Run ----------------
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    bot.run(TOKEN)
