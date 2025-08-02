import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.database import get_guild_config, update_guild_config
import re

class YouTubeVerifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ytsub", description="YouTube subscription verification system")
    @app_commands.describe(
        action="Choose an action",
        channel="YouTube channel URL",
        role="Role to give verified users"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="setup", value="setup"),
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def ytsub(self, interaction: discord.Interaction, 
                   action: app_commands.Choice[str],
                   channel: str = None,
                   role: discord.Role = None):
        if action.value == "setup":
            if not channel or not role:
                return await interaction.response.send_message(
                    "❌ Both channel URL and role are required for setup.",
                    ephemeral=True
                )
            
            # Validate YouTube URL
            if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/', channel):
                return await interaction.response.send_message(
                    "❌ Invalid YouTube channel URL.",
                    ephemeral=True
                )
            
            # Create proof channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
            }
            
            try:
                proof_channel = await interaction.guild.create_text_channel(
                    "proof",
                    overwrites=overwrites,
                    reason="YouTube verification system"
                )
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ I don't have permission to create channels.",
                    ephemeral=True
                )
            
            # Save to database
            update_guild_config(
                interaction.guild_id,
                yt_verify_channel=proof_channel.id,
                yt_verify_role=role.id
            )
            
            # Send setup message
            embed = discord.Embed(
                title="📺 YouTube Verification Setup",
                description=f"Users can now submit proof in {proof_channel.mention} to get {role.mention}",
                color=config.SUCCESS
            )
            embed.add_field(name="YouTube Channel", value=channel)
            embed.set_footer(text="Submissions will be manually verified by moderators")
            
            await interaction.response.send_message(embed=embed)
            
            # Send instructions to proof channel
            embed = discord.Embed(
                title="📺 YouTube Verification",
                description=f"To get {role.mention}, please submit a screenshot proving you're subscribed to:\n{channel}",
                color=config.PRIMARY
            )
            embed.set_footer(text="Upload your screenshot here for verification")
            await proof_channel.send(embed=embed)
        
        elif action.value == "enable":
            update_guild_config(interaction.guild_id, yt_verify_channel=1)  # Using 1 as enabled flag
            await interaction.response.send_message(
                "✅ YouTube verification system has been enabled.",
                ephemeral=True
            )
        
        elif action.value == "disable":
            update_guild_config(interaction.guild_id, yt_verify_channel=0)  # Using 0 as disabled flag
            await interaction.response.send_message(
                "⚠️ YouTube verification system has been disabled.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Check if this is a proof submission
        config = get_guild_config(message.guild.id)
        if not config or not config[1] or message.channel.id != config[1]:
            return
        
        # Check if message has attachments
        if not message.attachments:
            await message.delete()
            try:
                await message.author.send("🔍 Your proof submission was deleted because it didn't contain any images.")
            except:
                pass
            return
        
        # Notify moderators
        embed = discord.Embed(
            title="📺 New Verification Submission",
            description=f"From {message.author.mention}",
            color=config.PRIMARY
        )
        embed.set_image(url=message.attachments[0].url)
        embed.set_footer(text="React with ✅ to approve or ❌ to reject")
        
        log_channel = message.guild.get_channel(config[1])
        if log_channel:
            log_msg = await log_channel.send(embed=embed)
            await log_msg.add_reaction("✅")
            await log_msg.add_reaction("❌")
        
        # DM user
        try:
            await message.author.send(
                "🎉 Your proof has been submitted! Moderators will review it shortly."
            )
        except:
            pass
        
        # Delete original message
        await message.delete()
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Ignore bots
        if payload.member.bot:
            return
        
        # Check if this is a verification message
        config = get_guild_config(payload.guild_id)
        if not config or not config[1]:
            return
        
        channel = self.bot.get_channel(payload.channel_id)
        if not channel or channel.id != config[1]:
            return
        
        message = await channel.fetch_message(payload.message_id)
        if not message.embeds or not message.embeds[0].title == "📺 New Verification Submission":
            return
        
        # Check if reactor has manage_guild permission
        member = payload.member
        if not member.guild_permissions.manage_guild:
            try:
                await message.remove_reaction(payload.emoji, member)
            except:
                pass
            return
        
        # Get the user being verified
        embed = message.embeds[0]
        user_id = int(embed.description.split(" ")[1][2:-1])
        user = await self.bot.fetch_user(user_id)
        
        if str(payload.emoji) == "✅":
            # Approve verification
            role = member.guild.get_role(config[2])
            if role:
                try:
                    guild_member = await member.guild.fetch_member(user_id)
                    await guild_member.add_roles(role)
                    
                    # Update database
                    update_guild_config(
                        payload.guild_id,
                        user_id=user_id,
                        status="approved"
                    )
                    
                    # Notify user
                    try:
                        await user.send("🎉 Your YouTube subscription has been verified! Role granted.")
                    except:
                        pass
                    
                    # Update embed
                    embed.color = config.SUCCESS
                    embed.add_field(name="Status", value="Approved ✅")
                    await message.edit(embed=embed)
                except discord.Forbidden:
                    await channel.send("❌ I don't have permission to add roles.")
        
        elif str(payload.emoji) == "❌":
            # Reject verification
            update_guild_config(
                payload.guild_id,
                user_id=user_id,
                status="rejected"
            )
            
            # Notify user
            try:
                await user.send("❌ Your YouTube verification was rejected. Please make sure you're subscribed and resubmit.")
            except:
                pass
            
            # Update embed
            embed.color = config.ERROR
            embed.add_field(name="Status", value="Rejected ❌")
            await message.edit(embed=embed)

async def setup(bot):
    await bot.add_cog(YouTubeVerifier(bot))