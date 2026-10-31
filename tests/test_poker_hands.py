"""Tests for the poker hand evaluator (aceroyale.poker.hands)."""

import random
from collections import Counter
from itertools import combinations

from aceroyale.poker import hands
from aceroyale.poker.hands import (
    evaluate_5, score_7, best_hand, full_deck, describe,
)


def c(text):
    """'As' -> 101 (ace of spades). Suits: s spades, c clubs, h hearts, d diamonds."""
    suits = {"s": 1, "c": 2, "h": 3, "d": 4}
    ranks = {"A": 1, "K": 13, "Q": 12, "J": 11, "T": 10}
    face = text[:-1]
    r = ranks.get(face, None)
    if r is None:
        r = int(face)
    return suits[text[-1]] * 100 + r


def cards(*texts):
    return [c(t) for t in texts]


# ---------------------------------------------------------------- categories

def test_categories():
    cases = [
        (cards("As", "Ks", "Qs", "Js", "Ts"), hands.STRAIGHT_FLUSH, "royal flush"),
        (cards("5h", "4h", "3h", "2h", "Ah"), hands.STRAIGHT_FLUSH, "5-high straight flush (wheel)"),
        (cards("9c", "9h", "9d", "9s", "2c"), hands.FOUR_OF_A_KIND, "four of a kind"),
        (cards("8c", "8h", "8d", "3s", "3c"), hands.FULL_HOUSE, "full house"),
        (cards("Ac", "Jc", "8c", "5c", "2c"), hands.FLUSH, "flush"),
        (cards("9c", "8h", "7d", "6s", "5c"), hands.STRAIGHT, "straight"),
        (cards("5h", "4d", "3c", "2s", "Ah"), hands.STRAIGHT, "wheel A-2-3-4-5"),
        (cards("Qc", "Qh", "Qd", "9s", "4c"), hands.THREE_OF_A_KIND, "three of a kind"),
        (cards("Kc", "Kh", "7d", "7s", "4c"), hands.TWO_PAIR, "two pair"),
        (cards("Ac", "Ah", "9d", "6s", "3c"), hands.PAIR, "pair"),
        (cards("Ac", "Jh", "9d", "6s", "3c"), hands.HIGH_CARD, "high card"),
    ]
    for hand, expected, name in cases:
        s = evaluate_5(hand)
        assert s[0] == expected, f"{name}: got {hands.CATEGORY_NAMES[s[0]]}"

    # the wheel is the LOWEST straight: its top card is the 5, not the ace
    s = evaluate_5(cards("5h", "4d", "3c", "2s", "Ah"))
    assert s[1] == 5, f"the wheel is 5-high, not ace-high: high={s[1]}"


# ---------------------------------------------------------------- ordering

def test_ordering():
    pairs = [
        ("As Ks Qs Js Ts", "9c 9h 9d 9s 2c", "straight flush > four of a kind"),
        ("9c 9h 9d 9s 2c", "8c 8h 8d 3s 3c", "four of a kind > full house"),
        ("8c 8h 8d 3s 3c", "Ac Jc 8c 5c 2c", "full house > flush"),
        ("Ac Jc 8c 5c 2c", "9c 8h 7d 6s 5c", "flush > straight"),
        ("9c 8h 7d 6s 5c", "Qc Qh Qd 9s 4c", "straight > three of a kind"),
        ("Qc Qh Qd 9s 4c", "Kc Kh 7d 7s 4c", "three of a kind > two pair"),
        ("Kc Kh 7d 7s 4c", "Ac Ah 9d 6s 3c", "two pair > pair"),
        ("Ac Ah 9d 6s 3c", "Ac Jh 9d 6s 3c", "pair > high card"),
        # fine tie-breaks
        ("Ac Ah Kd 6s 3c", "Ac Ah Qd 6s 3c", "same pair, kicker wins"),
        ("Kc Kh 7d 7s 9c", "Kc Kh 7d 7s 4c", "same two pair, kicker wins"),
        ("Ac Kc 8c 5c 2c", "Ah Kh 8h 5h 3h", "same flush up to the fourth card, the fifth decides... reversed"),
        ("9c 8h 7d 6s 5c", "8c 7h 6d 5s 4c", "higher straight wins"),
        ("Ac Ah Ad As Kc", "Ac Ah Ad As Qc", "same four of a kind, kicker wins"),
    ]
    for a, b, name in pairs:
        sa = evaluate_5(cards(*a.split()))
        sb = evaluate_5(cards(*b.split()))
        if name.endswith("reversed"):
            assert sa < sb, f"{name}: {sa} vs {sb}"
        else:
            assert sa > sb, f"{name}: {sa} vs {sb}"

    # exact tie (same ranks, different suits): suits do not break ties
    sa = evaluate_5(cards("Ac", "Kh", "9d", "6s", "3c"))
    sb = evaluate_5(cards("Ad", "Ks", "9h", "6c", "3d"))
    assert sa == sb, f"suits do not break ties: {sa} vs {sb}"


# ---------------------------------------------------------------- 7 cards

def test_best_of_seven():
    s, five = best_hand(cards("As", "Ks", "Qs", "Js", "Ts", "2c", "7d"))
    assert s[0] == hands.STRAIGHT_FLUSH, "finds the royal flush among 7"

    # a 6-card flush must take the 5 highest
    s, five = best_hand(cards("Ac", "Kc", "9c", "6c", "3c", "2c", "7d"))
    assert s[0] == hands.FLUSH and s[1] == 14 and s[2] == 13 and s[3] == 9, \
        f"the flush takes the 5 highest cards: {s}"

    # trips + pair must give a full house, not trips
    s, _ = best_hand(cards("8c", "8h", "8d", "3s", "3c", "Ah", "Kd"))
    assert s[0] == hands.FULL_HOUSE, "trips + pair = full house"

    # the wheel using the board
    s, _ = best_hand(cards("Ah", "2d", "3c", "4s", "5h", "Kd", "Qc"))
    assert s[0] == hands.STRAIGHT and s[1] == 5, "wheel with 7 cards"


def test_best_hand_needs_five_cards():
    try:
        best_hand(cards("As", "Ks", "Qs", "Js"))
    except ValueError:
        return
    assert False, "best_hand with 4 cards must raise ValueError"


def test_describe():
    assert describe(evaluate_5(cards("As", "Ks", "Qs", "Js", "Ts"))) == "Straight flush, A high"
    assert describe(evaluate_5(cards("8c", "8h", "8d", "3s", "3c"))) == "Full house, 8s over 3s"
    assert describe(evaluate_5(cards("Kc", "Kh", "7d", "7s", "4c"))) == "Two pair, Ks and 7s"
    assert describe(evaluate_5(cards("Ac", "Ah", "9d", "6s", "3c"))) == "Pair of As"
    assert describe(evaluate_5(cards("5h", "4d", "3c", "2s", "Ah"))) == "Straight, 5 high"


# ------------------------------------------- fast path vs reference

def test_score_7_matches_reference_on_random_hands():
    """score_7 must return exactly best_hand(...)[0] (random 5, 6 and 7-card hands)."""
    rng = random.Random(2024)
    deck = full_deck()
    for n in range(30000):
        size = (7, 7, 6, 5)[n % 4]
        hand = rng.sample(deck, size)
        fast = score_7(hand)
        ref = best_hand(hand)[0]
        assert fast == ref, f"{hand}: score_7={fast} best_hand={ref}"


def test_score_7_matches_reference_on_tricky_hands():
    """Hand-picked 7-card cases where the shortcuts are easy to get wrong."""
    tricky = [
        "8c 8h 8d 3s 3c 3h Ah",     # two trips: the second one is the pair
        "Kc Kh 7d 7s 4c 4h Ad",     # three pairs: kicker can come from the third pair
        "Kc Kh 7d 7s 4c 4h 2d",     # three pairs, kicker is the lowest pair
        "9c 9h 9d 9s 8c 8h 8d",     # quads + trips
        "Ah 2h 3h 4h 5h 6h 7d",     # straight flush 6-high inside a 6-card flush
        "Ah Kh Qh Jh 9h 8h Th",     # 7-card flush, royal inside
        "Ah 2d 3c 4s 5h 6d 7c",     # straight 7-high, not the wheel
        "Ac Ad 2h 3h 4h 5h 9h",     # flush beats the wheel and the pair
    ]
    for text in tricky:
        hand = cards(*text.split())
        assert score_7(hand) == best_hand(hand)[0], \
            f"{text}: score_7={score_7(hand)} best_hand={best_hand(hand)[0]}"


# ------------------------------------------------- frequencies (exact)

TRUE_FREQUENCIES = {
    hands.STRAIGHT_FLUSH: 40,
    hands.FOUR_OF_A_KIND: 624,
    hands.FULL_HOUSE: 3744,
    hands.FLUSH: 5108,
    hands.STRAIGHT: 10200,
    hands.THREE_OF_A_KIND: 54912,
    hands.TWO_PAIR: 123552,
    hands.PAIR: 1098240,
    hands.HIGH_CARD: 1302540,
}


def test_exact_frequencies():
    """Full enumeration of all 2,598,960 five-card hands (takes a few seconds)."""
    counts = Counter()
    for combo in combinations(full_deck(), 5):
        counts[evaluate_5(combo)[0]] += 1
    total = sum(counts.values())
    assert total == 2598960, f"all hands counted: {total}"
    for cat, expected in sorted(TRUE_FREQUENCIES.items(), reverse=True):
        assert counts[cat] == expected, \
            f"{hands.CATEGORY_NAMES[cat]}: expected {expected}, got {counts[cat]}"
