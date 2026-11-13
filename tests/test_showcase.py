"""Tests for the showcase page's Python side: showcase/bridge.py and the build.

The page itself is static HTML and JavaScript; what can go wrong in Python is
the bridge giving the page wrong numbers or a game that breaks the rules, and
the build shipping an engine that does not import.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "showcase"))

import bridge  # noqa: E402
import build   # noqa: E402

RESULTS = ROOT / "sim" / "results"


def test_equity_matches_known_values():
    # Pocket aces against one random hand win about 85% of the time.
    aces = json.loads(bridge.equity([101, 301], [], 1, 20000, seed=1))
    assert abs(aces["equity"] - 0.852) < 0.015
    assert 0 < aces["ci95"] < 0.01
    # A made royal flush on the board for us: it cannot lose.
    nuts = json.loads(bridge.equity([101, 113], [112, 111, 110, 202, 303], 3, 500, seed=2))
    assert nuts["equity"] == 1.0


def test_equity_rejects_bad_input():
    bad = [
        ([101], [], 1),                    # one hole card
        ([101, 101], [], 1),               # the same card twice
        ([101, 201], [301], 1),            # a one-card board
        ([101, 201], [], 0),               # nobody to play against
        ([101, 999], [], 1),               # not a card
    ]
    for cards, board, opponents in bad:
        try:
            bridge.equity(cards, board, opponents, 100)
        except ValueError:
            continue
        raise AssertionError(f"accepted {cards} {board} {opponents}")


def test_level_spread_gets_noisier_with_fewer_samples():
    spread = json.loads(bridge.level_spread([113, 213], [], 1, 30, seed=3))
    assert list(spread) == ["beginner", "casual", "advanced", "expert"]

    def sd(xs):
        m = sum(xs) / len(xs)
        return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5

    assert sd(spread["beginner"]["estimates"]) > sd(spread["expert"]["estimates"])


def test_match_conserves_chips_and_enforces_turns():
    state = json.loads(bridge.start_match("beginner", seed=4))
    for hand in range(40):
        while not state["finished"]:
            actions = state["actions"]
            if "raise" in actions and hand % 4 == 0:
                state = json.loads(bridge.match_act("raise", actions["raise"]["max"]))
            elif "check" in actions:
                state = json.loads(bridge.match_act("check"))
            else:
                state = json.loads(bridge.match_act("call"))
        assert sum(state["chips"].values()) == 2000
        try:
            bridge.match_act("check")
        except ValueError:
            pass
        else:
            raise AssertionError("acted on a finished hand")
        state = json.loads(bridge.match_next_hand())


def test_match_hides_bot_cards_until_showdown():
    state = json.loads(bridge.start_match("casual", seed=5))
    assert state["bot_cards"] is None
    while not state["finished"]:
        assert state["bot_cards"] is None
        actions = state["actions"]
        state = json.loads(bridge.match_act("check" if "check" in actions else "call"))
    if state["result"]["showdown"]:
        assert len(state["bot_cards"]) == 2


def test_banker_returns_reproduce_the_rounding_finding():
    probs = json.loads((RESULTS / "baccarat.json").read_text())
    rows = json.loads(bridge.banker_returns(probs["probabilities"]["banker"],
                                            probs["probabilities"]["player"], 100))
    favour_down = [r["bet"] for r in rows if r["down"] > 0]
    favour_up = [r["bet"] for r in rows if r["up"] > 0]
    assert favour_down == probs["bet_sizes_favouring_player"]["round_down"]
    assert favour_up == []
    by_bet = {r["bet"]: r for r in rows}
    assert abs(by_bet[20]["up"] - probs["return_per_chip"]["banker"]) < 1e-12


def test_build_ships_an_importable_engine():
    with tempfile.TemporaryDirectory() as tmp:
        out = build.build(Path(tmp) / "site")
        for name in build.PAGE_FILES + ("engine.zip", "results.json"):
            assert (out / name).exists(), name
        data = json.loads((out / "results.json").read_text())
        assert set(data) == set(build.RESULTS)
        # Import the engine from the zip alone, as Pyodide does in the browser.
        code = ("import sys, json; sys.path[:0] = [sys.argv[1]]; import bridge, aceroyale;"
                "assert aceroyale.__file__.startswith(sys.argv[1]);"
                "print(json.loads(bridge.equity([101, 201], [], 1, 200, seed=1))['samples'])")
        run = subprocess.run([sys.executable, "-I", "-c", code, str(out / "engine.zip")],
                             capture_output=True, text=True, cwd=tmp)
        assert run.returncode == 0, run.stderr
        assert run.stdout.strip() == "200"
