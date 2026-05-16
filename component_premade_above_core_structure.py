"""
Above Core Structure (ACS) — ZLP simplified parametric model.

Geometry (bottom to top):
  1. Base cylinder         — flat disc
  2. Conical skirt shell   — frusto-conical shell, wider at top
  3. Top annular plate     — flat ring
  4. Control-rod guide tubes — hollow pipes through and above plate

Key reference dimensions from drawing:
  plate OD   Ø3686 mm  → r = 1.843 m
  plate bore Ø2217 mm  → r = 1.109 m
  skirt bot  Ø2806 mm  → r = 1.403 m
  tube OD    Ø142  mm  → r = 0.071 m
"""

from __future__ import annotations
import math
import cadquery as cq


def create_above_core_structure(
    # ── Top annular plate ─────────────────────────────────────────────
    plate_outer_r:    float = 1.843,   # Ø3686 / 2
    plate_inner_r:    float = 1.109,   # Ø2217 / 2  (central bore)
    plate_thickness:  float = 1.008,
    # ── Conical skirt ─────────────────────────────────────────────────
    skirt_top_r:      float = 1.843,   # = plate_outer_r
    skirt_bot_r:      float = 1.403,   # Ø2806 / 2
    skirt_height:     float = 2.429,
    skirt_wall_t:     float = 0.025,
    # ── Base disc ─────────────────────────────────────────────────────
    base_r:           float = 1.403,   # = skirt_bot_r
    base_thickness:   float = 0.498,
    # ── Control-rod guide tubes ───────────────────────────────────────
    tube_outer_r:     float = 0.071,   # Ø142 / 2
    tube_wall_t:      float = 0.010,
    tube_above_plate: float = 2.000,   # how far tubes protrude above plate
    n_tubes:          int   = 7,       # 1 centre + 6 on pitch circle
    tube_pitch_r:     float = 0.400,
    # ── Positioning ───────────────────────────────────────────────────
    z_bottom:         float = 0.0,
) -> cq.Workplane:

    z0 = z_bottom
    z1 = z0 + base_thickness          # base top  = skirt bottom
    z2 = z1 + skirt_height            # skirt top = plate bottom
    z3 = z2 + plate_thickness         # plate top

    # ── 1. Base disc ──────────────────────────────────────────────────
    base = (cq.Workplane("XY")
            .workplane(offset=z0)
            .circle(base_r)
            .extrude(base_thickness))

    # ── 2. Conical skirt shell ────────────────────────────────────────
    # Draw a trapezoid cross-section in the XZ plane, revolve 360° around Z.
    # In "XZ" workplane: moveTo(radius, height)
    skirt = (cq.Workplane("XZ")
             .moveTo(skirt_bot_r,              z1)
             .lineTo(skirt_top_r,              z2)
             .lineTo(skirt_top_r - skirt_wall_t, z2)
             .lineTo(skirt_bot_r - skirt_wall_t, z1)
             .close()
             .revolve(360, (0, 0, 0), (0, 0, 1)))

    # ── 3. Top annular plate ──────────────────────────────────────────
    plate = (cq.Workplane("XY")
             .workplane(offset=z2)
             .circle(plate_outer_r)
             .extrude(plate_thickness))
    plate_bore = (cq.Workplane("XY")
                  .workplane(offset=z2)
                  .circle(plate_inner_r)
                  .extrude(plate_thickness))
    plate = plate.cut(plate_bore)

    # ── 4. Guide tubes ────────────────────────────────────────────────
    # 1 central tube + (n_tubes - 1) on a pitch circle
    positions = [(0.0, 0.0)]
    for i in range(n_tubes - 1):
        angle = 2 * math.pi * i / (n_tubes - 1)
        positions.append((tube_pitch_r * math.cos(angle),
                          tube_pitch_r * math.sin(angle)))

    tubes = None
    for tx, ty in positions:
        t_out = (cq.Workplane("XY")
                 .workplane(offset=z2)
                 .moveTo(tx, ty)
                 .circle(tube_outer_r)
                 .extrude(plate_thickness + tube_above_plate))
        t_in  = (cq.Workplane("XY")
                 .workplane(offset=z2)
                 .moveTo(tx, ty)
                 .circle(tube_outer_r - tube_wall_t)
                 .extrude(plate_thickness + tube_above_plate))
        tube = t_out.cut(t_in)
        tubes = tube if tubes is None else tubes.union(tube)

    # ── Assemble all parts ────────────────────────────────────────────
    result = base.union(skirt).union(plate)
    if tubes is not None:
        result = result.union(tubes)

    return result.clean()


if __name__ == "__main__":
    from ocp_vscode import show

    # In the full assembly, z_bottom = core top = 0.590 + 3.910 = 4.500 m
    acs = create_above_core_structure(z_bottom=0.0)
    show(acs)