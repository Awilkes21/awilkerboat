import discord
import signal
from discord.ext import commands
import asyncio
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import os
import logging
from discord.ui import Button, View
import random

# Set up logging
logging.basicConfig(
    filename='awilkerboat.log',  # Log file location
    level=logging.INFO,  # Log level (INFO, DEBUG, ERROR, etc.)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    filemode='w',
)

logging.info("\n\n" + "="*50)
logging.info("Bot session started")

intents = discord.Intents.default()
intents.messages = True  # Enable the intent to read messages
intents.message_content = True  # Enable the privileged message content intent
bot = commands.Bot(command_prefix="!", intents=intents)  # Command prefix is unused but required for the Bot instance

guild_queues = {}
guild_current_voice = {}    
guild_pages = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()

# Handle shutdown
@bot.event
async def on_shutdown():
    logging.info("Bot is shutting down. Clearing queues...")
    # Clear all queues
    guild_queues.clear()
    logging.info("All queues have been cleared.")

@bot.tree.command(name="join", description="Make the bot join your voice channel")
async def join(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if guild_id in guild_current_voice and guild_current_voice[guild_id] is not None:
            await guild_current_voice[guild_id].disconnect()
        guild_current_voice[guild_id] = await channel.connect()
        logging.info(f"Bot joined voice channel {channel} in guild {interaction.guild.name}")
        await interaction.response.send_message(f"Joined {channel}")
    else:
        await interaction.response.send_message("You need to join a voice channel first!", ephemeral=True)

@bot.tree.command(name="leave", description="Make the bot leave the voice channel and clear the queue.")
async def leave(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_current_voice and guild_current_voice[guild_id] is not None:
        await guild_current_voice[guild_id].disconnect()
        guild_current_voice[guild_id] = None
        logging.info(f"Bot left the voice channel in guild {interaction.guild.name}")

        # Clear the queue for the guild
        if guild_id in guild_queues:
            guild_queues[guild_id].clear()
            logging.info(f"Queue cleared for guild {interaction.guild.name}")

        await interaction.response.send_message("Disconnected from the voice channel and cleared the queue.")
    else:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)


@bot.tree.command(name="add", description="Add a YouTube video or playlist to the queue.")
async def add_to_queue(interaction: discord.Interaction, url: str):
    await interaction.response.defer(ephemeral=True)  # Acknowledge the interaction quickly

    guild_id = interaction.guild.id
    
    # Check if the guild has a queue, otherwise create an empty one
    if guild_id not in guild_queues:
        guild_queues[guild_id] = []
    
    # Check if the URL is a playlist or a single video
    if "playlist" in url:
        # Extract the playlist using yt_dlp
        with youtube_dl.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
            try:
                playlist_info = ydl.extract_info(url, download=False)
                # If the URL is a valid playlist
                if 'entries' in playlist_info:
                    for entry in playlist_info['entries']:
                        video_url = entry['url']
                        guild_queues[guild_id].append(video_url)
                    await interaction.followup.send(f"Added {len(playlist_info['entries'])} videos from the playlist to the queue.")
                else:
                    await interaction.followup.send("Failed to extract videos from the playlist.", ephemeral=True)
            except youtube_dl.utils.DownloadError as e:
                await interaction.followup.send(f"Error adding playlist: {str(e)}", ephemeral=True)
                logging.error(f"Error adding playlist: {str(e)}")
    else:
        # Handle a single video URL
        try:
            with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
                video_info = ydl.extract_info(url, download=False)
                if 'entries' not in video_info:  # Check if the video info contains entries (playlist)
                    video_title = video_info.get('title', 'Unknown Title')
                    guild_queues[guild_id].append(url)
                    logging.info(f"Added video {video_title} to queue in guild {interaction.guild.name}")
                    await interaction.followup.send(f"Added to queue: {video_title}")
                else:
                    await interaction.followup.send(f"Error: Video is part of a playlist. Please provide a valid single video URL.", ephemeral=True)
        except youtube_dl.utils.DownloadError as e:
            await interaction.followup.send(f"Error adding video: {str(e)}", ephemeral=True)
            logging.error(f"Error adding video: {str(e)}")


@bot.tree.command(name="queue", description="View the current music queue.")
async def queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Check if the guild has a queue
    if guild_id not in guild_queues or not guild_queues[guild_id]:
        await interaction.response.send_message("The queue is empty.", ephemeral=True)
        return

    # Create an embed to display the queue in a card-like format
    embed = discord.Embed(title="Current Queue", description="Here are the videos in the queue:", color=discord.Color.blue())

    for i, song in enumerate(guild_queues[guild_id][:20], 1):  # Show the first 20 songs
        embed.add_field(name=f"Song {i}", value=song['title'], inline=False)

    # Add a footer with the total number of songs
    embed.set_footer(text=f"Total songs: {len(guild_queues[guild_id])}")

    # Send the message as an ephemeral message (visible only to the user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="play", description="Play tracks from the queue.")
async def play(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id not in guild_current_voice or guild_current_voice[guild_id] is None:
        await interaction.response.send_message("I'm not in a voice channel. Use /join first.")
        return

    if guild_id not in guild_queues or not guild_queues[guild_id]:
        await interaction.response.send_message("Queue is empty!")
        return

    await interaction.response.send_message("Starting playback...")  # Send the response once at the beginning

    while guild_queues[guild_id]:
        url = guild_queues[guild_id].pop(0)  # Get the next video from the queue
        channel = interaction.channel
        await channel.send(f"Now playing: {url}")

        try:
            with youtube_dl.YoutubeDL({'format': 'bestaudio', 'noplaylist': True, 'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                audio_url = info['url']

            def after_playing(error):
                if error:
                    print(f"Error: {error}")

            guild_current_voice[guild_id].play(discord.FFmpegPCMAudio(audio_url), after=after_playing)
            guild_current_voice[guild_id].source = discord.PCMVolumeTransformer(guild_current_voice[guild_id].source, volume=0.5)
            logging.info(f"Now playing {url} in guild {interaction.guild.name}")

            while guild_current_voice[guild_id].is_playing():
                await asyncio.sleep(1)

        except youtube_dl.DownloadError as e:
            logging.error(f"Failed to fetch the video: {str(e)} in guild {interaction.guild.name}")
            await channel.send(f"Failed to fetch the video: {str(e)}")
            continue  # Skip to the next video in the queue

    await channel.send("Queue is empty!")

# Pause Command
@bot.tree.command(name="pause", description="Pause the current track.")
async def pause(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_current_voice and guild_current_voice[guild_id] and guild_current_voice[guild_id].is_playing():
        guild_current_voice[guild_id].pause()
        logging.info(f"Playback paused in guild {interaction.guild.name}")
        await interaction.response.send_message("Playback paused.")
    else:
        await interaction.response.send_message("No audio is playing to pause.", ephemeral=True)

# Resume Command
@bot.tree.command(name="resume", description="Resume the paused track.")
async def resume(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_current_voice and guild_current_voice[guild_id] and guild_current_voice[guild_id].is_paused():
        guild_current_voice[guild_id].resume()
        logging.info(f"Playback resumed in guild {interaction.guild.name}")
        await interaction.response.send_message("Playback resumed.")
    else:
        await interaction.response.send_message("No audio is paused to resume.", ephemeral=True)

@bot.tree.command(name="clear_queue", description="Clear the music queue.")
async def clear_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Check if the guild has a queue
    if guild_id in guild_queues and guild_queues[guild_id]:
        # Clear the queue for the current guild
        guild_queues[guild_id] = []
        logging.info(f"Cleared the queue for guild {interaction.guild.name}")
        await interaction.response.send_message("The queue has been cleared.", ephemeral=True)
    else:
        await interaction.response.send_message("The queue is already empty.", ephemeral=True)

@bot.tree.command(name="skip", description="Skip the current track.")
async def skip(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_current_voice and guild_current_voice[guild_id] and guild_current_voice[guild_id].is_playing():
        guild_current_voice[guild_id].stop()
        logging.info(f"Playback skipped in guild {interaction.guild.name}")
        await interaction.response.send_message("Skipped the current track.")
    else:
        await interaction.response.send_message("No track is playing to skip.", ephemeral=True)
        
@bot.tree.command(name="skip_to", description="Skip to a specific track in the queue.")
async def skip_to_number(interaction: discord.Interaction, number: int):
    guild_id = interaction.guild.id

    # Check if the guild is in the voice channel and has a queue
    if guild_id not in guild_current_voice or guild_current_voice[guild_id] is None:
        await interaction.response.send_message("I'm not in a voice channel. Use /join first.", ephemeral=True)
        return

    if guild_id not in guild_queues or not guild_queues[guild_id]:
        await interaction.response.send_message("The queue is empty!", ephemeral=True)
        return

    # Check if the number provided is within the bounds of the queue
    if number < 1 or number > len(guild_queues[guild_id]):
        await interaction.response.send_message(f"Invalid number. Please provide a number between 1 and {len(guild_queues[guild_id])}.", ephemeral=True)
        return

    # Skip to the specified track (indexing is 0-based, so subtract 1)
    skipped_url = guild_queues[guild_id][number - 1]  # Get the track at the provided number
    guild_queues[guild_id] = guild_queues[guild_id][number - 1:]  # Remove tracks before the specified one

    # Stop the current track and start playing the new one
    guild_current_voice[guild_id].stop()

    try:
        with youtube_dl.YoutubeDL({'format': 'bestaudio', 'noplaylist': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(skipped_url, download=False)
            audio_url = info['url']

        def after_playing(error):
            if error:
                print(f"Error: {error}")

        guild_current_voice[guild_id].play(discord.FFmpegPCMAudio(audio_url), after=after_playing)
        guild_current_voice[guild_id].source = discord.PCMVolumeTransformer(guild_current_voice[guild_id].source, volume=0.5)

        logging.info(f"Skipped to {skipped_url} in guild {interaction.guild.name}")
        await interaction.response.send_message(f"Skipped to the track: {skipped_url}", ephemeral=True)

    except youtube_dl.DownloadError as e:
        logging.error(f"Failed to fetch the video: {str(e)} in guild {interaction.guild.name}")
        await interaction.response.send_message(f"Failed to fetch the video: {str(e)}", ephemeral=True)

@bot.tree.command(name="shuffle", description="Shuffle the current music queue.")
async def shuffle(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Check if the guild has a queue
    if guild_id not in guild_queues or not guild_queues[guild_id]:
        await interaction.response.send_message("The queue is empty, cannot shuffle.", ephemeral=True)
        return

    # Shuffle the queue for the guild
    random.shuffle(guild_queues[guild_id])

    # Create a message with the shuffled queue
    embed = discord.Embed(title="Shuffled Queue", description="The queue has been shuffled:", color=discord.Color.blue())

    # Add the shuffled videos to the embed
    for i, url in enumerate(guild_queues[guild_id], start=1):
        with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown Title')
                embed.add_field(name=f"Song {i}", value=title, inline=False)
            except Exception:
                embed.add_field(name=f"Song {i}", value="Failed to load title", inline=False)

    # Send the embed with the shuffled queue
    await interaction.response.send_message(embed=embed)


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)
