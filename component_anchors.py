"""
component_anchors.py
─────────────────────
Each premade component declares its CONNECTION POINTS ("anchors") here.
An anchor is a named geometric feature of the component that other
components might want to mate with — for example, the elbow mouth of a
primary pump, or the boss-bore center of a diagrid.

Anchor functions take the component's GEOMETRY-ONLY dict (the same dict
the user writes) and return geometric quantities in the component's
LOCAL frame — the frame in which the component is built by its
create_*() function.

Why anchors are pure functions of the dict
──────────────────────────────────────────
The resolver (component_resolver.py) needs to know where every anchor is
BEFORE assembly, so it can derive the placement parameters
(center_coords, rotation_angles, plus any cross-component params like
diagrid.nozzle_z_abs) that will make anchors meet. Computing anchors
analytically from the dict — without actually building the geometry — is
cheap and avoids circular dependencies.

For components whose anchor positions cannot be computed in closed form
from the dict, the resolver falls back to building the component once
and measuring (see PUMP_CENTROID_LOCAL_Z below for an example).
"""

from __future__ import annotations
import math
from typing import Any


# ════════════════════════════════════════════════════════════════════════
#  Primary pump anchors
# ════════════════════════════════════════════════════════════════════════

def pump_elbow_mouth_local(pump: dict[str, Any]) -> dict[str, float]:
    """
    Returns the LOCAL-frame position of the RIGHT-hand elbow mouth of a
    primary pump, plus the azimuthal offset `phi` between the pump's own
    centerline and that mouth (the left mouth is the mirror, at −phi).

    Coordinates returned (all in metres, all in the pump's local frame):
        x, y, z   — center of the right-hand elbow mouth
        phi_deg   — azimuthal angle of (x, y) from the +x axis, in degrees
    """
    R_bend   = pump["nozzle_R_bend"]
    arc_deg  = pump["nozzle_arc_deg"]
    L_leg    = pump["nozzle_L_leg"]
    L_inlet  = pump["nozzle_L_inlet"]
    r_barrel = pump["barrel_radius"]
    wall_t   = pump["barrel_wall_t"]
    nozzle_z = pump["nozzle_z"]

    # End of elbow centerline in the elbow's own frame:
    arc_rad = math.radians(arc_deg)
    ex = R_bend * (1.0 - math.cos(arc_rad)) + L_leg * math.sin(arc_rad)
    ey = L_inlet + R_bend * math.sin(arc_rad) + L_leg * math.cos(arc_rad)

    # create_primary_pump rotates the elbow by −90° about Z and translates
    # by (r_barrel − overshoot, 0, nozzle_z):
    overshoot = wall_t * 1.5
    mouth_x = ey + (r_barrel - overshoot)
    mouth_y = -ex
    mouth_z = nozzle_z

    phi_deg = abs(math.degrees(math.atan2(mouth_y, mouth_x)))

    return {"x": mouth_x, "y": mouth_y, "z": mouth_z, "phi_deg": phi_deg}


# ════════════════════════════════════════════════════════════════════════
#  Diagrid anchors
# ════════════════════════════════════════════════════════════════════════
#
# The diagrid's relevant connection is its OUTER CYLINDRICAL FACE — the
# Ø_outer surface where bosses get attached. The anchor isn't a single
# point but rather "any (theta, z) on the outer cylinder" — the resolver
# decides which (theta, z) the bosses sit at, based on what pumps are
# in the assembly.

def diagrid_outer_radius(diagrid: dict[str, Any]) -> float:
    return diagrid["diameter"] / 2.0

def diagrid_z_range(diagrid: dict[str, Any]) -> tuple[float, float]:
    z_bottom = diagrid.get("z_bottom", 0.0)
    return z_bottom, z_bottom + diagrid["thickness"]