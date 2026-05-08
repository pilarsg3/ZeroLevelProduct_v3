"""
J-bend using sweep_profile from utils.py.
Path in XZ plane (start going +Z, arc to +X).
Profile circle in XY plane.
"""
import cadquery as cq
from ocp_vscode import show
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile

R_bend = 0.800   # bend radius [m]
L_leg  = 0.800   # straight leg length [m]

# J-path: straight +Z leg, then 90° arc in XZ plane curving to +X
# radiusArc is built on a Workplane, so we use that to make the arc edge
path_wire1 = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(0, L_leg)
    .radiusArc((R_bend, L_leg + R_bend), R_bend)
    .wire()
    .val()
)

# Profile: circle in XY plane (perpendicular to +Z = path start tangent)
profile1 = build_2D_sketch({"obj_type": "circle", "radius": 0.460 / 2}, sketch_plane="XY")

result1 = sweep_profile(profile1, path_wire1, isFrenet=True)

show(result1)

import time
time.sleep(2)

R_bend = 0.800   # bend radius [m]
L_leg  = 0.800   # straight leg length [m]

# J-path: straight +Z leg, then 90° arc in XZ plane curving to +X
# radiusArc is built on a Workplane, so we use that to make the arc edge
path_wire2 = (
    cq.Workplane("XY")
    .moveTo(0, 0)
    .lineTo(0, L_leg)
    .radiusArc((-R_bend, L_leg + R_bend), -R_bend)
    .wire()
    .val()
)

# Profile: circle in XY plane (perpendicular to +Z = path start tangent)
profile2 = build_2D_sketch({"obj_type": "circle", "radius": 0.460 / 2}, sketch_plane="XY")

result2 = sweep_profile(profile2, path_wire2, isFrenet=True)

show(result2)