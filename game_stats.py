import sqlite3
import json
import discord


# Database setup for 1v1 games
def init_database():
    """Initialize the SQLite database for 1v1 games"""
    conn = sqlite3.connect('game_results.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_type TEXT NOT NULL,
            player1_id TEXT NOT NULL,
            player2_id TEXT NOT NULL,
            result INTEGER NOT NULL  -- 0: draw, 1: player1 won, 2: player2 won
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player1 ON games(player1_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_player2 ON games(player2_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_game_type ON games(game_type)')

    conn.commit()
    conn.close()


# Database setup for KOD games
def init_kod_database():
    """Initialize the SQLite database for KOD games"""
    conn = sqlite3.connect('kod_results.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kod_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            players_id TEXT NOT NULL,  -- JSON array of all player IDs
            result INTEGER NOT NULL,   -- index of winner in players list (0-based), -1 if draw
            drawn_players TEXT         -- JSON array of player indexes who drew (if result = -1)
        )
    ''')

    # Create index for faster player lookups
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_kod_players ON kod_games(players_id)')

    conn.commit()
    conn.close()


# Initialize databases when module loads
init_database()
init_kod_database()


def record_game_result(game_type, player1_id, player2_id, result):
    """Record a 1v1 game result in the database"""
    conn = sqlite3.connect('game_results.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO games (game_type, player1_id, player2_id, result)
        VALUES (?, ?, ?, ?)
    ''', (game_type, str(player1_id), str(player2_id), result))

    conn.commit()
    conn.close()


def record_kod_game_result(players, winner_index, drawn_players=None):
    """Record a KOD game result in the database"""
    conn = sqlite3.connect('kod_results.db')
    cursor = conn.cursor()

    players_json = json.dumps([str(p.id) for p in players])
    drawn_players_json = json.dumps(drawn_players) if drawn_players else None

    cursor.execute('''
        INSERT INTO kod_games (players_id, result, drawn_players)
        VALUES (?, ?, ?)
    ''', (players_json, winner_index, drawn_players_json))

    conn.commit()
    conn.close()


async def get_player_stats(player_id):
    """Get overall statistics for a player (excluding KOD)"""
    conn = sqlite3.connect('game_results.db')
    cursor = conn.cursor()

    query = '''
        SELECT game_type,
               COUNT(*) as total,
               SUM(CASE 
                   WHEN (player1_id = ? AND result = 1) OR (player2_id = ? AND result = 2) THEN 1 
                   ELSE 0 
               END) as wins,
               SUM(CASE WHEN result = 0 THEN 1 ELSE 0 END) as draws,
               SUM(CASE 
                   WHEN (player1_id = ? AND result = 2) OR (player2_id = ? AND result = 1) THEN 1 
                   ELSE 0 
               END) as losses
        FROM games 
        WHERE player1_id = ? OR player2_id = ?
        GROUP BY game_type
        ORDER BY game_type
    '''

    cursor.execute(query,
                   (str(player_id), str(player_id), str(player_id), str(player_id), str(player_id), str(player_id)))
    results = cursor.fetchall()
    conn.close()

    return results


async def get_kod_player_stats(player_id):
    """Get KOD statistics for a player"""
    conn = sqlite3.connect('kod_results.db')
    cursor = conn.cursor()

    cursor.execute('SELECT players_id, result, drawn_players FROM kod_games')
    all_kod_games = cursor.fetchall()
    conn.close()

    wins = 0
    draws = 0
    losses = 0

    for players_json, result, drawn_players_json in all_kod_games:
        players = json.loads(players_json)
        player_str_id = str(player_id)

        if player_str_id in players:
            player_index = players.index(player_str_id)

            if result == -1:  # Draw
                drawn_players = json.loads(drawn_players_json) if drawn_players_json else []
                if player_index in drawn_players:
                    draws += 1
                else:
                    losses += 1
            else:  # Someone won
                if result == player_index:
                    wins += 1
                else:
                    losses += 1

    # Return None if player has no KOD games at all
    if wins == 0 and draws == 0 and losses == 0:
        return None

    return wins, draws, losses


async def get_head_to_head_stats(player1_id, player2_id):
    """Get statistics for 1v1 games between two specific players"""
    conn = sqlite3.connect('game_results.db')
    cursor = conn.cursor()

    query = '''
        SELECT game_type,
               COUNT(*) as total,
               SUM(CASE 
                   WHEN (player1_id = ? AND player2_id = ? AND result = 1) OR 
                        (player1_id = ? AND player2_id = ? AND result = 2) THEN 1 
                   ELSE 0 
               END) as wins1,
               SUM(CASE 
                   WHEN (player1_id = ? AND player2_id = ? AND result = 2) OR 
                        (player1_id = ? AND player2_id = ? AND result = 1) THEN 1 
                   ELSE 0 
               END) as wins2,
               SUM(CASE WHEN result = 0 THEN 1 ELSE 0 END) as draws
        FROM games 
        WHERE (player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?)
        GROUP BY game_type
        ORDER BY game_type
    '''

    cursor.execute(query, (
        str(player1_id), str(player2_id), str(player2_id), str(player1_id),
        str(player1_id), str(player2_id), str(player2_id), str(player1_id),
        str(player1_id), str(player2_id), str(player2_id), str(player1_id)
    ))
    results = cursor.fetchall()
    conn.close()

    return results


async def get_kod_head_to_head_stats(player1_id, player2_id):
    """Get KOD statistics for games where both players participated"""
    conn = sqlite3.connect('kod_results.db')
    cursor = conn.cursor()

    cursor.execute('SELECT players_id, result, drawn_players FROM kod_games')
    all_kod_games = cursor.fetchall()
    conn.close()

    wins1 = 0
    wins2 = 0
    draws = 0

    for players_json, result, drawn_players_json in all_kod_games:
        players = json.loads(players_json)
        player1_str = str(player1_id)
        player2_str = str(player2_id)

        # Only count games where both players participated
        if player1_str in players and player2_str in players:
            player1_index = players.index(player1_str)
            player2_index = players.index(player2_str)

            if result == -1:  # Draw
                drawn_players = json.loads(drawn_players_json) if drawn_players_json else []
                if player1_index in drawn_players and player2_index in drawn_players:
                    draws += 1
            else:  # Someone won
                if result == player1_index:
                    wins1 += 1
                elif result == player2_index:
                    wins2 += 1

    return wins1, wins2, draws


async def extract_user_from_mention(bot, ctx, mention):
    """Extract user object from mention string"""
    # Remove <@ and > from mention
    clean_mention = mention.strip().replace('<@', '').replace('>', '')

    try:
        user_id = int(clean_mention)
        user = await bot.fetch_user(user_id)
        return user
    except (ValueError, discord.NotFound):
        # Try to find by username
        for member in ctx.guild.members:
            if member.mention == mention or member.name.lower() == mention.lower():
                return member
    return None


def get_game_display_name(game_type):
    """Convert game type code to display name"""
    names = {
        'dth': 'DTH',
        'mdth': 'MDTH',
        'gops': 'GOPS',
        'dotty': 'Dotty',
        'comb': 'Combination',
        'airpoker': 'Air Poker',
        'kb': 'Knucklebones',
        'contr': 'Contradiction'
    }
    return names.get(game_type, game_type)
