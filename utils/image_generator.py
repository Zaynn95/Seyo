from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import config
from io import BytesIO
import discord

class CardGenerator:
    def __init__(self):
        self.font_regular = config.FONT_REGULAR
        
    async def generate_level_up_card(self, user: discord.User, old_level: int, new_level: int, xp: int, max_xp: int):
        # Load base image
        base = Image.open(config.LEVEL_CARD)
        draw = ImageDraw.Draw(base)
        
        # Load font
        try:
            title_font = ImageFont.truetype(self.font_regular, 42)
            name_font = ImageFont.truetype(self.font_regular, 36)
            xp_font = ImageFont.truetype(self.font_regular, 28)
        except:
            # Fallback if font fails
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            xp_font = ImageFont.load_default()
        
        # Draw text
        draw.text((base.width//2, 50), "🎉 LEVEL UP!", fill="white", font=title_font, anchor="mm")
        draw.text((base.width//2, 120), f"{user.display_name}", fill="white", font=name_font, anchor="mm")
        draw.text((base.width//2, 170), f"🏆 Level {old_level} → {new_level}", fill="white", font=xp_font, anchor="mm")
        
        # Progress bar
        progress = xp / max_xp
        bar_width = 500
        bar_height = 20
        bar_x = (base.width - bar_width) // 2
        bar_y = 220
        
        # Draw background bar
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), 
                              fill=(50, 50, 50), radius=10)
        
        # Draw progress
        draw.rounded_rectangle((bar_x, bar_y, bar_x + int(bar_width * progress), bar_y + bar_height), 
                              fill=(88, 101, 242), radius=10)
        
        # Draw percentage text
        draw.text((base.width//2, bar_y + bar_height + 10), 
                 f"{int(progress * 100)}%", fill="white", font=xp_font, anchor="mm")
        
        # Save to bytes
        buffer = BytesIO()
        base.save(buffer, format="PNG")
        buffer.seek(0)
        
        return discord.File(buffer, filename="levelup.png")
    
    async def generate_rank_card(self, user: discord.User, xp: int, level: int, max_xp: int, rank: int):
        # Load base image
        base = Image.open(config.RANK_CARD)
        draw = ImageDraw.Draw(base)
        
        # Load font
        try:
            title_font = ImageFont.truetype(self.font_regular, 36)
            name_font = ImageFont.truetype(self.font_regular, 32)
            stats_font = ImageFont.truetype(self.font_regular, 24)
        except:
            # Fallback if font fails
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            stats_font = ImageFont.load_default()
        
        # Draw text
        draw.text((base.width//2, 30), "🏆 USER STATS", fill="white", font=title_font, anchor="mm")
        
        # User avatar
        avatar_size = 100
        avatar = await self._get_user_avatar(user, avatar_size)
        if avatar:
            avatar = avatar.resize((avatar_size, avatar_size))
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
            base.paste(avatar, ((base.width - avatar_size) // 2, 70), mask)
        
        # Stats
        draw.text((base.width//2, 180), f"✨ XP: {xp:,}/{max_xp:,}", fill="white", font=stats_font, anchor="mm")
        draw.text((base.width//2, 210), f"⚡ Level: {level}", fill="white", font=stats_font, anchor="mm")
        draw.text((base.width//2, 240), f"🏅 Rank: #{rank}", fill="white", font=stats_font, anchor="mm")
        
        # Progress bar
        progress = xp / max_xp
        bar_width = 400
        bar_height = 15
        bar_x = (base.width - bar_width) // 2
        bar_y = 280
        
        # Draw background bar
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), 
                              fill=(50, 50, 50), radius=7)
        
        # Draw progress
        draw.rounded_rectangle((bar_x, bar_y, bar_x + int(bar_width * progress), bar_y + bar_height), 
                              fill=(88, 101, 242), radius=7)
        
        # Draw progress characters
        filled = int(10 * progress)
        progress_text = "■" * filled + "□" * (10 - filled)
        draw.text((base.width//2, bar_y + bar_height + 10), 
                 progress_text, fill="white", font=stats_font, anchor="mm")
        
        # Save to bytes
        buffer = BytesIO()
        base.save(buffer, format="PNG")
        buffer.seek(0)
        
        return discord.File(buffer, filename="rank.png")
    
    async def _get_user_avatar(self, user: discord.User, size: int):
        try:
            avatar_bytes = await user.display_avatar.read()
            return Image.open(BytesIO(avatar_bytes))
        except:
            return None