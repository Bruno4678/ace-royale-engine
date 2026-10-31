"""Tests for the Three Card Poker rules.

The hands are tested with fixed cards.
"""

from aceroyale.three_card.rules import (HIGH_CARD, FLUSH, STRAIGHT, STRAIGHT_FLUSH,
                                        PAIR, THREE_OF_A_KIND, dealer_qualifies,
                                        describe, evaluate, settle)


# ------------------------------------------------------------ hands

def test_categories():
    cases = [
        ([409, 410, 411], STRAIGHT_FLUSH, "9-10-J of the same suit is a straight flush"),
        ([107, 207, 307], THREE_OF_A_KIND, "three sevens are three of a kind"),
        ([304, 205, 106], STRAIGHT, "4-5-6 is a straight"),
        ([101, 202, 303], STRAIGHT, "A-2-3 is a straight"),
        ([112, 213, 301], STRAIGHT, "Q-K-A is a straight"),
        ([113, 201, 302], HIGH_CARD, "K-A-2 is NOT a straight"),
        ([402, 408, 412], FLUSH, "three of the same suit is a flush"),
        ([113, 313, 205], PAIR, "two kings are a pair"),
        ([101, 209, 304], HIGH_CARD, "nothing: high card"),
    ]
    for cards, cat, name in cases:
        r = evaluate(cards)
        assert r[0] == cat, f"{name}: got {r}"


def test_ranking():
    straight = evaluate([304, 205, 106])
    flush = evaluate([402, 408, 412])
    assert straight > flush, "with three cards the straight beats the flush"
    assert evaluate([112, 213, 301]) > evaluate([111, 212, 313]), \
        "Q-K-A beats J-Q-K"
    assert evaluate([101, 202, 303]) < evaluate([102, 203, 304]), \
        "A-2-3 is the lowest straight"
    assert evaluate([113, 313, 205]) > evaluate([112, 312, 401]), \
        "pair of kings beats pair of queens"
    assert evaluate([113, 313, 206]) > evaluate([213, 413, 205]), \
        "with the same pair, the kicker decides"
    assert evaluate([101, 209, 304]) > evaluate([113, 212, 210]), \
        "ace high beats king high"


def test_qualifies():
    assert dealer_qualifies(evaluate([112, 206, 304])), "qualifies with queen high"
    assert not dealer_qualifies(evaluate([111, 209, 304])), "not with jack high"
    assert dealer_qualifies(evaluate([102, 202, 304])), "does with a pair of twos"
    assert describe(evaluate([112, 206, 304])) == "Queen high", "described as 'Queen high'"
    assert describe(evaluate([113, 313, 205])) == "Pair of Kings", "and 'Pair of Kings'"


def test_payouts():
    pair = [113, 313, 205]            # pair of kings
    queen = [112, 206, 304]           # queen high (qualifies)
    jack = [111, 209, 304]            # jack high (does not qualify)

    s = settle(10, 0, pair, jack, True)
    assert s["lines"]["ante"]["returned"] == 20 and s["lines"]["play"]["returned"] == 10, \
        f"dealer does not qualify: Ante pays and Play is returned: {s['lines']}"

    s = settle(10, 0, pair, queen, True)
    assert s["net"] == 20, f"the player wins: Ante and Play pay 1:1: {s}"

    s = settle(10, 0, queen, pair, True)
    assert s["net"] == -20, f"the dealer wins: Ante and Play are lost: {s}"

    s = settle(10, 0, [112, 206, 304], [212, 306, 404], True)
    assert s["net"] == 0 and s["winner"] == "tie", f"same hand: tie: {s}"

    s = settle(10, 5, pair, queen, False)
    assert s["net"] == -15, f"folding loses the Ante and the Pair Plus: {s}"

    s = settle(10, 5, pair, queen, True)
    assert s["lines"]["pair_plus"]["returned"] == 10, "Pair Plus with a pair pays 1:1"

    s = settle(10, 5, [107, 207, 307], [113, 313, 101], True)
    assert s["lines"]["pair_plus"]["returned"] == 155, \
        "Pair Plus with three of a kind pays 30:1"
    assert s["lines"]["bonus"]["returned"] == 40, \
        "three of a kind gets the Ante bonus 4:1"

    s = settle(10, 5, [409, 410, 411], [113, 313, 101], True)
    assert s["lines"]["pair_plus"]["returned"] == 205 and s["lines"]["bonus"]["returned"] == 50, \
        f"straight flush: Pair Plus 40:1 and bonus 5:1: {s['lines']}"

    s = settle(10, 5, [304, 205, 106], [107, 207, 307], True)
    assert s["lines"]["bonus"]["returned"] == 10 and s["lines"]["ante"]["returned"] == 0, \
        f"the straight's bonus is paid even if the dealer wins: {s['lines']}"

    s = settle(10, 5, [101, 209, 304], [113, 313, 101], True)
    assert s["lines"]["pair_plus"]["returned"] == 0, "Pair Plus without a pair loses"
