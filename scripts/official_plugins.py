"""Curated plugin resolution derived from metapackage dependencies.

Thin adapter over :mod:`repo_packages`. The curated (metapackage) plugin set is
the authoritative "recommended default installation" set; it may only contain
plugins whose lifecycle status is ``mature``.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import (  # noqa: E402
    FAMILY_META_DISTRIBUTIONS,
    PLUGIN_FAMILIES,
    ROOT,
    UMBRELLA_META_DISTRIBUTION,
    find_record,
    load_package_records,
    requirement_name,
)

__all__ = [
    "FAMILY_META_DISTRIBUTIONS",
    "PLUGIN_FAMILIES",
    "UMBRELLA_META_DISTRIBUTION",
    "official_plugin_paths_for_meta_distribution",
]


def official_plugin_paths_for_meta_distribution(
    meta_distribution: str, root: Path = ROOT
) -> list[Path]:
    """Return package paths for the plugins curated by ``meta_distribution``."""
    if meta_distribution == UMBRELLA_META_DISTRIBUTION:
        target_meta = [FAMILY_META_DISTRIBUTIONS[family] for family in PLUGIN_FAMILIES]
    elif meta_distribution in FAMILY_META_DISTRIBUTIONS.values():
        target_meta = [meta_distribution]
    else:
        raise RuntimeError(f"Unsupported metapackage distribution {meta_distribution!r}")

    records = load_package_records(root)
    selected: list[Path] = []
    for distribution_name in target_meta:
        meta = find_record(records, distribution_name)
        if meta is None:
            raise RuntimeError(f"Could not find metapackage directory for {distribution_name!r}")
        for dependency in meta.dependencies:
            dep_name = requirement_name(dependency)
            plugin = find_record(records, dep_name) if dep_name else None
            if plugin is None or plugin.package_type != "plugin":
                raise RuntimeError(
                    f"Metapackage {distribution_name!r} depends on unknown plugin "
                    f"distribution {dep_name or dependency!r}"
                )
            selected.append(plugin.path)

    return sorted({path.resolve() for path in selected})
