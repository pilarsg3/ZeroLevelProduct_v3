"""
examples_reactor_core.py — design variant examples for create_active_zone and create_reactor_core.

Run from project root:
    python examples/examples_reactor_core.py

Covers all 6 meaningful radial configurations (A–D for full core, plus active-zone-only variants).
"""

import time
from ocp_vscode import show, set_defaults
from component_premade_reactor_core import create_active_zone, create_reactor_core

set_defaults(reset_camera=True)

# Shared geometry (ESFR-SMART-like)
BARREL_IR   = 1.65    # barrel inner radius [m]
BARREL_T    = 0.05    # barrel wall thickness [m]
BARREL_H    = 2.60    # total barrel height [m]
BARREL_Z    = -1.30   # barrel z bottom [m]

R_INNER     = 0.86    # inner fuel zone radius [m]
R_OUTER     = 1.28    # outer fuel zone radius [m]
R_BLANKET   = 1.54    # radial blanket outer radius [m]

LP_H  = 0.50   # lower plenum height [m]
ABB_H = 0.30   # axial blanket bottom height [m]
ACT_H = 1.00   # active height [m]
ABT_H = 0.30   # axial blanket top height [m]
UP_H  = 0.50   # upper plenum height [m]

COLORS = {
    "active_inner":               "red",
    "active_outer":               "orange",
    "radial_blanket":             "green",
    "radial_blanket_active":      "green",
    "radial_blanket_bottom":      "green",
    "radial_blanket_top":         "green",
    "sodium_bypass":              "cyan",
    "sodium_bypass_active":       "cyan",
    "sodium_bypass_bottom":       "cyan",
    "sodium_bypass_top":          "cyan",
    "axial_blanket_bottom_inner": "lime",
    "axial_blanket_top_inner":    "lime",
    "lower_plenum":               "blue",
    "upper_plenum":               "blue",
    "core_barrel":                "gray",
}


def display(zones: dict, title: str) -> None:
    print(f"\n{title}")
    print("  zones:", list(zones.keys()))
    show({k: (v, COLORS.get(k, "white")) for k, v in zones.items()})
    time.sleep(3)


# ===========================================================================
# ACTIVE ZONE ONLY — create_active_zone()
# ===========================================================================

# A-az: 1-zone fuel, no blanket, no bypass
display(
    create_active_zone(
        r_outer_core=BARREL_IR,
        r_radial_blanket=BARREL_IR,
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        active_h=ACT_H,
        r_inner_core=None,
    ),
    "A-az: active zone only — 1-zone fuel, no blanket, no bypass",
)

# B-az: 1-zone fuel, radial blanket, no bypass
display(
    create_active_zone(
        r_outer_core=R_OUTER,
        r_radial_blanket=BARREL_IR,
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        active_h=ACT_H,
        r_inner_core=None,
    ),
    "B-az: active zone only — 1-zone fuel, radial blanket, no bypass",
)

# C-az: 2-zone fuel, radial blanket, no bypass
display(
    create_active_zone(
        r_outer_core=R_OUTER,
        r_radial_blanket=BARREL_IR,
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        active_h=ACT_H,
        r_inner_core=R_INNER,
    ),
    "C-az: active zone only — 2-zone fuel, radial blanket, no bypass",
)

# D-az: 2-zone fuel, radial blanket, bypass (ESFR-SMART)
display(
    create_active_zone(
        r_outer_core=R_OUTER,
        r_radial_blanket=R_BLANKET,
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        active_h=ACT_H,
        r_inner_core=R_INNER,
    ),
    "D-az: active zone only — 2-zone fuel, radial blanket, bypass (ESFR-SMART)",
)


# ===========================================================================
# FULL CORE — create_reactor_core()
# ===========================================================================

# A: 1-zone, no blanket, no bypass
display(
    create_reactor_core(
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        barrel_height=BARREL_H,
        barrel_z_bottom=BARREL_Z,
        r_outer_core=BARREL_IR,
        r_radial_blanket=BARREL_IR,
        lower_plenum_h=LP_H,
        axial_blanket_bottom_h=ABB_H,
        active_h=ACT_H,
        axial_blanket_top_h=ABT_H,
        upper_plenum_h=UP_H,
        r_inner_core=None,
    ),
    "A: full core — 1-zone fuel, no blanket, no bypass",
)

# B: 1-zone, radial blanket, no bypass
display(
    create_reactor_core(
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        barrel_height=BARREL_H,
        barrel_z_bottom=BARREL_Z,
        r_outer_core=R_OUTER,
        r_radial_blanket=BARREL_IR,
        lower_plenum_h=LP_H,
        axial_blanket_bottom_h=ABB_H,
        active_h=ACT_H,
        axial_blanket_top_h=ABT_H,
        upper_plenum_h=UP_H,
        r_inner_core=None,
    ),
    "B: full core — 1-zone fuel, radial blanket, no bypass",
)

# C: 2-zone, radial blanket, no bypass
display(
    create_reactor_core(
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        barrel_height=BARREL_H,
        barrel_z_bottom=BARREL_Z,
        r_outer_core=R_OUTER,
        r_radial_blanket=BARREL_IR,
        lower_plenum_h=LP_H,
        axial_blanket_bottom_h=ABB_H,
        active_h=ACT_H,
        axial_blanket_top_h=ABT_H,
        upper_plenum_h=UP_H,
        r_inner_core=R_INNER,
    ),
    "C: full core — 2-zone fuel, radial blanket, no bypass",
)

# D: 2-zone, radial blanket, bypass (ESFR-SMART)
display(
    create_reactor_core(
        barrel_inner_radius=BARREL_IR,
        barrel_wall_t=BARREL_T,
        barrel_height=BARREL_H,
        barrel_z_bottom=BARREL_Z,
        r_outer_core=R_OUTER,
        r_radial_blanket=R_BLANKET,
        lower_plenum_h=LP_H,
        axial_blanket_bottom_h=ABB_H,
        active_h=ACT_H,
        axial_blanket_top_h=ABT_H,
        upper_plenum_h=UP_H,
        r_inner_core=R_INNER,
    ),
    "D: full core — 2-zone fuel, radial blanket, bypass (ESFR-SMART)",
)