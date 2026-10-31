"""Blackjack rules.

Pure Python, no I/O: this way the rules can be tested on their own and no
caller can "skip" them by accident.

Card encoding (the same one used across the whole project):

    XYY  ->  X = suit (1 spades, 2 clubs, 3 hearts, 4 diamonds)
             YY = rank 01..13  (1 ace, 11 J, 12 Q, 13 K)

Two things that USED to be wrong and are fixed here:

1. The ace was always worth 1, so A+K added up to 11 and a blackjack was
   impossible. Now the ace is worth 11 as long as the hand does not go over
   21, and 1 as soon as it gets in the way: the hand is evaluated as a whole,
   not card by card.

2. Saving the deck and loading it back lost the four kings. The serialisation
   used 100*((i//13)+1)+(i%13), which for i=13 gave 200 instead of 113. After
   the first hand the game was played with 48 cards without anyone noticing.
   Now the position of each card in the string is computed in one single
   place, shared by reading and writing, and there is a round-trip test.
"""

from random import SystemRandom

# Cryptographic generator: the deal must not be predictable.
_rng = SystemRandom()

SUITS = (1, 2, 3, 4)
RANKS = tuple(range(1, 14))
DECK_SIZE = len(SUITS) * len(RANKS)

TARGET = 21
DEALER_STANDS_ON = 17         # the dealer hits on 16 or less


# --------------------------------------------------------------- helpers

def index_of(card: int) -> int:
    """Position 0..51 that a card takes in the saved string."""
    suit = card // 100
    rank = card % 100
    return (suit - 1) * len(RANKS) + (rank - 1)


def from_index(i: int) -> int:
    """Inverse of `index_of`."""
    suit, rank = divmod(i, len(RANKS))
    return (suit + 1) * 100 + (rank + 1)


def card_points(card: int) -> int:
    """Points of a card counting the ace as 1 (the adjustment is in hand_value)."""
    rank = card % 100
    return 10 if rank > 10 else rank


def is_ace(card: int) -> bool:
    return card % 100 == 1


# --------------------------------------------------------------- hand value

def hand_value(cards) -> int:
    """
    Score of a hand, with the ace worth 11 or 1, whichever suits it.

    All aces are added as 1 and then ONE of them is raised to 11 if it fits.
    There is no point in raising two: 11+11 is already 22.

        A          -> 11
        A + 5      -> 16
        A + 10     -> 21
        A + 7 + 9  -> 17   (the ace drops to 1)
        A + A      -> 12   (one is worth 11, the other 1)
        A + A + 9  -> 21
        A + A + 9 + 5 -> 16
    """
    total = sum(card_points(c) for c in cards)
    if any(is_ace(c) for c in cards) and total + 10 <= TARGET:
        total += 10
    return total


def is_soft(cards) -> bool:
    """
    Whether the hand is "soft": it has an ace counting as 11.

    It matters because a soft hand cannot bust by taking one more card.
    """
    total = sum(card_points(c) for c in cards)
    return any(is_ace(c) for c in cards) and total + 10 <= TARGET


def hand_text(cards) -> str:
    """How the score is shown: '17', or '7 / 17' if the hand is soft."""
    if not cards:
        return "0"
    hard = sum(card_points(c) for c in cards)
    soft = hand_value(cards)
    if soft != hard and soft <= TARGET:
        return f"{hard} / {soft}"
    return str(soft)


def is_blackjack(cards) -> bool:
    """21 with the first two cards. Not the same as reaching 21 by hitting."""
    return len(cards) == 2 and hand_value(cards) == TARGET


def is_bust(cards) -> bool:
    return hand_value(cards) > TARGET


def dealer_must_hit(cards) -> bool:
    """
    The dealer hits on 16 or less and stands on 17 or more.

    It does not look at the player's hand: that is not blackjack. (The
    previous version stopped hitting if the dealer was already winning.)
    """
    return hand_value(cards) < DEALER_STANDS_ON


def resolve(player, dealer, can_be_natural: bool = True) -> str:
    """
    Compares the two finished hands.

    :param can_be_natural: False for a hand that comes from a split. Its
        two-card 21 is an ordinary 21: it pushes against a dealer 21 instead
        of beating it as if it were a blackjack.
    :return: "player_bj" | "player" | "dealer" | "push"
    """
    player_bj = can_be_natural and is_blackjack(player)
    dealer_bj = is_blackjack(dealer)

    if player_bj and dealer_bj:
        return "push"
    if player_bj:
        return "player_bj"
    if dealer_bj:
        return "dealer"

    if is_bust(player):
        return "dealer"
    if is_bust(dealer):
        return "player"

    vp, vd = hand_value(player), hand_value(dealer)
    if vp > vd:
        return "player"
    if vd > vp:
        return "dealer"
    return "push"


# --------------------------------------------------------------- deck

class Deck:
    """
    52-card deck that can be saved as text and restored intact.

    The string has 52 positions: '1' if the card is still in the deck, '0' if
    it has already been dealt. The format is kept from the previous version so
    that decks saved with it still load.
    """

    def __init__(self, preloaded: str = None):
        if isinstance(preloaded, str) and len(preloaded) == DECK_SIZE:
            self.cards = [from_index(i) for i, c in enumerate(preloaded) if c == "1"]
            if not self.cards:
                self.reset()
        else:
            self.reset()

    def reset(self):
        """Fresh, complete deck."""
        self.cards = [s * 100 + r for s in SUITS for r in RANKS]
        return None

    def draw(self):
        """
        Draws a random card and returns it.

        :return: (card_id, rank 1..13, suit 1..4, points with the ace as 1)
        """
        if not self.cards:
            self.reset()
        c = self.cards.pop(_rng.randrange(len(self.cards)))
        return (c, c % 100, c // 100, card_points(c))

    def deal(self, count: int = 1) -> list:
        """Several cards at once; returns only the identifiers."""
        return [self.draw()[0] for _ in range(count)]

    def __len__(self):
        return len(self.cards)

    def __contains__(self, card):
        return card in self.cards

    def __str__(self):
        """Serialises the deck. `index_of` is the single source of the position."""
        marks = ["0"] * DECK_SIZE
        for c in self.cards:
            marks[index_of(c)] = "1"
        return "".join(marks)


# --------------------------------------------------- double, split, insurance

MAX_SPLITS = 3              # up to 4 hands in total


def can_double(cards) -> bool:
    """
    Doubling only with the first two cards.

    The bet is doubled and the player gets ONE more card, and stands with it.
    """
    return len(cards) == 2


def can_split(cards) -> bool:
    """
    Splitting when the first two cards are worth the same.

    The comparison is by POINTS and not by face, so K+Q can be split (both
    are worth 10), which is how most casinos do it.
    """
    if len(cards) != 2:
        return False
    return card_points(cards[0]) == card_points(cards[1])


def is_pair_of_aces(cards) -> bool:
    """Pair of aces: when split, each hand receives a single card."""
    return len(cards) == 2 and all(is_ace(c) for c in cards)


def offers_insurance(dealer_upcard) -> bool:
    """Insurance is offered when the dealer's face-up card is an ace."""
    return is_ace(dealer_upcard)


def insurance_payout(insurance_bet: int) -> int:
    """Insurance pays 2:1, i.e. three times the stake comes back."""
    return insurance_bet * 3
