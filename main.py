import discord
from discord.ext import commands
import os
import webserver
from dotenv import load_dotenv
from dth import DropTheHandkerchiefGame
from gops import GOPSGame
from combination import CombinationGame

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("discordkey")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='.', intents=intents)

# Game state storage
active_games = {}
game_channels = {}  # Store which channel each game is in


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name=".dth or .gops @opponent to play!"))


@bot.command(name='dth')
async def start_dth_game(ctx, opponent: discord.Member):
    """Start a Drop the Handkerchief game"""
    # Validation checks
    if opponent == ctx.author:
        await ctx.send("❌ You can't play against yourself!")
        return

    if opponent.bot:
        await ctx.send("❌ You can't play against a bot!")
        return

    # Check if either player is already in a game
    for game_id, game in active_games.items():
        if ctx.author.id in game_id or opponent.id in game_id:
            await ctx.send("❌ One of the players is already in an active game!")
            return

    # Create new game
    game_id = (ctx.author.id, opponent.id, "dth")
    game = DropTheHandkerchiefGame(ctx.author, opponent, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game


@bot.command(name='gops')
async def start_gops_game(ctx, opponent: discord.Member):
    """Start a GOPS game"""
    # Validation checks
    if opponent == ctx.author:
        await ctx.send("❌ You can't play against yourself!")
        return

    if opponent.bot:
        await ctx.send("❌ You can't play against a bot!")
        return

    # Check if either player is already in a game
    for game_id, game in active_games.items():
        if ctx.author.id in game_id or opponent.id in game_id:
            await ctx.send("❌ One of the players is already in an active game!")
            return

    # Create new game
    game_id = (ctx.author.id, opponent.id, "gops")
    game = GOPSGame(ctx.author, opponent, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game

@bot.command(name='comb')
async def start_combination_game(ctx, opponent: discord.Member):
    """Start a Combination game"""
    # Validation checks
    if opponent == ctx.author:
        await ctx.send("❌ You can't play against yourself!")
        return

    if opponent.bot:
        await ctx.send("❌ You can't play against a bot!")
        return

    # Check if either player is already in a game
    for game_id, game in active_games.items():
        if ctx.author.id in game_id or opponent.id in game_id:
            await ctx.send("❌ One of the players is already in an active game!")
            return

    # Create new game
    game_id = (ctx.author.id, opponent.id, "comb")
    game = CombinationGame(ctx.author, opponent, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game


async def process_dm_command(message):
    """Process commands received in DMs"""
    content = message.content.strip()

    # Handle Combination game commands specifically
    if content.startswith('.combo ') or content.startswith('.guess '):
        # Find which game this player is in
        player_game = None
        game_type = None
        game_id_to_remove = None

        for game_id, game in active_games.items():
            if message.author.id in game_id and game.game_active:
                player_game = game
                game_type = game_id[2]  # "dth", "gops", or "comb"
                break

        if not player_game:
            await message.channel.send("❌ You're not in an active game! Start one with `.comb @opponent` in a server.")
            return

        if game_type == "comb":
            if content.startswith('.combo '):
                cards = content[len('.combo '):].split()
                result = await player_game.process_combo(message.author, cards)

                if result:  # If there's an error message
                    await message.channel.send(result)
                else:  # If successful, add checkmark reaction
                    try:
                        await message.add_reaction('✅')
                    except:
                        pass

            elif content.startswith('.guess '):
                cards = content[len('.guess '):].split()
                result = await player_game.process_guess(message.author, cards)

                if result:  # If there's an error message
                    await message.channel.send(result)
                else:  # If successful, add checkmark reaction
                    try:
                        await message.add_reaction('✅')
                    except:
                        pass

            else:
                await message.channel.send(
                    "❌ Unknown command for Combination game. Use `.combo [cards]` or `.guess [cards]`")
                return

            # If Combination game ended, remove it from active games
            if not player_game.game_active:
                for game_id, game in active_games.items():
                    if game == player_game:
                        game_id_to_remove = game_id
                        break
                if game_id_to_remove:
                    del active_games[game_id_to_remove]
                    if game_id_to_remove in game_channels:
                        del game_channels[game_id_to_remove]

            return

    # ... rest of the existing process_dm_command function remains the same ...

    # Handle other commands (existing code)
    parts = content.split()
    if len(parts) < 2:
        await message.channel.send(
            "❌ Invalid command. Use `.drop [1-60]`, `.check [1-60]`, `.bid [1-13]`, `.hand [cards]`, or `.guess [cards]`")
        return

    try:
        # For numeric commands, try to parse the number
        if parts[0] in ['.drop', '.check', '.bid']:
            number = int(parts[1])
        else:
            number = None  # For non-numeric commands like .hand/.guess
    except ValueError:
        await message.channel.send("❌ Please provide a valid number!")
        return

    # Find which game this player is in
    player_game = None
    game_type = None
    game_id_to_remove = None

    for game_id, game in active_games.items():
        if message.author.id in game_id and game.game_active:
            player_game = game
            game_type = game_id[2]  # "dth", "gops", or "comb"
            break

    if not player_game:
        await message.channel.send(
            "❌ You're not in an active game! Start one with `.dth @opponent`, `.gops @opponent`, or `.comb @opponent` in a server.")
        return

    # Process the command based on game type
    if game_type == "dth":
        if parts[0] == '.drop':
            result = await player_game.process_drop(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        elif parts[0] == '.check':
            result = await player_game.process_check(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        else:
            await message.channel.send("❌ Unknown command for DTH game. Use `.drop [1-60]` or `.check [1-60]`")
            return

        # If DTH game ended, remove it from active games
        if not player_game.game_active:
            for game_id, game in active_games.items():
                if game == player_game:
                    game_id_to_remove = game_id
                    break

    elif game_type == "gops":
        if parts[0] == '.bid':
            result = await player_game.process_bid(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        else:
            await message.channel.send("❌ Unknown command for GOPS game. Use `.bid [1-13]`")
            return

        # If GOPS game ended, remove it from active games
        if not player_game.game_active:
            for game_id, game in active_games.items():
                if game == player_game:
                    game_id_to_remove = game_id
                    break

    # Remove ended game
    if game_id_to_remove:
        del active_games[game_id_to_remove]
        if game_id_to_remove in game_channels:
            del game_channels[game_id_to_remove]


@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # Check if this is a combo or guess command in a channel (needs to come BEFORE command processing)
    if (not isinstance(message.channel, discord.DMChannel) and
            (message.content.startswith('.combo ') or message.content.startswith('.guess '))):

        # Find if the author is in a Combination game
        player_game = None
        game_type = None
        for game_id, game in active_games.items():
            if (message.author.id in game_id and game.game_active and
                    game_id[2] == "comb" and hasattr(game, 'awaiting_maker')):
                player_game = game
                game_type = "comb"
                break

        if player_game:
            if message.content.startswith('.combo '):
                # Check if user is the maker
                if player_game.maker.id != message.author.id:
                    await message.channel.send("❌ You're not the maker this round! Wait for your turn as guesser.")
                    return

                if not player_game.awaiting_maker:
                    await message.channel.send("❌ You've already submitted your combination for this round!")
                    return

                cards = message.content[len('.combo '):].split()
                result = await player_game.process_combo(message.author, cards)

            elif message.content.startswith('.guess '):
                # Check if user is the guesser
                if player_game.guesser.id != message.author.id:
                    await message.channel.send("❌ You're not the guesser this round! Wait for your turn as maker.")
                    return

                if not player_game.awaiting_guesser:
                    await message.channel.send("❌ You've already submitted your guess for this round!")
                    return

                cards = message.content[len('.guess '):].split()
                result = await player_game.process_guess(message.author, cards)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

            # Check if game ended
            if not player_game.game_active:
                game_id_to_remove = None
                for game_id, game in active_games.items():
                    if game == player_game:
                        game_id_to_remove = game_id
                        break
                if game_id_to_remove:
                    del active_games[game_id_to_remove]
                    if game_id_to_remove in game_channels:
                        del game_channels[game_id_to_remove]

            return  # Prevent further processing

    # Process DMs separately
    if isinstance(message.channel, discord.DMChannel):
        await process_dm_command(message)
        return

    # Process regular server commands
    await bot.process_commands(message)


@bot.command(name='rules')
async def show_rules(ctx):
    """Show game rules"""
    rules = (
        "🎮 **Available Games**\n\n"
        "**1. Drop the Handkerchief (.dth)**\n"
        "- `.dth @opponent` to start\n"
        "- Dropper: `.drop [1-60]`\n"
        "- Checker: `.check [1-60]`\n"
        "- Avoid reaching 300 seconds penalty\n\n"
        "**2. GOPS (.gops)**\n"
        "- `.gops @opponent` to start\n"
        "- Bid: `.bid [1-13]`\n"
        "- Higher bid wins ALL prize cards' points\n"
        "- Ties: prize cards carry over to next round\n"
        "- First to 46+ points wins instantly!\n\n"
        "**3. Combination (.comb)**\n"
        "- `.comb @opponent` to start\n"
        "- Maker: `.combo [cards]` - create combination\n"
        "- Guesser: `.guess [cards]` - guess combination\n"
        "- Cards: A/1, 2-10, J/11, Q/12, K/13\n"
        "- Max 4 of each card, sum must match target\n"
        "- First to 0 HP loses!\n\n"
        "**Commands:**\n"
        "- `.dth @opponent` - Start DTH game\n"
        "- `.gops @opponent` - Start GOPS game\n"
        "- `.comb @opponent` - Start Combination game\n"
        "- `.rules` - Show these rules\n"
        "- `.cancel` - Cancel current game\n"
        "- `.score` - Show current game status"
    )
    await ctx.send(rules)


@bot.command(name='cancel')
async def cancel_game(ctx):
    """Cancel your current game"""
    game_to_remove = None

    for game_id, game in active_games.items():
        if ctx.author.id in game_id:
            opponent_id = game_id[0] if game_id[1] == ctx.author.id else game_id[1]
            opponent = bot.get_user(opponent_id)

            if opponent:
                try:
                    await opponent.send(f"❌ Game canceled by {ctx.author.mention}")
                except:
                    pass

            game_to_remove = game_id
            break

    if game_to_remove:
        del active_games[game_to_remove]
        if game_to_remove in game_channels:
            del game_channels[game_to_remove]
        await ctx.send("✅ Game canceled!")
    else:
        await ctx.send("❌ You're not in an active game!")


@bot.command(name='score')
async def show_score(ctx):
    """Show your current game score"""
    player_game = None
    game_type = None

    for game_id, game in active_games.items():
        if ctx.author.id in game_id:
            player_game = game
            game_type = game_id[2]
            break

    if not player_game:
        await ctx.send("❌ You're not in an active game!")
        return

    if game_type == "dth":
        score_message = (
            f"📊 **Drop the Handkerchief - Round {player_game.round}**\n"
            f"{player_game.player1.mention}: {player_game.penalties[player_game.player1.id]}/300\n"
            f"{player_game.player2.mention}: {player_game.penalties[player_game.player2.id]}/300\n\n"
            f"Current dropper: {player_game.dropper.mention}\n"
            f"Current checker: {player_game.checker.mention}"
        )
    else:  # GOPS
        score_message = player_game.get_score_display()

    await ctx.send(score_message)


# Error handling
@start_dth_game.error
@start_gops_game.error
async def start_game_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Please mention an opponent! Usage: `.dth @opponent` or `.gops @opponent`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Please mention a valid user! Usage: `.dth @opponent` or `.gops @opponent`")
    else:
        await ctx.send("❌ An error occurred. Please try again.")


# Run the bot
if __name__ == "__main__":
    webserver.keep_alive()
    bot.run(DISCORD_TOKEN)
