import discord
import random

class AirPokerGame:

    def __init__(self, player1, player2, channel, show_table=True):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.game_active = True
        self.round = 1
        self.total_rounds = 5
        self.show_table = show_table

        # Player bios (chips)
        self.bios = {player1.id: 25, player2.id: 25}

        # Generate numbers for both players
        self.numbers = self.generate_numbers()
        self.player1_numbers = self.numbers[:5]
        self.player2_numbers = self.numbers[5:]

        # Current round state
        self.current_plays = {player1.id: None, player2.id: None}
        self.awaiting_plays = [player1.id, player2.id]
        self.round_winner = None
        self.tie = False
        self.result = None

        # Set first player randomly for the entire game
        self.first_player = None

        # Track used numbers
        self.used_numbers = {player1.id: [], player2.id: []}

        # Poker phase variables (now comes BEFORE betting)
        self.poker_active = False
        self.player_hands = {player1.id: None, player2.id: None}
        self.awaiting_hands = []
        self.deck = self.initialize_deck()
        self.hand_attempts = 0

        # Betting phase variables (now comes AFTER poker)
        self.betting_active = False
        self.current_player = None
        self.pot = 0
        self.current_bets = {player1.id: 0, player2.id: 0}
        self.total_bets = {player1.id: 0, player2.id: 0}
        self.last_raise_amount = 0
        # self.betting_history = []

    def initialize_deck(self):
        """Initialize a full deck of 52 cards"""
        deck = []
        suits = ['s', 'h', 'd', 'c']
        values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        for suit in suits:
            for value in values:
                deck.append(f"{value}{suit}")
        return deck

    def format_deck_display(self):
        """Format the remaining deck for display"""
        suits = {'c': 'Clubs    |', 'd': 'Diamonds |', 'h': 'Hearts   |', 's': 'Spades   |'}
        value_order = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

        lines = ["Remaining cards:"]
        for suit_code, suit_name in suits.items():
            line = f"{suit_name} "
            for value in value_order:
                card = f"{value}{suit_code}"
                if card in self.deck:
                    line += f" {value}"
                elif value == '10':
                    line += " --"
                else:
                    line += " -"
            lines.append(line)

        return "```\n" + "\n".join(lines) + "\n```"

    def generate_numbers(self):
        """Generate 10 unique numbers between 6-64 with sum between 338-362, including lucky numbers"""
        lucky_numbers = [15, 20, 25, 30, 35, 40, 45, 50, 55, 47]

        while True:
            # Start with the required lucky numbers
            numbers = []

            # Select 2 different lucky numbers
            selected_lucky = random.sample(lucky_numbers, 2)
            numbers.extend(selected_lucky)

            # Generate the remaining 8 unique numbers from 6-64, excluding already selected numbers
            available_numbers = [i for i in range(6, 65) if i not in numbers]
            remaining_numbers = random.sample(available_numbers, 8)
            numbers.extend(remaining_numbers)

            # Check if sum is within range
            total_sum = sum(numbers)
            if 338 <= total_sum <= 362:
                # Ensure each player gets exactly one lucky number
                player1_numbers = []
                player2_numbers = []

                # Give each player one lucky number
                player1_numbers.append(selected_lucky[0])
                player2_numbers.append(selected_lucky[1])

                # Remove the lucky numbers from the pool
                remaining_pool = numbers.copy()
                remaining_pool.remove(selected_lucky[0])
                remaining_pool.remove(selected_lucky[1])

                # Split the remaining 8 numbers equally between players
                random.shuffle(remaining_pool)
                player1_numbers.extend(remaining_pool[:4])
                player2_numbers.extend(remaining_pool[4:])

                # Combine and return
                final_numbers = player1_numbers + player2_numbers
                return final_numbers

    async def start_game(self):
        """Initialize and start the game"""
        try:
            # Send each player their own numbers
            await self.player1.send(
                f"**:clubs: :diamonds: Air Poker :hearts: :spades: Game Started!**\n\n"
                f"Your numbers: {self.player1_numbers}\n"
                f"Choose a number to play in round 1 using `.play [number]`!"
            )
            await self.player2.send(
                f"**:clubs: :diamonds: Air Poker :hearts: :spades: Game Started!**\n\n"
                f"Your numbers: {self.player2_numbers}\n"
                f"Choose a number to play in round 1 using `.play [number]`!"
            )
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start in channel
        await self.channel.send(
            f":clubs: :diamonds: **Air Poker** :hearts: :spades: game started between {self.player1.mention} and {self.player2.mention}!\n"
            f"Check your DMs for instructions. Both players should choose a number now!"
        )

        return True

    async def process_play(self, player, number):
        """Process a play command"""
        if player.id not in self.awaiting_plays:
            return "❌ You've already chosen a number for this round!"

        # Check if player has this number available
        player_numbers = self.player1_numbers if player == self.player1 else self.player2_numbers
        if number not in player_numbers:
            return f"❌ You don't have {number} in your numbers! Your available numbers: {player_numbers}"

        # Check if number was already used
        if number in self.used_numbers[player.id]:
            return f"❌ You already used {number} in a previous round!"

        self.current_plays[player.id] = number
        self.awaiting_plays.remove(player.id)

        # Check if both players have played
        if len(self.awaiting_plays) == 0:
            result = await self._start_poker_phase()
            await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    async def _start_poker_phase(self):
        """Handle the start of poker phase after both players have chosen numbers"""
        # Mark numbers as used
        self.used_numbers[self.player1.id].append(self.current_plays[self.player1.id])
        self.used_numbers[self.player2.id].append(self.current_plays[self.player2.id])

        # Initialize poker phase
        self.poker_active = True
        self.player_hands = {self.player1.id: None, self.player2.id: None}
        self.awaiting_hands = [self.player1.id, self.player2.id]
        self.hand_attempts = 0

        # Create poker phase start message
        result_message = (
            f"***===== :clubs: :diamonds: Air Poker - Round {self.round} - Start :hearts: :spades: =====***\n\n"
            f"{self.player1.mention} **vs** {self.player2.mention}\n"
            f"Both players have chosen their numbers!\n\n"
            f"**Now make your poker hands!** Use `.hand [5 cards]` in DMs.\n"
            f"Your hand must sum to your chosen number."
        )

        return result_message

    async def process_hand(self, player, cards):
        """Process a hand command for poker phase"""
        if not self.poker_active:
            return "❌ No poker phase active right now!"

        if player.id not in self.awaiting_hands:
            return "❌ You've already submitted your hand for this round!"

        # Validate hand format and count
        if len(cards) != 5:
            return "❌ You must provide exactly 5 cards!"

        # Validate each card format
        valid_hand = []
        for card in cards:
            if len(card) < 2:
                return f"❌ Invalid card format: {card}"

            # Extract suit (last character) and value (the rest)
            suit = card[-1]
            value_str = card[:-1]

            if suit not in ['s', 'h', 'd', 'c']:
                return f"❌ Invalid suit: {suit}. Use s, h, d, or c"

            if value_str not in ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']:
                return f"❌ Invalid card value: {value_str}. Use 2-10 or J, Q, K, A."

            valid_hand.append(card)

        if len(set(cards)) != 5:
            return "❌ You can't have repeating cards!"

        # Check if hand sums to player's chosen number
        hand_sum = self.calculate_hand_sum(valid_hand)
        chosen_number = self.current_plays[player.id]

        if hand_sum != chosen_number:
            return f"❌ Your hand sums to {hand_sum}, but you chose {chosen_number}!"

        self.player_hands[player.id] = valid_hand
        self.awaiting_hands.remove(player.id)

        # Check if both players have submitted hands
        if len(self.awaiting_hands) == 0:
            result = await self._evaluate_hands()
            if isinstance(result, str):  # If it returns a string message
                # This means either:
                # - "Both players made a mistake!" (need to wait for new hands)
                # - Or the round ended immediately (message from _end_round_tie_immediately)
                await self.channel.send(result)
                # If the round ended immediately, clear the flag
                if hasattr(self, '_round_ended_immediately'):
                    delattr(self, '_round_ended_immediately')
            elif result is None:
                # Hands were evaluated and betting phase should start
                result = await self._start_betting_phase()
                await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    def calculate_hand_sum(self, hand):
        """Calculate the sum of a poker hand"""
        total = 0
        for card in hand:
            value_str = card[:-1]  # Remove suit
            if value_str == 'A':
                total += 1
            elif value_str == 'J':
                total += 11
            elif value_str == 'Q':
                total += 12
            elif value_str == 'K':
                total += 13
            else:
                total += int(value_str)
        return total

    async def _evaluate_hands(self):
        """Evaluate both poker hands for legality only"""
        hand1 = self.player_hands[self.player1.id]
        hand2 = self.player_hands[self.player2.id]

        # Check if hands use cards from the deck
        hand1_legal = all(card in self.deck for card in hand1)
        hand2_legal = all(card in self.deck for card in hand2)

        # Handle illegal hands
        if not hand1_legal and not hand2_legal:
            self.hand_attempts += 1
            if self.hand_attempts < 2:
                # Give players another chance
                self.player_hands = {self.player1.id: None, self.player2.id: None}
                self.awaiting_hands = [self.player1.id, self.player2.id]
                return f"Both {self.player1.mention} & {self.player2.mention} made a mistake! They have one more chance to submit a legal hand!"
            else:
                # Both illegal twice - round ends immediately as a tie, no cards removed
                self._round_ended_immediately = True  # Set flag
                result_message = await self._end_round_tie_immediately()
                return result_message  # Return the message to be sent

        elif not hand1_legal:
            # Only one hand is illegal - remove cards and continue to betting
            self.round_winner = self.player2
            return None

        elif not hand2_legal:
            self.round_winner = self.player1
            return None

        # Both hands are legal - remove cards and continue to betting
        self.illegal_hands = {self.player1.id: False, self.player2.id: False}  # Both legal
        return None

    async def _end_round_tie_immediately(self):
        """End the round immediately as a tie when both players have illegal hands twice"""
        hand1 = self.player_hands[self.player1.id]
        hand2 = self.player_hands[self.player2.id]

        # Remove cards from the deck
        self._remove_cards_from_deck(hand1 + hand2)

        # Create result message for immediate tie
        result_message = (
            f"***===== :clubs: :diamonds: Air Poker - Round {self.round} - Results :hearts: :spades: =====***\n\n"
            f"{self.player1.mention} chose: **{self.current_plays[self.player1.id]}** | Hand: `{' '.join(hand1)}` - ***Illegal Hand***\n"
            f"{self.player2.mention} chose: **{self.current_plays[self.player2.id]}** | Hand: `{' '.join(hand2)}` - ***Illegal Hand***\n\n"
            f"Both players submitted illegal hands twice!\n"
            f"🤝 Round is a draw! No betting occurred.\n"
            f"All used cards are removed from the deck.\n\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios\n"
        )

        if self.show_table:
            result_message += f"{self.format_deck_display()}"

        # Check for game end conditions
        if self.round == self.total_rounds or self._check_bankruptcy():
            game_end_message = await self._end_game()
            result_message += f"\n{game_end_message}"
            return result_message

        # Prepare for next round
        result_message += f"\n**Round {self.round + 1} begins!** Players must choose their number."
        await self._prepare_next_round()

        return result_message

    def _remove_cards_from_deck(self, cards):
        """Remove used cards from the deck"""
        for card in cards:
            if card in self.deck:
                self.deck.remove(card)

    async def _start_betting_phase(self):
        """Start the betting phase after both players have made legal hands"""

        number1 = self.current_plays[self.player1.id]
        number2 = self.current_plays[self.player2.id]

        if self.round == 1:
            self.first_player = self.player1 if number1 < number2 else self.player2

        first_player = self.first_player

        # Initialize betting phase
        self.betting_active = True
        self.current_player = first_player
        self.pot = self.round * 2  # Ante from both players
        self.current_bets = {self.player1.id: self.round, self.player2.id: self.round}
        self.total_bets = {self.player1.id: self.round, self.player2.id: self.round}
        self.last_raise_amount = 0
        self.betting_history = []

        # Deduct ante from bios
        self.bios[self.player1.id] -= self.round
        self.bios[self.player2.id] -= self.round

        # End poker phase
        self.poker_active = False

        # Create betting phase start message
        result_message = (
            f"***===== :clubs: :diamonds: Air Poker - Round {self.round} - Betting :hearts: :spades: =====***\n\n"
            f"Both players have made their hands!\n\n"
            f"{self.player1.mention}'s number was: **{number1}**\n"
            f"{self.player2.mention}'s number was: **{number2}**\n\n"
            f"**Betting begins!** {first_player.mention} starts the action.\n"
            f"Ante - {self.round} Bios | Pot - {self.pot} Bios"
        )

        return result_message

    async def process_fold(self, player):
        """Process a fold command"""
        if not self.betting_active:
            return "❌ No betting active right now!"

        if player != self.current_player:
            return "❌ It's not your turn to act!"

        # Player folds - end betting phase
        self.betting_active = False

        # Add betting action to history
        self.betting_history.append(f"{player.mention} fold")

        # Determine winner (the other player)
        self.round_winner = self.player2 if player == self.player1 else self.player1

        # Create pot update message
        pot_message = (
            f"\n**Pot: {self.pot} Bios**\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios"
        )

        result_message = await self._end_round()
        await self.channel.send(f"✅ {player.mention} folds!{pot_message}\n\n{result_message}")
        return None

    async def process_check(self, player):
        """Process a check command"""
        if not self.betting_active:
            return "❌ No betting active right now!"

        if player != self.current_player:
            return "❌ It's not your turn to act!"

        # Check if checking is allowed (no current bet to call)
        if self.current_bets[self.player1.id] != self.current_bets[self.player2.id]:
            return "❌ You cannot check when there's an outstanding bet!"

        # Add betting action to history
        self.betting_history.append(f"{player.mention} check")

        # Create pot update message
        pot_message = (
            f"\n**Pot: {self.pot} Bios**\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios"
        )

        # Move to next player or end betting if both checked
        result = await self._advance_betting(player)
        if result is None:
            return f"✅ {player.mention} checks!{pot_message}"
        else:
            await self.channel.send(f"✅ {player.mention} checks!{pot_message}\n\n{result}")
            return None

    async def process_call(self, player):
        """Process a call command"""
        if not self.betting_active:
            return "❌ No betting active right now!"

        if player != self.current_player:
            return "❌ It's not your turn to act!"

        # Calculate amount needed to call
        other_player = self.player2 if player == self.player1 else self.player1
        call_amount = self.current_bets[other_player.id] - self.current_bets[player.id]

        if call_amount <= 0:
            return "❌ No bet to call!"

        if call_amount > self.bios[player.id]:
            return f"❌ Not enough Bios! You need {call_amount} but only have {self.bios[player.id]}.\n If you see this I messed up fr"

        # Process the call
        self.bios[player.id] -= call_amount
        self.current_bets[player.id] += call_amount
        self.total_bets[player.id] += call_amount
        self.pot += call_amount

        # Add betting action to history
        self.betting_history.append(f"{player.mention} call {call_amount} Bios")

        # Create pot update message
        pot_message = (
            f"\n**Pot: {self.pot} Bios**\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios"
        )

        # End betting phase
        self.betting_active = False
        result_message = await self._end_round()  # No fold winner
        await self.channel.send(f"✅ {player.mention} calls {call_amount} Bios!{pot_message}\n\n{result_message}")
        return None

    async def process_raise(self, player, amount_str):
        """Process a raise command"""
        if not self.betting_active:
            return "❌ No betting active right now!"

        if player != self.current_player:
            return "❌ It's not your turn to act!"

        max_amount = await self._calculate_max_raise(player)
        # Handle "all in" command
        if amount_str.lower() == 'max':
            amount = max_amount
            if max_amount == 0:
                return "❌ You cannot raise now!"
        else:
            try:
                amount = int(amount_str)
            except ValueError:
                return "❌ Please provide a valid number for raise amount or 'max' for the maximum possible raise!"

        if amount < 1:
            return "❌ Raise amount must be at least 1 Bios!"

        # Calculate current bet difference
        other_player = self.player2 if player == self.player1 else self.player1
        call_amount = self.current_bets[other_player.id] - self.current_bets[player.id]
        total_needed = call_amount + amount

        if total_needed > self.bios[player.id]:
            max_amount = await self._calculate_max_raise(player)
            return f"❌ Not enough Bios! Your max raise is {max_amount} Bios!"

        # Check raise amount is not greater than opponent's total bet
        if amount > self.total_bets[other_player.id]:
            return f"❌ Raise amount ({amount}) cannot exceed opponent's total bet ({self.total_bets[other_player.id]})"

        # Check if opponent can call the raise
        opponent_call_amount = amount  # The amount opponent would need to call after the raise
        max_opponent_can_call = self.bios[other_player.id]
        if opponent_call_amount > max_opponent_can_call:
            return f"❌ Opponent can only call up to {max_opponent_can_call} Bios (they have {max_opponent_can_call} Bios)"

        # Process the raise
        self.bios[player.id] -= total_needed
        self.current_bets[player.id] += total_needed
        self.total_bets[player.id] += total_needed
        self.pot += total_needed
        self.last_raise_amount = amount

        # Add betting action to history
        action_text = f"{player.mention} raises {amount} Bios"
        if amount_str.lower() == 'all':
            action_text = f"{player.mention} raises maximum ({amount} Bios)"
        self.betting_history.append(action_text)

        # Create pot update message
        pot_message = (
            f"\n**Pot: {self.pot} Bios**\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios"
        )

        # Move to next player
        self.current_player = other_player

        # Return success message with pot update
        return f"✅ {action_text}{pot_message}"

    async def _calculate_max_raise(self, player):
        """Calculate the maximum amount a player can raise"""
        other_player = self.player2 if player == self.player1 else self.player1

        # Calculate current call amount
        call_amount = self.current_bets[other_player.id] - self.current_bets[player.id]

        # Maximum raise is limited by:
        # 1. Player's remaining bios after calling
        max_by_player_bank = self.bios[player.id] - call_amount

        # 2. Opponent's total bet (can't raise more than what opponent has bet)
        max_by_opponent_bet = self.total_bets[other_player.id]

        # 3. Opponent's ability to call (can't raise more than opponent can afford to call)
        max_by_opponent_bank = self.bios[other_player.id]

        # The maximum raise is the minimum of these constraints
        max_raise = min(max_by_player_bank, max_by_opponent_bet, max_by_opponent_bank)

        # Ensure at least 1 Bio raise is possible
        if max_raise < 1:
            return 0

        return max_raise

    async def _advance_betting(self, player):
        """Advance to next player or end betting phase"""
        other_player = self.player2 if player == self.player1 else self.player1

        # Check if betting should end (both players checked consecutively)
        if (self.current_bets[self.player1.id] == self.current_bets[self.player2.id] and
                len(self.betting_history) >= 2 and
                "check" in self.betting_history[-1] and
                "check" in self.betting_history[-2]):
            # Both players checked - end betting
            self.betting_active = False
            result_message = await self._end_round()
            # await self.channel.send(result_message)
            return result_message
        else:
            # Continue betting with next player
            self.current_player = other_player
            return None

    async def _end_round(self):
        """End the round and show results"""
        # Create betting summary
        # betting_lines = "\n".join(self.betting_history)

        hand1 = self.player_hands[self.player1.id]
        hand2 = self.player_hands[self.player2.id]

        # Get hand rankings
        hand1_rank = self.get_hand_ranking(hand1) if hand1 else "No valid hand"
        hand2_rank = self.get_hand_ranking(hand2) if hand2 else "No valid hand"

        check_for_calamity = False
        # Determine winner
        if not self.round_winner and not self.tie:
            check_for_calamity = True
            # Compare poker hands to determine winner
            from poker_utils import compare_poker_hands
            result = compare_poker_hands(hand1, hand2)
            if result == 1:
                self.round_winner = self.player1
            elif result == 2:
                self.round_winner = self.player2

        # Check for calamity
        calamity_message = ""
        if check_for_calamity:
            calamity_cards = []
            if hand1 and hand2:
                hand1_set = set(hand1)
                hand2_set = set(hand2)
                calamity_cards = list(hand1_set.intersection(hand2_set))

            # Apply calamity penalty
            if calamity_cards and self.round_winner:
                loser = self.player2 if self.round_winner == self.player1 else self.player1
                penalty = self.total_bets[loser.id]
                if penalty > self.bios[loser.id]:
                    self.bios[loser.id] = 0
                    calamity_cards_str = ", ".join(calamity_cards)
                    calamity_message = f"\n 💥 **Calamity!** 💥 Both hands include `{calamity_cards_str}`. {loser.mention} loses all remaining Bios!"
                else:
                    self.bios[loser.id] -= penalty
                    calamity_cards_str = ", ".join(calamity_cards)
                    calamity_message = f"\n 💥 **Calamity!** 💥 Both hands include `{calamity_cards_str}`. {loser.mention} loses {penalty} Bios!"

        # Award pot to winner or split for draw
        pot_distribution_message = ""
        if self.round_winner:
            self.bios[self.round_winner.id] += self.pot
            pot_distribution_message = (f"🏆 {self.round_winner.mention} wins the round! (+{self.pot} Bios){calamity_message}\n"
                                        f"All used cards are removed from the deck.")
        else:
            # Split pot equally between both players
            half_pot = self.pot // 2
            self.bios[self.player1.id] += half_pot
            self.bios[self.player2.id] += half_pot
            # If pot is odd, give the extra Bios to first player
            if self.pot % 2 == 1:
                self.bios[self.player1.id] += 1
                pot_distribution_message = (f"🤝 Round is a draw! Pot split: {self.player1.mention} gets {half_pot + 1} Bios, {self.player2.mention} gets {half_pot} Bios.\n"
                                            f"All used cards are removed from the deck.")
            else:
                pot_distribution_message = (f"🤝 Round is a draw! Pot split equally: both players get {half_pot} Bios.\n"
                                            f"All used cards are removed from the deck.")

        # Remove cards from the deck
        self._remove_cards_from_deck(hand1 + hand2)

        # Create result message
        result_message = (
            f"***===== :clubs: :diamonds: Air Poker - Round {self.round} - Results :hearts: :spades: =====***\n\n"
            f"{self.player1.mention} chose: **{self.current_plays[self.player1.id]}** | Hand: `{' '.join(hand1)}` - ***{hand1_rank}***\n"
            f"{self.player2.mention} chose: **{self.current_plays[self.player2.id]}** | Hand: `{' '.join(hand2)}` - ***{hand2_rank}***\n\n"
            # f"**Betting:**\n{betting_lines}\n"
            # f"**Pot size: {self.pot} Bios**\n\n"
            f"{pot_distribution_message}\n\n"
            f"{self.player1.mention} - {self.bios[self.player1.id]} Bios | {self.player2.mention} - {self.bios[self.player2.id]} Bios\n"
        )

        if self.show_table:
            result_message += f"{self.format_deck_display()}"

        # Check for game end conditions
        if self.round == self.total_rounds or self._check_bankruptcy():
            game_end_message = await self._end_game()
            result_message += f"\n{game_end_message}"
            return result_message

        # Prepare for next round
        result_message += f"\n**Round {self.round + 1} begins!** Players must choose their number."
        await self._prepare_next_round()

        return result_message

    def get_hand_ranking(self, hand):
        """Get the poker hand ranking name"""
        if not hand:
            return "No hand"

        if not all(card in self.deck for card in hand):
            return "Illegal Hand"

        values = [card[:-1] for card in hand]
        suits = [card[-1] for card in hand]

        # Convert values to numbers for analysis
        value_nums = []
        for v in values:
            if v == 'A':
                value_nums.append(14)  # Ace high
            elif v == 'K':
                value_nums.append(13)
            elif v == 'Q':
                value_nums.append(12)
            elif v == 'J':
                value_nums.append(11)
            else:
                value_nums.append(int(v))

        value_nums.sort()

        # Check for Ace-low straight (A-2-3-4-5)
        is_ace_low_straight = False
        if set(values) == {'A', '2', '3', '4', '5'}:
            is_ace_low_straight = True
            # For Ace-low straight, treat Ace as 1
            value_nums = [1, 2, 3, 4, 5]

        value_counts = {}
        for v in value_nums:
            value_counts[v] = value_counts.get(v, 0) + 1

        is_flush = len(set(suits)) == 1

        # Check for regular straight (not Ace-low)
        is_straight = False
        if not is_ace_low_straight:
            is_straight = len(set(value_nums)) == 5 and max(value_nums) - min(value_nums) == 4

        # Royal Flush
        if is_straight and is_flush and max(value_nums) == 14:
            return "Royal Flush"

        # Straight Flush (including Ace-low)
        if (is_straight or is_ace_low_straight) and is_flush:
            if is_ace_low_straight:
                return "Straight Flush (A-5)"
            return "Straight Flush"

        # Four of a Kind
        if 4 in value_counts.values():
            return "Four of a Kind"

        # Full House
        if 3 in value_counts.values() and 2 in value_counts.values():
            return "Full House"

        # Flush
        if is_flush:
            return "Flush"

        # Straight (including Ace-low)
        if is_straight or is_ace_low_straight:
            if is_ace_low_straight:
                return "Straight (A-5)"
            return "Straight"

        # Three of a Kind
        if 3 in value_counts.values():
            return "Three of a Kind"

        # Two Pair
        if list(value_counts.values()).count(2) == 2:
            return "Two Pair"

        # One Pair
        if 2 in value_counts.values():
            return "One Pair"

        # High Card
        return "High Card"

    def _check_bankruptcy(self):
        """Check if any player can't afford next round's ante"""
        next_ante = self.round + 1
        return (self.bios[self.player1.id] < next_ante or
                self.bios[self.player2.id] < next_ante)

    async def _prepare_next_round(self):
        """Prepare the game for the next round"""
        self.round += 1
        self.round_winner = None
        self.current_plays = {self.player1.id: None, self.player2.id: None}
        self.awaiting_plays = [self.player1.id, self.player2.id]
        self.poker_active = False
        self.betting_active = False
        self.hand_attempts = 0

        # Switch first player to act for the next round
        self.first_player = self.player2 if self.first_player == self.player1 else self.player1

    async def _end_game(self):
        """End the entire game"""
        self.game_active = False

        if self.bios[self.player1.id] > self.bios[self.player2.id]:
            winner = self.player1
        elif self.bios[self.player2.id] > self.bios[self.player1.id]:
            winner = self.player2
        else:
            return f"🎊 **Game Over!** It's a tie! Both players have {self.bios[self.player1.id]} Bios."

        return f"🎊 **Game Over!** {winner.mention} wins with {self.bios[winner.id]} Bios!"
