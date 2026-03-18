import discord
import random
from game_stats import record_game_result

class KnucklebonesGame:
    def __init__(self, player1, player2, channel):
        self.players = [player1, player2]
        self.channel = channel
        self.game_active = True

        # Game state
        self.current_player_index = random.randint(0, 1)
        self.current_roll = None
        self.awaiting_column = False

        # Player matrices (3x3 grids)
        # Top player (player1) - numbers "fall down"
        # Bottom player (player2) - numbers "float up"
        self.matrices = {
            player1.id: [[None, None, None], [None, None, None], [None, None, None]],
            player2.id: [[None, None, None], [None, None, None], [None, None, None]]
        }

        # Track which rows/columns are filled
        self.filled_slots = {
            player1.id: [0, 0, 0],  # Number of filled slots in each column (top matrix fills from bottom)
            player2.id: [0, 0, 0]  # Number of filled slots in each column (bottom matrix fills from top)
        }

    async def start_game(self):
        """Initialize and start the game"""
        # Start first turn - this will send the initial game state
        await self._start_turn()
        return True

    async def _start_turn(self):
        """Start a new turn"""
        current_player = self.players[self.current_player_index]
        self.current_roll = random.randint(1, 6)
        self.awaiting_column = True

        # Send game state with roll information
        game_state = await self._get_game_state()
        await self.channel.send(
            f"***===== 🎲 Knucklebones 🎲 =====***\n"
            f"{current_player.mention} rolls a {self._get_dice_emoji(self.current_roll)}\n"
            f"Choose a column to place it\n\n"
            f"{game_state}"
        )

    async def process_col(self, player, column):
        """Process a column command"""
        if not self.awaiting_column:
            return "❌ It's not your turn or no dice has been rolled!"

        current_player = self.players[self.current_player_index]
        if player.id != current_player.id:
            return "❌ It's not your turn!"

        if column < 1 or column > 3:
            return "❌ Column must be 1, 2, or 3!"

        column_index = column - 1

        # Check if column is full
        if self.filled_slots[current_player.id][column_index] >= 3:
            return "❌ That column is already full!"

        # Place the number
        success = await self._place_number(current_player.id, column_index, self.current_roll)
        if not success:
            return "❌ Could not place number in that column!"

        # Apply elimination to opponent
        opponent_id = self.players[1 - self.current_player_index].id
        eliminated = await self._eliminate_opponent_numbers(opponent_id, column_index, self.current_roll)

        # Check for game end
        game_ended, winner = await self._check_game_end()

        # Send result message
        result_message = ""

        if game_ended:
            if winner:
                result_message += f"🎊 **GAME OVER!** {winner.mention} wins!\n\n"
                # Record game result
                if winner.id == self.players[0].id:
                    result_code = 1
                else:
                    result_code = 2
                record_game_result('kb', self.players[0].id, self.players[1].id, result_code)
            else:
                result_message += f"🎊 **GAME OVER!** It's a tie!\n\n"
                # Record game result - draw
                record_game_result('kb', self.players[0].id, self.players[1].id, 0)
            result_message += await self._get_game_state()
            self.game_active = False
            await self.channel.send(result_message)
            return None
        else:
            # Switch to next player and start next turn
            self.current_player_index = 1 - self.current_player_index
            next_player = self.players[self.current_player_index]
            self.current_roll = random.randint(1, 6)

            result_message = (
                f"***===== 🎲 Knucklebones 🎲 =====***\n"
                f"{next_player.mention} rolls a {self._get_dice_emoji(self.current_roll)}\n"
                f"Choose a column to place it\n\n"
            )

            result_message += await self._get_game_state()
            await self.channel.send(result_message)

        return None

    async def _place_number(self, player_id, column, number):
        """Place a number in the player's matrix"""
        filled_count = self.filled_slots[player_id][column]

        if filled_count >= 3:
            return False

        if player_id == self.players[0].id:  # Top player - fill from bottom
            row = 2 - filled_count  # Fill bottom to top: row 2, then 1, then 0
        else:  # Bottom player - fill from top
            row = filled_count  # Fill top to bottom: row 0, then 1, then 2

        self.matrices[player_id][row][column] = number
        self.filled_slots[player_id][column] += 1
        return True

    async def _eliminate_opponent_numbers(self, opponent_id, column, number):
        """Eliminate matching numbers from opponent's column"""
        eliminated_count = 0
        matrix = self.matrices[opponent_id]

        # Find and remove matching numbers
        for row in range(3):
            if matrix[row][column] == number:
                matrix[row][column] = None
                eliminated_count += 1

        if eliminated_count > 0:
            # Reorganize the column to remove gaps
            if opponent_id == self.players[0].id:  # Top player - numbers should fall down
                # Move numbers down to fill gaps
                col_numbers = [matrix[row][column] for row in range(3)]
                col_numbers = [num for num in col_numbers if num is not None]  # Remove None
                col_numbers = [None] * (3 - len(col_numbers)) + col_numbers  # Add None to top
                for row in range(3):
                    matrix[row][column] = col_numbers[row]
            else:  # Bottom player - numbers should float up
                # Move numbers up to fill gaps
                col_numbers = [matrix[row][column] for row in range(3)]
                col_numbers = [num for num in col_numbers if num is not None]  # Remove None
                col_numbers = col_numbers + [None] * (3 - len(col_numbers))  # Add None to bottom
                for row in range(3):
                    matrix[row][column] = col_numbers[row]

            # Update filled count
            self.filled_slots[opponent_id][column] = sum(1 for row in range(3) if matrix[row][column] is not None)

        return eliminated_count

    async def _check_game_end(self):
        """Check if the game has ended"""
        for player in self.players:
            if sum(self.filled_slots[player.id]) >= 9:  # All slots filled
                scores = await self._calculate_scores()
                if scores[self.players[0].id] > scores[self.players[1].id]:
                    return True, self.players[0]
                elif scores[self.players[1].id] > scores[self.players[0].id]:
                    return True, self.players[1]
                else:
                    return True, None  # Tie
        return False, None

    async def _calculate_scores(self):
        """Calculate scores for both players"""
        scores = {}
        for player in self.players:
            total_score = 0
            matrix = self.matrices[player.id]

            # Calculate score for each column
            for col in range(3):
                numbers = [matrix[row][col] for row in range(3) if matrix[row][col] is not None]
                if not numbers:
                    continue

                # Pad with zeros if needed for scoring
                while len(numbers) < 3:
                    numbers.append(0)

                a, b, c = numbers

                if a == b == c:
                    total_score += 9 * a
                elif a == b:
                    total_score += 4 * a + c
                elif a == c:
                    total_score += 4 * a + b
                elif b == c:
                    total_score += 4 * b + a
                else:
                    total_score += a + b + c

            scores[player.id] = total_score

        return scores

    async def _get_game_state(self):
        """Get the current game state as a formatted string"""
        scores = await self._calculate_scores()

        # Build the display
        display_lines = []

        # Player 1 (top) matrix
        p1_matrix = self.matrices[self.players[0].id]
        p1_scores = await self._get_column_scores(self.players[0].id)

        # Player 2 (bottom) matrix
        p2_matrix = self.matrices[self.players[1].id]
        p2_scores = await self._get_column_scores(self.players[1].id)

        # Build the grid display
        for row in range(3):
            line = ""
            for col in range(3):
                num = p1_matrix[row][col]
                line += self._get_number_emoji(num) + " "
            if row == 1:
                line += f" {self.players[0].mention}"
            display_lines.append(line)

        # Score line for player 1
        p1_total = scores[self.players[0].id]
        display_lines.append(f"`{p1_scores[0]:2} {p1_scores[1]:2} {p1_scores[2]:2} = {p1_total:2}`")

        # Separator
        display_lines.append("")

        # Score line for player 2
        p2_total = scores[self.players[1].id]
        display_lines.append(f"`{p2_scores[0]:2} {p2_scores[1]:2} {p2_scores[2]:2} = {p2_total:2}`")

        # Player 2 matrix
        for row in range(3):
            line = ""
            for col in range(3):
                num = p2_matrix[row][col]
                line += self._get_number_emoji(num) + " "
            if row == 1:
                line += f" {self.players[1].mention}"
            display_lines.append(line)

        return "\n".join(display_lines)

    async def _get_column_scores(self, player_id):
        """Calculate individual column scores for a player"""
        matrix = self.matrices[player_id]
        column_scores = []

        for col in range(3):
            numbers = [matrix[row][col] for row in range(3) if matrix[row][col] is not None]
            if not numbers:
                column_scores.append(0)
                continue

            # Pad with zeros if needed for scoring
            while len(numbers) < 3:
                numbers.append(0)

            a, b, c = numbers

            if a == b == c:
                column_scores.append(9 * a)
            elif a == b:
                column_scores.append(4 * a + c)
            elif a == c:
                column_scores.append(4 * a + b)
            elif b == c:
                column_scores.append(4 * b + a)
            else:
                column_scores.append(a + b + c)

        return column_scores

    def _get_dice_emoji(self, number):
        """Get emoji for dice number"""
        emojis = {
            1: ":one:",
            2: ":two:",
            3: ":three:",
            4: ":four:",
            5: ":five:",
            6: ":six:"
        }
        return emojis.get(number, f"{number}")

    def _get_number_emoji(self, number):
        """Get emoji for matrix number or empty slot"""
        if number is None:
            return ":small_blue_diamond:"
        emojis = {
            1: ":one:",
            2: ":two:",
            3: ":three:",
            4: ":four:",
            5: ":five:",
            6: ":six:"
        }
        return emojis.get(number, f"{number}")
