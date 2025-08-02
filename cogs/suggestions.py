import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.database import get_guild_config, update_guild_config

class Suggestions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="suggestion", description="Setup the suggestion system")
    @app_commands.default_permissions(manage_guild=True)
    async def suggestion_setup(self, interaction: discord.Interaction):
        # Create suggestions channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
        }
        
        try:
            suggestions_channel = await interaction.guild.create_text_channel(
                "suggestions",
                overwrites=overwrites,
                reason="Suggestion system"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to create channels.",
                ephemeral=True
            )
        
        # Save to database
        update_guild_config(
            interaction.guild_id,
            suggestions_channel=suggestions_channel.id
        )
        
        # Send setup message
        embed = discord.Embed(
            title="💡 Suggestion System Setup",
            description=f"Users can now make suggestions in {suggestions_channel.mention}",
            color=config.SUCCESS
        )
        embed.set_footer(text="Use /suggest to submit a suggestion")
        
        await interaction.response.send_message(embed=embed)
        
        # Send instructions to suggestions channel
        embed = discord.Embed(
            title="💡 Suggestions",
            description="Submit your suggestions here with `/suggest` command.\n\n"
                       "Good suggestions include:\n"
                       "- Clear description of your idea\n"
                       "- Why it would be beneficial\n"
                       "- Any relevant examples",
            color=config.PRIMARY
        )
        await suggestions_channel.send(embed=embed)
    
    @app_commands.command(name="suggest", description="Submit a suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        config = get_guild_config(interaction.guild_id)
        if not config or not config[2]:  # suggestions_channel
            return await interaction.response.send_message(
                "❌ Suggestion system is not setup on this server.",
                ephemeral=True
            )
        
        # Get suggestions channel
        channel = interaction.guild.get_channel(config[2])
        if not channel:
            return await interaction.response.send_message(
                "❌ Suggestions channel not found.",
                ephemeral=True
            )
        
        # Create suggestion embed
        embed = discord.Embed(
            title=f"💡 New Suggestion",
            description=suggestion,
            color=config.PRIMARY
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Vote with reactions below")
        
        # Send to suggestions channel
        msg = await channel.send(embed=embed)
        
        # Add reactions
        await msg.add_reaction("🟢")  # Upvote
        await msg.add_reaction("🔴")  # Downvote
        
        # Confirm to user
        await interaction.response.send_message(
            f"✅ Your suggestion has been posted in {channel.mention}!",
            ephemeral=True
        )
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Ignore bots
        if payload.member and payload.member.bot:
            return
        
        # Check if this is a suggestion message
        config = get_guild_config(payload.guild_id)
        if not config or not config[2] or payload.channel_id != config[2]:
            return
        
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        message = await channel.fetch_message(payload.message_id)
        if not message.embeds or not message.embeds[0].title.startswith("💡"):
            return
        
        # Check if user already voted
        for reaction in message.reactions:
            if reaction.emoji != str(payload.emoji):
                async for user in reaction.users():
                    if user.id == payload.user_id:
                        await message.remove_reaction(payload.emoji, payload.member)
                        return

async def setup(bot):
    await bot.add_cog(Suggestions(bot))