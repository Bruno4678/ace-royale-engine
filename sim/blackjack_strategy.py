"""Blackjack basic strategy derived by dynamic programming.

Rules (the casino standard chosen for the simulations): dealer stands on soft
17, blackjack pays 3:2, double on any first two cards, double after split,
split up to four hands, split aces get one card each, the dealer checks for
blackjack first (a dealer blackjack only takes the original bet), no
surrender, no insurance.

Method: infinite-deck probabilities (each rank independent, a ten-value card
4/13), which is the standard way basic strategy is derived; the 6-deck
simulation then measures how it actually does in a real shoe.

  1. The dealer's final total is computed exactly for each upcard, given
     that the dealer does not have blackjack (the hand would be over).
  2. Standing is worth P(win) - P(lose) against that distribution.
  3. Hitting is the expectation, over the next card, of the best choice
     after it: a recursion over (total, soft) states, memoised.
  4. Doubling is twice the value of standing after exactly one card.
  5. Splitting is twice the value of a hand started with one card of the
     pair, where doubling is allowed again (resplits are not modelled; they
     change the edge by a few thousandths of a percent).

The best action in each cell gives the strategy table; the probability
weighted value of the initial deal gives the player's expected return.
"""

from functools import lru_cache

from .common import pct, save_json

UPCARDS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 1)        # 1 = ace
P = {r: (4 / 13 if r == 10 else 1 / 13) for r in range(1, 11)}
BLACKJACK_PAYS = 1.5


def add(total, soft, card):
    """Adds a card (1..10) to a (total, soft) hand. Aces count 11 when they fit."""
    if card == 1:
        if total + 11 <= 21:
            return total + 11, True
        card = 1
    total += card
    if total > 21 and soft:
        return total - 10, False
    return total, soft


# ---------------------------------------------------------------- dealer

@lru_cache(maxsize=None)
def _dealer_from(total, soft):
    """Final dealer distribution from a (total, soft) state, standing on all 17s."""
    if total > 21:
        return {"bust": 1.0}
    if total >= 17:
        return {total: 1.0}
    out = {}
    for r, p in P.items():
        for k, v in _dealer_from(*add(total, soft, r)).items():
            out[k] = out.get(k, 0.0) + p * v
    return out


@lru_cache(maxsize=None)
def dealer_final(upcard):
    """Dealer final distribution for an upcard, given no dealer blackjack."""
    start = add(0, False, upcard)
    out, mass = {}, 0.0
    for hole, p in P.items():
        if (upcard == 1 and hole == 10) or (upcard == 10 and hole == 1):
            continue                                  # that would be blackjack
        mass += p
        for k, v in _dealer_from(*add(*start, hole)).items():
            out[k] = out.get(k, 0.0) + p * v
    return {k: v / mass for k, v in out.items()}


def dealer_blackjack_probability(upcard):
    return P[10] if upcard == 1 else (P[1] if upcard == 10 else 0.0)


# ---------------------------------------------------------------- player

@lru_cache(maxsize=None)
def ev_stand(total, upcard):
    if total > 21:
        return -1.0
    ev = 0.0
    for k, p in dealer_final(upcard).items():
        if k == "bust" or total > k:
            ev += p
        elif total < k:
            ev -= p
    return ev


@lru_cache(maxsize=None)
def ev_hit(total, soft, upcard):
    """Value of hitting once and then playing the best of hit/stand."""
    ev = 0.0
    for r, p in P.items():
        t, s = add(total, soft, r)
        ev += p * (-1.0 if t > 21 else max(ev_stand(t, upcard), ev_hit(t, s, upcard)))
    return ev


@lru_cache(maxsize=None)
def ev_double(total, soft, upcard):
    ev = 0.0
    for r, p in P.items():
        t, _ = add(total, soft, r)
        ev += p * ev_stand(t, upcard)
    return 2 * ev


def ev_best(total, soft, upcard, can_double=True):
    options = {"S": ev_stand(total, upcard), "H": ev_hit(total, soft, upcard)}
    if can_double:
        options["D"] = ev_double(total, soft, upcard)
    action = max(options, key=options.get)
    return options[action], action, options


@lru_cache(maxsize=None)
def ev_split(card, upcard):
    """Value of splitting a pair of `card` (both hands together)."""
    ev = 0.0
    for r, p in P.items():
        total, soft = add(*add(0, False, card), r)
        if card == 1:
            ev += p * ev_stand(total, upcard)       # split aces: one card each
        else:
            ev += p * ev_best(total, soft, upcard, can_double=True)[0]
    return 2 * ev


def decision(cards, upcard):
    """
    Best action for a two-card hand: "H", "S", "D" or "P", with every option's EV.
    `cards` are blackjack points (1 = ace).
    """
    total, soft = add(*add(0, False, cards[0]), cards[1])
    best, action, options = ev_best(total, soft, upcard)
    if cards[0] == cards[1]:
        options["P"] = ev_split(cards[0], upcard)
        if options["P"] > best:
            action = "P"
    return action, options


# ---------------------------------------------------------------- tables

def _label(options):
    """Table code. D = double (else hit), Ds = double (else stand)."""
    action = max(options, key=options.get)
    if action == "D":
        return "Ds" if options["S"] > options["H"] else "D"
    return action


def strategy_tables():
    hard, soft, pairs = {}, {}, {}
    for total in range(5, 18):
        # a hard total made of two non-pair cards
        a = 2 if total - 2 != 2 else 3
        cards = (a, total - a) if total - a <= 10 else (10, total - 10)
        hard[total] = {u: _label(decision(cards, u)[1]) for u in UPCARDS}
    for other in range(2, 10):
        soft[other] = {u: _label(decision((1, other), u)[1]) for u in UPCARDS}
    for c in (1, 10, 9, 8, 7, 6, 5, 4, 3, 2):
        pairs[c] = {}
        for u in UPCARDS:
            action, options = decision((c, c), u)
            pairs[c][u] = "P" if action == "P" else _label(
                {k: v for k, v in options.items() if k != "P"})
    return hard, soft, pairs


def player_edge():
    """Expected return of one round, per unit of the original bet."""
    ev = 0.0
    for u, pu in P.items():
        p_dbj = dealer_blackjack_probability(u)
        for c1, p1 in P.items():
            for c2, p2 in P.items():
                p = pu * p1 * p2
                natural = {c1, c2} == {1, 10}
                if natural:
                    play = BLACKJACK_PAYS
                    with_dbj = 0.0                      # blackjack vs blackjack
                else:
                    action, options = decision((c1, c2), u)
                    play = options[action]
                    with_dbj = -1.0                     # only the original bet
                ev += p * (p_dbj * with_dbj + (1 - p_dbj) * play)
    return ev


def _name(u):
    return "A" if u == 1 else ("T" if u == 10 else str(u))


def format_tables(hard, soft, pairs):
    """Plain-text tables: rows are the player's hand, columns the dealer upcard."""
    head = "       " + " ".join(f"{_name(u):>3}" for u in UPCARDS)
    lines = ["Hard", head]
    for t, row in hard.items():
        lines.append(f"{t:>6} " + " ".join(f"{row[u]:>3}" for u in UPCARDS))
    lines += ["Soft", head]
    for o, row in soft.items():
        lines.append(f"{'A,' + str(o):>6} " + " ".join(f"{row[u]:>3}" for u in UPCARDS))
    lines += ["Pairs", head]
    for c, row in pairs.items():
        label = _name(c) + "," + _name(c)
        lines.append(f"{label:>6} " + " ".join(f"{row[u]:>3}" for u in UPCARDS))
    return "\n".join(lines)


def main():
    hard, soft, pairs = strategy_tables()
    edge = player_edge()
    text = format_tables(hard, soft, pairs)
    print("Blackjack basic strategy (S17, DAS, 3:2, infinite deck)")
    print(text)
    print(f"Player expected return with this strategy: {pct(edge, 3)}")
    keyed = lambda table: {str(k): {_name(u): a for u, a in row.items()} for k, row in table.items()}
    return save_json("blackjack_strategy", {
        "rules": "S17, DAS, 3:2, double any two, split to 4, split aces one card, peek, no surrender",
        "player_edge_infinite_deck": edge,
        "hard": keyed(hard), "soft": keyed(soft), "pairs": keyed(pairs),
        "table_text": text,
    })


if __name__ == "__main__":
    main()
