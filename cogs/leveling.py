import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.database import get_guild_config, update_guild_config
from utils.image_generator import CardGenerator
import random
import time
import sqlite3

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.card_gen = CardGenerator()
        self.cooldowns = {}
    
    @app_commands.command(name="leveling", description="Setup the leveling system")
    @app_commands.default_permissions(manage_guild=True)
    async def leveling_setup(self, interaction: discord.Interaction):
        # Create level-up channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        try:
            level_channel = await interaction.guild.create_text_channel(
                "level-up",
                overwrites=overwrites,
                reason="Leveling system"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to create channels.",
                ephemeral=True
            )
        
        # Save to database
        update_guild_config(
            interaction.guild_id,
            level_channel=level_channel.id
        )
        
        # Send setup message
        embed = discord.Embed(
            title="📈 Leveling System Setup",
            description=f"Level up notifications will be posted in {level_channel.mention}",
            color=config.SUCCESS
        )
        embed.set_footer(text="Users will earn XP by participating in chat")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="rank", description="Check your rank and level")
    async def rank(self, interaction: discord.Interaction, user: discord.User = None):
        user = user or interaction.user
        
        # Get user level data
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # Get user's level
        c.execute("""
            SELECT xp, level FROM levels 
            WHERE user_id=? AND guild_id=?
        """, (user.id, interaction.guild_id))
        result = c.fetchone()
        
        if not result:
            xp, level = 0, 1
        else:
            xp, level = result
        
        # Calculate max XP for current level
        max_xp = self._calculate_max_xp(level)
        
        # Get user's rank
        c.execute("""
            SELECT COUNT(*) FROM levels 
            WHERE guild_id=? AND (level > ? OR (level = ? AND xp > ?))
        """, (interaction.guild_id, level, level, xp))
        rank = c.fetchone()[0] + 1
        
        conn.close()
        
        # Generate rank card
        card = await self.card_gen.generate_rank_card(user, xp, level, max_xp, rank)
        
        await interaction.response.send_message(file=card)
    
    @app_commands.command(name="xp_give", description="Give XP to a user (Admin only)")
    @app_commands.default_permissions(manage_guild=True)
    async def xp_give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive.",
                ephemeral=True
            )
        
        # Update user's XP
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # Get current XP
        c.execute("""
            SELECT xp, level FROM levels 
            WHERE user_id=? AND guild_id=?
        """, (user.id, interaction.guild_id))
        result = c.fetchone()
        
        if result:
            xp, level = result
            new_xp = xp + amount
        else:
            xp, level = 0, 1
            new_xp = amount
        
        # Check for level up
        max_xp = self._calculate_max_xp(level)
        levels_gained = 0
        
        while new_xp >= max_xp:
            new_xp -= max_xp
            level += 1
            levels_gained += 1
            max_xp = self._calculate_max_xp(level)
        
        # Update database
        c.execute("""
            INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level, last_message)
            VALUES (?, ?, ?, ?, ?)
        """, (user.id, interaction.guild_id, new_xp, level, int(time.time())))
        
        conn.commit()
        conn.close()
        
        # Notify if leveled up
        if levels_gained > 0:
            config = get_guild_config(interaction.guild_id)
            if config and config[3]:  # level_channel
                channel = interaction.guild.get_channel(config[3])
                if channel:
                    card = await self.card_gen.generate_level_up_card(
                        user, level - levels_gained, level, new_xp, max_xp
                    )
                    await channel.send(
                        f"🎉 {user.mention} leveled up to level {level}!",
                        file=card
                    )
        
        await interaction.response.send_message(
            f"✅ Gave {amount} XP to {user.mention}. They're now level {level} with {new_xp}/{max_xp} XP.",
            ephemeral=True
        )
    
    @app_commands.command(name="xp_remove", description="Remove XP from a user (Admin only)")
    @app_commands.default_permissions(manage_guild=True)
    async def xp_remove(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if amount <= 0:
            return await interaction.response.send_message(
                "❌ Amount must be positive.",
                ephemeral=True
            )
        
        # Update user's XP
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # Get current XP
        c.execute("""
            SELECT xp, level FROM levels 
            WHERE user_id=? AND guild_id=?
        """, (user.id, interaction.guild_id))
        result = c.fetchone()
        
        if not result:
            return await interaction.response.send_message(
                f"❌ {user.mention} doesn't have any XP yet.",
                ephemeral=True
            )
        
        xp, level = result
        new_xp = max(0, xp - amount)
        new_level = level
        
        # Check for level down
        while new_xp < 0 and new_level > 1:
            new_level -= 1
            new_xp += self._calculate_max_xp(new_level)
        
        # Update database
        c.execute("""
            INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level, last_message)
            VALUES (?, ?, ?, ?, ?)
        """, (user.id, interaction.guild_id, new_xp, new_level, int(time.time())))
        
        conn.commit()
        conn.close()
        
        await interaction.response.send_message(
            f"✅ Removed {amount} XP from {user.mention}. They're now level {new_level} with {new_xp}/{self._calculate_max_xp(new_level)} XP.",
            ephemeral=True
        )
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Check cooldown
        cooldown_key = f"{message.guild.id}-{message.author.id}"
        if cooldown_key in self.cooldowns and time.time() - self.cooldowns[cooldown_key] < 60:
            return
        
        # Get guild config
        config = get_guild_config(message.guild.id)
        if not config or not config[3]:  # level_channel
            return
        
        # Give random XP between 15-25
        xp = random.randint(15, 25)
        
        # Update database
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        
        # Get current XP
        c.execute("""
            SELECT xp, level FROM levels 
            WHERE user_id=? AND guild_id=?
        """, (message.author.id, message.guild.id))
        result = c.fetchone()
        
        if result:
            current_xp, level = result
            new_xp = current_xp + xp
        else:
            current_xp, level = 0, 1
            new_xp = xp
        
        # Check for level up
        max_xp = self._calculate_max_xp(level)
        leveled_up = False
        
        if new_xp >= max_xp:
            new_xp -= max_xp
            level += 1
            leveled_up = True
        
        # Update database
        c.execute("""
            INSERT OR REPLACE INTO levels (user_id, guild_id, xp, level, last_message)
            VALUES (?, ?, ?, ?, ?)
        """, (message.author.id, message.guild.id, new_xp, level, int(time.time())))
        
        conn.commit()
        conn.close()
        
        # Update cooldown
        self.cooldowns[cooldown_key] = time.time()
        
        # Send level up message if applicable
        if leveled_up and config[3]:
            channel = message.guild.get_channel(config[3])
            if channel:
                card = await self.card_gen.generate_level_up_card(
                    message.author, level - 1, level, new_xp, self._calculate_max_xp(level)
                )
                await channel.send(
                    f"🎉 {message.author.mention} leveled up to level {level}!",
                    file=card
                )
    
    def _calculate_max_xp(self, level):
        return 100 * (level ** 2)  # Quadratic scaling

async def setup(bot):
    await bot.add_cog(Leveling(bot))