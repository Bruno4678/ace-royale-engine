"""No-limit Texas Hold'em: hand evaluator, single-hand engine and bots.

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
)
from .engine import Seat, Hand
from .bots import (
    Personality, PERSONALITIES, LEVEL_ORDER, BotView, BotStrategy,
    estimate_equity, create_strategy, view_for, available_names,
)

__all__ = [
    "STRAIGHT_FLUSH", "FOUR_OF_A_KIND", "FULL_HOUSE", "FLUSH", "STRAIGHT",
    "THREE_OF_A_KIND", "TWO_PAIR", "PAIR", "HIGH_CARD", "CATEGORY_NAMES",
    "RANK_NAMES", "rank", "suit", "full_deck", "evaluate_5", "score_7",
    "best_hand", "describe",
    "Seat", "Hand",
    "Personality", "PERSONALITIES", "LEVEL_ORDER", "BotView", "BotStrategy",
    "estimate_equity", "create_strategy", "view_for", "available_names",
]
