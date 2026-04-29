"""
Parametric SFR reactor core component — ZLP V2/V3.

Two public functions:
  create_active_zone()   — radial zone structure at the active level only
  create_reactor_core()  — full core including plenums and axial blankets

DESIGN OPTIONS
--------------
Radial structure is controlled by four radius parameters:

  r_inner_core         float | None
  r_outer_core         float
  r_radial_blanket     float
  barrel_inner_radius  float

  r_inner_core=None        → single fuel zone (no enrichment split)
  r_inner_core=float       → two-zone fuel (inner higher, outer lower enrichment)

  r_outer_core == r_radial_blanket   → no radial fertile blanket
  r_outer_core <  r_radial_blanket   → radial fertile blanket present

  r_radial_blanket == barrel_inner_radius  → no sodium bypass gap
  r_radial_blanket <  barrel_inner_radius  → sodium bypass gap present

Common configurations:
  A) 1-zone, no blanket, no bypass
       r_inner_core=None, r_outer_core=barrel_inner_radius, r_radial_blanket=barrel_inner_radius
  B) 1-zone, blanket, no bypass
       r_inner_core=None, r_outer_core<barrel_inner_radius, r_radial_blanket=barrel_inner_radius
  C) 2-zone, blanket, no bypass        (compact pool SFR)
       r_inner_core<r_outer_core, r_radial_blanket=barrel_inner_radius
  D) 2-zone, blanket, bypass           (ESFR-SMART reference)
       r_inner_core<r_outer_core, r_outer_core<r_radial_blanket<barrel_inner_radius

Valid for: pool-type SFR with cylindrical homogenisation of hexagonal assembly lattice.
OpenMC: call these functions directly (not via assemble_objects) to get per-zone dicts
for material assignment.
"""

import warnings
import cadquery as cq


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _cylinder(r: float, h: float, z_bottom: float) -> cq.Workplane:
    return cq.Workplane("XY").circle(r).extrude(h).translate((0, 0, z_bottom))


def _annulus(r_in: float, r_out: float, h: float, z_bottom: float) -> cq.Workplane:
    solid = cq.Workplane("XY").circle(r_out).extrude(h)
    if r_in > 0:
        solid = solid.cut(cq.Workplane("XY").circle(r_in).extrude(h))
    return solid.translate((0, 0, z_bottom))


def _validate_radii(
    r_inner_core: float | None,
    r_outer_core: float,
    r_radial_blanket: float,
    barrel_inner_radius: float,
) -> None:
    if r_inner_core is not None and not (0 < r_inner_core < r_outer_core):
        raise ValueError(
            f"r_inner_core={r_inner_core} must be in (0, r_outer_core={r_outer_core})"
        )
    if not (r_outer_core <= r_radial_blanket <= barrel_inner_radius):
        raise ValueError(
            f"Must satisfy r_outer_core <= r_radial_blanket <= barrel_inner_radius. "
            f"Got {r_outer_core}, {r_radial_blanket}, {barrel_inner_radius}."
        )


# ---------------------------------------------------------------------------
# create_active_zone
# ---------------------------------------------------------------------------

def create_active_zone(
    r_outer_core: float,
    r_radial_blanket: float,
    barrel_inner_radius: float,
    barrel_wall_t: float,
    active_h: float,
    z_bottom: float = 0.0,
    r_inner_core: float | None = None,
) -> dict[str, cq.Workplane]:
    """
    Radial zone structure at the active level only — no plenums or axial blankets.

    Args:
        r_outer_core:        outer fuel zone radius [m]
        r_radial_blanket:    radial blanket outer radius [m]
                             (set == barrel_inner_radius for no bypass)
        barrel_inner_radius: barrel inner surface radius [m]
        barrel_wall_t:       barrel wall thickness [m]
        active_h:            axial height [m]
        z_bottom:            z of bottom face [m] (default 0)
        r_inner_core:        inner fuel radius [m], or None for single fuel zone

    Returns dict with keys (depending on design):
        active_inner                          always present
        active_outer                          if r_inner_core is not None
        radial_blanket                        if r_outer_core < r_radial_blanket
        sodium_bypass                         if r_radial_blanket < barrel_inner_radius
        core_barrel                           always present
    """
    _validate_radii(r_inner_core, r_outer_core, r_radial_blanket, barrel_inner_radius)

    zones: dict[str, cq.Workplane] = {}

    if r_inner_core is None:
        zones["active_inner"] = _cylinder(r_outer_core, active_h, z_bottom)
    else:
        zones["active_inner"] = _cylinder(r_inner_core, active_h, z_bottom)
        zones["active_outer"] = _annulus(r_inner_core, r_outer_core, active_h, z_bottom)

    if r_outer_core < r_radial_blanket:
        zones["radial_blanket"] = _annulus(r_outer_core, r_radial_blanket, active_h, z_bottom)

    if r_radial_blanket < barrel_inner_radius:
        zones["sodium_bypass"] = _annulus(r_radial_blanket, barrel_inner_radius, active_h, z_bottom)

    zones["core_barrel"] = _annulus(
        barrel_inner_radius, barrel_inner_radius + barrel_wall_t, active_h, z_bottom
    )

    return zones


# ---------------------------------------------------------------------------
# create_reactor_core
# ---------------------------------------------------------------------------

def create_reactor_core(
    barrel_inner_radius: float,
    barrel_wall_t: float,
    barrel_height: float,
    barrel_z_bottom: float,
    r_outer_core: float,
    r_radial_blanket: float,
    lower_plenum_h: float,
    axial_blanket_bottom_h: float,
    active_h: float,
    axial_blanket_top_h: float,
    upper_plenum_h: float,
    r_inner_core: float | None = None,
) -> dict[str, cq.Workplane]:
    """
    Full SFR reactor core: sodium plenums, axial blankets, active zone, core barrel.

    Args:
        barrel_inner_radius:    barrel inner surface radius [m]
        barrel_wall_t:          barrel wall thickness [m]
        barrel_height:          total barrel height [m]
        barrel_z_bottom:        z of barrel bottom face [m]
        r_outer_core:           outer fuel zone radius [m]
        r_radial_blanket:       radial blanket outer radius [m]
                                (set == barrel_inner_radius for no bypass)
        lower_plenum_h:         lower sodium plenum height [m]
        axial_blanket_bottom_h: lower axial fertile blanket height [m]
        active_h:               active fuel zone height [m]
        axial_blanket_top_h:    upper axial fertile blanket height [m]
        upper_plenum_h:         upper sodium plenum height [m]
        r_inner_core:           inner fuel radius [m], or None for single fuel zone

    Returns dict with keys (depending on design):

        Always:
            lower_plenum, upper_plenum,
            axial_blanket_bottom_inner, axial_blanket_top_inner,
            active_inner, core_barrel

        If r_inner_core is not None:
            active_outer

        If r_outer_core < r_radial_blanket:
            radial_blanket_bottom, radial_blanket_active, radial_blanket_top

        If r_radial_blanket < barrel_inner_radius:
            sodium_bypass_bottom, sodium_bypass_active, sodium_bypass_top
    """
    _validate_radii(r_inner_core, r_outer_core, r_radial_blanket, barrel_inner_radius)

    axial_sum = (
        lower_plenum_h + axial_blanket_bottom_h + active_h
        + axial_blanket_top_h + upper_plenum_h
    )
    if abs(axial_sum - barrel_height) > 1e-6:
        warnings.warn(
            f"Axial heights sum to {axial_sum:.4f} m but barrel_height={barrel_height:.4f} m. "
            "Zones will not fill the barrel exactly.",
            stacklevel=2,
        )

    has_blanket = r_outer_core < r_radial_blanket
    has_bypass  = r_radial_blanket < barrel_inner_radius

    z0 = barrel_z_bottom
    z1 = z0 + lower_plenum_h
    z2 = z1 + axial_blanket_bottom_h
    z3 = z2 + active_h
    z4 = z3 + axial_blanket_top_h

    zones: dict[str, cq.Workplane] = {}

    # Sodium plenums — full inner radius
    zones["lower_plenum"] = _cylinder(barrel_inner_radius, lower_plenum_h, z0)
    zones["upper_plenum"] = _cylinder(barrel_inner_radius, upper_plenum_h, z4)

    # Axial blanket levels — inner fertile cylinder
    zones["axial_blanket_bottom_inner"] = _cylinder(r_outer_core, axial_blanket_bottom_h, z1)
    zones["axial_blanket_top_inner"]    = _cylinder(r_outer_core, axial_blanket_top_h,    z3)

    if has_blanket:
        zones["radial_blanket_bottom"] = _annulus(r_outer_core, r_radial_blanket, axial_blanket_bottom_h, z1)
        zones["radial_blanket_top"]    = _annulus(r_outer_core, r_radial_blanket, axial_blanket_top_h,    z3)

    if has_bypass:
        zones["sodium_bypass_bottom"] = _annulus(r_radial_blanket, barrel_inner_radius, axial_blanket_bottom_h, z1)
        zones["sodium_bypass_top"]    = _annulus(r_radial_blanket, barrel_inner_radius, axial_blanket_top_h,    z3)

    # Active zone
    if r_inner_core is None:
        zones["active_inner"] = _cylinder(r_outer_core, active_h, z2)
    else:
        zones["active_inner"] = _cylinder(r_inner_core, active_h, z2)
        zones["active_outer"] = _annulus(r_inner_core, r_outer_core, active_h, z2)

    if has_blanket:
        zones["radial_blanket_active"] = _annulus(r_outer_core, r_radial_blanket, active_h, z2)

    if has_bypass:
        zones["sodium_bypass_active"] = _annulus(r_radial_blanket, barrel_inner_radius, active_h, z2)

    # Core barrel — full height
    zones["core_barrel"] = _annulus(
        barrel_inner_radius,
        barrel_inner_radius + barrel_wall_t,
        barrel_height,
        barrel_z_bottom,
    )

    return zones