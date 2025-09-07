import discord
import asyncio
import os

TOKEN = os.getenv("DISCORD_TOKEN")
OTHER_BOT_ID = 123456789012345678  # <-- Replace with Mazoku bot's real ID
COOLDOWN_SECONDS = 60

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)

cooldowns = {}

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return  # ignore self

    # Debug print
    print(f"📩 Message from {message.author}: {message.content} | Embeds: {len(message.embeds)}")

    # Only react to Mazoku bot
    if message.author.id == OTHER_BOT_ID:
        if message.embeds:
            embed = message.embeds[0]
            if embed.title and "Refreshing Box Opened" in embed.title:
                claimed_by = None
                if embed.description and "Claimed By" in embed.description:
                    parts = embed.description.split()
                    if len(parts) >= 3:
                        claimed_by = parts[2]

                if claimed_by:
                    print(f"🎯 Detected box opened by {claimed_by}")

                    if claimed_by not in cooldowns:
                        cooldowns[claimed_by] = True
                        try:
                            await message.channel.send(
                                f"⏳ {claimed_by}, cooldown started! I'll remind you in {COOLDOWN_SECONDS} seconds."
                            )
                            await asyncio.sleep(COOLDOWN_SECONDS)
                            await message.channel.send(
                                f"✅ {claimed_by}, cooldown is over! You can open the box again."
                            )
                        finally:
                            cooldowns.pop(claimed_by, None)
if __name__ == "__main__":
    try:
        print("🚀 Starting bot...", flush=True)
        client.run(TOKEN)
    except Exception as e:
        print(f"❌ Failed to start bot: {e}", flush=True)
