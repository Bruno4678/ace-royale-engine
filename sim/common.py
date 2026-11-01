"""Small helpers shared by the simulations: output paths, charts, statistics."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "sim" / "results"
IMAGES = ROOT / "docs" / "img"


def save_json(name, data):
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def figure(name):
    """A matplotlib figure that `save()` writes to docs/img/<name>.png."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=120)
    fig.name = name
    return fig, ax


def save(fig):
    IMAGES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(IMAGES / f"{fig.name}.png")
    import matplotlib.pyplot as plt
    plt.close(fig)


def mean_ci(values, z=1.96):
    """Mean and the half-width of its 95% confidence interval."""
    import numpy as np
    values = np.asarray(values, dtype=float)
    return float(values.mean()), float(z * values.std(ddof=1) / math.sqrt(len(values)))


def pct(x, digits=2):
    return f"{100 * x:.{digits}f}%"
