import discord
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
MAZOKU_BOT_ID = 1242388858897956906  # Mazoku bot's ID
COOLDOWN_SECONDS = 60  # adjust cooldown length

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

# Track cooldowns by user ID
cooldowns = {}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user} ({client.user.id})")

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    # Only listen to Mazoku
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        if message.interaction and message.interaction.name == "open-boxes":
            user = message.interaction.user
            print(f"🎯 Detected /open-boxes by {user} ({user.id})")

            if user.id in cooldowns:
                await message.channel.send(
                    f"⏳ {user.mention}, you are still on cooldown! Please wait."
                )
                return

            cooldowns[user.id] = True
            await message.channel.send(
                f"⚡ {user.mention}, cooldown started! I'll remind you in {COOLDOWN_SECONDS} seconds."
            )

            await asyncio.sleep(COOLDOWN_SECONDS)
            del cooldowns[user.id]

            await message.channel.send(
                f"✅ {user.mention}, cooldown is over! You can open the box again."
            )

client.run(TOKEN)
