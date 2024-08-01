import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import logging
from app.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents)

# Mapping of channel IDs to competition IDs
CHANNEL_TO_COMPETITION = {}

# URL of your FastAPI application
API_URL = "http://localhost:8000"  # Update this to your actual API URL

async def query_llm(competition_id, question, model="claude-3-sonnet-20240229"):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/query", json={
            "competition_id": competition_id,
            "question": question,
            "model": model
        }) as response:
            if response.status == 200:
                data = await response.json()
                return data['response']
            else:
                return f"Error: Unable to get response (Status code: {response.status})"

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info("Registered commands:")
    for command in bot.commands:
        logger.info(f"- {command.name}")

@bot.event
async def on_message(message):
    logger.info(f"Received message: {message.content}")

    # Always process commands first
    await bot.process_commands(message)

    try:
        # Ignore messages from the bot itself
        if message.author == bot.user:
            return

        # Only respond to messages in threads
        if not isinstance(message.channel, discord.Thread):
            return

        # Check if the parent channel is mapped to a competition
        parent_channel_id = message.channel.parent_id
        competition_id = CHANNEL_TO_COMPETITION.get(parent_channel_id)
        
        if not competition_id:
            return  # Don't respond if the channel isn't mapped to a competition

        # Process the message content as a question
        question = message.content.strip()

        # Send the "Generating response..." message
        generating_message = await message.channel.send("Generating response...")
        
        # Query the LLM bot
        response = await query_llm(competition_id, question)

        # Delete the "Generating response..." message
        await generating_message.delete()
        
        # Split the response into chunks if necessary
        response_chunks = split_message(response)

        # Send the response in chunks
        for chunk in response_chunks:
            await message.channel.send(chunk)

    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}", exc_info=True)

@bot.command()
async def ping(ctx):
    logger.info(f"ping command invoked by {ctx.author}")
    await ctx.send('Pong!')
    
@bot.command()
@commands.guild_only()
@commands.has_permissions(administrator=True)
async def map_channel(ctx, channel_id: int, competition_id: str):
    """Map a channel to a competition ID (Admin only)"""
    logger.info(f"map_channel command invoked by {ctx.author} with channel_id={channel_id} and competition_id={competition_id}")
    CHANNEL_TO_COMPETITION[channel_id] = competition_id
    await ctx.send(f"Channel {channel_id} mapped to competition {competition_id}")

@bot.command()
@commands.guild_only()
async def get_mapping(ctx):
    """Get the current channel-to-competition mapping"""
    logger.info(f"get_mapping command invoked by {ctx.author}")
    if not CHANNEL_TO_COMPETITION:
        await ctx.send("No channel-to-competition mappings found.")
        return
    mapping = "\n".join([f"Channel {channel}: Competition {comp}" for channel, comp in CHANNEL_TO_COMPETITION.items()])
    await ctx.send(f"Current mapping:\n{mapping}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')
    elif isinstance(error, commands.errors.CommandNotFound):
        pass
    else:
        logger.error(f"Command error: {str(error)}", exc_info=True)
        await ctx.send(f"An error occurred: {str(error)}")


def split_message(message, limit=2000):
    if len(message) <= limit:
        return [message]
    
    chunks = []
    current_chunk = ""
    
    for paragraph in message.split('\n\n'):
        if len(current_chunk) + len(paragraph) + 2 > limit:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        
        if len(paragraph) > limit:
            words = paragraph.split()
            for word in words:
                if len(current_chunk) + len(word) + 1 > limit:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                current_chunk += word + " "
        else:
            current_chunk += paragraph + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

# Run the bot
try:
    bot.run(Config.DISCORD_TOKEN)
except Exception as e:
    logger.error(f"Error running bot: {str(e)}", exc_info=True)


