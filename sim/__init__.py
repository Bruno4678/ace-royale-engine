"""Quant simulations on top of the Ace Royale engine.

Run them from the repo root with the simulation environment:

    python -m venv .venv && .venv/bin/pip install -r sim/requirements.txt
    .venv/bin/python -m sim.run_all

Every script reuses the engine's own rule functions, so the numbers measure
the games exactly as the engine plays them.
"""
