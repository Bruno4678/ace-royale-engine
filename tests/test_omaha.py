"""Tests for Pot-Limit Omaha: evaluator, pot-limit betting, showdown and bots."""

import random
from itertools import combinations

from aceroyale.poker.bots import create_strategy, estimate_equity, view_for
from aceroyale.poker.engine import OmahaHand, Seat
from aceroyale.poker.hands import (FLUSH, FULL_HOUSE, PAIR, THREE_OF_A_KIND,
                                   TWO_PAIR, best_hand, best_omaha_hand,
                                   full_deck)


def seats(*chips):
    return [Seat(f"P{i}", chips[i], is_bot=False) for i in range(len(chips))]


def rigged(sequence):
    """Deck that deals `sequence` in order (the engine pops from the end)."""
    rest = [c for c in full_deck() if c not in sequence]
    return rest + list(reversed(sequence))


def expect_error(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return
    assert False, f"expected ValueError from {fn.__name__}{args}"


# ---------------------------------------------------------------- evaluator

def test_exactly_two_hole_cards():
    board = [303, 307, 309, 313, 102]               # four hearts on the board
    one_heart = [301, 204, 405, 208]                # only the ace of hearts
    two_hearts = [301, 302, 405, 208]
    assert best_omaha_hand(one_heart, board)[0][0] != FLUSH, \
        "one heart in hand cannot make a flush"
    assert best_omaha_hand(two_hearts, board)[0][0] == FLUSH
    # In Hold'em-style scoring the single heart WOULD make a flush
    assert best_hand(one_heart + board)[0][0] == FLUSH


def test_four_aces_on_board_count_as_three():
    board = [101, 201, 301, 401, 113]
    assert best_omaha_hand([102, 203, 304, 405], board)[0][0] == THREE_OF_A_KIND
    assert best_omaha_hand([112, 212, 203, 304], board)[0][0] == FULL_HOUSE


def test_four_of_a_kind_in_hand_is_only_a_pair():
    board = [102, 203, 304, 113, 412]
    assert best_omaha_hand([101, 201, 301, 401], board)[0][0] == PAIR


def test_chosen_five_always_has_two_hole_cards():
    rng = random.Random(11)
    deck = full_deck()
    for _ in range(2000):
        cards = rng.sample(deck, 9)
        hole, board = cards[:4], cards[4:]
        score, five = best_omaha_hand(hole, board)
        assert len([c for c in five if c in hole]) == 2, (hole, board, five)
        # using any 5 of the 9 cards can only be as good or better
        assert score <= best_hand(cards)[0]


def test_omaha_matches_brute_force():
    rng = random.Random(12)
    deck = full_deck()
    for _ in range(300):
        cards = rng.sample(deck, 9)
        hole, board = cards[:4], cards[4:]
        legal = [best_hand(list(two) + list(three))[0]
                 for two in combinations(hole, 2)
                 for three in combinations(board, 3)]
        assert best_omaha_hand(hole, board)[0] == max(legal)


# ---------------------------------------------------------------- pot limit

def test_pot_limit_preflop():
    # Blinds 5/10, button P0 -> P1 small blind, P2 big blind, P0 acts first.
    h = OmahaHand(seats(1000, 1000, 1000), button=0, small_blind=5, big_blind=10)
    assert all(len(s.cards) == 4 for s in h.seats)
    assert h.valid_actions()["raise"] == {"min": 20, "max": 35}, \
        "first in can raise to 10 + (15 + 10) = 35"
    expect_error(h.act, 0, "raise", 36)
    h.act(0, "raise", 35)
    # small blind has 5 in: call 30 -> pot 80, raise 80 -> to 115
    assert h.valid_actions()["raise"]["max"] == 115
    h.act(1, "call")
    # big blind has 10 in: call 25 -> pot 105, raise 105 -> to 140
    assert h.valid_actions()["raise"]["max"] == 140
    h.act(2, "call")
    assert h.street == "flop" and h.pot == 105
    # with no bet yet, the most anyone can bet is the pot
    assert h.valid_actions()["bet"] == {"min": 10, "max": 105}


def test_pot_limit_never_exceeds_stack():
    h = OmahaHand(seats(30, 1000, 1000), button=2, small_blind=5, big_blind=10)
    # button P2 -> P0 small blind with 30 chips, P1 big blind, P2 first to act
    h.act(2, "call")
    assert h.turn == 0
    assert h.valid_actions()["raise"]["max"] == 30, "capped by the stack"


# ---------------------------------------------------------------- showdown

def test_showdown_uses_omaha_rules():
    # P0 holds one heart with four hearts on board: a flush in Hold'em, only
    # ace high in Omaha. P1 makes kings and twos with K-2 from hand.
    p0 = [301, 204, 405, 208]
    p1 = [113, 202, 411, 212]
    board_draws = [110, 303, 307, 309, 210, 313, 310, 102]   # burns: 110 210 310
    h = OmahaHand(seats(1000, 1000), button=0, small_blind=5, big_blind=10,
                  deck=rigged(p0 + p1 + board_draws))
    assert h.seats[0].cards == p0 and h.seats[1].cards == p1
    h.act(0, "call")
    h.act(1, "check")
    while not h.finished:
        h.act(h.turn, "check")
    assert h.board == [303, 307, 309, 313, 102]
    assert h.result["winners"] == [1]
    assert h.seats[1].chips == 1010 and h.seats[0].chips == 990
    assert h.result["hands"][1]["text"].lower().startswith("two pair"), h.result
    assert best_omaha_hand(p1, h.board)[0][0] == TWO_PAIR


def test_no_duplicate_cards():
    for seed in range(60):
        random.seed(seed)
        h = OmahaHand(seats(*[1000] * 6), button=seed, small_blind=5, big_blind=10)
        while not h.finished:
            h.act(h.turn, "call" if "call" in h.valid_actions() else "check")
        dealt = [c for s in h.seats for c in s.cards] + h.board
        assert len(dealt) == 6 * 4 + 5 and len(set(dealt)) == len(dealt)


# ---------------------------------------------------------------- bots

def test_omaha_equity():
    rng = random.Random(3)
    aakk_ds = estimate_equity([101, 301, 113, 313], [], 1, 2000, rng)
    assert 0.62 < aakk_ds < 0.76, aakk_ds
    # a dry low hand against two random hands is well below a fair share
    weak = estimate_equity([102, 207, 309, 413], [], 2, 2000, rng)
    assert weak < 0.30, weak


def test_bots_play_omaha():
    # Four bots, 40 hands in a row with stacks carried over. Every intent the
    # bots produce must be legal under pot limit, and no chip appears or vanishes.
    rng = random.Random(21)
    chips = [1000] * 4
    bots = [create_strategy(level, seed=k, samples=25)
            for k, level in enumerate(("beginner", "casual", "advanced", "expert"))]
    button = 0
    for _ in range(40):
        players = [k for k in range(4) if chips[k] > 0]
        if len(players) < 2:
            break
        table = [Seat(f"B{k}", chips[k], is_bot=True) for k in players]
        deck = full_deck()
        rng.shuffle(deck)
        h = OmahaHand(table, button=button, small_blind=5, big_blind=10, deck=deck)
        while not h.finished:
            i = h.turn
            action, amount = bots[players[i]].decide(view_for(h, i))
            h.act(i, action, amount)        # raises if a bot breaks pot limit
        for k, s in zip(players, table):
            chips[k] = s.chips
        assert sum(chips) == 4000, chips
        button += 1
