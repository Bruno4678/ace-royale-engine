"""Exact house edge of baccarat, by enumerating every way a coup can be dealt.

The engine deals each coup from a fresh 8-deck shoe, so the outcome depends
only on the first four to six cards. Every sequence of card POINTS is walked
(0 for tens and faces, 1-9 for the rest) with its exact probability of being
drawn without replacement, and the engine's own `player_draws` /
`banker_draws` decide the third cards. No sampling, so no error bars.

A Monte Carlo run with the engine's `play_hand` checks the enumeration.

Finding: the engine rounds the 5% commission DOWN on whole chips, so on a
Banker bet of 5 to 19 chips the commission is 0 and the bet favours the
player. The edge is reported for several bet sizes.
"""

import random

from aceroyale.baccarat.rules import (BANKER_COMMISSION, TIE_PAYOUT, Shoe,
                                      banker_draws, commission, hand_value,
                                      play_hand, player_draws)

from .common import figure, pct, save, save_json

DECKS = 8
# One representative card per point value: 110 (a ten) for 0, 101..109 for 1..9
CARD = {0: 110, **{v: 100 + v for v in range(1, 10)}}


def shoe_counts(decks=DECKS):
    counts = {v: 4 * decks for v in range(1, 10)}
    counts[0] = 16 * decks                      # 10, J, Q, K
    return counts


def outcome_probabilities(decks=DECKS):
    """Exact P(player), P(banker), P(tie) for one coup."""
    counts = shoe_counts(decks)
    total = sum(counts.values())
    probs = {"player": 0.0, "banker": 0.0, "tie": 0.0}

    def draw(counts, left):
        """Yields (card, probability, counts after the draw)."""
        for v, n in counts.items():
            if n:
                after = dict(counts)
                after[v] = n - 1
                yield CARD[v], n / left, after

    def finish(player, banker, p, counts, left):
        pv, bv = hand_value(player), hand_value(banker)
        if pv > bv:
            probs["player"] += p
        elif bv > pv:
            probs["banker"] += p
        else:
            probs["tie"] += p

    def banker_turn(player, banker, p, counts, left, player_third):
        if banker_draws(banker, player_third):
            for c, q, after in draw(counts, left):
                finish(player, banker + [c], p * q, after, left - 1)
        else:
            finish(player, banker, p, counts, left)

    for p1, q1, c1 in draw(counts, total):
        for b1, q2, c2 in draw(c1, total - 1):
            for p2, q3, c3 in draw(c2, total - 2):
                for b2, q4, c4 in draw(c3, total - 3):
                    p = q1 * q2 * q3 * q4
                    player, banker = [p1, p2], [b1, b2]
                    left = total - 4
                    if hand_value(player) >= 8 or hand_value(banker) >= 8:
                        finish(player, banker, p, c4, left)       # natural
                    elif player_draws(player):
                        for c, q, after in draw(c4, left):
                            banker_turn(player + [c], banker, p * q, after,
                                        left - 1, player_third=c)
                    else:
                        banker_turn(player, banker, p, c4, left, player_third=None)
    return probs


def edges(probs, bet=100):
    """Expected return per chip bet on each box (negative = house edge)."""
    pp, pb, pt = probs["player"], probs["banker"], probs["tie"]
    banker_win = (bet - commission(bet)) / bet
    return {
        # Player and Banker are returned on a tie
        "player": pp - pb,
        "banker": pb * banker_win - pp,
        "tie": pt * TIE_PAYOUT - (1 - pt),
    }


def monte_carlo(n, seed=1):
    rng = random.Random(seed)
    import aceroyale.baccarat.rules as rules
    original = rules._rng
    rules._rng = rng                       # seeded shoe, restored afterwards
    try:
        wins = {"player": 0, "banker": 0, "tie": 0}
        for _ in range(n):
            wins[play_hand(Shoe(DECKS).draw)["winner"]] += 1
    finally:
        rules._rng = original
    return {k: v / n for k, v in wins.items()}


def main(mc_hands=200_000):
    probs = outcome_probabilities()
    edge = edges(probs)
    mc = monte_carlo(mc_hands)
    by_bet = {bet: edges(probs, bet)["banker"] for bet in (5, 10, 19, 20, 25, 50, 100, 1000)}

    print("Baccarat (8 decks, exact):")
    for k in ("banker", "player", "tie"):
        print(f"  P({k}) = {probs[k]:.6f}   Monte Carlo {mc[k]:.4f}   "
              f"return per chip {pct(edge[k], 3)}")
    print("  Banker return by bet size (commission rounded down):")
    for bet, e in by_bet.items():
        print(f"    bet {bet:>5}: {pct(e, 3)}")

    fig, ax = figure("baccarat_banker_by_bet")
    bets = list(range(5, 101))
    ax.plot(bets, [100 * edges(probs, b)["banker"] for b in bets], color="#1f6f4a")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel("Banker bet (chips)")
    ax.set_ylabel("Player return per chip (%)")
    ax.set_title("Baccarat Banker bet: commission rounded down on whole chips")
    save(fig)

    return save_json("baccarat", {
        "decks": DECKS, "probabilities": probs, "return_per_chip": edge,
        "banker_return_by_bet": by_bet, "monte_carlo": {"hands": mc_hands, **mc},
        "commission_pct": BANKER_COMMISSION, "tie_pays": TIE_PAYOUT,
    })


if __name__ == "__main__":
    main()
