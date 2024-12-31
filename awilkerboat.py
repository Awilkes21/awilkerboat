import discord
from discord.ext import commands
import asyncio
import youtube_dl

intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)  # Command prefix is unused but required for the Bot instance

queue = []
current_voice = None

guild_tree = discord.app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await guild_tree.sync()

@guild_tree.command(name="join", description="Make the bot join your voice channel.")
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        global current_voice
        if current_voice is not None:
            await current_voice.disconnect()
        current_voice = await channel.connect()
        await interaction.response.send_message(f"Joined {channel}")
    else:
        await interaction.response.send_message("You need to join a voice channel first!", ephemeral=True)

@guild_tree.command(name="leave", description="Make the bot leave the voice channel.")
async def leave(interaction: discord.Interaction):
    global current_voice
    if current_voice is not None:
        await current_voice.disconnect()
        current_voice = None
        await interaction.response.send_message("Disconnected from the voice channel.")
    else:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

@guild_tree.command(name="add", description="Add a YouTube video to the queue.")
async def add_to_queue(interaction: discord.Interaction, url: str):
    queue.append(url)
    await interaction.response.send_message(f"Added to queue: {url}")

@guild_tree.command(name="play", description="Play tracks from the queue.")
async def play(interaction: discord.Interaction):
    global current_voice
    if current_voice is None:
        await interaction.response.send_message("I'm not in a voice channel. Use /join first.")
        return

    if not queue:
        await interaction.response.send_message("Queue is empty!")
        return

    await interaction.response.send_message("Starting playback...")

    while queue:
        url = queue.pop(0)
        channel = interaction.channel
        await channel.send(f"Now playing: {url}")

        with youtube_dl.YoutubeDL({'format': 'bestaudio', 'noplaylist': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']

        def after_playing(error):
            if error:
                print(f"Error: {error}")

        current_voice.play(discord.FFmpegPCMAudio(audio_url), after=after_playing)
        current_voice.source = discord.PCMVolumeTransformer(current_voice.source, volume=0.5)

        while current_voice.is_playing():
            await asyncio.sleep(1)

    await channel.send("Queue is empty!")

@guild_tree.command(name="skip", description="Skip the current track.")
async def skip(interaction: discord.Interaction):
    global current_voice
    if current_voice and current_voice.is_playing():
        current_voice.stop()
        await interaction.response.send_message("Skipped the current track.")
    else:
        await interaction.response.send_message("No track is playing to skip.", ephemeral=True)

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
bot.run(TOKEN)
