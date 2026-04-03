"""
SAGE MCP Server — Hardware Design Tools
========================================
MCP tools that agents invoke to CREATE and VALIDATE hardware artifacts.

Wraps external tools (KiCad, FreeCAD, ngspice, gcc-arm-none-eabi) so
agents can produce real PCBs, 3D models, simulations, and firmware binaries.

Each tool checks if the external binary is available. If not, it returns
a structured error explaining what to install — the agent can then inform
the human via HITL.

Works with any LLM provider via MCPRegistry.invoke().
"""

import json
import logging
import os
import shutil
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger("hardware_tools_mcp")

try:
    from fastmcp import FastMCP
    mcp = FastMCP("hardware-tools")
except ImportError:
    logger.warning("fastmcp not installed — MCP server cannot start standalone")
    mcp = None


# ---------------------------------------------------------------------------
# Tool availability detection
# ---------------------------------------------------------------------------

def _check_tool(binary: str) -> Dict:
    """Check if an external tool binary is available."""
    path = shutil.which(binary)
    if path:
        try:
            version = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=10
            ).stdout.strip().split("\n")[0]
        except Exception:
            version = "available"
        return {"available": True, "path": path, "version": version}
    return {
        "available": False,
        "path": None,
        "version": None,
        "install_hint": _install_hints().get(binary, f"Install {binary}"),
    }


def _install_hints() -> Dict[str, str]:
    return {
        "kicad-cli": "sudo apt install kicad  # or brew install kicad",
        "freecad": "sudo apt install freecad  # or brew install freecad",
        "openscad": "sudo apt install openscad  # or brew install openscad",
        "ngspice": "sudo apt install ngspice  # or brew install ngspice",
        "arm-none-eabi-gcc": "sudo apt install gcc-arm-none-eabi  # or brew install arm-none-eabi-gcc",
        "cppcheck": "sudo apt install cppcheck  # MISRA-C static analysis",
    }


def _run_command(cmd: List[str], timeout: int = 60, cwd: Optional[str] = None) -> Dict:
    """Run an external command and return structured result."""
    binary = cmd[0]
    check = _check_tool(binary)
    if not check["available"]:
        return {
            "success": False,
            "error": f"{binary} not installed",
            "install_hint": check.get("install_hint", ""),
            "stdout": "",
            "stderr": "",
        }
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:5000],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool Status (discovery)
# ---------------------------------------------------------------------------

def list_hardware_tools() -> Dict:
    """List all available hardware tools and their status."""
    tools = {
        "kicad": {
            "name": "KiCad",
            "purpose": "PCB schematic capture, layout, DRC/ERC, Gerber generation, BOM",
            "binary": "kicad-cli",
            **_check_tool("kicad-cli"),
        },
        "freecad": {
            "name": "FreeCAD",
            "purpose": "3D mechanical CAD — enclosures, assemblies, STEP/STL export",
            "binary": "freecad",
            **_check_tool("freecad"),
        },
        "openscad": {
            "name": "OpenSCAD",
            "purpose": "Parametric 3D modeling via code — ideal for agent-generated designs",
            "binary": "openscad",
            **_check_tool("openscad"),
        },
        "ngspice": {
            "name": "ngspice",
            "purpose": "SPICE circuit simulation — analog/mixed-signal verification",
            "binary": "ngspice",
            **_check_tool("ngspice"),
        },
        "gcc_arm": {
            "name": "GCC ARM",
            "purpose": "ARM firmware cross-compilation (Cortex-M0/M3/M4/M7)",
            "binary": "arm-none-eabi-gcc",
            **_check_tool("arm-none-eabi-gcc"),
        },
        "cppcheck": {
            "name": "cppcheck",
            "purpose": "C/C++ static analysis — MISRA-C compliance checking",
            "binary": "cppcheck",
            **_check_tool("cppcheck"),
        },
    }
    available_count = sum(1 for t in tools.values() if t.get("available"))
    return {
        "tools": tools,
        "available_count": available_count,
        "total_count": len(tools),
    }


# ---------------------------------------------------------------------------
# KiCad Tools
# ---------------------------------------------------------------------------

def kicad_create_project(project_name: str, workspace: str) -> Dict:
    """Create a new KiCad project directory structure."""
    project_dir = os.path.join(workspace, project_name)
    os.makedirs(project_dir, exist_ok=True)

    # Create minimal KiCad project files
    kicad_pro = {
        "meta": {"filename": f"{project_name}.kicad_pro", "version": 1},
    }
    pro_path = os.path.join(project_dir, f"{project_name}.kicad_pro")
    with open(pro_path, "w") as f:
        json.dump(kicad_pro, f, indent=2)

    # Create empty schematic
    sch_path = os.path.join(project_dir, f"{project_name}.kicad_sch")
    with open(sch_path, "w") as f:
        f.write('(kicad_sch (version 20230121) (generator "sage_agent"))\n')

    # Create empty PCB
    pcb_path = os.path.join(project_dir, f"{project_name}.kicad_pcb")
    with open(pcb_path, "w") as f:
        f.write('(kicad_pcb (version 20221018) (generator "sage_agent"))\n')

    return {
        "success": True,
        "project_dir": project_dir,
        "files_created": [pro_path, sch_path, pcb_path],
    }


def kicad_run_erc(schematic_path: str) -> Dict:
    """Run Electrical Rules Check on a KiCad schematic."""
    return _run_command(["kicad-cli", "sch", "erc", schematic_path])


def kicad_run_drc(pcb_path: str) -> Dict:
    """Run Design Rules Check on a KiCad PCB."""
    return _run_command(["kicad-cli", "pcb", "drc", "--exit-code-violations", pcb_path])


def kicad_export_gerbers(pcb_path: str, output_dir: str) -> Dict:
    """Export Gerber files from KiCad PCB."""
    os.makedirs(output_dir, exist_ok=True)
    return _run_command([
        "kicad-cli", "pcb", "export", "gerbers",
        "-o", output_dir, pcb_path,
    ])


def kicad_export_bom(schematic_path: str, output_path: str) -> Dict:
    """Export Bill of Materials from KiCad schematic."""
    return _run_command([
        "kicad-cli", "sch", "export", "python-bom",
        "-o", output_path, schematic_path,
    ])


def kicad_export_netlist(schematic_path: str, output_path: str) -> Dict:
    """Export netlist from KiCad schematic for SPICE simulation."""
    return _run_command([
        "kicad-cli", "sch", "export", "netlist",
        "-o", output_path, schematic_path,
    ])


# ---------------------------------------------------------------------------
# FreeCAD / OpenSCAD Tools
# ---------------------------------------------------------------------------

def openscad_render(scad_file: str, output_stl: str) -> Dict:
    """Render OpenSCAD file to STL."""
    return _run_command(["openscad", "-o", output_stl, scad_file])


def openscad_render_png(scad_file: str, output_png: str) -> Dict:
    """Render OpenSCAD file to PNG preview."""
    return _run_command([
        "openscad", "--render", "-o", output_png,
        "--imgsize=1024,768", scad_file,
    ])


def freecad_export_step(fcstd_file: str, output_step: str) -> Dict:
    """Export FreeCAD model to STEP format for manufacturing."""
    return _run_command([
        "freecad", "--console",
        "-c", f"import Part; Part.open('{fcstd_file}'); Part.export(Part.getDocument('Unnamed').Objects, '{output_step}')",
    ], timeout=120)


# ---------------------------------------------------------------------------
# SPICE Simulation Tools
# ---------------------------------------------------------------------------

def ngspice_simulate(netlist_path: str, output_dir: str) -> Dict:
    """Run ngspice simulation on a netlist."""
    os.makedirs(output_dir, exist_ok=True)
    return _run_command([
        "ngspice", "-b", "-o", os.path.join(output_dir, "output.log"),
        netlist_path,
    ], timeout=120)


# ---------------------------------------------------------------------------
# Firmware Tools
# ---------------------------------------------------------------------------

def firmware_compile(
    source_dir: str,
    target: str = "cortex-m4",
    optimization: str = "-O2",
) -> Dict:
    """Compile firmware with gcc-arm-none-eabi."""
    c_files = []
    for root, _, files in os.walk(source_dir):
        for f in files:
            if f.endswith(".c"):
                c_files.append(os.path.join(root, f))

    if not c_files:
        return {"success": False, "error": "No .c files found in source directory"}

    cpu_flags = {
        "cortex-m0": "-mcpu=cortex-m0 -mthumb",
        "cortex-m3": "-mcpu=cortex-m3 -mthumb",
        "cortex-m4": "-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16",
        "cortex-m7": "-mcpu=cortex-m7 -mthumb -mfloat-abi=hard -mfpu=fpv5-sp-d16",
    }
    flags = cpu_flags.get(target, cpu_flags["cortex-m4"])

    output_elf = os.path.join(source_dir, "firmware.elf")
    cmd = f"arm-none-eabi-gcc {flags} {optimization} -o {output_elf} {' '.join(c_files)}"

    return _run_command(cmd.split())


def firmware_size(elf_path: str) -> Dict:
    """Get firmware binary size breakdown (text/data/bss)."""
    return _run_command(["arm-none-eabi-size", elf_path])


def cppcheck_misra(source_dir: str) -> Dict:
    """Run MISRA-C static analysis on firmware source."""
    return _run_command([
        "cppcheck",
        "--enable=all",
        "--addon=misra",
        "--suppress=missingInclude",
        source_dir,
    ], timeout=120)


# ---------------------------------------------------------------------------
# Unified tool registry for MCP
# ---------------------------------------------------------------------------

HARDWARE_TOOL_REGISTRY = {
    "list_hardware_tools": list_hardware_tools,
    "kicad_create_project": kicad_create_project,
    "kicad_run_erc": kicad_run_erc,
    "kicad_run_drc": kicad_run_drc,
    "kicad_export_gerbers": kicad_export_gerbers,
    "kicad_export_bom": kicad_export_bom,
    "kicad_export_netlist": kicad_export_netlist,
    "openscad_render": openscad_render,
    "openscad_render_png": openscad_render_png,
    "freecad_export_step": freecad_export_step,
    "ngspice_simulate": ngspice_simulate,
    "firmware_compile": firmware_compile,
    "firmware_size": firmware_size,
    "cppcheck_misra": cppcheck_misra,
}
