from __future__ import annotations

import argparse
import subprocess
import tempfile
import venv
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from lifecycle import load_packages, meta_closure
from runtime_harness import entry_points_for_group, static_plugin_meta

ROOT = Path(__file__).resolve().parents[1]
MAIN_GROUP = "calibrated_explanations.plugins"
PLOT_BUILDER_GROUP = "calibrated_explanations.plugins.plot_builders"


def read_distribution_name(package_path: Path) -> str:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    name = data.get("project", {}).get("name")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"{package_path} is missing project.name")
    return name


def read_family(package_path: Path) -> str | None:
    with (package_path / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    family = data.get("tool", {}).get("ce_plugin_repo", {}).get("family")
    return family if isinstance(family, str) else None


def venv_python(venv_dir: Path) -> Path:
    candidate = venv_dir / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return venv_dir / "bin" / "python"


def package_plugin_paths(meta_package_path: Path) -> list[Path]:
    """Paths of the plugins curated by the metapackage (via family metas for the umbrella)."""
    distribution_name = read_distribution_name(meta_package_path)
    packages = load_packages(ROOT)
    meta = next(p for p in packages if p.name == distribution_name)
    return [p.path for p in meta_closure(packages, meta) if p.package_type == "plugin"]


def find_wheel(package_path: Path, artifact_dir: Path) -> Path:
    distribution = read_distribution_name(package_path).replace("-", "_")
    wheels = sorted(artifact_dir.glob(f"{distribution}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(
            f"Expected exactly one wheel for {package_path} in {artifact_dir}, found {len(wheels)}"
        )
    return wheels[0]


def create_virtualenv(venv_dir: Path) -> Path:
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(venv_dir)
    return venv_python(venv_dir)


def run_checked(command: list[str]) -> None:
    subprocess.check_call(command, cwd=ROOT)


def run_python_script(python_bin: Path, script: str) -> None:
    subprocess.check_call([str(python_bin), "-c", script], cwd=ROOT)


def module_has_spec(python_bin: Path, module: str) -> bool:
    result = subprocess.run(
        [
            str(python_bin),
            "-c",
            f"import importlib.util, sys; sys.exit(0 if importlib.util.find_spec({module!r}) else 1)",
        ],
        cwd=ROOT,
    )
    return result.returncode == 0


def assert_module_presence(python_bin: Path, module: str, *, expected: bool) -> None:
    present = module_has_spec(python_bin, module)
    if present != expected:
        wanted = "present" if expected else "absent"
        found = "present" if present else "absent"
        raise RuntimeError(
            f"Expected {module!r} to be {wanted} in the installed environment, found it {found}."
        )
    print(f"{module!r} presence check passed (expected {'present' if expected else 'absent'}).")


def visualization_style_ids(package_path: Path) -> tuple[str, list[str]]:
    """Statically resolve (bootstrap entry-point target, [plot style ids]) without importing."""
    main_entries = entry_points_for_group(package_path, MAIN_GROUP)
    if len(main_entries) != 1:
        raise RuntimeError(f"{package_path} must expose exactly one main plugin entry point")
    bootstrap_target = next(iter(main_entries.values()))
    style_ids = [
        str(static_plugin_meta(package_path, target)["style"])
        for target in entry_points_for_group(package_path, PLOT_BUILDER_GROUP).values()
    ]
    if not style_ids:
        raise RuntimeError(f"{package_path} declares no plot builder entry points")
    return bootstrap_target, style_ids


def assert_not_pretrusted_then_register(python_bin: Path, package_path: Path) -> None:
    """Prove installation alone never trusts/activates a visualization plugin.

    Before any explicit registration call, none of the plugin's styles may be
    registered and ``CE_TRUST_PLUGIN`` must be unset in the fresh interpreter.
    Only an explicit call to the bootstrap's public ``register()`` hook may add
    them — this is the documented, supported activation path.
    """
    bootstrap_target, style_ids = visualization_style_ids(package_path)
    module_name, _, attribute = bootstrap_target.partition(":")
    script = (
        "import os\n"
        "assert 'CE_TRUST_PLUGIN' not in os.environ, "
        "'CE_TRUST_PLUGIN must not be preset for this check'\n"
        "import importlib\n"
        "from calibrated_explanations.plugins.registry import find_plot_style_descriptor\n"
        f"style_ids = {style_ids!r}\n"
        "for style_id in style_ids:\n"
        "    assert find_plot_style_descriptor(style_id) is None, (\n"
        "        f'{style_id} was already registered by installation alone, before any '\n"
        "        'explicit trust/registration call')\n"
        f"bootstrap = getattr(importlib.import_module({module_name!r}), {attribute!r})\n"
        "assert bootstrap.plugin_meta['trusted'] is False, (\n"
        "    'bootstrap plugin_meta must declare trusted=False by default')\n"
        "bootstrap.register()\n"
        "for style_id in style_ids:\n"
        "    assert find_plot_style_descriptor(style_id) is not None, (\n"
        "        f'{style_id} did not register via the explicit, supported register() call')\n"
        "print('NOT_AUTO_TRUSTED_THEN_EXPLICITLY_REGISTERED_OK')\n"
    )
    run_python_script(python_bin, script)
    print(f"Not-auto-trusted + explicit registration check passed for {package_path.name}.")


_LIVE_DASHBOARD_SMOKE_SCRIPT = """
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from calibrated_explanations import CalibratedExplainer
from ce_visualization_plotly.dashboard import launch_instance_workspace
import dash

x, y = make_classification(
    n_samples=60, n_features=5, n_informative=3, n_redundant=0, random_state=0
)
x_train, x_test, y_train, y_test = train_test_split(
    x, y, test_size=0.3, random_state=0, stratify=y
)
learner = LogisticRegression(random_state=0, solver="liblinear").fit(x_train, y_train)
explainer = CalibratedExplainer(learner, x_train, y_train, mode="classification", seed=0)

app = launch_instance_workspace(
    explainer, x_test[:3], y=y_test[:3], run_server=False, open_browser=False
)
assert isinstance(app, dash.Dash), "launch_instance_workspace must return a real Dash app"
assert app.runs == [] if hasattr(app, "runs") else True
print("LIVE_DASHBOARD_CONSTRUCTION_OK")
"""


def assert_live_dashboard_constructs_without_server(python_bin: Path) -> None:
    """Minimal live-dashboard construction smoke test; never calls app.run()."""
    run_python_script(python_bin, _LIVE_DASHBOARD_SMOKE_SCRIPT)
    print("Live-dashboard construction smoke test passed (no server started).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate metapackage runtime coverage via local wheelhouse."
    )
    parser.add_argument("--package-path", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument(
        "--extra",
        default=None,
        help="Optional extra to install alongside the metapackage wheel, e.g. 'live'.",
    )
    args = parser.parse_args()

    package_path = Path(args.package_path).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    wheelhouse = Path(args.wheelhouse).resolve()
    package_wheel = find_wheel(package_path, artifact_dir)
    plugin_paths = package_plugin_paths(package_path)
    is_visualization_family = read_distribution_name(package_path) in {
        "calibrated-explanations-visualization",
        "calibrated-explanations-plugins",
    }

    with tempfile.TemporaryDirectory(prefix="ce-meta-runtime-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        python_bin = create_virtualenv(tmp_path / "venv")
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "calibrated-explanations[viz]",
            ]
        )
        wheel_spec = f"{package_wheel}[{args.extra}]" if args.extra else str(package_wheel)
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "--find-links",
                str(wheelhouse),
                wheel_spec,
            ]
        )
        run_checked([str(python_bin), "-m", "pip", "check"])

        if is_visualization_family:
            assert_module_presence(python_bin, "dash", expected=args.extra == "live")

        for plugin_path in plugin_paths:
            if read_family(plugin_path) == "visualization":
                assert_not_pretrusted_then_register(python_bin, plugin_path)

        for plugin_path in plugin_paths:
            run_checked(
                [
                    str(python_bin),
                    str(ROOT / "scripts" / "runtime_check_package.py"),
                    "--installed",
                    "--skip-pytest",
                    "--package-path",
                    str(plugin_path),
                ]
            )

        if is_visualization_family and args.extra == "live":
            assert_live_dashboard_constructs_without_server(python_bin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
