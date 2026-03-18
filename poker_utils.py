# Convert card strings to numerical values and suits
def parse_card(card):
    card = card.upper()
    suit = card[-1]
    value_str = card[:-1]

    # Convert value to number
    if value_str in ['A', '1']:
        value = 14  # Ace high
    elif value_str in ['K', '13']:
        value = 13
    elif value_str in ['Q', '12']:
        value = 12
    elif value_str in ['J', '11']:
        value = 11
    else:
        value = int(value_str)
    return (value, suit)

def get_hand_rank(hand):
    """Return a tuple (rank, primary, secondary, kickers) for hand comparison"""
    values = [card[0] for card in hand]
    suits = [card[1] for card in hand]

    # Sort values descending
    values.sort(reverse=True)
    value_counts = {}
    for v in values:
        value_counts[v] = value_counts.get(v, 0) + 1

    # Check for straight and flush
    is_flush = len(set(suits)) == 1
    is_straight = len(set(values)) == 5 and max(values) - min(values) == 4

    # Handle Ace-low straight (A-2-3-4-5)
    if set(values) == {14, 2, 3, 4, 5}:
        is_straight = True
        values = [5, 4, 3, 2, 1]  # Treat Ace as 1 for comparison

    # Royal Flush
    if is_straight and is_flush and max(values) == 14:
        return (10, max(values), 0, values)

    # Straight Flush
    if is_straight and is_flush:
        return (9, max(values), 0, values)

    # Four of a Kind
    if 4 in value_counts.values():
        four_of_kind = [v for v, count in value_counts.items() if count == 4][0]
        kicker = [v for v in values if v != four_of_kind][0]
        return (8, four_of_kind, kicker, values)

    # Full House
    if 3 in value_counts.values() and 2 in value_counts.values():
        three_of_kind = [v for v, count in value_counts.items() if count == 3][0]
        pair = [v for v, count in value_counts.items() if count == 2][0]
        return (7, three_of_kind, pair, values)

    # Flush
    if is_flush:
        return (6, max(values), 0, values)

    # Straight
    if is_straight:
        return (5, max(values), 0, values)

    # Three of a Kind
    if 3 in value_counts.values():
        three_of_kind = [v for v, count in value_counts.items() if count == 3][0]
        kickers = [v for v in values if v != three_of_kind]
        kickers.sort(reverse=True)
        return (4, three_of_kind, kickers[0], values)

    # Two Pair
    pairs = [v for v, count in value_counts.items() if count == 2]
    if len(pairs) == 2:
        pairs.sort(reverse=True)
        kicker = [v for v in values if v not in pairs][0]
        return (3, pairs[0], pairs[1], values)

    # One Pair
    if 2 in value_counts.values():
        pair = [v for v, count in value_counts.items() if count == 2][0]
        kickers = [v for v in values if v != pair]
        kickers.sort(reverse=True)
        return (2, pair, kickers[0], values)

    # High Card
    return (1, max(values), 0, values)

def compare_poker_hands(hand1, hand2):
    """
    Compare two poker hands and return:
    1 if hand1 wins, 2 if hand2 wins, 0 if tie

    Cards are strings like "As" (Ace of Spades), "Qc" (Queen of Clubs), "10h" (10 of Hearts)
    Suits: s=Spades, h=Hearts, d=Diamonds, c=Clubs
    """
    try:
        # Parse both hands
        parsed_hand1 = [parse_card(card) for card in hand1]
        parsed_hand2 = [parse_card(card) for card in hand2]

        # Get hand ranks
        rank1, primary1, secondary1, kickers1 = get_hand_rank(parsed_hand1)
        rank2, primary2, secondary2, kickers2 = get_hand_rank(parsed_hand2)

        # Compare ranks
        if rank1 > rank2:
            return 1
        elif rank2 > rank1:
            return 2

        # Same rank, compare primary value
        if primary1 > primary2:
            return 1
        elif primary2 > primary1:
            return 2

        # Same primary, compare secondary value
        if secondary1 > secondary2:
            return 1
        elif secondary2 > secondary1:
            return 2

        # Same secondary, compare kickers
        for k1, k2 in zip(kickers1, kickers2):
            if k1 > k2:
                return 1
            elif k2 > k1:
                return 2

        # Complete tie
        return 0

    except Exception as e:
        return "Unexpected error in hand evaluation"