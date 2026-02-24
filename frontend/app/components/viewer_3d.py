"""
Ligant.ai 3D Protein Structure Viewer

Provides py3Dmol-based rendering helpers for displaying PDB structures
inside the Streamlit UI.  Supports multiple visualization styles, coloring
schemes, and overlay comparisons.
"""

from typing import List

import py3Dmol
from stmol import showmol
import streamlit as st

# Color palette for distinguishing chains / models
CHAIN_COLORS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
]


def _get_color(index: int) -> str:
    """Return a color from the palette, cycling if necessary."""
    return CHAIN_COLORS[index % len(CHAIN_COLORS)]


def render_pdb_viewer(
    pdb_contents: List[str],
    style: str = "cartoon",
    color_by: str = "chain",
    label: str = "",
    width: int = 800,
    height: int = 500,
) -> None:
    """
    Render one or more PDB structures in an interactive 3D viewer.

    Parameters
    ----------
    pdb_contents : list[str]
        List of PDB file contents as strings.
    style : str
        Visualization style: ``"cartoon"``, ``"surface"``, ``"stick"``,
        or ``"cartoon+surface"``.
    color_by : str
        Coloring scheme: ``"chain"``, ``"spectrum"``, or
        ``"secondary_structure"``.
    label : str
        Optional caption displayed above the viewer.
    width : int
        Viewer width in pixels.
    height : int
        Viewer height in pixels.
    """
    if label:
        st.caption(label)

    view = py3Dmol.view(width=width, height=height)

    for i, pdb_content in enumerate(pdb_contents):
        view.addModel(pdb_content, "pdb")
        color = _get_color(i)

        # ── Apply coloring ────────────────────────────────────────────
        if color_by == "spectrum":
            _apply_style_spectrum(view, i, style)
        elif color_by == "secondary_structure":
            _apply_style_ss(view, i, style)
        else:
            # Default: color by chain (each model gets a unique color)
            _apply_style_chain(view, i, style, color)

    view.zoomTo()
    showmol(view, height=height, width=width)


def _apply_style_chain(view, model_idx: int, style: str, color: str) -> None:
    """Apply the requested style with a single per-model chain color."""
    selector = {"model": model_idx}

    if style == "cartoon":
        view.setStyle(selector, {"cartoon": {"color": color}})

    elif style == "surface":
        view.setStyle(selector, {"cartoon": {"color": color}})
        view.addSurface(
            py3Dmol.VDW,
            {"opacity": 0.7, "color": color},
            selector,
        )

    elif style == "stick":
        view.setStyle(selector, {"stick": {"color": color}})

    elif style == "cartoon+surface":
        view.setStyle(selector, {"cartoon": {"color": color}})
        view.addSurface(
            py3Dmol.VDW,
            {"opacity": 0.4, "color": color},
            selector,
        )

    else:
        # Fallback to cartoon
        view.setStyle(selector, {"cartoon": {"color": color}})


def _apply_style_spectrum(view, model_idx: int, style: str) -> None:
    """Apply rainbow-spectrum coloring along the residue sequence."""
    selector = {"model": model_idx}

    if style in ("cartoon", "cartoon+surface"):
        view.setStyle(selector, {"cartoon": {"color": "spectrum"}})
        if style == "cartoon+surface":
            view.addSurface(
                py3Dmol.VDW,
                {"opacity": 0.4, "colorscheme": "spectral"},
                selector,
            )
    elif style == "surface":
        view.setStyle(selector, {"cartoon": {"color": "spectrum"}})
        view.addSurface(
            py3Dmol.VDW,
            {"opacity": 0.7, "colorscheme": "spectral"},
            selector,
        )
    elif style == "stick":
        view.setStyle(selector, {"stick": {"colorscheme": "spectral"}})
    else:
        view.setStyle(selector, {"cartoon": {"color": "spectrum"}})


def _apply_style_ss(view, model_idx: int, style: str) -> None:
    """
    Color by secondary structure type:
    helix = red, sheet = blue, coil = gray.
    """
    selector = {"model": model_idx}

    ss_style = {
        "cartoon": {
            "colorfunc": (
                "function(atom) {"
                "  if (atom.ss === 'h') return '#d62728';"
                "  if (atom.ss === 's') return '#1f77b4';"
                "  return '#7f7f7f';"
                "}"
            )
        }
    }

    if style in ("cartoon", "cartoon+surface"):
        view.setStyle(selector, ss_style)
        if style == "cartoon+surface":
            view.addSurface(
                py3Dmol.VDW,
                {"opacity": 0.4},
                selector,
            )
    elif style == "surface":
        view.setStyle(selector, ss_style)
        view.addSurface(
            py3Dmol.VDW,
            {"opacity": 0.7},
            selector,
        )
    elif style == "stick":
        view.setStyle(selector, {"stick": {}})
    else:
        view.setStyle(selector, ss_style)


def render_overlay_comparison(
    target_pdb: str,
    design_pdbs: List[str],
    label: str = "",
) -> None:
    """
    Overlay one or more designed binder structures on the target protein.

    The target is rendered as a gray semi-transparent surface.  Each design
    is rendered as a cartoon with a distinct chain color.

    Parameters
    ----------
    target_pdb : str
        PDB file contents for the target protein.
    design_pdbs : list[str]
        List of PDB file contents for the designed binders.
    label : str
        Optional caption displayed above the viewer.
    """
    if label:
        st.caption(label)

    view = py3Dmol.view(width=800, height=600)

    # Model 0: target -- gray semi-transparent surface
    view.addModel(target_pdb, "pdb")
    view.setStyle({"model": 0}, {"cartoon": {"color": "#cccccc", "opacity": 0.5}})
    view.addSurface(
        py3Dmol.VDW,
        {"opacity": 0.3, "color": "#cccccc"},
        {"model": 0},
    )

    # Subsequent models: designed binders
    for i, design_pdb in enumerate(design_pdbs):
        model_idx = i + 1
        color = _get_color(i)

        view.addModel(design_pdb, "pdb")
        view.setStyle({"model": model_idx}, {"cartoon": {"color": color}})

    view.zoomTo()
    showmol(view, height=600, width=800)
