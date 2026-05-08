"""
Parametric primary pump (simplified) — ZLP V3.

Two hollow J-bend nozzles inserted into a vertical hollow barrel.
The nozzle bores connect to the barrel interior so fluid can flow.

All geometry dimensions are required — no defaults. This follows the same
convention as create_reactor_vessel and create_strongback, keeping
reactor-specific values in the assembly file rather than the component builder.

Operation order:
  1. Build solid (filled) barrel + filled J-bend outer shells, unioned.
     This gives the full external solid envelope of the pump.
  2. Cut the barrel inner bore + the J-bend inner bores from this envelope.
     What remains is the wall everywhere, with all fluid paths hollow.
"""

from __future__ import annotations
import cadquery as cq
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile


def _jbend_outer_and_inner(
    r_pipe: float, wall_t: float, L_leg: float, R_bend: float, clockwise: bool,
    arc_deg: float = 90.0,
    inner_stub: float = 0.0,
):
    """
    Returns (outer_solid, inner_solid) for a J-bend along an XY-plane path.
      arc_deg: total sweep of the arc in degrees (>90 makes the leg angle inward)
      outer_solid / inner_solid: filled cylinders along the J path (and inner stub)
    """
    import math
    if clockwise:
        sign = +1
    else:
        sign = -1
    cx = sign * R_bend
    cy = L_leg

    a = math.radians(arc_deg)
    a_eff = -a if clockwise else a

    rx0 = -sign * R_bend
    ry0 = 0
    rx1 = rx0 * math.cos(a_eff) - ry0 * math.sin(a_eff)
    ry1 = rx0 * math.sin(a_eff) + ry0 * math.cos(a_eff)
    end = (cx + rx1, cy + ry1)

    if clockwise:
        tip_dir = (ry1, -rx1)
    else:
        tip_dir = (-ry1, rx1)
    tlen = math.hypot(*tip_dir)
    tip_dir = (tip_dir[0] / tlen, tip_dir[1] / tlen)

    rad = sign * R_bend

    outer_path = (
        cq.Workplane("XY")
        .moveTo(0, 0)
        .lineTo(0, L_leg)
        .radiusArc(end, rad)
        .wire()
        .val()
    )

    if inner_stub > 0:
        ext_end = (end[0] + tip_dir[0] * inner_stub,
                   end[1] + tip_dir[1] * inner_stub)
        inner_path = (
            cq.Workplane("XY")
            .moveTo(0, 0)
            .lineTo(0, L_leg)
            .radiusArc(end, rad)
            .lineTo(*ext_end)
            .wire()
            .val()
        )
    else:
        inner_path = outer_path

    profile_outer = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},          sketch_plane="XY")
    profile_inner = build_2D_sketch({"obj_type": "circle", "radius": r_pipe - wall_t}, sketch_plane="XY")

    outer = sweep_profile(profile_outer, outer_path, isFrenet=True)
    inner = sweep_profile(profile_inner, inner_path, isFrenet=True)
    return outer, inner


def create_primary_pump(
    # ── Barrel (required) ─────────────────────────────────────────────────
    barrel_radius:  float,
    barrel_wall_t:  float,
    barrel_height:  float,

    # ── Nozzle J-bends (required) ─────────────────────────────────────────
    nozzle_r_pipe:  float,
    nozzle_wall_t:  float,
    nozzle_L_leg:   float,
    nozzle_R_bend:  float,
    nozzle_arc_deg: float,   # >90° makes legs angle inward
    nozzle_z:       float,   # axial position of nozzle centre on barrel

    # ── Flange (required) ─────────────────────────────────────────────────
    flange_width:   float,   # radial protrusion
    flange_height:  float,   # axial height
    flange_depth:   float,   # tangential depth

    # ── Positioning ───────────────────────────────────────────────────────
    z_bottom:       float = 0.0,
    flange_z_top:   float | None = None,   # defaults to barrel_height - 0.5
) -> cq.Workplane:
    """
    Build a primary pump: hollow barrel with two J-bend nozzles and a flange.

    Args:
        barrel_radius:  outer radius of the barrel [m]
        barrel_wall_t:  barrel wall thickness [m]
        barrel_height:  total axial height of the barrel [m]
        nozzle_r_pipe:  outer radius of each nozzle pipe [m]
        nozzle_wall_t:  nozzle wall thickness [m]
        nozzle_L_leg:   straight leg length of each J-bend [m]
        nozzle_R_bend:  bend radius of each J-bend [m]
        nozzle_arc_deg: arc sweep in degrees (90 = right angle, >90 = legs angle inward)
        nozzle_z:       z of nozzle connection on barrel (above barrel base) [m]
        flange_width:   radial protrusion of rectangular flange [m]
        flange_height:  axial height of rectangular flange [m]
        flange_depth:   tangential depth of rectangular flange [m]
        z_bottom:       translate so barrel base sits at this z [m]
        flange_z_top:   z of flange top face; defaults to barrel_height - 0.5 [m]

    Returns:
        cq.Workplane — single solid
    """
    if flange_z_top is None:
        flange_z_top = barrel_height - 0.5

    overshoot = barrel_wall_t * 1.5

    # ── 1. Build the FILLED OUTER ENVELOPE (no bores yet) ────────────────
    barrel_outer = cq.Workplane("XY").circle(barrel_radius).extrude(barrel_height)

    inner_stub = barrel_wall_t * 4
    j1_out, j1_in = _jbend_outer_and_inner(nozzle_r_pipe, nozzle_wall_t,
                                           nozzle_L_leg, nozzle_R_bend,
                                           clockwise=False,
                                           arc_deg=nozzle_arc_deg,
                                           inner_stub=inner_stub)
    shift_r = (barrel_radius + nozzle_R_bend - overshoot,
               -(nozzle_L_leg + nozzle_R_bend), nozzle_z)
    j1_out = j1_out.translate(shift_r)
    j1_in  = j1_in.translate(shift_r)

    j2_out, j2_in = _jbend_outer_and_inner(nozzle_r_pipe, nozzle_wall_t,
                                           nozzle_L_leg, nozzle_R_bend,
                                           clockwise=True,
                                           arc_deg=nozzle_arc_deg,
                                           inner_stub=inner_stub)
    shift_l = (-(barrel_radius + nozzle_R_bend - overshoot),
               -(nozzle_L_leg + nozzle_R_bend), nozzle_z)
    j2_out = j2_out.translate(shift_l)
    j2_in  = j2_in.translate(shift_l)

    envelope = barrel_outer.union(j1_out).union(j2_out)

    flange = (cq.Workplane("XY")
              .workplane(offset=flange_z_top - flange_height)
              .moveTo(0, barrel_radius + flange_width / 2 - overshoot)
              .rect(flange_depth, flange_width)
              .extrude(flange_height))
    envelope = envelope.union(flange)

    # ── 2. Cut all bores from the envelope ───────────────────────────────
    # barrel_bore = cq.Workplane("XY").circle(barrel_radius - barrel_wall_t).extrude(barrel_height)
    barrel_bore = (
    cq.Workplane("XY")
    .workplane(offset=barrel_wall_t)
    .circle(barrel_radius - barrel_wall_t)
    .extrude(barrel_height - 2 * barrel_wall_t)
    )
    solid = envelope.cut(barrel_bore).cut(j1_in).cut(j2_in)

    if z_bottom != 0.0:
        solid = solid.translate((0, 0, z_bottom))

    return solid.clean()


if __name__ == "__main__":
    from ocp_vscode import show
    pump = create_primary_pump(
        barrel_radius  = 1.350 / 2,
        barrel_wall_t  = 0.040,
        barrel_height  = 12.000,
        nozzle_r_pipe  = 0.460 / 2,
        nozzle_wall_t  = 0.025,
        nozzle_L_leg   = 0.800,
        nozzle_R_bend  = 0.800,
        nozzle_arc_deg = 112.5,
        nozzle_z       = 0.450,
        flange_width   = 0.548,
        flange_height  = 0.900,
        flange_depth   = 0.500,
    )
    show(pump)



























"""
Parametric primary pump (simplified) — ZLP V3.

Two hollow J-bend nozzles inserted into a vertical hollow barrel.
The nozzle bores connect to the barrel interior so fluid can flow.

Operation order:
  1. Build solid (filled) barrel + filled J-bend outer shells, unioned.
     This gives the full external solid envelope of the pump.
  2. Cut the barrel inner bore + the J-bend inner bores from this envelope.
     What remains is the wall everywhere, with all fluid paths hollow.
"""
"""
from __future__ import annotations
import cadquery as cq
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile


def _jbend_outer_and_inner(
    r_pipe: float, wall_t: float, L_leg: float, R_bend: float, clockwise: bool,
    arc_deg: float = 90.0,
    inner_stub: float = 0.0,
):
    """
    # Returns (outer_solid, inner_solid) for a J-bend along an XY-plane path.
    #  arc_deg: total sweep of the arc in degrees (>90 makes the leg angle inward)
    #  outer_solid / inner_solid: filled cylinders along the J path (and inner stub)
"""
    import math
    # Arc starts at (0, L_leg) tangent to +Y. Sweeps `arc_deg` clockwise (or CCW).
    # Centre of arc at (sign*R_bend, L_leg).
    # End point of arc: rotate (0, L_leg) by arc_deg around centre.
    if clockwise:
        sign = +1
    else:
        sign = -1
    cx = sign * R_bend
    cy = L_leg

    # Start point relative to centre: (-sign*R_bend, 0)
    # Rotate by arc_deg in the appropriate direction
    a = math.radians(arc_deg)
    if clockwise:
        # CW rotation: (x,y) -> (x cos - y sin, x sin + y cos)? Use -a for CW
        a_eff = -a
    else:
        a_eff = a

    rx0 = -sign * R_bend
    ry0 = 0
    rx1 = rx0 * math.cos(a_eff) - ry0 * math.sin(a_eff)
    ry1 = rx0 * math.sin(a_eff) + ry0 * math.cos(a_eff)
    end = (cx + rx1, cy + ry1)

    # Tangent at arc end: perpendicular to radius (rx1, ry1), rotated 90° in sweep direction
    if clockwise:
        tip_dir = (ry1, -rx1)
    else:
        tip_dir = (-ry1, rx1)
    # Normalise
    tlen = math.hypot(*tip_dir)
    tip_dir = (tip_dir[0] / tlen, tip_dir[1] / tlen)

    # radiusArc accepts the endpoint and signed radius (sign chooses arc side)
    rad = sign * R_bend

    outer_path = (
        cq.Workplane("XY")
        .moveTo(0, 0)
        .lineTo(0, L_leg)
        .radiusArc(end, rad)
        .wire()
        .val()
    )

    if inner_stub > 0:
        ext_end = (end[0] + tip_dir[0] * inner_stub,
                   end[1] + tip_dir[1] * inner_stub)
        inner_path = (
            cq.Workplane("XY")
            .moveTo(0, 0)
            .lineTo(0, L_leg)
            .radiusArc(end, rad)
            .lineTo(*ext_end)
            .wire()
            .val()
        )
    else:
        inner_path = outer_path

    profile_outer = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},          sketch_plane="XY")
    profile_inner = build_2D_sketch({"obj_type": "circle", "radius": r_pipe - wall_t}, sketch_plane="XY")

    outer = sweep_profile(profile_outer, outer_path, isFrenet=True)
    inner = sweep_profile(profile_inner, inner_path, isFrenet=True)
    return outer, inner


def create_primary_pump(
    barrel_radius:  float = 1.350 / 2,
    barrel_wall_t:  float = 0.040,
    barrel_height:  float = 12.000,

    nozzle_r_pipe:  float = 0.460 / 2,
    nozzle_wall_t:  float = 0.025,
    nozzle_L_leg:   float = 0.800,
    nozzle_R_bend:  float = 0.800,
    nozzle_arc_deg: float = 112.5,    # >90° makes legs angle inward (135° between legs)
    nozzle_z:       float = 0.450,

    # Top-right rectangular flange (from drawing)
    flange_width:   float = 0.548,    # 548 mm — radial protrusion
    flange_height:  float = 0.900,    # 900 mm — axial height
    flange_depth:   float = 0.500,    # tangential depth (estimated; not given on drawing)
    flange_z_top:   float = 11.500,   # top of flange aligns with top of barrel area

    z_bottom:       float = 0.0,
) -> cq.Workplane:
    overshoot = barrel_wall_t * 1.5

    # ── 1. Build the FILLED OUTER ENVELOPE (no bores yet) ────────────────
    barrel_outer = cq.Workplane("XY").circle(barrel_radius).extrude(barrel_height)

    # Right J outer & inner sweeps. Inner sweep is extended past the arc tip
    # by `inner_stub` so the cutter cleanly punches through the barrel wall.
    inner_stub = barrel_wall_t * 4
    j1_out, j1_in = _jbend_outer_and_inner(nozzle_r_pipe, nozzle_wall_t,
                                           nozzle_L_leg, nozzle_R_bend,
                                           clockwise=False,
                                           arc_deg=nozzle_arc_deg,
                                           inner_stub=inner_stub)
    shift_r = (barrel_radius + nozzle_R_bend - overshoot,
               -(nozzle_L_leg + nozzle_R_bend), nozzle_z)
    j1_out = j1_out.translate(shift_r)
    j1_in  = j1_in.translate(shift_r)

    # Left J outer & inner sweeps
    j2_out, j2_in = _jbend_outer_and_inner(nozzle_r_pipe, nozzle_wall_t,
                                           nozzle_L_leg, nozzle_R_bend,
                                           clockwise=True,
                                           arc_deg=nozzle_arc_deg,
                                           inner_stub=inner_stub)
    shift_l = (-(barrel_radius + nozzle_R_bend - overshoot),
               -(nozzle_L_leg + nozzle_R_bend), nozzle_z)
    j2_out = j2_out.translate(shift_l)
    j2_in  = j2_in.translate(shift_l)

    # Union all outer solids → the complete external envelope
    envelope = barrel_outer.union(j1_out).union(j2_out)

    # ── Top-right rectangular flange (from drawing, near top of barrel) ─
    # Top view shows it on the opposite side of the barrel from the two U-bends.
    # Push slightly inward (overshoot) so it overlaps the barrel wall instead of
    # just touching at a single point.
    flange = (cq.Workplane("XY")
              .workplane(offset=flange_z_top - flange_height)
              .moveTo(0, barrel_radius + flange_width / 2 - overshoot)
              .rect(flange_depth, flange_width)
              .extrude(flange_height))
    envelope = envelope.union(flange)

    # ── 2. Cut all bores from the envelope ───────────────────────────────
    # Barrel inner bore: full-height vertical cylinder
    barrel_bore = cq.Workplane("XY").circle(barrel_radius - barrel_wall_t).extrude(barrel_height)

    solid = envelope.cut(barrel_bore).cut(j1_in).cut(j2_in)

    if z_bottom != 0.0:
        solid = solid.translate((0, 0, z_bottom))

    return solid.clean()


if __name__ == "__main__":
    from ocp_vscode import show
    pump = create_primary_pump()
    show(pump)
"""




