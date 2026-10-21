import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import os
import datetime
import asyncio

# ================= CONFIG - TRINIUM =================
LAVALINK_URI = "https://nodelink.triniumhost.com:443"
LAVALINK_PASS = "free"
LAVALINK_ID = "trinium"
DEFAULT_PREFIX = "!"

COLORS = {"main": 0xFF0080, "success": 0x00FF88, "error": 0xFF0040, "queue": 0x8A2BE2, "filter": 0x00FFFF}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=DEFAULT_PREFIX, intents=intents, help_command=None)

twenty_four_seven = set()
loop_mode = {}

def embed(title, desc, color=COLORS["main"], thumb=None):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.datetime.now())
    if thumb: e.set_thumbnail(url=thumb)
    e.set_footer(text=f"✨ {LAVALINK_ID} • Aesthetic • 247")
    return e

@bot.event
async def on_ready():
    print(f"Bot {bot.user} Ready | Lavalink {LAVALINK_ID} Ready")
    nodes = [wavelink.Node(uri=LAVALINK_URI, password=LAVALINK_PASS, identifier=LAVALINK_ID)]
    await wavelink.Pool.connect(nodes=nodes, client=bot, cache_capacity=100)
    await bot.tree.sync()

@bot.event
async def on_wavelink_node_ready(payload): 
    print(f"Lavalink {payload.node.identifier} Ready! | {payload.node.uri}")

@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    player = payload.player
    track = payload.track
    if not player.home: return
    em = discord.Embed(title="🎧 Now Playing", description=f"**[{track.title}]({track.uri})**\n`{track.author}`", color=COLORS["main"])
    if track.artwork: em.set_thumbnail(url=track.artwork)
    await player.home.send(embed=em)

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if player.queue:
        await player.play(player.queue.get())
    else:
        if player.guild.id not in twenty_four_seven:
            await asyncio.sleep(60)
            if not player.playing:
                await player.disconnect()

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and after.channel is None:
        if before.channel and before.channel.guild.id in twenty_four_seven:
            await asyncio.sleep(2)
            try:
                await before.channel.connect(cls=wavelink.Player)
            except: pass

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
    search_em = embed("🔍 Searching...", f"`{query}`...", COLORS["queue"])
    if is_slash:
        msg = await interaction_or_ctx.followup.send(embed=search_em)
    else:
        msg = await channel.send(embed=search_em)
    tracks = await wavelink.Playable.search(query)
    if not tracks:
        return await msg.edit(embed=embed("😔 Nahi Mila", f"`{query}` nahi mila", COLORS["error"]))
    if isinstance(tracks, wavelink.Playlist):
        for i, t in enumerate(tracks.tracks):
            if i == 0 and not player.playing:
                await player.play(t)
            else:
                player.queue.put(t)
        return await msg.edit(embed=embed("📜 Playlist Added", f"{len(tracks.tracks)} gaane", COLORS["queue"]))
    else:
        track = tracks[0]
        if player.playing:
            player.queue.put(track)
            await msg.edit(embed=embed("📜 Queued", f"**{track.title}**", COLORS["queue"]))
        else:
            await player.play(track)
            await msg.delete()

@bot.hybrid_command(name="play", description="🎶 Gaana bajao")
async def play(ctx, *, query: str):
    if ctx.interaction: await ctx.defer()
    await do_play(ctx.interaction if ctx.interaction else ctx, query, is_slash=ctx.interaction is not None)

@bot.hybrid_command(name="247", description="🔒 24/7 ON/OFF")
async def cmd_247(ctx):
    gid = ctx.guild.id
    if gid in twenty_four_seven:
        twenty_four_seven.remove(gid)
        em = embed("🔓 247 OFF", "Nikal jaunga", COLORS["error"])
    else:
        twenty_four_seven.add(gid)
        em = embed("🔒 247 ON", "VC me hi rahunga!", COLORS["success"])
    await ctx.send(embed=em) if not ctx.interaction else await ctx.interaction.response.send_message(embed=em)

@bot.hybrid_command(name="stop", description="👋 Stop")
async def stop(ctx):
    p = ctx.guild.voice_client
    if p: await p.disconnect()
    await ctx.send(embed=embed("👋 Bye", "Nikal gaya", COLORS["main"]))

bot.run(os.environ.get("DISCORD_TOKEN"))
