"""Tests for the single-hand no-limit Hold'em engine (aceroyale.poker.engine)."""

import random

from aceroyale.poker.engine import Hand, Seat
from aceroyale.poker.hands import full_deck


def seats(*chips):
    return [Seat(f"P{i}", chips[i], is_bot=False) for i in range(len(chips))]


def expect_error(fn, *args):
    try:
        fn(*args)
    except ValueError:
        return
    assert False, f"expected ValueError from {fn.__name__}{args}"


# ---------------------------------------------------------------- pots

def test_side_pots():
    # Three players, one short. A=50, B=200, C=200.
    # A goes all-in with 50, B and C go to 200 -> main pot 150,
    # side pot 300 that A has no share in.
    h = Hand(seats(50, 200, 200), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    # force the contributions by hand to test only the split
    h.seats[0].total_contributed = 50
    h.seats[1].total_contributed = 200
    h.seats[2].total_contributed = 200
    h.seats[0].state = "all_in"
    pots = h._compute_pots()
    assert len(pots) == 2, f"two pots expected: {pots}"
    assert pots[0][0] == 150 and set(pots[0][1]) == {0, 1, 2}, \
        f"main pot 150 with all three: {pots[0]}"
    assert pots[1][0] == 300 and set(pots[1][1]) == {1, 2}, \
        f"side pot 300 without the short stack: {pots[1]}"

    # A player who folds contributes to the pot but cannot win it
    h = Hand(seats(100, 100, 100), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    h.seats[0].total_contributed = 30
    h.seats[0].state = "folded"
    h.seats[1].total_contributed = 100
    h.seats[2].total_contributed = 100
    pots = h._compute_pots()
    total = sum(p[0] for p in pots)
    assert total == 230, f"the folded player's chips stay in the pot: {total}"
    for _, eligible in pots:
        assert 0 not in eligible, "the folded player is not eligible for any pot"


# ---------------------------------------------------------------- payout

def test_chip_conservation():
    """200 hands with random legal actions: no hand creates or destroys chips."""
    random.seed(7)
    bad = []
    for n in range(200):
        chips = [random.choice([40, 100, 200, 500]) for _ in range(random.randint(2, 6))]
        before = sum(chips)
        h = Hand(seats(*chips), button=n % len(chips),
                 small_blind=5, big_blind=10)
        guard = 0
        while not h.finished and guard < 400:
            guard += 1
            options = h.valid_actions()
            if not options:
                break
            action = random.choice(list(options.keys()))
            amount = 0
            if action in ("bet", "raise"):
                lim = options[action]
                amount = random.randint(lim["min"], lim["max"])
            h.act(h.turn, action, amount)
        after = sum(s.chips for s in h.seats)
        if before != after or not h.finished:
            bad.append((n, before, after, h.finished, h.street))
    assert not bad, f"{len(bad)} bad hands out of 200, first: {bad[0]}"


def test_side_pot_payout_at_showdown():
    """Short stack all-in with the best hand only wins the main pot."""
    # The deck is popped from the end, so it is built back to front:
    # hole cards go P0, P0, P1, P1, P2, P2; then burn, flop, burn, turn, burn, river.
    order = [113, 213,          # P0: K K   (short stack, best hand)
             102, 307,          # P1: 2 7
             103, 308,          # P2: 3 8
             450,               # burn (placeholder, replaced below)
             109, 210, 404,     # flop 9 10 4
             451, 112,          # burn, turn Q
             452, 405]          # burn, river 5
    used = {c for c in order if c < 450}
    spare = [c for c in full_deck() if c not in used]
    burns = iter(spare)
    order = [next(burns) if c >= 450 else c for c in order]
    rest = [c for c in full_deck() if c not in order]
    deck = rest + list(reversed(order))

    h = Hand(seats(50, 300, 300), button=2, small_blind=5, big_blind=10, deck=deck)
    assert h.seats[0].cards == [113, 213], h.seats[0].cards
    # button=2 -> SB = P0, BB = P1, first to act preflop = P2
    assert (h.i_sb, h.i_bb, h.turn) == (0, 1, 2), (h.i_sb, h.i_bb, h.turn)
    h.act(2, "raise", 100)
    h.act(0, "call")                # all-in for 50 total
    assert h.seats[0].state == "all_in"
    h.act(1, "call")
    while not h.finished:
        h.act(h.turn, "check")

    assert h.result["showdown"], h.result
    total = sum(s.chips for s in h.seats)
    assert total == 650, f"chips conserved: {total}"
    main, side = h.result["pots"]
    assert main["amount"] == 150 and main["winners"] == [0], main
    assert side["amount"] == 100 and len(side["winners"]) >= 1 and 0 not in side["winners"], side
    assert h.seats[0].chips == 150, f"short stack wins only the main pot: {h.seats[0].chips}"


def test_fold_wins_without_showdown():
    h = Hand(seats(100, 100, 100), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    # button=0 -> SB = P1, BB = P2, first to act = P0
    h.act(0, "fold")
    h.act(1, "fold")
    assert h.finished
    assert h.result["showdown"] is False
    assert h.result["winners"] == [2]
    assert h.result["hands"] == {}, "nobody shows cards"
    assert [s.chips for s in h.seats] == [100, 95, 105]


def test_split_pot_odd_chip():
    """Equal hands split the pot; the odd chip goes to the first winner left of the button."""
    # The board plays (royal flush on board), so everyone still in ties.
    # 0 marks a burn card, filled in below with any unused card.
    order = [202, 303,          # P0
             204, 305,          # P1
             206, 307,          # P2
             0, 101, 113, 112,  # burn, flop
             0, 111,            # burn, turn
             0, 110]            # burn, river
    burns = iter(c for c in full_deck() if c not in order)
    order = [next(burns) if c == 0 else c for c in order]
    deck = [c for c in full_deck() if c not in order] + list(reversed(order))

    h = Hand(seats(100, 100, 100), button=0, small_blind=5, big_blind=10, deck=deck)
    # button=0 -> SB = P1, BB = P2, first to act = P0
    h.act(0, "call")
    h.act(1, "fold")                # leaves 5 dead chips: pot of 25 is odd
    h.act(2, "check")
    while not h.finished:
        h.act(h.turn, "check")

    assert h.result["winners"] == [0, 2], h.result
    assert all(p["hand"] == "Straight flush, A high" for p in h.result["pots"]), h.result
    # main pot 15 -> 7 + 7 + odd chip, side level 10 -> 5 + 5.
    # Left of button 0 the order is P1, P2, P0, so P2 gets the odd chip.
    assert [s.chips for s in h.seats] == [102, 95, 103], [s.chips for s in h.seats]


def test_heads_up_order():
    """Heads-up the button posts the small blind, acts first preflop and last after."""
    h = Hand(seats(100, 100), button=1, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    assert (h.i_sb, h.i_bb, h.turn) == (1, 0, 1), (h.i_sb, h.i_bb, h.turn)
    h.act(1, "call")
    h.act(0, "check")
    assert h.street == "flop"
    assert h.turn == 0, "after the flop the non-button player acts first"


# ---------------------------------------------------------------- legality

def test_engine_rejects_illegal_actions():
    h = Hand(seats(100, 100, 100), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    assert h.turn == 0
    expect_error(h.act, 1, "call")              # not your turn
    expect_error(h.act, 0, "check")             # facing the big blind, cannot check
    expect_error(h.act, 0, "bet", 20)           # there is a bet already: it is a raise
    expect_error(h.act, 0, "raise", 15)         # below the minimum raise (to 20)
    expect_error(h.act, 0, "raise", 101)        # more than the stack
    expect_error(h.act, 0, "teleport")          # not an action
    assert h.turn == 0 and h.pot == 15, "rejected actions change nothing"
    assert h.valid_actions(1) == {}, "only the player in turn has options"

    h.act(0, "raise", 30)
    # min raise is now 20 more: re-raise must be to at least 50
    assert h.valid_actions()["raise"]["min"] == 50, h.valid_actions()
    h.act(1, "fold")
    h.act(2, "fold")
    assert h.finished
    expect_error(h.act, 0, "check")             # hand already finished
    assert h.valid_actions(0) == {}


def test_min_raise_and_bet_limits():
    h = Hand(seats(500, 500), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    opts = h.valid_actions()
    assert opts["call"] == {"amount": 5}, opts
    assert opts["raise"] == {"min": 20, "max": 500}, opts
    h.act(0, "raise", 60)                        # raise by 50
    opts = h.valid_actions()
    assert opts["raise"]["min"] == 110, f"next raise must add at least 50: {opts}"
    h.act(1, "call")
    # new street: min bet is the big blind again
    assert h.street == "flop" and len(h.board) == 3
    opts = h.valid_actions()
    assert "check" in opts and opts["bet"] == {"min": 10, "max": 440}, opts


def test_no_duplicate_cards_dealt():
    rng = random.Random(11)
    for n in range(300):
        deck = full_deck()
        rng.shuffle(deck)
        h = Hand(seats(*[100] * (2 + n % 5)), button=n, small_blind=5,
                 big_blind=10, deck=deck)
        while not h.finished:
            opts = h.valid_actions()
            h.act(h.turn, "call" if "call" in opts else "check")
        dealt = list(h.board)
        for s in h.seats:
            dealt += s.cards
        assert len(h.board) == 5
        assert len(dealt) == len(set(dealt)), f"duplicated card in hand {n}: {dealt}"


# ---------------------------------------------------------------- short all-in

def test_short_all_in_must_be_called():
    # Blinds 5/10, button P0 -> P1 small blind, P2 big blind with 45 chips.
    # P0 raises to 30, P1 calls, P2 goes all-in to 45: only 15 more, less
    # than the minimum raise (20). The betting is NOT reopened, but P0 and P1
    # still owe 15: they must call or fold before the flop comes.
    h = Hand(seats(1000, 1000, 45), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    h.act(0, "raise", 30)
    h.act(1, "call")
    h.act(2, "raise", 45)
    assert h.street == "preflop", "the street closed with 15 chips still owed"
    assert h.turn == 0
    options = h.valid_actions()
    assert options.get("call") == {"amount": 15}, options
    assert "raise" not in options, "a short all-in must not reopen the raising"
    h.act(0, "call")
    assert h.turn == 1 and "raise" not in h.valid_actions()
    h.act(1, "call")
    assert h.street == "flop"
    assert [s.total_contributed for s in h.seats] == [45, 45, 45]


def test_short_all_in_does_not_close_raising_for_those_yet_to_act():
    # P0 raises to 30, P1 (small blind, 45 chips) goes all-in short to 45.
    # P2 has not acted since the raise, so P2 may still re-raise; P0 then
    # faces a full raise and may raise again too.
    h = Hand(seats(1000, 45, 1000), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    h.act(0, "raise", 30)
    h.act(1, "raise", 45)
    assert h.turn == 2
    assert "raise" in h.valid_actions(), "P2 had not acted yet: raising stays open"
    h.act(2, "raise", 100)
    assert h.turn == 0 and "raise" in h.valid_actions()


def test_short_all_in_caller_can_only_call_or_fold():
    # P0 raises to 30, P1 calls, P2 goes all-in short: P0 may not re-raise,
    # only fold or call. P0 folds, P1 calls; with P2 all-in nobody else can
    # bet, so the board is run out straight to the showdown.
    h = Hand(seats(1000, 1000, 45), button=0, small_blind=5, big_blind=10,
             deck=list(full_deck()))
    h.act(0, "raise", 30)
    h.act(1, "call")
    h.act(2, "raise", 45)
    expect_error(h.act, 0, "raise", 100)
    h.act(0, "fold")
    h.act(1, "call")
    assert h.finished and len(h.board) == 5
    assert [s.total_contributed for s in h.seats] == [30, 45, 45]
    assert sum(s.chips for s in h.seats) == 1000 + 1000 + 45
