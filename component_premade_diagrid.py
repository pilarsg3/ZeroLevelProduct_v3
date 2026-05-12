"""
Parametric diagrid — ZLP V6.
"""

from __future__ import annotations
import math
import cadquery as cq


def create_diagrid(
    diameter:               float,
    thickness:              float,
    z_bottom:               float = 0.0,
    nozzle_boss_angles_deg: list[float] | None = None,
    nozzle_z_abs:           float | None = None,
    nozzle_r_bore:          float = 0.230,
    nozzle_depth:           float = 0.300,
    nozzle_r_boss:          float = 0.301,
    nozzle_boss_height:     float = 0.080,
) -> cq.Workplane:

    if diameter <= 0 or thickness <= 0:
        raise ValueError("diameter and thickness must be > 0")

    radius = diameter / 2.0
    z_top  = z_bottom + thickness

    disc = (cq.Workplane("XY")
            .workplane(offset=z_bottom)
            .circle(radius)
            .extrude(thickness))

    if nozzle_boss_angles_deg and nozzle_z_abs is not None:

        margin = nozzle_r_boss
        if not (z_bottom + margin < nozzle_z_abs < z_top - margin):
            raise ValueError(
                f"nozzle_z_abs={nozzle_z_abs:.4f} m clips the diagrid face. "
                f"Must be in ({z_bottom + margin:.4f}, {z_top - margin:.4f})."
            )

        for theta in nozzle_boss_angles_deg:
            rad = math.radians(theta)

            ox = radius * math.cos(rad)
            oy = radius * math.sin(rad)

            outward = cq.Vector( math.cos(rad),  math.sin(rad), 0.0)
            inward  = cq.Vector(-math.cos(rad), -math.sin(rad), 0.0)
            tangent = cq.Vector(-math.sin(rad),  math.cos(rad), 0.0)
            origin  = cq.Vector(ox, oy, nozzle_z_abs)

            # Boss protruding outward
            boss_plane = cq.Plane(origin=origin, xDir=tangent, normal=outward)
            boss = (cq.Workplane(boss_plane)
                    .circle(nozzle_r_boss)
                    .extrude(nozzle_boss_height))
            disc = disc.union(boss)

            # Bore inward through boss and into diagrid body
            bore_origin = origin + outward.multiply(nozzle_boss_height)
            bore_plane  = cq.Plane(origin=bore_origin, xDir=tangent, normal=inward)
            bore = (cq.Workplane(bore_plane)
                    .circle(nozzle_r_bore)
                    .extrude(nozzle_boss_height + nozzle_depth))
            disc = disc.cut(bore)

    return disc.clean()


if __name__ == "__main__":
    from ocp_vscode import show

    _RPV_INNER_D = 8.91;  _RPV_WALL_T = 0.05
    _TORI_Rc = 5.245;     _TORI_rk = 0.379
    _od = _RPV_INNER_D + 2 * _RPV_WALL_T
    _r  = _od / 2
    _xk = _r - _TORI_rk
    _zc = math.sqrt((_TORI_Rc - _TORI_rk)**2 - _xk**2)
    _HEAD_BOTTOM_Z    = _zc - _TORI_Rc
    _PUMP_Z_BOTTOM    = _HEAD_BOTTOM_Z + 2.562
    _DIAGRID_Z_BOTTOM = -1.702 + 1.242
    _pump_r           = 3.369

    arc_rad   = math.radians(105.0)
    L_leg     = 0.600; L_inlet = 0.050; R_bend = 0.460
    barrel_r  = 1.350 / 2
    overshoot = 0.040 * 1.5
    ex  = R_bend * (1.0 - math.cos(arc_rad)) + L_leg * math.sin(arc_rad)
    ey  = L_inlet + R_bend * math.sin(arc_rad) + L_leg * math.cos(arc_rad)
    lx  = ey + (barrel_r - overshoot)
    ly  = -ex
    phi = math.degrees(math.atan2(lx, _pump_r + ly))

    boss_angles = []
    for a in [60.0, 180.0, 300.0]:
        boss_angles.append(a - phi)
        boss_angles.append(a + phi)

    diagrid = create_diagrid(
        diameter               = 4.660,
        thickness              = 1.050,
        z_bottom               = _DIAGRID_Z_BOTTOM,
        nozzle_boss_angles_deg = boss_angles,
        nozzle_z_abs           = _PUMP_Z_BOTTOM + 0.350,
        nozzle_r_bore          = 0.230,
        nozzle_depth           = 0.300,
        nozzle_r_boss          = 0.301,
        nozzle_boss_height     = 0.080,
    )
    show(diagrid)







# """
# Parametric diagrid — ZLP V3.

# The diagrid is a horizontal disc that supports the reactor core assemblies
# in an SFR. Geometrically it's a flat cylindrical plate.

# All dimensions must be provided explicitly.

# Single public function:
#     create_diagrid()  — returns a single cq.Workplane solid
# """

# from __future__ import annotations
# import cadquery as cq


# def create_diagrid(
#     diameter:  float,
#     thickness: float,
#     z_bottom:  float = 0.0,
# ) -> cq.Workplane:
#     """
#     Build the diagrid as a flat cylindrical disc.

#     Args:
#         diameter:  outer diameter [m]
#         thickness: axial thickness [m]
#         z_bottom:  z coordinate of the bottom face [m] (default 0)

#     Returns:
#         cq.Workplane — disc with bottom face at z_bottom
#     """
#     if diameter <= 0:
#         raise ValueError(f"diameter must be > 0, got {diameter}")
#     if thickness <= 0:
#         raise ValueError(f"thickness must be > 0, got {thickness}")

#     return (cq.Workplane("XY")
#             .workplane(offset=z_bottom)
#             .circle(diameter / 2.0)
#             .extrude(thickness))


# # ---------------------------------------------------------------------------
# # Example
# # ---------------------------------------------------------------------------

# if __name__ == "__main__":
#     from ocp_vscode import show
#     diagrid = create_diagrid(
#         diameter  = 4.660,
#         thickness = 1.050,
#         z_bottom  = 0.0,
#     )
#     show(diagrid)


