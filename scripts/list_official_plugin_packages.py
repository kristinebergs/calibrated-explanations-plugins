from __future__ import annotations

import argparse
import json
from pathlib import Path

from official_plugins import UMBRELLA_META_DISTRIBUTION, official_plugin_paths_for_meta_distribution

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List official plugin package directories derived from metapackage dependencies."
    )
    parser.add_argument("--metapackage", default=UMBRELLA_META_DISTRIBUTION)
    args = parser.parse_args()

    package_paths = official_plugin_paths_for_meta_distribution(args.metapackage)
    relative = [str(path.relative_to(ROOT)) for path in package_paths]
    print(json.dumps(relative))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
