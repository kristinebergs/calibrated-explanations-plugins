from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = ROOT / "packages"
TAG_PATTERN = re.compile(r"^pkg/(?P<distribution_name>[^/]+)/v(?P<version>\d+\.\d+\.\d+)$")


@dataclass(frozen=True)
class PackageRecord:
    root: Path
    family: str
    distribution_name: str
    version: str

    @property
    def package_type(self) -> str:
        return "meta" if self.family == "meta" else "plugin"


def load_package_records() -> list[PackageRecord]:
    records: list[PackageRecord] = []
    for pyproject_path in sorted(PACKAGES_DIR.glob("*/*/pyproject.toml")):
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
        project = data.get("project", {})
        tool_cfg = data.get("tool", {}).get("ce_plugin_repo", {})
        distribution_name = project.get("name")
        version = project.get("version")
        family = tool_cfg.get("family")
        if not isinstance(distribution_name, str) or not isinstance(version, str):
            raise SystemExit(f"Invalid package metadata in {pyproject_path.relative_to(ROOT)}")
        if not isinstance(family, str):
            raise SystemExit(
                f"Missing tool.ce_plugin_repo.family in {pyproject_path.relative_to(ROOT)}"
            )
        records.append(
            PackageRecord(
                root=pyproject_path.parent,
                family=family,
                distribution_name=distribution_name,
                version=version,
            )
        )
    return records


def parse_tag(tag: str) -> tuple[str, str]:
    match = TAG_PATTERN.match(tag)
    if match is None:
        raise SystemExit(
            "Release tag must match pkg/<distribution-name>/v<version>; " f"received {tag!r}."
        )
    return match.group("distribution_name"), match.group("version")


def resolve_package(records: list[PackageRecord], distribution_name: str) -> PackageRecord:
    matches = [record for record in records if record.distribution_name == distribution_name]
    if not matches:
        raise SystemExit(f"No package matches release tag distribution {distribution_name!r}.")
    if len(matches) > 1:
        paths = ", ".join(record.root.relative_to(ROOT).as_posix() for record in matches)
        raise SystemExit(
            f"Release tag distribution {distribution_name!r} is ambiguous across: {paths}."
        )
    return matches[0]


def write_output_line(handle, key: str, value: str) -> None:
    handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a package-specific release tag.")
    parser.add_argument("--tag", default=os.getenv("GITHUB_REF_NAME", ""))
    parser.add_argument("--github-output")
    args = parser.parse_args()

    if not args.tag:
        raise SystemExit("Missing release tag. Pass --tag or set GITHUB_REF_NAME.")

    distribution_name, tag_version = parse_tag(args.tag)
    package = resolve_package(load_package_records(), distribution_name)
    if package.version != tag_version:
        raise SystemExit(
            f"Tag version {tag_version!r} does not match {package.root.relative_to(ROOT).as_posix()} "
            f"project.version {package.version!r}."
        )

    outputs = {
        "distribution_name": distribution_name,
        "family": package.family,
        "package_path": package.root.relative_to(ROOT).as_posix(),
        "package_type": package.package_type,
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
