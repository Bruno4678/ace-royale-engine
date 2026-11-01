"""Poker Spins: a three-player sit & go with a random prize multiplier.

Three players buy in, each starts with the same small stack and the blinds
rise every few hands until one player has every chip. Before the first hand
a multiplier is drawn: the prize is the buy-in times that multiplier. Most of
the time it is small; very rarely it is huge, and then second and third place
get a share too.

This module only adds the tournament around the hands. Each hand is a normal
engine `Hand` (or `OmahaHand`): the tournament hands it out, the caller drives
it with actions exactly as at a cash table, and the tournament records the
result, eliminates busted players and moves the blinds.

Blinds rise by number of hands, not by time. A clock belongs to whatever runs
the game live; counting hands keeps the engine deterministic and testable,
and at a live table a level of a few minutes is roughly that many hands.
"""

import random

from .bots import view_for
from .engine import Hand, Seat
from .hands import full_deck

PLAYERS = 3
STARTING_CHIPS = 500
HANDS_PER_LEVEL = 6

# (small blind, big blind) per level; the last level repeats until the end.
# With 1,500 chips in play, by the last levels every hand is close to all-in,
# so a Spin always finishes.
BLIND_SCHEDULE = (
    (10, 20), (15, 30), (20, 40), (30, 60), (40, 80), (50, 100),
    (75, 150), (100, 200), (150, 300), (200, 400), (300, 600),
)

# (multiplier, weight out of 1000, prize split in % by finishing place).
# Winner takes all, except at the top multiplier where the prize is big
# enough that second and third get something too.
#
# These odds are an example to be tuned: their expected multiplier is 3.05,
# so the three buy-ins (3x) pay back 3.05x on average and the format slightly
# INFLATES the chip supply. The Spins economy simulation measures that.
MULTIPLIERS = (
    (2,   750, (100,)),
    (3,   150, (100,)),
    (5,    70, (100,)),
    (10,   25, (100,)),
    (100,   5, (80, 10, 10)),
)


# ---------------------------------------------------------------- multiplier

def draw_multiplier(rng, table=MULTIPLIERS)->int:
    """Draws a multiplier with the table's weights."""
    total = sum(w for _, w, _ in table)
    roll = rng.randrange(total)
    for multiplier, weight, _ in table:
        if roll < weight:
            return multiplier
        roll -= weight
    raise AssertionError("unreachable: weights exhausted")


def expected_multiplier(table=MULTIPLIERS)->float:
    """Average multiplier over many Spins."""
    total = sum(w for _, w, _ in table)
    return sum(m * w for m, w, _ in table) / total


def return_to_players(table=MULTIPLIERS, players=PLAYERS)->float:
    """
    Chips paid out per chip of buy-in collected, on average.

    Below 1 the format removes chips from the economy (a rake); above 1 it
    creates them.
    """
    return expected_multiplier(table) / players


def prize_split(multiplier, table=MULTIPLIERS)->tuple:
    """Prize split in % by place for a given multiplier."""
    for m, _, split in table:
        if m == multiplier:
            return split
    raise ValueError(f"multiplier not in the table: {multiplier}")


def split_prize(prize:int, split)->list:
    """
    Turns a % split into whole chips. Rounding leftovers go to the winner,
    so the parts always add up to the prize exactly.
    """
    parts = [prize * pct // 100 for pct in split]
    parts[0] += prize - sum(parts)
    return parts


# ---------------------------------------------------------------- tournament

class SpinTournament:
    """
    One Spin from the multiplier draw to the last hand.

    Typical use::

        spin = SpinTournament(["Ann", "Bob", "Cat"], buy_in=100, rng=rng)
        while not spin.finished:
            hand = spin.next_hand()
            while not hand.finished:
                hand.act(hand.turn, action, amount)
            spin.record(hand)
        spin.payouts()      # {"Bob": 200}
    """

    def __init__(self, names, buy_in:int=100, multiplier:int=None, rng=None,
                 table=MULTIPLIERS, starting_chips:int=STARTING_CHIPS,
                 schedule=BLIND_SCHEDULE, hands_per_level:int=HANDS_PER_LEVEL,
                 hand_class=Hand):
        names = list(names)
        if len(names) != PLAYERS or len(set(names)) != PLAYERS:
            raise ValueError(f"a Spin needs {PLAYERS} players with different names")
        self.rng = rng or random.Random()
        self.table = table
        self.multiplier = (multiplier if multiplier is not None
                           else draw_multiplier(self.rng, table))
        self.split = prize_split(self.multiplier, table)
        self.buy_in = int(buy_in)
        self.prize_pool = self.buy_in * self.multiplier

        self.order = names                       # seating order, fixed
        self.chips = {n: int(starting_chips) for n in names}
        self.schedule = tuple(schedule)
        self.hands_per_level = int(hands_per_level)
        self.hand_class = hand_class

        self.button = self.rng.choice(names)     # who has the button
        self.hands_played = 0
        self.eliminated = []                     # first one out first
        self.current = None
        self._start = None

    # ------------------------------------------------------------ state

    @property
    def level(self)->int:
        """Blind level, from 0. Rises every `hands_per_level` hands."""
        return min(self.hands_played // self.hands_per_level, len(self.schedule) - 1)

    @property
    def blinds(self)->tuple:
        return self.schedule[self.level]

    @property
    def hands_to_next_level(self)->int:
        """Hands left at this level (0 at the last level, which never ends)."""
        if self.level == len(self.schedule) - 1:
            return 0
        return self.hands_per_level - self.hands_played % self.hands_per_level

    def alive(self)->list:
        return [n for n in self.order if self.chips[n] > 0]

    @property
    def finished(self)->bool:
        return len(self.alive()) <= 1

    # ------------------------------------------------------------ hands

    def next_hand(self, deck:list=None):
        """
        Deals the next hand with the players still alive and the current
        blinds. The caller drives it and passes it back to `record()`.
        """
        if self.finished:
            raise ValueError("the Spin is already over")
        if self.current is not None:
            raise ValueError("record the hand in play first")
        alive = self.alive()
        seats = [Seat(n, self.chips[n], player_id=n) for n in alive]
        sb, bb = self.blinds
        if deck is None:
            deck = full_deck()
            self.rng.shuffle(deck)
        self._start = {n: self.chips[n] for n in alive}
        self.current = self.hand_class(seats, button=alive.index(self.button),
                                       small_blind=sb, big_blind=bb, deck=deck)
        return self.current

    def record(self, hand):
        """Takes the stacks from a finished hand, eliminates and moves on."""
        if hand is not self.current:
            raise ValueError("that is not the hand in play")
        if not hand.finished:
            raise ValueError("the hand is not finished")
        for s in hand.seats:
            self.chips[s.id] = s.chips

        # Busted in the same hand: whoever started it with more chips
        # finishes higher, so they are eliminated "later".
        busted = [n for n in self._start if self.chips[n] == 0]
        busted.sort(key=lambda n: self._start[n])
        self.eliminated.extend(busted)

        self.hands_played += 1
        self.current = None
        self._start = None
        if not self.finished:
            self.button = self._next_alive(self.button)

    def _next_alive(self, name):
        i = self.order.index(name)
        for step in range(1, len(self.order) + 1):
            candidate = self.order[(i + step) % len(self.order)]
            if self.chips[candidate] > 0:
                return candidate
        return name

    # ------------------------------------------------------------ results

    def standings(self)->list:
        """Names from first to last place. Only once the Spin is over."""
        if not self.finished:
            raise ValueError("the Spin is not over")
        return self.alive() + list(reversed(self.eliminated))

    def payouts(self)->dict:
        """Chips won by each player who is paid."""
        parts = split_prize(self.prize_pool, self.split)
        return {name: amount
                for name, amount in zip(self.standings(), parts) if amount}


# ---------------------------------------------------------------- bots

def play_spin(strategies, buy_in:int=100, rng=None, multiplier:int=None,
              hand_class=Hand, max_hands:int=1000)->dict:
    """
    Plays a whole Spin between three bot strategies. Used by the simulations.

    :param strategies: three objects with `.decide(view)`, e.g. from
        `create_strategy`. Player i is named "P{i}".
    :return: {"multiplier", "prize_pool", "standings", "payouts", "hands"}
    """
    rng = rng or random.Random()
    names = [f"P{i}" for i in range(len(strategies))]
    by_name = dict(zip(names, strategies))
    spin = SpinTournament(names, buy_in=buy_in, multiplier=multiplier,
                          rng=rng, hand_class=hand_class)
    while not spin.finished:
        if spin.hands_played >= max_hands:
            raise RuntimeError(f"Spin still running after {max_hands} hands")
        hand = spin.next_hand()
        while not hand.finished:
            i = hand.turn
            action, amount = by_name[hand.seats[i].id].decide(view_for(hand, i))
            hand.act(i, action, amount)
        spin.record(hand)
    return {
        "multiplier": spin.multiplier,
        "prize_pool": spin.prize_pool,
        "standings": spin.standings(),
        "payouts": spin.payouts(),
        "hands": spin.hands_played,
    }
