"""Automated players.

A subsystem separate from the engine. The engine NEVER asks a bot "what
happens now?": it gives it a read-only view of the table and the bot answers
with an intent ("raise to 40"). The engine then validates that intent with
the same rules it applies to a human. A buggy bot can play badly, but it
cannot cheat or break the game.

Where the difference in skill comes from
----------------------------------------
Not from a list of "if X happens do Y", but mostly from how WELL each bot
estimates its chances. Equity is computed by simulation: random hands are
dealt to the opponents, the board is completed and the wins are counted. With
few simulations the estimate is noisy and the bot genuinely makes mistakes,
like a beginner; with many, it sharpens. On top of that, each personality has
its own character: how loose it plays, how much it raises and how much it
bluffs.
"""

import logging
from random import Random

from .hands import score_7, score_omaha, full_deck

log = logging.getLogger("aceroyale.poker.bots")


class Personality:
    """Parameters that define how a bot plays."""

    def __init__(self, key, name, label, samples, call_threshold,
                 raise_threshold, bluff, aggression, noise):
        self.key = key
        self.name = name                      # what is shown at the table
        self.label = label                    # skill level, for display
        self.samples = samples                # simulations when estimating equity
        self.call_threshold = call_threshold  # margin required over the pot odds
        self.raise_threshold = raise_threshold
        self.bluff = bluff                    # probability of bluffing with nothing
        self.aggression = aggression          # bet size relative to the pot
        self.noise = noise                    # how far it strays from its own plan


# raise_threshold is in "advantage", not in absolute equity: 1.0 is exactly the
# fair share per player (1/2 heads-up, 1/6 at a full table), so 1.4 means "40%
# better than my share" and works the same with two or with six at the table.
# With an absolute threshold, a bot raised non-stop heads-up and never raised
# at a full table.
PERSONALITIES = {
    "beginner": Personality(
        key="beginner", name="Rookie", label="Beginner",
        # Few simulations: it believes in good hands that are not.
        samples=40,
        call_threshold=-0.14,   # negative = calls below the pot odds
        raise_threshold=1.10,
        bluff=0.05, aggression=0.45, noise=0.28),

    "casual": Personality(
        key="casual", name="Casual", label="Casual",
        samples=120,
        call_threshold=-0.03,
        raise_threshold=1.28,
        bluff=0.08, aggression=0.58, noise=0.15),

    "advanced": Personality(
        key="advanced", name="Sharp", label="Advanced",
        samples=320,
        call_threshold=0.02,
        raise_threshold=1.42,
        bluff=0.11, aggression=0.68, noise=0.07),

    "expert": Personality(
        key="expert", name="Shark", label="Expert",
        samples=650,
        call_threshold=0.04,
        raise_threshold=1.52,
        bluff=0.14, aggression=0.78, noise=0.03),
}

LEVEL_ORDER = ("beginner", "casual", "advanced", "expert")


class BotView:
    """
    What a bot can see. Deliberately poor: its own cards, the board and the
    public numbers. Nothing about the other players' cards.
    """

    def __init__(self, cards, board, pot, to_call, chips,
                 opponents, street, actions, current_bet, big_blind):
        self.cards = list(cards)
        self.board = list(board)
        self.pot = pot
        self.to_call = to_call
        self.chips = chips
        self.opponents = opponents
        self.street = street
        self.actions = actions
        self.current_bet = current_bet
        self.big_blind = big_blind


def view_for(hand, i):
    """
    Builds the BotView of seat `i` from a running engine Hand.

    Only public information plus the seat's own hole cards is copied, so a
    strategy cannot look at anyone else's cards even by accident.
    """
    seat = hand.seats[i]
    opponents = sum(1 for s in hand.seats if s.in_hand and s is not seat)
    return BotView(
        cards=seat.cards,
        board=hand.board,
        pot=hand.pot,
        to_call=hand.current_bet - seat.street_bet,
        chips=seat.chips,
        opponents=opponents,
        street=hand.street,
        actions=hand.valid_actions(i),
        current_bet=hand.current_bet,
        big_blind=hand.bb,
    )


def estimate_equity(cards, board, opponents, samples, rng):
    """
    Approximate probability of winning, by Monte Carlo simulation.

    Random cards are dealt to the opponents and the missing community cards
    are completed, many times, counting how often we win. Ties count as a
    fraction, which is how the pot is really split.

    The game is read from the number of hole cards: two is Hold'em (any five
    of seven), four is Omaha (exactly two from the hand, and the opponents
    are dealt four each too).

    :param opponents: how many are still in the hand besides ourselves
    :param samples: number of simulations (more means a better estimate)
    """
    if opponents <= 0:
        return 1.0

    hole = len(cards)
    if hole == 2:
        def score(own, table):
            return score_7(own + table)
    else:
        score = score_omaha

    known = set(cards) | set(board)
    rest = [c for c in full_deck() if c not in known]
    missing = 5 - len(board)

    won = 0.0
    for _ in range(samples):
        rng.shuffle(rest)
        i = 0
        table = list(board)
        if missing:
            table += rest[i:i + missing]
            i += missing

        mine = score(list(cards), table)
        best_opponent = None
        for _ in range(opponents):
            theirs = rest[i:i + hole]
            i += hole
            s = score(theirs, table)
            if best_opponent is None or s > best_opponent:
                best_opponent = s

        if mine > best_opponent:
            won += 1.0
        elif mine == best_opponent:
            won += 0.5
    return won / samples


class BotStrategy:
    """Decides a bot's move from its personality."""

    def __init__(self, personality, seed=None):
        self.p = personality
        self.rng = Random(seed)

    def decide(self, view: BotView):
        """
        :return: (action, amount). The amount only matters for bet/raise and
            is the total the bet should be raised to.
        """
        actions = view.actions
        if not actions:
            return ("fold", 0)

        equity = estimate_equity(view.cards, view.board,
                                 view.opponents, self.p.samples, self.rng)
        # The noise is proportional, not absolute: if it were absolute, at a
        # six-handed table (equity ~0.17) it would swallow the whole signal.
        equity *= 1.0 + self.rng.gauss(0, self.p.noise)
        equity = min(1.0, max(0.0, equity))

        # Advantage: 1.0 = exactly my share given the number of players.
        advantage = equity * (view.opponents + 1)

        pot = max(1, view.pot)
        to_call = view.to_call

        if to_call <= 0:
            return self._unopened(view, equity, advantage, pot)
        return self._facing_bet(view, equity, advantage, pot, to_call)

    # ------------------------------------------------------ nobody has bet

    def _unopened(self, view, equity, advantage, pot):
        actions = view.actions
        can_bet = "bet" in actions or "raise" in actions

        if can_bet and advantage >= self.p.raise_threshold:
            return self._bet_size(view, equity, advantage, pot)

        # Bluff: betting with nothing. Only against few opponents; bluffing
        # four people at once does not work and burns chips.
        if (can_bet and view.opponents <= 2
                and self.rng.random() < self.p.bluff):
            return self._bet_size(view, 0.35, 1.0, pot, bluff=True)

        if "check" in actions:
            return ("check", 0)
        return ("fold", 0)

    # ------------------------------------------------------ facing a bet

    def _facing_bet(self, view, equity, advantage, pot, to_call):
        actions = view.actions

        # Pot odds: what share of the final pot I am putting in. If my equity
        # does not reach that, calling loses money in the long run.
        odds = to_call / (pot + to_call)

        if "raise" in actions and advantage >= self.p.raise_threshold:
            return self._bet_size(view, equity, advantage, pot)

        if equity >= odds + self.p.call_threshold:
            if "call" in actions:
                return ("call", 0)

        # bluff-raise, only when few players are left
        if ("raise" in actions and view.opponents == 1
                and self.rng.random() < self.p.bluff * 0.5):
            return self._bet_size(view, 0.35, 1.0, pot, bluff=True)

        # call something very cheap with any hand (everyone does it a bit)
        if "call" in actions and to_call <= view.big_blind and equity > 0.25:
            return ("call", 0)

        if "check" in actions:
            return ("check", 0)
        return ("fold", 0)

    # ------------------------------------------------------ bet sizing

    def _bet_size(self, view, equity, advantage, pot, bluff=False):
        """
        Bet size: a fraction of the pot, between a third and a bit over three
        quarters. Earlier versions produced bets of several times the pot and
        the variance exploded: hands were decided by who shoved, not by who
        played better.
        """
        actions = view.actions
        key = "raise" if "raise" in actions else "bet"
        if key not in actions:
            return ("call", 0) if "call" in actions else ("check", 0)

        limits = actions[key]
        minimum, maximum = limits["min"], limits["max"]

        strength = 0.0 if bluff else min(1.0, max(0.0, (advantage - 1.0) / 1.2))
        fraction = 0.35 + 0.45 * strength * self.p.aggression
        target = view.current_bet + int(pot * fraction)

        # Go all-in only with a near-made hand for real, and only now and then.
        if not bluff and equity > 0.88 and advantage > 1.7 and self.rng.random() < 0.18:
            target = maximum

        target = max(minimum, min(maximum, target))
        return (key, target)


def create_strategy(level: str, seed=None, samples=None) -> BotStrategy:
    """
    Strategy for a given level ('beginner', 'casual', 'advanced', 'expert').

    Unknown levels fall back to 'casual'.

    :param samples: if given, replaces the personality's number of
        simulations. Only the tests use it, so as not to take forever checking
        things that do not depend on how well the bot plays.
    """
    base = PERSONALITIES.get(level, PERSONALITIES["casual"])
    if samples is not None:
        base = Personality(base.key, base.name, base.label, int(samples),
                           base.call_threshold, base.raise_threshold, base.bluff,
                           base.aggression, base.noise)
    return BotStrategy(base, seed)


def available_names():
    """Names the bots sit down with, to avoid repeats at a table."""
    return ["Rookie", "Casual", "Sharp", "Shark", "Ace", "Duchess",
            "Slim", "Cooler", "Nickel", "Bishop", "Fox", "Ruby"]
