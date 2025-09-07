import discord
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
MAZOKU_BOT_ID = 1429838858897596960  # Mazoku bot ID
COOLDOWN_SECONDS = 60  # 60-second cooldown

# Enable all intents
intents = discord.Intents.all()
client = discord.Client(intents=intents)

cooldowns = {}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    # Debug log everything the bot sees
    print(f"[DEBUG] From {message.author} ({message.author.id})")
    print(f"Content: {message.content}")
    print(f"Embeds: {len(message.embeds)}")

    # Ignore self
    if message.author.id == client.user.id:
        return

    # Only watch Mazoku’s messages
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        for i, embed in enumerate(message.embeds):
            print(f"Embed {i} -> title: {embed.title}, desc: {embed.description}, fields: {embed.fields}")

        # Trigger when "Refreshing Box Opened" appears
        if "Refreshing Box Opened" in message.content:
            await handle_cooldown(message)
        else:
            for embed in message.embeds:
                if embed.title and "Refreshing Box Opened" in embed.title:
                    await handle_cooldown(message)

async def handle_cooldown(message: discord.Message):
    user = message.author  # fallback

    if message.mentions:
        user = message.mentions[0]

    if user.id in cooldowns:
        await message.channel.send(
            f"⏳ {user.mention}, you’re already on cooldown! Please wait."
        )
        return

    await message.channel.send(
        f"⚡ {user.mention}, cooldown started! I'll remind you in {COOLDOWN_SECONDS} seconds."
    )

    cooldowns[user.id] = True
    await asyncio.sleep(COOLDOWN_SECONDS)
    del cooldowns[user.id]

    await message.channel.send(f"✅ {user.mention}, cooldown is over! You can open the box again.")

client.run(TOKEN)
