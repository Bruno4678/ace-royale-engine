"""Exact house edge of Three Card Poker and its optimal play/fold strategy.

Every player hand (22,100) is compared with every dealer hand that can be
dealt from the remaining 49 cards (18,424 each). To keep that fast, player
hands that only differ by a relabelling of the suits are grouped (their
results are identical), and each group is compared against all dealer hands
at once with numpy bitmasks. Hands are ranked with the engine's `evaluate`
and `dealer_qualifies`, and paid with the engine's payout tables.

For each player hand the expected value of Play is compared with folding
(-1 ante), which gives the optimal strategy; the textbook answer is "play
queen-six-four or better".
"""

from itertools import combinations, permutations

import numpy as np

from aceroyale.three_card.rules import (ANTE_BONUS_PAYOUT, NAMES,
                                        PAIR_PLUS_PAYOUT, dealer_qualifies,
                                        describe, evaluate, full_deck)

from .common import pct, save_json

DECK = full_deck()
INDEX = {c: i for i, c in enumerate(DECK)}


def all_hands():
    hands = list(combinations(DECK, 3))
    scores = [evaluate(h) for h in hands]
    order = {s: r for r, s in enumerate(sorted(set(scores)))}   # dense ranks
    ranks = np.array([order[s] for s in scores], dtype=np.int32)
    masks = np.array([sum(1 << INDEX[c] for c in h) for h in hands], dtype=np.int64)
    qualifies = np.array([dealer_qualifies(s) for s in scores])
    return hands, scores, ranks, masks, qualifies


def canonical(hand):
    """Same key for hands that differ only by a relabelling of suits."""
    best = None
    for perm in permutations((1, 2, 3, 4)):
        key = tuple(sorted(perm[c // 100 - 1] * 100 + c % 100 for c in hand))
        if best is None or key < best:
            best = key
    return best


def analyse():
    hands, scores, ranks, masks, qualifies = all_hands()
    groups = {}
    for i, h in enumerate(hands):
        groups.setdefault(canonical(h), []).append(i)

    total_ev_ante = 0.0           # with optimal play/fold
    total_ev_q64 = 0.0            # with the "Q-6-4 or better" rule
    weakest_played = None
    worst_ev = None
    n = len(hands)

    for members in groups.values():
        i = members[0]
        free = (masks & masks[i]) == 0
        d_rank, d_q = ranks[free], qualifies[free]
        dealer_hands = free.sum()
        r = ranks[i]

        not_q = np.count_nonzero(~d_q)
        win = np.count_nonzero(d_q & (d_rank < r))
        lose = np.count_nonzero(d_q & (d_rank > r))
        bonus = ANTE_BONUS_PAYOUT.get(scores[i][0], 0)

        # Per unit of Ante (Play = Ante): dealer does not qualify -> Ante
        # paid, Play pushed; player wins -> both paid; dealer wins -> both lost.
        ev_play = (not_q * 1 + win * 2 - lose * 2) / dealer_hands + bonus
        ev_fold = -1.0
        best = max(ev_play, ev_fold)
        weight = len(members)
        total_ev_ante += best * weight

        plays_q64 = scores[i] >= evaluate((312, 206, 104))
        total_ev_q64 += (ev_play if plays_q64 else ev_fold) * weight

        if ev_play > ev_fold and (weakest_played is None or scores[i] < weakest_played):
            weakest_played = scores[i]
            worst_ev = ev_play

    # Pair Plus does not depend on the dealer: only on the player's category.
    category_counts = {}
    for s in scores:
        category_counts[s[0]] = category_counts.get(s[0], 0) + 1
    ev_pp = sum(cnt * PAIR_PLUS_PAYOUT.get(cat, -1) for cat, cnt in category_counts.items()) / n

    return {
        "ante_play_ev_per_ante": total_ev_ante / n,
        "ante_play_ev_q64": total_ev_q64 / n,
        "weakest_hand_to_play": describe(weakest_played),
        "weakest_hand_score": list(weakest_played),
        "weakest_hand_ev": worst_ev,
        "pair_plus_ev": ev_pp,
        "category_probabilities": {NAMES[c]: cnt / n for c, cnt in sorted(category_counts.items())},
        "suit_classes": len(groups),
    }


def main():
    r = analyse()
    print("Three Card Poker (exact):")
    print(f"  Ante/Play, optimal strategy: {pct(r['ante_play_ev_per_ante'], 3)} per Ante")
    print(f"  Ante/Play, Q-6-4 rule:       {pct(r['ante_play_ev_q64'], 3)} per Ante")
    print(f"  weakest hand worth playing:  {r['weakest_hand_to_play']} {r['weakest_hand_score']}")
    print(f"  Pair Plus:                   {pct(r['pair_plus_ev'], 3)}")
    return save_json("three_card", r)


if __name__ == "__main__":
    main()
