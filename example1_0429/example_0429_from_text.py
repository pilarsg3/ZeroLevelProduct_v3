"""
Example: Build reactor CAD from a text description (no drawing needed).

Edit the description string below, then run this script.
"""

from claude_pipeline import build_from_user_input

DESCRIPTION = """
Reactor vessel:
  - Inner diameter: 4.72 m
  - Wall thickness: 40 mm
  - Straight section height: 5.5 m
  - Bottom head: ellipsoidal, depth 1.0 m

Top plate:
  - Outer diameter: 4.80 m
  - Thickness: 100 mm
  - Sits on top of the vessel (z_bottom = 5.5 m)
"""

if __name__ == "__main__":
    build_from_user_input(description=DESCRIPTION, interactive=True)
