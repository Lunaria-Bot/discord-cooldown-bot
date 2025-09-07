@client.event
async def on_message(message: discord.Message):
    if message.author.id == client.user.id:
        return

    # only care about Mazoku bot
    if message.author.bot and message.author.id == MAZOKU_BOT_ID:
        inter = get_interaction_from_message(message)
        cmd_name = None
        user = None

        if inter:
            cmd_name = getattr(inter, "name", None)
            user = getattr(inter, "user", None)
        else:
            # fallback: check embed titles
            if message.embeds:
                title = message.embeds[0].title or ""
                cmd_name = title
                if message.mentions:
                    user = message.mentions[0]

        if not cmd_name or not user:
            return

        # resolve canonical command
        canonical = ALIASES.get(cmd_name)
        if not canonical or canonical not in COOLDOWN_SECONDS:
            return

        # --- 🛑 check for failure / skip cases ---
        error_texts = [
            "No boxes available to open",
            "You don’t have any boxes",  # (add other Mazoku fail lines if needed)
        ]

        msg_text = (message.content or "").strip()
        embed_text = ""
        if message.embeds:
            embed = message.embeds[0]
            embed_text = (embed.description or "").strip()

        if any(err in msg_text for err in error_texts) or any(err in embed_text for err in error_texts):
            print(f"⚠️ Skipping cooldown for {canonical} because Mazoku said: {msg_text or embed_text}", flush=True)
            return
        # ----------------------------------------

        now = time.time()
        key = (user.id, canonical)
        end = cooldowns.get(key, 0)

        if end > now:
            remaining = int(end - now)
            try:
                await user.send(f"⏳ You're still on cooldown for **{canonical}** ({remaining}s left).")
            except discord.Forbidden:
                try:
                    await message.channel.send(f"⏳ {user.mention}, you're still on cooldown for **{canonical}** ({remaining}s left). (Couldn't DM you)")
                except Exception:
                    pass
            return

        # start cooldown
        cd = COOLDOWN_SECONDS[canonical]
        cooldowns[key] = now + cd
        try:
            await user.send(f"⚡ Cooldown started for **{canonical}** — I'll remind you in {cd} seconds.")
        except discord.Forbidden:
            try:
                await message.channel.send(f"⚡ {user.mention}, cooldown started for **{canonical}** — I'll remind you in {cd} seconds. (Couldn't DM you)")
            except Exception:
                pass

        # reminder later
        await asyncio.sleep(cd)
        if cooldowns.get(key, 0) <= time.time():
            cooldowns.pop(key, None)
            try:
                await user.send(f"✅ Your cooldown for **{canonical}** is over — you can use it again.")
            except discord.Forbidden:
                try:
                    await message.channel.send(f"✅ {user.mention}, cooldown for **{canonical}** is over! (Couldn't DM you.)")
                except Exception:
                    pass
