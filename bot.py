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

# cooldown config
COOLDOWN_SECONDS = {
    "Refreshing Box": 60,
    "summer": 1800,
    "summon": 1800,
    "Premium Pack": 60,
}

# aliases mapping
ALIASES = {
    "open-boxes": "Refreshing Box",
    "Refreshing Box": "Refreshing Box",
    "summer": "summer",
    "summon": "summon",
    "Premium Pack": "Premium Pack",
    "open": "Premium Pack",
}

cooldowns = {}


def get_interaction_from_message(message: discord.Message):
    inter = getattr(message, "interaction", None)
    if inter:
        return inter
    return getattr(message, "interaction_metadata", None)


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

    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        cmd_name, user = None, None

        if inter:
            cmd_name = getattr(inter, "name", None)
            user = getattr(inter, "user", None)
        elif message.embeds:
            title = message.embeds[0].title or ""
            cmd_name = title
            if message.mentions:
                user = message.mentions[0]

        if not cmd_name or not user:
            return

        canonical = ALIASES.get(cmd_name)
        if not canonical or canonical not in COOLDOWN_SECONDS:
            return

        # 🚫 check for "fail" responses (skip cooldowns)
        error_texts = [
            "No boxes available to open",
            "You don’t have any boxes",
        ]
        msg_text = (message.content or "").strip()
        embed_text = ""
        if message.embeds:
            embed_text = (message.embeds[0].description or "").strip()

        if any(err in msg_text for err in error_texts) or any(err in embed_text for err in error_texts):
            print(f"⚠️ Skipping cooldown for {canonical} because Mazoku said: {msg_text or embed_text}", flush=True)
            return

        # cooldown check
        now = time.time()
        key = (user.id, canonical)
        end = cooldowns.get(key, 0)

        if end > now:
            remaining = int(end - now)
            try:
                await user.send(f"⏳ You're still on cooldown for **{canonical}** ({remaining}s left).")
            except discord.Forbidden:
                await message.channel.send(
                    f"⏳ {user.mention}, you're still on cooldown for **{canonical}** ({remaining}s left). (Couldn't DM you)"
                )
            return

        # start cooldown
        cd = COOLDOWN_SECONDS[canonical]
        cooldowns[key] = now + cd
        try:
            await user.send(f"⚡ Cooldown started for **{canonical}** — I'll remind you in {cd} seconds.")
        except discord.Forbidden:
            await message.channel.send(
                f"⚡ {user.mention}, cooldown started for **{canonical}** — I'll remind you in {cd} seconds. (Couldn't DM you)"
            )

        # reminder later
        await asyncio.sleep(cd)
        if cooldowns.get(key, 0) <= time.time():
            cooldowns.pop(key, None)
            try:
                await user.send(f"✅ Your cooldown for **{canonical}** is over — you can use it again.")
            except discord.Forbidden:
                await message.channel.send(
                    f"✅ {user.mention}, cooldown for **{canonical}** is over! (Couldn't DM you.)"
                )


# Slash commands
@tree.command(name="setcooldown", description="Set a cooldown time for a command (seconds).")
async def set_cooldown(interaction: discord.Interaction, command: str, seconds: int):
    if seconds < 0:
        await interaction.response.send_message("❌ Cooldown must be >= 0.", ephemeral=True)
        return
    COOLDOWN_SECONDS[command] = seconds
    await interaction.response.send_message(f"✅ Cooldown for **{command}** updated to {seconds} seconds.", ephemeral=True)


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


if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN not set!", flush=True)
        raise SystemExit(1)
    print("🚀 Starting bot...", flush=True)
    client.run(TOKEN)
