import discord
import random
from game_stats import record_game_result


class BloodyDottyGame:
    def __init__(self, player1, player2, channel):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.game_active = True

        # Player numbers (what they grabbed)
        self.numbers = {player1.id: None, player2.id: None}
        self.awaiting_grabs = [player1.id, player2.id]

        # Randomly assign first guesser (Player X) and second player (Player Y)
        if random.choice([True, False]):
            self.player_x = player1
            self.player_y = player2
            self.current_guesser = player1
            self.other_player = player2
        else:
            self.player_x = player2
            self.player_y = player1
            self.current_guesser = player2
            self.other_player = player1

        # Initialize the table of possible sums
        self.initialize_table()

    def initialize_table(self):
        """Initialize the table of possible sums"""
        self.table = [[i + j for j in range(1, 11)] for i in range(1, 11)]
        self.possible = [[True for _ in range(10)] for _ in range(10)]

    def format_table(self):
        """Format the table for display"""
        lines = []
        # Header row
        header = "Y\\X   " + "  ".join(f"{i}" for i in range(1, 10)) + " 10\n"
        lines.append(header)

        # Data rows
        for i in range(10):
            row_num = i + 1
            row = f"{row_num:2}   "
            for j in range(10):
                if self.possible[i][j]:
                    row += f"{self.table[i][j]:2} "
                else:
                    row += " - "
            lines.append(row)

        return "```\n" + "\n".join(lines) + "\n```"

    def update_table_after_guess(self, guess, guesser_is_x):
        """Update the table after an incorrect guess"""
        if guesser_is_x:
            # Guesser is player X (columns represent their number)
            # Remove all cells with the guessed sum AND columns where X >= guess
            for i in range(10):  # rows (Y)
                for j in range(10):  # columns (X)
                    if self.table[i][j] == guess or (j + 1) > (guess - 1) or (j + 1) < (guess - 10):
                        self.possible[i][j] = False
        else:
            # Guesser is player Y (rows represent their number)
            # Remove all cells with the guessed sum AND rows where Y <= (guess - 11)
            # Since max sum is 20, if Y guesses S, then Y <= S - 11 would make sum impossible
            for i in range(10):  # rows (Y)
                for j in range(10):  # columns (X)
                    if self.table[i][j] == guess or (i + 1) > (guess - 1) or (i + 1) < (guess - 10):
                        self.possible[i][j] = False

    def is_valid_guess(self, guess, player):
        """Check if a guess is valid given the player's number"""
        player_number = self.numbers[player.id]
        min_possible = 1 + player_number
        max_possible = 10 + player_number
        return min_possible <= guess <= max_possible

    async def start_game(self):
        """Initialize and start the game"""
        instructions = (
            "**Bloody Dotty Game Started!**\n\n"
            "**How to play:**\n"
            "- Both players grab 1-10 marbles using `.grab [1-10]` in DMs\n"
            "- Then take turns guessing the total sum (2-20)\n"
            "- You can't guess sums that are impossible given your number\n"
            "- First to guess the correct sum wins!\n\n"
            f"You're playing against {self.other_player.mention}\n"
            f"{self.current_guesser.mention} is Player X and will guess first!"
        )

        try:
            await self.player1.send(instructions)
            await self.player2.send(instructions)
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start
        await self.channel.send(
            f"🎯 **Bloody Dotty** game started between {self.player1.mention} and {self.player2.mention}!\n"
            f"Both players should grab 1-10 marbles using `.grab [number]` in my DMs.\n"
            f"{self.current_guesser.mention} is Player X and will guess first!\n"
            f"{self.other_player.mention} is Player Y."
        )

        return True

    async def process_grab(self, player, number):
        """Process a grab command"""
        if player.id not in self.awaiting_grabs:
            return "❌ You've already grabbed your marbles!"

        if not (1 <= number <= 10):
            return "❌ Number must be between 1 and 10!"

        self.numbers[player.id] = number
        self.awaiting_grabs.remove(player.id)

        # Check if both players have grabbed
        if len(self.awaiting_grabs) == 0:
            await self.channel.send(
                f"🎯 Both players have grabbed their marbles!\n"
                f"{self.current_guesser.mention} (Player X) starts guessing. Use `.guess [sum]` in this channel.\n\n"
                f"Initial Table of Possible Sums:\n{self.format_table()}"
            )

        return None  # No confirmation message, just reaction

    async def process_guess(self, player, guess):
        """Process a guess command"""
        if player != self.current_guesser:
            return "❌ It's not your turn to guess!"

        if not (2 <= guess <= 20):
            return "❌ Guess must be between 2 and 20!"

        # Check if guess is valid given player's number
        if not self.is_valid_guess(guess, player):
            player_number = self.numbers[player.id]
            min_possible = 1 + player_number
            max_possible = 10 + player_number

            # Player loses immediately for guessing an impossible sum
            winner = self.other_player  # The other player wins when someone makes an illegal guess
            result_message = (
                f"🎯 **Bloody Dotty - Guess Result**\n"
                f"{player.mention} guessed: **{guess}**\n"
                f"💀 **ILLEGAL GUESS!** {player.mention} loses the game!\n"
                f"With your number {player_number}, you can only guess between {min_possible} and {max_possible}.\n\n"
                f"Actual numbers: {self.player_x.mention} (X) had {self.numbers[self.player_x.id]}, "
                f"{self.player_y.mention} (Y) had {self.numbers[self.player_y.id]}\n\n"
                f"Final Table:\n{self.format_table()}"
            )
            self.game_active = False

            # Record game result
            if winner.id == self.player1.id:
                result_code = 1
            else:
                result_code = 2
            record_game_result('dotty', self.player1.id, self.player2.id, result_code)

            return result_message

        # Determine if guesser is player X or Y
        guesser_is_x = (player == self.player_x)

        # Get the actual sum
        actual_sum = self.numbers[self.player1.id] + self.numbers[self.player2.id]

        if guess == actual_sum:
            # Correct guess - game over
            winner = player
            result_message = (
                f"🎯 **Bloody Dotty - Guess Result**\n"
                f"{player.mention} guessed: **{guess}**\n"
                f"🎉 **CORRECT!** {player.mention} wins!\n"
                f"Actual numbers: {self.player_x.mention} (X) had {self.numbers[self.player_x.id]}, "
                f"{self.player_y.mention} (Y) had {self.numbers[self.player_y.id]}\n\n"
                f"Final Table:\n{self.format_table()}"
            )
            self.game_active = False

            # Record game result
            if winner.id == self.player1.id:
                result_code = 1
            else:
                result_code = 2
            record_game_result('dotty', self.player1.id, self.player2.id, result_code)

        else:
            # Incorrect guess - update table and switch turns
            self.update_table_after_guess(guess, guesser_is_x)

            # Switch turns
            self.current_guesser, self.other_player = self.other_player, self.current_guesser

            result_message = (
                f"🎯 **Bloody Dotty - Guess Result**\n"
                f"{player.mention} guessed: **{guess}**\n"
                f"❌ **INCORRECT!**\n\n"
                f"Updated Table of Possible Sums:\n{self.format_table()}\n"
                f"Next to guess: {self.current_guesser.mention}"
            )

        return result_message
