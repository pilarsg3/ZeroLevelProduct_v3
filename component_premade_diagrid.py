"""
Parametric diagrid — ZLP V3.

The diagrid is a horizontal disc that supports the reactor core assemblies
in an SFR. Geometrically it's a flat cylindrical plate.

All dimensions must be provided explicitly.

Single public function:
    create_diagrid()  — returns a single cq.Workplane solid
"""

from __future__ import annotations
import cadquery as cq


def create_diagrid(
    diameter:  float,
    thickness: float,
    z_bottom:  float = 0.0,
) -> cq.Workplane:
    """
    Build the diagrid as a flat cylindrical disc.

    Args:
        diameter:  outer diameter [m]
        thickness: axial thickness [m]
        z_bottom:  z coordinate of the bottom face [m] (default 0)

    Returns:
        cq.Workplane — disc with bottom face at z_bottom
    """
    if diameter <= 0:
        raise ValueError(f"diameter must be > 0, got {diameter}")
    if thickness <= 0:
        raise ValueError(f"thickness must be > 0, got {thickness}")

    return (cq.Workplane("XY")
            .workplane(offset=z_bottom)
            .circle(diameter / 2.0)
            .extrude(thickness))


# ---------------------------------------------------------------------------
# Example
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from ocp_vscode import show
    diagrid = create_diagrid(
        diameter  = 4.660,
        thickness = 1.050,
        z_bottom  = 0.0,
    )
    show(diagrid)


