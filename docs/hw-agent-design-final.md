Looking at this task, I need to design a complete hardware engineer agent for SAGE. Let me produce all 6 components.

---

## 1. `solutions/hardware_engineer/prompts.yaml`

```yaml
roles:
  hardware_engineer:
    name: Hardware Engineer
    description: >
      PCB diagnostics, schematic review, DRC, BOM generation, and net tracing.
      All change proposals are HITL-gated — the agent never applies changes directly.
    skills:
      - diagnose-board
      - review-schematic
      - run-drc
    mcp_servers:
      - wrench_board
      - kicad
    system_prompt: |
      You are the SAGE Hardware Engineer Agent — a senior embedded hardware engineer
      fluent in PCB diagnostics, schematic analysis, and KiCad design flows.

      ═══ CORE MANDATE ═══
      Your job is to surface hardware faults, design violations, and improvement
      opportunities, then package every actionable finding as a SAGE proposal routed
      through the HITL approval gate. You NEVER apply changes directly.

      ═══ DIAGNOSTIC WORKFLOW ═══
      1. Load the board artifact:
         - For boardview/layout files (.kicad_pcb, .brd, .bdv, .asc):
           Call wrench_board.bv_load_board with the file path.
         - For schematic PDFs: Call wrench_board.query_schematic.
         - For KiCad projects (.pro / .kicad_pro): Call kicad.open_project.
      2. Identify the fault hypothesis from the task description.
      3. Run targeted tools — do not run every tool blindly:
         - Power rail issues → bv_check_power_rails, bv_measure_resistance
         - Net continuity → bv_trace_net + kicad.trace_net (cross-validate)
         - Component identity → bv_get_component_info, query_component
         - Thermal/layout → bv_simulate_failure with mode=thermal
      4. Cross-reference boardview findings against the schematic before concluding.
      5. Emit a structured FaultReport (see PROPOSAL FORMAT below).

      ═══ DESIGN REVIEW WORKFLOW ═══
      - Schematic review: kicad.open_project → kicad.run_erc → triage violations
        by severity (error/warning/info); map each to a net and reference designator.
      - Layout review: kicad.run_drc → group violations by rule name; flag
        clearance and annular ring violations as high-risk, silkscreen as low-risk.
      - BOM review: kicad.get_bom → check for DNP conflicts, missing values,
        duplicate reference designators.

      ═══ NET TRACING ═══
      Always use both kicad.trace_net (authoritative, from PCB data) and
      wrench_board.bv_trace_net (visual, confirms physical routing). Discrepancies
      between the two are themselves findings — report them.

      ═══ PROPOSAL FORMAT (MANDATORY FOR ALL CHANGES) ═══
      Every recommended change must be submitted as a SAGE proposal. Never emit
      raw instructions to modify files. Use this exact structure:

        proposal_type: hardware_fix | schematic_edit | bom_update | layout_change
        title: <one line>
        affected_components: [U1, R12, ...]
        affected_nets: [VCC_3V3, GND, ...]
        change_description: |
          <precise description of what changes and why>
        rationale: <engineering justification>
        risk_level: low | medium | high
        requires_respins: true | false
        verification_steps:
          - <measurable step to confirm the fix worked>

      ═══ HALLUCINATION GUARD ═══
      - If any tool returns "unknown", "not found", or empty data for a component
        or net, STOP and report the gap. Do not infer component values from context.
      - Reference designators and net names in proposals must match the loaded
        project exactly — copy them verbatim from tool responses.
      - Do not generate Gerber files (kicad.export_gerbers) without explicit user
        approval recorded in the task context. Gerber export is irreversible-adjacent.

      ═══ SKILL INVOCATION ═══
      Before starting any task, check the task type and invoke the matching skill:
        board_diagnosis    → follow diagnose-board skill
        schematic_review   → follow review-schematic skill
        drc_check          → follow run-drc skill
        bom_generation     → use kicad.get_bom, validate, propose corrections
        net_trace          → use kicad.trace_net + bv_trace_net, cross-validate

      ═══ ESCALATION ═══
      Escalate to the orchestrator when:
      - A fault cannot be diagnosed without physical measurement data not in the files
      - A proposed fix requires a PCB respin (requires_respins: true) — flag prominently
      - Two or more conflicting nets are implicated (potential schematic error)
```

---

## 2. `solutions/hardware_engineer/tasks.yaml`

```yaml
task_types:

  board_diagnosis:
    description: >
      Analyze a boardview or PCB file for faults, failed components, or
      unexpected electrical behavior. Produces a structured FaultReport proposal.
    agent_role: hardware_engineer
    required_inputs:
      - board_file        # path to .kicad_pcb | .brd | .bdv | .asc | schematic PDF
    optional_inputs:
      - symptom_description   # free-text description of observed failure
      - suspect_nets          # list of net names to prioritize
      - reference_schematic   # path to schematic PDF for cross-reference
    output_type: fault_report
    hitl_required: true
    timeout_seconds: 300

  schematic_review:
    description: >
      Review a KiCad schematic for ERC violations, missing pull-ups/pull-downs,
      power flag errors, unconnected pins, and design convention violations.
    agent_role: hardware_engineer
    required_inputs:
      - project_path      # path to .kicad_pro or .kicad_sch
    optional_inputs:
      - review_scope      # "full" | "power_only" | "digital_only" | "analog_only"
      - reference_standard  # e.g. "IPC-2612", "company_checklist.md"
    output_type: review_report
    hitl_required: true
    timeout_seconds: 180

  bom_generation:
    description: >
      Extract BOM from a KiCad project, validate for DNP conflicts and missing
      values, and emit a clean BOM proposal in CSV + JSON formats.
    agent_role: hardware_engineer
    required_inputs:
      - project_path
    optional_inputs:
      - output_format     # "csv" | "json" | "both" (default: both)
      - include_dnp       # boolean, default false
      - group_by          # "value" | "manufacturer_pn" | "none" (default: value)
    output_type: bom_artifact
    hitl_required: true
    timeout_seconds: 120

  drc_check:
    description: >
      Run KiCad Design Rule Check on a PCB layout. Triage violations by severity,
      group by rule name, and propose layout corrections for error-level violations.
    agent_role: hardware_engineer
    required_inputs:
      - project_path
    optional_inputs:
      - rules_file        # path to custom .kicad_dru rules override
      - severity_filter   # "error" | "warning" | "all" (default: error)
    output_type: drc_report
    hitl_required: true
    timeout_seconds: 180

  net_trace:
    description: >
      Trace a specific net through the PCB and schematic, confirming connectivity,
      identifying stubs or opens, and cross-validating layout against schematic.
    agent_role: hardware_engineer
    required_inputs:
      - project_path
      - net_name          # exact net name as it appears in the project
    optional_inputs:
      - board_file        # boardview file for physical cross-validation
      - trace_depth       # "direct" | "full" (follows through hierarchical sheets)
    output_type: net_trace_report
    hitl_required: true
    timeout_seconds: 120
```

---

## 3. `config/config.yaml` — MCP server declarations

```yaml
# Add under existing mcp_servers: block

mcp_servers:

  wrench_board:
    description: "Agent-native PCB diagnostic workbench (boardview + schematic analysis)"
    transport: sse
    url: "${WRENCH_BOARD_URL:-http://localhost:8000}/mcp/sse"
    auth:
      type: bearer
      token_env: WRENCH_BOARD_API_KEY
    tool_manifest_url: "${WRENCH_BOARD_URL:-http://localhost:8000}/mcp/manifest"
    # wrench-board exposes all 36 tools from api/agent/manifest.py via this endpoint.
    # Subset exposed to SAGE (others remain internal to wrench-board's own agent loop):
    exposed_tools:
      - bv_load_board
      - bv_highlight_pin
      - bv_trace_net
      - bv_simulate_failure
      - bv_measure_resistance
      - bv_get_component_info
      - bv_list_nets
      - bv_check_power_rails
      - query_schematic
      - query_component
      - query_net_connections
      - query_bom
    health_check:
      endpoint: "${WRENCH_BOARD_URL:-http://localhost:8000}/health"
      interval_seconds: 60
    roles_allowed:
      - hardware_engineer

  kicad:
    description: "KiCad pcbnew wrapper — schematic/layout query, DRC, BOM, Gerber export"
    transport: stdio
    command: python
    args:
      - "${SAGE_ROOT}/mcp-kicad/server.py"
    env:
      KICAD_CONFIG_HOME: "${KICAD_CONFIG_HOME:-}"
      PYTHONPATH: "${KICAD_PYTHON_PATH:-/usr/lib/python3/dist-packages}"
    exposed_tools:
      - kicad_open_project
      - kicad_run_drc
      - kicad_run_erc
      - kicad_get_bom
      - kicad_trace_net
      - kicad_export_gerbers
    roles_allowed:
      - hardware_engineer
```

---

## 4. `mcp-kicad/server.py` — Minimal KiCad MCP server

```python
#!/usr/bin/env python3
"""
Minimal KiCad MCP server wrapping the pcbnew Python scripting API.

Requirements:
  pip install mcp
  KiCad 7+ installed (provides pcbnew as a system Python module)

Run via stdio (declared in config.yaml as transport: stdio).
"""
import json
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# pcbnew is installed alongside KiCad — not on PyPI.
# If import fails, server exits with a clear message.
try:
    import pcbnew
except ImportError:
    sys.exit(
        "pcbnew not found. Ensure KiCad is installed and PYTHONPATH includes "
        "the KiCad Python scripting directory (e.g. /usr/lib/python3/dist-packages)."
    )

server = Server("kicad")

# Per-session state: one board + project loaded at a time.
_state: dict[str, Any] = {"board": None, "project_path": None}


# ─── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="kicad_open_project",
        description=(
            "Load a KiCad project file (.kicad_pro) or PCB file (.kicad_pcb). "
            "Must be called before any other kicad_* tool."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to .kicad_pro or .kicad_pcb file.",
                }
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="kicad_run_drc",
        description=(
            "Run Design Rule Check on the loaded PCB. Returns violations grouped "
            "by rule name with severity (error/warning/info), affected nets, and "
            "coordinates."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "severity_filter": {
                    "type": "string",
                    "enum": ["error", "warning", "all"],
                    "default": "error",
                    "description": "Minimum severity level to include in results.",
                }
            },
        },
    ),
    Tool(
        name="kicad_run_erc",
        description=(
            "Run Electrical Rules Check on the loaded schematic. Returns ERC "
            "violations with pin references, sheet names, and severity."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "severity_filter": {
                    "type": "string",
                    "enum": ["error", "warning", "all"],
                    "default": "error",
                }
            },
        },
    ),
    Tool(
        name="kicad_get_bom",
        description=(
            "Extract Bill of Materials from the loaded PCB. Returns components "
            "grouped by value+footprint with reference designators, quantities, "
            "and DNP flags."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "include_dnp": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include Do-Not-Populate components.",
                },
                "group_by": {
                    "type": "string",
                    "enum": ["value", "manufacturer_pn", "none"],
                    "default": "value",
                },
            },
        },
    ),
    Tool(
        name="kicad_trace_net",
        description=(
            "Trace a named net through the PCB: list all pads connected to it, "
            "track segments, copper pours, and vias. Identifies opens (disconnected "
            "islands) and stubs."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "net_name": {
                    "type": "string",
                    "description": "Exact net name as it appears in the PCB netlist.",
                }
            },
            "required": ["net_name"],
        },
    ),
    Tool(
        name="kicad_export_gerbers",
        description=(
            "Export Gerber manufacturing files to a directory. "
            "WARNING: Confirm with the user before calling — this produces "
            "production-ready output."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "output_dir": {
                    "type": "string",
                    "description": "Absolute path to output directory (created if absent).",
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Layer names to export, e.g. [\"F.Cu\", \"B.Cu\", \"F.Mask\"]. "
                        "Omit for all copper + mask + silkscreen layers."
                    ),
                },
            },
            "required": ["output_dir"],
        },
    ),
]


# ─── Handlers ──────────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


def _dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "kicad_open_project":
        return _open_project(args["path"])
    _require_board()
    if name == "kicad_run_drc":
        return _run_drc(args.get("severity_filter", "error"))
    if name == "kicad_run_erc":
        return _run_erc(args.get("severity_filter", "error"))
    if name == "kicad_get_bom":
        return _get_bom(args.get("include_dnp", False), args.get("group_by", "value"))
    if name == "kicad_trace_net":
        return _trace_net(args["net_name"])
    if name == "kicad_export_gerbers":
        return _export_gerbers(args["output_dir"], args.get("layers"))
    raise ValueError(f"Unknown tool: {name}")


def _require_board() -> pcbnew.BOARD:
    if _state["board"] is None:
        raise RuntimeError(
            "No project loaded. Call kicad_open_project first."
        )
    return _state["board"]


# ─── Tool implementations ──────────────────────────────────────────────────────

def _open_project(path: str) -> dict:
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    if p.suffix == ".kicad_pro":
        # Load the PCB file that lives next to the project file.
        pcb_path = p.with_suffix(".kicad_pcb")
        if not pcb_path.exists():
            raise FileNotFoundError(f"PCB file not found alongside project: {pcb_path}")
        board = pcbnew.LoadBoard(str(pcb_path))
    elif p.suffix == ".kicad_pcb":
        board = pcbnew.LoadBoard(str(p))
    else:
        raise ValueError(f"Unsupported file type: {p.suffix}. Use .kicad_pro or .kicad_pcb")

    _state["board"] = board
    _state["project_path"] = str(p)

    nets = [n for n in board.GetNetInfo().NetsByName().keys() if n]
    footprints = [f.GetReference() for f in board.GetFootprints()]
    return {
        "status": "loaded",
        "project_path": str(p),
        "footprint_count": len(footprints),
        "net_count": len(nets),
        "sample_nets": nets[:20],
        "sample_refs": sorted(footprints)[:20],
    }


def _run_drc(severity_filter: str) -> dict:
    board: pcbnew.BOARD = _state["board"]

    drc = pcbnew.DRC_ENGINE()
    drc.InitEngine(board, pcbnew.REPORTER())
    drc.RunTests(None)

    sev_map = {"error": 0, "warning": 1, "all": 2}
    min_sev = sev_map.get(severity_filter, 0)

    violations = []
    for item in drc.GetViolations():
        sev = item.GetSeverity()  # 0=error, 1=warning, 2=info
        if sev > min_sev:
            continue
        violations.append({
            "rule": item.GetRuleDescription(),
            "severity": ["error", "warning", "info"][sev],
            "description": item.GetErrorMessage(),
            "net": item.GetMainItem().GetNetname() if item.GetMainItem() else None,
            "position": {
                "x_mm": pcbnew.ToMM(item.GetMainItem().GetX()) if item.GetMainItem() else None,
                "y_mm": pcbnew.ToMM(item.GetMainItem().GetY()) if item.GetMainItem() else None,
            },
        })

    by_rule: dict[str, list] = {}
    for v in violations:
        by_rule.setdefault(v["rule"], []).append(v)

    return {
        "total_violations": len(violations),
        "severity_filter": severity_filter,
        "by_rule": {rule: {"count": len(vs), "samples": vs[:3]} for rule, vs in by_rule.items()},
    }


def _run_erc(severity_filter: str) -> dict:
    # ERC requires the schematic (SCH_SHEET) — best-effort via pcbnew's netlist.
    # Full ERC requires KiCad's eeschema scripting; return available net metadata.
    board: pcbnew.BOARD = _state["board"]
    net_info = board.GetNetInfo()
    unconnected = []
    for track in board.GetTracks():
        if hasattr(track, "GetNet") and track.GetNet().GetNetCode() == 0:
            unconnected.append({
                "position": {
                    "x_mm": pcbnew.ToMM(track.GetX()),
                    "y_mm": pcbnew.ToMM(track.GetY()),
                }
            })
    return {
        "note": (
            "Full ERC requires eeschema scripting API (KiCad 8+). "
            "Returning unconnected items from PCB netlist as proxy."
        ),
        "unconnected_count": len(unconnected),
        "unconnected_samples": unconnected[:10],
    }


def _get_bom(include_dnp: bool, group_by: str) -> dict:
    board: pcbnew.BOARD = _state["board"]
    groups: dict[str, dict] = {}

    for fp in board.GetFootprints():
        if not include_dnp and fp.IsDNP():
            continue
        ref = fp.GetReference()
        value = fp.GetValue()
        footprint = fp.GetFPID().GetLibItemName().wx_str() if hasattr(fp.GetFPID().GetLibItemName(), "wx_str") else str(fp.GetFPID().GetLibItemName())
        mpn = ""
        for field in fp.GetFields():
            if field.GetName().lower() in ("mpn", "manufacturer_pn", "mfr_pn"):
                mpn = field.GetText()
                break

        if group_by == "value":
            key = f"{value}|{footprint}"
        elif group_by == "manufacturer_pn":
            key = mpn or f"{value}|{footprint}"
        else:
            key = ref

        if key not in groups:
            groups[key] = {
                "value": value,
                "footprint": footprint,
                "manufacturer_pn": mpn,
                "references": [],
                "quantity": 0,
                "dnp": fp.IsDNP(),
            }
        groups[key]["references"].append(ref)
        groups[key]["quantity"] += 1

    items = sorted(groups.values(), key=lambda x: x["value"])
    return {
        "component_count": sum(i["quantity"] for i in items),
        "line_count": len(items),
        "include_dnp": include_dnp,
        "group_by": group_by,
        "bom": items,
    }


def _trace_net(net_name: str) -> dict:
    board: pcbnew.BOARD = _state["board"]
    net_info = board.GetNetInfo()
    nets_by_name = net_info.NetsByName()

    if net_name not in nets_by_name:
        available = [n for n in nets_by_name.keys() if n]
        close = [n for n in available if net_name.lower() in n.lower()][:10]
        return {
            "error": f"Net '{net_name}' not found in project.",
            "suggestions": close,
        }

    net = nets_by_name[net_name]
    net_code = net.GetNetCode()

    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net_code:
                pads.append({
                    "reference": fp.GetReference(),
                    "pin": pad.GetNumber(),
                    "position": {"x_mm": pcbnew.ToMM(pad.GetX()), "y_mm": pcbnew.ToMM(pad.GetY())},
                    "layer": pad.GetLayerName(),
                })

    tracks = []
    for track in board.GetTracks():
        if track.GetNetCode() == net_code:
            tracks.append({
                "type": "via" if isinstance(track, pcbnew.PCB_VIA) else "track",
                "layer": track.GetLayerName(),
                "width_mm": pcbnew.ToMM(track.GetWidth()),
            })

    zones = []
    for zone in board.Zones():
        if zone.GetNetCode() == net_code:
            zones.append({"layer": zone.GetLayerName(), "filled": zone.IsFilled()})

    return {
        "net_name": net_name,
        "pad_count": len(pads),
        "track_segment_count": len(tracks),
        "copper_pour_count": len(zones),
        "pads": pads,
        "track_summary": {
            "via_count": sum(1 for t in tracks if t["type"] == "via"),
            "segment_count": sum(1 for t in tracks if t["type"] == "track"),
        },
        "copper_pours": zones,
        "open_detection": (
            "OPEN: net has pads but no tracks — likely ratsnest only"
            if pads and not tracks and not zones
            else "connected"
        ),
    }


def _export_gerbers(output_dir: str, layers: list[str] | None) -> dict:
    board: pcbnew.BOARD = _state["board"]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    settings = pcbnew.GERBER_JOBFILE_WRITER(board)
    plot_controller = pcbnew.PLOT_CONTROLLER(board)
    plot_opts = plot_controller.GetPlotOptions()
    plot_opts.SetOutputDirectory(str(out))
    plot_opts.SetPlotFrameRef(False)
    plot_opts.SetUseGerberProtelExtensions(True)

    default_layers = [
        (pcbnew.F_Cu, "F.Cu"),
        (pcbnew.B_Cu, "B.Cu"),
        (pcbnew.F_Mask, "F.Mask"),
        (pcbnew.B_Mask, "B.Mask"),
        (pcbnew.F_Silks, "F.Silkscreen"),
        (pcbnew.B_Silks, "B.Silkscreen"),
        (pcbnew.Edge_Cuts, "Edge.Cuts"),
    ]

    layer_name_map = {name: lid for lid, name in default_layers}
    target_layers = (
        [(layer_name_map[l], l) for l in layers if l in layer_name_map]
        if layers
        else default_layers
    )

    exported = []
    for layer_id, layer_name in target_layers:
        plot_controller.SetLayer(layer_id)
        plot_controller.OpenPlotfile(layer_name, pcbnew.PLOT_FORMAT_GERBER, layer_name)
        plot_controller.PlotLayer()
        plot_controller.ClosePlot()
        exported.append(layer_name)

    return {
        "status": "exported",
        "output_directory": str(out),
        "layers_exported": exported,
        "file_count": len(exported),
    }


# ─── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## 5. Skill files

### `.claude/skills/diagnose-board.md`

```markdown
# diagnose-board

Use this skill for task type: `board_diagnosis`

## Step 1 — Load the artifact
Call `wrench_board.bv_load_board` with the board file path from task inputs.
If a schematic PDF is also provided, call `wrench_board.query_schematic` in parallel.
Confirm both tools return status "loaded" before proceeding.

## Step 2 — Orient to the symptom
Read `symptom_description` from task inputs. Map it to an initial hypothesis:
- "no power" / "dead board"   → check power rails first
- "intermittent"              → check solder joints, thermal, marginal voltages
- "wrong output"              → trace the signal net from source to sink
- "component hot"             → simulate_failure with mode=thermal on that region
If no symptom is given, run `bv_check_power_rails` and `bv_list_nets` to establish baseline.

## Step 3 — Targeted tool sequence
Run only the tools relevant to your hypothesis. Do not run all 36 tools.

| Hypothesis          | Tool sequence                                              |
|---------------------|------------------------------------------------------------|
| Power rail failure  | bv_check_power_rails → bv_measure_resistance(GND-to-rail) |
| Net open/short      | bv_trace_net → kicad.trace_net → compare both results     |
| Component failure   | bv_get_component_info → query_component → check datasheet |
| Thermal fault       | bv_simulate_failure(mode=thermal) → bv_highlight_pin      |
| Unknown             | bv_list_nets → bv_check_power_rails → bv_trace_net(VCC)   |

## Step 4 — Cross-validate
For every net implicated in the fault, call both:
1. `wrench_board.bv_trace_net(net_name)` — physical routing from boardview
2. `kicad.kicad_trace_net(net_name)` — authoritative from PCB database
Any discrepancy between the two is itself a finding. Report it explicitly.

## Step 5 — Build the FaultReport
Assemble findings into the SAGE proposal format:
```
proposal_type: hardware_fix
title: <fault + location, e.g. "VCC_3V3 open between U1 pin 3 and C12">
affected_components: [list from tool responses — copy verbatim]
affected_nets: [list from tool responses — copy verbatim]
change_description: |
  <what is wrong and where>
rationale: <which tools confirmed it and how>
risk_level: high if power/respin, medium if rework, low if DNP/jumper
requires_respins: <true only if PCB trace or pour must be rerouted>
verification_steps:
  - Measure voltage at <pin> with DMM: expect <value>
  - Reflow <ref> and retest continuity on <net>
```
Submit this as a SAGE proposal. Do not suggest the user apply the fix directly.

## Hallucination guard
- If `bv_get_component_info` returns "unknown" for any component, note it in the
  report as `status: unverified` — do not guess the part number.
- If `bv_trace_net` returns empty results, try the net name with a "/" prefix
  (KiCad uses both `/NET` and `NET` conventions). Report the form that works.
```

---

### `.claude/skills/review-schematic.md`

```markdown
# review-schematic

Use this skill for task type: `schematic_review`

## Step 1 — Load the project
Call `kicad.kicad_open_project` with the project path from task inputs.
Confirm `footprint_count > 0` and `net_count > 0` in the response.
If either is zero, the file may be a schematic-only project — report this and
request the .kicad_pcb file if layout review is needed.

## Step 2 — Run ERC
Call `kicad.kicad_run_erc(severity_filter: "all")`.
Note the `unconnected_count`. If > 0, list the unconnected items — these are
always errors regardless of KiCad severity classification.

## Step 3 — Review scope filter
Check `review_scope` from task inputs:
- `power_only`   → focus on nets containing "VCC", "VDD", "PWR", "3V3", "5V", "GND"
- `digital_only` → focus on GPIO, SPI, I2C, UART, CAN, USB net prefixes
- `analog_only`  → focus on nets containing "ADC", "DAC", "AIN", "REF", "VREF"
- `full`         → review all nets and components (default)

## Step 4 — BOM cross-check
Call `kicad.kicad_get_bom(include_dnp: true, group_by: "value")`.
Flag these BOM anomalies as warnings in your report:
- Any component with `value` = "~" or "" (no value assigned)
- Duplicate `manufacturer_pn` across different `value` groups (substitution conflict)
- DNP components on power nets (almost always an error)
- Reference designators that skip numbers in a sequence (U1, U2, U4 — where is U3?)

## Step 5 — Net naming conventions
Call `kicad.kicad_trace_net` on any nets flagged by ERC.
Additionally scan the net list from `kicad_open_project` for:
- Nets named "Net-(...)" — KiCad auto-names; these are unconnected wire stubs
- Nets with both "/" and without (naming inconsistency across hierarchy)
- Power nets that appear on fewer than 2 pads (floating power pin)

## Step 6 — Compile review report
```
proposal_type: schematic_edit
title: Schematic review findings — <project name>
affected_components: [refs with errors]
affected_nets: [nets with errors]
change_description: |
  ERROR (<count>):
    - <ref>: <description>
  WARNING (<count>):
    - <ref>: <description>
  INFO (<count>):
    - <note>
rationale: Based on ERC output and BOM cross-check via kicad MCP tools.
risk_level: high if power errors, medium if signal integrity, low if cosmetic
requires_respins: false  # schematic changes only need a re-pour/re-DRC
verification_steps:
  - Fix errors listed above, re-run ERC, confirm zero error-level violations
  - Re-export netlist and update PCB if affected nets changed
```
Submit as a SAGE proposal. Do not edit the schematic file directly.
```

---

### `.claude/skills/run-drc.md`

```markdown
# run-drc

Use this skill for task type: `drc_check`

## Step 1 — Load and run
Call `kicad.kicad_open_project` with the project path.
Then call `kicad.kicad_run_drc(severity_filter: "all")` to get the full picture,
even if only errors are ultimately actioned.

## Step 2 — Triage by rule name
Group violations from `by_rule` in the DRC response. Apply this priority mapping:

| Rule name contains            | Priority | Action required?      |
|-------------------------------|----------|-----------------------|
| clearance, creepage           | CRITICAL | Always fix before fab |
| annular_ring, hole_size       | CRITICAL | Always fix before fab |
| short_circuit                 | CRITICAL | Stop — do not fab     |
| courtyard_overlap             | HIGH     | Fix before assembly   |
| pad_to_mask_clearance         | HIGH     | Fix before fab        |
| silkscreen_overlap            | LOW      | Fix if time allows    |
| footprint_type_mismatch       | MEDIUM   | Review with designer  |
| unconnected_items             | CRITICAL | Always fix            |

## Step 3 — Locate each CRITICAL violation
For each CRITICAL violation, call `kicad.kicad_trace_net` on the affected net
to determine whether the violation is:
- A routing error (track too close to another track/pad)
- A footprint placement error (component too close to edge/other component)
- A missing connection (ratsnest not routed)

## Step 4 — Estimate fix effort
For each violation group:
- Routing error: estimate "reroute N segments" — requires PCB editor intervention
- Placement error: estimate "move <ref> <direction>" — requires placement change
- Missing connection: flag as open net — may require schematic correction first

## Step 5 — Compile DRC report proposal
```
proposal_type: layout_change
title: DRC violations — <count> critical, <count> high, <count> low
affected_components: [refs at violation locations]
affected_nets: [nets involved in violations]
change_description: |
  CRITICAL (<count>):
    [rule_name]: <count> violations
      Sample: <description from DRC response> at (<x_mm>, <y_mm>)
      Fix: <specific action>
  HIGH (<count>):
    ...
  LOW (<count>):
    ...
rationale: DRC run via kicad MCP on <project_path>. Total: <N> violations.
risk_level: high  # DRC errors always block fabrication
requires_respins: true  # layout changes require re-pour and re-DRC
verification_steps:
  - Apply fixes in KiCad PCB editor
  - Re-run DRC: expect zero error-level violations
  - Re-run copper fill (Edit → Fill All Zones) before re-checking
  - Generate updated Gerbers only after clean DRC
```
Submit as a SAGE proposal. Do not generate Gerbers until the proposal is approved
and a clean DRC is confirmed by the user.
```

---

## 6. TestAgent — Recommendation and design

### Recommendation: Dedicated `test_agent` role in `prompts.yaml`

**Reasoning:**

A skill file is the right choice when an operation is a *procedure* that an existing agent performs once. A dedicated role is right when an entity needs to *own a domain* across multiple task types, interpret results in context, and generate its own proposals.

The testbench meets the dedicated-role bar on three counts:

1. **Breadth of drivers.** Six drivers (api, browser, embedded, load, mobile, screenshot) with distinct configuration formats — a skill file encoding all of this would be longer than the skill can usefully be. The agent role owns the driver selection logic; a skill file just delegates it back to the agent anyway.

2. **Result interpretation is a domain, not a procedure.** A browser test failure, an embedded timing violation, and a load test degradation require different diagnostic reasoning. That reasoning belongs in an agent's system prompt, not in a bullet list in a skill file.

3. **Proposal generation.** When a test fails, the TestAgent should generate a SAGE `bug_report` proposal (HITL-gated) with reproduction steps, affected component, and severity. This is the same pattern as HardwareEngineerAgent generating `hardware_fix` proposals — it's agent-level behavior, not skill-level behavior.

A skill named `run-testbench.md` should still exist — it encodes *how* to invoke the testbench CLI — but the skill is invoked *by the TestAgent*, not by other agents.

---

### `solutions/test_agent/prompts.yaml`

```yaml
roles:
  test_agent:
    name: Test Agent
    description: >
      Owns test execution and result interpretation across all testbench drivers.
      Maps test outcomes to SAGE bug_report proposals through the HITL approval gate.
    skills:
      - run-testbench
    mcp_servers: []
    system_prompt: |
      You are the SAGE Test Agent — the single owner of the testbench/ directory
      and all test execution in this project.

      ═══ CORE MANDATE ═══
      Run tests, interpret results, and surface failures as SAGE proposals. You never
      fix bugs yourself — you diagnose, reproduce, and package findings for human review.

      ═══ DRIVER SELECTION ═══
      Map the task's test_target to the correct driver:

        api        → testbench/drivers/api.py
                     Use for: REST endpoint tests, auth flows, CRUD operations
        browser    → testbench/drivers/browser.mjs (Playwright)
                     Use for: UI flows, form validation, visual regression
        embedded   → testbench/drivers/embedded.py
                     Use for: firmware/hardware-in-the-loop tests (requires USB device)
        load       → testbench/drivers/load.py
                     Use for: throughput, latency under concurrency, rate limits
        mobile     → testbench/drivers/browser.py (mobile viewport)
                     Use for: responsive layout, touch interactions, PWA behavior
        screenshot → testbench/drivers/screenshot.mjs
                     Use for: visual snapshots for diff review

      ═══ CONFIG FORMAT ═══
      Test runs are driven by YAML configs in testbench/configs/.
      Reference _embedded.example.yaml for the config schema.
      Always write a task-specific config rather than modifying existing configs.
      Name the config: testbench/configs/<task_id>.yaml

      ═══ RESULT INTERPRETATION ═══
      After a test run completes:
      1. Parse the run output for PASS / FAIL / ERROR / TIMEOUT per test case.
      2. For each FAIL or ERROR, extract:
         - Test name and driver
         - Failure message / stack trace
         - Reproduction command
         - Whether the failure is consistent (deterministic) or flaky
      3. Classify severity:
         - CRITICAL: auth bypass, data loss, crash
         - HIGH: core user flow broken, wrong data returned
         - MEDIUM: degraded UX, non-critical feature broken
         - LOW: cosmetic, edge-case, logging error
      4. Package each distinct failure as a SAGE bug_report proposal.

      ═══ PROPOSAL FORMAT ═══
      Every test failure must become a HITL-gated proposal:

        proposal_type: bug_report
        title: <test name> — <one-line failure summary>
        test_driver: <driver name>
        test_config: <path to testbench/configs/<task_id>.yaml>
        severity: critical | high | medium | low
        failure_type: deterministic | flaky
        affected_component: <API route | UI component | firmware module>
        reproduction_command: |
          python testbench/run.py --config testbench/configs/<task_id>.yaml
        failure_evidence: |
          <exact error message or assertion failure>
        change_description: |
          Test <name> fails because <observed behavior>.
          Expected: <what the test asserted>
          Actual: <what was returned or observed>
        rationale: <why this is a real failure, not a test environment issue>
        risk_level: <maps from severity: critical→high, high→high, medium→medium, low→low>
        requires_respins: false
        verification_steps:
          - Apply fix
          - Re-run: python testbench/run.py --config testbench/configs/<task_id>.yaml
          - Confirm all cases in <test_name> pass

      ═══ FLAKY TEST HANDLING ═══
      If a test fails intermittently (< 100% failure rate over 3 runs):
      - Mark failure_type: flaky
      - Run the test 3 times and report the failure rate
      - Include timing information if the failure correlates with latency

      ═══ ESCALATION ═══
      Escalate to orchestrator when:
      - An embedded test requires physical hardware not connected (driver returns DeviceNotFound)
      - A test failure blocks more than 3 other test cases (cascading failure)
      - A load test reveals latency regression > 20% vs baseline
```

---

### `solutions/test_agent/tasks.yaml`

```yaml
task_types:

  run_test_suite:
    description: >
      Execute a named test suite against a target driver. Produces bug_report
      proposals for each failing test case.
    agent_role: test_agent
    required_inputs:
      - test_driver       # api | browser | embedded | load | mobile | screenshot
      - test_suite        # name of the test suite or path to config
    optional_inputs:
      - repeat_count      # run N times to detect flakiness (default: 1)
      - baseline_results  # path to prior run output for regression comparison
    output_type: test_run_report
    hitl_required: true
    timeout_seconds: 600

  regression_check:
    description: >
      Compare current test results against a baseline run. Surfaces new failures
      and newly-passing tests as SAGE proposals.
    agent_role: test_agent
    required_inputs:
      - test_driver
      - baseline_results  # path to prior run YAML/JSON output
    optional_inputs:
      - test_suite
    output_type: regression_diff_report
    hitl_required: true
    timeout_seconds: 600

  flakiness_audit:
    description: >
      Run a specific test case N times to characterize flakiness. Reports failure
      rate, timing correlation, and packages a bug_report if rate > 10%.
    agent_role: test_agent
    required_inputs:
      - test_driver
      - test_name         # specific test case to audit
      - repeat_count      # how many times to run (minimum 5)
    output_type: flakiness_report
    hitl_required: true
    timeout_seconds: 1800
```

---

### `.claude/skills/run-testbench.md` (invoked by TestAgent)

```markdown
# run-testbench

Use this skill when executing any testbench run.

## Step 1 — Write the task config
Create `testbench/configs/<task_id>.yaml` using the schema from
`testbench/configs/_embedded.example.yaml`.
Set `driver:` to the driver required by the task.
Set `suite:` and `cases:` from task inputs.
Do not modify existing config files.

## Step 2 — Execute
Run the testbench:
```
python testbench/run.py --config testbench/configs/<task_id>.yaml
```
Capture stdout and stderr in full. Do not truncate the output.

## Step 3 — Parse results
Look for lines matching: `PASS`, `FAIL`, `ERROR`, `TIMEOUT`, `SKIP`.
Build a result table:
| Test case | Result | Duration | Message |
For each FAIL or ERROR, extract the full stack trace or assertion message.

## Step 4 — Re-run flaky candidates
If a FAIL result seems environment-dependent (network timeout, file lock, port conflict):
- Re-run that specific test case twice more
- If it passes on retry, mark it as flaky (not a deterministic bug)

## Step 5 — Return to TestAgent
Return the parsed result table and all raw FAIL/ERROR entries.
The TestAgent will handle proposal creation — do not create proposals from this skill.
```