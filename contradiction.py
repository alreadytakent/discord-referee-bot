import discord
import random


class ContradictionGame:
    def __init__(self, player1, player2, channel):
        self.players = [player1, player2]
        self.channel = channel
        self.game_active = False

        # Game state
        self.bios = {player1.id: 35000, player2.id: 35000}
        self.hp = {player1.id: 10, player2.id: 10}

        # Round state
        self.current_draw = 0
        self.current_round = 1
        self.spear_chooser = None
        self.shield_chooser = None

        # Player choices
        self.spear_choices = {}
        self.shield_choices = {}
        self.bets = {}

        # Available tools for current round
        self.available_spears = ["taser", "katana", "gun"]
        self.available_shields = ["rubber", "wooden", "iron"]

        # Damage matrix
        self.damage_matrix = {
            "gun": {"rubber": 5, "wooden": 3, "iron": 0},
            "katana": {"rubber": 3, "wooden": 2, "iron": 0},
            "taser": {"rubber": 0, "wooden": 0, "iron": 3}
        }

    async def start_game(self):
        """Start the Contradiction game"""
        try:
            # Randomly decide who chooses spear first
            self.spear_chooser = random.choice(self.players)
            self.shield_chooser = [p for p in self.players if p != self.spear_chooser][0]

            self.game_active = True
            self.current_draw = 1
            self.current_round = 1

            # Send initial message to channel
            await self.channel.send(
                f":crossed_swords: :shield: **CONTRADICTION** :shield: :crossed_swords: game started between {self.players[0].mention} and {self.players[1].mention}!\n\n"
                f"**Round {self.current_round} - Draw {self.current_draw}/3**\n"
                f"• {self.spear_chooser.mention} will choose a SPEAR\n"
                f"• {self.shield_chooser.mention} will choose a SHIELD\n\n"
                f"Damage Matrix:\n"
                f"```\n"
                f"Spear\\Shield   Rubber   Wood    Iron\n"
                f"      \n"
                f"Gun              5       3       0\n"
                f"Katana           3       2       0\n"
                f"Taser            0       0       3\n"
                f"```\n"
                f"Check your DMs for instructions."
            )

            # Send DM instructions
            await self.send_dm_instructions()

            return True

        except Exception as e:
            await self.channel.send(f"❌ Failed to start game: {str(e)}")
            return False

    async def send_dm_instructions(self):
        """Send DM instructions to players"""
        spear_dm = (
            f":crossed_swords: :shield: **CONTRADICTION** :shield: :crossed_swords: game started!\n\n"
            f"You're playing against {self.shield_chooser.mention if self.spear_chooser.id == self.players[0].id else self.players[0].mention}\n"
            f"Choose a SPEAR to use: `.spear [taser/katana/gun]`\n\n"
            f"Damage Matrix:\n"
            f"```\n"
            f"Spear\\Shield   Rubber   Wood    Iron\n"
            f"      \n"
            f"Gun              5       3       0\n"
            f"Katana           3       2       0\n"
            f"Taser            0       0       3\n"
            f"```"
        )

        shield_dm = (
            f":crossed_swords: :shield: **CONTRADICTION** :shield: :crossed_swords: game started!\n\n"
            f"You're playing against {self.spear_chooser.mention if self.shield_chooser.id == self.players[0].id else self.players[0].mention}\n"
            f"Choose a SHIELD to use: `.shield [rubber/wooden/iron]`\n\n"
            f"Damage Matrix:\n"
            f"```\n"
            f"Spear\\Shield   Rubber   Wood    Iron\n"
            f"      \n"
            f"Gun              5       3       0\n"
            f"Katana           3       2       0\n"
            f"Taser            0       0       3\n"
            f"```"
        )

        try:
            await self.spear_chooser.send(spear_dm)
            await self.shield_chooser.send(shield_dm)
        except discord.Forbidden:
            await self.channel.send(f"❌ Could not send DM to players. Please enable DMs!")

    async def process_spear(self, player, spear_choice):
        """Process spear choice"""
        if player.id != self.spear_chooser.id:
            return "❌ It's not your turn to choose a spear!"

        spear_choice = spear_choice.lower()
        if spear_choice not in self.available_spears:
            return f"❌ Invalid spear! Available: {', '.join(self.available_spears)}"

        self.spear_choices[player.id] = spear_choice

        # Check if both players have made their choices
        return await self.check_choices_complete()

    async def process_shield(self, player, shield_choice):
        """Process shield choice"""
        if player.id != self.shield_chooser.id:
            return "❌ It's not your turn to choose a shield!"

        shield_choice = shield_choice.lower()
        if shield_choice not in self.available_shields:
            return f"❌ Invalid shield! Available: {', '.join(self.available_shields)}"

        self.shield_choices[player.id] = shield_choice

        # Check if both players have made their choices
        return await self.check_choices_complete()

    async def check_choices_complete(self):
        """Check if both players have made their tool choices"""
        if len(self.spear_choices) == 1 and len(self.shield_choices) == 1:
            # Both players have chosen, request bets
            await self.request_bets()
            return None
        return None

    async def request_bets(self):
        """Request bets from both players"""
        bet_dm = "💰 **Place your bet!** Use: `.bet [amount]`"

        try:
            await self.spear_chooser.send(bet_dm)
            await self.shield_chooser.send(bet_dm)
        except discord.Forbidden:
            await self.channel.send("❌ Could not send bet instructions via DM!")

    async def process_bet(self, player, amount):
        """Process player's bet"""
        if amount == 'all':
            bet_amount = self.bios[player.id]
        else:
            try:
                bet_amount = int(amount)
            except ValueError:
                return "❌ Please provide a valid number for your bet!"

            if bet_amount <= 0:
                return "❌ Bet must be positive!"

            if bet_amount > self.bios[player.id]:
                return f"❌ You don't have enough Bios! You have {self.bios[player.id]:,}"

        self.bets[player.id] = bet_amount

        # Check if both players have bet
        if len(self.bets) == 2:
            return await self.resolve_bets()

        return None

    async def resolve_bets(self):
        """Resolve bets and determine attacker/defender"""
        bet1 = self.bets[self.players[0].id]
        bet2 = self.bets[self.players[1].id]

        # Check for tie
        if bet1 == bet2:
            await self.channel.send(
                f"⚖️ **Bet Tie!**\n"
                f"Both players bet {bet1:,} Bios.\n"
                f"Please bet again with different amounts!"
            )

            # Reset bets for rebetting
            self.bets = {}
            await self.request_bets()
            return None

        # Determine attacker and defender based on bets
        if bet1 > bet2:
            attacker = self.players[0]
            defender = self.players[1]
        else:
            attacker = self.players[1]
            defender = self.players[0]

        # Get the chosen tools from the original choosers
        spear = self.spear_choices[self.spear_chooser.id]
        shield = self.shield_choices[self.shield_chooser.id]

        # Get the bets for the spear chooser and shield chooser
        spear_chooser_bet = self.bets[self.spear_chooser.id]
        shield_chooser_bet = self.bets[self.shield_chooser.id]

        # Calculate damage
        damage = self.damage_matrix[spear][shield]

        # Apply damage and deduct bios
        self.hp[defender.id] = max(0, self.hp[defender.id] - damage)
        self.bios[attacker.id] -= self.bets[attacker.id]
        self.bios[defender.id] -= self.bets[defender.id]

        # Send result to channel and prepare next draw
        await self.send_round_result_and_next(spear_chooser_bet, shield_chooser_bet, spear, shield, damage)

        return None

    async def send_round_result_and_next(self, spear_chooser_bet, shield_chooser_bet, spear, shield, damage):
        """Send round result to channel and prepare next draw in one message"""
        player1 = self.players[0]
        player2 = self.players[1]
        # Create HP bars
        hp_bar1 = self.create_hp_bar(player1)
        hp_bar2 = self.create_hp_bar(player2)

        damage_emoji = "💥" if damage > 0 else "❌"

        # Build the result message - show who chose spear vs shield with their respective bets
        result_msg = (
            f"***===== :crossed_swords: :shield: CONTRADICTION - Round {self.current_round} - Draw {self.current_draw}/3 :shield: :crossed_swords: =====***\n\n"
            f"{self.spear_chooser.mention} chose **{spear.upper()}** and bet **{spear_chooser_bet:,} Bios**\n"
            f"{self.shield_chooser.mention} chose **{shield.upper()} SHIELD** and bet **{shield_chooser_bet:,} Bios**\n\n"
            f"**{spear.upper()}** vs **{shield.upper()} SHIELD** = {damage} damage! {damage_emoji}\n\n"
            f"{hp_bar1}{player1.mention} {self.bios[player1.id]:,} Bios\n\n"
            f"{hp_bar2}{player2.mention} {self.bios[player2.id]:,} Bios"
        )

        # Remove used tools from available choices
        used_spear = self.spear_choices[self.spear_chooser.id]
        used_shield = self.shield_choices[self.shield_chooser.id]

        self.available_spears.remove(used_spear)
        self.available_shields.remove(used_shield)

        # Reset choices and bets for next draw
        self.spear_choices = {}
        self.shield_choices = {}
        self.bets = {}

        # Switch roles for next draw
        self.spear_chooser, self.shield_chooser = self.shield_chooser, self.spear_chooser

        self.current_draw += 1

        # Check if game ended (check both players' HP)
        if self.hp[player1.id] <= 0:
            self.game_active = False
            result_msg += f"\n\n**🏆 GAME OVER! {player2.mention} wins!**"
        elif self.hp[player2.id] <= 0:
            self.game_active = False
            result_msg += f"\n\n**🏆 GAME OVER! {player1.mention} wins!**"
        elif self.bios[player1.id] == 0:
            self.game_active = False
            result_msg += f"\n\n**🏆 GAME OVER! {player2.mention} wins!**"
        elif self.bios[player2.id] == 0:
            self.game_active = False
            result_msg += f"\n\n**🏆 GAME OVER! {player1.mention} wins!**"

        # Add next draw information to the message if game is still active
        elif self.current_draw <= 3:
            if self.current_draw == 3:  # Last draw of the round
                # Automatic choices for last draw
                remaining_spear = self.available_spears[0]
                remaining_shield = self.available_shields[0]

                self.spear_choices[self.spear_chooser.id] = remaining_spear
                self.shield_choices[self.shield_chooser.id] = remaining_shield

                result_msg += (
                    f"\n\n**Round {self.current_round} - Draw 3/3**\n"
                    f"It's the last draw of the round, so:\n"
                    f"• {self.spear_chooser.mention}'s SPEAR is **{remaining_spear.upper()}**\n"
                    f"• {self.shield_chooser.mention}'s SHIELD is **{remaining_shield.upper()}**\n"
                    f"Now place your bets!"
                )

                # Send bet DMs
                await self.request_bets()
            else:
                # Continue to next draw with choices
                result_msg += (
                    f"\n\n**Round {self.current_round} - Draw {self.current_draw}/3**\n"
                    f"• {self.spear_chooser.mention} will choose a SPEAR\n"
                    f"• {self.shield_chooser.mention} will choose a SHIELD"
                )

                # Send choice DMs for subsequent draws
                await self.send_choice_dms()
        else:
            # Round completed, start new round
            self.current_round += 1
            self.current_draw = 1
            self.available_spears = ["taser", "katana", "gun"]
            self.available_shields = ["rubber", "wooden", "iron"]

            result_msg += (
                f"\n\n**Round {self.current_round} - Draw 1/3**\n"
                f"• {self.spear_chooser.mention} will choose a SPEAR\n"
                f"• {self.shield_chooser.mention} will choose a SHIELD"
            )

            # Send choice DMs for new round
            await self.send_choice_dms()

        await self.channel.send(result_msg)

    async def send_choice_dms(self):
        """Send choice DMs to players for subsequent draws"""
        spear_dm = ":crossed_swords: Choose a SPEAR! Use: `.spear [gun/katana/taser]`"
        shield_dm = ":shield: Choose a SHIELD! Use: `.shield [rubber/wooden/iron]`"

        try:
            await self.spear_chooser.send(spear_dm)
            await self.shield_chooser.send(shield_dm)
        except discord.Forbidden:
            await self.channel.send("❌ Could not send choice instructions via DM!")

    def create_hp_bar(self, player):
        """Create a visual HP bar"""
        hp_count = self.hp[player.id]
        return ":green_square: " * hp_count + ":red_square: " * (10 - hp_count)
