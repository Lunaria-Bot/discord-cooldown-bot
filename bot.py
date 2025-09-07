import discord
import asyncio
import os
import time

TOKEN = os.getenv("DISCORD_TOKEN")

COOLDOWN_SECONDS = 60
OTHER_BOT_ID = 142938885889795696  # Mazoku bot ID

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for DMs

client = discord.Client(intents=intents)

# Track cooldowns: user_id -> timestamp
cooldowns = {}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return  # ignore itself

    if message.author.id == OTHER_BOT_ID:
        # Look for "Refreshing Box Opened" in Mazoku's embed
        if message.embeds and "Refreshing Box Opened" in message.embeds[0].title:
            embed = message.embeds[0]

            claimed_by = None
            if embed.description and "Claimed By" in embed.description:
                for user in message.mentions:
                    if user.mention in embed.description:
                        claimed_by = user
                        break

            if claimed_by:
                now = time.time()
                cooldown_end = cooldowns.get(claimed_by.id, 0)

                if now < cooldown_end:
                    # Still on cooldown
                    remaining = int(cooldown_end - now)
                    try:
                        await claimed_by.send(
                            f"⚠️ You’re still on cooldown for {remaining} seconds!"
                        )
                    except discord.Forbidden:
                        await message.channel.send(
                            f"⚠️ {claimed_by.mention}, I couldn’t DM you. Please enable DMs."
                        )
                else:
                    # Start cooldown
                    cooldowns[claimed_by.id] = now + COOLDOWN_SECONDS
                    try:
                        await claimed_by.send(
                            f"⏳ Cooldown started! I’ll remind you in {COOLDOWN_SECONDS} seconds."
                        )
                    except discord.Forbidden:
                        await message.channel.send(
                            f"⚠️ {claimed_by.mention}, I couldn’t DM you. Please enable DMs."
                        )

                    await asyncio.sleep(COOLDOWN_SECONDS)

                    try:
                        await claimed_by.send(
                            f"✅ Cooldown is over! You can open a box again."
                        )
                    except discord.Forbidden:
                        await message.channel.send(
                            f"✅ {claimed_by.mention}, cooldown is over (DMs blocked)."
                        )

