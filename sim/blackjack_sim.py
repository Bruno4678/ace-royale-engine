"""Blackjack in a real 6-deck shoe: house edge of basic strategy and Hi-Lo counts.

The engine's blackjack deals from a single deck that is rebuilt when it runs
low, which makes card counting pointless. This simulator uses its own
multi-deck shoe with a cut card instead, and plays the basic strategy derived
in `blackjack_strategy` (same rules: S17, DAS, 3:2, split to four hands, split
aces one card, dealer peeks for blackjack, no surrender, no insurance).

Every round records the Hi-Lo true count BEFORE the deal and the net result
for a flat one-unit bet (splits and doubles included). That is all the Kelly
analysis needs: player edge as a function of the true count.

Hi-Lo: 2-6 count +1, 7-9 count 0, tens and aces count -1. The true count is
the running count divided by the decks left, rounded down.

Hands are scored on (total, soft) states for speed; `tests/test_sim.py`
checks that scoring against the engine's `hand_value` and `resolve`.
"""

import math
import random

import numpy as np

from .blackjack_strategy import add, decision, ev_hit, ev_stand
from .common import mean_ci, pct, save_json

DECKS = 6
PENETRATION = 0.75          # reshuffle once 75% of the shoe has been dealt
MAX_HANDS = 4               # split up to four hands
HI_LO = {1: -1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0, 10: -1}


class Shoe:
    """Card points (1 = ace, 10 = ten/face) with a cut card and a running count."""

    def __init__(self, rng, decks=DECKS, penetration=PENETRATION):
        self.rng = rng
        self.decks = decks
        self.cut = int(52 * decks * penetration)
        self._shuffle()

    def _shuffle(self):
        self.cards = [r for r in range(1, 11) for _ in range(16 if r == 10 else 4)] * self.decks
        self.rng.shuffle(self.cards)
        self.pos = 0
        self.running = 0

    def draw(self):
        c = self.cards[self.pos]
        self.pos += 1
        self.running += HI_LO[c]
        return c

    def true_count(self):
        decks_left = (len(self.cards) - self.pos) / 52
        return math.floor(self.running / decks_left)

    def new_round(self):
        if self.pos >= self.cut:
            self._shuffle()


# ---------------------------------------------------------------- strategy

_HIT = {}


def hits(total, soft, upcard):
    """Hit or stand for a hand of three or more cards (no double possible)."""
    key = (total, soft, upcard)
    if key not in _HIT:
        _HIT[key] = ev_hit(total, soft, upcard) > ev_stand(total, upcard)
    return _HIT[key]


_FIRST = {}


def first_action(c1, c2, upcard, can_split):
    """H / S / D / P for a two-card hand, from the dynamic-programming table."""
    key = (min(c1, c2), max(c1, c2), upcard, can_split)
    if key not in _FIRST:
        action, options = decision((c1, c2), upcard)
        if action == "P" and not can_split:
            options.pop("P")
            action = max(options, key=options.get)
        _FIRST[key] = action
    return _FIRST[key]


# ---------------------------------------------------------------- one round

def dealer_play(shoe, up, hole):
    total, soft = add(*add(0, False, up), hole)
    while total < 17:
        total, soft = add(total, soft, shoe.draw())
    return total


def play_hand(shoe, cards, upcard, n_hands, from_split_aces=False):
    """
    Plays one player hand to the end. Returns a list of finished hands as
    (total, bet, is_natural_candidate) plus how many hands now exist.
    """
    c1, c2 = cards
    if from_split_aces:
        total, _ = add(*add(0, False, c1), c2)
        return [(total, 1)], n_hands

    action = first_action(c1, c2, upcard, can_split=n_hands < MAX_HANDS and c1 == c2)
    if action == "P":
        n_hands += 1
        out = []
        for _ in range(2):
            new = (c1, shoe.draw())
            if c1 == 1:
                hands, n_hands = play_hand(shoe, new, upcard, n_hands, from_split_aces=True)
            else:
                hands, n_hands = play_hand(shoe, new, upcard, n_hands)
            out += hands
        return out, n_hands

    total, soft = add(*add(0, False, c1), c2)
    if action == "D":
        total, _ = add(total, soft, shoe.draw())
        return [(total, 2)], n_hands
    if action == "S":
        return [(total, 1)], n_hands
    while total < 21:
        total, soft = add(total, soft, shoe.draw())
        if total > 21 or not hits(total, soft, upcard):
            break
    return [(total, 1)], n_hands


def play_round(shoe):
    """Net result of one round for a one-unit bet."""
    p1, up, p2, hole = shoe.draw(), shoe.draw(), shoe.draw(), shoe.draw()
    player_bj = {p1, p2} == {1, 10}
    dealer_bj = {up, hole} == {1, 10}
    if dealer_bj:
        return 0.0 if player_bj else -1.0
    if player_bj:
        return 1.5

    hands, _ = play_hand(shoe, (p1, p2), up, 1)
    if all(t > 21 for t, _ in hands):
        return -float(sum(b for _, b in hands))   # dealer does not need to draw
    dealer = dealer_play(shoe, up, hole)
    net = 0.0
    for total, bet in hands:
        if total > 21:
            net -= bet
        elif dealer > 21 or total > dealer:
            net += bet
        elif total < dealer:
            net -= bet
    return net


def simulate(rounds, seed=2026):
    """Plays `rounds` rounds. Returns numpy arrays (true count, net units)."""
    rng = random.Random(seed)
    shoe = Shoe(rng)
    tcs = np.empty(rounds, dtype=np.int16)
    nets = np.empty(rounds, dtype=np.float32)
    for i in range(rounds):
        shoe.new_round()
        tcs[i] = shoe.true_count()
        nets[i] = play_round(shoe)
    return tcs, nets


def edge_by_true_count(tcs, nets, low=-6, high=8):
    """Mean result and 95% CI per true count (clipped to [low, high])."""
    clipped = np.clip(tcs, low, high)
    out = {}
    for tc in range(low, high + 1):
        sel = nets[clipped == tc]
        if len(sel) > 1000:
            m, h = mean_ci(sel)
            out[tc] = {"edge": m, "ci95": h, "rounds": int(len(sel)),
                       "share": float(len(sel) / len(nets))}
    return out


def main(rounds=3_000_000, seed=2026):
    import time
    t = time.perf_counter()
    tcs, nets = simulate(rounds, seed)
    elapsed = time.perf_counter() - t
    edge, ci = mean_ci(nets)
    by_tc = edge_by_true_count(tcs, nets)
    print(f"Blackjack, {DECKS} decks, {int(PENETRATION * 100)}% penetration, "
          f"{rounds:,} rounds in {elapsed:.0f}s")
    print(f"  basic strategy return: {pct(edge, 3)} +/- {pct(ci, 3)} (95% CI)")
    print(f"  variance per round: {float(np.var(nets)):.3f}")
    for tc, v in by_tc.items():
        print(f"  TC {tc:+d}: {pct(v['edge'], 2):>8} +/- {pct(v['ci95'], 2)}"
              f"   ({pct(v['share'], 1)} of rounds)")
    np.savez_compressed(_rounds_path(), tcs=tcs, nets=nets)
    save_json("blackjack_shoe", {
        "decks": DECKS, "penetration": PENETRATION, "rounds": rounds, "seed": seed,
        "return": edge, "ci95": ci, "variance": float(np.var(nets)),
        "by_true_count": {str(k): v for k, v in by_tc.items()},
    })
    return tcs, nets


def _rounds_path():
    from .common import RESULTS
    RESULTS.mkdir(parents=True, exist_ok=True)
    return RESULTS / "blackjack_rounds.npz"


def load_rounds():
    data = np.load(_rounds_path())
    return data["tcs"], data["nets"]


if __name__ == "__main__":
    main()
