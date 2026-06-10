"""Dashboard layout utilities: panel capture, narrative, and plotly assembly."""

from __future__ import annotations

import base64
import html as _html_module
import io
import math
import re
from typing import Any


def _text_to_plotly(text: str) -> str:
    """Prepare plain narrative text for a plotly annotation.

    Escapes HTML-special characters (so feature conditions like ``feature > 3``
    render correctly), then converts newlines to ``<br>`` which plotly
    annotations render as actual line breaks.
    """
    escaped = _html_module.escape(text)
    # Normalise line endings, then convert to plotly <br>
    escaped = re.sub(r"\r?\n", "<br>", escaped)
    # Collapse 3+ consecutive <br> to 2 to avoid excessive whitespace
    escaped = re.sub(r"(<br>){3,}", "<br><br>", escaped)
    return escaped


def figure_to_png_bytes(figure: Any) -> bytes:
    """Convert a matplotlib or plotly figure to PNG bytes."""
    if hasattr(figure, "savefig"):
        buf = io.BytesIO()
        figure.savefig(buf, format="png", bbox_inches="tight")
        import matplotlib.pyplot as plt

        plt.close(figure)
        buf.seek(0)
        return buf.getvalue()

    if hasattr(figure, "to_image"):
        return figure.to_image(format="png")  # type: ignore[return-value]  # requires kaleido

    raise TypeError(f"Cannot convert figure of type {type(figure).__name__!r} to PNG.")


def error_placeholder_bytes(message: str) -> bytes:
    """Render a small placeholder image containing the given error message."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 1.2))
    ax.axis("off")
    ax.text(
        0.5,
        0.5,
        f"Panel error: {message}",
        ha="center",
        va="center",
        fontsize=8,
        color="red",
        wrap=True,
        transform=ax.transAxes,
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_narrative_panel(explanation: Any, expertise_level: str) -> str:
    """Generate narrative text for *explanation*.

    Works for both a single explanation instance and a collection:
    pass the right object in — the caller is responsible for slicing.
    """
    try:
        result = explanation.to_narrative(expertise_level=expertise_level, output_format="text")
        return result if isinstance(result, str) else str(result)
    except Exception as exc:  # noqa: BLE001
        return f"Narrative unavailable: {exc}"


def _narrative_html(narrative: str | list[str]) -> str:
    """Build narrative HTML for one or multiple instance narratives."""
    if isinstance(narrative, str):
        return _text_to_plotly(narrative)

    blocks = []
    for idx, item in enumerate(narrative):
        blocks.append(
            (
                "<div style='margin-bottom:10px;'>"
                f"<b>Instance {idx + 1}</b><br>"
                f"{_text_to_plotly(item)}"
                "</div>"
            )
        )
    blocks_html = "".join(blocks)
    return (
        "<div style='max-height:260px; overflow-y:auto; "
        "border:1px solid lightgrey; padding:8px; background:white;'>"
        f"{blocks_html}"
        "</div>"
    )


def assemble_dashboard(
    panel_bytes: list[bytes],
    narrative_text: str | list[str] | None,
    title: str | None,
) -> Any:
    """Assemble a plotly Figure from a list of PNG panel bytes and optional narrative HTML.

    The narrative is embedded as an HTML annotation below the plot area so that
    HTML formatting from ``to_narrative(output_format="html")`` renders correctly.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    has_narrative = narrative_text is not None
    has_multi_narrative = isinstance(narrative_text, list) and len(narrative_text) > 1
    n_panels = len(panel_bytes)

    # --- determine grid layout (narrative never occupies a subplot row) ---
    if n_panels == 0 and not has_narrative:
        fig = go.Figure()
        fig.update_layout(
            title_text=title or "Calibrated Explanation Dashboard",
            height=300,
            paper_bgcolor="white",
        )
        return fig

    if n_panels == 0:
        # Narrative only — empty figure with no subplots; annotation added below
        fig = go.Figure()
        n_rows = 0
    else:
        n_cols = min(2, n_panels)
        n_rows = math.ceil(n_panels / n_cols)
        specs = _image_grid_specs(n_panels, n_rows, n_cols)
        subplot_titles = [f"Plot {i + 1}" for i in range(n_panels)]
        total_cells = n_rows * n_cols
        subplot_titles += [""] * (total_cells - n_panels)

        fig = make_subplots(
            rows=n_rows,
            cols=n_cols,
            specs=specs,
            subplot_titles=subplot_titles,
            vertical_spacing=0.06,
            horizontal_spacing=0.04,
        )

        # --- add image panels ---
        for idx, png_bytes in enumerate(panel_bytes):
            row = idx // n_cols + 1
            col = idx % n_cols + 1
            b64 = base64.b64encode(png_bytes).decode()
            fig.add_trace(
                go.Image(source=f"data:image/png;base64,{b64}"),
                row=row,
                col=col,
            )

        # Remove axes from image subplots
        for idx in range(n_panels):
            row = idx // n_cols + 1
            col = idx % n_cols + 1
            axis_suffix = "" if (row == 1 and col == 1) else str(idx + 1)
            fig.update_layout(
                **{
                    f"xaxis{axis_suffix}": {"visible": False},
                    f"yaxis{axis_suffix}": {"visible": False},
                }
            )

    # --- narrative annotation (always yref="paper") ---
    # Narrative-only: annotations sit at the top of the paper domain (y≈1.0) with
    # no plot area beneath them.  When panels are present the annotations go below
    # the plot area (y < 0) and are revealed by the bottom margin.
    narrative_height = 0
    if has_narrative:
        narrative_height = 420 if has_multi_narrative else 320
        narrative_heading = "<b>Explanations</b>" if has_multi_narrative else "<b>Explanation</b>"
        narrative_body = _narrative_html(narrative_text)
        if n_panels == 0:
            # Hide the empty default axes so only the annotation is visible
            fig.update_layout(
                xaxis={"visible": False, "fixedrange": True},
                yaxis={"visible": False, "fixedrange": True},
            )
            fig.add_annotation(
                text=narrative_heading,
                xref="paper",
                yref="paper",
                x=0.0,
                y=1.0,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font={"size": 13},
                align="left",
            )
            fig.add_annotation(
                text=narrative_body,
                xref="paper",
                yref="paper",
                x=0.0,
                y=0.93,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font={"size": 11, "family": "monospace"},
                align="left",
                bgcolor="white",
                bordercolor="lightgrey",
                borderwidth=1,
                borderpad=8,
            )
        else:
            fig.add_annotation(
                text=narrative_heading,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.05,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font={"size": 13},
                align="left",
            )
            fig.add_annotation(
                text=narrative_body,
                xref="paper",
                yref="paper",
                x=0.0,
                y=-0.10,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font={"size": 11, "family": "monospace"},
                align="left",
                bgcolor="white",
                bordercolor="lightgrey",
                borderwidth=1,
                borderpad=8,
            )

    # --- overall layout ---
    plot_height = 480 * n_rows  # 0 when there are no panels
    total_height = max(narrative_height, plot_height + narrative_height)

    fig.update_layout(
        title_text=title or "Calibrated Explanation Dashboard",
        height=total_height,
        showlegend=False,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"t": 60, "b": narrative_height or 20, "l": 20, "r": 20},
    )

    return fig


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _image_grid_specs(n_panels: int, plot_rows: int, n_cols: int) -> list[list[dict]]:
    """Build specs list for a grid of image subplots, with None padding."""
    specs = []
    panel_idx = 0
    for _row in range(plot_rows):
        row_specs = []
        for _col in range(n_cols):
            if panel_idx < n_panels:
                row_specs.append({"type": "image"})
                panel_idx += 1
            else:
                row_specs.append(None)
        specs.append(row_specs)
    return specs
