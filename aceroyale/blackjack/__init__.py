"""Ace Royale blackjack rules, kept as plain functions so they can be tested."""

from .rules import (
    Deck,
    hand_value,
    is_soft,
    is_blackjack,
    is_bust,
    dealer_must_hit,
    resolve,
    hand_text,
    can_double,
    can_split,
    is_pair_of_aces,
    offers_insurance,
    insurance_payout,
    MAX_SPLITS,
)

__all__ = [
    "Deck", "hand_value", "is_soft", "is_blackjack", "is_bust",
    "dealer_must_hit", "resolve", "hand_text",
    "can_double", "can_split", "is_pair_of_aces",
    "offers_insurance", "insurance_payout", "MAX_SPLITS",
]
