"""Tests for Poker Spins: multiplier draw, prize split, blinds and the tournament."""

import random

from aceroyale.poker.bots import create_strategy
from aceroyale.poker.engine import OmahaHand
from aceroyale.poker.spins import (BLIND_SCHEDULE, HANDS_PER_LEVEL, MULTIPLIERS,
                                   STARTING_CHIPS, SpinTournament,
                                   draw_multiplier, expected_multiplier,
                                   play_spin, prize_split, return_to_players,
                                   split_prize)

NAMES = ["Ann", "Bob", "Cat"]


def expect_error(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return
    assert False, f"expected ValueError from {fn.__name__}{args}"


# ---------------------------------------------------------------- multiplier

def test_multiplier_table():
    assert sum(w for _, w, _ in MULTIPLIERS) == 1000
    for _, _, split in MULTIPLIERS:
        assert sum(split) == 100
    assert abs(expected_multiplier() - 3.05) < 1e-9
    assert abs(return_to_players() - 3.05 / 3) < 1e-9


def test_multiplier_frequencies():
    rng = random.Random(4)
    n = 200_000
    counts = {m: 0 for m, _, _ in MULTIPLIERS}
    for _ in range(n):
        counts[draw_multiplier(rng)] += 1
    for m, w, _ in MULTIPLIERS:
        p = w / 1000
        sd = (p * (1 - p) / n) ** 0.5
        assert abs(counts[m] / n - p) < 5 * sd, (m, counts[m] / n, p)


def test_prize_split():
    assert prize_split(2) == (100,)
    assert split_prize(200, prize_split(2)) == [200]
    assert split_prize(10_000, prize_split(100)) == [8000, 1000, 1000]
    # rounding leftovers go to the winner and nothing is lost
    parts = split_prize(1001, (80, 10, 10))
    assert parts == [801, 100, 100] and sum(parts) == 1001
    expect_error(prize_split, 7)


# ---------------------------------------------------------------- blinds

def test_blinds_rise_by_hands():
    spin = SpinTournament(NAMES, multiplier=2, rng=random.Random(1))
    assert spin.blinds == BLIND_SCHEDULE[0]
    assert spin.hands_to_next_level == HANDS_PER_LEVEL
    spin.hands_played = HANDS_PER_LEVEL
    assert spin.blinds == BLIND_SCHEDULE[1]
    spin.hands_played = 10_000
    assert spin.blinds == BLIND_SCHEDULE[-1], "the last level never ends"
    assert spin.hands_to_next_level == 0


# ---------------------------------------------------------------- tournament

def play_out(spin, choose):
    """Plays a Spin to the end with a simple scripted policy."""
    total = STARTING_CHIPS * 3
    while not spin.finished:
        hand = spin.next_hand()
        assert len(hand.seats) == len(spin.alive())
        assert (hand.sb, hand.bb) == spin.blinds
        while not hand.finished:
            action, amount = choose(hand)
            hand.act(hand.turn, action, amount)
        spin.record(hand)
        assert sum(spin.chips.values()) == total, spin.chips
        assert spin.hands_played < 2000


def all_in(hand):
    options = hand.valid_actions()
    for key in ("raise", "bet"):
        if key in options:
            return key, options[key]["max"]
    return ("call", 0) if "call" in options else ("check", 0)


def test_spin_plays_to_the_end():
    rng = random.Random(9)
    for k in range(30):
        spin = SpinTournament(NAMES, buy_in=100, rng=rng)
        play_out(spin, all_in)
        standings = spin.standings()
        assert sorted(standings) == sorted(NAMES)
        assert spin.chips[standings[0]] == STARTING_CHIPS * 3
        payouts = spin.payouts()
        assert sum(payouts.values()) == spin.prize_pool
        assert payouts[standings[0]] >= max(payouts.values())


def test_double_elimination_order():
    # All-in three ways on the first hand with a rigged deck: Cat (shortest
    # start) and Bob both bust; Bob started with more, so Bob finishes 2nd.
    spin = SpinTournament(NAMES, multiplier=100, rng=random.Random(2))
    spin.chips = {"Ann": 700, "Bob": 500, "Cat": 300}
    spin.button = "Ann"
    # Seats Ann, Bob, Cat; hole cards dealt in seat order: Ann gets AA.
    hole = [101, 201, 102, 207, 203, 308]
    board = [110, 312, 404, 211, 109, 313, 410, 405]   # burns: 110 211 410
    rest = [c for c in range(100, 500) if 1 <= c % 100 <= 13
            and c not in hole + board]
    hand = spin.next_hand(deck=rest + list(reversed(hole + board)))
    while not hand.finished:
        action, amount = all_in(hand)
        hand.act(hand.turn, action, amount)
    spin.record(hand)
    assert spin.finished
    assert spin.standings() == ["Ann", "Bob", "Cat"]
    assert spin.payouts() == {"Ann": 8000, "Bob": 1000, "Cat": 1000}


def test_button_moves_and_skips_busted():
    spin = SpinTournament(NAMES, multiplier=2, rng=random.Random(3))
    spin.button = "Ann"
    hand = spin.next_hand()
    while not hand.finished:
        hand.act(hand.turn, "fold" if "check" not in hand.valid_actions() else "check")
    spin.record(hand)
    assert spin.button == "Bob"
    spin.chips["Cat"], spin.chips["Ann"] = 0, spin.chips["Ann"] + spin.chips["Cat"]
    spin.eliminated.append("Cat")
    spin.button = "Bob"
    hand = spin.next_hand()
    assert [s.id for s in hand.seats] == ["Ann", "Bob"]
    while not hand.finished:
        hand.act(hand.turn, "fold" if "check" not in hand.valid_actions() else "check")
    spin.record(hand)
    assert spin.button == "Ann", "Cat is out, so the button skips her"


def test_misuse_is_rejected():
    spin = SpinTournament(NAMES, multiplier=2, rng=random.Random(5))
    hand = spin.next_hand()
    expect_error(spin.next_hand)                 # one hand at a time
    expect_error(spin.record, hand)              # not finished yet
    expect_error(SpinTournament, ["A", "B"])     # needs three players
    expect_error(SpinTournament, ["A", "A", "B"])


# ---------------------------------------------------------------- bots

def test_bots_play_spins():
    rng = random.Random(17)
    for k in range(12):
        bots = [create_strategy(level, seed=10 * k + j, samples=30)
                for j, level in enumerate(("beginner", "casual", "expert"))]
        result = play_spin(bots, buy_in=50, rng=rng)
        assert sum(result["payouts"].values()) == result["prize_pool"]
        assert result["prize_pool"] == 50 * result["multiplier"]
        assert sorted(result["standings"]) == ["P0", "P1", "P2"]


def test_omaha_spin():
    bots = [create_strategy("casual", seed=j, samples=15) for j in range(3)]
    result = play_spin(bots, rng=random.Random(8), hand_class=OmahaHand)
    assert len(result["standings"]) == 3
