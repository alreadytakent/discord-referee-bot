import discord
import random
from game_stats import record_game_result


class GOPSGame:
    def __init__(self, player1, player2, channel):
        self.player1 = player1
        self.player2 = player2
        self.channel = channel
        self.game_active = True
        self.round = 1
        self.total_cards = 13

        # Create deck of prize cards (1-13)
        self.prize_deck = list(range(1, 14))
        random.shuffle(self.prize_deck)

        # Current prize pool (starts with one card, grows on ties)
        self.current_prizes = [self.prize_deck.pop()]

        # Players' hands (each gets all cards 1-13)
        self.original_hands = {
            player1.id: list(range(1, 14)),
            player2.id: list(range(1, 14))
        }

        # Current hands (cards actually remaining)
        self.hands = {
            player1.id: list(range(1, 14)),
            player2.id: list(range(1, 14))
        }

        self.scores = {player1.id: 0, player2.id: 0}
        self.bids = {}  # Store bids for current round
        self.awaiting_bids = [player1.id, player2.id]
        self.carryover_rounds = 0  # Track how many rounds have had carryover prizes
        self.round_completed = True  # Track if current round is complete

    def format_cards_display(self, cards):
        """Format cards with dashes for missing numbers, double dashes for 10+"""
        display = []
        for i in range(1, 14):
            if i in cards:
                display.append(str(i))
            else:
                # Double-digit numbers get two dashes, single digit get one
                display.append("-" if i < 10 else "--")

        return " ".join(display)

    def format_prize_track(self):
        """Format the remaining prize cards track"""
        # All cards that are still available as prizes (in deck or current prizes)
        available_prizes = self.prize_deck + self.current_prizes
        display = []
        for i in range(1, 14):
            if i in available_prizes:
                display.append(str(i))
            else:
                # Double-digit numbers get two dashes, single digit get one
                display.append("-" if i < 10 else "--")

        return " ".join(display)

    def get_score_display(self):
        """Get the formatted score display"""
        # Use original_hands for display (only shows cards available at round start)
        p1_cards = self.format_cards_display(sorted(self.original_hands[self.player1.id]))
        p2_cards = self.format_cards_display(sorted(self.original_hands[self.player2.id]))

        # Format prize track (cards still available as prizes)
        prize_track = self.format_prize_track()

        # Current prize value
        current_prize = sum(self.current_prizes) if self.current_prizes else 0

        score_message = (
            f"📊 **GOPS - Round {self.round}**\n\n"
            f"{self.player1.mention}: {self.scores[self.player1.id]} points\n"
            f"Available cards: {p1_cards}\n\n"
            f"{self.player2.mention}: {self.scores[self.player2.id]} points\n"
            f"Available cards: {p2_cards}\n\n"
            f"Current prize: {current_prize}\n"
            f"Prize cards left: {prize_track}"
        )

        return score_message

    async def start_game(self):
        """Initialize and start the game"""
        instructions = (
            "**Game of Pure Strategy started!**\n\n"
            "**How to play:**\n"
            "- Each round, prize cards are revealed\n"
            "- You bid one card from your hand (1-13)\n"
            "- Higher bid wins ALL prize cards' values as points\n"
            "- Ties: prize cards carry over to next round\n"
            "- First to reach 46+ points wins instantly!\n"
            "- Use `.bid [1-13]` to play your card\n\n"
            f"You're playing against {self.player2.mention if self.player1.id == self.awaiting_bids[0] else self.player1.mention}"
        )

        try:
            await self.player1.send(instructions)
            await self.player2.send(instructions)
        except discord.Forbidden:
            await self.channel.send(f"❌ Cannot send DMs to players. Please enable DMs from server members!")
            return False

        # Announce game start and first prize
        await self.channel.send(
            f"🎴 **Game of Pure Strategy** started between {self.player1.mention} and {self.player2.mention}!\n"
            f"**Round 1** - Prize card: {self.current_prizes[0]}\n"
            f"Check your DMs for instructions. Both players should bid now!"
        )

        return True

    async def process_bid(self, player, card):
        """Process a bid command"""
        if player.id not in self.awaiting_bids:
            return "❌ You've already bid this round!"

        # Check against original hand (cards that should be available at round start)
        if card not in self.original_hands[player.id]:
            return f"❌ You don't have card {card} in your hand! Your available cards: {sorted(self.original_hands[player.id])}"

        # Record the bid
        self.bids[player.id] = card
        self.awaiting_bids.remove(player.id)

        # Remove card from current hand (but keep original hand intact until round ends)
        self.hands[player.id].remove(card)

        # If both players have bid, resolve the round
        if len(self.awaiting_bids) == 0:
            result = await self._resolve_round()
            await self.channel.send(result)
            return None

        return None  # No confirmation message, just reaction

    async def _resolve_round(self):
        """Resolve the current round and return results"""
        bid1 = self.bids[self.player1.id]
        bid2 = self.bids[self.player2.id]
        total_prize_value = sum(self.current_prizes)

        if len(self.current_prizes) == 1:
            prize_display = f"**{' + '.join(str(p) for p in self.current_prizes)}**"
        else:
            prize_display = f"{' + '.join(str(p) for p in self.current_prizes)} = **{total_prize_value}**"

        result_message = (
            f"***===== Game of Pure Strategy - Round {self.round} =====***\n\n"
            f"Prize cards: {prize_display}\n"
            f"{self.player1.mention} bid: **{bid1}**\n"
            f"{self.player2.mention} bid: **{bid2}**\n\n"
        )

        winner = None
        if bid1 > bid2:
            # Player 1 wins all prize cards
            self.scores[self.player1.id] += total_prize_value
            result_message += f"🏆 {self.player1.mention} wins the round! (+{total_prize_value} points)"
            winner = self.player1
            # Reset prize pool for next round
            if self.prize_deck:
                self.current_prizes = [self.prize_deck.pop()]
            else:
                self.current_prizes = []  # No more prize cards

        elif bid2 > bid1:
            # Player 2 wins all prize cards
            self.scores[self.player2.id] += total_prize_value
            result_message += f"🏆 {self.player2.mention} wins the round! (+{total_prize_value} points)"
            winner = self.player2
            # Reset prize pool for next round
            if self.prize_deck:
                self.current_prizes = [self.prize_deck.pop()]
            else:
                self.current_prizes = []  # No more prize cards

        else:
            # Tie - carry over prizes to next round
            if self.prize_deck:
                # Add another card to the prize pool
                new_prize = self.prize_deck.pop()
                self.current_prizes.append(new_prize)
                self.carryover_rounds += 1
                result_message += f"🤝 **Tie!** Prize cards carry over to next round. Added card: **{new_prize}**"
            else:
                # No more cards to add - discard the prize pool
                result_message += f"🤝 **Tie!** No more cards to add. Prize pool of {total_prize_value} points is discarded!"
                self.current_prizes = []

        # NOW update the original hands to reflect the bids that were just resolved
        self.original_hands[self.player1.id].remove(bid1)
        self.original_hands[self.player2.id].remove(bid2)
        self.round_completed = True

        """Get the formatted score display"""
        # Use original_hands for display (only shows cards available at round start)
        p1_cards = self.format_cards_display(sorted(self.original_hands[self.player1.id]))
        p2_cards = self.format_cards_display(sorted(self.original_hands[self.player2.id]))

        # Format prize track (cards still available as prizes)
        prize_track = self.format_prize_track()

        # Current prize value
        current_prize = sum(self.current_prizes) if self.current_prizes else 0

        score_message = (
            f"`{p1_cards}` {self.player1.mention} ({self.scores[self.player1.id]} points)\n"
            f"`{p2_cards}` {self.player2.mention} ({self.scores[self.player2.id]} points)\n"
            f"`{prize_track}` Remaining prizes"
        )

        # Add the score display to the results
        result_message += f"\n\n{score_message}"

        # Check for automatic victory (46+ points)
        if self.scores[self.player1.id] >= 46:
            result_message += f"\n\n🎉 **GAME OVER!** {self.player1.mention} reaches {self.scores[self.player1.id]} points and wins instantly!"
            self.game_active = False
            # Record game result
            record_game_result('gops', self.player1.id, self.player2.id, 1)
            return result_message
        elif self.scores[self.player2.id] >= 46:
            result_message += f"\n\n🎉 **GAME OVER!** {self.player2.mention} reaches {self.scores[self.player2.id]} points and wins instantly!"
            self.game_active = False
            # Record game result
            record_game_result('gops', self.player1.id, self.player2.id, 2)
            return result_message

        # Check if game is over (both players out of cards)
        if not self.original_hands[self.player1.id] and not self.original_hands[self.player2.id]:
            # Game over
            if self.scores[self.player1.id] > self.scores[self.player2.id]:
                winner = self.player1
                result_message += f"\n\n🎉 **GAME OVER!** {winner.mention} wins with {self.scores[winner.id]} points!"
                self.game_active = False
                # Record game result
                record_game_result('gops', self.player1.id, self.player2.id, 1)
            elif self.scores[self.player2.id] > self.scores[self.player1.id]:
                winner = self.player2
                result_message += f"\n\n🎉 **GAME OVER!** {winner.mention} wins with {self.scores[winner.id]} points!"
                self.game_active = False
                # Record game result
                record_game_result('gops', self.player1.id, self.player2.id, 2)
            else:
                # Tie game
                result_message += f"\n\n🎉 **GAME OVER!** It's a tie! Both players scored {self.scores[self.player1.id]} points!"
                self.game_active = False
                # Record game result - draw
                record_game_result('gops', self.player1.id, self.player2.id, 0)
            return result_message
        else:
            # Setup next round
            self.round += 1
            self.bids = {}
            self.awaiting_bids = [self.player1.id, self.player2.id]
            self.round_completed = False

            # Reset current hands to match original hands for the new round
            self.hands = {
                self.player1.id: self.original_hands[self.player1.id][:],
                self.player2.id: self.original_hands[self.player2.id][:]
            }

            if self.current_prizes:
                if len(self.current_prizes) == 1:
                    prize_display = f"**{' + '.join(str(p) for p in self.current_prizes)}**"
                else:
                    total_prize_value = sum(self.current_prizes)
                    prize_display = f"{' + '.join(str(p) for p in self.current_prizes)} = **{total_prize_value}**"
                result_message += f"\n\n**Round {self.round}** - Prize cards: {prize_display}"
            else:
                # If no prize cards left but players still have cards, draw a new one
                if self.prize_deck:
                    self.current_prizes = [self.prize_deck.pop()]
                    if len(self.current_prizes) == 1:
                        prize_display = f"**{' + '.join(str(p) for p in self.current_prizes)}**"
                    else:
                        total_prize_value = sum(self.current_prizes)
                        prize_display = f"{' + '.join(str(p) for p in self.current_prizes)} = **{total_prize_value}**"
                    result_message += f"\n\n**Round {self.round}** - Prize cards: {prize_display}"
                else:
                    # No more prize cards but players still have cards (shouldn't happen in normal game)
                    result_message += f"\n\n**Game ended unexpectedly** - no more prize cards but players still have cards."
                    self.game_active = False

        return result_message

