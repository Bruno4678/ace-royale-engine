"""Poker hand evaluation.

Cards use the SAME numbering as the rest of the package (blackjack included):

    XYY  ->  X = suit (1 spades, 2 clubs, 3 hearts, 4 diamonds)
             YY = rank 01..13 (1 = ace, 11 = J, 12 = Q, 13 = K)

Careful: in blackjack the ace is worth 1. In poker it is worth 14 (or 1 in the
A-2-3-4-5 straight), so it is translated here.

A score is a tuple comparable with < and >: the first element is the category
and the rest are the tie-breakers, already ordered. Two hands of the same
category always produce tuples of the same length.
"""

from collections import Counter
from itertools import combinations

# Categories, best to worst
STRAIGHT_FLUSH  = 8
FOUR_OF_A_KIND  = 7
FULL_HOUSE      = 6
FLUSH           = 5
STRAIGHT        = 4
THREE_OF_A_KIND = 3
TWO_PAIR        = 2
PAIR            = 1
HIGH_CARD       = 0

# Display name of each category
CATEGORY_NAMES = {
    STRAIGHT_FLUSH:  "Straight flush",
    FOUR_OF_A_KIND:  "Four of a kind",
    FULL_HOUSE:      "Full house",
    FLUSH:           "Flush",
    STRAIGHT:        "Straight",
    THREE_OF_A_KIND: "Three of a kind",
    TWO_PAIR:        "Two pair",
    PAIR:            "Pair",
    HIGH_CARD:       "High card",
}

RANK_NAMES = {
    14: "A", 13: "K", 12: "Q", 11: "J", 10: "10", 9: "9", 8: "8", 7: "7",
    6: "6", 5: "5", 4: "4", 3: "3", 2: "2",
}


def rank(card:int)->int:
    """Poker rank of a card: the ace goes up to 14."""
    r = card % 100
    return 14 if r == 1 else r


def suit(card:int)->int:
    """Suit of a card: 1 spades, 2 clubs, 3 hearts, 4 diamonds."""
    return card // 100


def full_deck()->list:
    """All 52 cards."""
    return [s*100 + r for s in (1, 2, 3, 4) for r in range(1, 14)]


def evaluate_5(cards)->tuple:
    """
    Score of a hand of exactly 5 cards.

    :param cards: iterable of 5 cards
    :return: comparable tuple (category, tie-breakers...)
    """
    ranks = [rank(c) for c in cards]
    suits = [suit(c) for c in cards]

    flush = len(set(suits)) == 1

    # Straight: needs 5 distinct, consecutive ranks. The exception is the
    # "wheel" A-2-3-4-5, where the ace plays low and the straight is 5-high.
    unique = sorted(set(ranks))
    straight = False
    straight_high = 0
    if len(unique) == 5:
        if unique[4] - unique[0] == 4:
            straight = True
            straight_high = unique[4]
        elif unique == [2, 3, 4, 5, 14]:
            straight = True
            straight_high = 5

    # Groups sorted by (count, rank), highest first: that way the first group
    # is always the one that decides the tie-break.
    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    sizes = [g[1] for g in groups]
    order = [g[0] for g in groups]

    if straight and flush:
        return (STRAIGHT_FLUSH, straight_high)
    if sizes[0] == 4:
        return (FOUR_OF_A_KIND, order[0], order[1])
    if sizes[0] == 3 and sizes[1] == 2:
        return (FULL_HOUSE, order[0], order[1])
    if flush:
        return (FLUSH, *sorted(ranks, reverse=True))
    if straight:
        return (STRAIGHT, straight_high)
    if sizes[0] == 3:
        return (THREE_OF_A_KIND, order[0], order[1], order[2])
    if sizes[0] == 2 and sizes[1] == 2:
        return (TWO_PAIR, order[0], order[1], order[2])
    if sizes[0] == 2:
        return (PAIR, order[0], order[1], order[2], order[3])
    return (HIGH_CARD, *sorted(ranks, reverse=True))


def _straight_high(ranks)->int:
    """
    Top card of the best straight within a set of ranks, or 0.

    The ace also counts as 1 for the A-2-3-4-5 wheel.
    """
    r = set(ranks)
    if 14 in r:
        r = r | {1}
    in_a_row = 0
    for n in range(14, 0, -1):
        if n in r:
            in_a_row += 1
            if in_a_row == 5:
                return n + 4
        else:
            in_a_row = 0
    return 0


def score_7(cards)->tuple:
    """
    Score of the best possible hand, without trying the 21 combinations.

    Returns exactly the same as `best_hand(cards)[0]`, but by looking at the
    counts directly. It exists because the bots call this millions of times
    when estimating their equity and the combinations were very expensive.

    `best_hand` is still the reference: it is the obviously correct version
    and tests/test_poker_hands.py checks that the two always agree.
    """
    ranks = [rank(c) for c in cards]
    suits = [suit(c) for c in cards]

    suit_counts = Counter(suits)
    flush_suit = next((s for s, n in suit_counts.items() if n >= 5), None)

    if flush_suit is not None:
        flush_ranks = sorted((rank(c) for c in cards if suit(c) == flush_suit),
                             reverse=True)
        high = _straight_high(flush_ranks)
        if high:
            return (STRAIGHT_FLUSH, high)

    counts = Counter(ranks)
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    sizes = [g[1] for g in groups]
    order = [g[0] for g in groups]

    if sizes[0] == 4:
        kicker = max(r for r in ranks if r != order[0])
        return (FOUR_OF_A_KIND, order[0], kicker)

    # With seven cards there can be two trips: the second one acts as the pair.
    if sizes[0] == 3 and len(sizes) > 1 and sizes[1] >= 2:
        return (FULL_HOUSE, order[0], order[1])

    if flush_suit is not None:
        return (FLUSH, *flush_ranks[:5])

    high = _straight_high(ranks)
    if high:
        return (STRAIGHT, high)

    if sizes[0] == 3:
        kickers = sorted((r for r in ranks if r != order[0]), reverse=True)[:2]
        return (THREE_OF_A_KIND, order[0], *kickers)

    if sizes[0] == 2 and len(sizes) > 1 and sizes[1] == 2:
        # There can be three pairs; the two highest count, plus the best kicker.
        p1, p2 = order[0], order[1]
        kicker = max(r for r in ranks if r not in (p1, p2))
        return (TWO_PAIR, p1, p2, kicker)

    if sizes[0] == 2:
        kickers = sorted((r for r in ranks if r != order[0]), reverse=True)[:3]
        return (PAIR, order[0], *kickers)

    return (HIGH_CARD, *sorted(ranks, reverse=True)[:5])


def best_hand(cards)->tuple:
    """
    Best 5-card combination among the cards given (usually 7).

    All 21 possible combinations are tried: there are few of them and that
    way there are no tricky cases to get wrong.

    :param cards: iterable of 5 to 7 cards
    :return: (score, tuple of the 5 chosen cards)
    """
    cards = tuple(cards)
    if len(cards) < 5:
        raise ValueError("at least 5 cards are needed")
    if len(cards) == 5:
        return (evaluate_5(cards), cards)

    best_score = None
    best_cards = None
    for combo in combinations(cards, 5):
        s = evaluate_5(combo)
        if best_score is None or s > best_score:
            best_score = s
            best_cards = combo
    return (best_score, best_cards)


def best_omaha_hand(hole, board)->tuple:
    """
    Best Omaha hand: EXACTLY two of the hole cards and three of the board.

    This is the rule that catches Hold'em players out. With four hearts on
    the board and a single heart in hand there is no flush, and four aces on
    the board are worth only three of them. So the 7-card shortcut cannot be
    reused: every 2-from-hole x 3-from-board combination is tried, 6 x 10 = 60
    with four hole cards and a full board.

    :param hole: the hole cards (4 in Omaha)
    :param board: 3 to 5 community cards
    :return: (score, tuple of the 5 chosen cards)
    """
    hole, board = tuple(hole), tuple(board)
    if len(hole) < 2 or len(board) < 3:
        raise ValueError("at least 2 hole cards and 3 board cards are needed")

    best_score = None
    best_cards = None
    threes = list(combinations(board, 3))
    for two in combinations(hole, 2):
        for three in threes:
            combo = two + three
            s = evaluate_5(combo)
            if best_score is None or s > best_score:
                best_score = s
                best_cards = combo
    return (best_score, best_cards)


def score_omaha(hole, board)->tuple:
    """Score only of best_omaha_hand, for the bots' simulations."""
    return best_omaha_hand(hole, board)[0]


def describe(score:tuple)->str:
    """Short text for a score, to show at showdown."""
    cat = score[0]
    name = CATEGORY_NAMES[cat]
    r = RANK_NAMES.get

    if cat == STRAIGHT_FLUSH:
        return f"{name}, {r(score[1])} high"
    if cat == FOUR_OF_A_KIND:
        return f"{name}, {r(score[1])}s"
    if cat == FULL_HOUSE:
        return f"{name}, {r(score[1])}s over {r(score[2])}s"
    if cat == FLUSH:
        return f"{name}, {r(score[1])} high"
    if cat == STRAIGHT:
        return f"{name}, {r(score[1])} high"
    if cat == THREE_OF_A_KIND:
        return f"{name}, {r(score[1])}s"
    if cat == TWO_PAIR:
        return f"{name}, {r(score[1])}s and {r(score[2])}s"
    if cat == PAIR:
        return f"{name} of {r(score[1])}s"
    return f"{name}, {r(score[1])} high"
