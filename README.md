# Ace Royale Engine

The game engine behind **Ace Royale**, a free web card room for playing poker
with friends and practising casino games. This repository holds only the
computational core: rules, payouts, hand evaluation and the poker bots. The
web app that runs on top of it is a separate, private project.

Pure Python 3.9+, standard library only, no I/O: everything here just
computes, so it can be tested exhaustively and simulated in bulk.

## What's inside

| Package | What it does |
|---|---|
| `aceroyale.blackjack` | Hand values (soft/hard), naturals, dealer rule (stands on 17), splits, doubles, insurance, settlement |
| `aceroyale.baccarat` | Punto banco with the full third-card tableau, 8-deck shoe, 5% banker commission, 8:1 tie |
| `aceroyale.three_card` | Three Card Poker ranking (straight beats flush), dealer qualifies with queen high, Ante, Play, Pair Plus and Ante bonus |
| `aceroyale.poker` | No-limit Texas Hold'em: 5- and 7-card evaluator, a single-hand engine with side pots and min-raise rules, and Monte Carlo bots |

Every game uses the same card encoding: an int `XYY`, where `X` is the suit
(1-4) and `YY` the rank (1 = ace ... 13 = king). `101` is an ace, `413` a king.

## Poker bots

Bots are a separate subsystem from the engine. The engine never asks a bot what
happens next: it hands the bot a read-only view of the table (its own two
cards, the board, pot, stacks, legal actions) and the bot answers with an
*intent*, such as "raise to 40". The engine then validates that intent with the
same rules it applies to a human. A buggy bot can play badly, but it cannot
cheat or corrupt the hand.

Skill comes mostly from **how well each bot estimates its equity**, not from a
list of hand-written rules. Equity is estimated by Monte Carlo: deal random
hands to the opponents, complete the board, count how often the bot wins.
With few samples the estimate is noisy and the bot makes real mistakes, like a
beginner; with many it gets sharp. On top of that, each personality has its own
style: how loose it plays, how often it raises and bluffs. Decisions weigh that
equity against pot odds.

| Level | Display name | Monte Carlo samples |
|---|---|---|
| `beginner` | Rookie | few, noisy estimates |
| `casual` | Casual | more |
| `advanced` | Sharp | more still |
| `expert` | Shark | many, accurate estimates |

The tests pit each level against the one below over hundreds of seeded hands
and check that the stronger level comes out ahead.

## Hand evaluator

`best_hand` is the reference implementation: it tries all 21 five-card
combinations of a 7-card hand. `score_7` is the fast path used by the bots,
which reads rank and suit counts directly. The two are checked against each
other on 30,000 random 5-, 6- and 7-card hands, and `evaluate_5` is checked
against the exact category frequencies of all 2,598,960 five-card hands.

| Evaluator (7 cards, Python 3.9) | Hands per second |
|---|---|
| `best_hand` (reference) | ~21,000 |
| `score_7` (fast path) | ~252,000 |

Measured on 20,000 seeded random hands; both give identical results.

## Quick start

```bash
git clone <this repo>
cd ace-royale-engine
python3 tests/run.py          # or: pip install -e ".[dev]" && pytest
```

A full Hold'em hand between two bots:

```python
from aceroyale.poker import Hand, Seat, create_strategy, view_for

seats = [Seat("A", 1000, is_bot=True), Seat("B", 1000, is_bot=True)]
bots = [create_strategy("expert", seed=1), create_strategy("beginner", seed=2)]
hand = Hand(seats, button=0, small_blind=5, big_blind=10)
while not hand.finished:
    i = hand.turn
    action, amount = bots[i].decide(view_for(hand, i))
    hand.act(i, action, amount)          # raises ValueError if illegal
print(hand.result["winners"], [s.chips for s in seats])
```

A baccarat coup:

```python
from aceroyale.baccarat import Shoe, play_hand, settle

hand = play_hand(Shoe().draw)
print(hand["player"], hand["banker"], hand["winner"])
print(settle({"player": 0, "banker": 100, "tie": 0}, hand["winner"]))
```

## Tests

47 tests, about 40 seconds, all seeded so they are deterministic. Highlights:

- Exact enumeration of every five-card hand against the known category counts
- Fast evaluator vs. reference evaluator on random and hand-picked tricky hands
- Side pots, split pots (odd chip), short all-ins, chip conservation over hundreds of random hands
- The engine rejects every illegal action (wrong turn, under-minimum raise, over-stack bet...)
- Bots only ever see their own cards, cannot break the rules, and stronger levels beat weaker ones
- Blackjack splits, doubles, insurance and naturals; baccarat tableau; Three Card Poker payouts

## Roadmap

- Fast hand evaluator in Rust (bitmasks + lookup tables), benchmarked against `score_7`
- Omaha (four hole cards, must use exactly two)
- Poker Spins (three-player sit & go with a random prize multiplier) and tournaments (blind schedule, payouts)
- Blackjack and baccarat side bets
- Quant simulations: house edge of every game and side bet, blackjack basic strategy,
  Hi-Lo card counting with Kelly bet sizing and risk of ruin, and the chip economy of Spins

## Author

Built by **Bruno González**, with contributions from Pablo de la Fuente and
Robert Cincea.

## License

[MIT](LICENSE)
