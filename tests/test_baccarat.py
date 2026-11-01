"""Tests for the baccarat rules.

The rules are tested with fixed cards (each case of the third-card table).
"""

from aceroyale.baccarat.rules import (banker_draws, payout, play_hand,
                                      settle, card_points, hand_value)


def rigged(*cards):
    """draw() function that hands out these cards in order."""
    pending = list(cards)
    return lambda: pending.pop(0)


# ------------------------------------------------------------ points

def test_points():
    assert card_points(101) == 1, "the ace is worth 1"
    assert card_points(207) == 7, "the 7 is worth 7"
    assert all(card_points(c) == 0 for c in (110, 211, 312, 413)), \
        "the 10 and the face cards are worth 0"
    assert hand_value([109, 406]) == 5, "9 + 6 = 15 -> 5"
    assert hand_value([113, 212]) == 0, "K + Q = 0"
    assert hand_value([104, 205, 309]) == 8, "4 + 5 + 9 = 18 -> 8"


# ------------------------------------------------------------ third card

def test_third_card():
    # (banker total, player's third card, draws?)
    cases = [
        (2, 108, True), (3, 108, False), (3, 109, True),
        (4, 101, False), (4, 102, True), (4, 107, True), (4, 108, False),
        (5, 103, False), (5, 104, True), (5, 107, True), (5, 108, False),
        (6, 105, False), (6, 106, True), (6, 107, True), (6, 108, False),
        (7, 106, False),
    ]
    banker_with = {2: [102, 110], 3: [103, 110], 4: [104, 110], 5: [105, 110],
                   6: [106, 110], 7: [107, 110]}
    bad = [(t, p, e) for t, p, e in cases if banker_draws(banker_with[t], p) != e]
    assert not bad, f"the banker's table holds case by case; failing: {bad}"
    assert banker_draws([105, 110], None) and not banker_draws([106, 110], None), \
        "if the player stands, the banker draws on 0-5 and stands on 6"


def test_hands():
    # order: P1, B1, P2, B2, (P3), (B3)
    h = play_hand(rigged(104, 110, 105, 113))              # player 9, banker 0
    assert h["natural"] and len(h["player"]) == 2 and len(h["banker"]) == 2, \
        "a natural stops the hand at two cards"
    assert h["winner"] == "player", "natural 9 against 0: the player wins"

    h = play_hand(rigged(102, 103, 101, 110, 108, 109))    # P 3 draws, B 3 with an 8: no
    assert len(h["player"]) == 3 and len(h["banker"]) == 2, \
        f"banker on 3 does not draw if the player's third card is an 8: {h}"
    assert h["player_value"] == 1 and h["winner"] == "banker", \
        "3 + 8 = 11 -> 1 loses to 3"

    h = play_hand(rigged(103, 106, 104, 110, 102, 101))    # P 7 stands, B 6 stands
    assert len(h["player"]) == 2 and len(h["banker"]) == 2, "7 against 6: nobody draws"

    h = play_hand(rigged(110, 113, 111, 112, 109, 109))    # 0 against 0, both draw
    assert h["winner"] == "tie" and len(h["order"]) == 6, \
        "both draw and tie on 9"
    assert [o["side"] for o in h["order"]] == \
        ["player", "banker", "player", "banker", "player", "banker"], \
        "the dealing order alternates"


# ------------------------------------------------------------ payouts

def test_payouts():
    assert payout("player", 100, "player") == 200, "Player 1:1"
    assert payout("banker", 100, "banker") == 195, "Banker 1:1 minus 5%"
    assert payout("banker", 5, "banker") == 9, \
        "the commission on 5 rounds up to 1"
    assert payout("banker", 30, "banker") == 58, "the commission on 30 is 2"
    assert payout("banker", 20, "banker") == 39, "on 20 the 5% is exact"


def test_no_banker_bet_favours_the_player():
    # Exact outcome probabilities of an 8-deck shoe (see sim/baccarat_edge.py)
    p_banker, p_player = 0.458597, 0.446247
    favoured = [n for n in range(1, 2001)
                if p_banker * (payout("banker", n, "banker") - n) / n - p_player > 0]
    assert not favoured, favoured[:10]
    assert payout("tie", 10, "tie") == 90, "Tie 8:1"
    assert payout("player", 50, "tie") == 50, "a tie returns Player"
    assert payout("banker", 50, "tie") == 50, "a tie returns Banker"
    assert payout("tie", 10, "banker") == 0, "Tie loses if there is no tie"
    assert payout("player", 10, "banker") == 0, "Player loses if the banker wins"

    s = settle({"player": 100, "tie": 20}, "tie")
    assert s["staked"] == 120 and s["returned"] == 280 and s["net"] == 160, \
        f"Player + Tie on a tie: Player is returned and Tie is paid: {s}"
