import discord
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
OTHER_BOT_ID = 1242388858897956906  # 👈 Replace with the ID of the other bot
COOLDOWN_SECONDS = 60  # 50-second cooldown

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.bot and message.author.id == OTHER_BOT_ID:
        if "Refreshing Box Opened" in message.content:
            await message.channel.send(
                f"⏳ Cooldown started! I’ll remind you in {COOLDOWN_SECONDS} seconds."
            )
            await asyncio.sleep(COOLDOWN_SECONDS)
            await message.channel.send(
                f"⏰ Cooldown is over! You can open the box again."
            )

client.run(TOKEN)
