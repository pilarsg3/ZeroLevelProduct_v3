import math
from assemble import assemble_objects
from ocp_vscode import show

_SB_Z_BOTTOM       = -1.702
_SB_TOP_Z          = _SB_Z_BOTTOM + 1.242
_DIAGRID_THICKNESS = 1.050
_DIAGRID_Z_BOTTOM  = _SB_TOP_Z
_DIAGRID_TOP_Z     = _DIAGRID_Z_BOTTOM + _DIAGRID_THICKNESS
_CORE_Z_BOTTOM     = _DIAGRID_TOP_Z

_RPV_INNER_D    = 8.91
_RPV_WALL_T     = 0.05
_RPV_STRAIGHT_H = 9.0
_TORI_Rc        = 5.245
_TORI_rk        = 0.379

RPV = {
    "operation":          "primitive",
    "obj_id":             "rpv",
    "obj_type":           "reactor_vessel",
    "inner_d":            _RPV_INNER_D,
    "wall_t":             _RPV_WALL_T,
    "straight_h":         _RPV_STRAIGHT_H,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": _TORI_Rc, "rk": _TORI_rk},
}

_od            = _RPV_INNER_D + 2 * _RPV_WALL_T
_r             = _od / 2
_xk            = _r - _TORI_rk
_zc            = math.sqrt((_TORI_Rc - _TORI_rk)**2 - _xk**2)
_HEAD_BOTTOM_Z = _zc - _TORI_Rc

TOP_PLATE = {
    "operation": "primitive",
    "obj_id":    "top_plate",
    "obj_type":  "reactor_top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  _RPV_STRAIGHT_H,
    "hole_groups": [
        {
            "hole_diameter": 2.224,
            "layout":        "explicit_positions",
            "positions":     [(0.0, 0.0)],
        },
        {
            "hole_diameter":    1.600,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 2.730,
            "start_angle_deg":  0.0,
        },
        {
            "hole_diameter":    1.350,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 3.369,
            "start_angle_deg":  60.0,
        },
    ],
}

_ihx_r = 2.730

def _make_ihx(obj_id: str, angle_deg: float, center_z: float = 7.0) -> dict:
    rad = math.radians(angle_deg)
    return {
        "operation":       "primitive",
        "obj_id":          obj_id,
        "obj_type":        "ihx",
        "center_coords":   (_ihx_r * math.cos(rad), _ihx_r * math.sin(rad), center_z),
        "rotation_angles": (0.0, 0.0, angle_deg),
        "lower_plenum_inner_radius":  0.760,
        "lower_plenum_wall":          0.025,
        "lower_plenum_height":        0.600,
        "lower_plenum_dome_radius":   0.785,
        "upper_plenum_inner_radius":  0.760,
        "upper_plenum_wall":          0.025,
        "upper_plenum_height":        0.600,
        "upper_plenum_dome_radius":   0.785,
        "bundle_height":              6.0,
        "tube_rings": [
            dict(n=8,  inner_radius=0.020, wall=0.003, pitch_radius=0.12),
            dict(n=16, inner_radius=0.018, wall=0.003, pitch_radius=0.25),
            dict(n=24, inner_radius=0.016, wall=0.003, pitch_radius=0.40),
            dict(n=32, inner_radius=0.014, wall=0.003, pitch_radius=0.55),
            dict(n=40, inner_radius=0.014, wall=0.003, pitch_radius=0.70),
        ],
        "central_pipe_inner_radius":  0.20,
        "central_pipe_wall":          0.025,
        "central_pipe_bend_radius":   0.25,
        "central_pipe_z_offset":      0.20,
        "central_pipe_horiz_len":     0.60,
        "riser_inner_radius":         0.20,
        "riser_wall":                 0.025,
        "riser_height":               0.60,
        "lateral_pipe_inner_radius":  0.10,
        "lateral_pipe_wall":          0.015,
        "lateral_pipe_length":        0.50,
        "lateral_pipe_z_offset":      0.30,
        "bundle_shell_inner_radius":  0.775,
        "bundle_shell_wall":          0.025,
        "bundle_shell_n_bars":        8,
        "bundle_shell_bar_width":     0.030,
        "bundle_shell_window_height": 2.50,
    }

IHX1 = _make_ihx("ihx_1",   0.0)
IHX2 = _make_ihx("ihx_2", 120.0)
IHX3 = _make_ihx("ihx_3", 240.0)

_PUMP_BARREL_HEIGHT = 12.0
_PUMP_Z_BOTTOM      = _HEAD_BOTTOM_Z + 2.562
_PUMP_CENTER_Z      = _PUMP_Z_BOTTOM + _PUMP_BARREL_HEIGHT / 2
_pump_r             = 3.369

def _make_pump(obj_id: str, angle_deg: float) -> dict:
    rad = math.radians(angle_deg)
    return {
        "operation":       "primitive",
        "obj_id":          obj_id,
        "obj_type":        "primary_pump",
        "rotation_angles": (0.0, 0.0, angle_deg - 90.0),
        "center_coords":   (_pump_r * math.cos(rad), _pump_r * math.sin(rad), _PUMP_CENTER_Z),
        "barrel_radius":   1.350 / 2,
        "barrel_wall_t":   0.040,
        "barrel_height":   _PUMP_BARREL_HEIGHT,
        "nozzle_r_pipe":   0.460 / 2,
        "nozzle_wall_t":   0.025,
        "nozzle_L_leg":    0.600,
        "nozzle_R_bend":   0.460,
        "nozzle_arc_deg":  105.0,
        "nozzle_L_inlet":  0.050,
        "nozzle_z":        0.350,
        "flange_width":    0.548,
        "flange_height":   0.900,
        "flange_depth":    0.500,
    }

PUMP1 = _make_pump("pump_1",  60.0)
PUMP2 = _make_pump("pump_2", 180.0)
PUMP3 = _make_pump("pump_3", 300.0)

# ── Diagrid nozzle boss angles ────────────────────────────────────────────────
def _nozzle_boss_angles() -> list[float]:
    arc_rad   = math.radians(105.0)
    L_leg     = 0.600;  L_inlet = 0.050;  R_bend = 0.460
    barrel_r  = 1.350 / 2
    overshoot = 0.040 * 1.5
    ex  = R_bend * (1.0 - math.cos(arc_rad)) + L_leg * math.sin(arc_rad)
    ey  = L_inlet + R_bend * math.sin(arc_rad) + L_leg * math.cos(arc_rad)
    lx  = ey + (barrel_r - overshoot)
    ly  = -ex
    phi = math.degrees(math.atan2(lx, _pump_r + ly))  # ≈ 23.4°
    angles = []
    for a in [60.0, 180.0, 300.0]:
        angles.append(a - phi)   # right nozzle
        angles.append(a + phi)   # left  nozzle
    return angles

_NOZZLE_BOSS_ANGLES = _nozzle_boss_angles()
_PUMP_NOZZLE_Z_ABS  = _PUMP_Z_BOTTOM + 0.350   # ≈ +0.247 m

DIAGRID = {
    "operation":              "primitive",
    "obj_id":                 "diagrid",
    "obj_type":               "diagrid",
    "diameter":               4.660,
    "thickness":              _DIAGRID_THICKNESS,
    "z_bottom":               _DIAGRID_Z_BOTTOM,
    "nozzle_boss_angles_deg": _NOZZLE_BOSS_ANGLES,
    "nozzle_z_abs":           _PUMP_NOZZLE_Z_ABS,
    "nozzle_r_bore":          0.230,
    "nozzle_depth":           0.300,
    "nozzle_r_boss":          0.301,
    "nozzle_boss_height":     0.080,
}

CORE = {
    "operation": "primitive",
    "obj_id":    "core",
    "obj_type":  "reactor_core",
    "radius":    3.600 / 2,
    "height":    3.910,
    "z_bottom":  _CORE_Z_BOTTOM,
}

STRONGBACK = {
    "operation":              "primitive",
    "obj_id":                 "strongback",
    "obj_type":               "strongback",
    "total_height":           1.242,
    "flange_radius":          2.684,
    "skirt_outer_radius":     3.030,
    "skirt_inner_radius":     2.243,
    "skirt_height":           0.436,
    "taper_bottom_z":         0.356,
    "bore_radius":            0.303,
    "small_hole_radius":      0.0755,
    "small_hole_count":       6,
    "small_hole_placement_r": 0.900,
    "z_bottom":               _SB_Z_BOTTOM,
}

show(assemble_objects([
    RPV,
    TOP_PLATE,
    IHX1, IHX2, IHX3,
    PUMP1, PUMP2, PUMP3,
    DIAGRID,
    CORE,
    STRONGBACK,
]))






"""
# RPV + top plate + IHX × 3 + pump × 3 + core + strongback — all through assemble_objects()

import math
from assemble import assemble_objects
from ocp_vscode import show

_SB_Z_BOTTOM   = -1.702   # outer skirt rests on torispherical head at r=3.030 m
_CORE_Z_BOTTOM = _SB_Z_BOTTOM + 1.242   # = -0.460 m

# ── Reactor pressure vessel ───────────────────────────────────────────────────
_RPV_INNER_D    = 8.91
_RPV_WALL_T     = 0.05
_RPV_STRAIGHT_H = 9.0
_TORI_Rc        = 5.245
_TORI_rk        = 0.379

RPV = {
    "operation":          "primitive",
    "obj_id":             "rpv",
    "obj_type":           "reactor_vessel",
    "inner_d":            _RPV_INNER_D,
    "wall_t":             _RPV_WALL_T,
    "straight_h":         _RPV_STRAIGHT_H,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": _TORI_Rc, "rk": _TORI_rk},
}

# Compute z of the very bottom (pole) of the torispherical outer head.
# Rim sits at z=0; head extends downward (z < 0).
#   zc  = sqrt((Rc - rk)^2 - (r - rk)^2)   ← depth of crown centre
#   pole z = zc - Rc                         (negative)
_od            = _RPV_INNER_D + 2 * _RPV_WALL_T           # 9.01 m
_r             = _od / 2                                    # 4.505 m
_xk            = _r - _TORI_rk                             # 4.126 m
_zc            = math.sqrt((_TORI_Rc - _TORI_rk)**2 - _xk**2)   # ≈ 2.580 m
_HEAD_BOTTOM_Z = _zc - _TORI_Rc                            # ≈ -2.665 m

# ── Top plate ─────────────────────────────────────────────────────────────────
TOP_PLATE = {
    "operation": "primitive",
    "obj_id":    "top_plate",
    "obj_type":  "reactor_top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  _RPV_STRAIGHT_H,
    "hole_groups": [
        {
            "hole_diameter": 2.224,
            "layout":        "explicit_positions",
            "positions":     [(0.0, 0.0)],
        },
        {
            "hole_diameter":    1.600,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 2.730,
            "start_angle_deg":  0.0,
        },
        {
            "hole_diameter":    1.350,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 3.369,
            "start_angle_deg":  60.0,
        },
    ],
}

# ── IHX ───────────────────────────────────────────────────────────────────────
_ihx_r = 2.730

def _make_ihx(obj_id: str, angle_deg: float, center_z: float = 7.0) -> dict:
    rad = math.radians(angle_deg)
    return {
        "operation":       "primitive",
        "obj_id":          obj_id,
        "obj_type":        "ihx",
        "center_coords":   (_ihx_r * math.cos(rad), _ihx_r * math.sin(rad), center_z),
        "rotation_angles": (0.0, 0.0, angle_deg),
        # geometry
        "lower_plenum_inner_radius":  0.760,
        "lower_plenum_wall":          0.025,
        "lower_plenum_height":        0.600,
        "lower_plenum_dome_radius":   0.785,
        "upper_plenum_inner_radius":  0.760,
        "upper_plenum_wall":          0.025,
        "upper_plenum_height":        0.600,
        "upper_plenum_dome_radius":   0.785,
        "bundle_height":              6.0,
        "tube_rings": [
            dict(n=8,  inner_radius=0.020, wall=0.003, pitch_radius=0.12),
            dict(n=16, inner_radius=0.018, wall=0.003, pitch_radius=0.25),
            dict(n=24, inner_radius=0.016, wall=0.003, pitch_radius=0.40),
            dict(n=32, inner_radius=0.014, wall=0.003, pitch_radius=0.55),
            dict(n=40, inner_radius=0.014, wall=0.003, pitch_radius=0.70),
        ],
        "central_pipe_inner_radius":  0.20,
        "central_pipe_wall":          0.025,
        "central_pipe_bend_radius":   0.25,
        "central_pipe_z_offset":      0.20,
        "central_pipe_horiz_len":     0.60,
        "riser_inner_radius":         0.20,
        "riser_wall":                 0.025,
        "riser_height":               0.60,
        "lateral_pipe_inner_radius":  0.10,
        "lateral_pipe_wall":          0.015,
        "lateral_pipe_length":        0.50,
        "lateral_pipe_z_offset":      0.30,
        "bundle_shell_inner_radius":  0.775,
        "bundle_shell_wall":          0.025,
        "bundle_shell_n_bars":        8,
        "bundle_shell_bar_width":     0.030,
        "bundle_shell_window_height": 2.50,
    }

IHX1 = _make_ihx("ihx_1",   0.0)
IHX2 = _make_ihx("ihx_2", 120.0)
IHX3 = _make_ihx("ihx_3", 240.0)

# ── Primary pumps ─────────────────────────────────────────────────────────────
# ROTATION: flange faces radially outward → rotation_angles = (0, 0, angle_deg − 90).
# AXIAL:    pump bottom 2562 mm above torispherical head bottom.
#   _HEAD_BOTTOM_Z ≈ −2.665 m  →  pump z_bottom ≈ −0.103 m
#   pump centroid z = pump z_bottom + barrel_height / 2 ≈ 5.897 m
# flange_z_top omitted — auto-computed as barrel_height - 0.5 inside create_primary_pump.

_PUMP_BARREL_HEIGHT = 12.0
_PUMP_Z_BOTTOM      = _HEAD_BOTTOM_Z + 2.562              # ≈ -0.103 m
_PUMP_CENTER_Z      = _PUMP_Z_BOTTOM + _PUMP_BARREL_HEIGHT / 2   # ≈  5.897 m
_pump_r             = 3.369

def _make_pump(obj_id: str, angle_deg: float) -> dict:
    rad = math.radians(angle_deg)
    return {
        "operation":       "primitive",
        "obj_id":          obj_id,
        "obj_type":        "primary_pump",
        "rotation_angles": (0.0, 0.0, angle_deg - 90.0),
        "center_coords":   (_pump_r * math.cos(rad), _pump_r * math.sin(rad), _PUMP_CENTER_Z),
        # geometry
        "barrel_radius":   1.350 / 2,
        "barrel_wall_t":   0.040,
        "barrel_height":   _PUMP_BARREL_HEIGHT,
        "nozzle_r_pipe":   0.460 / 2,
        "nozzle_wall_t":   0.025,
        "nozzle_L_leg":    0.800,
        "nozzle_R_bend":   0.800,
        "nozzle_arc_deg":  112.5,
        "nozzle_z":        0.450,
        "flange_width":    0.548,
        "flange_height":   0.900,
        "flange_depth":    0.500,
    }

PUMP1 = _make_pump("pump_1",  60.0)
PUMP2 = _make_pump("pump_2", 180.0)
PUMP3 = _make_pump("pump_3", 300.0)

# ── Reactor core ──────────────────────────────────────────────────────────────
CORE = {
    "operation": "primitive",
    "obj_id":    "core",
    "obj_type":  "reactor_core",
    "radius":    3.600 / 2,
    "height":    3.910,
    "z_bottom":  _CORE_Z_BOTTOM,
}

# ── Strongback ────────────────────────────────────────────────────────────────
STRONGBACK = {
    "operation":          "primitive",
    "obj_id":             "strongback",
    "obj_type":           "strongback",
    "total_height":       1.242,
    "flange_radius":      2.684,
    "skirt_outer_radius": 3.030,
    "skirt_inner_radius": 2.243,
    "skirt_height":       0.436,
    "taper_bottom_z":     0.356,
    "bore_radius":            0.303,
    "small_hole_radius":      0.0755,
    "small_hole_count":       6,
    "small_hole_placement_r": 0.900,
    "z_bottom":           _SB_Z_BOTTOM,
}

# ── Assemble ──────────────────────────────────────────────────────────────────
show(assemble_objects([
    RPV,
    TOP_PLATE,
    IHX1, IHX2, IHX3,
    PUMP1, PUMP2, PUMP3,
    CORE,
    STRONGBACK,
]))
"""

























































































































































































# # RPV + top plate + IHX × 3 + pump × 3 + core + strongback — all through assemble_objects()

# import math
# from assemble import assemble_objects
# from ocp_vscode import show

# _SB_Z_BOTTOM   = -1.702   # outer skirt rests on torispherical head at r=3.030 m
# _CORE_Z_BOTTOM = _SB_Z_BOTTOM + 1.242   # = -0.460 m

# # ── Reactor pressure vessel ───────────────────────────────────────────────────
# _RPV_INNER_D    = 8.91
# _RPV_WALL_T     = 0.05
# _RPV_STRAIGHT_H = 9.0
# _TORI_Rc        = 5.245
# _TORI_rk        = 0.379

# RPV = {
#     "operation":          "primitive",
#     "obj_id":             "rpv",
#     "obj_type":           "reactor_vessel",
#     "inner_d":            _RPV_INNER_D,
#     "wall_t":             _RPV_WALL_T,
#     "straight_h":         _RPV_STRAIGHT_H,
#     "bottom_head_type":   "torispherical",
#     "bottom_head_params": {"Rc": _TORI_Rc, "rk": _TORI_rk},
# }

# # Compute z of the very bottom (pole) of the torispherical outer head.
# # Rim sits at z=0; head extends downward (z < 0).
# #   zc  = sqrt((Rc - rk)^2 - (r - rk)^2)   ← depth of crown centre
# #   pole z = zc - Rc                         (negative)
# _od            = _RPV_INNER_D + 2 * _RPV_WALL_T           # 9.01 m
# _r             = _od / 2                                    # 4.505 m
# _xk            = _r - _TORI_rk                             # 4.126 m
# _zc            = math.sqrt((_TORI_Rc - _TORI_rk)**2 - _xk**2)   # ≈ 2.580 m
# _HEAD_BOTTOM_Z = _zc - _TORI_Rc                            # ≈ -2.665 m

# # ── Top plate ─────────────────────────────────────────────────────────────────
# # Hole groups:
# #   - centre bore Ø2.224 (control rods / instrumentation column)
# #   - 3 × Ø1.600 at r=2.730, 0°/120°/240°   → IHX penetrations
# #   - 3 × Ø1.350 at r=3.369, 60°/180°/300°  → primary pump penetrations
# TOP_PLATE = {
#     "operation": "primitive",
#     "obj_id":    "top_plate",
#     "obj_type":  "reactor_top_plate",
#     "outer_d":   10.0,
#     "thickness": 0.5,
#     "z_bottom":  _RPV_STRAIGHT_H,
#     "hole_groups": [
#         {
#             "hole_diameter": 2.224,
#             "layout":        "explicit_positions",
#             "positions":     [(0.0, 0.0)],
#         },
#         {
#             "hole_diameter":    1.600,
#             "layout":           "symmetric",
#             "count":            3,
#             "placement_radius": 2.730,
#             "start_angle_deg":  0.0,
#         },
#         {
#             "hole_diameter":    1.350,
#             "layout":           "symmetric",
#             "count":            3,
#             "placement_radius": 3.369,
#             "start_angle_deg":  60.0,
#         },
#     ],
# }

# # ── IHX ───────────────────────────────────────────────────────────────────────
# _IHX_SPEC = {
#     "lower_plenum_inner_radius":  0.760,
#     "lower_plenum_wall":          0.025,
#     "lower_plenum_height":        0.600,
#     "lower_plenum_dome_radius":   0.785,
#     "upper_plenum_inner_radius":  0.760,
#     "upper_plenum_wall":          0.025,
#     "upper_plenum_height":        0.600,
#     "upper_plenum_dome_radius":   0.785,
#     "bundle_height": 6.0,
#     "tube_rings": [
#         dict(n=8,  inner_radius=0.020, wall=0.003, pitch_radius=0.12),
#         dict(n=16, inner_radius=0.018, wall=0.003, pitch_radius=0.25),
#         dict(n=24, inner_radius=0.016, wall=0.003, pitch_radius=0.40),
#         dict(n=32, inner_radius=0.014, wall=0.003, pitch_radius=0.55),
#         dict(n=40, inner_radius=0.014, wall=0.003, pitch_radius=0.70),
#     ],
#     "central_pipe_inner_radius":  0.20,
#     "central_pipe_wall":          0.025,
#     "central_pipe_bend_radius":   0.25,
#     "central_pipe_z_offset":      0.20,
#     "central_pipe_horiz_len":     0.60,
#     "riser_inner_radius":         0.20,
#     "riser_wall":                 0.025,
#     "riser_height":               0.60,
#     "lateral_pipe_inner_radius":  0.10,
#     "lateral_pipe_wall":          0.015,
#     "lateral_pipe_length":        0.50,
#     "lateral_pipe_z_offset":      0.30,
#     "bundle_shell_inner_radius":  0.775,
#     "bundle_shell_wall":          0.025,
#     "bundle_shell_n_bars":        8,
#     "bundle_shell_bar_width":     0.030,
#     "bundle_shell_window_height": 2.50,
# }

# _ihx_r = 2.730
# _ihx_positions = [
#     ( _ihx_r,                                              0.0),
#     ( _ihx_r * math.cos(math.radians(120)), _ihx_r * math.sin(math.radians(120))),
#     ( _ihx_r * math.cos(math.radians(240)), _ihx_r * math.sin(math.radians(240))),
# ]

# def _make_ihx(obj_id, x, y, center_z=7.0, rotation_angles=(0.0, 0.0, 0.0)):
#     spec = _IHX_SPEC.copy()
#     spec.update({
#         "operation":       "primitive",
#         "obj_id":          obj_id,
#         "obj_type":        "ihx",
#         "center_coords":   (x, y, center_z),
#         "rotation_angles": rotation_angles,
#     })
#     return spec

# IHX1 = _make_ihx("ihx_1", *_ihx_positions[0], rotation_angles=(0.0, 0.0,   0.0))
# IHX2 = _make_ihx("ihx_2", *_ihx_positions[1], rotation_angles=(0.0, 0.0, 120.0))
# IHX3 = _make_ihx("ihx_3", *_ihx_positions[2], rotation_angles=(0.0, 0.0, 240.0))

# # ── Primary pumps ─────────────────────────────────────────────────────────────
# # Three pumps at r=3.369 m, angles 60°/180°/300° (between the IHX slots).
# #
# # ROTATION — derivation:
# #   Default build: flange on pump's local +Y, J-bend legs pointing in local -Y.
# #   Goal: flange faces radially outward at angular position θ, i.e. pump's +Y
# #         must align with the global radial direction (cos θ, sin θ).
# #   Z-rotation by φ maps pump's +Y → (-sin φ, cos φ) in global frame.
# #   Solving (-sin φ, cos φ) = (cos θ, sin θ)  →  φ = θ − 90°.
# #   Therefore: rotation_angles = (0, 0, angle_deg − 90).
# #
# # AXIAL POSITION:
# #   Pump bottom must sit 2562 mm above the bottom of the torispherical head.
# #   Head bottom z  = _HEAD_BOTTOM_Z  ≈ −2.665 m  (computed above from Rc, rk)
# #   Pump z_bottom  = _HEAD_BOTTOM_Z + 2.562      ≈ −0.103 m
# #   Pump centroid z = pump z_bottom + barrel_height / 2

# _PUMP_BARREL_HEIGHT = 12.0
# _PUMP_Z_BOTTOM      = _HEAD_BOTTOM_Z + 2.562              # ≈ -0.103 m
# _PUMP_CENTER_Z      = _PUMP_Z_BOTTOM + _PUMP_BARREL_HEIGHT / 2   # ≈  3.397 m

# _PUMP_SPEC: dict = dict(
#     barrel_radius  = 1.350 / 2,
#     barrel_wall_t  = 0.040,
#     barrel_height  = _PUMP_BARREL_HEIGHT,
#     nozzle_r_pipe  = 0.460 / 2,
#     nozzle_wall_t  = 0.025,
#     nozzle_L_leg   = 0.800,
#     nozzle_R_bend  = 0.800,
#     nozzle_arc_deg = 112.5,
#     nozzle_z       = 0.450,
#     flange_width   = 0.548,
#     flange_height  = 0.900,
#     flange_depth   = 0.500,
#     flange_z_top   = _PUMP_BARREL_HEIGHT - 0.500,   # 0.5 m below barrel top
#     z_bottom       = 0.0,   # axial positioning handled via center_coords below
# )

# _pump_r      = 3.369
# _pump_angles = [60.0, 180.0, 300.0]   # degrees — interleaved between the IHX slots

# def _make_pump(obj_id: str, angle_deg: float) -> dict:
#     """Return an assemble_objects spec for one primary pump."""
#     rad = math.radians(angle_deg)
#     x   = _pump_r * math.cos(rad)
#     y   = _pump_r * math.sin(rad)
#     spec: dict = _PUMP_SPEC.copy()
#     spec.update({
#         "operation":       "primitive",
#         "obj_id":          obj_id,
#         "obj_type":        "primary_pump",
#         "rotation_angles": (0.0, 0.0, angle_deg - 90.0),
#         "center_coords":   (x, y, _PUMP_CENTER_Z),
#     })
#     return spec

# PUMP1 = _make_pump("pump_1", _pump_angles[0])
# PUMP2 = _make_pump("pump_2", _pump_angles[1])
# PUMP3 = _make_pump("pump_3", _pump_angles[2])

# # ── Reactor core ──────────────────────────────────────────────────────────────
# CORE = {
#     "operation": "primitive",
#     "obj_id":    "core",
#     "obj_type":  "reactor_core",
#     "radius":    3.600 / 2,
#     "height":    3.910,
#     "z_bottom":  _CORE_Z_BOTTOM,
# }

# # ── Strongback ────────────────────────────────────────────────────────────────
# STRONGBACK = {
#     "operation": "primitive",
#     "obj_id":    "strongback",
#     "obj_type":  "strongback",
#     "z_bottom":  _SB_Z_BOTTOM,
# }

# # ── Assemble ──────────────────────────────────────────────────────────────────
# show(assemble_objects([
#     RPV,
#     TOP_PLATE,
#     IHX1, IHX2, IHX3,
#     PUMP1, PUMP2, PUMP3,
#     CORE,
#     STRONGBACK,
# ]))