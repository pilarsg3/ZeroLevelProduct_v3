"""
component_resolver.py — v2 with explicit user overrides
─────────────────────────────────────────────────────────
User-facing rule: the resolver computes placement for every component
involved in a connection rule, UNLESS the user has explicitly opted out
or provided their own values.

Three ways the user can interact with placement:

  1. Default (paramak-style): omit center_coords / rotation_angles
     entirely, give only `at_angle_deg` + `at_radius`. The resolver
     computes everything.

  2. Full manual override: provide center_coords AND rotation_angles
     yourself. The resolver leaves them alone, but still uses them as
     inputs for downstream calculations (the diagrid's boss angles
     follow your manually-placed pumps).

  3. Opt-out completely: set `"manual_placement": True`. The resolver
     skips this component entirely — no params written to it, no params
     read from it for downstream calculations.

Why three modes
───────────────
Mode 1 is paramak-style — the magical default. Mode 2 covers users who
want the resolver to drive ONE side of a connection but not the other
(e.g. "I placed the pumps by hand, now build the diagrid to match").
Mode 3 is the escape hatch for edge cases the rules don't cover.
"""

from __future__ import annotations
import copy
import math
from typing import Any

import cadquery as cq

from component_anchors import (
    pump_elbow_mouth_local,
    diagrid_outer_radius,
    diagrid_z_range,
)
from component_premade_primary_pump import create_primary_pump


# ════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════

def _find_all(dicts: list[dict], obj_type: str) -> list[dict]:
    return [d for d in dicts if d.get("obj_type") == obj_type]

def _find_one(dicts: list[dict], obj_type: str) -> dict | None:
    matches = _find_all(dicts, obj_type)
    if len(matches) > 1:
        raise ValueError(
            f"Expected at most one {obj_type}, found {len(matches)}."
        )
    return matches[0] if matches else None


def _is_opted_out(d: dict) -> bool:
    """True if the user has explicitly removed this component from
    resolver consideration."""
    return bool(d.get("manual_placement", False))


def _has_full_manual_placement(d: dict) -> bool:
    """True if the user already provided BOTH center_coords and
    rotation_angles. The resolver doesn't override them but may still
    READ them to drive other components."""
    return ("center_coords" in d) and ("rotation_angles" in d)


def _build_pump_local(pump: dict) -> cq.Workplane:
    return create_primary_pump(
        barrel_radius  = pump["barrel_radius"],
        barrel_wall_t  = pump["barrel_wall_t"],
        barrel_height  = pump["barrel_height"],
        nozzle_r_pipe  = pump["nozzle_r_pipe"],
        nozzle_wall_t  = pump["nozzle_wall_t"],
        nozzle_L_leg   = pump["nozzle_L_leg"],
        nozzle_R_bend  = pump["nozzle_R_bend"],
        nozzle_arc_deg = pump["nozzle_arc_deg"],
        nozzle_L_inlet = pump["nozzle_L_inlet"],
        nozzle_z       = pump["nozzle_z"],
        flange_width   = pump["flange_width"],
        flange_height  = pump["flange_height"],
        flange_depth   = pump["flange_depth"],
        z_bottom       = 0.0,
    )


def _pump_world_radius(p: dict) -> float:
    """Return the radial distance from the reactor axis to the pump's
    centerline. Reads from `at_radius` if given (mode 1), otherwise
    from `center_coords` XY (mode 2)."""
    if "at_radius" in p:
        return p["at_radius"]
    if "center_coords" in p:
        cc = p["center_coords"]
        return math.hypot(cc[0], cc[1])
    raise ValueError(
        f"Pump {p.get('obj_id')} needs either `at_radius` (resolver mode) "
        f"or `center_coords` (manual mode)."
    )


def _pump_world_angle_deg(p: dict) -> float:
    """Return the azimuthal angle of the pump's centerline. Reads from
    `at_angle_deg` if given (mode 1), otherwise from `center_coords`
    XY (mode 2)."""
    if "at_angle_deg" in p:
        return p["at_angle_deg"]
    if "center_coords" in p:
        cc = p["center_coords"]
        return math.degrees(math.atan2(cc[1], cc[0]))
    raise ValueError(
        f"Pump {p.get('obj_id')} needs either `at_angle_deg` or "
        f"`center_coords`."
    )


# ════════════════════════════════════════════════════════════════════════
#  Connection rule: primary_pump ↔ diagrid
# ════════════════════════════════════════════════════════════════════════

def _resolve_pump_diagrid(dicts: list[dict]) -> None:
    diagrid = _find_one(dicts, "diagrid")
    if diagrid is None or _is_opted_out(diagrid):
        return

    # Only pumps that haven't opted out are considered.
    pumps = [p for p in _find_all(dicts, "primary_pump") if not _is_opted_out(p)]
    if not pumps:
        return

    # Reference pump for elbow geometry — all pumps in one assembly share it.
    ref         = pumps[0]
    mouth_local = pump_elbow_mouth_local(ref)

    # Pre-build one pump → measure its centroid (needed because
    # assemble_objects centers solids by their centroid).
    centroid_local_z = _build_pump_local(ref).val().Center().z      # type: ignore

    # Connection Z in world coordinates. User may override.
    z_bot, z_top   = diagrid_z_range(diagrid)
    nozzle_z_world = diagrid.get("nozzle_z_abs", (z_bot + z_top) / 2.0)

    # Radial distance of pumps (must all match).
    radii = {round(_pump_world_radius(p), 6) for p in pumps}
    if len(radii) > 1:
        raise ValueError(
            f"All primary_pump dicts must share a single radial distance. "
            f"Found: {sorted(radii)}."
        )
    pump_R = next(iter(radii))

    # World radius of the elbow mouth, derived from pump radius + elbow geom.
    mx_l, my_l    = mouth_local["x"], mouth_local["y"]
    wx, wy        = pump_R + my_l, -mx_l
    mouth_R_world = math.hypot(wx, wy)
    phi_deg       = abs(math.degrees(math.atan2(wy, wx)))

    # Boss protrusion → flush mate with mouth.
    diagrid_outer_r = diagrid_outer_radius(diagrid)
    boss_protrusion = mouth_R_world - diagrid_outer_r
    if boss_protrusion <= 0:
        raise ValueError(
            f"Diagrid outer radius ({diagrid_outer_r}) ≥ elbow mouth radius "
            f"({mouth_R_world:.4f}). Move pumps outward or shrink diagrid."
        )

    # Boss azimuthal angles — one pair per pump.
    boss_angles: list[float] = []
    for p in pumps:
        a = _pump_world_angle_deg(p)
        boss_angles.append(a - phi_deg)
        boss_angles.append(a + phi_deg)

    # Fill in the diagrid dict (never overwrite user-set values).
    diagrid.setdefault("nozzle_z_abs",           nozzle_z_world)
    diagrid.setdefault("nozzle_boss_angles_deg", boss_angles)
    diagrid.setdefault("nozzle_boss_height",     boss_protrusion)
    diagrid.setdefault("nozzle_r_bore",          ref["nozzle_r_pipe"])
    diagrid.setdefault("nozzle_r_boss",          ref["nozzle_r_pipe"] + 0.071)

    # Place each pump (skip those the user already placed).
    #
    # Centroid-placement math:
    #   move_center_to: world_z(P) = P_local.z + (cc.z − centroid_local.z)
    #   With P = mouth, requiring world_z = nozzle_z_world:
    #       cc.z = nozzle_z_world − mouth_local.z + centroid_local.z
    cc_z = nozzle_z_world - mouth_local["z"] + centroid_local_z

    for p in pumps:
        if _has_full_manual_placement(p):
            continue   # user placed it; respect them

        if "at_angle_deg" not in p or "at_radius" not in p:
            raise ValueError(
                f"Pump {p.get('obj_id')} needs both `at_angle_deg` and "
                f"`at_radius` for resolver placement. Alternatively, "
                f"provide both `center_coords` and `rotation_angles`."
            )

        a   = p["at_angle_deg"]
        r   = p["at_radius"]
        rad = math.radians(a)
        p["rotation_angles"] = (0.0, 0.0, a - 90.0)
        p["center_coords"]   = (r * math.cos(rad), r * math.sin(rad), cc_z)


# ════════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════════

_CONNECTION_RULES = [
    _resolve_pump_diagrid,
    # _resolve_ihx_topplate,
    # _resolve_strongback_rpv,
]

def resolve(user_dicts: list[dict]) -> list[dict]:
    """Apply every connection rule. Returns a new list of fully-resolved
    dicts, ready for assemble_objects."""
    resolved = [copy.deepcopy(d) for d in user_dicts]
    for rule in _CONNECTION_RULES:
        rule(resolved)
    return resolved