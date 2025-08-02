import discord
from discord.ext import commands
import config
import asyncio

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

async def load_cogs():
    cogs = [
        'cogs.youtube_verifier',
        'cogs.suggestions',
        'cogs.leveling',
        'cogs.ai_chat',
        'cogs.youtube_notifier'
    ]
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f'✅ Loaded {cog}')
        except Exception as e:
            print(f'❌ Failed to load {cog}: {e}')

@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name="your commands 👀"
    ))

async def main():
    async with bot:
        await load_cogs()
        await bot.start(config.TOKEN)

asyncio.run(main())