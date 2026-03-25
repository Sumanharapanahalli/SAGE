"""
Wearable Band Assembly
=======================
Material  : Medical-grade silicone (Dow Corning Q7-4850 LSR)
            ISO 10993-5 (cytotoxicity) and ISO 10993-10 (sensitisation) compliant
            Supplier Certificate of Conformance required at incoming inspection
Lug width : 22 mm (ISO 3826 spring-bar standard)
Band dims : 22 mm wide × 2.2 mm thick, adjustable 130–210 mm circumference
Closure   : 316L stainless tang buckle, nickel-free

Run:  python band_assembly.py
Deps: pip install cadquery cadquery-ocp
Out : output/band_assembly.step, output/band_assembly.stl
"""

import os
import cadquery as cq
from cadquery import exporters

# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------

BAND_W        = 22.0    # lug-end band width (mm)
BAND_T        = 2.2     # band thickness
BAND_EDGE_R   = 1.0     # edge comfort radius

LUG_END_L     = 12.0    # lug-end segment length
LUG_HOLE_D    = 1.6     # spring-bar hole Ø (bar Ø 1.5 + 0.05 clearance each side)
LUG_HOLE_X    = 5.5     # hole centre from lug end

BODY_L        = 130.0   # adjustable body length

BUCKLE_END_L  = 25.0    # buckle end segment length
BUCKLE_END_W  = 18.0    # narrowed width at buckle end

HOLE_DIA      = 2.5     # adjustment hole Ø
HOLE_PITCH    = 5.0     # hole pitch
HOLE_COUNT    = 5       # number of holes
FIRST_HOLE_X  = 18.0    # first hole centre from body end

BUCKLE_SLOT_W = 5.5     # buckle-bar slot width
BUCKLE_SLOT_L = 14.0    # slot length
BUCKLE_SLOT_X = 7.0     # slot centre from buckle end

# Comfort relief grooves (top face, transverse – aids skin breathability)
RELIEF_W      = 3.0
RELIEF_D      = 0.5
RELIEF_PITCH  = 9.0

# Buckle (316L stainless, simplified frame + tang)
BUCKLE_FRAME_W = 24.0
BUCKLE_FRAME_D = 5.0
BUCKLE_FRAME_H = 3.5
BUCKLE_WALL_T  = 1.5
TANG_DIA       = 1.3


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def build_band_body() -> cq.Workplane:
    """Main adjustable band — lug end + body as single moulded piece."""

    total_l = LUG_END_L + BODY_L

    # Base band
    band = (
        cq.Workplane("XY")
        .box(total_l, BAND_W, BAND_T, centered=(False, True, False))
        .edges("|Z")
        .fillet(BAND_EDGE_R)
        .edges(">Z or <Z")
        .fillet(0.4)
    )

    # Spring-bar through-holes (both lug ends, Y direction)
    band = (
        band
        .faces(">Y")
        .workplane()
        .center(-total_l / 2.0 + LUG_HOLE_X, 0.0)
        .circle(LUG_HOLE_D / 2.0)
        .cutThruAll()
    )

    # Adjustment holes in body segment
    hole_x_positions = [
        (LUG_END_L + FIRST_HOLE_X + i * HOLE_PITCH - total_l / 2.0, 0.0)
        for i in range(HOLE_COUNT)
    ]
    band = (
        band
        .faces(">Z")
        .workplane()
        .pushPoints(hole_x_positions)
        .circle(HOLE_DIA / 2.0)
        .cutThruAll()
    )

    # Buckle slot (far end of body)
    slot_cx = total_l / 2.0 - BUCKLE_SLOT_X
    band = (
        band
        .faces(">Z")
        .workplane()
        .center(slot_cx, 0.0)
        .rect(BUCKLE_SLOT_L, BUCKLE_SLOT_W)
        .cutThruAll()
    )

    # Comfort relief grooves (top face)
    n_grooves = int(BODY_L / RELIEF_PITCH) - 2
    for i in range(n_grooves):
        gx = (-total_l / 2.0 + LUG_END_L + RELIEF_PITCH * (i + 1))
        band = (
            band
            .faces(">Z")
            .workplane()
            .center(gx, 0.0)
            .rect(RELIEF_W, BAND_W - 5.0)
            .cutBlind(RELIEF_D)
        )

    return band


def build_buckle_end() -> cq.Workplane:
    """Narrower strap tail that threads through buckle."""
    tail = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, 0))
        .box(BUCKLE_END_L, BUCKLE_END_W, BAND_T, centered=(False, True, False))
        .edges("|Z")
        .fillet(BAND_EDGE_R)
    )
    # Tip chamfer (pointed end for easier threading)
    # modelled as simple taper via extrude — approximated as box for STEP simplicity
    return tail


def build_buckle() -> cq.Workplane:
    """Simplified 316L stainless tang buckle frame."""
    # Frame
    outer = (
        cq.Workplane("XY")
        .box(BUCKLE_FRAME_W, BUCKLE_FRAME_D, BUCKLE_FRAME_H,
             centered=(True, True, False))
    )
    inner = (
        cq.Workplane("XY")
        .box(BUCKLE_FRAME_W - 2 * BUCKLE_WALL_T,
             BUCKLE_FRAME_D + 0.1,
             BUCKLE_FRAME_H - BUCKLE_WALL_T,
             centered=(True, True, False))
    )
    frame = outer.cut(inner)

    # Tang pin (Ø 1.3 mm, spans across frame interior width)
    tang = (
        cq.Workplane("YZ")
        .circle(TANG_DIA / 2.0)
        .extrude(BUCKLE_FRAME_W)
        .translate((-BUCKLE_FRAME_W / 2.0, 0, BUCKLE_FRAME_H / 2.0))
    )
    frame = frame.union(tang)

    return frame


def build_spring_bar() -> cq.Workplane:
    """316L spring bar, Ø 1.5 mm × 26 mm (spans 22 mm lug width + 2 mm each side)."""
    return (
        cq.Workplane("YZ")
        .circle(0.75)
        .extrude(26.0)
        .translate((0, -13.0, 0))
    )


def build_assembly() -> cq.Workplane:
    """Full band assembly at nominal (one spring bar shown, buckle positioned)."""
    total_l = LUG_END_L + BODY_L

    band   = build_band_body()
    buckle = build_buckle().translate((total_l / 2.0 - 5.0, 0, BAND_T))
    bar    = build_spring_bar().translate((
        -total_l / 2.0 + LUG_HOLE_X, 0, BAND_T / 2.0
    ))

    return band.union(buckle).union(bar)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building band_assembly …")
    result = build_assembly()
    os.makedirs("output", exist_ok=True)
    exporters.export(result, "output/band_assembly.step")
    exporters.export(result, "output/band_assembly.stl",
                     opt={"linearDeflection": 0.05, "angularDeflection": 0.1})
    print("  ✓  output/band_assembly.step")
    print("  ✓  output/band_assembly.stl")
    bb = result.val().BoundingBox()
    print(f"  BBox: {bb.xmax-bb.xmin:.2f} x {bb.ymax-bb.ymin:.2f} x {bb.zmax-bb.zmin:.2f} mm")
    print(f"  Vol : {result.val().Volume():.0f} mm³")
