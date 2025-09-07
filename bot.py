# bot.py
import discord
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))
MAZOKU_BOT_ID = 1242388858897956906

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# ----------------------------
# CONFIG
# ----------------------------
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}
COMMAND_ALIASES = {
    "open-boxes": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "open": "Premium Pack",
}
cooldowns = {}

# ----------------------------
# SAFE SEND HELPER
# ----------------------------
async def safe_send(target, content: str, retries: int = 3, delay: float = 1.0):
    """
    Safely send a message to target (channel or DM).
    Retries on rate-limit or temporary failure.
    """
    for attempt in range(retries):
        try:
            return await target.send(content)
        except discord.Forbidden:
            raise  # DM blocked, caller should fallback
        except discord.HTTPException as e:
            if attempt < retries - 1:
                await asyncio.sleep(delay * (attempt + 1))  # backoff
            else:
                print(f"❌ Failed to send message after {retries} retries: {e}", flush=True)

# ----------------------------
# UTILS
# ----------------------------
def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)

# ----------------------------
# EVENTS
# ----------------------------
@client.event
async def on_ready():
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

    # DEBUG
    print(
        f"[DEBUG] From {message.author} ({message.author.id}) content={repr(message.content)}",
        flush=True,
    )

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        if not inter:
            return

        raw_cmd = getattr(inter, "name", None)
        user = getattr(inter, "user", None)

        if not raw_cmd or not user:
            return

        cmd_name = COMMAND_ALIASES.get(raw_cmd, raw_cmd)
        if cmd_name not in COOLDOWN_SECONDS:
            return

        # check for failure text like "No boxes available"
        if any("no boxes available" in embed.description.lower()
               for embed in message.embeds if embed.description):
            print(f"⚠️ Skipping cooldown for {user} because action failed.", flush=True)
            return

        now = time.time()
        key = (user.id, cmd_name)
        end = cooldowns.get(key, 0)

        if end > now:
            remaining = int(end - now)
            try:
                await safe_send(user, f"⏳ Cooldown still active for `{cmd_name}` — {remaining}s left.")
            except discord.Forbidden:
                await safe_send(message.channel, f"⏳ {user.mention}, cooldown still active for `{cmd_name}` — {remaining}s left.")
            return

        # start cooldown
        cd = COOLDOWN_SECONDS[cmd_name]
        cooldowns[key] = now + cd
        try:
            await safe_send(user, f"⚡ Cooldown started for `{cmd_name}` — I'll remind you in {cd} seconds.")
        except discord.Forbidden:
            await safe_send(message.channel, f"⚡ {user.mention}, cooldown started for `{cmd_name}` — I'll remind you in {cd} seconds.")

        await asyncio.sleep(cd)
        if cooldowns.get(key, 0) <= time.time():
            cooldowns.pop(key, None)
            try:
                await safe_send(user, f"✅ Your cooldown for `{cmd_name}` is over!")
            except discord.Forbidden:
                await safe_send(message.channel, f"✅ {user.mention}, cooldown for `{cmd_name}` is over!")

# ----------------------------
# SLASH COMMANDS
# ----------------------------
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds).")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return
    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for `{command}` updated to {seconds} seconds.", ephemeral=True)

@tree.command(name="checkcooldowns", description="Check your active cooldowns")
async def check_cooldowns(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    active = []
    for (uid, cmd), end_time in cooldowns.items():
        if uid == user_id and end_time > now:
            active.append(f"{cmd}: {int(end_time - now)}s")

    if not active:
        await interaction.response.send_message("✅ You have no active cooldowns!", ephemeral=True)
    else:
        await interaction.response.send_message("⏳ Active cooldowns:\n" + "\n".join(active), ephemeral=True)

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
