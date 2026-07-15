"""Resolve and gate a package-specific release tag.

A tag alone never authorizes publication. This script enforces the lifecycle
release policy before the workflow builds or publishes anything:

- individual plugins are releasable only with ``status = "mature"``;
- deprecated plugins are rejected unless the maintainer-controlled
  ``--allow-deprecated`` override is passed (exceptional security/migration
  releases only; the tag-push workflow never passes it);
- metapackage releases are rejected if curation invariants fail anywhere;
- the tag version must match ``project.version``;
- with ``--default-branch``, the released commit must be reachable from the
  protected default branch (no releases from unmerged commits).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from repo_packages import (  # noqa: E402
    ROOT,
    PackageRecord,
    find_record,
    load_package_records,
    validate_curation,
    validate_statuses,
)

TAG_PATTERN = re.compile(r"^pkg/(?P<distribution_name>[^/]+)/v(?P<version>\d+\.\d+\.\d+)$")


def parse_tag(tag: str) -> tuple[str, str]:
    match = TAG_PATTERN.match(tag)
    if match is None:
        raise SystemExit(
            "Release tag must match pkg/<distribution-name>/v<version>; " f"received {tag!r}."
        )
    return match.group("distribution_name"), match.group("version")


def resolve_package(
    records: list[PackageRecord],
    distribution_name: str,
    tag_version: str,
    *,
    allow_deprecated: bool = False,
    root: Path = ROOT,
) -> PackageRecord:
    """Resolve the tagged package and enforce lifecycle release policy."""
    package = find_record(records, distribution_name)
    if package is None:
        raise SystemExit(f"No package matches release tag distribution {distribution_name!r}.")

    if package.version != tag_version:
        raise SystemExit(
            f"Tag version {tag_version!r} does not match "
            f"{package.relative_path(root)} project.version {package.version!r}."
        )

    status_errors = validate_statuses(records)
    if status_errors:
        details = "\n".join(f"- {error}" for error in status_errors)
        raise SystemExit(
            "Release blocked: lifecycle metadata is invalid somewhere in the "
            f"repository. Fix these before releasing:\n{details}"
        )

    if package.package_type == "plugin":
        if package.status == "experimental":
            raise SystemExit(
                f"Release blocked: {distribution_name!r} has status 'experimental'. "
                "Experimental plugins are never published through the official "
                "workflow. Open a maturity-promotion PR (see "
                "docs/plugin-lifecycle.md) and merge it before tagging a release."
            )
        if package.status == "deprecated":
            if not allow_deprecated:
                raise SystemExit(
                    f"Release blocked: {distribution_name!r} has status 'deprecated'. "
                    "Deprecated plugins do not receive ordinary releases. An "
                    "exceptional security or migration release requires a "
                    "maintainer-approved manual workflow dispatch with the "
                    "deprecated-release override (see docs/plugin-lifecycle.md)."
                )
            print(
                f"WARNING: releasing deprecated package {distribution_name!r} via "
                "explicit maintainer override.",
                file=sys.stderr,
            )
        elif package.status != "mature":
            raise SystemExit(
                f"Release blocked: {distribution_name!r} has status "
                f"{package.status!r}; only mature plugins are releasable."
            )
    else:
        curation_errors = validate_curation(records)
        if curation_errors:
            details = "\n".join(f"- {error}" for error in curation_errors)
            raise SystemExit(
                f"Release blocked: metapackage {distribution_name!r} cannot be "
                f"released while curation invariants fail:\n{details}"
            )
    return package


def ensure_reachable_from(commit: str, branch_ref: str, *, cwd: Path = ROOT) -> None:
    """Require that ``commit`` is an ancestor of ``branch_ref``."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, branch_ref],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise SystemExit(
            f"Release blocked: commit {commit!r} is not reachable from "
            f"{branch_ref!r}. Releases must be cut from commits that were merged "
            "to the protected default branch through review; merge first, then "
            "re-tag the merged commit."
        )
    raise SystemExit(
        f"Could not verify that {commit!r} is reachable from {branch_ref!r}: "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )


def write_output_line(handle, key: str, value: str) -> None:
    handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a package-specific release tag.")
    parser.add_argument("--tag", default=os.getenv("GITHUB_REF_NAME", ""))
    parser.add_argument("--github-output")
    parser.add_argument(
        "--default-branch",
        help="Git ref the released commit must be reachable from (e.g. origin/main).",
    )
    parser.add_argument(
        "--commit",
        default="HEAD",
        help="Commit being released (default HEAD).",
    )
    parser.add_argument(
        "--allow-deprecated",
        action="store_true",
        help=(
            "Maintainer-controlled override for an exceptional security or "
            "migration release of a deprecated package. Never set on the "
            "ordinary tag-push path."
        ),
    )
    args = parser.parse_args()

    if not args.tag:
        raise SystemExit("Missing release tag. Pass --tag or set GITHUB_REF_NAME.")

    distribution_name, tag_version = parse_tag(args.tag)
    package = resolve_package(
        load_package_records(),
        distribution_name,
        tag_version,
        allow_deprecated=args.allow_deprecated,
    )
    if args.default_branch:
        ensure_reachable_from(args.commit, args.default_branch)

    outputs = {
        "distribution_name": distribution_name,
        "family": package.family,
        "package_path": package.relative_path(ROOT),
        "package_type": package.package_type,
        "status": package.status or "",
        "version": tag_version,
    }

    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as handle:
            for key, value in outputs.items():
                write_output_line(handle, key, value)
    else:
        for key, value in outputs.items():
            write_output_line(sys.stdout, key, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
