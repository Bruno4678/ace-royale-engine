"""Checks that the simulations play by the engine's rules.

    .venv/bin/python -m sim.test_sim

Kept apart from tests/ because these need numpy; the engine tests do not.
"""

import random

from aceroyale.blackjack.rules import dealer_must_hit, hand_value
from aceroyale.three_card.rules import evaluate

from .baccarat_edge import outcome_probabilities
from .blackjack_sim import Shoe, simulate
from .blackjack_strategy import add, decision, player_edge
from .three_card_edge import analyse


def as_cards(points):
    """Blackjack points (1-10) as engine cards; tens become kings."""
    return [100 + (13 if p == 10 else p) for p in points]


def test_scoring_matches_engine():
    rng = random.Random(1)
    for _ in range(20_000):
        points = [rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10])
                  for _ in range(rng.randint(2, 7))]
        total, soft = 0, False
        for p in points:
            total, soft = add(total, soft, p)
        assert total == hand_value(as_cards(points)), points
        if total <= 21:
            assert (total < 17) == dealer_must_hit(as_cards(points)), points


def test_basic_strategy_cells():
    expected = {((10, 6), 10): "H", ((10, 2), 4): "S", ((10, 2), 2): "H",
                ((10, 3), 2): "S", ((5, 6), 6): "D", ((4, 6), 9): "D",
                ((4, 6), 10): "H", ((1, 7), 9): "H", ((1, 8), 6): "S",
                ((8, 8), 10): "P", ((10, 10), 6): "S", ((9, 9), 7): "S",
                ((9, 9), 9): "P", ((1, 1), 1): "P", ((5, 5), 9): "D"}
    for (cards, up), action in expected.items():
        assert decision(cards, up)[0] == action, (cards, up, decision(cards, up))
    assert -0.0065 < player_edge() < -0.0045


def test_baccarat_exact():
    p = outcome_probabilities()
    assert abs(sum(p.values()) - 1) < 1e-12
    assert abs(p["banker"] - 0.458597) < 1e-6
    assert abs(p["player"] - 0.446247) < 1e-6


def test_three_card_exact():
    r = analyse()
    assert abs(r["ante_play_ev_per_ante"] - (-0.03373)) < 2e-5
    assert r["weakest_hand_score"] == list(evaluate((312, 206, 104)))


def test_shoe_and_count():
    shoe = Shoe(random.Random(2))
    assert len(shoe.cards) == 312 and shoe.cards.count(10) == 96
    while shoe.pos < len(shoe.cards):
        shoe.draw()
    assert shoe.running == 0, "a balanced count ends at zero"
    tcs, nets = simulate(20_000, seed=3)
    assert -0.03 < nets.mean() < 0.02


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ok      {name}")
