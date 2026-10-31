"""Engine for one hand of no-limit Texas Hold'em.

This is pure Python: it knows nothing about networking, threads or storage.
A `Hand` holds the state of ONE hand from the blinds to the distribution of
the pot, and only moves forward when someone calls `act()`. Who has to act,
when and with which options is always decided by the Hand; the caller never
works anything out on its own.

Rules implemented:
  - small blind / big blind, rotating button
  - heads-up (2 players): the button is the small blind and acts first
    before the flop, and last after it
  - minimum raise = size of the last raise (standard no-limit rule)
  - an all-in below the minimum raise does NOT reopen the betting
  - side pots when someone is short-stacked
  - if only one player has not folded, they win without showing cards
"""

import random

from .hands import best_hand, full_deck, describe


class Seat:
    """A player within one specific hand."""

    def __init__(self, name:str, chips:int, is_bot:bool=False, player_id:str=None):
        self.name = name
        self.id = player_id or name
        self.is_bot = is_bot
        self.chips = int(chips)

        self.cards = []             # the two hole cards
        self.street_bet = 0         # put in on the current street
        self.total_contributed = 0  # put in over the whole hand
        self.state = "active"       # active | folded | all_in
        self.last_action = None     # to show at the table

    @property
    def in_hand(self)->bool:
        """Still contending for the pot (even if all-in and unable to bet more)."""
        return self.state in ("active", "all_in")

    @property
    def can_act(self)->bool:
        return self.state == "active" and self.chips > 0


class Hand:
    """A complete hand. Create it, keep sending it actions, and it finishes."""

    STREETS = ("preflop", "flop", "turn", "river")

    def __init__(self, seats, button:int, small_blind:int, big_blind:int,
                 deck:list=None):
        self.seats = list(seats)
        self.button = button % len(self.seats)
        self.sb = int(small_blind)
        self.bb = int(big_blind)

        self.deck = deck if deck is not None else full_deck()
        if deck is None:
            random.shuffle(self.deck)

        self.board = []
        self.street = "preflop"
        self.dead_pot = 0           # chips from streets already closed
        self.current_bet = 0        # amount to match on this street
        self.min_raise = self.bb
        self.turn = None
        self.to_act = set()
        self.finished = False
        self.result = None          # filled in when the hand ends
        self.history = []

        self._deal_hole_cards()
        self._post_blinds()

    # ------------------------------------------------------------ setup

    def _draw(self):
        return self.deck.pop()

    def _deal_hole_cards(self):
        for s in self.seats:
            if s.chips > 0:
                s.cards = [self._draw(), self._draw()]

    def _seats_with_chips(self):
        return [i for i, s in enumerate(self.seats) if s.chips > 0]

    def _next(self, start:int, only_active:bool=True)->int:
        """Index of the next seat going round the table."""
        n = len(self.seats)
        for step in range(1, n + 1):
            i = (start + step) % n
            s = self.seats[i]
            if only_active:
                if s.can_act:
                    return i
            elif s.in_hand:
                return i
        return start

    def _post_blinds(self):
        playing = [i for i, s in enumerate(self.seats) if s.in_hand]
        n = len(playing)

        if n == 2:
            # Heads-up: the button is the small blind.
            i_sb = self.button
            i_bb = [i for i in playing if i != self.button][0]
        else:
            i_sb = self._next(self.button, only_active=False)
            i_bb = self._next(i_sb, only_active=False)

        self.i_sb = i_sb
        self.i_bb = i_bb
        self._bet(i_sb, min(self.sb, self.seats[i_sb].chips), blind=True)
        self._bet(i_bb, min(self.bb, self.seats[i_bb].chips), blind=True)

        self.current_bet = self.bb
        self.min_raise = self.bb

        # Before the flop the player to the left of the big blind acts first;
        # heads-up, the small blind (who is the button).
        if n == 2:
            first = i_sb if self.seats[i_sb].can_act else i_bb
        else:
            first = self._next(i_bb)

        self.to_act = {i for i, s in enumerate(self.seats) if s.can_act}
        self.turn = first if self.seats[first].can_act else None
        if self.turn is None:
            self._close_street()

    # ------------------------------------------------------------ betting

    def _bet(self, i:int, amount:int, blind:bool=False):
        """Moves chips from the seat into the current street's pot."""
        s = self.seats[i]
        amount = max(0, min(int(amount), s.chips))
        s.chips -= amount
        s.street_bet += amount
        s.total_contributed += amount
        if s.chips == 0:
            s.state = "all_in"
        return amount

    @property
    def pot(self)->int:
        """Everything bet in the hand: closed streets + the current street."""
        return self.dead_pot + sum(s.street_bet for s in self.seats)

    def valid_actions(self, i:int=None)->dict:
        """
        What seat `i` (by default, the one whose turn it is) can do right now.

        Returns a dictionary like::

            {"fold": {}, "call": {"amount": 20},
             "raise": {"min": 40, "max": 200}}

        The limits come already computed: the caller does not need to know
        the rules.
        """
        if i is None:
            i = self.turn
        if self.finished or i is None or i != self.turn:
            return {}
        s = self.seats[i]
        if not s.can_act:
            return {}

        to_call = self.current_bet - s.street_bet
        options = {}

        # Folding is always allowed, even though it makes no sense if you can check.
        options["fold"] = {}

        if to_call <= 0:
            options["check"] = {}
        else:
            options["call"] = {"amount": min(to_call, s.chips)}

        # Bet or raise: you need more chips than it costs to call.
        if s.chips > to_call:
            if self.current_bet == 0:
                minimum = min(self.bb, s.chips)
                options["bet"] = {"min": minimum,
                                  "max": s.chips}
            else:
                # the total the bet would be raised to, not the increment
                minimum = self.current_bet + self.min_raise
                maximum = s.street_bet + s.chips
                options["raise"] = {"min": min(minimum, maximum), "max": maximum}
        return options

    def act(self, i:int, action:str, amount:int=0):
        """
        Applies an action. Raises ValueError if it is not legal: the caller can
        pass whatever it likes, nothing illegal gets through.
        """
        if self.finished:
            raise ValueError("the hand is already finished")
        if i != self.turn:
            raise ValueError("not your turn")

        options = self.valid_actions(i)
        if action not in options:
            raise ValueError(f"action not allowed: {action}")

        s = self.seats[i]

        if action == "fold":
            s.state = "folded"
            s.last_action = "Fold"

        elif action == "check":
            s.last_action = "Check"

        elif action == "call":
            put_in = self._bet(i, options["call"]["amount"])
            s.last_action = "All-in" if s.state == "all_in" else f"Call {put_in}"

        elif action in ("bet", "raise"):
            lim = options[action]
            target = int(amount)
            if target < lim["min"] or target > lim["max"]:
                raise ValueError(f"amount out of range: {target}")

            previous = self.current_bet
            self._bet(i, target - s.street_bet)
            new = s.street_bet

            # A short all-in raises the bar but does NOT reopen the betting:
            # those who had already called do not get the right to raise again.
            increment = new - previous
            reopens = increment >= self.min_raise

            self.current_bet = max(self.current_bet, new)
            if reopens:
                self.min_raise = increment
                self.to_act = {
                    j for j, o in enumerate(self.seats)
                    if o.can_act and j != i
                }
            else:
                self.to_act.discard(i)

            s.last_action = ("All-in" if s.state == "all_in"
                             else ("Bet " if action == "bet" else "Raise to ") + str(new))

        self.to_act.discard(i)
        self.history.append((self.street, s.name, s.last_action))
        self._advance()

    # ------------------------------------------------------------ flow

    def _advance(self):
        alive = [i for i, s in enumerate(self.seats) if s.in_hand]
        if len(alive) <= 1:
            self._finish_without_showdown(alive)
            return

        pending = {i for i in self.to_act if self.seats[i].can_act}
        if pending:
            following = self._next(self.turn)
            # find the next one who really has to act
            for step in range(len(self.seats) + 1):
                cand = (self.turn + 1 + step) % len(self.seats)
                if cand in pending:
                    self.turn = cand
                    return
            self.turn = following
            return

        self._close_street()

    def _close_street(self):
        """Closes the street: collects the bets and deals the next one."""
        self.dead_pot += sum(s.street_bet for s in self.seats)
        for s in self.seats:
            s.street_bet = 0
            if s.state == "active":
                s.last_action = None
        self.current_bet = 0
        self.min_raise = self.bb

        if self.street == "river":
            self._showdown()
            return

        self.street = self.STREETS[self.STREETS.index(self.street) + 1]
        if self.street == "flop":
            self._draw()  # burn card
            self.board += [self._draw(), self._draw(), self._draw()]
        else:
            self._draw()
            self.board.append(self._draw())

        able = [i for i, s in enumerate(self.seats) if s.can_act]
        if len(able) <= 1:
            # Everyone all-in but one: no more betting, everything is turned over.
            self.to_act = set()
            self.turn = None
            self._close_street()
            return

        self.to_act = set(able)
        # After the flop the player to the left of the button acts first.
        self.turn = self._next(self.button)

    # ------------------------------------------------------------ payout

    def _compute_pots(self):
        """
        Splits the pot into the main pot and side pots.

        Returns a list of (amount, [indices that can win it]) from smallest to
        largest. Chips from players who folded stay in the pot but their seat
        is not among the eligible ones.
        """
        contributions = {i: s.total_contributed for i, s in enumerate(self.seats)
                         if s.total_contributed > 0}
        if not contributions:
            return []

        levels = sorted(set(contributions.values()))
        pots = []
        previous = 0
        for level in levels:
            amount = sum(min(v, level) - min(v, previous)
                         for v in contributions.values())
            eligible = [i for i, s in enumerate(self.seats)
                        if s.in_hand and s.total_contributed >= level]
            if amount > 0 and eligible:
                pots.append((amount, eligible))
            elif amount > 0 and pots:
                # nobody eligible at this level: it is added to the previous pot
                a, e = pots[-1]
                pots[-1] = (a + amount, e)
            previous = level
        return pots

    def _finish_without_showdown(self, alive):
        self.dead_pot += sum(s.street_bet for s in self.seats)
        for s in self.seats:
            s.street_bet = 0
        total = self.dead_pot
        winner = alive[0] if alive else None
        if winner is not None:
            self.seats[winner].chips += total
        self.result = {
            "showdown": False,
            "winners": [winner] if winner is not None else [],
            "pots": [{"amount": total,
                      "winners": [winner] if winner is not None else [],
                      "hand": None}],
            "hands": {},
        }
        self.dead_pot = 0
        self.turn = None
        self.finished = True

    def _showdown(self):
        # completes the board if cards are missing (everyone all-in early)
        while len(self.board) < 5:
            self._draw()
            self.board.append(self._draw())

        scores = {}
        for i, s in enumerate(self.seats):
            if s.in_hand:
                score, five = best_hand(list(s.cards) + list(self.board))
                scores[i] = {"score": score, "cards": list(five),
                             "text": describe(score)}

        detail = []
        all_winners = set()
        for amount, eligible in self._compute_pots():
            candidates = [i for i in eligible if i in scores]
            if not candidates:
                continue
            best = max(scores[i]["score"] for i in candidates)
            winners = [i for i in candidates if scores[i]["score"] == best]

            # split: the odd chip goes to the first winner left of the button
            share = amount // len(winners)
            odd = amount - share * len(winners)
            for i in winners:
                self.seats[i].chips += share
            if odd:
                order = sorted(winners, key=lambda i: (i - self.button - 1) % len(self.seats))
                self.seats[order[0]].chips += odd

            all_winners.update(winners)
            detail.append({"amount": amount, "winners": winners,
                           "hand": scores[winners[0]]["text"]})

        self.result = {
            "showdown": True,
            "winners": sorted(all_winners),
            "pots": detail,
            "hands": {i: {"text": v["text"], "cards": v["cards"]}
                      for i, v in scores.items()},
        }
        self.dead_pot = 0
        self.street = "showdown"
        self.turn = None
        self.finished = True
