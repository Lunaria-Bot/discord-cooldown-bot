import discord
import os
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")
MAZOKU_BOT_ID = 1242388858897956906  # Mazoku bot's ID
COOLDOWN_SECONDS = 60  # adjust as needed

# Enable all intents for debugging
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} ({client.user.id})")

@client.event
async def on_message(message: discord.Message):
    # Ignore self
    if message.author.id == client.user.id:
        return

    # Only log Mazoku messages for now
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        print("=== New Message from Mazoku ===")
        print(f"Author: {message.author} ({message.author.id})")
        print(f"Content: {repr(message.content)}")
        print(f"Embeds: {len(message.embeds)}")
        for i, embed in enumerate(message.embeds):
            print(f"Embed {i} title: {embed.title}")
            print(f"Embed {i} description: {embed.description}")
            print(f"Embed {i} fields: {embed.fields}")
        print(f"Components: {message.components}")
        print(f"Attachments: {message.attachments}")
        print(f"Interaction: {message.interaction}")
        try:
            raw_data = message.to_dict()
            print(f"Raw data keys: {list(raw_data.keys())}")
            print(f"Raw data: {raw_data}")
        except Exception as e:
            print(f"Could not dump raw data: {e}")
        print("===============================")

client.run(TOKEN)
