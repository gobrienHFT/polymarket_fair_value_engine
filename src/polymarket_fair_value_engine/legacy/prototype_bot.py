"""Legacy wrapper for the original single-file prototype.

The original seed script remains at the repository root as `polymarket_bot.py`.
This wrapper keeps a legacy entrypoint inside the package layout without copying
secrets or mutating the user's existing prototype file.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    prototype_path = Path(__file__).resolve().parents[3] / "polymarket_bot.py"
    if not prototype_path.exists():
        raise FileNotFoundError(f"Legacy prototype not found at {prototype_path}")
    runpy.run_path(str(prototype_path), run_name="__main__")


if __name__ == "__main__":
    main()
