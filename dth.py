import discord
import random
from game_stats import record_game_result


class DropTheHandkerchiefGame:
    def __init__(self, player1, player2, channel):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel

        # Randomly assign first roles (50/50 chance)
        if random.choice([True, False]):
            self.dropper = player1
            self.checker = player2
        else:
            self.dropper = player2
            self.checker = player1

        self.dropped_number = None
        self.game_active = True
        self.round = 1
        self.penalties = {player1.id: 0, player2.id: 0}
        self.max_penalty = 300
        self.pending_check = None  # Store check move if made before drop

    async def start_game(self):
        """Initialize and start the game"""
        # Send DM instructions to both players
        instructions = (
            "**Drop the Handkerchief Game Started!**\n\n"
            "**How to play:**\n"
            "- Dropper: `.drop [1-60]` - choose when to drop the handkerchief (seconds)\n"
            "- Checker: `.check [1-60]` - choose when to look back (seconds)\n"
            "- If check is successful (C ≥ D): penalty = C - D\n"
            "- If check fails (C < D): penalty = 60\n"
            "- First to reach 300 seconds penalty loses!\n\n"
            f"You're playing against {self.checker.mention if self.dropper == self.player1 else self.player1.mention}\n"
            f"{self.dropper.mention} is the dropper first!"
        )

        try:
            await self.player1.send(instructions)
            await self.player2.send(instructions)
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start in channel
        await self.channel.send(
            f"🎮 **Drop the Handkerchief** game started between {self.player1.mention} and {self.player2.mention}!\n"
            f"Check your DMs for instructions. {self.dropper.mention} is the dropper first!"
        )

        return True

    async def process_drop(self, player, number):
        """Process a drop command"""
        if player != self.dropper:
            return "❌ It's not your turn to drop! Wait for your role as checker."

        # Check for leap second (round 18 only)
        max_number = 61 if self.round == 18 else 60

        if not (1 <= number <= max_number):
            return f"❌ Number must be between 1 and {max_number} seconds!"

        self.dropped_number = number

        # If there's a pending check, process it immediately
        if self.pending_check is not None:
            check_player, check_time = self.pending_check
            self.pending_check = None
            result = await self._calculate_results(check_time)
            # Send result to channel only
            await self.channel.send(result)
            return None  # No confirmation message, just reaction

        return None  # No confirmation message, just reaction

    async def process_check(self, player, check_time):
        """Process a check command"""
        if player != self.checker:
            return "❌ It's not your turn to check! Wait for your role as dropper."

        # Check for leap second (round 18 only)
        max_number = 61 if self.round == 18 else 60

        if not (1 <= check_time <= max_number):
            return f"❌ Check time must be between 1 and {max_number} seconds!"

        # If dropper has already dropped, calculate results immediately
        if self.dropped_number is not None:
            result = await self._calculate_results(check_time)
            # Send result to channel only
            await self.channel.send(result)
            return None  # No confirmation message, just reaction

        # Store the check move for when the dropper makes their move
        self.pending_check = (player, check_time)
        return None  # No confirmation message, just reaction

    async def _calculate_results(self, check_time):
        """Calculate and return game results"""
        # Check for leap second (round 18 allows 61)
        max_number = 61 if self.round == 18 else 60
        drop_time = self.dropped_number if self.dropped_number is not None else max_number + 1

        # Calculate penalty
        if check_time >= drop_time:
            # Successful check
            penalty = check_time - drop_time
            result_type = "SUCCESSFUL CHECK"
        else:
            # Failed check
            penalty = 60
            result_type = "FAILED CHECK"

        # Add penalty to checker
        self.penalties[self.checker.id] += penalty

        # Create result message
        result_message = (
            f"====**𝐃𝐫𝐨𝐩 𝐓𝐡𝐞 𝐇𝐚𝐧𝐝𝐤𝐞𝐫𝐜𝐡𝐢𝐞𝐟**====\n"
            f"**Round {self.round}** \n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
            f"{self.dropper.mention} dropped: {self.dropped_number}\n"
            f"{self.checker.mention} checked: {check_time}\n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
            f"**RESULT: {result_type}**\n"
            f"{self.checker.mention} accumulated: {penalty}\n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
            f"{self.player1.mention} ({self.penalties[self.player1.id]}/{self.max_penalty})\n"
            f"{self.player2.mention} ({self.penalties[self.player2.id]}/{self.max_penalty})"
        )

        # Check for game end
        if self.penalties[self.checker.id] >= self.max_penalty:
            winner = self.dropper  # The dropper wins when checker reaches max penalty
            result_message += f"\n\n🏆 **GAME OVER!** {winner.mention} wins!\n{self.checker.mention} reached 300 seconds penalty!"
            self.game_active = False

            # Record game result
            # Determine result code: 1 = player1 won, 2 = player2 won
            if winner.id == self.player1.id:
                result_code = 1
            else:
                result_code = 2
            record_game_result('dth', self.player1.id, self.player2.id, result_code)

            return result_message

        # Switch roles for next round
        self.dropper, self.checker = self.checker, self.dropper
        self.dropped_number = None
        self.pending_check = None
        self.round += 1

        result_message += f"\n\n🔄 **Round {self.round}** - {self.dropper.mention} is now the dropper!"

        return result_message
