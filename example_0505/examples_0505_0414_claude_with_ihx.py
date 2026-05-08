# This is the updated versionn of the example 0414_claude that only included reactor and top plate, now with the IHX added in.


# ------------------------ START - FROM THE ORIGINAL EXAMPLE_0414_CLaude.py ------------------------
# All units in metres (divide drawing mm by 1000)
# ⚠ wall_t not explicit in drawing — 0.05 m assumed

from assemble import assemble_objects
from ocp_vscode import show

RPV = {
    "operation":          "primitive",
    "obj_id":             "rpv",
    "obj_type":           "reactor_vessel",
    "inner_d":            8.91,       # OD 9.01 − 2 × 0.05
    "wall_t":             0.05,
    "straight_h":         9.0,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 5.245, "rk": 0.379},
}

TOP_PLATE = {
    "operation": "primitive",
    "obj_id":    "top_plate",
    "obj_type":  "reactor_top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  9.0,          # sits flush on top of straight section
    "hole_groups": [
        {   # central penetration
            "hole_diameter": 2.224,
            "layout":        "explicit_positions",
            "positions":     [(0.0, 0.0)],
        },
        {   # inner ring — 3 × Ø1600 at r = 2730 mm
            "hole_diameter":    1.600,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 2.730,
            "start_angle_deg":  0.0,
        },
        {   # outer ring — 3 × Ø1350 at r = 3369 mm, offset 60°
            "hole_diameter":    1.350,
            "layout":           "symmetric",
            "count":            3,
            "placement_radius": 3.369,
            "start_angle_deg":  60.0,
        },
    ],
}


# ------------------------ END - FROM THE ORIGINAL EXAMPLE_0414_CLaude.py ------------------------

# ── IHX geometry (all values in metres, consistent with reactor scale) ──────
# Hole radius (inner ring) = 1.600 / 2 = 0.800 m
# bundle_shell outer = bundle_shell_inner_radius + bundle_shell_wall = 0.800 m exactly ← snug fit
# Plenum outer radius = 0.760 + 0.025 = 0.785 m < 0.800 m ✓ (clears hole)
# Outermost tube edge = 0.700 + 0.014 + 0.003 = 0.717 m < 0.775 (shell inner) ✓
import math

_IHX_SPEC = {
    # Lower plenum — outer radius 0.785 m, clears 0.800 m hole ✓
    "lower_plenum_inner_radius": 0.760,
    "lower_plenum_wall":          0.025,
    "lower_plenum_height":        0.600,
    "lower_plenum_dome_radius":   0.785,
    # Upper plenum
    "upper_plenum_inner_radius": 0.760,
    "upper_plenum_wall":          0.025,
    "upper_plenum_height":        0.600,
    "upper_plenum_dome_radius":   0.785,
    # Tube bundle — tall, 5 rings filling the shell
    "bundle_height": 6.0,
    "tube_rings": [
        dict(n=8,  inner_radius=0.020, wall=0.003, pitch_radius=0.12),
        dict(n=16, inner_radius=0.018, wall=0.003, pitch_radius=0.25),
        dict(n=24, inner_radius=0.016, wall=0.003, pitch_radius=0.40),
        dict(n=32, inner_radius=0.014, wall=0.003, pitch_radius=0.55),
        dict(n=40, inner_radius=0.014, wall=0.003, pitch_radius=0.70),
    ],
    # Central pipe
    "central_pipe_inner_radius":  0.20,
    "central_pipe_wall":          0.025,
    "central_pipe_bend_radius":   0.25,
    "central_pipe_z_offset":      0.20,   # 0.20 + 0.25 = 0.45 < 0.60 (up_h) ✓
    "central_pipe_horiz_len":     0.60,
    # Outlet riser — must be larger than lateral pipe
    "riser_inner_radius": 0.20,
    "riser_wall":         0.025,
    "riser_height":       0.60,
    # Lateral pipe — smaller bore so it branches cleanly off the riser
    "lateral_pipe_inner_radius":  0.10,
    "lateral_pipe_wall":          0.015,
    "lateral_pipe_length":        0.50,
    "lateral_pipe_z_offset":      0.30,
    # Bundle shell — outer radius = 0.775 + 0.025 = 0.800 m = hole radius ✓
    "bundle_shell_inner_radius": 0.775,
    "bundle_shell_wall":          0.025,
    "bundle_shell_n_bars":         8,
    "bundle_shell_bar_width":      0.030,
    "bundle_shell_window_height":  2.50,
}

# 3 positions from inner ring (r=2.730 m, angles 0° / 120° / 240°)
_r = 2.730
_ihx_positions = [
    ( _r,                                         0.0),
    ( _r * math.cos(math.radians(120)),  _r * math.sin(math.radians(120))),
    ( _r * math.cos(math.radians(240)),  _r * math.sin(math.radians(240))),
]

def _make_ihx(obj_id, x, y, center_z=7.0, rotation_angles=(0.0, 0.0, 0.0)):
    spec = _IHX_SPEC.copy()
    spec.update({
        "operation":    "primitive",
        "obj_id":       obj_id,
        "obj_type":     "ihx",
        "center_coords": (x, y, center_z),
        "rotation_angles": rotation_angles,
    })
    return spec

IHX1 = _make_ihx("ihx_1", *_ihx_positions[0], rotation_angles=(0.0, 0.0, 0.0))
IHX2 = _make_ihx("ihx_2", *_ihx_positions[1], rotation_angles=(0.0, 0.0, 120.0))
IHX3 = _make_ihx("ihx_3", *_ihx_positions[2], rotation_angles=(0.0, 0.0, 240.0))

# ── Reactor core (ESFR design drawing) ──────────────────────────────────────
# Height: 3910 mm from drawing.
# Radius: must not reach the IHX inner edge.
#   IHX inner edge = _r - (bundle_shell_inner_radius + bundle_shell_wall)
#                  = 2.730 - 0.800 = 1.930 m
# The 4284 mm diameter in the drawing is the outer core barrel envelope;
# for a homogenised cylinder model, the active zone fits inside 1.930 m.
# _ihx_shell_outer = _IHX_SPEC["bundle_shell_inner_radius"] + _IHX_SPEC["bundle_shell_wall"]  # 0.800 m
#_core_radius = _r - _ihx_shell_outer - 0.001   # 1 mm clearance to avoid tangent-surface overlap

CORE = {
    "operation": "primitive",
    "obj_id":    "core",
    "obj_type":  "reactor_core",
    "radius":    3600 / 2 / 1000, # 4284 / 2 / 1000,
    "height":    3.910,         # 3910 mm from drawing
    "z_bottom":  1.5,
}

show(assemble_objects([RPV, TOP_PLATE, IHX1, IHX2, IHX3, CORE]))











