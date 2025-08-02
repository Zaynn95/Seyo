# cogs/__init__.py

from .youtube_verifier import YouTubeVerifier
from .suggestions import Suggestions
from .leveling import Leveling
from .ai_chat import AIChat
from .youtube_notifier import YouTubeNotifier

# Optional: Define what gets imported with 'from cogs import *'
__all__ = [
    'YouTubeVerifier',
    'Suggestions',
    'Leveling',
    'AIChat',
    'YouTubeNotifier'
]