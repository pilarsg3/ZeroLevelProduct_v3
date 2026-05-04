"""
components_premade/simple_ihx.py
─────────────────────────────────
Parametric shell-and-tube IHX builder for ZeroLevelProduct V2.

Geometry (bottom → top, z increasing upward)
─────────────────────────────────────────────

                          outlet_riser ──► lateral_pipe
                               │
    ╔══════════════════════════╧═╗   ← top dome (outlet_riser exits here)
    ║   upper plenum             ║
    ║                        ═══╬═══► central_pipe horizontal exit
    ║   (central_pipe on axis)   ║     (bends inside upper plenum, exits +X wall)
    ╚═══════════════════════╤════╝   ← bottom plate (n tube holes + central pipe axial bore)
          │  │  │   tube_bundle
    ╔═════╧══════════════════════╗   ← top plate (n tube holes + central pipe axial bore)
    ║   lower plenum             ║
    ║                            ║
    ╚══════════╤═════════════════╝   ← bottom dome (central pipe axial bore)
               │
          central_pipe  (continues external below dome)

Seven independent components
─────────────────────────────
  lower_plenum_shell   bowl dome + cylindrical shell + top plate
  tube_bundle          n hollow vertical tubes
  upper_plenum_shell   bottom plate + cylindrical shell + top dome
  central_pipe         L-shaped: vert on axis (through both plenums) → arc → horiz exit
                       (pipe_436 pattern; bends inside upper plenum, exits +X wall)
  outlet_riser         straight vertical pipe above upper dome — independent of central_pipe
  lateral_pipe         horizontal pipe connected to outlet_riser +X wall

Coordinate convention
─────────────────────
  z = 0  →  bottom face of lower plenum cylindrical section
  +z     →  upward; all horizontal exits in +X direction (y = 0 plane)
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import cadquery as cq


def build_simple_ihx(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a simple shell-and-tube IHX. All lengths in mm.

    spec keys
    ─────────
    Lower plenum
        lower_plenum_inner_radius
        lower_plenum_wall
        lower_plenum_height
        lower_plenum_dome_radius

    Upper plenum
        upper_plenum_inner_radius
        upper_plenum_wall
        upper_plenum_height
        upper_plenum_dome_radius

    Tube bundle
        bundle_height
        tube_rings   list of dicts, each describing one circumferential ring:
            n              (int)   number of tubes in this ring
            inner_radius   (float) tube bore radius
            wall           (float) tube wall thickness
            pitch_radius   (float) radial distance from axis to tube centreline
            start_angle_deg (float, optional) first tube angle in degrees (default 0)

        Backward-compatible flat params (used if tube_rings is absent):
            n_tubes, tube_inner_radius, tube_wall, tube_pitch_radius,
            tube_positions (list of (r_mm, theta_deg), overrides uniform ring)

    Central pipe  (vert on axis → 90° arc INSIDE upper plenum → horiz exit +X wall)
        Same pipe_436 construction. Bores through: lower dome, lower top plate,
        upper bottom plate, upper +X wall.

        central_pipe_inner_radius
        central_pipe_wall
        central_pipe_bend_radius    Arc centreline radius inside upper plenum.
        central_pipe_z_offset       Z of bend centre above upper plenum bottom plate.
                                    Constraint: central_pipe_z_offset
                                                + central_pipe_bend_radius < upper_plenum_height
        central_pipe_horiz_len      External horizontal exit length (from outer wall).

    Outlet riser  (independent; straight vert pipe above upper dome)
        riser_inner_radius
        riser_wall
        riser_height

    Lateral pipe  (horizontal, connected to riser +X wall)
        lateral_pipe_inner_radius
        lateral_pipe_wall
        lateral_pipe_length
        lateral_pipe_z_offset       Centreline z above riser base.

    Bundle shell  (optional cylindrical envelope around tube bundle)
        bundle_shell_inner_radius   Inner radius of the wrapper cylinder.
        bundle_shell_wall           Wall thickness.
        bundle_shell_n_bars         Number of vertical bars (= number of windows).
        bundle_shell_bar_width      Arc-length width of each bar at the inner surface.
        bundle_shell_window_height  Height of the window openings.
        bundle_shell_window_z_from_top (optional) Gap from the shell top to the window
                                    top edge. Default 0 (windows flush with top).

    Returns
    -------
    dict with keys: lower_plenum_shell, tube_bundle, upper_plenum_shell,
                    central_pipe, outlet_riser, lateral_pipe,
                    bundle_shell (only if bundle_shell_wall is in spec)
    """

    # ── Unpack ───────────────────────────────────────────────────────────────
    lp_ir, lp_wall = spec["lower_plenum_inner_radius"], spec["lower_plenum_wall"]
    lp_h,  lp_dr   = spec["lower_plenum_height"],       spec["lower_plenum_dome_radius"]

    up_ir, up_wall = spec["upper_plenum_inner_radius"], spec["upper_plenum_wall"]
    up_h,  up_dr   = spec["upper_plenum_height"],       spec["upper_plenum_dome_radius"]
    up_or           = up_ir + up_wall

    bh = float(spec["bundle_height"])

    # ── Tube rings — new API or backward-compat flat params ───────────────────
    if "tube_rings" in spec:
        tube_rings: List[Dict[str, Any]] = spec["tube_rings"]
    else:
        # Build a single ring from flat params
        tube_pos: Optional[List[Tuple[float, float]]] = spec.get("tube_positions")
        n_tubes = int(spec["n_tubes"])
        t_ir    = spec["tube_inner_radius"]
        t_wall  = spec["tube_wall"]
        t_pitch = spec["tube_pitch_radius"]
        if tube_pos is not None:
            positions = [(r * math.cos(math.radians(th)),
                          r * math.sin(math.radians(th))) for r, th in tube_pos]
        else:
            positions = [(t_pitch * math.cos(2 * math.pi * i / n_tubes),
                          t_pitch * math.sin(2 * math.pi * i / n_tubes))
                         for i in range(n_tubes)]
        tube_rings = [dict(inner_radius=t_ir, wall=t_wall,
                           pitch_radius=t_pitch, _xy_pos=positions)]

    cp_ir       = spec["central_pipe_inner_radius"]
    cp_wall_t   = spec["central_pipe_wall"]
    cp_or       = cp_ir + cp_wall_t
    cp_bend     = spec["central_pipe_bend_radius"]
    cp_z        = spec["central_pipe_z_offset"]   # bend centre z above upper plenum bottom
    cp_horiz    = spec["central_pipe_horiz_len"]

    rs_ir   = spec["riser_inner_radius"]
    rs_wall = spec["riser_wall"]
    rs_h    = spec["riser_height"]
    rs_or   = rs_ir + rs_wall

    lat_ir   = spec["lateral_pipe_inner_radius"]
    lat_wall = spec["lateral_pipe_wall"]
    lat_or   = lat_ir + lat_wall
    lat_len  = spec["lateral_pipe_length"]
    lat_z    = spec["lateral_pipe_z_offset"]

    # ── Validation ────────────────────────────────────────────────────────────
    assert cp_z + cp_bend < up_h, (
        f"Central pipe bend exits the upper plenum top. "
        f"Need central_pipe_z_offset + central_pipe_bend_radius < upper_plenum_height "
        f"(currently {cp_z + cp_bend:.1f} >= {up_h})"
    )

    # ── Z layout ──────────────────────────────────────────────────────────────
    z_lp_top = lp_h                 # top plate of lower plenum
    z_up_bot = z_lp_top + bh        # bottom plate of upper plenum
    z_up_top = z_up_bot + up_h      # top of upper plenum cylindrical section
    z_rs_bot = z_up_top + up_dr     # base of outlet riser (above dome tip)

    z_cp_bend   = z_up_bot + cp_z   # world-z of central pipe bend centre
    z_cp_horiz  = z_cp_bend + cp_bend  # world-z of central pipe horizontal section
    z_cp_bot    = z_lp_top             # central pipe starts at top of lower plenum

    # ── Primitive helpers ─────────────────────────────────────────────────────

    def _annular_cyl(ir, wall, h, z_bot):
        cz = z_bot + h / 2
        return (cq.Workplane("XY").workplane(offset=cz).cylinder(h, ir + wall)
                .cut(cq.Workplane("XY").workplane(offset=cz).cylinder(h, ir)).val())

    def _solid_disc(r, h, z_bot):
        cz = z_bot + h / 2
        return cq.Workplane("XY").workplane(offset=cz).cylinder(h, r).val()

    def _dome_shell(dome_r, wall, z_eq, keep_upper):
        outer = cq.Workplane("XY").workplane(offset=z_eq).sphere(dome_r)
        inner = cq.Workplane("XY").workplane(offset=z_eq).sphere(dome_r - wall)
        shell = outer.cut(inner)
        b = dome_r * 4
        cut = (cq.Workplane("XY").workplane(offset=z_eq - dome_r).box(b, b, dome_r * 2)
               if keep_upper else
               cq.Workplane("XY").workplane(offset=z_eq + dome_r).box(b, b, dome_r * 2))
        return shell.cut(cut).val()

    def _fuse(*shapes):
        result = shapes[0]
        for s in shapes[1:]:
            result = result.fuse(s)
        return result

    components: Dict[str, Any] = {}

    # ── Resolve XY positions for every ring ──────────────────────────────────
    def _ring_xy(ring: Dict[str, Any]) -> List[Tuple[float, float]]:
        if "_xy_pos" in ring:          # pre-computed from flat-param fallback
            return ring["_xy_pos"]
        n      = int(ring["n"])
        r      = float(ring["pitch_radius"])
        a0_deg = float(ring.get("start_angle_deg", 0.0))
        return [(r * math.cos(math.radians(a0_deg + 360.0 * i / n)),
                 r * math.sin(math.radians(a0_deg + 360.0 * i / n)))
                for i in range(n)]

    # Flat list of (x, y, outer_radius) for all tubes — used for plate perforations
    all_tubes: List[Tuple[float, float, float]] = [
        (tx, ty, float(ring["inner_radius"]) + float(ring["wall"]))
        for ring in tube_rings
        for tx, ty in _ring_xy(ring)
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # 1. LOWER PLENUM SHELL
    # ─────────────────────────────────────────────────────────────────────────
    lp_sh = _fuse(
        _dome_shell(lp_dr, lp_wall, z_eq=0.0, keep_upper=False),
        _annular_cyl(lp_ir, lp_wall, lp_h, z_bot=0.0),
        _solid_disc(lp_ir, lp_wall, z_bot=z_lp_top - lp_wall),
    )
    # Tube perforations in top plate
    for tx, ty, t_or in all_tubes:
        lp_sh = lp_sh.cut(
            cq.Workplane("XY").workplane(offset=z_lp_top - lp_wall / 2)
            .center(tx, ty).cylinder(lp_wall + 2, t_or).val()
        )
    components["lower_plenum_shell"] = lp_sh

    # ─────────────────────────────────────────────────────────────────────────
    # 2. TUBE BUNDLE
    # ─────────────────────────────────────────────────────────────────────────
    tube_solids = []
    cz = z_lp_top + bh / 2
    for ring in tube_rings:
        r_ir = float(ring["inner_radius"])
        r_or = r_ir + float(ring["wall"])
        for tx, ty in _ring_xy(ring):
            tube_solids.append(
                cq.Workplane("XY").workplane(offset=cz).center(tx, ty).cylinder(bh, r_or)
                .cut(cq.Workplane("XY").workplane(offset=cz).center(tx, ty).cylinder(bh, r_ir))
                .val()
            )
    if tube_solids:
        components["tube_bundle"] = cq.Compound.makeCompound(tube_solids)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BUNDLE SHELL  (optional wrapper cylinder with upper windows)
    # ─────────────────────────────────────────────────────────────────────────
    if "bundle_shell_wall" in spec:
        bs_wall   = float(spec["bundle_shell_wall"])
        bs_ir     = float(spec["bundle_shell_inner_radius"])
        bs_or     = bs_ir + bs_wall
        bs_n_bars = int(spec["bundle_shell_n_bars"])
        bs_bar_w  = float(spec["bundle_shell_bar_width"])    # arc length at inner surface
        bs_win_h  = float(spec["bundle_shell_window_height"])
        bs_win_dz = float(spec.get("bundle_shell_window_z_from_top", 0.0))

        assert bs_n_bars >= 1, "bundle_shell_n_bars must be >= 1"
        bar_half_angle = bs_bar_w / (2.0 * bs_ir)          # radians
        win_half_angle = math.pi / bs_n_bars - bar_half_angle
        assert win_half_angle > 0, (
            f"bundle_shell_bar_width ({bs_bar_w}) leaves no room for windows. "
            "Reduce bar_width or increase n_bars."
        )

        # Shell spans full bundle height: z_lp_top → z_up_bot
        bs_sh = _annular_cyl(bs_ir, bs_wall, bh, z_bot=z_lp_top)

        # Window zone at upper part of shell
        z_win_top = z_up_bot - bs_win_dz
        z_win_bot = z_win_top - bs_win_h
        z_win_cen = (z_win_bot + z_win_top) / 2.0

        # Box cutter: depth through wall, width = chord at outer surface, height = window
        chord = 2.0 * (bs_or + 2.0) * math.sin(win_half_angle)
        depth = bs_wall + 4.0
        x_cen = bs_ir + bs_wall / 2.0   # radial centre of wall

        for i in range(bs_n_bars):
            theta_deg = 360.0 * i / bs_n_bars
            cutter = (
                cq.Workplane("XY")
                .box(depth, chord, bs_win_h + 2.0)
                .translate((x_cen, 0.0, z_win_cen))
                .rotate((0, 0, 0), (0, 0, 1), theta_deg)
                .val()
            )
            bs_sh = bs_sh.cut(cutter)

        components["bundle_shell"] = bs_sh

    # ─────────────────────────────────────────────────────────────────────────
    # 3. UPPER PLENUM SHELL
    # ─────────────────────────────────────────────────────────────────────────
    up_sh = _fuse(
        _solid_disc(up_ir, up_wall, z_bot=z_up_bot),
        _annular_cyl(up_ir, up_wall, up_h, z_bot=z_up_bot),
        _dome_shell(up_dr, up_wall, z_eq=z_up_top, keep_upper=True),
    )
    # Axial bore: outlet riser exits through top dome
    up_sh = up_sh.cut(_solid_disc(rs_or, up_dr * 2 + 2, z_bot=z_up_top - 1))
    # Axial bore: central pipe enters through bottom plate (on axis)
    up_sh = up_sh.cut(_solid_disc(cp_or, up_wall + 2, z_bot=z_up_bot - 1))
    # Horizontal bore: central pipe exits through +X wall (one side only)
    up_sh = up_sh.cut(
        cq.Workplane("YZ").workplane(offset=up_ir - 1)
        .center(0, z_cp_horiz).circle(cp_or).extrude(up_wall + 2).val()
    )
    # Tube perforations in bottom plate
    for tx, ty, t_or in all_tubes:
        up_sh = up_sh.cut(
            cq.Workplane("XY").workplane(offset=z_up_bot + up_wall / 2)
            .center(tx, ty).cylinder(up_wall + 2, t_or).val()
        )
    components["upper_plenum_shell"] = up_sh

    # ─────────────────────────────────────────────────────────────────────────
    # 4. CENTRAL PIPE  (pipe_436 pattern: vert on axis → arc inside UP → horiz)
    # ─────────────────────────────────────────────────────────────────────────
    #
    # Path in XZ plane (same direction as pipe_436: +Z at start → +X at end):
    #
    #   (0, z_cp_bot)   starts at top of lower plenum
    #        │  straight up through bundle region, upper plenum
    #   (0, z_cp_bend)  bend centre inside upper plenum
    #        )  90° arc, radius = cp_bend
    #   (cp_bend, z_cp_horiz)
    #        ─────────────────────────────────────────────►  horizontal exit
    #   (cp_bend + up_or + cp_horiz, z_cp_horiz)
    #
    # Profile: XY at z = z_cp_bot, centred on axis (0, 0). Ring cross-section.

    x_cp_far = cp_bend + up_or + cp_horiz   # far end of horizontal exit

    cp_path = (
        cq.Workplane("XZ")
        .moveTo(0, z_cp_bot)
        .lineTo(0, z_cp_bend)
        .radiusArc((cp_bend, z_cp_horiz), cp_bend)
        .lineTo(x_cp_far, z_cp_horiz)
        .wire().val()
    )
    components["central_pipe"] = (
        cq.Workplane("XY").workplane(offset=z_cp_bot)
        .circle(cp_or).circle(cp_ir)     # ring profile — no boolean cut
        .sweep(cq.Workplane("XY").newObject([cp_path]), isFrenet=True)
        .val()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. OUTLET RISER  (independent; straight vert pipe above upper dome)
    # ─────────────────────────────────────────────────────────────────────────
    cz_rs = z_rs_bot + rs_h / 2
    rs_wp = (
        cq.Workplane("XY").workplane(offset=cz_rs).cylinder(rs_h, rs_or)
        .cut(cq.Workplane("XY").workplane(offset=cz_rs).cylinder(rs_h, rs_ir))
    )
    # Lateral bore: only through +X wall
    rs_wp = rs_wp.cut(
        cq.Workplane("YZ").workplane(offset=rs_ir - 1)
        .center(0, z_rs_bot + lat_z).circle(lat_or).extrude(rs_wall + 2)
    )
    components["outlet_riser"] = rs_wp.val()

    # ─────────────────────────────────────────────────────────────────────────
    # 6. LATERAL PIPE
    # ─────────────────────────────────────────────────────────────────────────
    z_lat_cen = z_rs_bot + lat_z
    components["lateral_pipe"] = (
        cq.Workplane("YZ").workplane(offset=rs_or)
        .center(0, z_lat_cen).circle(lat_or).extrude(lat_len)
        .cut(
            cq.Workplane("YZ").workplane(offset=rs_or)
            .center(0, z_lat_cen).circle(lat_ir).extrude(lat_len)
        ).val()
    )

    return components


# ─── Demo ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_spec = {
        # Lower plenum
        "lower_plenum_inner_radius": 300.0,
        "lower_plenum_wall":          20.0,
        "lower_plenum_height":        200.0,
        "lower_plenum_dome_radius":   320.0,
        # Upper plenum
        "upper_plenum_inner_radius": 300.0,
        "upper_plenum_wall":          20.0,
        "upper_plenum_height":        300.0,
        "upper_plenum_dome_radius":   320.0,
        # Tube bundle — multiple circumferential rings
        "bundle_height": 2000.0,
        "tube_rings": [
            dict(n=6,  inner_radius=12.0, wall=2.0, pitch_radius= 80.0),
            dict(n=12, inner_radius=12.0, wall=2.0, pitch_radius=150.0),
            dict(n=18, inner_radius=10.0, wall=2.0, pitch_radius=220.0),
            dict(n=18, inner_radius=10.0, wall=2.0, pitch_radius=260.0),
        ],
        # Central pipe — on axis, bends inside upper plenum, exits +X wall
        "central_pipe_inner_radius":  60.0,
        "central_pipe_wall":          10.0,
        "central_pipe_bend_radius":   80.0,
        "central_pipe_z_offset":     100.0,  # 100 + 80 = 180 < 300 (up_h) ✓
        "central_pipe_horiz_len":    400.0,
        # Outlet riser — independent, above upper dome
        "riser_inner_radius": 80.0,
        "riser_wall":         10.0,
        "riser_height":      300.0,
        # Lateral pipe
        "lateral_pipe_inner_radius":  40.0,
        "lateral_pipe_wall":           8.0,
        "lateral_pipe_length":        300.0,
        "lateral_pipe_z_offset":      150.0,
        # Bundle shell — wrapper cylinder with windowed upper section
        "bundle_shell_inner_radius": 285.0,   # > outermost tube edge (260+10=270)
        "bundle_shell_wall":          15.0,
        "bundle_shell_n_bars":         8,
        "bundle_shell_bar_width":      20.0,
        "bundle_shell_window_height": 600.0,
    }

    print("Building simple IHX ...")
    parts = build_simple_ihx(demo_spec)
    assembly = cq.Assembly()
    for name, shape in parts.items():
        assembly.add(shape, name=name)
    print("Done — showing in ocp_vscode ...")
    from ocp_vscode import show
    show(assembly)



    # os.makedirs("output_ihx", exist_ok=True)
    # for name, shape in parts.items():
    #     path = f"output_ihx/{name}.step"
    #     cq.exporters.export(shape, path)
    #     print(f"  {path}")
    # print("Done.")

