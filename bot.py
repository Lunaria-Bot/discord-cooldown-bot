# bot.py
import discord
import asyncio
import os
import time
import json

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
MAZOKU_BOT_ID = 1242388858897956906

SETTINGS_FILE = "settings.json"
COOLDOWNS_FILE = "cooldowns.json"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# Cooldowns + Aliases
# ----------------------------
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}

ALIASES = {
    "open-boxes": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "premium-pack": "Premium Pack",
}

# ----------------------------
# Persistent data
# ----------------------------
user_settings = {}   # user_id -> {"dm_reminders": bool}
cooldowns = {}       # (user_id, command) -> end_timestamp

def load_settings():
    global user_settings
    try:
        with open(SETTINGS_FILE, "r") as f:
            user_settings = json.load(f)
        print("✅ Loaded user settings from file.", flush=True)
    except FileNotFoundError:
        user_settings = {}
        print("ℹ️ No settings file found, starting fresh.", flush=True)

def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(user_settings, f)
        print("💾 User settings saved.", flush=True)
    except Exception as e:
        print(f"❌ Failed to save settings: {e}", flush=True)

def load_cooldowns():
    global cooldowns
    try:
        with open(COOLDOWNS_FILE, "r") as f:
            raw = json.load(f)
        now = time.time()
        cooldowns = {
            (int(uid), cmd): end
            for (uid, cmd), end in raw.items()
            if end > now  # skip expired cooldowns
        }
        print(f"✅ Loaded {len(cooldowns)} active cooldowns from file.", flush=True)
    except FileNotFoundError:
        cooldowns = {}
        print("ℹ️ No cooldowns file found, starting fresh.", flush=True)
    except Exception as e:
        cooldowns = {}
        print(f"❌ Failed to load cooldowns: {e}", flush=True)

def save_cooldowns():
    try:
        raw = { (str(uid), cmd): end for (uid, cmd), end in cooldowns.items() }
        with open(COOLDOWNS_FILE, "w") as f:
            json.dump(raw, f)
        print("💾 Cooldowns saved.", flush=True)
    except Exception as e:
        print(f"❌ Failed to save cooldowns: {e}", flush=True)

def wants_dm(user_id: int) -> bool:
    return user_settings.get(str(user_id), {}).get("dm_reminders", True)

# ----------------------------
# Utility helpers
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction_metadata", None)
    if inter:
        return inter
    return getattr(message, "interaction", None)

# ----------------------------
# Events
# ----------------------------
@client.event
async def on_ready():
    load_settings()
    load_cooldowns()

    # restart timers for active cooldowns
    now = time.time()
    for (uid, cmd), end in list(cooldowns.items()):
        remaining = end - now
        if remaining > 0:
            async def reminder_task(user_id=uid, command=cmd, wait=remaining):
                await asyncio.sleep(wait)
                if cooldowns.get((user_id, command), 0) <= time.time():
                    cooldowns.pop((user_id, command), None)
                    save_cooldowns()
                    reminder = f"✅ Your cooldown for `{command}` is over — you can use it again."
                    try:
                        user = await client.fetch_user(user_id)
                        if wants_dm(user_id):
                            await user.send(reminder)
                        else:
                            # fallback: no channel reference, so just DM attempt
                            await user.send(reminder)
                    except Exception:
                        pass
            client.loop.create_task(reminder_task())

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

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        cmd_name = getattr(inter, "name", None)
        user = getattr(inter, "user", None)
        if not cmd_name or not user:
            return

        if cmd_name in ALIASES:
            display_name = ALIASES[cmd_name]
        else:
            return

        if display_name not in COOLDOWN_SECONDS:
            return

        now = time.time()
        key = (user.id, display_name)
        end = cooldowns.get(key, 0)

        if end > now:
            remaining = int(end - now)
            msg = f"⏳ {user.mention}, you're still on cooldown for `{display_name}` ({remaining}s left)."
            try:
                if wants_dm(user.id):
                    await user.send(msg)
                else:
                    await message.channel.send(msg)
            except Exception:
                pass
            return

        cd = COOLDOWN_SECONDS[display_name]
        cooldowns[key] = now + cd
        save_cooldowns()

        start_msg = f"⚡ Cooldown started for `{display_name}` — I'll remind you in {cd} seconds."
        try:
            if wants_dm(user.id):
                await user.send(start_msg)
            else:
                await message.channel.send(f"{user.mention} {start_msg}")
        except Exception:
            pass

        async def reminder_task():
            await asyncio.sleep(cd)
            if cooldowns.get(key, 0) <= time.time():
                cooldowns.pop(key, None)
                save_cooldowns()
                reminder = f"✅ Your cooldown for `{display_name}` is over — you can use it again."
                try:
                    if wants_dm(user.id):
                        await user.send(reminder)
                    else:
                        await message.channel.send(f"{user.mention} {reminder}")
                except discord.Forbidden:
                    try:
                        await message.channel.send(f"✅ {user.mention}, cooldown for `{display_name}` is over! (Couldn't DM you.)")
                    except Exception:
                        pass

        client.loop.create_task(reminder_task())

# ----------------------------
# Slash commands
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds). Admins only recommended.")
@discord.app_commands.describe(command="Command name (alias or display)", seconds="Seconds")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return
    if command in ALIASES:
        command = ALIASES[command]
    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for `{command}` updated to {seconds} seconds.", ephemeral=True)

@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    active = []
    for (uid, cmd), end_time in list(cooldowns.items()):
        if uid == user_id and end_time > now:
            active.append(f"{cmd}: {int(end_time - now)}s")
    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Your active cooldowns:\n" + "\n".join(active), ephemeral=True)

@tree.command(name="settings", description="Change your cooldown reminder settings")
@discord.app_commands.describe(dm="Enable or disable DM reminders (on/off)")
async def settings(interaction: discord.Interaction, dm: str):
    uid = str(interaction.user.id)
    if uid not in user_settings:
        user_settings[uid] = {"dm_reminders": True}
    if dm.lower() in ["on", "true", "yes"]:
        user_settings[uid]["dm_reminders"] = True
        save_settings()
        await interaction.response.send_message("✅ Cooldown reminders will now be sent via DM.", ephemeral=True)
    elif dm.lower() in ["off", "false", "no"]:
        user_settings[uid]["dm_reminders"] = False
        save_settings()
        await interaction.response.send_message("✅ Cooldown reminders will now be sent in the channel only.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Please specify `on` or `off` for DM reminders.", ephemeral=True)

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
