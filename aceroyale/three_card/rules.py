"""Three Card Poker rules.

Pure Python, no I/O, like blackjack/rules.py and baccarat/rules.py.

Same card encoding as the rest of the project:

    XYY  ->  X = suit (1 spades, 2 clubs, 3 hearts, 4 diamonds)
             YY = rank 01..13  (1 ace, 11 J, 12 Q, 13 K)

The game, as these rules apply it:

  - The player bets Ante (mandatory) and, optionally, Pair Plus.
  - Player and dealer receive three cards each; the dealer's face down.
  - The player looks at theirs and decides: Play (places another bet equal to
    the Ante) or Fold (gives up and loses the Ante and the Pair Plus).
  - The dealer "qualifies" with queen high or better. If it does not qualify,
    the Ante pays 1:1 and the Play is returned. If it qualifies, the hands are
    compared: player wins -> Ante and Play pay 1:1; dealer wins -> both are
    lost; tie -> both are returned.
  - Ante bonus (if the player plays, whatever happens with the dealer):
    straight 1:1, three of a kind 4:1, straight flush 5:1.
  - Pair Plus only looks at the player's hand: pair 1:1, flush 4:1,
    straight 6:1, three of a kind 30:1, straight flush 40:1.

Careful: with three cards the hand ranking is NOT the one from regular poker:
the straight beats the flush, because it is harder to make.
"""

from collections import Counter
from random import SystemRandom

_rng = SystemRandom()

SUITS = (1, 2, 3, 4)
RANKS = tuple(range(1, 14))

# Categories, from worst to best
HIGH_CARD       = 0
PAIR            = 1
FLUSH           = 2
STRAIGHT        = 3
THREE_OF_A_KIND = 4
STRAIGHT_FLUSH  = 5

NAMES = {
    STRAIGHT_FLUSH:  "Straight flush",
    THREE_OF_A_KIND: "Three of a kind",
    STRAIGHT:        "Straight",
    FLUSH:           "Flush",
    PAIR:            "Pair",
    HIGH_CARD:       "High card",
}

RANK_NAME = {14: "Ace", 13: "King", 12: "Queen", 11: "Jack", 10: "Ten",
             9: "Nine", 8: "Eight", 7: "Seven", 6: "Six", 5: "Five",
             4: "Four", 3: "Three", 2: "Two"}
RANK_PLURAL = {14: "Aces", 13: "Kings", 12: "Queens", 11: "Jacks", 10: "Tens",
               9: "Nines", 8: "Eights", 7: "Sevens", 6: "Sixes", 5: "Fives",
               4: "Fours", 3: "Threes", 2: "Twos"}

QUEEN = 12

# What each bet pays, "to 1": 30 means the player wins 30 times the stake and
# also gets the stake back.
PAIR_PLUS_PAYOUT = {PAIR: 1, FLUSH: 4, STRAIGHT: 6, THREE_OF_A_KIND: 30, STRAIGHT_FLUSH: 40}
ANTE_BONUS_PAYOUT = {STRAIGHT: 1, THREE_OF_A_KIND: 4, STRAIGHT_FLUSH: 5}


# --------------------------------------------------------------- cards

def rank(card: int) -> int:
    """Poker rank: the ace is 14."""
    r = card % 100
    return 14 if r == 1 else r


def suit(card: int) -> int:
    return card // 100


def full_deck() -> list:
    return [s * 100 + r for s in SUITS for r in RANKS]


class Deck:
    """
    A 52-card deck from which cards are drawn at random.

    :param exclude: cards that are already out (the player's, when dealing to
        the dealer afterwards).
    """

    def __init__(self, exclude=()):
        out = set(exclude)
        self.cards = [c for c in full_deck() if c not in out]

    def draw(self) -> int:
        return self.cards.pop(_rng.randrange(len(self.cards)))

    def deal(self, count: int = 3) -> list:
        return [self.draw() for _ in range(count)]

    def __len__(self):
        return len(self.cards)


# --------------------------------------------------------------- evaluate

def evaluate(cards) -> tuple:
    """
    Score of a three-card hand, comparable with < and >.

    The first element is the category and the rest are the tie-breakers.
    A-2-3 is a straight (the lowest one, it counts as "3 high"); Q-K-A is the
    highest.
    """
    if len(cards) != 3:
        raise ValueError("a three-card hand has three cards")
    ranks = sorted((rank(c) for c in cards), reverse=True)
    flush = len({suit(c) for c in cards}) == 1

    straight = None
    if len(set(ranks)) == 3:
        if ranks[0] - ranks[2] == 2:
            straight = ranks[0]
        elif ranks == [14, 3, 2]:
            straight = 3                       # A-2-3: the ace counts as 1

    if straight and flush:
        return (STRAIGHT_FLUSH, straight)
    if ranks[0] == ranks[2]:
        return (THREE_OF_A_KIND, ranks[0])
    if straight:
        return (STRAIGHT, straight)
    if flush:
        return (FLUSH, *ranks)

    counts = Counter(ranks)
    if 2 in counts.values():
        pair = next(r for r, n in counts.items() if n == 2)
        kicker = next(r for r, n in counts.items() if n == 1)
        return (PAIR, pair, kicker)
    return (HIGH_CARD, *ranks)


def describe(score: tuple) -> str:
    """'Pair of Kings', 'Queen high', 'Straight'..."""
    cat = score[0]
    if cat == PAIR:
        return f"Pair of {RANK_PLURAL[score[1]]}"
    if cat == THREE_OF_A_KIND:
        return f"Three {RANK_PLURAL[score[1]]}"
    if cat == HIGH_CARD:
        return f"{RANK_NAME[score[1]]} high"
    return NAMES[cat]


def dealer_qualifies(score: tuple) -> bool:
    """The dealer plays with queen high or better."""
    return score[0] > HIGH_CARD or score[1] >= QUEEN


# --------------------------------------------------------------- payouts

def _line(staked, returned):
    if returned > staked:
        result = "win"
    elif returned == staked:
        result = "push"
    else:
        result = "lose"
    return {"staked": staked, "returned": returned, "result": result}


def settle(ante: int, pair_plus: int, player, dealer, plays: bool) -> dict:
    """
    How much comes back from each bet, stake included.

    :param plays: True if the player chose Play; False if they folded.
    :return: {"lines": {"ante", "play", "pair_plus", "bonus"} (only those
              present), "qualifies", "winner", "player_hand", "dealer_hand",
              "staked", "returned", "net"}
    """
    sp, sd = evaluate(player), evaluate(dealer)
    qualifies = dealer_qualifies(sd)
    lines = {}

    if not plays:
        # Folding costs the Ante and the Pair Plus.
        lines["ante"] = _line(ante, 0)
        if pair_plus:
            lines["pair_plus"] = _line(pair_plus, 0)
        winner = "dealer"
    else:
        play = ante
        if not qualifies:
            lines["ante"] = _line(ante, ante * 2)
            lines["play"] = _line(play, play)
            winner = "player"
        elif sp > sd:
            lines["ante"] = _line(ante, ante * 2)
            lines["play"] = _line(play, play * 2)
            winner = "player"
        elif sd > sp:
            lines["ante"] = _line(ante, 0)
            lines["play"] = _line(play, 0)
            winner = "dealer"
        else:
            lines["ante"] = _line(ante, ante)
            lines["play"] = _line(play, play)
            winner = "tie"

        # The bonus is not a bet: it is an extra prize on top of the Ante, and
        # it is paid even if the dealer wins the hand.
        bonus = ante * ANTE_BONUS_PAYOUT.get(sp[0], 0)
        if bonus:
            lines["bonus"] = {"staked": 0, "returned": bonus, "result": "win"}

        if pair_plus:
            mult = PAIR_PLUS_PAYOUT.get(sp[0])
            lines["pair_plus"] = _line(pair_plus, pair_plus * (mult + 1) if mult else 0)

    staked = sum(l["staked"] for l in lines.values())
    returned = sum(l["returned"] for l in lines.values())
    return {
        "lines": lines,
        "qualifies": qualifies,
        "winner": winner,
        "player_hand": describe(sp),
        "dealer_hand": describe(sd),
        "staked": staked,
        "returned": returned,
        "net": returned - staked,
    }
