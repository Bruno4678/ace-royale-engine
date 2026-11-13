"""Glue between the showcase page and the engine.

The page loads this module into Pyodide (CPython compiled to WebAssembly) next
to the `aceroyale` package, so every number it shows comes from the engine
itself. Each public function takes plain values and returns a JSON string, the
simplest thing to hand across the JavaScript boundary.

The same module runs under normal CPython, which is how tests/test_showcase.py
checks it.
"""

import json
import math
from random import Random

from aceroyale.baccarat.rules import BANKER_COMMISSION, payout
from aceroyale.poker import bots as _bots
from aceroyale.poker import (PERSONALITIES, Hand, Seat, create_strategy,
                             full_deck, view_for)

# ------------------------------------------------------------------ equity

def equity(cards, board, opponents=1, samples=20000, seed=None):
    """
    Monte Carlo equity of `cards` against random hands, with the engine's own
    `estimate_equity`: the same function the bots use, only with more samples.

    Ties count as half a win, so the 95% interval uses the binomial standard
    error as a (slightly conservative) approximation.
    """
    cards = [int(c) for c in cards]
    board = [int(c) for c in board]
    known = cards + board
    if len(cards) != 2:
        raise ValueError("pick exactly two hole cards")
    if len(board) not in (0, 3, 4, 5):
        raise ValueError("the board has 0, 3, 4 or 5 cards")
    if len(set(known)) != len(known) or not set(known) <= set(full_deck()):
        raise ValueError("every card must be a different, valid card")
    if not 1 <= int(opponents) <= 8:
        raise ValueError("between 1 and 8 opponents")

    samples = int(samples)
    p = _estimate_equity(cards, board, int(opponents), samples, Random(seed))
    ci = 1.96 * math.sqrt(max(p * (1 - p), 1e-12) / samples)
    return json.dumps({"equity": p, "ci95": ci, "samples": samples,
                       "opponents": int(opponents)})


def level_spread(cards, board, opponents=1, runs=40, seed=None):
    """
    The same equity estimated `runs` times with each bot level's sample
    count: how noisy each level's view of its own hand is.
    """
    cards = [int(c) for c in cards]
    board = [int(c) for c in board]
    rng = Random(seed)
    out = {}
    for key, p in PERSONALITIES.items():
        out[key] = {"name": p.name, "samples": p.samples,
                    "estimates": [_estimate_equity(cards, board, int(opponents),
                                                   p.samples, rng)
                                  for _ in range(int(runs))]}
    return json.dumps(out)


# ----------------------------------------------------------- heads-up match

# The bots call `estimate_equity` from their own module. Wrapping it there
# lets the page show the equity a bot believed it had when it decided, before
# its personality's noise, without changing the bot.
_last_estimate = {}
_estimate_equity = _bots.estimate_equity


def _recording_estimate(*args, **kwargs):
    value = _estimate_equity(*args, **kwargs)
    _last_estimate["equity"] = value
    return value


_bots.estimate_equity = _recording_estimate


class Match:
    """You against one bot, heads-up no-limit Hold'em, hand after hand."""

    HUMAN, BOT = 0, 1

    def __init__(self, level="expert", chips=1000, small_blind=5, big_blind=10,
                 seed=None):
        if level not in PERSONALITIES:
            raise ValueError(f"unknown level {level!r}")
        self.level = level
        self.start_chips = int(chips)
        self.sb, self.bb = int(small_blind), int(big_blind)
        self.rng = Random(seed)
        self.bot = create_strategy(level, seed=self.rng.randrange(2 ** 32))
        self.names = ["You", PERSONALITIES[level].name]
        self.chips = [self.start_chips, self.start_chips]
        self.seats = None
        self.button = self.rng.randrange(2)
        self.hand = None
        self.hands_played = 0
        self.log = []
        self.new_hand()

    def new_hand(self):
        """Deals the next hand; if someone went broke, both restart."""
        if self.seats is not None:
            self.chips = [s.chips for s in self.seats]
        reset = any(c < self.bb for c in self.chips)
        if reset:
            self.chips = [self.start_chips, self.start_chips]
        if self.hand is not None:
            self.button = 1 - self.button
        # A Seat is a player within ONE hand, so every hand gets fresh seats.
        self.seats = [Seat(self.names[0], self.chips[0]),
                      Seat(self.names[1], self.chips[1], is_bot=True)]
        deck = full_deck()
        self.rng.shuffle(deck)
        self.hand = Hand(self.seats, button=self.button, small_blind=self.sb,
                         big_blind=self.bb, deck=deck)
        self.hands_played += 1
        self.log = [{"event": "deal", "hand": self.hands_played,
                     "button": self.seats[self.button].name, "reset": reset}]
        self._run_bot()

    def act(self, action, amount=0):
        """Your move. Raises ValueError, from the engine, if it is illegal."""
        if self.hand.finished or self.hand.turn != self.HUMAN:
            raise ValueError("it is not your turn")
        street = self.hand.street
        self.hand.act(self.HUMAN, action, int(amount))
        self.log.append({"event": "action", "who": "You", "street": street,
                         "action": action, "amount": int(amount)})
        self._run_bot()

    def _run_bot(self):
        h = self.hand
        while not h.finished and h.turn == self.BOT:
            street = h.street
            _last_estimate.clear()
            action, amount = self.bot.decide(view_for(h, self.BOT))
            h.act(self.BOT, action, amount)
            self.log.append({"event": "action", "who": self.seats[self.BOT].name,
                             "street": street, "action": action,
                             "amount": int(amount),
                             "equity": _last_estimate.get("equity")})

    def state(self):
        h = self.hand
        me, bot = self.seats
        result = None
        bot_cards = None
        if h.finished:
            r = h.result
            result = {
                "showdown": r["showdown"],
                "winners": [self.seats[i].name for i in r["winners"]],
                "pots": [{"amount": p["amount"], "hand": p["hand"],
                          "winners": [self.seats[i].name for i in p["winners"]]}
                         for p in r["pots"]],
                "hands": {self.seats[i].name: v["text"] for i, v in r["hands"].items()},
            }
            if r["showdown"]:
                bot_cards = list(bot.cards)
        return {
            "level": self.level,
            "bot_name": bot.name,
            "hand_number": self.hands_played,
            "button": self.seats[self.button].name,
            "street": h.street,
            "board": list(h.board),
            "my_cards": list(me.cards),
            "bot_cards": bot_cards,
            "pot": h.pot,
            "chips": {me.name: me.chips, bot.name: bot.chips},
            "bets": {me.name: me.street_bet, bot.name: bot.street_bet},
            "my_turn": (not h.finished) and h.turn == self.HUMAN,
            "actions": h.valid_actions(self.HUMAN) if not h.finished else {},
            "finished": h.finished,
            "result": result,
            "log": self.log,
        }


_match = None


def start_match(level="expert", seed=None):
    global _match
    _match = Match(level, seed=seed)
    return json.dumps(_match.state())


def match_act(action, amount=0):
    _match.act(action, amount)
    return json.dumps(_match.state())


def match_next_hand():
    _match.new_hand()
    return json.dumps(_match.state())


# ---------------------------------------------------------------- baccarat

def banker_returns(p_banker, p_player, max_bet=200):
    """
    Expected return per chip of a Banker bet of every size from 5 to
    `max_bet`, with the engine's commission (rounded up) and with the old
    rounded-down version, for comparison.
    """
    def expected(bet, returned_on_win):
        p_tie = 1 - p_banker - p_player
        back = p_banker * returned_on_win + p_tie * bet
        return (back - bet) / bet

    rows = []
    for bet in range(5, int(max_bet) + 1):
        up = expected(bet, payout("banker", bet, "banker"))
        down = expected(bet, 2 * bet - bet * BANKER_COMMISSION // 100)
        rows.append({"bet": bet, "up": up, "down": down})
    return json.dumps(rows)
