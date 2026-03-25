"""
Wearable Enclosure - Top Shell (Display Side)
=============================================
Material : Medical-grade polycarbonate (PC ISO 10993-1 compliant)
Dimensions: 40.0 x 35.0 x 5.5 mm
Features  : LED window, SOS button port, O-ring groove, screw bosses

Run:  python enclosure_top.py
Deps: pip install cadquery cadquery-ocp
Out : output/enclosure_top.step, output/enclosure_top.stl
"""

import os
import cadquery as cq
from cadquery import exporters

# ---------------------------------------------------------------------------
# Master dimensions  (all units: mm)
# ---------------------------------------------------------------------------

# Outer envelope
OUTER_W    = 40.0      # X – width
OUTER_D    = 35.0      # Y – depth
TOP_H      = 5.5       # Z – top shell height
WALL_T     = 1.5       # nominal wall / floor thickness
CORNER_R   = 3.5       # outer corner radius (XY plane)
TOP_FILLET = 1.0       # top-face edge fillet

# O-ring groove – Parker 2-031 (nominal CS=1.78 mm)
# Target 15.7 % radial compression → groove depth = 1.78 * 0.843 = 1.50 mm
# Groove width = 1.24 * CS = 2.207 mm
OG_CL_INSET = 2.8      # groove centreline inset from outer wall face
OG_W        = 2.20     # groove width
OG_D        = 1.50     # groove depth (per tolerance analysis A2 recommendation)

# LED / display window (accepts polycarbonate lens insert)
LED_W       = 28.0     # window outer width  (lens seats here)
LED_D       = 18.0     # window outer depth
LED_LIP_W   = 0.8      # retaining lip width on each side
LED_RECESS  = 0.5      # lens seat depth

# SOS button port  – left-side wall (-X face), centred vertically
SOS_DIA     = 8.2      # through-hole Ø (button body 8.0 + 0.1/side clearance)
SOS_Y_POS   = 0.0      # centred on device Y axis
SOS_Z_POS   = 2.8      # from bottom of top shell to button centre

# Screw through-holes (M1.6 clearance Ø 1.8 mm, 4 off)
SCREW_CL_D  = 1.8      # clearance drill
BOSS_INSET  = 5.0      # boss centre from outer wall

# Haptic motor cable pass-through (Ø 2.5 mm, bottom face rear corner)
HAPTIC_PORT_D = 2.5
HAPTIC_X      =  OUTER_W / 2.0 - 6.0
HAPTIC_Y      = -OUTER_D / 2.0 + 5.0


# ---------------------------------------------------------------------------
# Helper: rectangular O-ring groove cutter (annular prism)
# ---------------------------------------------------------------------------

def _oring_groove_cutter(cl_w: float, cl_d: float,
                          g_w: float, g_d: float) -> cq.Workplane:
    """Return a solid shaped like the rectangular groove channel."""
    half_w = g_w / 2.0
    outer_box = (
        cq.Workplane("XY")
        .box(cl_w + g_w, cl_d + g_w, g_d, centered=(True, True, False))
    )
    inner_box = (
        cq.Workplane("XY")
        .box(cl_w - g_w, cl_d - g_w, g_d + 0.1, centered=(True, True, False))
    )
    return outer_box.cut(inner_box)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_top() -> cq.Workplane:
    # ── Outer shell solid ──────────────────────────────────────────────────
    outer = (
        cq.Workplane("XY")
        .box(OUTER_W, OUTER_D, TOP_H, centered=(True, True, False))
        .edges("|Z")
        .fillet(CORNER_R)
        .edges(">Z")
        .fillet(TOP_FILLET)
    )

    # ── Interior cavity ─────────────────────────────────────────────────────
    inner_w = OUTER_W - 2.0 * WALL_T
    inner_d = OUTER_D - 2.0 * WALL_T
    inner_h = TOP_H - WALL_T        # retain top face thickness = WALL_T
    inner_r = max(0.2, CORNER_R - WALL_T)

    inner = (
        cq.Workplane("XY")
        .box(inner_w, inner_d, inner_h, centered=(True, True, False))
        .edges("|Z")
        .fillet(inner_r)
    )
    top = outer.cut(inner)

    # ── O-ring groove on bottom mating face (Z = 0 plane) ───────────────────
    og_cl_w = OUTER_W - 2.0 * OG_CL_INSET
    og_cl_d = OUTER_D - 2.0 * OG_CL_INSET
    groove = _oring_groove_cutter(og_cl_w, og_cl_d, OG_W / 2.0, OG_D)
    top = top.cut(groove)

    # ── LED window – outer recess (lens seat) ────────────────────────────────
    top = (
        top
        .faces(">Z")
        .workplane()
        .rect(LED_W, LED_D)
        .cutBlind(LED_RECESS)
    )
    # Inner through-hole (light path)
    inner_led_w = LED_W - 2.0 * LED_LIP_W
    inner_led_d = LED_D - 2.0 * LED_LIP_W
    top = (
        top
        .faces(">Z")
        .workplane()
        .rect(inner_led_w, inner_led_d)
        .cutThruAll()
    )

    # ── SOS button port – left side wall (-X face) ───────────────────────────
    top = (
        top
        .faces("<X")
        .workplane(centerOption="CenterOfBoundBox")
        .center(SOS_Y_POS, SOS_Z_POS - TOP_H / 2.0)
        .circle(SOS_DIA / 2.0)
        .cutThruAll()
    )

    # ── Screw clearance holes (4× M1.6) ─────────────────────────────────────
    bx = OUTER_W / 2.0 - BOSS_INSET
    by = OUTER_D / 2.0 - BOSS_INSET
    screw_pts = [(bx, by), (-bx, by), (bx, -by), (-bx, -by)]
    top = (
        top
        .faces("<Z")
        .workplane()
        .pushPoints(screw_pts)
        .circle(SCREW_CL_D / 2.0)
        .cutThruAll()
    )

    # ── Haptic cable port (bottom face, rear corner) ─────────────────────────
    top = (
        top
        .faces("<Z")
        .workplane()
        .center(HAPTIC_X, HAPTIC_Y)
        .circle(HAPTIC_PORT_D / 2.0)
        .cutThruAll()
    )

    return top


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building enclosure_top …")
    result = build_top()
    os.makedirs("output", exist_ok=True)
    exporters.export(result, "output/enclosure_top.step")
    exporters.export(result, "output/enclosure_top.stl",
                     opt={"linearDeflection": 0.05, "angularDeflection": 0.1})
    print("  ✓  output/enclosure_top.step")
    print("  ✓  output/enclosure_top.stl")
    bb = result.val().BoundingBox()
    print(f"  BBox: {bb.xmax-bb.xmin:.2f} x {bb.ymax-bb.ymin:.2f} x {bb.zmax-bb.zmin:.2f} mm")
    print(f"  Vol : {result.val().Volume():.0f} mm³")
