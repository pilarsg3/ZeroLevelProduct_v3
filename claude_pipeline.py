"""
claude_vision_pipeline.py
=========================
Pipeline: technical drawing (image/PDF)  →  assemble_objects() specs.

Uses Claude's vision API to extract structured geometry from reactor drawings.
Output is a clean spec list ready for assemble_objects(). Fully self-contained
— no dependency on nuextract_pipeline.py or any other ZLP module.

Workflows
---------
A) SINGLE IMAGE:

    from claude_vision_pipeline import extract_specs_from_drawing, patch_spec
    specs = extract_specs_from_drawing("drawing.png")
    specs = patch_spec(specs, "reactor_vessel_1", {"inner_d": 8.91, "wall_t": 0.05})
    assembly = assemble_objects(specs)

B) SAVE RAW + RELOAD (inspect JSON before building):

    specs = extract_specs_from_drawing("drawing.png", save_raw_to="raw.json")
    # later:
    from claude_vision_pipeline import specs_from_json
    specs = specs_from_json("raw.json")

C) MULTIPLE VIEWS (plan + elevation in one call):

    from claude_vision_pipeline import extract_specs_from_drawings
    specs = extract_specs_from_drawings(["top_view.png", "side_view.png"])

Environment variables
---------------------
    ANTHROPIC_API_KEY   — your Anthropic API key (alternative to passing api_key=)

Requirements
------------
    pip install anthropic
"""







from __future__ import annotations

import base64
import json
import os
import warnings
from pathlib import Path
from typing import Any


from dotenv import load_dotenv
load_dotenv()




# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DRAWING_EXTRACTION_SCHEMA: dict[str, Any] = {
    "units":       ["mm", "cm", "m"],
    "drawing_id":  "verbatim-string",
    "description": "string",
    "components": [
        {
            "obj_id":    "string",
            "operation": ["primitive", "extrude", "revolve", "sweep"],

            "center_x":       "number",
            "center_y":       "number",
            "center_z":       "number",
            "rotation_roll":  "number",
            "rotation_pitch": "number",
            "rotation_yaw":   "number",

            "insert_into": "string",

            "obj_type": [
                "cylinder", "pipe", "box", "sphere",
                "reactor_vessel", "reactor_top_plate", "ihx",
            ],

            # generic geometry
            "radius":       "number",
            "height":       "number",
            "outer_radius": "number",
            "inner_radius": "number",
            "length":       "number",
            "width":        "number",

            # reactor_vessel
            "inner_d":    "number",
            "wall_t":     "number",
            "straight_h": "number",

            "bottom_head_type":    ["flat", "hemispherical", "ellipsoidal", "torispherical"],
            "bottom_head_plate_t": "number",
            "bottom_head_depth":   "number",
            "bottom_head_Rc":      "number",
            "bottom_head_rk":      "number",

            "top_head_type":    ["flat", "hemispherical", "ellipsoidal", "torispherical"],
            "top_head_plate_t": "number",
            "top_head_depth":   "number",
            "top_head_Rc":      "number",
            "top_head_rk":      "number",

            # reactor_top_plate
            "outer_d":   "number",
            "thickness": "number",
            "z_bottom":  "number",
            "hole_groups": [
                {
                    "hole_diameter":    "number",
                    "layout":           ["symmetric", "custom_angles", "explicit_positions"],
                    "count":            "integer",
                    "placement_radius": "number",
                    "start_angle_deg":  "number",
                    "angles_deg":       ["number"],
                    "positions_x":      ["number"],
                    "positions_y":      ["number"],
                }
            ],

            # ihx
            "shell_od":                "number",
            "shell_wall_t":            "number",
            "shell_straight_h":        "number",
            "inner_od":                "number",
            "inner_wall_t":            "number",
            "inner_h":                 "number",
            "bundle_od":               "number",
            "bundle_id":               "number",
            "bundle_h":                "number",
            "secondary_inlet_od":      "number",
            "secondary_inlet_wall_t":  "number",
            "secondary_inlet_length":  "number",
            "secondary_inlet_z":       "number",
            "secondary_outlet_od":     "number",
            "secondary_outlet_wall_t": "number",
            "secondary_outlet_length": "number",
            "secondary_outlet_z":      "number",

            # profile-based operations (extrude / revolve / sweep)
            "profile_obj_type":     ["rectangle", "circle", "ellipse",
                                     "trapezoid", "slot", "regular_polygon"],
            "profile_width":        "number",
            "profile_height":       "number",
            "profile_radius":       "number",
            "profile_r1":           "number",
            "profile_r2":           "number",
            "profile_a1":           "number",
            "profile_nmb_of_sides": "integer",
            "profile_angle":        "number",

            "extrude_height": "number",
            "wall_thickness": "number",
            "revolve_angle":  "number",
            "revolve_axis":   ["X", "Y", "Z"],
            "plane":          ["XY", "XZ", "YZ"],

            # OpenMC / DAGMC
            "material_tag":   "string",   # e.g. 'steel316', 'sodium', 'lead'
        }
    ],
}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a nuclear engineering CAD assistant.
Your task is to extract 3D component geometry from a reactor technical drawing
and return it as a single JSON object that conforms exactly to the schema below.

RULES
-----
1. Output ONLY valid JSON — no prose, no markdown fences, no comments.
2. Use null for values not visible or not labelled in the drawing.
3. Use the drawing's own unit system and record it in the "units" field
   ("mm", "cm", or "m"). Do NOT convert units.
4. obj_type must be one of:
     cylinder | pipe | box | sphere |
     reactor_vessel | reactor_top_plate | ihx
5. For PREMADE types (reactor_vessel, reactor_top_plate, ihx): ALWAYS set operation="primitive".
6. For reactor_vessel: populate inner_d, wall_t, straight_h, bottom_head_type.
   Use outer_d only if inner_d is not labelled.
7. For hole_groups in reactor_top_plate: populate as many fields as visible.
8. If a dimension label is ambiguous, use your best engineering judgement and
   note the ambiguity in the top-level "description" field.
9. Generate a short snake_case obj_id for each component.
10. Set material_tag if the material is labelled or obvious from context
    (e.g. 'steel316', 'sodium', 'lead', 'graphite'). Use null if unknown.
11. ONLY extract components that are EXPLICITLY VISIBLE in the drawing.
    Do NOT invent, infer, or add components that are not drawn
    (e.g. no drain pipes, nozzles, supports, or internals unless clearly shown).

JSON SCHEMA (all fields except obj_id and operation are nullable)
-----------------------------------------------------------------
{schema}
""".format(schema=json.dumps(DRAWING_EXTRACTION_SCHEMA, indent=2))

# _USER_PROMPT = "Extract all reactor components from this drawing. Return only the JSON object."

_USER_PROMPT = """\
Before outputting JSON, carefully count all visible holes in the top plate, \
identify their diameters and bolt circle radii from the drawing labels, \
and verify head geometry type from the elevation view. \
Then output the JSON object — nothing else after it.\
"""

_MULTI_USER_PROMPT = (
    "These are multiple views of the same reactor. "
    "Reconcile dimensions across all views — e.g. diameters from the plan view, "
    "heights from the elevation — and return one combined JSON object. "
    + _USER_PROMPT
)


# ---------------------------------------------------------------------------
# Unit scaling and postprocessing
# ---------------------------------------------------------------------------

_UNIT_SCALE: dict[str, float] = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}

_LINEAR_FIELDS = {
    "radius", "height", "length", "width", "outer_radius", "inner_radius",
    "inner_d", "wall_t", "straight_h",
    "bottom_head_plate_t", "bottom_head_depth", "bottom_head_Rc", "bottom_head_rk",
    "top_head_plate_t",    "top_head_depth",    "top_head_Rc",    "top_head_rk",
    "outer_d", "thickness", "z_bottom",
    "hole_diameter", "placement_radius",
    "profile_width", "profile_height", "profile_radius", "profile_r1", "profile_r2",
    "extrude_height", "wall_thickness",
    "shell_od", "shell_wall_t", "shell_straight_h",
    "inner_od", "inner_wall_t", "inner_h",
    "bundle_od", "bundle_id", "bundle_h",
    "secondary_inlet_od", "secondary_inlet_wall_t", "secondary_inlet_length", "secondary_inlet_z",
    "secondary_outlet_od", "secondary_outlet_wall_t", "secondary_outlet_length", "secondary_outlet_z",
}


def _sc(value: Any, s: float) -> Any:
    if isinstance(value, (int, float)):
        return value * s
    if isinstance(value, list):
        return [_sc(v, s) for v in value]
    return value


def _rebuild_component(c: dict[str, Any], s: float) -> dict[str, Any]:
    """Convert one flat extracted component into a nested assemble_objects() spec."""
    spec: dict[str, Any] = {}

    for f in ("obj_id", "operation", "insert_into", "plane", "material_tag"):
        if c.get(f):
            spec[f] = c[f]

    #if c.get("obj_type") and not c.get("profile_obj_type"):
    #    spec["obj_type"] = c["obj_type"]

    if c.get("obj_type"):
        spec["obj_type"] = c["obj_type"]

    cx, cy, cz = c.get("center_x"), c.get("center_y"), c.get("center_z")
    if any(v is not None for v in (cx, cy, cz)):
        spec["center_coords"] = (_sc(cx or 0.0, s), _sc(cy or 0.0, s), _sc(cz or 0.0, s))

    rr, rp, ry = c.get("rotation_roll"), c.get("rotation_pitch"), c.get("rotation_yaw")
    if any(v is not None for v in (rr, rp, ry)):
        spec["rotation_angles"] = (rr or 0.0, rp or 0.0, ry or 0.0)

    for f in ("radius", "height", "length", "width", "outer_radius", "inner_radius",
              "inner_d", "wall_t", "straight_h",
              "outer_d", "thickness", "z_bottom", "wall_thickness"):
        if c.get(f) is not None:
            spec[f] = _sc(c[f], s)

    if c.get("bottom_head_type"):
        spec["bottom_head_type"] = c["bottom_head_type"]
        bhp: dict[str, Any] = {}
        for src, dst in [("bottom_head_plate_t", "plate_t"), ("bottom_head_depth", "head_depth"),
                         ("bottom_head_Rc", "Rc"), ("bottom_head_rk", "rk")]:
            if c.get(src) is not None:
                bhp[dst] = _sc(c[src], s)
        if bhp:
            spec["bottom_head_params"] = bhp

    if c.get("top_head_type"):
        spec["top_head_type"] = c["top_head_type"]
        thp: dict[str, Any] = {}
        for src, dst in [("top_head_plate_t", "plate_t"), ("top_head_depth", "head_depth"),
                         ("top_head_Rc", "Rc"), ("top_head_rk", "rk")]:
            if c.get(src) is not None:
                thp[dst] = _sc(c[src], s)
        if thp:
            spec["top_head_params"] = thp

    for h in (c.get("hole_groups") or []):
        hg: dict[str, Any] = {}
        if h.get("hole_diameter") is not None:
            hg["hole_diameter"] = _sc(h["hole_diameter"], s)
        if h.get("layout"):
            hg["layout"] = h["layout"]
        if h.get("count") is not None:
            hg["count"] = h["count"]
        if h.get("placement_radius") is not None:
            hg["placement_radius"] = _sc(h["placement_radius"], s)
        if h.get("start_angle_deg") is not None:
            hg["start_angle_deg"] = h["start_angle_deg"]
        if h.get("angles_deg"):
            hg["angles_deg"] = h["angles_deg"]
        xs = h.get("positions_x") or []
        ys = h.get("positions_y") or []
        if xs and ys:
            hg["positions"] = [(_sc(x, s), _sc(y, s)) for x, y in zip(xs, ys)]
        if hg:
            spec.setdefault("hole_groups", []).append(hg)

    ihx_fields = (
        "shell_od", "shell_wall_t", "shell_straight_h",
        "inner_od", "inner_wall_t", "inner_h",
        "bundle_od", "bundle_id", "bundle_h",
        "secondary_inlet_od", "secondary_inlet_wall_t",
        "secondary_inlet_length", "secondary_inlet_z",
        "secondary_outlet_od", "secondary_outlet_wall_t",
        "secondary_outlet_length", "secondary_outlet_z",
    )
    for f in ihx_fields:
        if c.get(f) is not None:
            spec[f] = _sc(c[f], s)

    if c.get("profile_obj_type"):
        profile: dict[str, Any] = {"obj_type": c["profile_obj_type"]}
        for src, dst in [("profile_width", "width"), ("profile_height", "height"),
                         ("profile_radius", "radius"), ("profile_r1", "r1"),
                         ("profile_r2", "r2"), ("profile_a1", "a1"),
                         ("profile_nmb_of_sides", "nmb_of_sides"), ("profile_angle", "angle")]:
            if c.get(src) is not None:
                profile[dst] = _sc(c[src], s) if src in _LINEAR_FIELDS else c[src]
        spec["profile"] = profile

    op = spec.get("operation", "")
    if op == "extrude" and c.get("extrude_height") is not None:
        spec["height"] = _sc(c["extrude_height"], s)
    if op == "revolve":
        if c.get("revolve_angle") is not None:
            spec["angle"] = c["revolve_angle"]
        if c.get("revolve_axis"):
            spec["axis"] = c["revolve_axis"]

    _FIELDS_BY_TYPE: dict[str, set] = {
        "reactor_vessel": {
            "inner_d", "outer_d", "wall_t", "straight_h", "height",
            "bottom_head_type", "bottom_head_params",
            "top_head_type", "top_head_params",
        },
        "reactor_top_plate": {
            "outer_d", "thickness", "z_bottom", "hole_groups",
        },
        "ihx": {
            "shell_od", "shell_wall_t", "shell_straight_h",
            "inner_od", "inner_wall_t", "inner_h",
            "bundle_od", "bundle_id", "bundle_h",
            "secondary_inlet_od", "secondary_inlet_wall_t",
            "secondary_inlet_length", "secondary_inlet_z",
            "secondary_outlet_od", "secondary_outlet_wall_t",
            "secondary_outlet_length", "secondary_outlet_z",
        },
        "cylinder": {"radius", "height", "profile"},
        "pipe":     {"outer_radius", "inner_radius", "height", "profile"},
        "box":      {"length", "width", "height", "profile"},
        "sphere":   {"radius", "profile"},
    }
    _COMMON = {"obj_id", "operation", "obj_type", "insert_into",
           "center_coords", "rotation_angles",
           "plane", "angle", "axis", "wall_thickness",
           "material_tag"}

    obj_type = spec.get("obj_type")
    allowed = _COMMON | _FIELDS_BY_TYPE.get(obj_type, set()) #type: ignore

    return {k: v for k, v in spec.items() if k in allowed}


def postprocess(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert raw Claude extraction JSON into a clean assemble_objects() spec list.

    Parameters
    ----------
    raw : dict
        Parsed JSON as returned by extract_raw_from_drawing().

    Returns
    -------
    list[dict]
        One dict per component, ready for assemble_objects(specs).
    """
    units = (raw.get("units") or "mm").lower().strip()
    if units not in _UNIT_SCALE:
        warnings.warn(f"Unknown unit '{units}' — defaulting to mm.", stacklevel=2)
        units = "mm"
    s = _UNIT_SCALE[units]

    specs = []
    for comp in raw.get("components") or []:
        rebuilt = _rebuild_component(comp, s)
        if not rebuilt.get("operation"):
            continue
        if not rebuilt.get("obj_id"):
            rebuilt["obj_id"] = f"component_{len(specs)}"

        _REQUIRED_BY_TYPE = {
            "reactor_vessel":    ("outer_d", "inner_d", "straight_h", "height"),
            "reactor_top_plate": ("outer_d",),
            "ihx":               ("shell_od", "shell_straight_h"),
        }
        obj_type = rebuilt.get("obj_type")
        if obj_type in _REQUIRED_BY_TYPE:
            if not any(rebuilt.get(f) for f in _REQUIRED_BY_TYPE[obj_type]):
                continue
        elif obj_type and not any(rebuilt.get(f) for f in (
            "radius", "height", "length", "outer_radius", "extrude_height",
        )) and not rebuilt.get("profile"):
            continue

        # force correct operation for premade and primitive types
        if rebuilt.get("obj_type") in ("reactor_vessel", "reactor_top_plate", "ihx"):
            rebuilt["operation"] = "primitive"

        specs.append(rebuilt)

    return specs


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def specs_from_json(json_path: str | Path) -> list[dict[str, Any]]:
    """
    Load a previously saved raw extraction JSON and postprocess it.

    Useful for re-running postprocess() after manually editing the raw file.
    """
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_path}")
    with open(json_path) as f:
        raw = json.load(f)
    return postprocess(raw)


def patch_spec(
    specs:   list[dict[str, Any]],
    obj_id:  str,
    updates: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Apply manual overrides to one component after extraction.

    Useful for values not readable from the drawing (wall_t, inner_d, etc.).

    Example
    -------
    >>> specs = patch_spec(specs, "reactor_vessel_1", {"wall_t": 0.04, "inner_d": 8.91})
    """
    for spec in specs:
        if spec.get("obj_id") == obj_id:
            spec.update(updates)
            return specs
    raise KeyError(f"No component with obj_id='{obj_id}' found in specs.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _encode_image(image_path: Path) -> tuple[str, str]:
    suffix = image_path.suffix.lower()
    media_type_map = {
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif":  "image/gif",
        ".webp": "image/webp",
        ".pdf":  "application/pdf",
    }
    media_type = media_type_map.get(suffix)
    if media_type is None:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            "Supported: .png .jpg .jpeg .gif .webp .pdf"
        )
    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def _image_content_block(image_path: Path) -> dict[str, Any]:
    b64_data, media_type = _encode_image(image_path)
    if media_type == "application/pdf":
        return {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": b64_data},
        }
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64_data},
    }


def _parse_response(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        raw_text = raw_text.rsplit("```", 1)[0]
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude did not return valid JSON.\n"
            f"Parse error: {e}\n"
            f"Raw response (first 500 chars):\n{raw_text[:500]}"
        ) from e


def _save_raw(raw: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"Raw extraction saved → {path}")


def _get_client(api_key: str | None) -> Any:
    try:
        import anthropic    # type: ignore
    except ImportError as e:
        raise ImportError("anthropic package required: pip install anthropic") from e
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("No API key — pass api_key= or set ANTHROPIC_API_KEY env var.")
    import anthropic as _anthropic  #type: ignore
    return _anthropic.Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# Core API calls
# ---------------------------------------------------------------------------

def extract_raw_from_drawing(
    drawing_path: str | Path,
    *,
    api_key:     str | None = None,
    model:       str = "claude-sonnet-4-6",
    max_tokens:  int = 4096,
    save_raw_to: str | Path | None = None,
) -> dict[str, Any]:
    """
    Send a single drawing to Claude and return the raw extracted dict.

    Save via save_raw_to= to inspect the extraction or reload later with
    specs_from_json() without making another API call.

    Parameters
    ----------
    drawing_path : str | Path
        Path to a .png / .jpg / .gif / .webp / .pdf file.
    api_key : str, optional
        Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
    model : str
        Default: "claude-sonnet-4-6". Use "claude-opus-4-5" for maximum
        extraction quality on complex or low-resolution drawings.
    max_tokens : int
        Increase to 8192 for drawings with many components.
    save_raw_to : str | Path, optional
        If given, saves the raw JSON for inspection / later reuse.
    """
    drawing_path = Path(drawing_path)
    if not drawing_path.exists():
        raise FileNotFoundError(f"Drawing not found: {drawing_path}")

    client = _get_client(api_key)
    # response = client.messages.create(
    #     model      = model,
    #     max_tokens = max_tokens,
    #     system     = _SYSTEM_PROMPT,
    #     messages   = [{
    #         "role": "user",
    #         "content": [
    #             _image_content_block(drawing_path),
    #             {"type": "text", "text": _USER_PROMPT},
    #         ],
    #     }],
    # )

    response = client.messages.create(
        model      = model,
        max_tokens = 16000,
        thinking   = {"type": "enabled", "budget_tokens": 8000},
        system     = _SYSTEM_PROMPT,
        messages   = [{
            "role": "user",
            "content": [
                _image_content_block(drawing_path),
                {"type": "text", "text": _USER_PROMPT},
            ],
        }],
    )



    raw_text = "".join(b.text for b in response.content if b.type == "text")
    raw = _parse_response(raw_text)

    if save_raw_to is not None:
        _save_raw(raw, save_raw_to)

    return raw


def extract_specs_from_drawing(
    drawing_path: str | Path,
    *,
    api_key:     str | None = None,
    model:       str = "claude-sonnet-4-6",
    max_tokens:  int = 4096,
    save_raw_to: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Single drawing → assemble_objects() spec list.

    Example
    -------
    >>> from claude_vision_pipeline import extract_specs_from_drawing, patch_spec
    >>> from assemble import assemble_objects
    >>>
    >>> specs = extract_specs_from_drawing("esfr.png", save_raw_to="esfr_raw.json")
    >>> specs = patch_spec(specs, "reactor_vessel_1", {"wall_t": 0.04})
    >>> assembly = assemble_objects(specs)
    """
    raw = extract_raw_from_drawing(
        drawing_path,
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        save_raw_to=save_raw_to,
    )
    return postprocess(raw)


def extract_specs_from_drawings(
    drawing_paths: list[str | Path],
    *,
    api_key:     str | None = None,
    model:       str = "claude-sonnet-4-6",
    max_tokens:  int = 8192,
    save_raw_to: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Multiple views of the same reactor → single merged spec list.

    All images are sent in one Claude call so it can reconcile dimensions
    across views (e.g. diameters from plan, heights from elevation).

    Parameters
    ----------
    drawing_paths : list[str | Path]
        Two or more drawing images. Recommended order: plan view first.
    """
    client = _get_client(api_key)

    content: list[dict[str, Any]] = []
    for i, dp in enumerate(drawing_paths):
        dp = Path(dp)
        if not dp.exists():
            raise FileNotFoundError(f"Drawing not found: {dp}")
        content.append({"type": "text", "text": f"Drawing {i + 1} ({dp.name}):"})
        content.append(_image_content_block(dp))
    content.append({"type": "text", "text": _MULTI_USER_PROMPT})

    response = client.messages.create(
        model      = model,
        max_tokens = max_tokens,
        system     = _SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": content}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text")
    raw = _parse_response(raw_text)

    if save_raw_to is not None:
        _save_raw(raw, save_raw_to)

    return postprocess(raw)


# ---------------------------------------------------------------------------
# Text description → specs
# ---------------------------------------------------------------------------

_TEXT_SYSTEM_PROMPT = """\
You are a nuclear engineering CAD assistant.
Your task is to interpret a text description of a reactor or component and extract
3D geometry into a single JSON object that conforms exactly to the schema below.

RULES
-----
1. Output ONLY valid JSON — no prose, no markdown fences, no comments.
2. Use null for values not mentioned in the description.
3. Infer the unit system from context ("mm", "cm", or "m") and record it in "units".
   If ambiguous, default to "m". Do NOT convert units.
4. obj_type must be one of:
     cylinder | pipe | box | sphere |
     reactor_vessel | reactor_top_plate | ihx
5. For PREMADE types (reactor_vessel, reactor_top_plate, ihx): ALWAYS set operation="primitive".
6. For reactor_vessel: populate inner_d, wall_t, straight_h, bottom_head_type.
   Use outer_d only if inner_d cannot be inferred.
7. For hole_groups in reactor_top_plate: populate as many fields as mentioned.
8. If a value is ambiguous, use your best engineering judgement and note the
   ambiguity in the top-level "description" field.
9. Generate a short snake_case obj_id for each component.
10. Set material_tag if the material is mentioned or obvious from context
    (e.g. 'steel316', 'sodium', 'lead', 'graphite'). Use null if unknown.
11. ONLY extract components that are EXPLICITLY mentioned in the description.
    Do NOT invent or add components not described by the user.

JSON SCHEMA (all fields except obj_id and operation are nullable)
-----------------------------------------------------------------
{schema}
""".format(schema=json.dumps(DRAWING_EXTRACTION_SCHEMA, indent=2))


def extract_specs_from_text(
    description: str,
    *,
    api_key:     str | None = None,
    model:       str = "claude-sonnet-4-6",
    max_tokens:  int = 4096,
    save_raw_to: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Text description → assemble_objects() spec list.

    Sends a natural-language description of a reactor/component to Claude
    and returns a clean spec list — no image required.

    Parameters
    ----------
    description : str
        Free-form text describing the reactor geometry.
        Example: "A reactor vessel with inner diameter 4.72 m, wall thickness
        40 mm, straight section 5.5 m, ellipsoidal bottom head with depth 1 m.
        A flat top plate of outer diameter 4.8 m and thickness 100 mm sits on
        top at z = 5.5 m."
    api_key : str, optional
        Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
    model : str
        Default: "claude-sonnet-4-6".
    max_tokens : int
        Default: 4096.
    save_raw_to : str | Path, optional
        If given, saves the raw JSON for inspection / later reuse.

    Returns
    -------
    list[dict]
        Spec list ready for assemble_objects() or ask_for_missing_params().

    Example
    -------
    >>> from claude_pipeline import extract_specs_from_text
    >>> specs = extract_specs_from_text(
    ...     "Reactor vessel: inner diameter 4.72 m, wall 40 mm, height 5.5 m."
    ... )
    >>> assembly = assemble_objects(specs)
    """
    if not description or not description.strip():
        raise ValueError("description must be a non-empty string.")

    client = _get_client(api_key)

    response = client.messages.create(
        model      = model,
        max_tokens = max_tokens,
        system     = _TEXT_SYSTEM_PROMPT,
        messages   = [{
            "role":    "user",
            "content": description.strip(),
        }],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text")
    raw = _parse_response(raw_text)

    if save_raw_to is not None:
        _save_raw(raw, save_raw_to)

    return postprocess(raw)


def build_from_description(
    description: str,
    output_dir:  str  = "output",
    visualize:   bool = True,
    interactive: bool = False,
    confirm_cost: bool = False,
    save_raw_to: str | Path | None = None,
    *,
    api_key: str | None = None,
    model:   str = "claude-sonnet-4-6",
):
    """Text description → 3D CAD. Thin wrapper around build_from_user_input()."""
    return build_from_user_input(
        description  = description,
        output_dir   = output_dir,
        visualize    = visualize,
        interactive  = interactive,
        confirm_cost = confirm_cost,
        save_raw_to  = save_raw_to,
        api_key      = api_key,
        model        = model,
    )


# ---------------------------------------------------------------------------
# Unified pipeline internals
# ---------------------------------------------------------------------------

# Approximate pricing per million tokens (update if Anthropic changes rates)
# Source: https://www.anthropic.com/pricing  (as of 2025-04)
_PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6":  {"input": 3.0,  "output": 15.0},
    "claude-opus-4-5":    {"input": 15.0, "output": 75.0},
    "claude-haiku-4-5":   {"input": 0.8,  "output": 4.0},
}
_DEFAULT_PRICING = {"input": 3.0, "output": 15.0}  # fallback


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD."""
    p = _PRICING_PER_MTOK.get(model, _DEFAULT_PRICING)
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def _count_and_confirm(
    client:   Any,
    model:    str,
    system:   str,
    content:  list[dict[str, Any]],
    label:    str = "this call",
    expected_output_tokens: int = 1500,
) -> bool:
    """
    Count input tokens, display estimated cost, and ask user to confirm.

    Returns True to proceed, False to abort.
    """
    try:
        count_response = client.messages.count_tokens(
            model    = model,
            system   = system,
            messages = [{"role": "user", "content": content}],
        )
        input_tokens = count_response.input_tokens
    except Exception as e:
        print(f"  (Token count unavailable: {e})")
        choice = input("  Proceed anyway? [y/N]: ").strip().lower()
        return choice == "y"

    est_cost = _estimate_cost(model, input_tokens, expected_output_tokens)

    print(f"\n{'─'*50}")
    print(f"  Token estimate for {label}:")
    print(f"    Input tokens  : {input_tokens:,}")
    print(f"    Output tokens : ~{expected_output_tokens:,}  (estimate)")
    print(f"    Estimated cost: ~${est_cost:.4f} USD")
    print(f"    Model         : {model}")
    print(f"  (Prices approx. — check anthropic.com/pricing for current rates)")
    print(f"{'─'*50}")

    choice = input("  Proceed? [Y/n]: ").strip().lower()
    return choice in ("", "y", "yes")


def _extract_specs(
    description:  str | None,
    drawings:     list[Path],
    api_key:      str | None,
    model:        str,
    save_raw_to:  str | Path | None,
    confirm_cost: bool = False,
) -> list[dict[str, Any]]:
    """
    Smart dispatcher: extract specs from text, drawings, or both combined.

    - text only          → single Claude text call
    - drawings only (1)  → single-image vision call
    - drawings only (2+) → multi-image vision call
    - text + drawings    → single call with images AND description as extra context

    If confirm_cost=True, count tokens first and ask the user to confirm before
    making the real API call.
    """
    has_text     = bool(description and description.strip())
    has_drawings = bool(drawings)

    if has_text and has_drawings:
        client = _get_client(api_key)
        content: list[dict[str, Any]] = []
        if len(drawings) == 1:
            content.append({"type": "text", "text": f"Drawing ({drawings[0].name}):"})
            content.append(_image_content_block(drawings[0]))
        else:
            for i, dp in enumerate(drawings):
                content.append({"type": "text", "text": f"Drawing {i+1} ({dp.name}):"})
                content.append(_image_content_block(dp))
        content.append({"type": "text", "text":
            f"Additional description from the user:\n{(description or '').strip()}\n\n"
            + _MULTI_USER_PROMPT
        })
        if confirm_cost:
            if not _count_and_confirm(client, model, _SYSTEM_PROMPT, content,
                                      label="text + drawings extraction"):
                raise SystemExit("Aborted by user.")
        response = client.messages.create(
            model      = model,
            max_tokens = 8192,
            system     = _SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": content}],
        )
        raw_text = "".join(b.text for b in response.content if b.type == "text")
        raw = _parse_response(raw_text)
        if save_raw_to is not None:
            _save_raw(raw, save_raw_to)
        return postprocess(raw)

    elif has_text:
        if confirm_cost:
            client = _get_client(api_key)
            content_text = [{"type": "text", "text": (description or "").strip()}]
            if not _count_and_confirm(client, model, _TEXT_SYSTEM_PROMPT, content_text,
                                      label="text extraction"):
                raise SystemExit("Aborted by user.")
        return extract_specs_from_text(
            description,  # type: ignore[arg-type]
            api_key=api_key, model=model, save_raw_to=save_raw_to,
        )

    elif has_drawings:
        if confirm_cost:
            client = _get_client(api_key)
            content_imgs: list[dict[str, Any]] = []
            for i, dp in enumerate(drawings):
                if len(drawings) > 1:
                    content_imgs.append({"type": "text", "text": f"Drawing {i+1} ({dp.name}):"})
                content_imgs.append(_image_content_block(dp))
            content_imgs.append({"type": "text", "text":
                _USER_PROMPT if len(drawings) == 1 else _MULTI_USER_PROMPT
            })
            if not _count_and_confirm(client, model, _SYSTEM_PROMPT, content_imgs,
                                      label="drawings extraction"):
                raise SystemExit("Aborted by user.")
        if len(drawings) == 1:
            return extract_specs_from_drawing(
                drawings[0], api_key=api_key, model=model, save_raw_to=save_raw_to,
            )
        else:
            return extract_specs_from_drawings(
                [str(d) for d in drawings],
                api_key=api_key, model=model, save_raw_to=save_raw_to,
            )

    else:
        raise ValueError("Provide at least one of: description, drawings, or input_dir.")


def export_for_openmc(
    assembly:   Any,
    output_dir: "str | Path",
) -> tuple[list[str], list[str]]:
    """
    Export one STEP file per unique material_tag from a built assembly.

    Groups all solids sharing a material_tag into one STEP file (as a compound).
    Returns (step_files, material_tags) lists directly consumable by
    convert_to_dagmc(step_files, tags, h5m_path).

    Parameters
    ----------
    assembly : cq.Assembly
        Built by assemble_objects(). Must have _specs attached.
    output_dir : str | Path
        Folder where per-material STEP files are written.
        Files are named  material_<tag>.step

    Returns
    -------
    step_files    : list[str]   — absolute paths to the exported STEP files
    material_tags : list[str]   — corresponding material tags (same order)

    Raises
    ------
    ValueError
        If the assembly has no _specs, or no component has a material_tag.

    Example
    -------
    >>> step_files, tags = export_for_openmc(assembly, "output/esfr")
    >>> convert_to_dagmc(step_files, tags, "output/esfr/reactor.h5m")
    """
    import warnings
    from collections import defaultdict
    from pathlib import Path as _Path
    import cadquery as cq

    output_path = _Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    specs = getattr(assembly, "_specs", [])
    if not specs:
        raise ValueError(
            "Assembly has no _specs attached. Build with assemble_objects()."
        )

    # Build {obj_id: material_tag} from specs
    obj_to_tag: dict[str, str] = {}
    for spec in specs:
        tag = spec.get("material_tag")
        if tag:
            obj_to_tag[spec["obj_id"]] = str(tag)
        else:
            warnings.warn(
                f"'{spec.get('obj_id', '?')}' has no material_tag — "
                "excluded from OpenMC/DAGMC export.",
                stacklevel=2,
            )

    if not obj_to_tag:
        raise ValueError(
            "No components have material_tag set. "
            "Add 'material_tag' to each spec or use interactive=True to be prompted."
        )

    # Build {tag: [Shape, ...]} from assembly children
    tag_to_shapes: dict[str, list[Any]] = defaultdict(list)
    for child in assembly.children:
        tag = obj_to_tag.get(child.name)
        if tag is None or child.obj is None:
            continue
        obj = child.obj
        shape = obj.val() if hasattr(obj, "val") else obj
        tag_to_shapes[tag].append(shape)

    # Export one STEP per material tag
    step_files:    list[str] = []
    material_tags: list[str] = []
    for tag, shapes in sorted(tag_to_shapes.items()):
        step_path = str(output_path / f"material_{tag}.step")
        compound = cq.Compound.makeCompound(shapes)
        cq.exporters.export(compound, step_path, exportType="STEP")
        step_files.append(step_path)
        material_tags.append(tag)
        print(f"  ✓ {tag}: {len(shapes)} solid(s) → {step_path}")

    return step_files, material_tags


def _run_pipeline(
    specs:       list[dict[str, Any]],
    output_dir:  str,
    output_stem: str,
    visualize:   bool,
    interactive: bool,
) -> tuple[Any, list[dict[str, Any]], Path]:
    """Shared steps 2-5: interactive fill → build → export → visualize."""
    from pathlib import Path
    from assemble import assemble_objects
    from utils import export_step
    from ocp_vscode import show

    if interactive:
        print("\n🔧 Interactive mode: completing missing parameters...")
        specs = ask_for_missing_params(specs)

    print("\n🔨 Building 3D CAD assembly...")
    try:
        assembly = assemble_objects(specs)
        print("✓ Assembly complete")
    except Exception as e:
        print(f"✗ Assembly failed: {e}")
        raise

    print("\n💾 Exporting to STEP...")
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    output_file = output_path / f"{output_stem}.step"
    try:
        export_step(assembly, str(output_file))  # type: ignore
        print(f"✓ CAD export: {output_file}")
    except Exception as e:
        print(f"✗ Export failed: {e}")
        raise

    # Per-material STEP files for DAGMC/OpenMC (only if specs carry material_tag)
    if any(s.get("material_tag") for s in specs):
        print("\n🔬 Exporting per-material STEP files for OpenMC/DAGMC...")
        try:
            openmc_step_files, openmc_tags = export_for_openmc(assembly, output_dir)
            print(f"✓ {len(openmc_step_files)} material STEP file(s) ready for DAGMC")
        except Exception as e:
            print(f"✗ OpenMC export skipped: {e}")
    else:
        openmc_step_files, openmc_tags = [], []
        print("ℹ  No material_tag set — skipping per-material STEP export.")
        print("   Re-run with interactive=True or add 'material_tag' to specs.")

    if visualize:
        print("\n🎨 Visualizing...")
        show(assembly)  # type: ignore

    print("\n✅ Done!")
    return assembly, specs, output_file, openmc_step_files, openmc_tags # type: ignore


def build_from_user_input(
    description:  str | None = None,
    input_dir:    str | Path | None = None,
    drawings:     list[str | Path] | None = None,
    output_dir:   str  = "output",
    visualize:    bool = True,
    interactive:  bool = False,
    confirm_cost: bool = False,
    save_raw_to:  str | Path | None = None,
    *,
    api_key: str | None = None,
    model:   str = "claude-sonnet-4-6",
):
    """
    Universal entry point: text description, drawings, or both → 3D CAD assembly.

    Any combination of inputs is accepted:

    Text only::

        build_from_user_input(
            description="Reactor vessel: inner diameter 4.72 m, wall 40 mm ..."
        )

    Drawings only (auto-discover from folder)::

        build_from_user_input(input_dir=Path(__file__).parent)

    Explicit drawing list::

        build_from_user_input(drawings=["rv.jpg", "top_plate.jpg"])

    Text + drawings (Claude reconciles both)::

        build_from_user_input(
            description="Wall thickness is 40 mm.",
            input_dir=Path(__file__).parent,
        )

    Parameters
    ----------
    description : str, optional
        Free-form text describing reactor geometry.
    input_dir : Path, optional
        Folder to auto-discover .jpg/.png files from.
    drawings : list[str|Path], optional
        Explicit list of drawing file paths (overrides input_dir).
    output_dir : str
        Output folder for STEP file. Default: "output"
    visualize : bool
        Show in 3D viewer. Default: True
    interactive : bool
        Prompt for missing parameters via terminal. Default: False
    confirm_cost : bool
        Count tokens first, show estimated cost, and ask to proceed. Default: False
    save_raw_to : str | Path, optional
        Save raw Claude JSON for inspection / replay.
    api_key : str, optional
        Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
    model : str
        Claude model. Default: "claude-sonnet-4-6".

    Returns
    -------
    assembly : cq.Assembly
    specs    : list[dict]
    output_file : Path
    """
    from pathlib import Path as _Path

    # ── Resolve drawing paths ────────────────────────────────────────────
    resolved_drawings: list[Path] = []
    if drawings is not None:
        for d in drawings:
            p = _Path(d)
            if not p.exists():
                raise FileNotFoundError(f"Drawing not found: {p}")
            resolved_drawings.append(p)
    elif input_dir is not None:
        base = _Path(input_dir)
        resolved_drawings = sorted(base.glob("*.jpg")) + sorted(base.glob("*.png"))
        if not resolved_drawings and not description:
            raise FileNotFoundError(
                f"No .jpg/.png drawings found in {base}\n"
                "Pass a description= or add image files."
            )
    elif not description:
        # Default: auto-discover from cwd
        base = _Path.cwd()
        resolved_drawings = sorted(base.glob("*.jpg")) + sorted(base.glob("*.png"))
        if not resolved_drawings:
            raise FileNotFoundError(
                f"No drawings found in {base} and no description given.\n"
                "Pass description=, input_dir=, or drawings=, or place image files in cwd."
            )

    if resolved_drawings:
        print(f"✓ Found {len(resolved_drawings)} drawing(s):")
        for i, d in enumerate(resolved_drawings, 1):
            print(f"  {i}. {d.name}")
    if description:
        preview = description.strip().splitlines()[0][:80]
        print(f"✓ Description: {preview}{'...' if len(description.strip()) > 80 else ''}")

    # ── Extract ──────────────────────────────────────────────────────────
    mode = ("text+drawings" if description and resolved_drawings
            else "drawings" if resolved_drawings
            else "text")
    print(f"\n\U0001f4d0 Extracting geometry from {mode} via Claude...")
    try:
        specs = _extract_specs(description, resolved_drawings, api_key, model, save_raw_to,
                               confirm_cost=confirm_cost)
        print(f"✓ Extracted {len(specs)} component(s)")
        for spec in specs:
            print(f"  - {spec.get('obj_id')}: {spec.get('obj_type')}")
    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        raise

    # ── Output directory — put each example in its own subfolder ─────────
    if resolved_drawings:
        example_name = _Path(resolved_drawings[0]).parent.name or "assembly"
    else:
        example_name = "description_assembly"
    sub_output_dir = str(_Path(output_dir) / example_name)

    return _run_pipeline(specs, sub_output_dir, "assembly", visualize, interactive)


# ---------------------------------------------------------------------------
# CLI — python claude_vision_pipeline.py drawing.png [raw_output.json]
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python claude_vision_pipeline.py <drawing.[png|jpg|pdf]> [raw_output.json]")
        sys.exit(1)

    drawing = sys.argv[1]
    save_to = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Extracting from: {drawing}")
    specs = extract_specs_from_drawing(drawing, save_raw_to=save_to)

    print(f"\nExtracted {len(specs)} component(s):")
    for s in specs:
        print(f"  {s.get('obj_id', '?'):30s}  obj_type={s.get('obj_type')}  operation={s.get('operation')}")

    if save_to:
        print(f"\nTo reload:  from claude_vision_pipeline import specs_from_json")
        print(f"            specs = specs_from_json('{save_to}')")


# ---------------------------------------------------------------------------
# Interactive parameter completion helpers
# ---------------------------------------------------------------------------

def _ask_float(prompt: str, required: bool = True) -> float | None:
    """Prompt user for a float. Returns None if skipped (only allowed when not required)."""
    while True:
        try:
            user_input = input(f"  Enter {prompt}: ").strip()
            if not user_input:
                if required:
                    print("    (required — cannot skip)")
                    continue
                else:
                    print("    (skipped)")
                    return None
            return float(user_input)
        except ValueError:
            print("  ✗ Invalid — please enter a number.")


def _ask_choice(prompt: str, options: list[str]) -> str:
    """Prompt user to pick from a list of options."""
    while True:
        choice = input(f"  {prompt} ({'/'.join(options)}): ").strip()
        if choice in options:
            return choice
        print(f"  ✗ Choose one of: {options}")


def _resolve_radii(spec: dict, label: str = "") -> None:
    """
    Resolve pipe-like geometry: any two of {outer_radius, inner_radius, wall_thickness} → derive the third.
    Modifies spec in place.
    """
    ro = spec.get("outer_radius")
    ri = spec.get("inner_radius")
    wt = spec.get("wall_thickness")

    has_ro = ro is not None
    has_ri = ri is not None
    has_wt = wt is not None
    n_known = sum([has_ro, has_ri, has_wt])

    if n_known >= 2:
        # Already sufficient — derive the missing one
        if has_ro and has_ri:
            if not has_wt:
                spec["wall_thickness"] = ro - ri
        elif has_ro and has_wt:
            spec["inner_radius"] = ro - wt
        elif has_ri and has_wt:
            spec["outer_radius"] = ri + wt
        return

    # Need to ask user
    print(f"\n  Radius specification for {label}:")
    print("    [1]  outer_radius + wall_thickness  (inner derived)")
    print("    [2]  inner_radius + wall_thickness  (outer derived)")
    print("    [3]  outer_radius + inner_radius    (wall derived)")
    choice = _ask_choice("Choose", ["1", "2", "3"])

    if choice == "1":
        if not has_ro:
            spec["outer_radius"] = _ask_float("outer_radius")
        if not has_wt:
            spec["wall_thickness"] = _ask_float("wall_thickness")
        spec["inner_radius"] = spec["outer_radius"] - spec["wall_thickness"]  # type: ignore[operator]
        print(f"    ✓ Derived inner_radius = {spec['inner_radius']:.6g}")
    elif choice == "2":
        if not has_ri:
            spec["inner_radius"] = _ask_float("inner_radius")
        if not has_wt:
            spec["wall_thickness"] = _ask_float("wall_thickness")
        spec["outer_radius"] = spec["inner_radius"] + spec["wall_thickness"]  # type: ignore[operator]
        print(f"    ✓ Derived outer_radius = {spec['outer_radius']:.6g}")
    elif choice == "3":
        if not has_ro:
            spec["outer_radius"] = _ask_float("outer_radius")
        if not has_ri:
            spec["inner_radius"] = _ask_float("inner_radius")
        spec["wall_thickness"] = spec["outer_radius"] - spec["inner_radius"]  # type: ignore[operator]
        print(f"    ✓ Derived wall_thickness = {spec['wall_thickness']:.6g}")


def _resolve_rv_diameter(spec: dict) -> None:
    """
    reactor_vessel: resolve inner_d + wall_t OR outer_d + wall_t → derive the other.
    Modifies spec in place.
    """
    inner_d = spec.get("inner_d")
    wall_t  = spec.get("wall_t")
    outer_d = spec.get("outer_d")  # outer_d = inner_d + 2*wall_t

    has_inner = inner_d is not None
    has_wall  = wall_t  is not None
    has_outer = outer_d is not None

    if has_inner and has_wall:
        return  # sufficient

    if has_outer and has_wall:
        spec["inner_d"] = outer_d - 2 * wall_t  # type: ignore[operator]
        print(f"    ✓ Derived inner_d = {spec['inner_d']:.6g}")
        return

    if has_inner and has_outer:
        spec["wall_t"] = (outer_d - inner_d) / 2  # type: ignore[operator]
        print(f"    ✓ Derived wall_t = {spec['wall_t']:.6g}")
        return

    # Need to ask — always use inner_d + wall_t (most common for reactor vessels)
    if not has_inner:
        spec["inner_d"] = _ask_float("inner_d (Inner diameter)")
    if not has_wall:
        spec["wall_t"] = _ask_float("wall_t (Wall thickness)")


# ---------------------------------------------------------------------------
# Main interactive completion function
# ---------------------------------------------------------------------------

def ask_for_missing_params(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Interactive: Ask user to fill in missing critical parameters.

    Handles all component types and their logical input combinations:

    Primitive types:
      cylinder              : radius, height
      sphere                : radius
      box                   : length, width, height
      pipe                  : height + any two of {outer_radius, inner_radius, wall_thickness}
      cylinder_closed_bottom: height + any two of {outer_radius, inner_radius, wall_thickness}

    Premade types (operation="primitive"):
      reactor_vessel        : (inner_d OR outer_d) + wall_t + straight_h
      reactor_top_plate     : outer_d, thickness, z_bottom
      ihx                   : shell_od, shell_wall_t, shell_straight_h + optional fields

    Parameters
    ----------
    specs : list[dict]
        Component specifications from extraction (may have nulls)

    Returns
    -------
    list[dict]
        Updated specs with user-provided values

    Example
    -------
    >>> specs = extract_specs_from_drawing("drawing.png")
    >>> specs = ask_for_missing_params(specs)
    >>> assembly = assemble_objects(specs)
    """

    updated_specs = []

    for spec in specs:
        obj_id   = spec.get("obj_id", "unknown")
        obj_type = spec.get("obj_type")

        print(f"\n{'='*60}")
        print(f"Component : {obj_id}  (type: {obj_type})")
        print(f"{'='*60}")

        # ── cylinder ────────────────────────────────────────────────────
        if obj_type == "cylinder":
            if spec.get("radius") is None:
                spec["radius"] = _ask_float("radius")
            else:
                print(f"✓ radius: {spec['radius']}")
            if spec.get("height") is None:
                spec["height"] = _ask_float("height")
            else:
                print(f"✓ height: {spec['height']}")

        # ── sphere ───────────────────────────────────────────────────────
        elif obj_type == "sphere":
            if spec.get("radius") is None:
                spec["radius"] = _ask_float("radius")
            else:
                print(f"✓ radius: {spec['radius']}")

        # ── box ──────────────────────────────────────────────────────────
        elif obj_type == "box":
            for field in ("length", "width", "height"):
                if spec.get(field) is None:
                    spec[field] = _ask_float(field)
                else:
                    print(f"✓ {field}: {spec[field]}")

        # ── pipe ─────────────────────────────────────────────────────────
        elif obj_type == "pipe":
            if spec.get("height") is None:
                spec["height"] = _ask_float("height")
            else:
                print(f"✓ height: {spec['height']}")
            _resolve_radii(spec, label=obj_id)

        # ── cylinder_closed_bottom ────────────────────────────────────────
        elif obj_type == "cylinder_closed_bottom":
            if spec.get("height") is None:
                spec["height"] = _ask_float("height")
            else:
                print(f"✓ height: {spec['height']}")
            _resolve_radii(spec, label=obj_id)

        # ── reactor_vessel ────────────────────────────────────────────────
        elif obj_type == "reactor_vessel":
            _resolve_rv_diameter(spec)
            straight_h = spec.get("straight_h") or spec.get("height")
            if straight_h is None:
                straight_h = _ask_float("straight_h (Straight section height)")
                spec["straight_h"] = straight_h
            else:
                print(f"✓ straight_h: {straight_h}")
            # Optional head geometry — ask only if not set
            if spec.get("bottom_head_type") is None:
                print("\n  Bottom head type (optional — press Enter to skip):")
                print("    Options: flat | hemispherical | ellipsoidal | torispherical")
                val = input("  Enter bottom_head_type: ").strip()
                if val in ("flat", "hemispherical", "ellipsoidal", "torispherical"):
                    spec["bottom_head_type"] = val
                elif val:
                    print("  ✗ Unrecognised type — skipped")
            else:
                print(f"✓ bottom_head_type: {spec['bottom_head_type']}")

            # Ask for head params if needed — also re-ask if extracted value is invalid
            head_type = spec.get("bottom_head_type")
            existing_params = spec.get("bottom_head_params") or {}
            od = (spec.get("inner_d") or 0) + 2 * (spec.get("wall_t") or 0)
            if head_type == "ellipsoidal" and existing_params.get("head_depth") is None:
                hd = _ask_float("bottom head_depth (ellipsoidal depth)")
                spec["bottom_head_params"] = {**existing_params, "head_depth": hd}
            elif head_type == "torispherical":
                Rc = existing_params.get("Rc")
                # Validate: Rc defaults to od inside the builder, so only re-ask if present but wrong
                if Rc is not None and od > 0 and Rc <= od / 2:
                    print(f"  ✗ Extracted Rc={Rc:.4g} is invalid (must be > od/2 = {od/2:.4g}) — please re-enter")
                    Rc = None
                if Rc is None:
                    rc_min = f" > {od/2:.4g}" if od > 0 else ""
                    rc_default = f"; Enter = use default Rc=od={od:.4g}" if od > 0 else ""
                    Rc = _ask_float(f"Rc — Crown radius (must be{rc_min}{rc_default})", required=False)
                    if Rc is not None:
                        existing_params = {**existing_params, "Rc": Rc}
                else:
                    print(f"✓ bottom_head_params Rc: {Rc}")
                if existing_params.get("rk") is None:
                    rk = _ask_float("bottom_head_params rk (Knuckle radius, optional — Enter to use default)", required=False)
                    if rk is not None:
                        if rk <= 0:
                            print(f"  ✗ rk must be > 0 — skipped, default will be used")
                            rk = None
                        else:
                            existing_params = {**existing_params, "rk": rk}
                else:
                    print(f"✓ bottom_head_params rk: {existing_params['rk']}")
                spec["bottom_head_params"] = existing_params
            elif head_type == "flat" and existing_params.get("plate_t") is None:
                pt = _ask_float("bottom_head_params plate_t (Flat head plate thickness, optional — Enter to use wall_t)", required=False)
                if pt is not None:
                    spec["bottom_head_params"] = {**existing_params, "plate_t": pt}

        # ── reactor_top_plate ─────────────────────────────────────────────
        elif obj_type == "reactor_top_plate":
            for field, prompt in (
                ("outer_d",   "outer_d (Outer diameter)"),
                ("thickness", "thickness (Plate thickness)"),
                ("z_bottom",  "z_bottom (Z position of bottom face)"),
            ):
                if spec.get(field) is None:
                    spec[field] = _ask_float(prompt)
                else:
                    print(f"✓ {field}: {spec[field]}")

            # Validate / complete each hole_group
            hole_groups = spec.get("hole_groups") or []
            for g_idx, group in enumerate(hole_groups):
                prefix = f"  hole_groups[{g_idx}]"
                layout = group.get("layout", "symmetric")
                print(f"{prefix} layout={layout!r}")

                if group.get("hole_diameter") is None:
                    group["hole_diameter"] = _ask_float(f"{prefix} hole_diameter")
                else:
                    print(f"{prefix} hole_diameter: {group['hole_diameter']}")

                if layout in ("symmetric", "custom_angles"):
                    if group.get("placement_radius") is None:
                        group["placement_radius"] = _ask_float(
                            f"{prefix} placement_radius (radial distance from plate centre)"
                        )
                    else:
                        print(f"{prefix} placement_radius: {group['placement_radius']}")

                if layout == "symmetric":
                    if group.get("count") is None:
                        raw = input(f"{prefix} count (number of holes): ").strip()
                        group["count"] = int(raw) if raw else 1
                    else:
                        print(f"{prefix} count: {group['count']}")

        # ── ihx ───────────────────────────────────────────────────────────
        elif obj_type == "ihx":
            # Required fields
            for field, prompt in (
                ("shell_od",         "shell_od (Shell outer diameter)"),
                ("shell_wall_t",     "shell_wall_t (Shell wall thickness)"),
                ("shell_straight_h", "shell_straight_h (Shell height)"),
            ):
                if spec.get(field) is None:
                    spec[field] = _ask_float(prompt)
                else:
                    print(f"✓ {field}: {spec[field]}")

            # Optional fields with cross-field ordering constraints
            shell_r = (spec.get("shell_od") or 0) / 2
            optional_ihx = [
                ("inner_od",                f"inner_od (Inner cylinder outer diameter, must be < shell_od={spec.get('shell_od', '?')})"),
                ("inner_wall_t",            "inner_wall_t (Inner cylinder wall thickness)"),
                ("inner_h",                 "inner_h (Inner cylinder height)"),
                ("bundle_od",               "bundle_od (Bundle outer diameter)"),
                ("bundle_id",               "bundle_id (Bundle inner diameter)"),
                ("bundle_h",                "bundle_h (Bundle height)"),
                ("secondary_inlet_od",      "secondary_inlet_od"),
                ("secondary_inlet_wall_t",  "secondary_inlet_wall_t"),
                ("secondary_inlet_length",  "secondary_inlet_length"),
                ("secondary_inlet_z",       "secondary_inlet_z"),
                ("secondary_outlet_od",     "secondary_outlet_od"),
                ("secondary_outlet_wall_t", "secondary_outlet_wall_t"),
                ("secondary_outlet_length", "secondary_outlet_length"),
                ("secondary_outlet_z",      "secondary_outlet_z"),
            ]
            for field, prompt in optional_ihx:
                if spec.get(field) is None:
                    val = _ask_float(prompt + " (optional — Enter to skip)", required=False)
                    if val is not None:
                        spec[field] = val
                else:
                    print(f"✓ {field}: {spec[field]}")

            # Cross-field constraint validation
            inner_r = (spec.get("inner_od") or 0) / 2
            if spec.get("inner_od") and shell_r > 0 and inner_r >= shell_r:
                print(f"  ✗ inner_od={spec['inner_od']:.4g} must be < shell_od={spec.get('shell_od'):.4g} — re-enter")
                spec["inner_od"] = _ask_float(f"inner_od (must be < shell_od={spec.get('shell_od'):.4g})")
            if spec.get("bundle_od") and spec.get("bundle_id") and spec["bundle_id"] >= spec["bundle_od"]:
                print(f"  ✗ bundle_id={spec['bundle_id']:.4g} must be < bundle_od={spec['bundle_od']:.4g} — re-enter")
                spec["bundle_id"] = _ask_float(f"bundle_id (must be < bundle_od={spec['bundle_od']:.4g})")

        # ── unknown type ──────────────────────────────────────────────────
        else:
            print(f"  (no interactive checks defined for type '{obj_type}' — passed through)")

        # ── material_tag (for OpenMC/DAGMC) — asked for every component ──
        if spec.get("material_tag") is None:
            print("\n  material_tag (for OpenMC/DAGMC — press Enter to skip):")
            print("    Examples: steel316, sodium, lead, graphite, helium")
            val = input("  Enter material_tag: ").strip()
            if val:
                spec["material_tag"] = val
        else:
            print(f"✓ material_tag: {spec['material_tag']}")

        updated_specs.append(spec)

    print(f"\n{'='*60}")
    print("✅ Parameter completion done!\n")
    return updated_specs


def build_from_drawings(
    input_dir    = None,
    output_dir:  str  = "output",
    visualize:   bool = True,
    interactive: bool = False,
    confirm_cost: bool = False,
):
    """Drawings in a folder → 3D CAD. Thin wrapper around build_from_user_input()."""
    return build_from_user_input(
        input_dir    = input_dir,
        output_dir   = output_dir,
        visualize    = visualize,
        interactive  = interactive,
        confirm_cost = confirm_cost,
    )