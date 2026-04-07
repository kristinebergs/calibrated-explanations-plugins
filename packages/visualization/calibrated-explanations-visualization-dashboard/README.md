# calibrated-explanations-visualization-dashboard

Dashboard visualization plugin for [calibrated-explanations](https://github.com/Healthy-AI/calibrated-explanations).

Combines any number of registered plot plugins and a narrative text panel into a single
interactive [plotly](https://plotly.com/python/) figure.

## Installation

```bash
pip install calibrated-explanations-visualization-dashboard
# Optional: PNG export
pip install "calibrated-explanations-visualization-dashboard[png]"
```

## Usage

```python
import os
import calibrated_explanations.plugins.registry as registry

SHAP_STYLE    = "official.visualization.factual.shap"
DASHBOARD_STYLE = "official.visualization.dashboard"

os.environ["CE_TRUST_PLUGIN"] = ",".join([
    SHAP_STYLE,
    "official.visualization.factual.shap.builder",
    "official.visualization.factual.shap.renderer",
    DASHBOARD_STYLE,
    "official.visualization.dashboard.builder",
    "official.visualization.dashboard.renderer",
])
registry.load_entrypoint_plugins(include_untrusted=False)

# ... fit model and produce explanations ...

result = explanations.plot(
    style=DASHBOARD_STYLE,
    show=True,
    plots=[
        {"style": SHAP_STYLE, "shap_kind": "bar", "instance_index": 0},
        {"style": SHAP_STYLE, "shap_kind": "waterfall", "instance_index": 0},
    ],
    narrative=True,
    expertise_level="beginner",
    title="Explanation Dashboard",
)
result.figure   # interactive plotly figure
```

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `plots` | `list[dict]` | `[]` | Sub-plots to render. Each dict must have `"style"` (registered style ID); all other keys are forwarded to that plugin. |
| `narrative` | `bool` | `True` | Whether to append a narrative text panel. |
| `expertise_level` | `str` | `"beginner"` | Narrative level: `"beginner"`, `"intermediate"`, or `"advanced"`. |
| `title` | `str` | `None` | Dashboard title. |

### Sub-plot entry format

```python
{
    "style": "official.visualization.factual.shap",  # required
    "shap_kind": "waterfall",                         # forwarded to that plugin
    "shap_bound": "center",
    "instance_index": 0,
    # ... any other options the sub-plugin accepts
}
```

`show`, `path`, and `save_ext` are always overridden to `False`/`None` for sub-plots —
they are captured as images and embedded in the dashboard figure.

## Output

`result.figure` is a `plotly.graph_objects.Figure` that renders interactively in Jupyter
notebooks and can be saved as HTML:

```python
result = explanations.plot(
    style=DASHBOARD_STYLE,
    path="dashboard",
    save_ext=".html",
    plots=[...],
)
# Saves dashboard.html
```

PNG export requires [kaleido](https://github.com/plotly/Kaleido):
```bash
pip install kaleido
```

## Style ID

`official.visualization.dashboard`
