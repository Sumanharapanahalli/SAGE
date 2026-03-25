"""
Wearable Enclosure - Bottom Shell (PCB Side)
============================================
Material : Medical-grade polycarbonate (PC ISO 10993-1 compliant)
Dimensions: 40.0 x 35.0 x 6.5 mm
Features  : USB-C port + waterproof cover hinge, band lugs (22 mm),
            PCB standoffs (x4), haptic motor pocket, heat-set insert bosses

Run:  python enclosure_bottom.py
Deps: pip install cadquery cadquery-ocp
Out : output/enclosure_bottom.step, output/enclosure_bottom.stl
"""

import os
import cadquery as cq
from cadquery import exporters

# ---------------------------------------------------------------------------
# Master dimensions  (all units: mm)
# ---------------------------------------------------------------------------

OUTER_W   = 40.0
OUTER_D   = 35.0
BOT_H     = 6.5        # bottom shell height
WALL_T    = 1.5
CORNER_R  = 3.5

# Heat-set insert bosses (M1.6, Ruthex RX-M1.6×3.2, nickel-free brass)
INSERT_OD   = 3.5      # boss outer Ø
INSERT_ID   = 2.05     # pre-drill for M1.6 insert (manufacturer spec)
INSERT_H    = 4.0      # boss height from interior floor
BOSS_INSET  = 5.0      # from outer wall to boss centre

# PCB standoffs (4×, self-tap M1.4, 2.5 mm high, moulded integral)
PCB_SO_OD  = 2.8
PCB_SO_ID  = 1.2       # M1.4 self-tap pilot
PCB_SO_H   = 2.5
PCB_SO_PTS = [(14.0, 12.0), (-14.0, 12.0), (14.0, -12.0), (-14.0, -12.0)]

# Haptic motor recess (Ø 10 mm ERM coin motor)
MOTOR_OD   = 10.5      # pocket Ø (0.25 mm clearance)
MOTOR_D    = 2.0       # pocket depth
MOTOR_X    = 0.0
MOTOR_Y    = -OUTER_D / 2.0 + 8.5

# USB-C port cutout (+X wall, centred Y)
USBC_W     = 10.0      # cutout width (GCT USB4085: 9.0 mm body + 0.5/side)
USBC_H_CUT = 3.7       # cutout height (connector: 3.26 mm + 0.22/side)
USBC_Z_CEN = 3.5       # from bottom of shell to connector centre

# Waterproof cover hinge pin pockets (above USB-C, +X face)
HINGE_DIA  = 1.5
HINGE_Z    = USBC_Z_CEN + USBC_H_CUT / 2.0 + 1.5
HINGE_Y    = [-3.5, 3.5]

# Band lug spring-bar sockets (22 mm ISO 3826, ±Y walls)
LUG_Y_POS  = [LUG_W / 2.0 for LUG_W in [-11.0, 11.0]]  # ±11 mm = 22 mm centres
LUG_PIN_D  = 1.6       # spring-bar pin Ø 1.5 mm + 0.05 clearance
LUG_DEPTH  = 3.2       # socket depth into side wall
LUG_Z      = BOT_H / 2.0  # centred on shell height


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_bottom() -> cq.Workplane:

    # ── Outer shell ──────────────────────────────────────────────────────────
    outer = (
        cq.Workplane("XY")
        .box(OUTER_W, OUTER_D, BOT_H, centered=(True, True, False))
        .edges("|Z")
        .fillet(CORNER_R)
        .edges("<Z")
        .fillet(1.0)
    )

    # ── Interior cavity ──────────────────────────────────────────────────────
    inner_w = OUTER_W - 2.0 * WALL_T
    inner_d = OUTER_D - 2.0 * WALL_T
    inner_h = BOT_H - WALL_T
    inner_r = max(0.2, CORNER_R - WALL_T)

    inner = (
        cq.Workplane("XY")
        .transformed(offset=cq.Vector(0, 0, WALL_T))
        .box(inner_w, inner_d, inner_h + 0.1, centered=(True, True, False))
        .edges("|Z")
        .fillet(inner_r)
    )
    bot = outer.cut(inner)

    # ── Heat-set insert bosses (4× corners) ──────────────────────────────────
    bx = OUTER_W / 2.0 - BOSS_INSET
    by = OUTER_D / 2.0 - BOSS_INSET
    boss_pts = [(bx, by), (-bx, by), (bx, -by), (-bx, -by)]

    for (px, py) in boss_pts:
        boss = (
            cq.Workplane("XY")
            .transformed(offset=cq.Vector(px, py, WALL_T))
            .cylinder(INSERT_H, INSERT_OD / 2.0, centered=(True, True, False))
        )
        bot = bot.union(boss)

    # Drill insert holes (from top face down through boss)
    for (px, py) in boss_pts:
        bot = (
            bot
            .faces(">Z")
            .workplane()
            .center(px, py)
            .circle(INSERT_ID / 2.0)
            .cutBlind(-(INSERT_H + WALL_T + 0.5))
        )

    # ── PCB standoffs (4×) ───────────────────────────────────────────────────
    for (px, py) in PCB_SO_PTS:
        so = (
            cq.Workplane("XY")
            .transformed(offset=cq.Vector(px, py, WALL_T))
            .cylinder(PCB_SO_H, PCB_SO_OD / 2.0, centered=(True, True, False))
        )
        bot = bot.union(so)
        bot = (
            bot
            .faces(">Z")
            .workplane()
            .center(px, py)
            .circle(PCB_SO_ID / 2.0)
            .cutBlind(-(PCB_SO_H + WALL_T))
        )

    # ── Haptic motor pocket (coin motor recess) ───────────────────────────────
    bot = (
        bot
        .faces(">Z")
        .workplane()
        .center(MOTOR_X, MOTOR_Y)
        .circle(MOTOR_OD / 2.0)
        .cutBlind(MOTOR_D)
    )
    # Motor wire strain-relief slot
    bot = (
        bot
        .faces(">Z")
        .workplane()
        .center(MOTOR_X, MOTOR_Y + MOTOR_OD / 2.0 + 1.5)
        .rect(1.5, 4.0)
        .cutThruAll()
    )

    # ── USB-C port opening (+X side wall) ────────────────────────────────────
    usbc_cut = (
        cq.Workplane("YZ")
        .transformed(offset=cq.Vector(OUTER_W / 2.0 - WALL_T - 0.1, 0, USBC_Z_CEN))
        .rect(USBC_W, USBC_H_CUT)
        .extrude(WALL_T + 0.2)
    )
    bot = bot.cut(usbc_cut)

    # ── Hinge pin pockets (waterproof cover, above USB-C) ────────────────────
    for y_off in HINGE_Y:
        pocket = (
            cq.Workplane("YZ")
            .transformed(offset=cq.Vector(OUTER_W / 2.0 - WALL_T, y_off, HINGE_Z))
            .circle(HINGE_DIA / 2.0)
            .extrude(WALL_T + 0.5)
        )
        bot = bot.cut(pocket)

    # ── Band lug spring-bar sockets (+Y and -Y walls) ─────────────────────────
    for sign, face_sel in [(1, ">Y"), (-1, "<Y")]:
        for lug_y in LUG_Y_POS:
            x_pos = lug_y  # lug_y is already ±11 mm in X
            socket = (
                cq.Workplane("XZ")
                .transformed(offset=cq.Vector(
                    x_pos,
                    sign * (OUTER_D / 2.0 - WALL_T),
                    LUG_Z))
                .circle(LUG_PIN_D / 2.0)
                .extrude(LUG_DEPTH)
            )
            bot = bot.cut(socket)

        # Through-channel connecting the two lug sockets
        channel = (
            cq.Workplane("XZ")
            .transformed(offset=cq.Vector(
                0,
                sign * (OUTER_D / 2.0 - WALL_T),
                LUG_Z))
            .rect(22.0, LUG_PIN_D)
            .extrude(LUG_DEPTH)
        )
        bot = bot.cut(channel)

    # ── Alignment dowels (2× Ø 1.5 mm integral pins on parting face) ─────────
    dowel_positions = [(12.0, 0.0), (-12.0, 0.0)]
    for (px, py) in dowel_positions:
        pin = (
            cq.Workplane("XY")
            .transformed(offset=cq.Vector(px, py, BOT_H))
            .cylinder(1.5, 0.75, centered=(True, True, False))
        )
        bot = bot.union(pin)

    return bot


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building enclosure_bottom …")
    result = build_bottom()
    os.makedirs("output", exist_ok=True)
    exporters.export(result, "output/enclosure_bottom.step")
    exporters.export(result, "output/enclosure_bottom.stl",
                     opt={"linearDeflection": 0.05, "angularDeflection": 0.1})
    print("  ✓  output/enclosure_bottom.step")
    print("  ✓  output/enclosure_bottom.stl")
    bb = result.val().BoundingBox()
    print(f"  BBox: {bb.xmax-bb.xmin:.2f} x {bb.ymax-bb.ymin:.2f} x {bb.zmax-bb.zmin:.2f} mm")
    print(f"  Vol : {result.val().Volume():.0f} mm³")
