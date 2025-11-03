import discord
from discord.ext import commands
import os
import webserver

from dotenv import load_dotenv
from dth import DropTheHandkerchiefGame
from gops import GOPSGame
from combination import CombinationGame
from dotty import BloodyDottyGame
from airpoker import AirPokerGame
from kod import KingOfDiamondsGame
from knucklebones import KnucklebonesGame
from game_stats import *


# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv('discordkey')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='.', intents=intents)

# Game state storage
active_games = {}
game_channels = {}  # Store which channel each game is in

from backup_manager import initialize_backup_system, get_backup_manager
import asyncio


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name=".dth or .gops @opponent to play!"))

    # Initialize backup system
    initialize_backup_system()

    # Start the scheduled backup task
    if os.getenv('RENDER'):
        bot.loop.create_task(scheduled_backup())


# Add backup command
@bot.command(name='backup')
@commands.is_owner()
async def manual_backup(ctx):
    """Manual backup command (bot owner only)"""
    try:
        manager = get_backup_manager()
        if manager:
            success_count = manager.backup_all_databases()
            await ctx.send(f"✅ Manual backup completed: {success_count} databases backed up")
        else:
            await ctx.send("❌ Backup system not available")
    except Exception as e:
        await ctx.send(f"❌ Backup failed: {str(e)}")


@bot.command(name='restore')
@commands.is_owner()
async def manual_restore(ctx):
    """Manual restore command (bot owner only)"""
    try:
        manager = get_backup_manager()
        if manager:
            success_count = manager.restore_all_databases()
            await ctx.send(f"✅ Manual restore completed: {success_count} databases restored")
        else:
            await ctx.send("❌ Backup system not available")
    except Exception as e:
        await ctx.send(f"❌ Restore failed: {str(e)}")


# Automated backup task
async def scheduled_backup():
    """Run automated backups every 6 hours"""
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            manager = get_backup_manager()
            if manager and os.getenv('RENDER'):
                print("Running scheduled backup...")
                manager.backup_all_databases()
                manager.cleanup_old_backups(days_to_keep=7)  # Keep 1 week of backups
                print("Scheduled backup completed")
        except Exception as e:
            print(f"Scheduled backup error: {e}")

        # Wait 2 hours
        await asyncio.sleep(2 * 60 * 60)


@bot.command(name='score')
async def show_score(ctx, *, args=None):
    """Show player statistics"""
    # If no args provided, show author's score
    if args is None:
        player_mention = ctx.author.mention
    else:
        player_mention = args.strip()

    # Check for "vs" pattern for head-to-head
    if ' vs ' in player_mention.lower():
        parts = player_mention.split(' vs ', 1)
        if len(parts) != 2:
            await ctx.send("❌ Usage: `.score @player` or `.score @player1 vs @player2`")
            return

        player1_mention = parts[0].strip()
        player2_mention = parts[1].strip()

        # Extract user IDs from mentions
        player1 = await extract_user_from_mention(bot, ctx, player1_mention)
        player2 = await extract_user_from_mention(bot, ctx, player2_mention)

        if not player1 or not player2:
            await ctx.send("❌ Please mention valid players!")
            return

        # Get 1v1 game stats
        stats = await get_head_to_head_stats(player1.id, player2.id)

        # Get KOD stats
        kod_stats = await get_kod_head_to_head_stats(player1.id, player2.id)
        kod_wins1, kod_wins2, kod_draws = kod_stats if kod_stats else (0, 0, 0)

        # Format the response - always show the table, even if empty
        response = f"**{player1.mention}'s gambling score against {player2.mention}:**\n```\n"
        response += "Game           W   D   L\n\n"

        # Add 1v1 games
        for game_type, total, wins1, wins2, draws in stats:
            game_name = get_game_display_name(game_type)
            # For games that can't have draws, show "-" instead of 0
            if game_type in ['dth', 'dotty', 'comb']:
                draws_display = "-"
            else:
                draws_display = str(draws)
            # wins1 are player1's wins, wins2 are player2's wins (which are player1's losses)
            response += f"{game_name:<14} {wins1:<3} {draws_display:<3} {wins2:<3}\n"

        # Add KOD only if they have played KOD games together
        if kod_stats and (kod_wins1 > 0 or kod_wins2 > 0 or kod_draws > 0):
            response += f"{'KOD':<14} {kod_wins1:<3} {kod_draws:<3} {kod_wins2:<3}\n"

        response += "```"
        await ctx.send(response)

    else:
        # Single player stats
        player = await extract_user_from_mention(bot, ctx, player_mention)

        if not player:
            await ctx.send("❌ Please mention a valid player!")
            return

        # Get 1v1 game stats
        stats = await get_player_stats(player.id)

        # Get KOD stats
        kod_stats = await get_kod_player_stats(player.id)
        kod_wins, kod_draws, kod_losses = kod_stats if kod_stats else (0, 0, 0)

        # Format the response - always show the table, even if empty
        response = f"**{player.mention}'s gambling score:**\n```\n"
        response += "Game           W   D   L\n\n"

        # Add 1v1 games
        for game_type, total, wins, draws, losses in stats:
            game_name = get_game_display_name(game_type)
            # For games that can't have draws, show "-" instead of 0
            if game_type in ['dth', 'dotty', 'comb']:
                draws_display = "-"
            else:
                draws_display = str(draws)
            response += f"{game_name:<14} {wins:<3} {draws_display:<3} {losses:<3}\n"

        # Add KOD only if player has played KOD games
        if kod_stats:
            response += f"{'KOD':<14} {kod_wins:<3} {kod_draws:<3} {kod_losses:<3}\n"

        response += "```"
        await ctx.send(response)


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

@bot.command(name='dotty')
async def start_dotty_game(ctx, opponent: discord.Member):
    """Start a Bloody Dotty game"""
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
    game_id = (ctx.author.id, opponent.id, "dotty")
    game = BloodyDottyGame(ctx.author, opponent, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game

@bot.command(name='airpoker')
async def start_airpoker_game(ctx, opponent: discord.Member, *, options=None):
    """Start an Air Poker game"""
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

    # Parse options
    show_table = True
    if options and "no_table" in options.lower():
        show_table = False

    # Create new game
    game_id = (ctx.author.id, opponent.id, "airpoker")
    game = AirPokerGame(ctx.author, opponent, ctx.channel, show_table)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game

@bot.command(name='Kod')
async def start_kod_game(ctx, *opponents: discord.Member):
    """Start a King of Diamonds game"""
    if len(opponents) < 1:
        await ctx.send("❌ You need at least 1 opponent! Usage: `.Kod @player1 @player2 ...`")
        return

    players = [ctx.author] + list(opponents)

    # Check for duplicates and bots
    unique_players = set()
    for player in players:
        if player.bot:
            await ctx.send("❌ You can't play against bots!")
            return
        if player.id in unique_players:
            await ctx.send("❌ Duplicate players detected!")
            return
        unique_players.add(player.id)

    # Check if any player is already in a game
    for game_id, game in active_games.items():
        for player in players:
            if player.id in game_id:
                await ctx.send("❌ One of the players is already in an active game!")
                return

    # Create new game with sorted player IDs for consistent game_id
    sorted_player_ids = sorted(player.id for player in players)
    game_id = tuple(sorted_player_ids) + ("Kod",)
    game = KingOfDiamondsGame(players, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game

@bot.command(name='kb')
async def start_kb_game(ctx, opponent: discord.Member):
    """Start a Knucklebones game"""
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
    game_id = (ctx.author.id, opponent.id, "kb")
    game = KnucklebonesGame(ctx.author, opponent, ctx.channel)
    game_channels[game_id] = ctx.channel.id

    # Try to start the game
    if await game.start_game():
        active_games[game_id] = game


async def process_dm_command(message):
    """Process commands received in DMs"""
    content = message.content.strip()
    parts = content.split()

    if len(parts) == 0:
        await message.channel.send("❌ Please provide a command!")
        return

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

    # Handle other commands
    if len(parts) < 2:
        await message.channel.send(
            "❌ Invalid command.")
        return

    command = parts[0]

    try:
        # For numeric commands, try to parse the number
        if command in ['.drop', '.check', '.bid', '.grab']:
            number = int(parts[1])
        else:
            number = None  # For non-numeric commands like .combo/.guess
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
            game_type = game_id[-1]  # "dth", "gops", "comb", or "dotty"
            break

    if not player_game:
        await message.channel.send(
            "❌ You're not in an active game! Start one with `.dth @opponent`, `.gops @opponent`, `.comb @opponent`, or `.dotty @opponent` in a server.")
        return

    # Process the command based on game type
    if game_type == "dth":
        if command == '.drop':
            result = await player_game.process_drop(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        elif command == '.check':
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
        if command == '.bid':
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

    elif game_type == "dotty":
        if command == '.grab':
            result = await player_game.process_grab(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        else:
            await message.channel.send("❌ Unknown command for Bloody Dotty game. Use `.grab [1-10]`")
            return

        # If Bloody Dotty game ended, remove it from active games
        if not player_game.game_active:
            for game_id, game in active_games.items():
                if game == player_game:
                    game_id_to_remove = game_id
                    break

    elif game_type == "airpoker":
        if command == '.play':
            if len(parts) < 2:
                await message.channel.send("❌ Please provide a number to play! Usage: `.play [number]`")
                return

            try:
                number = int(parts[1])
            except ValueError:
                await message.channel.send("❌ Please provide a valid number!")
                return

            result = await player_game.process_play(message.author, number)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        elif command == '.hand':
            if len(parts) < 6:
                await message.channel.send("❌ Please provide 5 cards for your hand! Usage: `.hand As 2s 3s 4s 5s`")
                return

            cards = parts[1:6]  # Take exactly 5 cards
            result = await player_game.process_hand(message.author, cards)

            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        else:
            await message.channel.send("❌ Unknown command for Air Poker game. Use `.play [number]`")
            return

        # If Air Poker game ended, remove it from active games
        if not player_game.game_active:
            for game_id, game in active_games.items():
                if game == player_game:
                    game_id_to_remove = game_id
                    break

    elif game_type == "Kod":
        if command == '.num':
            if len(parts) < 2:
                await message.channel.send("❌ Please provide a number! Usage: `.num [0-100]`")
                return

            try:
                number = int(parts[1])
            except ValueError:
                await message.channel.send("❌ Please provide a valid number between 0-100!")
                return


            result = await player_game.process_num(message.author, number)


            if result:  # If there's an error message
                await message.channel.send(result)
            else:  # If successful, add checkmark reaction
                try:
                    await message.add_reaction('✅')
                except:
                    pass

        else:
            await message.channel.send("❌ Unknown command for King of Diamonds. Use `.num [0-100]`")
            return

        # If King of Diamonds game ended, remove it from active games
        if not player_game.game_active:
            # Find the correct game_id by matching the game object
            game_id_to_remove = None
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

    # Check for game commands in channels (needs to come BEFORE command processing)
    if not isinstance(message.channel, discord.DMChannel):
        # Handle guess commands for various games
        if message.content.startswith('.guess '):
            # First check for Combination game
            player_game = None
            game_type = None
            for game_id, game in active_games.items():
                if (message.author.id in game_id and game.game_active and
                        game_id[2] == "comb" and hasattr(game, 'awaiting_guesser') and
                        game.awaiting_guesser and game.guesser.id == message.author.id):
                    player_game = game
                    game_type = "comb"
                    break

            if player_game and game_type == "comb":
                # Handle Combination game guess
                cards = message.content[len('.guess '):].split()
                result = await player_game.process_guess(message.author, cards)

                if result:
                    await message.channel.send(result)
                else:
                    try:
                        await message.add_reaction('✅')
                    except:
                        pass

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

                return

            # Then check for Bloody Dotty game
            player_game = None
            game_type = None
            for game_id, game in active_games.items():
                if (message.author.id in game_id and game.game_active and
                        game_id[2] == "dotty" and hasattr(game, 'current_guesser') and
                        game.current_guesser.id == message.author.id and
                        len(game.awaiting_grabs) == 0):  # Only if both players have grabbed
                    player_game = game
                    game_type = "dotty"
                    break

            if player_game and game_type == "dotty":
                try:
                    guess = int(message.content[len('.guess '):].strip())
                except ValueError:
                    await message.channel.send("❌ Please provide a valid number between 2-20!")
                    return

                result = await player_game.process_guess(message.author, guess)
                await message.channel.send(result)

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

                return

        # Handle combo commands for Combination game in channel
        if message.content.startswith('.combo '):
            # Find if the author is in a Combination game
            player_game = None
            game_type = None
            for game_id, game in active_games.items():
                if (message.author.id in game_id and game.game_active and
                        game_id[2] == "comb" and hasattr(game, 'awaiting_maker')):
                    player_game = game
                    game_type = "comb"
                    break

            if player_game and game_type == "comb":
                # Check if user is the maker
                if player_game.maker.id != message.author.id:
                    await message.channel.send("❌ You're not the maker this round! Wait for your turn as guesser.")
                    return

                if not player_game.awaiting_maker:
                    await message.channel.send("❌ You've already submitted your combination for this round!")
                    return

                cards = message.content[len('.combo '):].split()
                result = await player_game.process_combo(message.author, cards)

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

                return

        # Handle Air Poker betting commands
        if (message.content.startswith('.fold') or
                message.content.startswith('.check') or
                message.content.startswith('.call') or
                message.content.startswith('.raise ')):

            # Find if the author is in an Air Poker game
            player_game = None
            game_type = None
            for game_id, game in active_games.items():
                if (message.author.id in game_id and game.game_active and
                        game_id[2] == "airpoker" and hasattr(game, 'betting_active') and
                        game.betting_active):
                    player_game = game
                    game_type = "airpoker"
                    break

            if player_game and game_type == "airpoker":
                content = message.content.strip()

                if content == '.fold':
                    result = await player_game.process_fold(message.author)

                elif content == '.check':
                    result = await player_game.process_check(message.author)

                elif content == '.call':
                    result = await player_game.process_call(message.author)

                elif content.startswith('.raise '):
                    amount_str = content[len('.raise '):].strip()
                    result = await player_game.process_raise(message.author, amount_str)

                else:
                    result = "❌ Unknown betting command!"

                # Check if the action was successful (result starts with ✅ or is None)
                if result is None or (isinstance(result, str) and result.startswith('✅')):
                    # If successful, add checkmark reaction
                    try:
                        await message.add_reaction('✅')
                    except:
                        pass

                    # If there's a success message with pot update, send it
                    if result and result.startswith('✅'):
                        await message.channel.send(result)
                else:
                    # If there's an error message, send it
                    await message.channel.send(result)

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

                return

        # Handle Knucklebones column commands in channel
        if message.content.startswith('.col '):
            # Find if the author is in a Knucklebones game
            player_game = None
            game_type = None
            for game_id, game in active_games.items():
                if (message.author.id in game_id and game.game_active and
                        game_id[2] == "kb" and hasattr(game, 'awaiting_column') and
                        game.awaiting_column):
                    player_game = game
                    game_type = "kb"
                    break

            if player_game and game_type == "kb":
                try:
                    column = int(message.content[len('.col '):].strip())
                except ValueError:
                    await message.channel.send("❌ Please provide a valid column number 1-3!")
                    return

                result = await player_game.process_col(message.author, column)

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

                return

    # Process DMs separately
    if isinstance(message.channel, discord.DMChannel):
        await process_dm_command(message)
        return

    # Process regular server commands
    await bot.process_commands(message)


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
