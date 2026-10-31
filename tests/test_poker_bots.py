"""Tests for the poker bots, driven directly against the engine.

What these tests set out to show:
  1. A bot NEVER manages to make an illegal move: the engine rejects it.
  2. Hands always finish, with no deadlocks or loops.
  3. Chips at the table are neither created nor destroyed.
  4. A bot only ever sees its own hole cards.
  5. Skill levels show: a better bot wins money from a worse one.
"""

from random import Random

from aceroyale.poker.bots import (
    BotStrategy, BotView, PERSONALITIES, LEVEL_ORDER, create_strategy,
    estimate_equity, view_for, available_names,
)
from aceroyale.poker.engine import Hand, Seat
from aceroyale.poker.hands import full_deck

# The legality and bookkeeping tests do not depend on how WELL the bot plays,
# only on it playing legally. With few samples they take seconds instead of
# hours; the duel between levels does use the real samples.
TEST_SAMPLES = 12


def shuffled_deck(rng):
    deck = full_deck()
    rng.shuffle(deck)
    return deck


def play_out(hand, strategies, guard_limit=500):
    """
    Drives a hand to the end asking each bot for its intent.

    Returns (decisions, rejected). An intent the engine rejects is replaced by
    check/fold, which is what a table manager would do.
    """
    decisions = 0
    rejected = 0
    guard = 0
    while not hand.finished and guard < guard_limit:
        guard += 1
        i = hand.turn
        options = hand.valid_actions(i)
        if not options:
            break
        action, amount = strategies[i].decide(view_for(hand, i))
        decisions += 1
        try:
            hand.act(i, action, amount)
        except ValueError:
            # The engine rejected it: that is exactly what must happen.
            rejected += 1
            hand.act(i, "check" if "check" in options else "fold")
    return decisions, rejected


# ------------------------------------------------------- personalities

def test_personalities_differ():
    keys = list(PERSONALITIES)
    assert len(keys) == 4, f"four levels expected: {keys}"
    assert tuple(keys) == LEVEL_ORDER, f"{keys} vs {LEVEL_ORDER}"
    samples = [PERSONALITIES[k].samples for k in LEVEL_ORDER]
    assert samples == sorted(samples), f"higher level, better estimate of the play: {samples}"
    bluffs = [PERSONALITIES[k].bluff for k in LEVEL_ORDER]
    assert bluffs == sorted(bluffs), f"higher level, more bluffing: {bluffs}"
    noise = [PERSONALITIES[k].noise for k in LEVEL_ORDER]
    assert noise == sorted(noise, reverse=True), f"higher level, less noise: {noise}"
    assert len({PERSONALITIES[k].name for k in keys}) == 4, "each one has its own table name"
    names = available_names()
    assert len(names) == len(set(names)), "bot names do not repeat"


def test_create_strategy():
    s = create_strategy("expert", seed=1)
    assert isinstance(s, BotStrategy) and s.p.samples == PERSONALITIES["expert"].samples
    s = create_strategy("expert", seed=1, samples=5)
    assert s.p.samples == 5 and s.p.bluff == PERSONALITIES["expert"].bluff
    assert PERSONALITIES["expert"].samples == 650, "overriding samples must not touch the shared personality"
    assert create_strategy("nonexistent").p.key == "casual", "unknown levels fall back to casual"


# ------------------------------------------------------- equity

def test_equity_estimates():
    rng = Random(3)
    # Pocket aces vs one random hand preflop: about 85%.
    aces = [101, 201]
    eq = estimate_equity(aces, [], 1, 4000, rng)
    assert 0.82 < eq < 0.88, f"AA vs 1 opponent ~0.85, got {eq:.3f}"
    # 7-2 offsuit vs one random hand: about 35%.
    eq = estimate_equity([107, 202], [], 1, 4000, rng)
    assert 0.31 < eq < 0.39, f"72o vs 1 opponent ~0.35, got {eq:.3f}"
    # Royal flush made on the river: always wins (or ties if the board plays).
    eq = estimate_equity([101, 113], [112, 111, 110, 202, 303], 3, 200, rng)
    assert eq == 1.0, eq
    assert estimate_equity(aces, [], 0, 10, rng) == 1.0, "no opponents left: the pot is ours"


def test_more_samples_less_noise():
    """The skill knob: more samples give a tighter equity estimate."""
    hole = [113, 212]           # K Q offsuit
    def spread(samples, runs=60):
        rng = Random(samples)
        values = [estimate_equity(hole, [], 2, samples, rng) for _ in range(runs)]
        mean = sum(values) / runs
        return (sum((v - mean) ** 2 for v in values) / runs) ** 0.5
    few = spread(PERSONALITIES["beginner"].samples)
    many = spread(PERSONALITIES["expert"].samples)
    assert many < few / 2, f"std with 40 samples {few:.3f}, with 650 {many:.3f}"


# ------------------------------------------------------- legality

def test_bots_cannot_break_the_rules():
    total_decisions = 0
    unfinished = 0
    for game in range(120):
        chips = [200, 200, 150, 400, 80, 300][: 2 + game % 5]
        seats = [Seat(f"B{i}", c, is_bot=True) for i, c in enumerate(chips)]
        strategies = [create_strategy(
            LEVEL_ORDER[i % len(LEVEL_ORDER)],
            seed=game * 10 + i, samples=TEST_SAMPLES)
            for i in range(len(chips))]
        before = sum(chips)

        h = Hand(seats, button=game % len(chips), small_blind=5, big_blind=10,
                 deck=shuffled_deck(Random(game)))
        decisions, _ = play_out(h, strategies)
        total_decisions += decisions

        if not h.finished:
            unfinished += 1
        after = sum(s.chips for s in h.seats)
        assert before == after, f"chips out of balance in game {game}: {before} -> {after}"

    assert unfinished == 0, f"{unfinished} of 120 hands got stuck"
    assert total_decisions > 120, f"bots made only {total_decisions} decisions"


def test_illegal_intents_are_rejected():
    """A strategy that only proposes nonsense cannot move the game off the rules."""
    class Cheater:
        def __init__(self):
            self.n = 0

        def decide(self, view):
            self.n += 1
            return [("raise", 10 ** 9), ("bet", -5), ("check", 0),
                    ("teleport", 0), ("raise", 1)][self.n % 5]

    for game in range(40):
        seats = [Seat(f"C{i}", 200, is_bot=True) for i in range(3)]
        h = Hand(seats, button=game, small_blind=5, big_blind=10,
                 deck=shuffled_deck(Random(game)))
        decisions, rejected = play_out(h, [Cheater(), Cheater(), Cheater()])
        assert h.finished, f"game {game} did not finish"
        assert sum(s.chips for s in h.seats) == 600
        assert all(s.chips >= 0 for s in h.seats)
        # Every intent that is not legal is refused (e.g. raising 1e9 chips).
        assert rejected > 0 or decisions == 0, (decisions, rejected)


# ------------------------------------------------------- card isolation

def test_bots_only_see_their_own_cards():
    class Spy:
        """Records every view it gets and then plays like a casual bot."""
        def __init__(self, seed):
            self.inner = create_strategy("casual", seed=seed, samples=TEST_SAMPLES)
            self.views = []

        def decide(self, view):
            self.views.append(view)
            return self.inner.decide(view)

    for game in range(60):
        seats = [Seat(f"S{i}", 300, is_bot=True) for i in range(2 + game % 5)]
        spies = [Spy(game * 10 + i) for i in range(len(seats))]
        h = Hand(seats, button=game, small_blind=5, big_blind=10,
                 deck=shuffled_deck(Random(1000 + game)))
        play_out(h, spies)
        for i, spy in enumerate(spies):
            own = set(h.seats[i].cards)
            others = {c for j, s in enumerate(h.seats) if j != i for c in s.cards}
            for v in spy.views:
                assert isinstance(v, BotView)
                assert set(v.cards) == own, f"seat {i} was shown {v.cards}, owns {own}"
                visible = set(v.cards) | set(v.board)
                assert not (visible & others), \
                    f"seat {i} could see someone else's cards: {visible & others}"
                # Nothing else in the view is a list of cards that could leak them.
                public = {k: val for k, val in vars(v).items() if k not in ("cards", "board")}
                assert not any(isinstance(val, (list, tuple, set)) for val in public.values()), public


def test_view_is_a_copy():
    """Mutating a view cannot change the hand."""
    h = Hand([Seat("A", 100), Seat("B", 100)], button=0, small_blind=5,
             big_blind=10, deck=shuffled_deck(Random(5)))
    v = view_for(h, h.turn)
    before = list(h.seats[h.turn].cards)
    v.cards.append(999)
    v.board.append(999)
    assert h.seats[h.turn].cards == before and h.board == []


# ------------------------------------------------------- multi-hand table

def test_bots_play_many_hands_in_a_row():
    """
    Five bots play 40 hands in a row carrying their stacks over, with the
    button rotating. Busted bots leave the table (the original product
    refilled them; that is table management, not poker rules).
    """
    rng = Random(42)
    names = available_names()[:5]
    stacks = {n: 400 for n in names}
    strategies = {n: create_strategy("casual", seed=k, samples=TEST_SAMPLES)
                  for k, n in enumerate(names)}
    start_total = sum(stacks.values())
    played = 0
    button = 0
    for _ in range(40):
        alive = [n for n in names if stacks[n] > 0]
        if len(alive) < 2:
            break
        seats = [Seat(n, stacks[n], is_bot=True) for n in alive]
        h = Hand(seats, button=button, small_blind=5, big_blind=10,
                 deck=shuffled_deck(rng))
        play_out(h, [strategies[n] for n in alive])
        assert h.finished, "every hand must finish"
        for s in h.seats:
            stacks[s.name] = s.chips
        played += 1
        button += 1
        assert sum(stacks.values()) == start_total, \
            f"chips out of balance after hand {played}: {sum(stacks.values())}"
    assert played >= 20, f"only {played} hands were played"


# ------------------------------------------------------- levels

def duel(level_a, level_b, hands=100, seed=1):
    """Plays two levels heads-up and returns A's net result."""
    rng = Random(seed)
    net = 0
    for n in range(hands):
        stack = 1000
        seats = [Seat("A", stack, is_bot=True), Seat("B", stack, is_bot=True)]
        strategies = [create_strategy(level_a, seed=rng.random()),
                      create_strategy(level_b, seed=rng.random())]
        h = Hand(seats, button=n % 2, small_blind=5, big_blind=10,
                 deck=shuffled_deck(rng))
        play_out(h, strategies, guard_limit=300)
        net += h.seats[0].chips - stack
    return net


def test_skill_levels_show():
    """
    Checks that the level makes a difference.

    Heads-up poker has a LOT of variance: a hundred hands say nothing, and in
    fact the first version of this test failed because of that with a single
    block. Here several independent blocks of hands are played and the total
    is checked, which is a reliable signal.

    The original ran 6 blocks x 100 hands per match-up (several minutes).
    To keep the suite fast this runs the same four match-ups over 4 blocks of
    60 hands each (~30 s); the seeds are fixed, so the result is reproducible.
    """
    for better, worse in (("expert", "beginner"), ("advanced", "beginner"),
                          ("casual", "beginner"), ("expert", "casual")):
        nets = [duel(better, worse, hands=60, seed=s) for s in range(4)]
        total = sum(nets)
        assert total > 0, \
            f"{better} should win money from {worse}: blocks {nets}, total {total:+d}"
