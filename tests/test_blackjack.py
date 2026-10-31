"""Tests for the blackjack rules.

Covers the ace value (1 or 11), several aces, natural blackjack, busting, the
dealer's rules, and that the deck survives being saved and loaded back (the
bug that made the kings disappear).
"""

import random
from collections import Counter

from aceroyale.blackjack import rules
from aceroyale.blackjack.rules import (Deck, hand_value, is_blackjack,
                                       is_bust, dealer_must_hit,
                                       resolve, hand_text, is_soft)

SUITS = {"s": 1, "c": 2, "h": 3, "d": 4}
FACES = {"A": 1, "K": 13, "Q": 12, "J": 11, "T": 10}


def c(text):
    """'As' -> ace of spades."""
    face = text[:-1]
    return SUITS[text[-1]] * 100 + (FACES[face] if face in FACES else int(face))


def hand(*t):
    return [c(x) for x in t]


class seeded:
    """Swaps the deck's random generator for a seeded one, so tests repeat."""

    def __init__(self, seed):
        self.seed = seed

    def __enter__(self):
        self.original = rules._rng
        rules._rng = random.Random(self.seed)

    def __exit__(self, *exc):
        rules._rng = self.original
        return False


# ------------------------------------------------------------ ace value

def test_ace_value():
    cases = [
        (("As",),                      11, "A = 11"),
        (("As", "5h"),                 16, "A + 5 = 16"),
        (("As", "Th"),                 21, "A + 10 = 21"),
        (("As", "Kh"),                 21, "A + K = 21"),
        (("As", "7h", "9d"),           17, "A + 7 + 9 = 17 (the ace drops to 1)"),
        (("As", "Ah"),                 12, "A + A = 12"),
        (("As", "Ah", "9d"),           21, "A + A + 9 = 21"),
        (("As", "Ah", "9d", "5c"),     16, "A + A + 9 + 5 = 16"),
        (("As", "Ah", "Ad"),           13, "A + A + A = 13"),
        (("As", "Ah", "Ad", "Ac"),     14, "all four aces = 14"),
        (("As", "Ah", "9d", "Kc"),     21, "A + A + 9 + K = 21"),
        (("As", "7h"),                 18, "A + 7 = 18"),
        (("Ks", "Qh", "Jd"),           30, "three face cards = 30 (bust)"),
        (("As", "2h", "3d", "4c", "5s"), 15, "A+2+3+4+5 = 15 (ace as 1)"),
    ]
    for cards, expected, name in cases:
        v = hand_value(hand(*cards))
        assert v == expected, f"{name}: got {v}"

    assert is_soft(hand("As", "6h")), "A+6 is a soft hand"
    assert not is_soft(hand("As", "7h", "9d")), "A+7+9 is no longer soft"
    text = hand_text(hand("As", "6h"))
    assert text == "7 / 17", f"soft hand is shown as '7 / 17', got {text!r}"
    assert hand_text(hand("Ks", "7h")) == "17", "hard hand shows a single number"


def test_natural_blackjack():
    assert is_blackjack(hand("As", "Kh")), "A + K with two cards is blackjack"
    assert is_blackjack(hand("Ts", "Ah")), "10 + A too"
    assert not is_blackjack(hand("As", "5h", "5d")), \
        "21 with three cards is NOT a natural blackjack"
    assert not is_blackjack(hand("Ks", "Qh")), "20 is not blackjack"


def test_bust():
    assert is_bust(hand("Ks", "Qh", "5d")), "25 is bust"
    assert not is_bust(hand("As", "Kh")), "21 is not bust"
    assert not is_bust(hand("As", "9h", "8d")), \
        "A+9+8 = 18, the ace protects from busting"
    assert is_bust(hand("Ks", "Qh", "As", "Ah")), \
        "K+Q+A+A = 22 is bust even with aces"


def test_dealer():
    assert dealer_must_hit(hand("Ks", "6h")), "hits on 16"
    assert not dealer_must_hit(hand("Ks", "7h")), "stands on 17"
    assert not dealer_must_hit(hand("As", "6h")), "stands on A+6 (soft 17)"
    assert dealer_must_hit(hand("As", "5h")), "hits on A+5 (soft 16)"
    assert not dealer_must_hit(hand("Ks", "Qh")), "stands on 20"


def test_resolve():
    cases = [
        (hand("As", "Kh"), hand("Ks", "Qh"), "player_bj", "player blackjack wins"),
        (hand("Ks", "Qh"), hand("As", "Kd"), "dealer", "dealer blackjack wins"),
        (hand("As", "Kh"), hand("Ah", "Kd"), "push", "two blackjacks push"),
        (hand("Ks", "Qh", "5d"), hand("Ks", "7h"), "dealer", "if the player busts, they lose"),
        (hand("Ks", "7h"), hand("Ks", "Qh", "5d"), "player", "if the dealer busts, the player wins"),
        (hand("Ks", "9h"), hand("Ks", "7d"), "player", "19 beats 17"),
        (hand("Ks", "7h"), hand("Ks", "9d"), "dealer", "17 loses to 19"),
        (hand("Ks", "8h"), hand("Qs", "8d"), "push", "same total, push"),
        (hand("Ks", "Qh", "2d"), hand("Ks", "Qh", "3d"), "dealer",
         "both bust: the dealer wins"),
    ]
    for p, d, expected, name in cases:
        r = resolve(p, d)
        assert r == expected, f"{name}: got {r!r}"

    # After a split, A+K is an ordinary 21, not blackjack.
    r = resolve(hand("As", "Kh"), hand("7s", "4h", "Kd"), can_be_natural=False)
    assert r == "push", f"21 after a split pushes against a dealer 21: got {r!r}"
    r = resolve(hand("As", "Kh"), hand("Ks", "7d"), can_be_natural=False)
    assert r == "player", f"21 after a split beats 17 as an ordinary hand: got {r!r}"
    r = resolve(hand("As", "Kh"), hand("7s", "4h", "Kd"))
    assert r == "player_bj", f"without a split, A+K is still blackjack: got {r!r}"


# ------------------------------------------------------------ the deck

def test_deck():
    d = Deck()
    assert len(d) == 52, f"a new deck has 52 cards, got {len(d)}"
    assert len(set(d.cards)) == 52, "no repeated cards"

    expected = {s * 100 + r for s in (1, 2, 3, 4) for r in range(1, 14)}
    assert set(d.cards) == expected, "exactly the 52 expected cards are there"


def test_deck_round_trip():
    # Round trip: the bug that ate the kings.
    with seeded(1):
        d = Deck()
        for _ in range(7):
            d.draw()
    before = sorted(d.cards)
    reloaded = Deck(str(d))
    assert sorted(reloaded.cards) == before, \
        f"the deck survives save and reload intact; lost={sorted(set(before) - set(reloaded.cards))}"

    # The kings specifically.
    d = Deck()
    kings = {113, 213, 313, 413}
    reloaded = Deck(str(d))
    assert kings <= set(reloaded.cards), \
        f"the four kings are still there after reloading; missing={sorted(kings - set(reloaded.cards))}"

    # A corrupt string must not blow up.
    assert len(Deck("garbage")) == 52, "an invalid string gives a fresh deck"
    assert len(Deck("0" * 52)) == 52, "an empty deck resets itself"


def test_kings_are_dealt():
    # And that they really come out when dealing, which is what the player suffered.
    seen = Counter()
    dealt = 0
    with seeded(2):
        for _ in range(300):
            d = Deck()
            d.draw()
            saved = str(d)
            for _ in range(6):
                d = Deck(saved)
                if len(d) < 14:
                    d.reset()
                card = d.draw()
                seen[card[1]] += 1
                dealt += 1
                saved = str(d)
    expected = dealt / 13
    assert seen[13] > expected * 0.6, \
        f"kings come out when dealing ({seen[13]} of {dealt}, expected ~{expected:.0f}); before the fix, 0"

    # Every rank shows up.
    missing = [r for r in range(1, 14) if seen[r] == 0]
    assert not missing, f"all thirteen ranks show up; missing {missing}"


def test_no_repeated_cards():
    bad = 0
    with seeded(3):
        for _ in range(500):
            d = Deck()
            dealt = d.deal(20)
            if len(set(dealt)) != 20:
                bad += 1
    assert bad == 0, f"500 deals of 20 cards without duplicates; {bad} bad"
