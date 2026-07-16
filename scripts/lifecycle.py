"""Lifecycle policy for the plugin monorepo, as one command.

Lifecycle state lives in exactly two places: each plugin's
``[tool.ce_plugin_repo] status`` (experimental/mature/deprecated) and each
family metapackage's dependency list (the curated set). Subcommands: ``check``
(statuses, family placement, curation), ``list`` (package paths as JSON),
``index`` (generate/verify docs/package-index.md), and ``release`` (gate a
``pkg/<distribution>/v<version>`` tag; prints ``key=value`` output lines).

Structural and plugin-contract checks (entry points, plugin_meta, READMEs)
live in ``scripts/validate_repo_structure.py``, not here. Runtime trust
(``plugin_meta["trusted"]``) is a separate concept and is never read here.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    from packaging.requirements import InvalidRequirement, Requirement
except ModuleNotFoundError:  # pragma: no cover
    Requirement = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FAMILIES = ("calibration", "explanation", "visualization")
ALLOWED_STATUSES = ("experimental", "mature", "deprecated")
FAMILY_META = {
    "calibration": "calibrated-explanations-calibration",
    "explanation": "calibrated-explanations-explanation",
    "visualization": "calibrated-explanations-visualization",
}
UMBRELLA = "calibrated-explanations-plugins"
TAG_PATTERN = re.compile(r"^pkg/(?P<name>[^/]+)/v(?P<version>\d+\.\d+\.\d+)$")
INDEX_PATH = "docs/package-index.md"


@dataclass(frozen=True)
class Package:
    """One package under ``packages/<family>/<distribution>/``."""

    path: Path
    name: str
    version: str
    package_type: str  # "plugin" or "meta"
    directory_family: str
    family: str | None
    status: str | None
    dependencies: tuple[str, ...]
    maintainers: tuple[str, ...]
    has_license: bool
    curated_in: tuple[str, ...]

    def rel(self, root: Path) -> str:
        return self.path.relative_to(root).as_posix()


def requirement_name(dependency: str) -> str | None:
    """Distribution name of a PEP 508 dependency string, or None."""
    if Requirement is None:  # pragma: no cover
        match = re.match(r"^[A-Za-z0-9_.-]+", dependency.strip())
        return match.group(0) if match else None
    try:
        return Requirement(dependency).name
    except InvalidRequirement:
        return None


def load_packages(root: Path = ROOT, errors: list[str] | None = None) -> list[Package]:
    """Discover packages from ``packages/*/*/pyproject.toml``.

    Malformed packages are appended to ``errors`` (or raised) and skipped.
    """
    packages: list[Package] = []
    for pyproject in sorted((root / "packages").glob("*/*/pyproject.toml")):
        rel = pyproject.relative_to(root).as_posix()
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        project = data.get("project", {})
        tool = data.get("tool", {}).get("ce_plugin_repo", {})
        if not isinstance(tool, dict):
            tool = {}
        name, version = project.get("name"), project.get("version")
        if not isinstance(name, str) or not isinstance(version, str) or not name or not version:
            message = f"{rel} is missing project.name or project.version"
            if errors is None:
                raise RuntimeError(message)
            errors.append(message)
            continue
        directory_family = pyproject.parent.parent.name
        packages.append(
            Package(
                path=pyproject.parent,
                name=name,
                version=version,
                package_type="meta" if directory_family == "meta" else "plugin",
                directory_family=directory_family,
                family=tool.get("family") if isinstance(tool.get("family"), str) else None,
                status=tool.get("status") if isinstance(tool.get("status"), str) else None,
                dependencies=tuple(
                    dep for dep in project.get("dependencies", []) if isinstance(dep, str)
                ),
                maintainers=tuple(
                    str(entry.get("name", ""))
                    for entry in project.get("maintainers", [])
                    if isinstance(entry, dict) and entry.get("name")
                ),
                has_license=bool(project.get("license") or project.get("license-files")),
                curated_in=(),
            )
        )
    curated: dict[str, list[str]] = {}
    for package in packages:
        if package.package_type == "meta" and package.name != UMBRELLA:
            for dep in package.dependencies:
                dep_name = requirement_name(dep)
                if dep_name:
                    curated.setdefault(dep_name, []).append(package.name)
    return [
        Package(**{**p.__dict__, "curated_in": tuple(sorted(curated.get(p.name, ())))})
        for p in packages
    ]


def validate(packages: list[Package]) -> list[str]:
    """All lifecycle policy errors: statuses, family placement, curation."""
    errors: list[str] = []
    index: dict[str, Package] = {}
    for package in packages:
        if package.name in index:
            errors.append(f"Duplicate distribution name {package.name!r}.")
        index[package.name] = package

    for p in packages:
        rel = p.path.name
        if p.package_type == "plugin":
            if p.status not in ALLOWED_STATUSES:
                errors.append(
                    f"{rel} must declare [tool.ce_plugin_repo] status as one of "
                    f"{', '.join(ALLOWED_STATUSES)} (found {p.status!r})."
                )
            if p.family != p.directory_family:
                errors.append(
                    f"{rel} declares family {p.family!r} but lives in "
                    f"packages/{p.directory_family}/; family must match its directory."
                )
            if p.status == "mature" and not p.maintainers:
                errors.append(f"{rel} is mature but declares no project.maintainers.")
            if p.status == "mature" and not p.has_license:
                errors.append(f"{rel} is mature but declares no licence metadata.")
        else:
            if p.status is not None:
                errors.append(
                    f"{rel} is a metapackage and must not declare a status; its "
                    "content is governed by curation of mature plugins."
                )
            if p.family != "meta":
                errors.append(f"{rel} must declare family = 'meta'.")

    for family, meta_name in FAMILY_META.items():
        meta = index.get(meta_name)
        if meta is None:
            errors.append(f"Missing family metapackage {meta_name!r} under packages/meta.")
            continue
        for dep in meta.dependencies:
            dep_name = requirement_name(dep)
            plugin = index.get(dep_name) if dep_name else None
            if plugin is None or plugin.package_type != "plugin":
                errors.append(
                    f"{meta_name!r} depends on {dep_name or dep!r}, which is not a "
                    "plugin package in this repository."
                )
            elif plugin.family != family:
                errors.append(
                    f"{meta_name!r} curates {dep_name!r} from the {plugin.family!r} "
                    "family; family metapackages may only curate their own family."
                )
            elif plugin.status != "mature":
                errors.append(
                    f"{meta_name!r} curates {dep_name!r}, whose status is "
                    f"{plugin.status!r}; only mature plugins may enter a metapackage."
                )
    umbrella = index.get(UMBRELLA)
    if umbrella is None:
        errors.append(f"Missing umbrella metapackage {UMBRELLA!r} under packages/meta.")
    else:
        actual = sorted(filter(None, (requirement_name(dep) for dep in umbrella.dependencies)))
        if actual != sorted(FAMILY_META.values()):
            errors.append(
                f"{UMBRELLA!r} must depend on exactly the family metapackages "
                f"{sorted(FAMILY_META.values())}, found {actual}."
            )
    return errors


def meta_closure(packages: list[Package], meta: Package) -> list[Package]:
    """The metapackage plus every package needed to build and test it:
    the family metapackages (umbrella only) and their curated mature plugins."""
    index = {p.name: p for p in packages}
    metas = [meta]
    if meta.name == UMBRELLA:
        metas += [index[name] for name in FAMILY_META.values() if name in index]
    closure = list(metas)
    for m in metas:
        for dep in m.dependencies:
            plugin = index.get(requirement_name(dep) or "")
            if plugin is not None and plugin.package_type == "plugin":
                closure.append(plugin)
    seen: set[str] = set()
    return [p for p in closure if not (p.name in seen or seen.add(p.name))]


def render_index(packages: list[Package], root: Path = ROOT) -> str:
    plugins = [p for p in packages if p.package_type == "plugin"]
    line = lambda p: f"- `{p.name}` {p.version} — `{p.rel(root)}`"  # noqa: E731
    sections = [
        (
            "Metapackages",
            "Curated PyPI products; family metapackages contain only mature plugins.",
            [f"- `{p.name}` {p.version}" for p in packages if p.package_type == "meta"],
        ),
        (
            "Mature curated plugins",
            "In a family metapackage; installable individually from PyPI once released.",
            [f"{line(p)} (in `{'`, `'.join(p.curated_in)}`)" for p in plugins
             if p.status == "mature" and p.curated_in],
        ),
        (
            "Mature standalone plugins",
            "Releasable to PyPI individually; not part of a metapackage.",
            [line(p) for p in plugins if p.status == "mature" and not p.curated_in],
        ),
        (
            "Experimental plugins",
            "Not published to PyPI; install from a repository checkout.",
            [line(p) for p in plugins if p.status == "experimental"],
        ),
        (
            "Deprecated plugins",
            "No longer recommended; see each README for migration guidance.",
            [line(p) for p in plugins if p.status == "deprecated"],
        ),
    ]
    out = [
        "# Package index",
        "",
        "<!-- Generated by `python scripts/lifecycle.py index`; do not edit by hand. -->",
        "",
        "Status semantics and the promotion process: `docs/plugin-lifecycle.md`.",
    ]
    for heading, blurb, entries in sections:
        out += ["", f"## {heading}", "", blurb, ""]
        out += sorted(entries) if entries else ["- None."]
    return "\n".join(out) + "\n"


def gate_release(packages: list[Package], tag: str, root: Path = ROOT) -> Package:
    """Resolve a release tag and enforce release policy; SystemExit on refusal."""
    match = TAG_PATTERN.match(tag)
    if match is None:
        raise SystemExit(f"Release tag must match pkg/<distribution>/v<X.Y.Z>; got {tag!r}.")
    name, version = match.group("name"), match.group("version")
    package = next((p for p in packages if p.name == name), None)
    if package is None:
        raise SystemExit(f"No package in this repository is named {name!r}.")
    if package.version != version:
        raise SystemExit(
            f"Tag version {version!r} does not match {package.rel(root)} "
            f"project.version {package.version!r}."
        )
    errors = validate(packages)
    if package.package_type == "plugin" and package.status != "mature":
        errors.append(
            f"{name!r} has status {package.status!r}; only mature plugins are "
            "released. Promote via a maturity-promotion PR first."
        )
    if package.package_type == "meta":
        checked = [package] if package.name != UMBRELLA else [
            p for p in packages if p.name in FAMILY_META.values()
        ]
        for meta in checked:
            if not meta.dependencies:
                errors.append(
                    f"{meta.name!r} is empty; empty metapackages are valid in the "
                    "repository but are not release products."
                )
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(f"Release blocked:\n{details}")
    return package


def ensure_reachable(commit: str, branch_ref: str, cwd: Path = ROOT) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, branch_ref],
        cwd=cwd, capture_output=True, text=True,
    )
    if result.returncode == 1:
        raise SystemExit(
            f"Release blocked: commit {commit!r} is not reachable from {branch_ref!r}; "
            "merge to the default branch through review, then tag the merged commit."
        )
    if result.returncode != 0:
        raise SystemExit(f"Could not verify ancestry: {result.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--type", choices=("plugin", "meta"))
    list_parser.add_argument("--status", choices=ALLOWED_STATUSES)
    list_parser.add_argument("--curated", action="store_true")
    index_parser = sub.add_parser("index")
    index_parser.add_argument("--check", action="store_true")
    release_parser = sub.add_parser("release")
    release_parser.add_argument("--tag", required=True)
    release_parser.add_argument("--default-branch")
    args = parser.parse_args(argv)

    if args.command == "check":
        errors: list[str] = []
        errors += validate(load_packages(ROOT, errors))
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if errors:
            return 1
        print("Lifecycle check passed.")
        return 0

    packages = load_packages()
    if args.command == "list":
        selected = [
            p.rel(ROOT)
            for p in packages
            if (not args.type or p.package_type == args.type)
            and (not args.status or p.status == args.status)
            and (not args.curated or p.curated_in)
        ]
        print(json.dumps(sorted(selected)))
    elif args.command == "index":
        content = render_index(packages)
        index_path = ROOT / INDEX_PATH
        if args.check:
            existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
            if existing != content:
                print(
                    f"ERROR: {INDEX_PATH} is stale; run `python scripts/lifecycle.py "
                    "index` and commit the result.",
                    file=sys.stderr,
                )
                return 1
            print("Package index is up to date.")
        else:
            index_path.write_text(content, encoding="utf-8")
            print(f"Wrote {INDEX_PATH}")
    elif args.command == "release":
        package = gate_release(packages, args.tag)
        if args.default_branch:
            ensure_reachable("HEAD", args.default_branch)
        build_paths = (
            [p.rel(ROOT) for p in meta_closure(packages, package)]
            if package.package_type == "meta"
            else [package.rel(ROOT)]
        )
        print(f"distribution_name={package.name}")
        print(f"package_path={package.rel(ROOT)}")
        print(f"package_type={package.package_type}")
        print(f"version={package.version}")
        print(f"build_paths={json.dumps(build_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
