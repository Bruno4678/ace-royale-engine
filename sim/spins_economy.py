"""Spins economy: what the multiplier table does to the chip supply and to players.

Three questions:

  1. The table. Expected multiplier, return to players, and how many chips
     the format creates or destroys per buy-in. Exact, from the weights.
  2. Luck. For a player of average skill (wins a third of the Spins), how
     often is the bankroll up after N Spins, and how much of the long-run
     result hangs on the rare x100? Monte Carlo with numpy.
  3. Skill. Bots of three levels play real Spins with the engine; their
     finishing frequencies give each level's return on investment.

It also proposes an alternative table that sinks about 5% of the buy-ins,
so the format slowly removes chips instead of printing them.
"""

import random

import numpy as np

from aceroyale.poker.bots import create_strategy
from aceroyale.poker.spins import (MULTIPLIERS, PLAYERS, expected_multiplier,
                                   play_spin, return_to_players, split_prize)

from .common import figure, mean_ci, pct, save, save_json

BUY_IN = 100

# Same multipliers, weights tuned for ~95% return to players (a 5% chip sink)
SINK_TABLE = (
    (2,   770, (100,)),
    (3,   160, (100,)),
    (5,    45, (100,)),
    (10,   21, (100,)),
    (100,   4, (80, 10, 10)),
)


def table_stats(table):
    weights = np.array([w for _, w, _ in table], dtype=float)
    mults = np.array([m for m, _, _ in table], dtype=float)
    p = weights / weights.sum()
    e = float((p * mults).sum())
    sd = float(np.sqrt((p * (mults - e) ** 2).sum()))
    return {
        "expected_multiplier": e,
        "multiplier_sd": sd,
        "return_to_players": return_to_players(table),
        "chips_created_per_buy_in": e / PLAYERS - 1,
        "share_of_prizes_from_top": float(p[-1] * mults[-1] / e),
    }


def luck_paths(table, spins=500, paths=20_000, win_rate=1 / 3, seed=3):
    """Bankroll after N Spins for a player who wins `win_rate` of them."""
    rng = np.random.default_rng(seed)
    weights = np.array([w for _, w, _ in table], dtype=float)
    p = weights / weights.sum()
    mults = np.array([m for m, _, _ in table])
    draw = rng.choice(len(table), size=(paths, spins), p=p)
    place = rng.random((paths, spins))
    payout = np.zeros((paths, spins))
    for k, (m, _, split) in enumerate(table):
        parts = split_prize(BUY_IN * m, split) + [0, 0]
        hit = draw == k
        # 1st with prob win_rate, 2nd and 3rd share the rest equally
        payout += hit * np.where(place < win_rate, parts[0],
                                 np.where(place < win_rate + (1 - win_rate) / 2, parts[1], parts[2]))
    net = (payout - BUY_IN).sum(axis=1)
    return {
        "spins": spins,
        "prob_in_profit": float((net > 0).mean()),
        "median_net": float(np.median(net)),
        "mean_net": float(net.mean()),
        "p05_net": float(np.quantile(net, 0.05)),
        "p95_net": float(np.quantile(net, 0.95)),
    }


def skill_study(spins=240, seed=11):
    """Expert, casual and beginner bots play real Spins with the engine."""
    rng = random.Random(seed)
    levels = ("beginner", "casual", "expert")
    places = {lv: [0, 0, 0] for lv in levels}
    nets = {lv: [] for lv in levels}
    hands = []
    for k in range(spins):
        seats = list(levels)
        rng.shuffle(seats)                       # random seating every Spin
        bots = [create_strategy(lv, seed=rng.randrange(10**9)) for lv in seats]
        result = play_spin(bots, buy_in=BUY_IN, rng=rng, multiplier=2)
        hands.append(result["hands"])
        for place, name in enumerate(result["standings"]):
            lv = seats[int(name[1:])]
            places[lv][place] += 1
        winner = seats[int(result["standings"][0][1:])]
        for lv in levels:
            nets[lv].append((1.0 if lv == winner else 0.0))
    out = {}
    e = expected_multiplier()
    for lv in levels:
        wins = np.array(nets[lv])
        rate, ci = mean_ci(wins)
        # Winner-takes-all in all but the top multiplier: ROI ~ win rate x E[mult] - 1
        out[lv] = {"win_rate": rate, "win_rate_ci95": ci, "places": places[lv],
                   "roi_estimate": rate * e - 1}
    return out, float(np.mean(hands))


def main(skill_spins=240):
    base, sink = table_stats(MULTIPLIERS), table_stats(SINK_TABLE)
    print("Spins table (current example odds):")
    print(f"  E[multiplier] {base['expected_multiplier']:.3f}, sd {base['multiplier_sd']:.2f},"
          f" return to players {pct(base['return_to_players'])},"
          f" chips created per buy-in {pct(base['chips_created_per_buy_in'])}")
    print(f"  {pct(base['share_of_prizes_from_top'], 1)} of all prize money comes from the x100")
    print(f"Alternative sink table: return to players {pct(sink['return_to_players'])},"
          f" chips per buy-in {pct(sink['chips_created_per_buy_in'])}")

    luck = {n: luck_paths(MULTIPLIERS, spins=n) for n in (50, 200, 1000)}
    for n, r in luck.items():
        print(f"  average player after {n:>4} Spins: in profit {pct(r['prob_in_profit'], 1)},"
              f" median {r['median_net']:+.0f}, mean {r['mean_net']:+.0f} chips")

    skill, avg_hands = skill_study(skill_spins)
    print(f"Skill ({skill_spins} bot Spins, {avg_hands:.1f} hands each):")
    for lv, r in skill.items():
        print(f"  {lv:>8}: wins {pct(r['win_rate'], 1)} +/- {pct(r['win_rate_ci95'], 1)},"
              f" places {r['places']}, ROI ~ {pct(r['roi_estimate'], 1)}")

    fig, ax = figure("spins_skill")
    names = list(skill)
    rates = [100 * skill[n]["win_rate"] for n in names]
    errs = [100 * skill[n]["win_rate_ci95"] for n in names]
    ax.bar(names, rates, yerr=errs, capsize=4, color=["#999999", "#1f6f4a", "#b8860b"])
    ax.axhline(100 / 3, color="#555", lw=0.8, ls="--", label="fair share (33.3%)")
    ax.set_ylabel("Spins won (%)")
    ax.set_title(f"Poker Spins: win rate by bot level ({skill_spins} Spins, 95% CI)")
    ax.legend()
    save(fig)

    return save_json("spins", {
        "buy_in": BUY_IN, "current_table": base, "sink_table": sink,
        "sink_weights": [[m, w] for m, w, _ in SINK_TABLE],
        "luck": {str(k): v for k, v in luck.items()},
        "skill": skill, "skill_spins": skill_spins, "avg_hands_per_spin": avg_hands,
    })


if __name__ == "__main__":
    main()
