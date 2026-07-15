"""Shared package discovery and lifecycle policy for the plugin monorepo.

This module is the single programmatic source of truth for:

- discovering package records from ``packages/*/*/pyproject.toml``;
- the allowed lifecycle statuses (``experimental``, ``mature``, ``deprecated``);
- which plugins are curated (referenced by a family metapackage);
- the metapackage curation invariants.

Lifecycle status is declared per package in ``[tool.ce_plugin_repo] status``.
Runtime trust metadata (``plugin_meta["trusted"]``, ``CE_TRUST_PLUGIN``) is a
separate concept and is deliberately not read here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.specifiers import InvalidSpecifier, SpecifierSet

    HAVE_PACKAGING = True
except ModuleNotFoundError:  # pragma: no cover
    HAVE_PACKAGING = False

ROOT = Path(__file__).resolve().parents[1]

PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
META_FAMILY = "meta"
ALLOWED_STATUSES = ("experimental", "mature", "deprecated")
RELEASABLE_STATUSES = ("mature",)

FAMILY_META_DISTRIBUTIONS = {
    "calibration": "calibrated-explanations-calibration",
    "explanation": "calibrated-explanations-explanation",
    "visualization": "calibrated-explanations-visualization",
}
UMBRELLA_META_DISTRIBUTION = "calibrated-explanations-plugins"

# CPython minor versions sampled when checking that a curated plugin does not
# contradict its metapackage's advertised requires-python range. Sampling minor
# versions is reliable for the ``>=X.Y``-style ranges used in this repository;
# exotic specifiers still need human review during curation.
PYTHON_VERSION_SAMPLES = ("3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.14")

_NAME_FALLBACK_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class PackageRecord:
    """One package under ``packages/<family>/<distribution>/``."""

    path: Path
    distribution_name: str
    version: str
    package_type: str  # "plugin" or "meta"
    family: str
    status: str | None
    import_name: str | None
    requires_python: str | None
    ce_requirement: str | None
    dependencies: tuple[str, ...]
    maintainers: tuple[str, ...]
    metapackage_memberships: tuple[str, ...]

    @property
    def in_metapackage(self) -> bool:
        return bool(self.metapackage_memberships)

    def relative_path(self, root: Path) -> str:
        return self.path.relative_to(root).as_posix()


class RepoMetadataError(RuntimeError):
    """Raised when package metadata cannot be interpreted."""


def requirement_name(dependency: str) -> str | None:
    """Return the distribution name of a PEP 508 dependency string."""
    dependency = dependency.strip()
    if not dependency:
        return None
    if HAVE_PACKAGING:
        try:
            return Requirement(dependency).name
        except InvalidRequirement:
            return None
    match = _NAME_FALLBACK_PATTERN.match(dependency)  # pragma: no cover
    return match.group(0) if match else None  # pragma: no cover


def load_package_records(
    root: Path = ROOT, errors: list[str] | None = None
) -> list[PackageRecord]:
    """Discover all package records under ``root/packages``.

    When ``errors`` is provided, malformed packages are reported there and
    skipped; otherwise a :class:`RepoMetadataError` is raised.
    """

    def report(message: str) -> None:
        if errors is None:
            raise RepoMetadataError(message)
        errors.append(message)

    packages_dir = root / "packages"
    raw_records: list[PackageRecord] = []
    for pyproject_path in sorted(packages_dir.glob("*/*/pyproject.toml")):
        rel = pyproject_path.relative_to(root).as_posix()
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
        project = data.get("project", {})
        tool_cfg = data.get("tool", {}).get("ce_plugin_repo", {})
        if not isinstance(tool_cfg, dict):
            tool_cfg = {}
        name = project.get("name")
        version = project.get("version")
        if not isinstance(name, str) or not name:
            report(f"{rel} is missing project.name")
            continue
        if not isinstance(version, str) or not version:
            report(f"{rel} is missing project.version")
            continue
        directory_family = pyproject_path.parent.parent.name
        family = tool_cfg.get("family")
        if not isinstance(family, str):
            family = directory_family
        dependencies = tuple(
            dep for dep in project.get("dependencies", []) if isinstance(dep, str)
        )
        ce_requirement = next(
            (
                dep
                for dep in dependencies
                if requirement_name(dep) == "calibrated-explanations"
            ),
            None,
        )
        status = tool_cfg.get("status")
        if not isinstance(status, str):
            status = None
        import_name = tool_cfg.get("import_name")
        if not isinstance(import_name, str):
            import_name = None
        requires_python = project.get("requires-python")
        if not isinstance(requires_python, str):
            requires_python = None
        maintainers = tuple(
            str(entry.get("name", ""))
            for entry in project.get("maintainers", [])
            if isinstance(entry, dict)
        )
        raw_records.append(
            PackageRecord(
                path=pyproject_path.parent,
                distribution_name=name,
                version=version,
                package_type="meta" if directory_family == META_FAMILY else "plugin",
                family=family,
                status=status,
                import_name=import_name,
                requires_python=requires_python,
                ce_requirement=ce_requirement,
                dependencies=dependencies,
                maintainers=maintainers,
                metapackage_memberships=(),
            )
        )

    memberships: dict[str, list[str]] = {}
    for record in raw_records:
        if record.package_type != "meta":
            continue
        if record.distribution_name == UMBRELLA_META_DISTRIBUTION:
            continue
        for dependency in record.dependencies:
            dep_name = requirement_name(dependency)
            if dep_name:
                memberships.setdefault(dep_name, []).append(record.distribution_name)

    records: list[PackageRecord] = []
    for record in raw_records:
        membership = tuple(sorted(memberships.get(record.distribution_name, ())))
        if membership:
            record = PackageRecord(
                **{**record.__dict__, "metapackage_memberships": membership}
            )
        records.append(record)
    return records


def records_by_distribution(records: list[PackageRecord]) -> dict[str, PackageRecord]:
    index: dict[str, PackageRecord] = {}
    for record in records:
        previous = index.get(record.distribution_name)
        if previous is not None:
            raise RepoMetadataError(
                f"Duplicate distribution name {record.distribution_name!r} in "
                f"{previous.path} and {record.path}"
            )
        index[record.distribution_name] = record
    return index


def find_record(
    records: list[PackageRecord], distribution_name: str
) -> PackageRecord | None:
    for record in records:
        if record.distribution_name == distribution_name:
            return record
    return None


def curated_distributions(records: list[PackageRecord]) -> dict[str, list[str]]:
    """Map each family to the plugin distributions its metapackage curates."""
    curated: dict[str, list[str]] = {family: [] for family in PLUGIN_FAMILIES}
    for family, meta_name in FAMILY_META_DISTRIBUTIONS.items():
        meta = find_record(records, meta_name)
        if meta is None:
            continue
        for dependency in meta.dependencies:
            dep_name = requirement_name(dependency)
            if dep_name:
                curated[family].append(dep_name)
    return curated


def _python_range_conflicts(
    meta: PackageRecord, plugin: PackageRecord
) -> list[str]:
    """Sampled requires-python compatibility check via ``packaging``."""
    if not HAVE_PACKAGING:  # pragma: no cover
        return []
    if not meta.requires_python or not plugin.requires_python:
        return []
    try:
        meta_range = SpecifierSet(meta.requires_python)
        plugin_range = SpecifierSet(plugin.requires_python)
    except InvalidSpecifier:
        return [
            f"{meta.distribution_name!r} or {plugin.distribution_name!r} declares an "
            "unparseable requires-python range; fix the specifier."
        ]
    unsupported = [
        sample
        for sample in PYTHON_VERSION_SAMPLES
        if meta_range.contains(sample) and not plugin_range.contains(sample)
    ]
    if unsupported:
        return [
            f"Metapackage {meta.distribution_name!r} advertises requires-python "
            f"{meta.requires_python!r} but curated plugin {plugin.distribution_name!r} "
            f"requires {plugin.requires_python!r}, excluding Python "
            f"{', '.join(unsupported)}. Narrow the metapackage range or drop the plugin."
        ]
    return []


def validate_curation(records: list[PackageRecord]) -> list[str]:
    """Enforce the metapackage curation invariants.

    1. Family metapackages depend only on known plugins of their own family.
    2. Only ``mature`` plugins may be curated; ``experimental`` and
       ``deprecated`` plugins are rejected with the governance action required.
    3. The umbrella metapackage depends on exactly the family metapackages.
    4. Curated plugins must not contradict the metapackage requires-python range.
    """
    errors: list[str] = []
    index = {record.distribution_name: record for record in records}

    for family, meta_name in FAMILY_META_DISTRIBUTIONS.items():
        meta = index.get(meta_name)
        if meta is None:
            errors.append(f"Missing family metapackage {meta_name!r} under packages/meta.")
            continue
        for dependency in meta.dependencies:
            dep_name = requirement_name(dependency)
            if dep_name is None:
                errors.append(
                    f"{meta_name!r} has unparseable dependency {dependency!r}."
                )
                continue
            plugin = index.get(dep_name)
            if plugin is None or plugin.package_type != "plugin":
                errors.append(
                    f"{meta_name!r} depends on {dep_name!r}, which is not a plugin "
                    "package in this repository. Metapackages may only curate "
                    "repository plugins."
                )
                continue
            if plugin.family != family:
                errors.append(
                    f"{meta_name!r} depends on {dep_name!r}, but that plugin belongs "
                    f"to the {plugin.family!r} family. Family metapackages may only "
                    "curate plugins from their own family."
                )
            if plugin.status != "mature":
                errors.append(
                    f"{meta_name!r} depends on {dep_name!r}, whose status is "
                    f"{plugin.status!r}. Only 'mature' plugins may enter a "
                    "metapackage; promote the plugin through a maturity-review PR "
                    "first (or remove the dependency)."
                )
            errors.extend(_python_range_conflicts(meta, plugin))

    umbrella = index.get(UMBRELLA_META_DISTRIBUTION)
    expected_umbrella = sorted(FAMILY_META_DISTRIBUTIONS.values())
    if umbrella is None:
        errors.append(
            f"Missing umbrella metapackage {UMBRELLA_META_DISTRIBUTION!r} under packages/meta."
        )
    else:
        actual = sorted(
            name
            for name in (requirement_name(dep) for dep in umbrella.dependencies)
            if name is not None
        )
        if actual != expected_umbrella:
            errors.append(
                f"{UMBRELLA_META_DISTRIBUTION!r} must depend on exactly the family "
                f"metapackages {expected_umbrella}, found {actual}."
            )
    return errors


def validate_statuses(records: list[PackageRecord]) -> list[str]:
    """Enforce lifecycle status declarations.

    Every plugin package must declare exactly one allowed status. Metapackages
    must not declare a status: their contents are derived from curation, not
    from an own lifecycle state.
    """
    errors: list[str] = []
    for record in records:
        rel = record.path.name
        if record.package_type == "plugin":
            if record.status is None:
                errors.append(
                    f"{rel} is missing [tool.ce_plugin_repo] status. Declare "
                    f"status = \"experimental\" (new plugins), \"mature\", or "
                    f"\"deprecated\"."
                )
            elif record.status not in ALLOWED_STATUSES:
                errors.append(
                    f"{rel} declares unknown status {record.status!r}. Allowed "
                    f"statuses: {', '.join(ALLOWED_STATUSES)}."
                )
        else:
            if record.status is not None:
                errors.append(
                    f"{rel} is a metapackage and must not declare a lifecycle "
                    "status; metapackage content is governed by curation of "
                    "mature plugins."
                )
    return errors
