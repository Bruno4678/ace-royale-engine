"""Hi-Lo bet sizing: flat betting vs full Kelly vs half Kelly.

Input: the rounds recorded by `blackjack_sim` (true count before the deal,
net result of a one-unit bet). From them:

  1. Player edge as a function of the true count, fitted with a weighted
     line over the counts that have plenty of data. Variance per round is
     measured directly (about 1.33, splits and doubles included).
  2. Kelly says to bet the fraction  edge / variance  of the bankroll when
     the edge is positive. Below that, the counter still has to play (or
     leave the table), so it bets the table minimum.
  3. Bankroll paths: rounds are resampled at random from the recorded ones
     and every strategy faces the SAME sequence of rounds, so differences
     come from bet sizing alone. Bets are whole multiples of the table
     minimum, capped at the table maximum.

Reported per strategy: median and quantiles of the final bankroll, growth
rate, drawdowns, and risk of ruin (the bankroll falls below one minimum bet).
"""

import numpy as np

from .blackjack_sim import load_rounds
from .common import figure, pct, save, save_json

START = 1000          # bankroll, in table-minimum units
MIN_BET = 1
MAX_BET = 100         # a 1:100 table spread
ROUNDS = 50_000       # about 500 hours at 100 rounds an hour
PATHS = 2000


def fit_edge(tcs, nets, low=-4, high=6):
    """Weighted least-squares line edge = a + b * tc over [low, high]."""
    xs, ys, ws = [], [], []
    for tc in range(low, high + 1):
        sel = nets[tcs == tc]
        if len(sel):
            xs.append(tc)
            ys.append(sel.mean())
            ws.append(len(sel))
    b, a = np.polyfit(xs, ys, 1, w=np.sqrt(ws))
    return float(a), float(b)


def bet_sizes(bankroll, tc, a, b, variance, kelly_fraction):
    """Bet for each path. kelly_fraction 0 means flat betting."""
    if kelly_fraction == 0:
        return np.full_like(bankroll, MIN_BET)
    edge = a + b * tc
    stake = np.where(edge > 0, kelly_fraction * edge / variance * bankroll, MIN_BET)
    stake = np.floor(stake / MIN_BET) * MIN_BET
    return np.clip(stake, MIN_BET, MAX_BET)


def round_table(tcs, nets):
    """
    How often each (true count, net result) pair came up, so the bankroll
    paths can be resampled elsewhere (the showcase page does it in the
    browser) without the 10 million recorded rounds.
    """
    pairs, counts = np.unique(np.stack([tcs.astype(float), nets.astype(float)]),
                              axis=1, return_counts=True)
    return {"tc": pairs[0].astype(int).tolist(), "net": pairs[1].tolist(),
            "count": counts.tolist(), "rounds": int(len(nets))}


def run_paths(tcs, nets, a, b, variance, seed=7):
    rng = np.random.default_rng(seed)
    strategies = {"flat": 0.0, "half Kelly": 0.5, "full Kelly": 1.0}
    pick = rng.integers(0, len(nets), size=(ROUNDS, PATHS))
    checkpoints = np.linspace(0, ROUNDS, 101, dtype=int)

    results = {}
    for name, fraction in strategies.items():
        bankroll = np.full(PATHS, float(START))
        peak = bankroll.copy()
        max_dd = np.zeros(PATHS)
        ruined = np.zeros(PATHS, dtype=bool)
        wagered = np.zeros(PATHS)
        history = [np.quantile(bankroll, (0.05, 0.5, 0.95))]
        for r in range(ROUNDS):
            idx = pick[r]
            bet = bet_sizes(bankroll, tcs[idx], a, b, variance, fraction)
            bet = np.where(ruined, 0.0, np.minimum(bet, bankroll))
            bankroll += bet * nets[idx]
            wagered += bet
            ruined |= bankroll < MIN_BET
            peak = np.maximum(peak, bankroll)
            max_dd = np.maximum(max_dd, 1 - bankroll / peak)
            if r + 1 in checkpoints:
                history.append(np.quantile(bankroll, (0.05, 0.5, 0.95)))
        final = bankroll
        log_growth = np.log(np.maximum(final, 1e-9) / START) / ROUNDS
        results[name] = {
            "final_median": float(np.median(final)),
            "final_p05": float(np.quantile(final, 0.05)),
            "final_p95": float(np.quantile(final, 0.95)),
            "mean_final": float(final.mean()),
            "growth_per_100_rounds": float(np.median(log_growth) * 100),
            "risk_of_ruin": float(ruined.mean()),
            "prob_halved": float((max_dd >= 0.5).mean()),
            "median_max_drawdown": float(np.median(max_dd)),
            "p95_max_drawdown": float(np.quantile(max_dd, 0.95)),
            "avg_bet": float(np.median(wagered / ROUNDS)),
            "history": [list(map(float, h)) for h in history],
        }
    return results


def main():
    tcs, nets = load_rounds()
    a, b = fit_edge(tcs, nets)
    variance = float(np.var(nets))
    breakeven = -a / b
    print(f"Edge(TC) = {pct(a, 3)} + {pct(b, 3)} x TC  (break-even at TC {breakeven:+.2f}),"
          f" variance {variance:.3f}")
    results = run_paths(tcs, nets, a, b, variance)
    print(f"Bankroll {START} units, bets {MIN_BET}-{MAX_BET}, {ROUNDS:,} rounds, {PATHS:,} paths:")
    for name, r in results.items():
        print(f"  {name:>10}: median {r['final_median']:>8.0f}  [5%: {r['final_p05']:.0f},"
              f" 95%: {r['final_p95']:.0f}]  ruin {pct(r['risk_of_ruin'], 1)}"
              f"  halved {pct(r['prob_halved'], 1)}  median max DD {pct(r['median_max_drawdown'], 0)}"
              f"  avg bet {r['avg_bet']:.1f}")

    fig, ax = figure("kelly_bankroll")
    colours = {"flat": "#888888", "half Kelly": "#1f6f4a", "full Kelly": "#b8860b"}
    x = np.linspace(0, ROUNDS, 101)
    for name, r in results.items():
        h = np.maximum(np.array(r["history"]), 1.0)    # ruined paths sit at 1
        ax.plot(x, h[:, 1], color=colours[name], label=f"{name} (median)")
        ax.fill_between(x, h[:, 0], h[:, 2], color=colours[name], alpha=0.12)
    ax.axhline(START, color="#999", lw=0.8)
    ax.set_yscale("log")
    ax.set_ylim(bottom=1)
    ax.set_xlabel("Rounds")
    ax.set_ylabel("Bankroll (table-minimum units, log)")
    ax.set_title("Hi-Lo with Kelly bet sizing: median and 5-95% band")
    ax.legend()
    save(fig)

    from .blackjack_sim import edge_by_true_count
    by_tc = edge_by_true_count(tcs, nets)
    fig, ax = figure("blackjack_edge_by_true_count")
    ks = sorted(by_tc)
    ax.errorbar(ks, [100 * by_tc[k]["edge"] for k in ks],
                yerr=[100 * by_tc[k]["ci95"] for k in ks], fmt="o", color="#1f6f4a",
                capsize=3, label="simulated (95% CI)")
    xs = np.array([-6, 8])
    ax.plot(xs, 100 * (a + b * xs), color="#b8860b", lw=1, label="weighted fit")
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel("Hi-Lo true count before the deal")
    ax.set_ylabel("Player edge (%)")
    ax.set_title("Blackjack, 6 decks: player edge vs true count")
    ax.legend()
    save(fig)

    save_json("kelly_rounds", round_table(tcs, nets))
    for r in results.values():
        r.pop("history")
    return save_json("kelly", {
        "edge_intercept": a, "edge_slope": b, "breakeven_true_count": breakeven,
        "variance": variance, "start_bankroll": START, "min_bet": MIN_BET,
        "max_bet": MAX_BET, "rounds": ROUNDS, "paths": PATHS, "strategies": results,
    })


if __name__ == "__main__":
    main()
