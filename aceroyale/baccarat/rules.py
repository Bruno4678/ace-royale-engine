"""Baccarat rules (punto banco).

Pure Python, no I/O, just like blackjack/rules.py: this way the rules are
tested on their own and no caller can skip them.

Same card encoding as the rest of the project:

    XYY  ->  X = suit (1 spades, 2 clubs, 3 hearts, 4 diamonds)
             YY = rank 01..13  (1 ace, 11 J, 12 Q, 13 K)

What you need to know about the game:

  - The player decides nothing during the hand. They bet on Player, on Banker
    or on Tie (or on several) and the cards come out on their own following
    fixed tables.
  - Points: the ace is worth 1, 2 to 9 their face value, the 10 and the face
    cards 0. The hand is worth the last digit of the sum (7 + 8 = 15 -> 5).
  - Payouts: Player 1:1. Banker 1:1 minus a 5 % commission, rounded down
    (winning with 100 pays 95). Tie 8:1. On a tie, whatever was bet on Player
    and on Banker is returned.
"""

from random import SystemRandom

# Cryptographic generator: the deal must not be predictable.
_rng = SystemRandom()

SUITS = (1, 2, 3, 4)
RANKS = tuple(range(1, 14))

BANKER_COMMISSION = 5       # percent, on what is won on Banker
TIE_PAYOUT = 8              # Tie pays 8 to 1

BETS = ("player", "banker", "tie")


# --------------------------------------------------------------- points

def card_points(card: int) -> int:
    """What a card adds: ace 1, 2..9 their number, 10 and face cards 0."""
    rank = card % 100
    return rank if rank < 10 else 0


def hand_value(cards) -> int:
    """The last digit of the sum of the hand."""
    return sum(card_points(c) for c in cards) % 10


def is_natural(cards) -> bool:
    """8 or 9 with the first two cards: nobody draws any more."""
    return len(cards) == 2 and hand_value(cards) >= 8


# --------------------------------------------------------------- third card

def player_draws(player_cards) -> bool:
    """The player draws on 0..5 and stands on 6 or 7."""
    return hand_value(player_cards) <= 5


def banker_draws(banker_cards, player_third=None) -> bool:
    """
    Whether the banker draws a third card.

    :param player_third: the player's third card, or None if the player stood.

    If the player stood, the banker plays like the player: draws on 0..5. If
    the player drew, the usual table applies, which looks at the banker's
    total and at the POINTS of that third player card:

        banker 0-2  always draws
        banker 3    draws unless the player's third card is an 8
        banker 4    draws if it is 2..7
        banker 5    draws if it is 4..7
        banker 6    draws if it is 6 or 7
        banker 7    stands
    """
    total = hand_value(banker_cards)
    if player_third is None:
        return total <= 5

    p = card_points(player_third)
    if total <= 2:
        return True
    if total == 3:
        return p != 8
    if total == 4:
        return 2 <= p <= 7
    if total == 5:
        return 4 <= p <= 7
    if total == 6:
        return p in (6, 7)
    return False


# --------------------------------------------------------------- the shoe

class Shoe:
    """
    Eight decks shuffled together, drawn at random.

    A fresh shoe is used for every hand (like a continuous shuffler), so it
    never has to be stored anywhere and counting cards is useless.
    """

    def __init__(self, decks: int = 8):
        self.cards = [s * 100 + r for _ in range(decks) for s in SUITS for r in RANKS]

    def draw(self) -> int:
        return self.cards.pop(_rng.randrange(len(self.cards)))

    def __len__(self):
        return len(self.cards)


# --------------------------------------------------------------- one hand

def play_hand(draw):
    """
    Deals a complete hand.

    :param draw: function with no arguments that returns the next card
        (Shoe().draw in play; a fixed list in the tests).
    :return: dict with each side's cards, the order in which they came out,
        the totals and who wins ("player" | "banker" | "tie").
    """
    player, banker, order = [], [], []

    def give(hand, side):
        c = draw()
        hand.append(c)
        order.append({"side": side, "card": c})
        return c

    # Dealt alternately, as at the table: player, banker, player, banker.
    give(player, "player")
    give(banker, "banker")
    give(player, "player")
    give(banker, "banker")

    third = None
    if not (is_natural(player) or is_natural(banker)):
        if player_draws(player):
            third = give(player, "player")
        if banker_draws(banker, third):
            give(banker, "banker")

    vp, vb = hand_value(player), hand_value(banker)
    if vp > vb:
        winner = "player"
    elif vb > vp:
        winner = "banker"
    else:
        winner = "tie"

    return {
        "player": player,
        "banker": banker,
        "order": order,
        "player_value": vp,
        "banker_value": vb,
        "natural": is_natural(player) or is_natural(banker),
        "winner": winner,
    }


# --------------------------------------------------------------- payouts

def commission(won: int) -> int:
    """5 % of what is won on Banker, rounded down."""
    return won * BANKER_COMMISSION // 100


def payout(bet: str, amount: int, winner: str) -> int:
    """
    Chips that come back to the player for ONE bet, stake included.

    0 if it loses; the stake if it is returned; stake + prize if it wins.
    """
    if amount <= 0:
        return 0
    if bet == "tie":
        return amount * (TIE_PAYOUT + 1) if winner == "tie" else 0
    if winner == "tie":
        return amount                         # Player and Banker are returned
    if bet != winner:
        return 0
    if bet == "banker":
        return amount * 2 - commission(amount)
    return amount * 2


def settle(bets: dict, winner: str) -> dict:
    """
    Result of each betting box and the total that comes back.

    :param bets: {"player": n, "banker": n, "tie": n} (missing ones count as 0)
    :return: {"per_bet": {box: {"staked", "returned", "result"}},
              "staked", "returned", "net"}
    """
    per_bet = {}
    staked = returned = 0
    for name in BETS:
        n = int(bets.get(name, 0) or 0)
        if n <= 0:
            continue
        r = payout(name, n, winner)
        if r > n:
            result = "win"
        elif r == n:
            result = "push"
        else:
            result = "lose"
        per_bet[name] = {"staked": n, "returned": r, "result": result}
        staked += n
        returned += r
    return {"per_bet": per_bet, "staked": staked,
            "returned": returned, "net": returned - staked}
