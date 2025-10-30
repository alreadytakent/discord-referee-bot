import discord
from game_stats import record_kod_game_result


class KingOfDiamondsGame:
    def __init__(self, players, channel):
        self.players = players
        self.channel = channel
        self.game_active = True
        self.round = 1

        # Player HP tracking
        self.hp = {player.id: 5 for player in players}
        self.eliminated_players = set()

        # Current round state
        self.current_numbers = {player.id: None for player in players}
        self.awaiting_numbers = [player.id for player in players]

    async def start_game(self):
        """Initialize and start the game"""
        player_mentions = " ".join(player.mention for player in self.players)

        instructions = (
            "**King of Diamonds Game Started!**\n\n"
            "**How to play:**\n"
            "- Each round, choose a number 0-100 using `.num [number]` in DMs\n"
            "- Target = 0.8 × average of all numbers\n"
            "- Closest to target wins, others lose 1 HP\n"
            "- Last player standing wins!\n"
            "- Special rules activate at 4, 3, and 2 players\n\n"
            f"Players: {player_mentions}"
        )

        try:
            for player in self.players:
                await player.send(
                    f"**King of Diamonds Game Started!**\n\n"
                    f"Use `.num [0-100]` each round to choose your number.\n"
                    f"Starting HP: 5\n"
                    f"Good luck!"
                )
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start in channel
        await self.channel.send(
            f"👑 **King of Diamonds** game started with {len(self.players)} players!\n"
            f"Players: {player_mentions}\n"
            f"Check your DMs for instructions. All players should choose a number now!"
        )

        return True

    async def process_num(self, player, number):
        """Process a number command"""
        if player.id not in self.awaiting_numbers:
            return "❌ You've already chosen a number for this round!"

        if not (0 <= number <= 100):
            return "❌ Number must be between 0 and 100!"

        self.current_numbers[player.id] = number
        self.awaiting_numbers.remove(player.id)

        # Check if all active players have chosen numbers
        if len(self.awaiting_numbers) == 0:
            result = await self._resolve_round()
            await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    async def _resolve_round(self):
        """Resolve the current round and determine winner"""
        active_players = [p for p in self.players if p.id not in self.eliminated_players]
        active_numbers = {p.id: self.current_numbers[p.id] for p in active_players}
        remaining_players = len(active_players)

        # Calculate target number
        numbers_list = list(active_numbers.values())
        average = sum(numbers_list) / len(numbers_list)
        target = 0.8 * average

        winners = []  # Changed to support multiple winners
        double_penalty = False
        exact_match = False

        # Step 1: Always check 4-player rule first (duplicate numbers) when 4 or fewer players
        if remaining_players <= 4:
            duplicates = self._find_duplicate_numbers(active_numbers)
            if duplicates:
                # Players with duplicate numbers are eliminated from winning
                valid_players = {pid: num for pid, num in active_numbers.items() if pid not in duplicates}

                # Special case: If all players have duplicates, no winner
                if not valid_players:
                    winners = []
                elif len(valid_players) >= 1:
                    # Find winners among non-duplicate players (can be multiple if tied)
                    winner_ids = self._find_closest_to_target(valid_players, target)
                    winners = [p for p in active_players if p.id in winner_ids]

        # Step 2: If no winners from 4-player rule AND there are valid players left, check other rules
        if not winners and remaining_players >= 2:
            # Only proceed if there are players eligible to win (not all eliminated by duplicates)
            eligible_players = active_players
            if remaining_players <= 4:
                duplicates = self._find_duplicate_numbers(active_numbers)
                eligible_players = [p for p in active_players if p.id not in duplicates]

            # If there are eligible players, check other rules
            if eligible_players:
                # Step 2a: Check 2-player rule (only when exactly 2 players remain)
                if remaining_players == 2:
                    p1, p2 = active_players
                    num1, num2 = active_numbers[p1.id], active_numbers[p2.id]

                    if (num1 == 0 and num2 == 100):
                        winners = [p2]
                    elif (num1 == 100 and num2 == 0):
                        winners = [p1]

                # Step 2b: If no winners from 2-player rule, check 3-player rule (perfect guesses)
                if not winners and remaining_players <= 3:
                    rounded_target = round(target)
                    exact_matches = [pid for pid, num in active_numbers.items() if num == rounded_target]

                    if len(exact_matches) == 1:
                        # Single exact match - they win with double penalty
                        winners = [p for p in active_players if p.id == exact_matches[0]]
                        double_penalty = True
                        exact_match = True
                    elif len(exact_matches) > 1:
                        # Multiple exact matches - they all lose (4-player rule applies again)
                        valid_players = {pid: num for pid, num in active_numbers.items() if pid not in exact_matches}
                        if valid_players:
                            winner_ids = self._find_closest_to_target(valid_players, target)
                            winners = [p for p in active_players if p.id in winner_ids]
                        else:
                            winners = []

        # Step 3: If still no winners AND there are eligible players, use default rule (closest to target)
        if not winners and remaining_players >= 2:
            # Check if there are players eligible to win (not all eliminated by previous rules)
            eligible_players_dict = active_numbers
            if remaining_players <= 4:
                duplicates = self._find_duplicate_numbers(active_numbers)
                eligible_players_dict = {pid: num for pid, num in active_numbers.items() if pid not in duplicates}

            # Also exclude players eliminated by exact match rule
            if remaining_players <= 3:
                rounded_target = round(target)
                exact_matches = [pid for pid, num in active_numbers.items() if num == rounded_target]
                if len(exact_matches) > 1:
                    eligible_players_dict = {pid: num for pid, num in eligible_players_dict.items() if
                                             pid not in exact_matches}

            # Only find winners if there are eligible players left
            if eligible_players_dict:
                winner_ids = self._find_closest_to_target(eligible_players_dict, target)
                winners = [p for p in active_players if p.id in winner_ids]

        # Apply penalties and check for eliminations
        self._apply_penalties(active_players, winners, double_penalty)

        return await self._create_round_message(active_players, active_numbers, target, winners, exact_match)

    def _find_duplicate_numbers(self, numbers_dict):
        """Find players who chose duplicate numbers"""
        value_count = {}
        for num in numbers_dict.values():
            value_count[num] = value_count.get(num, 0) + 1

        duplicates = set()
        for player_id, number in numbers_dict.items():
            if value_count[number] > 1:
                duplicates.add(player_id)

        return duplicates

    def _find_closest_to_target(self, numbers_dict, target):
        """Find players whose number is closest to target (can be multiple)"""
        closest_players = []
        closest_diff = float('inf')

        for player_id, number in numbers_dict.items():
            diff = abs(number - target)
            if diff < closest_diff:
                closest_diff = diff
                closest_players = [player_id]
            elif diff == closest_diff:
                # Tie - both players win
                closest_players.append(player_id)

        return closest_players

    def _apply_penalties(self, active_players, winners, double_penalty=False):
        """Apply HP penalties to losers"""
        penalty = 2 if double_penalty else 1

        # Special case: if all players had duplicates and no winners, everyone loses HP
        if not winners and len(active_players) > 0:
            for player in active_players:
                self.hp[player.id] -= penalty
                if self.hp[player.id] <= 0:
                    self.hp[player.id] = 0
                    self.eliminated_players.add(player.id)
        else:
            # Normal case: winners don't lose HP, losers do
            for player in active_players:
                if player not in winners:
                    self.hp[player.id] -= penalty
                    if self.hp[player.id] <= 0:
                        self.hp[player.id] = 0
                        self.eliminated_players.add(player.id)

    async def _create_round_message(self, active_players, active_numbers, target, winners, exact_match=False):
        """Create the round result message"""
        # Build numbers display
        numbers_display = []
        for player in active_players:
            hp_display = "❤️" * self.hp[player.id] + "💔" * (5 - self.hp[player.id])
            numbers_display.append(f"{hp_display} {player.mention}: {active_numbers[player.id]}")

        numbers_text = "\n".join(numbers_display)

        # Find duplicate players for the message
        duplicate_players = []
        if len(active_players) <= 4:
            duplicates = self._find_duplicate_numbers(active_numbers)
            if duplicates:
                duplicate_players = [p for p in active_players if p.id in duplicates]

        # Create result message
        result_message = (
            f"***===== 👑 King of Diamonds - Round {self.round} 👑 =====***\n\n"
            f"Numbers chosen:\n{numbers_text}\n\n"
            f"Target: {target:.2f}\n"
        )

        # Add duplicate player message if applicable
        if duplicate_players and len(duplicate_players) < len(active_players):
            duplicate_mentions = " ".join(player.mention for player in duplicate_players)
            result_message += f"🚫 {duplicate_mentions} lose{'s' if len(duplicate_players) == 1 else ''} the round due to choosing the same number.\n\n"

        if winners:
            if exact_match:
                winner_mentions = " ".join(winner.mention for winner in winners)
                result_message += f"🎯 **EXACT MATCH!** {winner_mentions} {'wins' if len(winners) == 1 else 'win'} with perfect guess!\n"
                result_message += f"💔 All other players lose **2 HP**!\n"
            else:
                winner_mentions = " ".join(winner.mention for winner in winners)
                result_message += f"🏆 {winner_mentions} win{'s' if len(winners) == 1 else ''} the round!\n"
                result_message += f"💔 All other players lose 1 HP!\n"
        else:
            if duplicate_players and len(duplicate_players) == len(active_players):
                # All players had duplicates
                result_message += f"🚫 All players chose duplicate numbers!\n"
            result_message += f"🤝 **No winners! Everyone loses 1 HP!**\n"

        # Check for eliminations
        eliminated_this_round = []
        for player in active_players:
            if self.hp[player.id] <= 0 and player not in winners:
                eliminated_this_round.append(player.mention)

        if eliminated_this_round:
            result_message += f"\n💀 **Eliminated:** {', '.join(eliminated_this_round)}\n"

        # Check for game end
        remaining_players = [p for p in self.players if p.id not in self.eliminated_players]
        if len(remaining_players) <= 1:
            if len(remaining_players) == 1:
                winner = remaining_players[0]
                result_message += f"\n🎊 **GAME OVER!** {winner.mention} is the King of Diamonds! 👑"

                # Record game result - single winner
                winner_index = self.players.index(winner)
                record_kod_game_result(self.players, winner_index)

            else:
                result_message += f"\n🎊 **GAME OVER!** It's a tie! No king today."

                # Record game result - draw (only between active players who survived to the end)
                # Get indices of players who were still active when the game ended
                drawn_player_indices = [self.players.index(player) for player in active_players]
                record_kod_game_result(self.players, -1, drawn_player_indices)

            self.game_active = False
        else:
            # Prepare for next round
            self.round += 1
            self.current_numbers = {player.id: None for player in self.players}
            self.awaiting_numbers = [p.id for p in self.players if p.id not in self.eliminated_players]
            result_message += f"\n**Round {self.round} begins!** Choose your numbers."

        return result_message
