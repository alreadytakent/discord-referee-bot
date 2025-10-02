import discord
import random


class CombinationGame:
    def __init__(self, player1, player2, channel):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.game_active = True
        self.round = 1

        # Randomly assign first roles
        if random.choice([True, False]):
            self.maker = player1
            self.guesser = player2
        else:
            self.maker = player2
            self.guesser = player1

        self.hp = {player1.id: 7, player2.id: 7}
        self.current_number = None
        self.maker_hand = None
        self.guesser_hand = None
        self.awaiting_maker = True
        self.awaiting_guesser = True

    def card_to_value(self, card_str):
        """Convert card string to numerical value"""
        card_str = card_str.upper().strip()
        if card_str in ['A', '1']:
            return 1
        elif card_str in ['J', '11']:
            return 11
        elif card_str in ['Q', '12']:
            return 12
        elif card_str in ['K', '13']:
            return 13
        else:
            try:
                value = int(card_str)
                if 2 <= value <= 10:
                    return value
                return None
            except ValueError:
                return None

    def value_to_card(self, value):
        """Convert numerical value back to card string"""
        if value == 1:
            return 'A'
        elif value == 11:
            return 'J'
        elif value == 12:
            return 'Q'
        elif value == 13:
            return 'K'
        else:
            return str(value)

    def validate_hand(self, cards):
        """Validate a hand and return (is_valid, error_message, card_values)"""
        if len(cards) != 5:
            return False, f"❌ Please provide exactly 5 cards that sum up to {self.current_number}!", None

        card_values = []
        for card in cards:
            value = self.card_to_value(card)
            if value is None:
                return False, f"❌ Invalid card: {card}. Use A/1, 2-10, J/11, Q/12, K/13.", None
            card_values.append(value)

        # Check card usage limits (max 4 of each card)
        card_counts = {}
        for value in card_values:
            card_counts[value] = card_counts.get(value, 0) + 1
            if card_counts[value] > 4:
                return False, f"❌ You used {self.value_to_card(value)} {card_counts[value]} times! Maximum is 4 of each card.", None

        # Check if sum matches the target number
        total_sum = sum(card_values)
        if total_sum != self.current_number:
            return False, f"❌ Your hand sums to {total_sum}, but the target is {self.current_number}.", None

        return True, None, card_values

    async def start_game(self):
        """Initialize and start the game"""
        # Generate first number
        self.current_number = random.randint(10, 60)

        instructions = (
            "**Combination Game Started!**\n\n"
            "**How to play:**\n"
            "- Each round has a target number (10-60)\n"
            "- Maker: Create a hand that sums to the target using `.combo [cards]`\n"
            "- Guesser: Guess the maker's hand using `.guess [cards]`\n"
            "- Cards: A/1, 2-10, J/11, Q/12, K/13\n"
            "- Maximum 4 of each card (4 suits)\n"
            "- For each correct card in guess, maker loses 1 HP\n"
            "- First to 0 HP loses!\n\n"
            f"You're playing against {self.guesser.mention if self.maker == self.player1 else self.player1.mention}\n"
            f"{self.maker.mention} is the maker first!"
        )

        try:
            await self.player1.send(instructions)
            await self.player2.send(instructions)
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start
        await self.channel.send(
            f"🃏 **Combination** game started between {self.player1.mention} and {self.player2.mention}!\n"
            f"**Round {self.round}** - Target number: **{self.current_number}**\n"
            f"{self.maker.mention} is the maker! Create a combination that sums to {self.current_number}.\n"
            f"{self.guesser.mention} is the guesser! Try to guess the maker's combination."
        )

        return True

    async def process_combo(self, player, cards):
        """Process a combo command from the maker"""
        if player != self.maker:
            return "❌ You're not the maker this round! Wait for your turn as guesser."

        if not self.awaiting_maker:
            return "❌ You've already submitted your combination for this round!"

        is_valid, error, card_values = self.validate_hand(cards)
        if not is_valid:
            return error

        self.maker_hand = card_values
        self.awaiting_maker = False

        # Check if both players have submitted
        if not self.awaiting_guesser:
            result = await self._resolve_round()
            await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    async def process_guess(self, player, cards):
        """Process a guess command from the guesser"""
        if player != self.guesser:
            return "❌ You're not the guesser this round! Wait for your turn as maker."

        if not self.awaiting_guesser:
            return "❌ You've already submitted your guess for this round!"

        is_valid, error, card_values = self.validate_hand(cards)
        if not is_valid:
            return error

        self.guesser_hand = card_values
        self.awaiting_guesser = False

        # Check if both players have submitted
        if not self.awaiting_maker:
            result = await self._resolve_round()
            await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    async def _resolve_round(self):
        """Resolve the current round and return results"""
        # Format hands for display
        maker_display = " ".join(self.value_to_card(card) for card in self.maker_hand)
        guesser_display = " ".join(self.value_to_card(card) for card in self.guesser_hand)

        # Calculate damage (number of common cards)
        maker_hand_set = self.maker_hand.copy()
        guesser_hand_set = self.guesser_hand.copy()

        damage = 0
        for card in guesser_hand_set:
            if card in maker_hand_set:
                damage += 1
                maker_hand_set.remove(card)

        # Apply damage to maker
        self.hp[self.maker.id] = max(0, self.hp[self.maker.id] - damage)

        # Create HP bars with emojis
        def create_hp_bar(hp):
            full_hearts = "🟩 " * hp
            empty_hearts = "🟥 " * (7 - hp)
            return full_hearts + empty_hearts

        p1_hp_bar = create_hp_bar(self.hp[self.player1.id])
        p2_hp_bar = create_hp_bar(self.hp[self.player2.id])

        # Create result message
        result_message = (
            f"***===== Combination - Round {self.round} =====***\n"
            f"Number: **{self.current_number}**\n"
            f"{self.maker.mention} combo `{maker_display}`  \n"
            f"{self.guesser.mention} guess `{guesser_display}` \n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
            f"HP lost: **{damage}**\n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
            f"{p1_hp_bar} {self.player1.mention}\n\n"
            f"{p2_hp_bar} {self.player2.mention}\n"
            f"~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~"
        )

        # Check for game end
        if self.hp[self.maker.id] <= 0:
            result_message += f"\n\n🎉 **GAME OVER!** {self.guesser.mention} wins! {self.maker.mention} reaches 0 HP!"
            self.game_active = False
            return result_message

        # Setup next round
        self.round += 1

        # Switch roles
        self.maker, self.guesser = self.guesser, self.maker

        # Reset for next round
        self.current_number = random.randint(10, 60)
        self.maker_hand = None
        self.guesser_hand = None
        self.awaiting_maker = True
        self.awaiting_guesser = True

        result_message += f"\nNext number : **{self.current_number}**"

        return result_message
