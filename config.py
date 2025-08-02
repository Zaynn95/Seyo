import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TOKEN = os.getenv('DISCORD_TOKEN')
    OPENAI_KEY = os.getenv('OPENAI_API_KEY')
    DB_PATH = 'data/database.db'
    
    # Colors
    PRIMARY = 0x5865F2
    SUCCESS = 0x57F287
    ERROR = 0xED4245
    
    # Font paths
    FONT_REGULAR = 'assets/nunito-regular.ttf'
    
    # Image paths
    LEVEL_CARD = 'assets/levelcard.png'
    RANK_CARD = 'assets/rankcard.png'