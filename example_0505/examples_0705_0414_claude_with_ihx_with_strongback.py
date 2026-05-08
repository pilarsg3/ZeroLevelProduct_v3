# RPV + top plate + IHX × 3 + core + strongback — all through assemble_objects()

import math
from assemble import assemble_objects
from ocp_vscode import show

_SB_Z_BOTTOM   = -1.702   # outer skirt rests on torispherical head at r=3.030 m
_CORE_Z_BOTTOM = _SB_Z_BOTTOM + 1.242   # = -0.460 m

# ── Reactor pressure vessel ───────────────────────────────────────────────────
RPV = {
    "operation":          "primitive",
    "obj_id":             "rpv",
    "obj_type":           "reactor_vessel",
    "inner_d":            8.91,
    "wall_t":             0.05,
    "straight_h":         9.0,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 5.245, "rk": 0.379},
}

# ── Top plate ─────────────────────────────────────────────────────────────────
TOP_PLATE = {
    "operation": "primitive",
    "obj_id":    "top_plate",
    "obj_type":  "reactor_top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  9.0,
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
_IHX_SPEC = {
    "lower_plenum_inner_radius":  0.760,
    "lower_plenum_wall":          0.025,
    "lower_plenum_height":        0.600,
    "lower_plenum_dome_radius":   0.785,
    "upper_plenum_inner_radius":  0.760,
    "upper_plenum_wall":          0.025,
    "upper_plenum_height":        0.600,
    "upper_plenum_dome_radius":   0.785,
    "bundle_height": 6.0,
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

_r = 2.730
_ihx_positions = [
    ( _r,                                        0.0),
    ( _r * math.cos(math.radians(120)), _r * math.sin(math.radians(120))),
    ( _r * math.cos(math.radians(240)), _r * math.sin(math.radians(240))),
]

def _make_ihx(obj_id, x, y, center_z=7.0, rotation_angles=(0.0, 0.0, 0.0)):
    spec = _IHX_SPEC.copy()
    spec.update({
        "operation":       "primitive",
        "obj_id":          obj_id,
        "obj_type":        "ihx",
        "center_coords":   (x, y, center_z),
        "rotation_angles": rotation_angles,
    })
    return spec

IHX1 = _make_ihx("ihx_1", *_ihx_positions[0], rotation_angles=(0.0, 0.0,   0.0))
IHX2 = _make_ihx("ihx_2", *_ihx_positions[1], rotation_angles=(0.0, 0.0, 120.0))
IHX3 = _make_ihx("ihx_3", *_ihx_positions[2], rotation_angles=(0.0, 0.0, 240.0))

# ── Reactor core ──────────────────────────────────────────────────────────────
CORE = {
    "operation": "primitive",
    "obj_id":    "core",
    "obj_type":  "reactor_core",
    "radius":    3.600 / 2,
    "height":    3.910,
    "z_bottom":  _CORE_Z_BOTTOM,
}

# ── Strongback — now through the pipeline like everything else ────────────────
STRONGBACK = {
    "operation": "primitive",
    "obj_id":    "strongback",
    "obj_type":  "strongback",
    "z_bottom":  _SB_Z_BOTTOM,
}

show(assemble_objects([RPV, TOP_PLATE, IHX1, IHX2, IHX3, CORE, STRONGBACK]))