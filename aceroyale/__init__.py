"""Ace Royale engine: game rules, payouts, hand evaluation and poker bots.

Every game shares the same card encoding: an int ``XYY`` where ``X`` is the
suit (1-4) and ``YY`` the rank (1 = ace ... 13 = king). ``101`` is the ace of
suit 1 and ``413`` the king of suit 4.

Pure Python 3.9+, standard library only. No web, database or I/O code lives
here: the engine only computes, so it can be tested and simulated in bulk.
"""

__version__ = "0.1.0"
