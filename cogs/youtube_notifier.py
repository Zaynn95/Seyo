import discord
from discord.ext import commands, tasks
from discord import app_commands
import config
from utils.database import get_guild_config, update_guild_config
import yt_dlp
import asyncio
from datetime import datetime
import re

class YouTubeNotifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.yt_dlp_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        self.check_channels.start()
    
    def cog_unload(self):
        self.check_channels.cancel()
    
    @app_commands.command(name="yt", description="YouTube notification system")
    @app_commands.describe(action="Choose an action", channel="YouTube channel URL")
    @app_commands.choices(action=[
        app_commands.Choice(name="setup", value="setup"),
        app_commands.Choice(name="add", value="add")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def yt_notifier(self, interaction: discord.Interaction, 
                         action: app_commands.Choice[str],
                         channel: str = None):
        if action.value == "setup":
            # Create notifications channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            try:
                notify_channel = await interaction.guild.create_text_channel(
                    "yt-notifications",
                    overwrites=overwrites,
                    reason="YouTube notification system"
                )
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ I don't have permission to create channels.",
                    ephemeral=True
                )
            
            # Save to database
            update_guild_config(
                interaction.guild_id,
                yt_notify_channel=notify_channel.id
            )
            
            # Send setup message
            embed = discord.Embed(
                title="🎥 YouTube Notifications Setup",
                description=f"New video notifications will be posted in {notify_channel.mention}",
                color=config.SUCCESS
            )
            embed.set_footer(text="Use /yt add to add YouTube channels to track")
            
            await interaction.response.send_message(embed=embed)
        
        elif action.value == "add":
            if not channel:
                return await interaction.response.send_message(
                    "❌ Please provide a YouTube channel URL.",
                    ephemeral=True
                )
            
            # Validate URL
            if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/(channel/|c/|user/)?[a-zA-Z0-9_-]+', channel):
                return await interaction.response.send_message(
                    "❌ Invalid YouTube channel URL.",
                    ephemeral=True
                )
            
            # Extract channel ID
            try:
                with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                    info = ydl.extract_info(channel, download=False)
                    channel_id = info.get('channel_id')
                    channel_name = info.get('channel')
                    
                    if not channel_id:
                        return await interaction.response.send_message(
                            "❌ Couldn't extract channel ID from URL.",
                            ephemeral=True
                        )
            except Exception as e:
                return await interaction.response.send_message(
                    f"❌ Error fetching channel info: {e}",
                    ephemeral=True
                )
            
            # Save to database
            conn = sqlite3.connect(config.DB_PATH)
            c = conn.cursor()
            
            # Check if already exists
            c.execute("""
                SELECT 1 FROM youtube_channels 
                WHERE channel_id=? AND guild_id=?
            """, (channel_id, interaction.guild_id))
            
            if c.fetchone():
                conn.close()
                return await interaction.response.send_message(
                    "⚠️ This channel is already being tracked.",
                    ephemeral=True
                )
            
            # Get latest video
            try:
                with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/channel/{channel_id}/videos", download=False)
                    entries = info.get('entries', [])
                    latest_video = entries[0] if entries else None
                    
                    if not latest_video:
                        return await interaction.response.send_message(
                            "❌ Channel has no videos or couldn't fetch them.",
                            ephemeral=True
                        )
                    
                    # Save to database
                    c.execute("""
                        INSERT INTO youtube_channels (channel_id, guild_id, last_video_id)
                        VALUES (?, ?, ?)
                    """, (channel_id, interaction.guild_id, latest_video['id']))
                    
                    conn.commit()
                    conn.close()
                    
                    await interaction.response.send_message(
                        f"✅ Now tracking YouTube channel: **{channel_name}**\n"
                        f"Latest video: {latest_video['title']}",
                        ephemeral=True
                    )
            except Exception as e:
                conn.close()
                return await interaction.response.send_message(
                    f"❌ Error fetching channel videos: {e}",
                    ephemeral=True
                )
    
    @tasks.loop(minutes=10)
    async def check_channels(self):
        # Get all channels to check
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        c.execute("""
            SELECT yc.channel_id, yc.guild_id, yc.last_video_id, g.yt_notify_channel
            FROM youtube_channels yc
            JOIN guilds g ON yc.guild_id = g.guild_id
            WHERE g.yt_notify_channel IS NOT NULL
        """)
        
        channels = c.fetchall()
        conn.close()
        
        for channel_id, guild_id, last_video_id, notify_channel_id in channels:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
                
            notify_channel = guild.get_channel(notify_channel_id)
            if not notify_channel:
                continue
            
            # Check for new videos
            try:
                with yt_dlp.YoutubeDL(self.yt_dlp_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/channel/{channel_id}/videos", download=False)
                    entries = info.get('entries', [])
                    
                    if not entries:
                        continue
                    
                    latest_video = entries[0]
                    if latest_video['id'] == last_video_id:
                        continue
                    
                    # New video found!
                    video_url = latest_video['url']
                    upload_time = latest_video.get('upload_date')
                    
                    if upload_time:
                        upload_time = datetime.strptime(upload_time, '%Y%m%d').strftime('%B %d, %Y')
                    else:
                        upload_time = "recently"
                    
                    # Create embed
                    embed = discord.Embed(
                        title=latest_video['title'],
                        url=video_url,
                        color=config.PRIMARY
                    )
                    embed.set_author(name=info.get('channel', 'YouTube Channel'))
                    embed.add_field(name="Uploaded", value=upload_time, inline=True)
                    embed.set_image(url=latest_video.get('thumbnail'))
                    
                    # Send notification
                    await notify_channel.send(
                        f"🎬 NEW VIDEO from **{info.get('channel', 'YouTube Channel')}**!",
                        embed=embed
                    )
                    
                    # Update database
                    conn = sqlite3.connect(config.DB_PATH)
                    c = conn.cursor()
                    c.execute("""
                        UPDATE youtube_channels
                        SET last_video_id=?
                        WHERE channel_id=? AND guild_id=?
                    """, (latest_video['id'], channel_id, guild_id))
                    conn.commit()
                    conn.close()
                    
            except Exception as e:
                print(f"Error checking YouTube channel {channel_id}: {e}")
                continue
    
    @check_channels.before_loop
    async def before_check_channels(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(YouTubeNotifier(bot))