"""Builds the showcase site into _site/, ready for GitHub Pages.

    python3 showcase/build.py            # then: python3 -m http.server -d _site

Copies the page and its assets, zips the `aceroyale` package and `bridge.py`
so Pyodide can import them in the browser, and copies the simulation results
the charts read.
Standard library only, so the Pages workflow needs nothing but Python.
"""

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOWCASE = ROOT / "showcase"
OUT = ROOT / "_site"

PAGE_FILES = ("index.html", "style.css", "app.js", "cards.js", "charts.js")
RESULTS = ("baccarat", "blackjack_shoe", "blackjack_strategy", "kelly",
           "kelly_rounds", "spins", "three_card")


def build(out=OUT):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in PAGE_FILES:
        shutil.copy2(SHOWCASE / name, out / name)
    shutil.copytree(SHOWCASE / "assets", out / "assets")

    with zipfile.ZipFile(out / "engine.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted((ROOT / "aceroyale").rglob("*.py")):
            z.write(path, path.relative_to(ROOT).as_posix())
        z.write(SHOWCASE / "bridge.py", "bridge.py")

    data = {}
    for name in RESULTS:
        data[name] = json.loads((ROOT / "sim" / "results" / f"{name}.json").read_text())
    (out / "results.json").write_text(json.dumps(data, separators=(",", ":")))

    (out / ".nojekyll").write_text("")
    return out


if __name__ == "__main__":
    print(f"built {build()}")
