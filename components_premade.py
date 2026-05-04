"""
Pre-made domain components.

Accessed through the same dict interface as build_3D_primitive(), so they
slot into assemble_objects() and build_solid() exactly like any primitive.

The distinction from components_3D_primitives.py:

  components_3D_primitives  — pure geometry, no domain knowledge
                               (cylinder, pipe, box, sphere, …)
  components_premade        — domain-specific assemblies, built from
                               primitives + boolean operations
                               (reactor_vessel, reactor_top_plate, …)

Adding a new component
----------------------
1. Write a  _build_<name>(obj: dict) -> cq.Workplane  function below.
2. Add one entry to PREMADE_BUILDERS.
Nothing else in the codebase needs to change.

Usage (identical style to all other build_solid primitives)
-----------------------------------------------------------
>>> RPV = {
...     "operation":          "primitive",
...     "obj_id":             "rpv",
...     "obj_type":           "reactor_vessel",
...     "inner_d":            4.72,
...     "wall_t":             0.04,
...     "straight_h":         5.5,
...     "bottom_head_type":   "ellipsoidal",
...     "bottom_head_params": {"head_depth": 1.0},
... }
>>> TOP_PLATE = {
...     "operation":  "primitive",
...     "obj_id":     "top_plate",
...     "obj_type":   "reactor_top_plate",
...     "outer_d":    4.72 + 2 * 0.04,
...     "thickness":  0.1,
...     "z_bottom":   5.5,
...     "hole_groups": [...],
... }
>>> CORE = {
...     "operation":             "primitive",
...     "obj_id":                "core",
...     "obj_type":              "reactor_core",
...     "barrel_inner_radius":   1.65,
...     "barrel_wall_t":         0.05,
...     "barrel_height":         2.60,
...     "barrel_z_bottom":       0.0,
...     "r_inner_core":          0.86,
...     "r_outer_core":          1.28,
...     "r_radial_blanket":      1.54,
...     "lower_plenum_h":        0.50,
...     "axial_blanket_bottom_h": 0.30,
...     "active_h":              1.00,
...     "axial_blanket_top_h":   0.30,
...     "upper_plenum_h":        0.50,
... }
>>> # NOTE: for OpenMC export, call create_reactor_core() directly to obtain
>>> # the per-zone dict and assign individual material tags.
>>> assembly = assemble_objects([RPV, TOP_PLATE, CORE])
"""

from __future__ import annotations
from typing import Any, cast
import cadquery as cq

from component_premade_reactor_vessel import create_reactor_vessel
from component_premade_top_plate      import create_top_plate
from component_premade_ihx_old            import create_ihx
from component_premade_reactor_core   import create_reactor_core


# ---------------------------------------------------------------------------
# Individual builders — each takes the raw dict, returns cq.Workplane
# ---------------------------------------------------------------------------

def _build_reactor_vessel(obj: dict[str, Any]) -> cq.Workplane:
    vessel, _ = create_reactor_vessel(
        inner_d            = obj["inner_d"],
        wall_t             = obj["wall_t"],
        straight_h = cast(float, obj.get("straight_h") or obj.get("height")),    # fallback for NuExtract
        bottom_head_type   = obj.get("bottom_head_type"),
        bottom_head_params = obj.get("bottom_head_params"),
        top_head_type      = obj.get("top_head_type"),
        top_head_params    = obj.get("top_head_params"),
        # top_plate intentionally excluded — use "reactor_top_plate" separately
    )
    return vessel


def _build_reactor_top_plate(obj: dict[str, Any]) -> cq.Workplane:
    return create_top_plate(
        plate_outer_d   = obj["outer_d"],
        plate_thickness = obj["thickness"],
        center_coords   = (0.0, 0.0, obj["z_bottom"] + obj["thickness"] / 2.0),
        hole_groups     = obj.get("hole_groups"),
    )


def _build_ihx(obj: dict[str, Any]) -> cq.Workplane:
    parts = create_ihx(**{
        k: v for k, v in obj.items()
        if k in (
            "shell_od", "shell_wall_t", "shell_straight_h",
            "inner_od", "inner_wall_t", "inner_h",
            "bundle_od", "bundle_id", "bundle_h",
            "secondary_inlet_od", "secondary_inlet_wall_t",
            "secondary_inlet_length", "secondary_inlet_z",
            "secondary_outlet_od", "secondary_outlet_wall_t",
            "secondary_outlet_length", "secondary_outlet_z",
        )
    })
    result = parts["outer_shell"]
    for name, solid in parts.items():
        if name != "outer_shell":
            result = result.union(solid)
    return result.clean()


def _build_reactor_core(obj: dict[str, Any]) -> cq.Workplane:
    """
    Merge all neutronic zones into a single solid for CAD visualization.

    For OpenMC export, call create_reactor_core() directly instead —
    the per-zone dict gives you individual material handles.
    """
    _CORE_KEYS = (
        "barrel_inner_radius",
        "barrel_wall_t",
        "barrel_height",
        "barrel_z_bottom",
        "r_inner_core",
        "r_outer_core",
        "r_radial_blanket",
        "lower_plenum_h",
        "axial_blanket_bottom_h",
        "active_h",
        "axial_blanket_top_h",
        "upper_plenum_h",
    )
    parts = create_reactor_core(**{k: v for k, v in obj.items() if k in _CORE_KEYS})
    solids = list(parts.values())
    result = solids[0]
    for solid in solids[1:]:
        result = result.union(solid)
    return result.clean()


# ---------------------------------------------------------------------------
# Registry — the only thing that needs editing when adding a new component
# ---------------------------------------------------------------------------

PREMADE_BUILDERS: dict[str, Any] = {
    "reactor_vessel":    _build_reactor_vessel,
    "reactor_top_plate": _build_reactor_top_plate,
    "ihx":               _build_ihx,
    "reactor_core":      _build_reactor_core,
}


# ---------------------------------------------------------------------------
# Public entry point — mirrors build_3D_primitive() signature
# ---------------------------------------------------------------------------

def build_premade_component(obj: dict[str, Any]) -> cq.Workplane:
    obj_type = obj.get("obj_type", "")
    if obj_type not in PREMADE_BUILDERS:
        raise ValueError(
            f"Unknown premade component {obj_type!r}. "
            f"Available: {sorted(PREMADE_BUILDERS)}"
        )
    return PREMADE_BUILDERS[obj_type](obj)