import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.database import get_guild_config, update_guild_config
import openai
import asyncio
from collections import defaultdict

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        openai.api_key = config.OPENAI_KEY
        self.rate_limits = defaultdict(int)
        self.active_chats = set()
    
    @app_commands.command(name="ai", description="AI chat system configuration")
    @app_commands.describe(action="Enable or disable the AI chat system")
    @app_commands.choices(action=[
        app_commands.Choice(name="setup", value="setup"),
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def ai_config(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        if action.value == "setup":
            # Create AI chat channel
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
            }
            
            try:
                ai_channel = await interaction.guild.create_text_channel(
                    "ai-chat",
                    overwrites=overwrites,
                    reason="AI chat system"
                )
            except discord.Forbidden:
                return await interaction.response.send_message(
                    "❌ I don't have permission to create channels.",
                    ephemeral=True
                )
            
            # Save to database
            update_guild_config(
                interaction.guild_id,
                ai_channel=ai_channel.id
            )
            
            # Send setup message
            embed = discord.Embed(
                title="🤖 AI Chat System Setup",
                description=f"Chat with the AI in {ai_channel.mention}",
                color=config.SUCCESS
            )
            embed.set_footer(text="Type a message starting with @Seyo to chat")
            
            await interaction.response.send_message(embed=embed)
            
            # Send instructions to AI channel
            embed = discord.Embed(
                title="🤖 AI Chat",
                description="Mention me (@Seyo) at the start of your message to chat with me!\n\n"
                           "Example:\n"
                           "@Seyo What's the meaning of life?",
                color=config.PRIMARY
            )
            embed.set_footer(text="Rate limited to 5 requests per minute")
            await ai_channel.send(embed=embed)
        
        elif action.value == "enable":
            update_guild_config(interaction.guild_id, ai_channel=1)  # Using 1 as enabled flag
            await interaction.response.send_message(
                "✅ AI chat system has been enabled.",
                ephemeral=True
            )
        
        elif action.value == "disable":
            update_guild_config(interaction.guild_id, ai_channel=0)  # Using 0 as disabled flag
            await interaction.response.send_message(
                "⚠️ AI chat system has been disabled.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Check if AI is mentioned at start of message
        if not message.content.startswith(f"<@{self.bot.user.id}>"):
            return
        
        # Check guild config
        config = get_guild_config(message.guild.id)
        if not config or not config[4]:  # ai_channel
            return
        
        # Check if in AI channel if configured
        if isinstance(config[4], int) and config[4] > 1 and message.channel.id != config[4]:
            return
        
        # Rate limiting
        user_key = f"{message.guild.id}-{message.author.id}"
        self.rate_limits[user_key] += 1
        
        if self.rate_limits[user_key] > 5:
            await message.reply("⚠️ You're sending too many requests. Please wait a minute.")
            return
        
        # Get clean prompt
        prompt = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
        if not prompt:
            await message.reply("🤖 Hello! How can I help you today?")
            return
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Check if this is an ongoing conversation
                conversation_id = f"{message.channel.id}-{message.author.id}"
                if conversation_id in self.active_chats:
                    # Continue existing conversation
                    response = await self._get_ai_response(prompt, is_continuation=True)
                else:
                    # Start new conversation
                    self.active_chats.add(conversation_id)
                    response = await self._get_ai_response(prompt)
                
                # Split long responses
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
                
            except Exception as e:
                print(f"AI Error: {e}")
                await message.reply("❌ Sorry, I encountered an error. Please try again later.")
    
    async def _get_ai_response(self, prompt: str, is_continuation: bool = False):
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise e

async def setup(bot):
    await bot.add_cog(AIChat(bot))