# bot.py
import discord
import asyncio
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))   # set this to your server ID for instant sync
MAZOKU_BOT_ID = 1242388858897956906                # replace if different

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# Persistence helpers
# ----------------------------
SETTINGS_FILE = "settings.json"
COOLDOWNS_FILE = "cooldowns.json"

def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Failed to save {path}: {e}", flush=True)

# ----------------------------
# Data
# ----------------------------
# per-command default cooldowns (seconds)
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}

# Aliases: internal Mazoku command -> display name
ALIASES = {
    "open-boxes": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "premium-pack": "Premium Pack",
}

# Persistence
user_settings = load_json(SETTINGS_FILE, {})       # {user_id: {"dm_reminders": bool}}
cooldowns = load_json(COOLDOWNS_FILE, {})          # {(user_id, command): end_timestamp}

# ----------------------------
# Utility helpers
# ----------------------------
def save_settings():
    save_json(SETTINGS_FILE, user_settings)

def save_cooldowns():
    save_json(COOLDOWNS_FILE, cooldowns)

def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

def wants_dm(user_id: int) -> bool:
    return user_settings.get(str(user_id), {}).get("dm_reminders", True)

def cleanup_expired_cooldowns():
    now = time.time()
    expired = [(k, v) for k, v in cooldowns.items() if v <= now]
    for k, _ in expired:
        cooldowns.pop(k, None)
    if expired:
        save_cooldowns()

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

    # DEBUG logging
    print(
        f"[DEBUG] From {message.author} ({message.author.id}) content={repr(message.content)} "
        f"embeds={len(message.embeds)} interaction={getattr(message,'interaction',None)} "
        f"interaction_metadata={getattr(message,'interaction_metadata',None)}",
        flush=True,
    )

    # only handle Mazoku bot messages
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)
        if not cmd_name or not user:
            return

        if cmd_name in ALIASES:
            display = ALIASES[cmd_name]
            if display not in COOLDOWN_SECONDS:
                return

            now = time.time()
            key = (str(user.id), display)
            end = cooldowns.get(str(key), 0)

            if end > now:
                remaining = int(end - now)
                if wants_dm(user.id):
                    try:
                        await user.send(f"⏳ You're still on cooldown for **{display}** ({remaining}s left).")
                        return
                    except discord.Forbidden:
                        pass
                await message.channel.send(f"⏳ {user.mention}, you're still on cooldown for **{display}** ({remaining}s left).")
                return

            # Start cooldown
            cd = COOLDOWN_SECONDS[display]
            cooldowns[str(key)] = now + cd
            save_cooldowns()

            if wants_dm(user.id):
                try:
                    await user.send(f"⚡ Cooldown started for **{display}** — I'll remind you in {cd} seconds.")
                except discord.Forbidden:
                    await message.channel.send(f"⚡ {user.mention}, cooldown started for **{display}** — I'll remind you in {cd} seconds. (Couldn't DM you.)")
            else:
                await message.channel.send(f"⚡ {user.mention}, cooldown started for **{display}** — I'll remind you in {cd} seconds.")

            # Schedule reminder
            async def reminder():
                await asyncio.sleep(cd)
                cleanup_expired_cooldowns()
                if cooldowns.get(str(key), 0) <= time.time():
                    cooldowns.pop(str(key), None)
                    save_cooldowns()
                    if wants_dm(user.id):
                        try:
                            await user.send(f"✅ Your cooldown for **{display}** is over — you can use it again.")
                            return
                        except discord.Forbidden:
                            pass
                    try:
                        await message.channel.send(f"✅ {user.mention}, cooldown for **{display}** is over!")
                    except Exception:
                        pass

            client.loop.create_task(reminder())

# ----------------------------
# Slash commands
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds).")
@discord.app_commands.describe(command="Command name", seconds="Seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if command not in COOLDOWN_SECONDS:
        await interaction.response.send_message("❌ Unknown command.", ephemeral=True)
        return
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return

    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for **{command}** updated to {seconds} seconds.", ephemeral=True)


@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = time.time()
    active = []
    for key, end_time in cooldowns.items():
        uid, cmd = eval(key)  # stored as str((uid, cmd))
        if uid == user_id and end_time > now:
            active.append(f"{cmd}: {int(end_time - now)}s")

    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True)


@tree.command(name="settings", description="Change your cooldown reminder settings")
@discord.app_commands.describe(dm="Enable or disable DM reminders (True = on, False = off)")
async def settings(interaction: discord.Interaction, dm: bool):
    uid = str(interaction.user.id)
    if uid not in user_settings:
        user_settings[uid] = {"dm_reminders": True}

    user_settings[uid]["dm_reminders"] = dm
    save_settings()

    if dm:
        await interaction.response.send_message("✅ Cooldown reminders will now be sent via **DM**.", ephemeral=True)
    else:
        await interaction.response.send_message("✅ Cooldown reminders will now be sent in the **channel only**.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
