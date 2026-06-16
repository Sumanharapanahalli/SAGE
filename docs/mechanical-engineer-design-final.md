**1. `solutions/mechanical_engineer/prompts.yaml`**

```yaml
roles:
  mechanical_engineer:
    persona: |
      Senior mechanical engineer specialising in electronics enclosure design,
      precision mounting hardware, and custom mechanical parts for PCB assemblies.
      Uses CadQuery — a parametric Python 3-D CAD library — to produce STEP, STL,
      and DXF files ready for CNC machining, 3-D printing, or sheet-metal fabrication.

    system_prompt: |
      You design and model mechanical parts using the CadQuery MCP server tools.
      Your outputs are always parametric Python scripts that produce manufacturable
      geometry — never hard-coded geometry blobs.

      ── WORKFLOW ──────────────────────────────────────────────────────────────────
      1. GATHER requirements before writing a single line of CadQuery:
           - PCB outline dimensions (width × length, origin at mounting-hole 1)
           - Component height envelope (tallest component above board top)
           - Mounting hole coordinates (list of [x, y] in mm from PCB origin)
           - Environmental spec (IP rating, operating temp, vibration class)
           - Fabrication process (FDM / SLA / CNC / sheet-metal) — sets wall thickness
           - If a KiCad `.kicad_pcb` file or BOM CSV is available, parse it first
             using the checklist in the design-enclosure skill (Step 0).
      2. WRITE a CadQuery script. Rules:
           - All tunable dimensions as named constants at the top (ALL_CAPS).
           - Final solid stored in `result` (the default shape_var for MCP tools).
           - Include a Python docstring summarising the part, version, and parameters.
      3. VALIDATE via `cq_execute_script`. Fix any OCC kernel errors before export.
      4. MEASURE via `cq_measure_volume` — confirm volume > 0 (solid body) and
         bounding box matches expectations.
      5. CLEARANCE-CHECK every mating interface via `cq_check_clearance`:
           - PCB body vs. enclosure inner cavity (expect ≥ 2 mm clearance)
           - Lid vs. base mating face (expect ≤ 0.1 mm gap for snap/screw lids)
           - Clip vs. DIN rail (expect 0.2–0.5 mm running clearance)
      6. EXPORT artefacts:
           - `cq_export_step`  → STEP for mechanical CAD hand-off
           - `cq_export_stl`   → STL for 3-D print preview / slicer
           - `cq_export_dxf`   → DXF for laser-cut / sheet-metal flat patterns
      7. PROPOSE via SAGE HITL gate: submit the CadQuery script, exported file
         paths, parameter table, and clearance report as a single proposal.
         ALL proposals require human approval before files are committed.

      ── DESIGN STANDARDS ──────────────────────────────────────────────────────────
      Wall thickness defaults by process:
        FDM          → 2.0 mm (perimeter count ≥ 3 at 0.4 mm nozzle)
        SLA / resin  → 1.5 mm
        CNC aluminium→ 1.5 mm (with 3 mm floor)
        Sheet metal  → 1.0 mm (bend radius = 1 × thickness)

      PCB clearances (hard minimums):
        Bottom standoff height: 3.0 mm
        Side clearance:         2.0 mm each side
        Lid-to-component gap:   2.0 mm

      Fastener geometry:
        M3 boss OD:          6.0 mm
        M3 clearance hole:   3.4 mm (through)
        M3 self-tap hole:    2.5 mm (FDM boss)
        M3 insert bore:      4.0 mm × 5.7 mm depth (heat-set insert)

      DIN rail (EN 60715 TS35):
        Rail width:          35.0 mm
        Rail height:         7.5 mm
        Snap retention force: 15–40 N (spring arm deflection 2.0–3.5 mm)

      Heatsink clip:
        Spring gap nominal:  0.3 mm push-fit (0.1–0.5 mm depending on heatsink pin tolerance)

      File naming:
        `<part_name>_v<version>.<ext>`  e.g. `enclosure_v1.step`

      ── CONSTRAINTS ───────────────────────────────────────────────────────────────
      - Never hard-code absolute paths; always use the `output_dir` from the task.
      - Never write outside `output_dir` without explicit user approval.
      - On OCC kernel errors: isolate the failing boolean operation, simplify the
        fillet/chamfer radius or the shell sequence, and retry.
      - Always emit a Markdown parameter table alongside every model proposal:
          | Parameter | Value | Unit | Notes |
          |-----------|-------|------|-------|
      - For IP54+ enclosures: add a 1.5 mm × 1.0 mm gasket groove on the lid mating face.

    tools:
      mcp:
        - cq_execute_script
        - cq_export_step
        - cq_export_stl
        - cq_export_dxf
        - cq_measure_volume
        - cq_check_clearance
    skills:
      - design-enclosure
      - model-mechanical-part
    task_routing:
      generate_enclosure:     design-enclosure
      model_bracket:          model-mechanical-part
      export_step:            model-mechanical-part
      run_interference_check: model-mechanical-part
```

---

**2. `solutions/mechanical_engineer/tasks.yaml`**

```yaml
tasks:

  generate_enclosure:
    description: >
      Design a parametric enclosure for a PCB assembly. Produces a CadQuery script,
      STEP/STL/DXF exports, clearance report, and a Markdown parameter table.
      Requires PCB outline dimensions, component height, and mounting hole positions.
      If a KiCad .kicad_pcb file or BOM CSV is provided, those are parsed first
      (see design-enclosure skill Step 0) to derive all dimensional inputs automatically.
    required_inputs:
      - pcb_width_mm:              # board X dimension — OR derive from kicad_pcb_path
      - pcb_length_mm:             # board Y dimension — OR derive from kicad_pcb_path
      - component_height_mm:       # tallest component above board top surface — OR derive from bom_csv_path
      - mounting_hole_positions:   # list of {x, y} dicts in mm, origin = hole-1 — OR derive from kicad_pcb_path
    optional_inputs:
      - kicad_pcb_path:            # path to .kicad_pcb file; auto-fills pcb_width/length and hole positions
      - bom_csv_path:              # path to KiCad BOM CSV; auto-fills component_height_mm
      - wall_thickness_mm:         # overrides process default
      - fabrication_process:       # "fdm" | "sla" | "cnc" | "sheet_metal" (default: fdm)
      - lid_type:                  # "screw" | "snap" | "friction" (default: screw)
      - ip_rating:                 # e.g. "IP54" — adds gasket groove to lid mating face
      - connector_cutouts:         # list of {face: "front"|"back"|"left"|"right", x, y, w, h}
      - output_dir:                # default: "outputs/mechanical"
      - export_formats:            # list: ["step","stl","dxf"] (default: all three)
    outputs:
      - cq_script:       path to the generated .py CadQuery script
      - step_file:       path to exported STEP
      - stl_file:        path to exported STL
      - dxf_file:        path to exported DXF (lid flat pattern)
      - clearance_report: list of {interface, min_clearance_mm, status}
      - parameter_table:  Markdown table of all named dimensions
      - kicad_parse_report: summary of values extracted from KiCad files (if used)
    approval_required: true
    skill: design-enclosure
    timeout_seconds: 120

  model_bracket:
    description: >
      Model a mounting bracket, heatsink clip, DIN rail mount, or other custom
      mechanical part. The agent selects and parametrises the appropriate template
      based on `part_type`. Outputs CadQuery script, STEP, STL, and parameter table.
    required_inputs:
      - part_type:   # "l_bracket" | "heatsink_clip" | "din_rail_mount" | "standoff" | "custom"
      - spec:        # dict of part-specific dimensions (see skill file for per-type keys)
    optional_inputs:
      - material:          # "PLA" | "PETG" | "ABS" | "aluminium" | "steel" (affects defaults)
      - finish:            # "as_printed" | "anodised" | "powder_coated"
      - output_dir:
      - export_formats:    # list: ["step","stl","dxf"] (default: ["step","stl"])
    outputs:
      - cq_script:       path to generated .py script
      - step_file:       path to exported STEP
      - stl_file:        path to exported STL
      - parameter_table: Markdown dimension table
    approval_required: true
    skill: model-mechanical-part
    timeout_seconds: 90

  export_step:
    description: >
      Execute an existing CadQuery script and export the result as a STEP file.
      Used when the model already exists and only a fresh export artefact is needed
      (e.g. after a parameter edit external to SAGE).
    required_inputs:
      - script_path:   # absolute or repo-relative path to an existing .py CadQuery script
    optional_inputs:
      - output_dir:
      - shape_var:     # variable name of the solid in the script (default: "result")
      - overwrite:     # bool — default false; prevents silent overwrites
    outputs:
      - step_file:    path to the exported STEP file
      - volume_mm3:   scalar — non-zero confirms a solid body was exported
    approval_required: true
    timeout_seconds: 60

  run_interference_check:
    description: >
      Load two or more CadQuery body scripts and report minimum clearance between
      each pair. Flags any pair whose clearance falls below `min_clearance_mm`.
      Read-only analysis; does not write or commit any files.
    required_inputs:
      - scripts:       # list of {label, script} objects (inline CadQuery Python or file path)
    optional_inputs:
      - min_clearance_mm:   # pairs below this are flagged TIGHT (default: 0.2)
      - output_dir:         # optional — write JSON report to disk if provided
    outputs:
      - clearance_report:      list of {part_a, part_b, min_clearance_mm, status: "OK"|"TIGHT"|"INTERFERENCE"}
      - interference_detected: bool — true if any pair status == "INTERFERENCE"
      - summary:               one-line human-readable verdict
    approval_required: false
    timeout_seconds: 60
```

---

**3. `mcp-cadquery/server.py`**

```python
#!/usr/bin/env python3
"""
mcp-cadquery/server.py — CadQuery MCP stdio server for SAGE.

Protocol: JSON-RPC 2.0 over stdin/stdout (MCP spec 2024-11-05).
Each tool call executes the supplied CadQuery Python script in an isolated
subprocess (multiprocessing spawn context) so that OCC kernel crashes,
infinite loops, or heavy memory use cannot corrupt the server process.

Start: python mcp-cadquery/server.py
Declare in config/config.yaml under mcp_servers.
"""

from __future__ import annotations

import json
import multiprocessing
import queue as _queue_mod
import sys
import traceback
from typing import Callable

SUBPROCESS_TIMEOUT = 60.0  # seconds per tool call


# ── stdio transport ────────────────────────────────────────────────────────────

def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _recv() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    return json.loads(line) if line else None


# ── isolated subprocess worker ─────────────────────────────────────────────────
# Must be a top-level function so multiprocessing (spawn) can pickle it.

def _cq_worker(tool_name: str, args: dict, result_queue: multiprocessing.Queue) -> None:
    """
    Executes inside a freshly spawned child process.
    Imports CadQuery locally so any OCC crash stays in this process and is
    caught before reaching the server's stdio loop.

    The very first action is a guarded import of cadquery. If the library is
    not installed the worker puts a structured ImportError response and exits
    cleanly rather than propagating a raw traceback.
    """
    import textwrap as _tw
    import traceback as _tb
    from pathlib import Path

    # ── Guard: verify cadquery is importable ───────────────────────────────────
    try:
        import cadquery as cq
    except ImportError as _import_err:
        result_queue.put({
            "success": False,
            "error_type": "import_error",
            "error": (
                "CadQuery library is not installed or cannot be imported. "
                "Install it with:  pip install cadquery\n"
                f"Detail: {_import_err}"
            ),
            "install_hint": "pip install cadquery",
        })
        return

    # ── helpers ────────────────────────────────────────────────────────────────

    def _exec(script: str) -> dict:
        ns: dict = {}
        exec(_tw.dedent(script), ns)  # noqa: S102
        return ns

    def _pick(ns: dict, var: str):
        obj = ns.get(var)
        if obj is None:
            for v in reversed(list(ns.values())):
                if isinstance(v, (cq.Workplane, cq.Shape)):
                    obj = v
                    break
        if obj is None:
            raise ValueError(f"No CadQuery shape found (looked for '{var}')")
        return obj

    def _unwrap(obj):
        return obj.val() if isinstance(obj, cq.Workplane) else obj

    def _bbox(shape) -> dict:
        bb = shape.BoundingBox()
        return {
            "x_mm": round(bb.xmax - bb.xmin, 4),
            "y_mm": round(bb.ymax - bb.ymin, 4),
            "z_mm": round(bb.zmax - bb.zmin, 4),
        }

    try:
        # ── cq_execute_script ──────────────────────────────────────────────────
        if tool_name == "cq_execute_script":
            ns = _exec(args["script"])
            summaries = []
            for name, obj in ns.items():
                if name.startswith("_") or not isinstance(obj, (cq.Workplane, cq.Shape)):
                    continue
                try:
                    shape = _unwrap(obj)
                    bb = shape.BoundingBox()
                    summaries.append({
                        "name": name,
                        "volume_mm3": round(shape.Volume(), 4),
                        "bounding_box": {
                            "xmin": round(bb.xmin, 4), "xmax": round(bb.xmax, 4),
                            "ymin": round(bb.ymin, 4), "ymax": round(bb.ymax, 4),
                            "zmin": round(bb.zmin, 4), "zmax": round(bb.zmax, 4),
                        },
                    })
                except Exception as exc:
                    summaries.append({"name": name, "error": str(exc)})
            result_queue.put({"success": True, "shapes": summaries})

        # ── cq_export_step ─────────────────────────────────────────────────────
        elif tool_name == "cq_export_step":
            ns = _exec(args["script"])
            obj = _pick(ns, args.get("shape_var", "result"))
            out = args["output_path"]
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            cq.exporters.export(obj, out)
            result_queue.put({
                "success": True,
                "path": out,
                "size_bytes": Path(out).stat().st_size,
                "bounding_box": _bbox(_unwrap(obj)),
            })

        # ── cq_export_stl ──────────────────────────────────────────────────────
        elif tool_name == "cq_export_stl":
            ns = _exec(args["script"])
            obj = _pick(ns, args.get("shape_var", "result"))
            out = args["output_path"]
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            cq.exporters.export(
                obj,
                out,
                exportType=cq.exporters.ExportTypes.STL,
                tolerance=args.get("tolerance", 0.1),
                angularTolerance=args.get("angular_tolerance", 0.1),
            )
            result_queue.put({
                "success": True,
                "path": out,
                "size_bytes": Path(out).stat().st_size,
            })

        # ── cq_export_dxf ──────────────────────────────────────────────────────
        elif tool_name == "cq_export_dxf":
            ns = _exec(args["script"])
            obj = _pick(ns, args.get("shape_var", "result"))
            out = args["output_path"]
            plane = args.get("plane", "XY")
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            if isinstance(obj, cq.Shape):
                obj = cq.Workplane(plane).add(obj)
            cq.exporters.export(obj, out, exportType=cq.exporters.ExportTypes.DXF)
            result_queue.put({
                "success": True,
                "path": out,
                "size_bytes": Path(out).stat().st_size,
            })

        # ── cq_measure_volume ──────────────────────────────────────────────────
        elif tool_name == "cq_measure_volume":
            ns = _exec(args["script"])
            obj = _pick(ns, args.get("shape_var", "result"))
            shape = _unwrap(obj)
            volume = shape.Volume()
            result_queue.put({
                "success": True,
                "volume_mm3": round(volume, 4),
                "is_solid": volume > 1e-6,
                "bounding_box": _bbox(shape),
            })

        # ── cq_check_clearance ─────────────────────────────────────────────────
        elif tool_name == "cq_check_clearance":
            ns_a = _exec(args["script_a"])
            ns_b = _exec(args["script_b"])
            shape_a = _unwrap(_pick(ns_a, args.get("shape_var_a", "result")))
            shape_b = _unwrap(_pick(ns_b, args.get("shape_var_b", "result")))
            min_gap: float = args.get("min_clearance_mm", 0.2)

            try:
                from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
                from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
                from OCC.Core.BRepGProp import brepgprop_VolumeProperties
                from OCC.Core.GProp import GProp_GProps

                dist_calc = BRepExtrema_DistShapeShape(shape_a.wrapped, shape_b.wrapped)
                dist_calc.Perform()
                min_dist = round(dist_calc.Value(), 4) if dist_calc.IsDone() else None

                common_op = BRepAlgoAPI_Common(shape_a.wrapped, shape_b.wrapped)
                common_op.Build()
                props = GProp_GProps()
                brepgprop_VolumeProperties(common_op.Shape(), props)
                interference_vol = round(props.Mass(), 4)

                if interference_vol > 0.001:
                    status = "INTERFERENCE"
                elif min_dist is not None and min_dist < min_gap:
                    status = "TIGHT"
                else:
                    status = "OK"

                result_queue.put({
                    "success": True,
                    "min_clearance_mm": min_dist,
                    "interference_volume_mm3": interference_vol,
                    "status": status,
                    "method": "occ_exact",
                })

            except ImportError:
                bb_a = shape_a.BoundingBox()
                bb_b = shape_b.BoundingBox()
                gaps = [
                    bb_b.xmin - bb_a.xmax,
                    bb_a.xmin - bb_b.xmax,
                    bb_b.ymin - bb_a.ymax,
                    bb_a.ymin - bb_b.ymax,
                    bb_b.zmin - bb_a.zmax,
                    bb_a.zmin - bb_b.zmax,
                ]
                positive_gaps = [g for g in gaps if g > 0]
                separating_gap = min(positive_gaps) if positive_gaps else max(gaps)

                if max(gaps) < 0:
                    status = "INTERFERENCE"
                    clearance = round(max(gaps), 4)
                elif separating_gap < min_gap:
                    status = "TIGHT"
                    clearance = round(separating_gap, 4)
                else:
                    status = "OK"
                    clearance = round(separating_gap, 4)

                result_queue.put({
                    "success": True,
                    "min_clearance_mm": clearance,
                    "interference_volume_mm3": None,
                    "status": status,
                    "method": "bounding_box_approx",
                    "note": (
                        "Install pythonocc-core for exact OCC surface-to-surface "
                        "measurement: pip install pythonocc-core"
                    ),
                })

        else:
            result_queue.put({"success": False, "error": f"Unknown tool in worker: {tool_name}"})

    except Exception:
        result_queue.put({"success": False, "error": _tb.format_exc()})


# ── subprocess dispatch ────────────────────────────────────────────────────────

def _run_isolated(tool_name: str, args: dict) -> dict:
    """
    Spawn a fresh process for each tool call.
    The OCC kernel and any imported CadQuery state live entirely in the child;
    a crash, segfault, or timeout cannot corrupt the server's stdin/stdout loop.
    """
    ctx = multiprocessing.get_context("spawn")
    q: multiprocessing.Queue = ctx.Queue()
    p = ctx.Process(target=_cq_worker, args=(tool_name, args, q), daemon=True)
    p.start()
    try:
        result = q.get(timeout=SUBPROCESS_TIMEOUT)
    except _queue_mod.Empty:
        result = {
            "success": False,
            "error_type": "timeout",
            "error": (
                f"Subprocess timed out after {SUBPROCESS_TIMEOUT}s — "
                "check for infinite loops or extremely complex geometry."
            ),
        }
    finally:
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join()
    return result


# ── tool wrappers ──────────────────────────────────────────────────────────────

def tool_cq_execute_script(args: dict) -> dict:
    return _run_isolated("cq_execute_script", args)

def tool_cq_export_step(args: dict) -> dict:
    return _run_isolated("cq_export_step", args)

def tool_cq_export_stl(args: dict) -> dict:
    return _run_isolated("cq_export_stl", args)

def tool_cq_export_dxf(args: dict) -> dict:
    return _run_isolated("cq_export_dxf", args)

def tool_cq_measure_volume(args: dict) -> dict:
    return _run_isolated("cq_measure_volume", args)

def tool_cq_check_clearance(args: dict) -> dict:
    return _run_isolated("cq_check_clearance", args)


# ── tool registry ──────────────────────────────────────────────────────────────

TOOLS: dict[str, dict] = {
    "cq_execute_script": {
        "fn": tool_cq_execute_script,
        "description": (
            "Execute a CadQuery Python script in an isolated subprocess. "
            "Returns shape summaries (bounding box, volume) for each CadQuery "
            "object found in the script namespace. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "Complete CadQuery Python script to execute.",
                },
            },
            "required": ["script"],
        },
    },
    "cq_export_step": {
        "fn": tool_cq_export_step,
        "description": (
            "Execute a CadQuery script in an isolated subprocess and export the "
            "resulting solid as a STEP file suitable for mechanical CAD hand-off. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script":      {"type": "string", "description": "CadQuery Python script."},
                "output_path": {"type": "string", "description": "Destination path, e.g. outputs/enclosure_v1.step"},
                "shape_var":   {"type": "string", "description": "Variable name of the target solid (default: 'result')."},
            },
            "required": ["script", "output_path"],
        },
    },
    "cq_export_stl": {
        "fn": tool_cq_export_stl,
        "description": (
            "Execute a CadQuery script in an isolated subprocess and export the "
            "result as an STL file for 3-D printing. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script":            {"type": "string"},
                "output_path":       {"type": "string"},
                "shape_var":         {"type": "string", "description": "Default: 'result'"},
                "tolerance":         {"type": "number", "description": "Chord tolerance in mm (default: 0.1)."},
                "angular_tolerance": {"type": "number", "description": "Angular tolerance in degrees (default: 0.1)."},
            },
            "required": ["script", "output_path"],
        },
    },
    "cq_export_dxf": {
        "fn": tool_cq_export_dxf,
        "description": (
            "Execute a CadQuery script in an isolated subprocess and export a "
            "2-D projection as a DXF file for laser-cutting or sheet-metal work. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script":      {"type": "string"},
                "output_path": {"type": "string"},
                "shape_var":   {"type": "string"},
                "plane":       {
                    "type": "string",
                    "enum": ["XY", "XZ", "YZ"],
                    "description": "Projection plane (default: 'XY' = top-down).",
                },
            },
            "required": ["script", "output_path"],
        },
    },
    "cq_measure_volume": {
        "fn": tool_cq_measure_volume,
        "description": (
            "Execute a CadQuery script in an isolated subprocess and return total "
            "solid volume in mm³ plus overall bounding-box dimensions. "
            "Volume = 0 means no solid was produced. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script":    {"type": "string"},
                "shape_var": {"type": "string", "description": "Default: 'result'"},
            },
            "required": ["script"],
        },
    },
    "cq_check_clearance": {
        "fn": tool_cq_check_clearance,
        "description": (
            "Check the minimum clearance (mm) between two CadQuery bodies, each "
            "defined by a separate script. Executed in an isolated subprocess. "
            "Returns status OK | TIGHT | INTERFERENCE. "
            "Uses exact OCC surface-distance when pythonocc-core is available; "
            "falls back to bounding-box approximation otherwise. "
            "Returns error_type='import_error' if CadQuery is not installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_a":         {"type": "string", "description": "CadQuery script defining body A."},
                "script_b":         {"type": "string", "description": "CadQuery script defining body B."},
                "shape_var_a":      {"type": "string", "description": "Variable name for body A (default: 'result')."},
                "shape_var_b":      {"type": "string", "description": "Variable name for body B (default: 'result')."},
                "min_clearance_mm": {
                    "type": "number",
                    "description": "Threshold below which clearance is flagged TIGHT (default: 0.2).",
                },
            },
            "required": ["script_a", "script_b"],
        },
    },
}


# ── MCP protocol handlers ──────────────────────────────────────────────────────

def handle_initialize(req: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mcp-cadquery", "version": "1.2.0"},
        },
    }


def handle_tools_list(req: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req.get("id"),
        "result": {
            "tools": [
                {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": spec["inputSchema"],
                }
                for name, spec in TOOLS.items()
            ]
        },
    }


def handle_tools_call(req: dict) -> dict:
    params = req.get("params", {})
    name = params.get("name")
    tool_args = params.get("arguments", {})

    if name not in TOOLS:
        return {
            "jsonrpc": "2.0",
            "id": req.get("id"),
            "error": {"code": -32601, "message": f"Unknown tool: {name}"},
        }

    try:
        result = TOOLS[name]["fn"](tool_args)
        is_error = not result.get("success", True)
    except Exception as exc:
        result = {"success": False, "error": str(exc), "traceback": traceback.format_exc()}
        is_error = True

    return {
        "jsonrpc": "2.0",
        "id": req.get("id"),
        "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": is_error,
        },
    }


DISPATCH: dict[str, Callable] = {
    "initialize":                handle_initialize,
    "notifications/initialized": lambda _req: None,
    "tools/list":                handle_tools_list,
    "tools/call":                handle_tools_call,
}


# ── entry point ────────────────────────────────────────────────────────────────
# The `if __name__ == "__main__"` guard is required on Windows so that
# multiprocessing (spawn) does not re-execute the server loop in worker processes.

def main() -> None:
    while True:
        req = _recv()
        if req is None:
            break
        method = req.get("method", "")
        handler = DISPATCH.get(method)
        if handler is None:
            _send({
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })
            continue
        response = handler(req)
        if response is not None:
            _send(response)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller/Windows executables
    main()
```

---

**4a. `.claude/skills/design-enclosure.md`**

````markdown
# Skill: design-enclosure

Design a parametric PCB enclosure using CadQuery.
Follow every step in order. Do not skip validation.

---

## Step 0 — (Optional) Parse KiCad source files

If `kicad_pcb_path` or `bom_csv_path` is provided, extract dimensions from those
files **before** manually specifying any numbers. This avoids transcription errors.

### 0-A  Parse the `.kicad_pcb` file

KiCad PCB files are S-expression text files. Read the file and apply the following
extraction rules in order.

#### Board outline → `pcb_width_mm` and `pcb_length_mm`

Search for `gr_line` (or `gr_arc`, `gr_rect`) elements on the `Edge.Cuts` layer:

```
(gr_line (start X Y) (end X Y) (layer "Edge.Cuts") ...)
```

Collect all `start` and `end` coordinates. Compute:

```
x_coords = [all X values from Edge.Cuts lines]
y_coords = [all Y values from Edge.Cuts lines]
pcb_width_mm  = max(x_coords) - min(x_coords)   # board X span
pcb_length_mm = max(y_coords) - min(y_coords)    # board Y span
origin_x      = min(x_coords)
origin_y      = min(y_coords)
```

If the board outline uses `gr_rect` instead of `gr_line`:
```
(gr_rect (start X1 Y1) (end X2 Y2) (layer "Edge.Cuts") ...)
pcb_width_mm  = abs(X2 - X1)
pcb_length_mm = abs(Y2 - Y1)
```

**Verify**: `pcb_width_mm` and `pcb_length_mm` should both be > 5 mm. If either
is < 5 mm or > 500 mm, flag a parse warning and ask the user to confirm.

#### Mounting holes → `mounting_hole_positions`

Search for footprint pads of type `"thru_hole"` on the `B.Cu` / `F.Cu` layer
whose reference starts with `H` or whose value contains `MountingHole`:

```
(footprint "MountingHole:MountingHole_3.2mm_M3" ...
  (at X Y)
  ...)
```

Also match any pad with:
- `(net 0)` (unconnected) AND
- drill diameter ≥ 2.5 mm AND ≤ 4.5 mm (covers M2.5 – M4)

For each candidate mounting hole, record:
```python
{
  "x": round(pad_x - origin_x, 3),   # relative to board origin
  "y": round(pad_y - origin_y, 3),
  "drill_d_mm": drill_diameter,
}
```

Sort by x then y. The first entry becomes the coordinate origin (subtract its
x/y from all others so hole-1 is at 0,0 per the enclosure convention).

**Minimum**: warn if fewer than 2 mounting holes are found — the PCB cannot be
secured. Ask the user whether to add boss positions manually.

#### Connector cutouts → `connector_cutouts`

Search for footprints whose value or reference contains any of:
`USB`, `CONN`, `J[0-9]`, `P[0-9]`, `SW`, `LED`, `BUTTON`

For each connector footprint:
1. Read the pad bounding box (union of all pad `(at x y)` + pad size).
2. Read any `(fp_line ... (layer "F.Fab"))` or `(fp_rect ...)` courtyard to get
   the courtyard bounding box.
3. Determine which board edge the connector faces: the face closest to any
   `Edge.Cuts` line within 3 mm of the courtyard boundary.
4. Record:
   ```python
   {
     "face": "front" | "back" | "left" | "right",
     "x": offset_along_face_mm,
     "y": 0,          # height from PCB bottom; refine from 3D model if available
     "w": courtyard_width_mm + 2.0,    # 1 mm tolerance each side
     "h": courtyard_height_mm + 1.0,   # 0.5 mm tolerance top/bottom
     "ref": footprint_reference,
   }
   ```

If 3D models are embedded (`(model ...)` tokens), prefer those bounding boxes
over courtyard estimates.

### 0-B  Parse the BOM CSV → `component_height_mm`

KiCad BOM CSVs (generated by the default BOM plugin or kibom) contain columns
such as `Reference`, `Value`, `Footprint`, and optionally `Height` or `3D_Height`.

Locate the height column by checking (case-insensitive) for column headers:
`Height`, `Height_mm`, `3D_Height`, `Comp_Height`, `Z_Height`.

If a height column exists:
```python
component_height_mm = max(float(row[height_col]) for row in bom_rows if row[height_col])
```

If no height column exists, fall back to footprint-name heuristics:

| Footprint pattern | Assumed height (mm) |
|-------------------|---------------------|
| `*_THT*` or `*DIP*` | 8.0 |
| `*Capacitor_THT*` | 12.0 |
| `*TO-220*` or `*TO-92*` | 10.0 |
| `*SMD*` or `*0402*`–`*1206*` | 1.5 |
| `*Connector*` | 8.5 |
| (unknown) | 10.0 (conservative default) |

Report the heuristic source in the `kicad_parse_report`.

### 0-C  Emit the parse report

After extracting all values, output a parse report before writing any CadQuery:

```
KiCad Parse Report
──────────────────
Source .kicad_pcb : <path>
Source BOM CSV    : <path or "not provided">

Extracted values:
  pcb_width_mm          : <value>  mm   (from Edge.Cuts bounding box)
  pcb_length_mm         : <value>  mm   (from Edge.Cuts bounding box)
  mounting_hole_count   : <n>           (footprint refs: <list>)
  mounting_hole_positions:
    hole-1  x=0.000  y=0.000   drill=<d> mm
    hole-2  x=<v>    y=<v>     drill=<d> mm
    …
  connector_cutouts     : <n> found
    J1  face=front  w=<w>  h=<h>  (from courtyard / 3D model)
    …
  component_height_mm   : <value>  mm   (from <column name / footprint heuristic>)

Warnings: <any warnings, or "none">
```

Ask the user to confirm or correct values before proceeding to Step 1.

---

## Step 1 — Confirm inputs

After Step 0 (or if no KiCad files were provided), verify you have all of:

| Input | Type | Example |
|-------|------|---------|
| `pcb_width_mm` | float | 80.0 |
| `pcb_length_mm` | float | 60.0 |
| `component_height_mm` | float | 18.0 |
| `mounting_hole_positions` | list of {x,y} | [{x:0,y:0},{x:76,y:0},...] |
| `fabrication_process` | string | "fdm" |
| `lid_type` | string | "screw" |
| `ip_rating` | string or null | "IP54" |
| `connector_cutouts` | list or [] | [{face:"front",x:10,y:5,w:12,h:8}] |
| `output_dir` | string | "outputs/mechanical" |

If any required input is missing and Step 0 did not supply it, ask before proceeding.

---

## Step 2 — Write the CadQuery script

Use this template. Keep ALL_CAPS constants at the top.

```python
"""
Enclosure for <PCB name>
Version: 1
Process: <fdm|sla|cnc|sheet_metal>
Lid: <screw|snap|friction>
"""
import cadquery as cq

# ── Parameters ─────────────────────────────────────────────────────────────
PCB_W          = <pcb_width_mm>
PCB_L          = <pcb_length_mm>
COMP_H         = <component_height_mm>
WALL           = <wall_thickness: 2.0 fdm / 1.5 sla or cnc / 1.0 sheet_metal>
FLOOR          = <floor_thickness: same as WALL, min 2.0>
STANDOFF_H     = 3.0        # PCB bottom clearance
LID_CLEARANCE  = 2.0        # gap above tallest component
SIDE_CLEARANCE = 2.0        # PCB-to-wall gap each side
BOSS_OD        = 6.0
BOSS_HOLE_D    = 3.4        # M3 clearance (through) or 2.5 (self-tap)
FILLET_R       = 1.5        # external corner radius

# Derived
INNER_W = PCB_W + 2 * SIDE_CLEARANCE
INNER_L = PCB_L + 2 * SIDE_CLEARANCE
INNER_H = FLOOR + STANDOFF_H + 1.6 + COMP_H + LID_CLEARANCE  # 1.6 = PCB thickness
OUTER_W = INNER_W + 2 * WALL
OUTER_L = INNER_L + 2 * WALL
OUTER_H = INNER_H + WALL  # base only; lid is separate

HOLE_POSITIONS = <list of (x, y) tuples from Step 0 or Step 1>

# ── Base ───────────────────────────────────────────────────────────────────
base = (
    cq.Workplane("XY")
    .box(OUTER_W, OUTER_L, OUTER_H)
    .shell(-WALL, kind="intersection")   # hollow shell, open top
    .edges("|Z").fillet(FILLET_R)
)

# Mounting bosses
for hx, hy in HOLE_POSITIONS:
    bx = hx + WALL + SIDE_CLEARANCE - OUTER_W / 2
    by = hy + WALL + SIDE_CLEARANCE - OUTER_L / 2
    boss = (
        cq.Workplane("XY")
        .cylinder(FLOOR + STANDOFF_H, BOSS_OD / 2)
        .translate((bx, by, (FLOOR + STANDOFF_H) / 2))
    )
    base = base.union(boss)
    base = (
        base
        .faces(">Z").workplane()
        .pushPoints([(bx, by)])
        .hole(BOSS_HOLE_D, FLOOR + STANDOFF_H)
    )

# Connector cutouts (from Step 0-A or manual spec)
# <add cutter blocks per connector_cutouts list>

# ── Lid ───────────────────────────────────────────────────────────────────
lid = (
    cq.Workplane("XY")
    .box(OUTER_W, OUTER_L, WALL)
    .edges("|Z").fillet(FILLET_R)
)
# For screw lid: add 4 corner bosses with M3 holes
# For snap lid:  add 1.2 mm snap lip on inner perimeter

# IP gasket groove (add if ip_rating is IP54 or better)
# <1.5 mm wide × 1.0 mm deep groove at lid mating face perimeter>

result = base   # change to `lid` when exporting lid separately
```

Rules:
- Store the base in `result` for all MCP tool calls.
- Model base and lid as separate variables; export each independently.
- Never use `.shell()` with open faces if the model has fillets first — fillet after shell.

---

## Step 3 — Execute and validate

```
cq_execute_script(script=<script>)
```

If the response contains `"error_type": "import_error"`:
- Stop immediately.
- Report to the user: "CadQuery is not installed on the MCP server. Run:
  `pip install cadquery` in the server's Python environment, then restart
  the MCP server."
- Do not attempt to work around the missing library.

On OCC kernel errors:
- `BRep_API: command not done` — the boolean (union/cut) failed; check that
  cutter bodies actually intersect the target.
- `StdFail_NotDone` — a fillet radius is too large; reduce `FILLET_R` or use
  `chamfer()` instead.
- Fix and retry. Do not proceed until `success: true`.

---

## Step 4 — Measure volume

```
cq_measure_volume(script=<script>, shape_var="result")
```

Expected: `volume_mm3 > 0` and `is_solid: true`.
Cross-check the bounding box matches `OUTER_W × OUTER_L × OUTER_H` (±0.5 mm).

---

## Step 5 — Clearance checks

Run `cq_check_clearance` for each interface:

| Interface | script_a | script_b | Expected |
|-----------|----------|----------|----------|
| PCB body vs enclosure inner | PCB box at correct position | base | ≥ 2.0 mm |
| Lid vs base mating face | lid | base | 0.05–0.15 mm |
| Boss hole vs M3 bolt shank | M3 cylinder D=3.0 | boss hole D=BOSS_HOLE_D | ≥ 0.2 mm |

For each check with status `INTERFERENCE` or `TIGHT`: adjust the relevant parameter
and re-execute from Step 3.

---

## Step 6 — Export

```
cq_export_step(script=<base_script>, output_path="<output_dir>/enclosure_base_v1.step")
cq_export_stl( script=<base_script>, output_path="<output_dir>/enclosure_base_v1.stl", tolerance=0.05)
cq_export_step(script=<lid_script>,  output_path="<output_dir>/enclosure_lid_v1.step")
cq_export_stl( script=<lid_script>,  output_path="<output_dir>/enclosure_lid_v1.stl", tolerance=0.05)
cq_export_dxf( script=<lid_script>,  output_path="<output_dir>/enclosure_lid_v1.dxf",  plane="XY")
```

---

## Step 7 — Build the SAGE proposal

Submit a proposal containing:

1. **KiCad parse report** (if Step 0 was run) — full text of the parse report.

2. **Parameter table** (Markdown):

   | Parameter | Value | Unit | Notes |
   |-----------|-------|------|-------|
   | PCB_W | … | mm | from KiCad Edge.Cuts / manual |
   | PCB_L | … | mm | from KiCad Edge.Cuts / manual |
   | COMP_H | … | mm | from BOM CSV / heuristic / manual |
   | WALL | … | mm | process default |
   | … | | | |

3. **Exported files** — list paths and file sizes.

4. **Clearance report** — one row per interface.

5. **CadQuery script** — full text of both base and lid scripts.

6. **Print settings recommendation** (FDM only):
   - Layer height: 0.2 mm, Infill: 30% gyroid, Walls: 3 perimeters,
     Supports: tree on build plate only.

Flag the proposal for HITL approval before committing any files.
````

---

**4b. `.claude/skills/model-mechanical-part.md`**

````markdown
# Skill: model-mechanical-part

Model custom mechanical parts using CadQuery: brackets, heatsink clips, DIN rail mounts,
standoffs, and freeform parts. Follow every step in order.

---

## Step 1 — Identify part type and gather spec

### L-bracket

| Input | Example |
|-------|---------|
| `flange_a_w` | 30.0 mm |
| `flange_a_l` | 40.0 mm |
| `flange_b_w` | 30.0 mm |
| `flange_b_l` | 40.0 mm |
| `thickness` | 2.5 mm |
| `hole_d` | 3.4 mm (M3 clearance) |
| `hole_positions_a` | [{x:8,y:8},{x:8,y:32}] |
| `hole_positions_b` | [{x:8,y:8},{x:8,y:32}] |

### Heatsink clip

| Input | Example |
|-------|---------|
| `heatsink_w` | 40.0 mm |
| `heatsink_h` | 25.0 mm |
| `pin_pitch` | 2.54 mm |
| `spring_thickness` | 0.8 mm |
| `spring_gap` | 0.3 mm (nominal push-fit) |
| `retention_tab_w` | 5.0 mm |

### DIN rail mount (EN 60715 TS35)

| Input | Example |
|-------|---------|
| `module_w` | 45.0 mm |
| `module_h` | 60.0 mm |
| `module_d` | 35.0 mm |
| `rail_type` | "TS35" |
| `fixed_tab` | true (one side fixed, one spring) |
| `spring_deflection_mm` | 2.5 |

### Custom

Collect all relevant dimensions. Ask if anything is ambiguous — wrong dimensions
mean a failed print or machined scrap.

---

## Step 2 — Write the CadQuery script

### Template: L-bracket

```python
"""L-bracket for <application> — v1"""
import cadquery as cq

FLANGE_A_W = <flange_a_w>
FLANGE_A_L = <flange_a_l>
FLANGE_B_W = <flange_b_w>
FLANGE_B_L = <flange_b_l>
T          = <thickness>
HOLE_D     = <hole_d>
FILLET_R   = min(T * 0.8, 1.5)

HOLES_A = <list of (x,y)>
HOLES_B = <list of (x,y)>

flange_a = cq.Workplane("XY").box(FLANGE_A_W, FLANGE_A_L, T)
flange_b = (
    cq.Workplane("YZ")
    .box(FLANGE_B_L, FLANGE_B_W, T)
    .translate((0, 0, T + FLANGE_B_W / 2))
)
result = flange_a.union(flange_b).edges("|Z").fillet(FILLET_R)

for hx, hy in HOLES_A:
    result = result.faces("<Z").workplane().pushPoints([(hx - FLANGE_A_W/2, hy - FLANGE_A_L/2)]).hole(HOLE_D)

for hx, hy in HOLES_B:
    result = result.faces(">X").workplane().pushPoints([(hx - FLANGE_B_L/2, hy - FLANGE_B_W/2)]).hole(HOLE_D)
```

### Template: DIN rail clip (snap-on TS35)

```python
"""DIN rail snap clip — TS35 — v1"""
import cadquery as cq

RAIL_W          = 35.0
RAIL_H          = 7.5
MODULE_D        = <module_d>
CLIP_T          = 2.0
SPRING_T        = 0.8
SPRING_DEFLECT  = 2.5   # mm over-centre for retention

upper_tab = (
    cq.Workplane("XY")
    .box(RAIL_W + 2 * CLIP_T, CLIP_T + RAIL_H, CLIP_T)
    .translate((0, 0, 0))
)
base = cq.Workplane("XY").box(RAIL_W + 2 * CLIP_T, MODULE_D, CLIP_T)
spring_arm = (
    cq.Workplane("XZ")
    .box(RAIL_W, SPRING_T, RAIL_H + SPRING_DEFLECT)
    .translate((0, -(MODULE_D / 2 - SPRING_T / 2), -(RAIL_H + SPRING_DEFLECT) / 2))
)
spring_tip = (
    cq.Workplane("XY")
    .box(RAIL_W, CLIP_T * 1.5, CLIP_T)
    .translate((0, -(MODULE_D / 2 - CLIP_T * 1.5 / 2), -(RAIL_H + SPRING_DEFLECT)))
)

result = base.union(upper_tab).union(spring_arm).union(spring_tip)
```

### Template: heatsink clip

```python
"""Push-fit heatsink retention clip — v1"""
import cadquery as cq

HS_W            = <heatsink_w>
HS_H            = <heatsink_h>
SPRING_T        = <spring_thickness>
SPRING_GAP      = <spring_gap>
RETENTION_TAB_W = <retention_tab_w>
CLIP_T          = 1.5

frame_w = HS_W + 2 * (SPRING_GAP + SPRING_T)
frame_h = HS_H + CLIP_T
frame = (
    cq.Workplane("XY")
    .rect(frame_w, frame_h).extrude(RETENTION_TAB_W)
    .shell(-SPRING_T, kind="intersection")
)
tab_top    = cq.Workplane("XY").box(frame_w, CLIP_T, RETENTION_TAB_W).translate((0,  frame_h / 2, 0))
tab_bottom = cq.Workplane("XY").box(frame_w, CLIP_T, RETENTION_TAB_W).translate((0, -frame_h / 2, 0))

result = frame.union(tab_top).union(tab_bottom)
```

---

## Step 3 — Execute, measure, clearance-check

```
cq_execute_script(script=<script>)
cq_measure_volume(script=<script>)
```

If the response contains `"error_type": "import_error"`:
- Stop immediately.
- Report to the user: "CadQuery is not installed on the MCP server. Run:
  `pip install cadquery` in the server's Python environment, then restart
  the MCP server."
- Do not attempt to work around the missing library.

Minimum clearance checks by part type:

| Part type | Check | Expected |
|-----------|-------|----------|
| L-bracket | hole vs M3 bolt | ≥ 0.2 mm |
| DIN clip  | clip inner vs rail profile | 0.2–0.5 mm running clearance |
| DIN clip  | spring tip vs rail lower edge | 0.0–0.1 mm (snap-through) |
| Heatsink clip | clip inner vs heatsink body | `SPRING_GAP` ± 0.05 mm |

On INTERFERENCE: increase gap parameter and re-run.
On TIGHT with spring parts: this is expected — verify the gap matches `SPRING_GAP`.

---

## Step 4 — Export

```
cq_export_step(script=<script>, output_path="<output_dir>/<part_name>_v1.step")
cq_export_stl( script=<script>, output_path="<output_dir>/<part_name>_v1.stl", tolerance=0.05)
```

For sheet-metal brackets, also export DXF:
```
cq_export_dxf(script=<unfolded_flat_script>, output_path="<output_dir>/<part_name>_flat_v1.dxf", plane="XY")
```

---

## Step 5 — Parameter table and SAGE proposal

Emit a Markdown parameter table:

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| RAIL_W | 35.0 | mm | EN 60715 TS35 fixed |
| SPRING_T | 0.8 | mm | PETG recommended |
| SPRING_DEFLECT | 2.5 | mm | ~20 N retention force at this deflection |
| … | | | |

Include fabrication notes:
- **FDM**: print spring arms vertically (Z-direction) to maximise layer-bond strength.
- **PETG over PLA** for spring arms — higher fatigue life.
- **Aluminium brackets**: deburr all edges, countersink holes if flush-mounting required.

Submit the proposal through the SAGE HITL gate. Human approval required before
exporting files to the shared output directory.
````

---

**Addendum — `config/config.yaml` snippet**

```yaml
mcp_servers:
  cadquery:
    transport: stdio
    command: python
    args:
      - mcp-cadquery/server.py
    description: "CadQuery parametric 3-D CAD — enclosures, brackets, DIN mounts"
    tools:
      - cq_execute_script
      - cq_export_step
      - cq_export_stl
      - cq_export_dxf
      - cq_measure_volume
      - cq_check_clearance
    env:
      PYTHONPATH: "."
    roles:
      - mechanical_engineer
```