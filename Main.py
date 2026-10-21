import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import os
import datetime
import asyncio

# ================= CONFIG =================
LAVALINK_URI = "http://fi14.bot-hosting.cloud:25209"
LAVALINK_PASS = "glaceyt"
LAVALINK_ID = "fi14"
DEFAULT_PREFIX = "!"

COLORS = {"main": 0xFF0080, "success": 0x00FF88, "error": 0xFF0040, "queue": 0x8A2BE2, "filter": 0x00FFFF}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=intents, help_command=None)

# 247 Storage
twenty_four_seven = set()
loop_mode = {} # guild_id: "off" / "track" / "queue"

def embed(title, desc, color=COLORS["main"], thumb=None):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.now())
    if thumb: e.set_thumbnail(url=thumb)
    e.set_footer(text=f"✨ {LAVALINK_ID} • Aesthetic • 247")
    return e

@bot.event
async def on_ready():
    print(f"Bot {bot.user} Ready | Lavalink fi14 Ready")
    nodes = [wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASS, identifier=LAVALINK_ID)]
    await wavelink.Pool.connect(nodes=nodes, client=bot, cache_capacity=100)
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/play | !help 🎧"))

@bot.event
async def on_wavelink_node_ready(payload): print(f"Lavalink Ready!")

@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    track = payload.track
    if not player.home: return
    em = discord.Embed(title="🎧 Now Playing", description=f"**[{track.title}]({track.uri})**\n`{track.author}`", color=COLORS["main"])
    if track.artwork: em.set_thumbnail(url=track.artwork)
    mode = loop_mode.get(player.guild.id, "off")
    em.set_footer(text=f"🔁 Loop: {mode} | Vol: {player.volume}% | 247: {'ON' if player.guild.id in twenty_four_seven else 'OFF'}")
    await player.home.send(embed=em)

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    guild_id = player.guild.id
    mode = loop_mode.get(guild_id, "off")
    
    if mode == "track" and payload.track:
        await player.play(payload.track)
    elif mode == "queue" and payload.track:
        player.queue.put(payload.track)
        if player.queue:
            await player.play(player.queue.get())
    else: # off
        if player.queue:
            await player.play(player.queue.get())
        else:
            # 247 check
            if guild_id not in twenty_four_seven:
                await asyncio.sleep(60)
                if not player.playing and not player.queue:
                    await player.disconnect()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        if before.channel and before.channel.guild.id in twenty_four_seven:
            await asyncio.sleep(2)
            try:
                await before.channel.connect(cls=wavelink.Player)
            except: pass

# ================= SHARED PLAY LOGIC =================
async def do_play(interaction_or_ctx, query: str, is_slash=False):
    user = interaction_or_ctx.user if is_slash else interaction_or_ctx.author
    guild = interaction_or_ctx.guild
    channel = interaction_or_ctx.channel
    
    if not user.voice:
        err = embed("🔇 VC Join Kar", "Pehle VC join kar!", COLORS["error"])
        if is_slash: return await interaction_or_ctx.followup.send(embed=err, ephemeral=True)
        else: return await channel.send(embed=err)
    
    if not guild.voice_client:
        await user.voice.channel.connect(cls=wavelink.Player)
    
    player: wavelink.Player = guild.voice_client
    player.home = channel

    # Spotify Detection
    is_spotify = "spotify.com" in query
    search_msg = f"🎵 Spotify link detect kiya! Spotify se la raha hu..." if is_spotify else f"🔍 `{query}` dhoondh raha hu..."
    search_em = embed("🔍 Searching...", search_msg, COLORS["queue"])
    
    if is_slash:
        msg = await interaction_or_ctx.followup.send(embed=search_em)
    else:
        msg = await channel.send(embed=search_em)

    # Wavelink handles Spotify links automatically if Lavalink has plugin
    tracks = await wavelink.Playable.search(query)
    
    if not tracks:
        return await msg.edit(embed=embed("😔 Nahi Mila", f"`{query}` nahi mila", COLORS["error"]))
    
    # If Spotify playlist / album
    if isinstance(tracks, wavelink.Playlist):
        # Playlist
        added = 0
        for t in tracks.tracks:
            t.requester = user
            if player.playing:
                player.queue.put(t)
            else:
                if added == 0:
                    await player.play(t)
                else:
                    player.queue.put(t)
            added += 1
        em = embed("📜 Spotify Playlist Added", f"**{tracks.name}**\n`{len(tracks.tracks)}` gaane add kiye! 🎶", COLORS["queue"], thumb=tracks.artwork if hasattr(tracks, 'artwork') else None)
        return await msg.edit(embed=em)
    else:
        track = tracks[0]
        track.requester = user
        if player.playing:
            player.queue.put(track)
            em = embed("📜 Queued", f"**{track.title}**\n`{track.author}`\nPos: #{len(player.queue)}", COLORS["queue"], thumb=track.artwork)
            await msg.edit(embed=em)
        else:
            await player.play(track)
            await msg.delete()

# ================= COMMANDS =================

@bot.hybrid_command(name="play", description="🎶 Gaana/Spotify link bajao")
@app_commands.describe(query="Naam, YT link ya Spotify link")
async def play(ctx, *, query: str):
    if ctx.interaction: await ctx.defer()
    await do_play(ctx.interaction if ctx.interaction else ctx, query, is_slash=ctx.interaction is not None)

@bot.hybrid_command(name="spotify", description="💚 Spotify link bajao")
@app_commands.describe(link="Spotify song/playlist/album link")
async def spotify_cmd(ctx, link: str):
    if ctx.interaction: await ctx.defer()
    await do_play(ctx.interaction if ctx.interaction else ctx, link, is_slash=ctx.interaction is not None)

@bot.hybrid_command(name="247", description="🔒 24/7 mode ON/OFF - Bot VC me rahega")
async def cmd_247(ctx):
    guild_id = ctx.guild.id
    player = ctx.guild.voice_client
    if not player:
        return await ctx.send(embed=embed("❌ VC me nahi hu", "Pehle `play` se VC join karao", COLORS["error"]))
    
    if guild_id in twenty_four_seven:
        twenty_four_seven.remove(guild_id)
        em = embed("🔓 247 OFF", "Ab gaana khatam hone ke 1 min baad nikal jaunga", COLORS["error"])
    else:
        twenty_four_seven.add(guild_id)
        em = embed("🔒 247 ON • 24/7 Mode", "Ab main VC me hi rahunga, kabhi nahi nikalunga! 🛡️\nAuto-reconnect ON", COLORS["success"])
    
    await ctx.send(embed=em) if not ctx.interaction else await ctx.interaction.response.send_message(embed=em)

@bot.hybrid_command(name="loop", description="🔁 Loop mode set karo")
@app_commands.describe(mode="off / track / queue")
@app_commands.choices(mode=[
    app_commands.Choice(name="Off - Band karo", value="off"),
    app_commands.Choice(name="Track - Ek hi gaana repeat", value="track"),
    app_commands.Choice(name="Queue - Saari queue repeat", value="queue"),
])
async def loop_cmd(ctx, mode: str):
    if mode not in ["off", "track", "queue"]:
        return await ctx.send(embed=embed("❌ Invalid", "Mode: `off`, `track`, `queue`", COLORS["error"]))
    
    loop_mode[ctx.guild.id] = mode
    emoji = {"off": "❌", "track": "🔂", "queue": "🔁"}
    em = embed(f"{emoji[mode]} Loop {mode.capitalize()}", f"Loop mode set to **{mode}** {emoji[mode]}", COLORS["main"])
    await ctx.send(embed=em) if not ctx.interaction else await ctx.interaction.response.send_message(embed=em)

# ---- FILTERS ----
def get_filter(name: str):
    f = wavelink.Filters()
    if name == "bassboost":
        f.equalizer.set(bands=[{"band":0,"gain":0.6},{"band":1,"gain":0.7},{"band":2,"gain":0.8}])
    elif name == "nightcore":
        f.timescale.set(speed=1.2, pitch=1.2)
    elif name == "vaporwave":
        f.timescale.set(speed=0.8, pitch=0.8)
    elif name == "8d":
        f.rotation.set(rotation_hz=0.2)
    elif name == "karaoke":
        f.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
    elif name == "chipmunk":
        f.timescale.set(speed=1.5, pitch=1.5)
    elif name == "slowmo":
        f.timescale.set(speed=0.5, pitch=1.0, rate=0.8)
    elif name == "daycore":
        f.timescale.set(speed=0.8, pitch=0.8, rate=0.8)
    elif name == "tremolo":
        f.tremolo.set(depth=0.5, frequency=14.0)
    elif name == "vibrato":
        f.vibrato.set(depth=0.5, frequency=14.0)
    elif name == "distortion":
        f.distortion.set(sin_offset=0, sin_scale=1, cos_offset=0, cos_scale=1, tan_offset=0, tan_scale=1, offset=0, scale=1)
    elif name == "lowpass":
        f.low_pass.set(smoothing=20.0)
    return f

@bot.hybrid_command(name="filter", description="🎛️ Music filters lagao")
@app_commands.describe(filter_name="Kaunsa filter")
@app_commands.choices(filter_name=[
    app_commands.Choice(name="Bassboost - Bass tez", value="bassboost"),
    app_commands.Choice(name="Nightcore - Fast + High", value="nightcore"),
    app_commands.Choice(name="Vaporwave - Slow + Low", value="vaporwave"),
    app_commands.Choice(name="8D - 8D Audio", value="8d"),
    app_commands.Choice(name="Karaoke - Vocals hatao", value="karaoke"),
    app_commands.Choice(name="Chipmunk - Chipmunk voice", value="chipmunk"),
    app_commands.Choice(name="Slowmo - Slow motion", value="slowmo"),
    app_commands.Choice(name="Daycore - Daycore effect", value="daycore"),
    app_commands.Choice(name="Tremolo - Tremolo", value="tremolo"),
    app_commands.Choice(name="Vibrato - Vibrato", value="vibrato"),
    app_commands.Choice(name="Lowpass - Lowpass", value="lowpass"),
    app_commands.Choice(name="Distortion - Distortion", value="distortion"),
])
async def filter_cmd(ctx, filter_name: str):
    player: wavelink.Player = ctx.guild.voice_client
    if not player or not player.playing:
        return await ctx.send(embed=embed("❌", "Pehle gaana bajao!", COLORS["error"]), ephemeral=True) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("❌", "Pehle gaana bajao!", COLORS["error"]), ephemeral=True)
    
    f = get_filter(filter_name)
    await player.set_filters(f)
    em = embed(f"🎛️ Filter: {filter_name.capitalize()}", f"Filter **{filter_name}** laga diya! 🎶\n`/filterclear` se hata sakta hai", COLORS["filter"])
    await ctx.send(embed=em) if not ctx.interaction else await ctx.interaction.response.send_message(embed=em)

@bot.hybrid_command(name="filterclear", description="✨ Saare filters hatao")
async def filterclear(ctx):
    player: wavelink.Player = ctx.guild.voice_client
    if player:
        await player.set_filters(wavelink.Filters())
        em = embed("✨ Filters Cleared", "Normal ho gaya! 🎧", COLORS["success"])
        await ctx.send(embed=em) if not ctx.interaction else await ctx.interaction.response.send_message(embed=em)

# ---- BASIC ----
@bot.hybrid_command(name="pause", description="⏸️ Roko") 
async def pause(ctx):
    p = ctx.guild.voice_client
    if p and p.playing: await p.pause(True); await ctx.send(embed=embed("⏸️ Paused", "Rok diya!", 0xFFAA00)) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("⏸️ Paused", "Rok diya!", 0xFFAA00))

@bot.hybrid_command(name="resume", description="▶️ Chalu")
async def resume(ctx):
    p = ctx.guild.voice_client
    if p and p.paused: await p.pause(False); await ctx.send(embed=embed("▶️ Resumed", "Chalu!", 0x00FF00)) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("▶️ Resumed", "Chalu!", 0x00FF00))

@bot.hybrid_command(name="skip", description="⏭️ Skip") 
async def skip(ctx):
    p = ctx.guild.voice_client
    if p: await p.skip(); await ctx.send(embed=embed("⏭️ Skipped", "Next!", 0x00AAFF)) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("⏭️ Skipped", "Next!", 0x00AAFF))

@bot.hybrid_command(name="stop", description="👋 Stop")
async def stop(ctx):
    p = ctx.guild.voice_client
    if p: 
        gid = ctx.guild.id
        if gid in twenty_four_seven: twenty_four_seven.remove(gid)
        if gid in loop_mode: loop_mode.pop(gid)
        p.queue.clear(); await p.disconnect()
        await ctx.send(embed=embed("👋 Bye", "Nikal gaya!", COLORS["main"])) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("👋 Bye", "Nikal gaya!", COLORS["main"]))

@bot.hybrid_command(name="queue", description="📜 Queue")
async def queue(ctx):
    p = ctx.guild.voice_client
    if not p or not p.queue: return await ctx.send(embed=embed("📭 Empty", "Khali hai", COLORS["queue"])) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("📭 Empty", "Khali hai", COLORS["queue"]))
    desc = "\n".join([f"`{i}.` {t.title[:40]}" for i,t in enumerate(list(p.queue)[:10],1)])
    await ctx.send(embed=embed(f"Queue {len(p.queue)}", desc, COLORS["queue"])) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed(f"Queue {len(p.queue)}", desc, COLORS["queue"]))

@bot.hybrid_command(name="volume", description="🔊 Volume")
async def volume(ctx, level: int):
    p = ctx.guild.voice_client
    if p: await p.set_volume(level); await ctx.send(embed=embed("🔊 Vol", f"{level}%", COLORS["success"])) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("🔊 Vol", f"{level}%", COLORS["success"]))

@bot.hybrid_command(name="help", description="✨ Help")
async def help_cmd(ctx):
    desc = f"""
    **🎵 Play**
    `/play` `!play <song/link>` - YT/Spotify
    `/spotify <link>` - Spotify direct 💚
    
    **🔒 247 & Loop**
    `/247` - 24/7 VC me rahega 🔒
    `/loop <off/track/queue>` - Loop 🔁
    
    **🎛️ Filters (12)**
    `/filter <name>` - nightcore, vaporwave, 8d, bassboost, karaoke, chipmunk, slowmo, daycore, tremolo, vibrato, lowpass, distortion
    `/filterclear` - Clear ✨
    
    **📜 Controls**
    `/pause /resume /skip /stop /queue /volume /clear /shuffle`
    
    **Spotify + 247 + Filters = Pro Bot**
    """
    await ctx.send(embed=embed("✨ Help Menu", desc, COLORS["main"])) if not ctx.interaction else await ctx.interaction.response.send_message(embed=embed("✨ Help Menu", desc, COLORS["main"]))

bot.run(os.environ.get("DISCORD_TOKEN"))
