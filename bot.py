import discord
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
MAZOKU_BOT_ID = 1429838858897596960  # Replace with Mazoku's bot ID
COOLDOWN_SECONDS = 60  # 60-second cooldown

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

# Store cooldowns per user
cooldowns = {}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    # Ignore self
    if message.author.id == client.user.id:
        return

    # Only check messages from the Mazoku bot
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        print("------ Mazoku Message Debug ------")
        print(f"Content: {message.content}")
        print(f"Embeds: {len(message.embeds)}")
        for i, embed in enumerate(message.embeds):
            print(f"Embed {i} title: {embed.title}")
            print(f"Embed {i} description: {embed.description}")
            print(f"Embed {i} fields: {embed.fields}")
        print("----------------------------------")

        # Look for "Refreshing Box Opened" either in content or embed
        if "Refreshing Box Opened" in message.content:
            await handle_cooldown(message)
        else:
            for embed in message.embeds:
                if embed.title and "Refreshing Box Opened" in embed.title:
                    await handle_cooldown(message)

async def handle_cooldown(message: discord.Message):
    user = None

    # Try to detect who opened the box
    if message.mentions:
        user = message.mentions[0]
    else:
        user = message.author  # fallback

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
