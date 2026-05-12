"""
Same elbow, with a more pronounced bend.

To make the curve LOOK more bent (more pronounced):
    - DECREASE R_bend  → tighter turning radius (the visible "sharpness")
    - INCREASE arc_deg → more of the circle traced (how far it wraps around)

Constraint: R_bend must be > r_pipe (otherwise the inner wall self-intersects).
Practical minimum: R_bend >= 1.5 * r_pipe for a clean sweep.
"""

import math
import cadquery as cq

from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile


# ── parameters ──────────────────────────────────────────────────────
r_pipe   = 0.460 / 2     # 0.230
R_bend   = 0.430         # TIGHTER bend: was 0.600 → now 1.5 * r_pipe
arc_deg  = 110         # WRAPS FURTHER: was 67.5 → now traces 5/12 of a circle
L_inlet  = 0.050
L_leg    = 0.500

# sanity check + info
if R_bend <= r_pipe:
    raise ValueError(f"R_bend ({R_bend}) must be > r_pipe ({r_pipe})")
arc_length = R_bend * math.radians(arc_deg)
# print(f"R/r ratio:    {R_bend / r_pipe:.2f}  (1.0 = broken, 1.5 = tight, 3+ = gentle)")
# print(f"arc length:   {arc_length:.4f}")
# print(f"inner radius: {R_bend - r_pipe:.4f}  (must be > 0)")


# ── key points along the centerline ───────────────────────────────
arc_rad = math.radians(arc_deg)

P_arc_start = (0.0, L_inlet, 0.0)

P_arc_end = (R_bend * (1.0 - math.cos(arc_rad)),
             L_inlet + R_bend * math.sin(arc_rad),
             0.0)

tan_end = (math.sin(arc_rad), math.cos(arc_rad), 0.0)

P_end = (P_arc_end[0] + L_leg * tan_end[0],
         P_arc_end[1] + L_leg * tan_end[1],
         0.0)


# ── build path as exact cq.Wire (line + arc + line) ───────────────
edges = [cq.Edge.makeLine(cq.Vector(0.0, 0.0, 0.0),
                          cq.Vector(*P_arc_start))]

half = arc_rad / 2.0
P_arc_mid = (R_bend * (1.0 - math.cos(half)),
             L_inlet + R_bend * math.sin(half),
             0.0)
edges.append(cq.Edge.makeThreePointArc(cq.Vector(*P_arc_start),
                                       cq.Vector(*P_arc_mid),
                                       cq.Vector(*P_arc_end)))

if L_leg > 0:
    edges.append(cq.Edge.makeLine(cq.Vector(*P_arc_end),
                                  cq.Vector(*P_end)))

path_wire = cq.Wire.assembleEdges(edges)


# ── profile and sweep ─────────────────────────────────────────────
profile = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},
                          sketch_plane="XY")

solid = sweep_profile(profile, path_wire, isFrenet=True)


# ── export & show ─────────────────────────────────────────────────
if __name__ == "__main__":
    obj = solid.val()
    print(f"result type:  {type(obj).__name__}")
    print(f"is null?      {obj.isNull()}")              # type: ignore
    if not obj.isNull():                                # type: ignore
        print(f"volume:       {obj.Volume():.6f}")     # type: ignore

    cq.exporters.export(solid, "elbow_swept.step")
    cq.exporters.export(solid, "elbow_swept.stl")
    print("Exported elbow_swept.step / .stl")

    try:
        from ocp_vscode import show
        show(solid)
    except ImportError:
        pass
















# """
# Sweep a circular profile along a centerline built as an exact cq.Wire
# (line + circular arc + line) — NOT a spline approximation.

# Why this matters:
#     Passing the path as a callable f(t) makes sweep_profile sample it at
#     N points and fit a single spline through them. A spline through points
#     on a line+arc+line path has tangents at t=0 and t=1 that are only
#     *approximately* aligned with the true tangents. The profile placed
#     perpendicular to a slightly-off tangent builds a valid shell, but
#     BRepOffsetAPI_MakePipeShell::MakeSolid fails when capping the ends.

#     A proper cq.Wire with separate line / arc / line edges has exact
#     tangents at every point, including the endpoints, so the end caps
#     close cleanly into a solid.
# """

# import math
# import cadquery as cq

# from profile_built_in_2D_sketch import build_2D_sketch
# from utils import sweep_profile


# # ── parameters ──────────────────────────────────────────────────────
# r_pipe   = 0.460 / 2     # circle profile radius
# R_bend   = 0.600         # arc radius
# arc_deg  = 120          # sweep angle
# L_inlet  = 0.050         # straight section before the arc
# L_leg    = 0.450         # straight section after the arc


# # ── key points along the centerline ───────────────────────────────
# arc_rad = math.radians(arc_deg)

# # end of straight inlet (start of arc)
# P_arc_start = (0.0, L_inlet, 0.0)

# # end of arc (start of exit leg). Arc center at (R_bend, L_inlet), sweeping
# # clockwise (viewed from +Z) by arc_deg → ends at:
# P_arc_end = (R_bend * (1.0 - math.cos(arc_rad)),
#              L_inlet + R_bend * math.sin(arc_rad),
#              0.0)

# # final tangent direction (unit vector)
# tan_end = (math.sin(arc_rad), math.cos(arc_rad), 0.0)

# # end of exit leg
# P_end = (P_arc_end[0] + L_leg * tan_end[0],
#          P_arc_end[1] + L_leg * tan_end[1],
#          0.0)


# # ── build the path as a real cq.Wire with three exact edges ───────
# # Edge 1: straight inlet from (0,0,0) to P_arc_start
# edge_inlet = cq.Edge.makeLine(cq.Vector(0.0, 0.0, 0.0),
#                               cq.Vector(*P_arc_start))

# # Edge 2: circular arc from P_arc_start to P_arc_end.
# # Edge.makeThreePointArc needs a midpoint on the arc. The midpoint is
# # at sweep angle = arc_deg / 2, parameterized the same way as the path:
# half = arc_rad / 2.0
# P_arc_mid = (R_bend * (1.0 - math.cos(half)),
#              L_inlet + R_bend * math.sin(half),
#              0.0)
# edge_arc = cq.Edge.makeThreePointArc(cq.Vector(*P_arc_start),
#                                      cq.Vector(*P_arc_mid),
#                                      cq.Vector(*P_arc_end))

# # Edge 3: straight exit leg
# edge_leg = cq.Edge.makeLine(cq.Vector(*P_arc_end),
#                             cq.Vector(*P_end))

# path_wire = cq.Wire.assembleEdges([edge_inlet, edge_arc, edge_leg])


# # ── profile and sweep ─────────────────────────────────────────────
# profile = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},
#                           sketch_plane="XY")

# solid = sweep_profile(profile, path_wire, isFrenet=True)


# # ── export & show ─────────────────────────────────────────────────
# if __name__ == "__main__":
#     obj = solid.val()
#     print(f"result type: {type(obj).__name__}")
#     print(f"is null?     {obj.isNull()}")
#     if not obj.isNull():
#         print(f"volume:      {obj.Volume():.6f}")

#     cq.exporters.export(solid, "elbow_swept.step")
#     cq.exporters.export(solid, "elbow_swept.stl")
#     print("Exported elbow_swept.step / .stl")

#     try:
#         from ocp_vscode import show
#         show(solid)
#     except ImportError:
#         pass