"""Runs every simulation and refreshes sim/results/*.json and docs/img/*.png.

    .venv/bin/python -m sim.run_all          # about 3 minutes
"""

from . import (baccarat_edge, blackjack_sim, blackjack_strategy, kelly,
               spins_economy, three_card_edge)


def main():
    for step in (baccarat_edge.main, three_card_edge.main, blackjack_strategy.main):
        step()
        print()
    blackjack_sim.main(rounds=10_000_000)
    print()
    kelly.main()
    print()
    spins_economy.main()


if __name__ == "__main__":
    main()
