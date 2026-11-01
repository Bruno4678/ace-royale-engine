"""No-limit Texas Hold'em and Pot-Limit Omaha: evaluators, single-hand engines,
bots and Spins (three-player sit & go with a prize multiplier).

Typical loop::

    from aceroyale.poker import Hand, Seat, create_strategy, view_for

    seats = [Seat("A", 1000, is_bot=True), Seat("B", 1000, is_bot=True)]
    bots = [create_strategy("expert", seed=1), create_strategy("beginner", seed=2)]
    hand = Hand(seats, button=0, small_blind=5, big_blind=10)
    while not hand.finished:
        i = hand.turn
        action, amount = bots[i].decide(view_for(hand, i))
        hand.act(i, action, amount)     # raises ValueError if illegal
    print(hand.result)
"""

from .hands import (
    STRAIGHT_FLUSH, FOUR_OF_A_KIND, FULL_HOUSE, FLUSH, STRAIGHT,
    THREE_OF_A_KIND, TWO_PAIR, PAIR, HIGH_CARD, CATEGORY_NAMES, RANK_NAMES,
    rank, suit, full_deck, evaluate_5, score_7, best_hand, describe,
    best_omaha_hand, score_omaha,
)
from .engine import Seat, Hand, OmahaHand
from .bots import (
    Personality, PERSONALITIES, LEVEL_ORDER, BotView, BotStrategy,
    estimate_equity, create_strategy, view_for, available_names,
)
from .spins import (
    MULTIPLIERS, BLIND_SCHEDULE, SpinTournament, play_spin, draw_multiplier,
    expected_multiplier, return_to_players,
)

__all__ = [
    "STRAIGHT_FLUSH", "FOUR_OF_A_KIND", "FULL_HOUSE", "FLUSH", "STRAIGHT",
    "THREE_OF_A_KIND", "TWO_PAIR", "PAIR", "HIGH_CARD", "CATEGORY_NAMES",
    "RANK_NAMES", "rank", "suit", "full_deck", "evaluate_5", "score_7",
    "best_hand", "describe", "best_omaha_hand", "score_omaha",
    "Seat", "Hand", "OmahaHand",
    "Personality", "PERSONALITIES", "LEVEL_ORDER", "BotView", "BotStrategy",
    "estimate_equity", "create_strategy", "view_for", "available_names",
    "MULTIPLIERS", "BLIND_SCHEDULE", "SpinTournament", "play_spin",
    "draw_multiplier", "expected_multiplier", "return_to_players",
]
