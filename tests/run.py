"""Run the whole test suite without pytest.

    python tests/run.py

Every ``test_*`` function in ``tests/test_*.py`` is a plain function that uses
``assert``, so pytest runs the same files unchanged (``pytest`` from the repo
root). This runner exists so the suite works with nothing but the standard
library.
"""

import importlib.util
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    failures = []
    total = 0
    start = time.perf_counter()
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        module = load(path)
        tests = [(name, fn) for name, fn in vars(module).items()
                 if name.startswith("test_") and callable(fn)]
        print(f"\n{path.name}")
        for name, fn in tests:
            total += 1
            try:
                fn()
                print(f"  ok      {name}")
            except Exception:
                print(f"  FAILED  {name}")
                failures.append((path.name, name, traceback.format_exc()))
    elapsed = time.perf_counter() - start

    for file, name, trace in failures:
        print(f"\n--- {file}::{name}\n{trace}")
    print(f"\n{total - len(failures)}/{total} passed in {elapsed:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
