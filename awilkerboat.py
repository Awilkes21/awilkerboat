import discord
from discord.ext import commands
import asyncio
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import os

intents = discord.Intents.default()
intents.messages = True  # Enable the intent to read messages
intents.message_content = True  # Enable the privileged message content intent
bot = commands.Bot(command_prefix="!", intents=intents)  # Command prefix is unused but required for the Bot instance

queue = []
current_voice = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()

@bot.tree.command(name="join", description="Make the bot join your voice channel")
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

@bot.tree.command(name="leave", description="Make the bot leave the voice channel.")
async def leave(interaction: discord.Interaction):
    global current_voice
    if current_voice is not None:
        await current_voice.disconnect()
        current_voice = None
        await interaction.response.send_message("Disconnected from the voice channel.")
    else:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

@bot.tree.command(name="add", description="Add a YouTube video to the queue.")
async def add_to_queue(interaction: discord.Interaction, url: str):
    queue.append(url)
    await interaction.response.send_message(f"Added to queue: {url}")

@bot.tree.command(name="play", description="Play tracks from the queue.")
async def play(interaction: discord.Interaction):
    global current_voice
    if current_voice is None:
        await interaction.response.send_message("I'm not in a voice channel. Use /join first.")
        return

    if not queue:
        await interaction.response.send_message("Queue is empty!")
        return

    await interaction.response.send_message("Starting playback...")  # Send the response once at the beginning

    while queue:
        url = queue.pop(0)
        channel = interaction.channel
        await channel.send(f"Now playing: {url}")

        try:
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

        except youtube_dl.DownloadError as e:
            # Send the error message without trying to respond again
            await channel.send(f"Failed to fetch the video: {str(e)}")
            continue  # Skip to the next video in the queue

    await channel.send("Queue is empty!")

@bot.tree.command(name="skip", description="Skip the current track.")
async def skip(interaction: discord.Interaction):
    global current_voice
    if current_voice and current_voice.is_playing():
        current_voice.stop()
        await interaction.response.send_message("Skipped the current track.")
    else:
        await interaction.response.send_message("No track is playing to skip.", ephemeral=True)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
