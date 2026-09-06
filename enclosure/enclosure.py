"""DriftAnalyser v2 enclosure: 3D-printed base + snap-on lid, generated with CadQuery.

Board frame (KiCad): x right, y down, origin at the board's top-left corner.
CAD frame here: X = board x, Y = -board y (so +Y is the strip-connector edge),
Z up, board bottom face at Z = 0.

Run:  enclosure/.venv/bin/python enclosure/enclosure.py
Out:  enclosure/out/{base,lid}.stl, enclosure/out/enclosure.step, enclosure/out/*.svg
"""
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "PCB", "v2"))
from gen import placement  # noqa: E402

OUT = os.path.join(HERE, "out")

# ---------------------------------------------------------------- parameters
BW, BH = placement.BOARD_W, placement.BOARD_H   # 110 x 75
PCB_T = 1.6

WALL = 2.4            # side wall
FLOOR = 2.0
CLEAR = 1.0           # board edge -> inner wall (right, top, bottom)
LEFT_EXT = 8.0        # extra cavity on the left for the ESP32 antenna overhang
STANDOFF_H = 5.0      # board bottom above the floor
COMP_H = 12.0         # tallest part above board top (JST VH 11.5)
LID_T = 2.0
LIP_H = 3.0           # lid lip going down inside the walls
LIP_T = 1.2
FIT = 0.25            # lip -> wall gap per side
OUTER_R = 3.0         # vertical corner radius outside

STANDOFF_D = 6.5
INSERT_HOLE = 4.0     # M3 heat-set insert; use 2.5 for self-tapping into plastic
INSERT_DEPTH = 5.0

EAR_W, EAR_L, EAR_T, EAR_HOLE = 14.0, 12.0, 3.0, 4.5   # mounting ears, screw 4 mm

# snap tabs: on the lid, bump outward into recesses in the wall inner face
TAB_W, TAB_H, TAB_T, BUMP = 10.0, 6.0, 1.2, 0.8

# ------------------------------------------------------------- derived sizes
IN_X0 = -LEFT_EXT                    # cavity x range in board coords
IN_X1 = BW + CLEAR
IN_Y0 = -CLEAR                       # board y range (KiCad y) of the cavity
IN_Y1 = BH + CLEAR
CAV_W = IN_X1 - IN_X0
CAV_D = IN_Y1 - IN_Y0
CAV_H = STANDOFF_H + PCB_T + COMP_H  # floor top -> lid underside
OUT_W = CAV_W + 2 * WALL
OUT_D = CAV_D + 2 * WALL
BASE_H = FLOOR + CAV_H

Z_BOARD_TOP = FLOOR + STANDOFF_H + PCB_T     # in base coords (floor bottom = 0)


def bx(x):
    """board x -> CAD X (cavity centred on 0)."""
    return x - (IN_X0 + IN_X1) / 2


def by(y):
    """board y (down) -> CAD Y (up)."""
    return -(y - (IN_Y0 + IN_Y1) / 2)


# ---------------------------------------------------------------- the base
def make_base():
    base = (cq.Workplane("XY").box(OUT_W, OUT_D, BASE_H, centered=(True, True, False))
            .edges("|Z").fillet(OUTER_R))
    cavity = (cq.Workplane("XY").workplane(offset=FLOOR)
              .box(CAV_W, CAV_D, CAV_H + 1, centered=(True, True, False))
              .edges("|Z").fillet(max(OUTER_R - WALL, 0.5)))
    base = base.cut(cavity)

    # standoffs with insert holes
    for (hx, hy) in placement.HOLES:
        post = (cq.Workplane("XY").workplane(offset=FLOOR).center(bx(hx), by(hy))
                .circle(STANDOFF_D / 2).extrude(STANDOFF_H))
        hole = (cq.Workplane("XY").workplane(offset=FLOOR + STANDOFF_H - INSERT_DEPTH)
                .center(bx(hx), by(hy)).circle(INSERT_HOLE / 2).extrude(INSERT_DEPTH + 0.01))
        base = base.union(post).cut(hole)

    # ---- windows in the bottom wall (board y = 75 side, CAD -Y)
    ywall_out = -OUT_D / 2
    def bottom_window(x0, x1, z0, z1):
        w = x1 - x0; h = z1 - z0
        return (cq.Workplane("XZ", origin=(0, ywall_out + WALL / 2, 0))
                .center(bx((x0 + x1) / 2), z0 + h / 2).rect(w, h).extrude(WALL + 2, both=True))

    # XT60PW-M: courtyard x 9.1..25.7, plug enters horizontally, body ~8.5 mm tall
    base = base.cut(bottom_window(8.0, 27.0, Z_BOARD_TOP - 0.6, Z_BOARD_TOP + 10.0))
    # USB-C: receptacle x 51.6..62.4, 3.3 mm tall; window sized for a plug overmold
    base = base.cut(bottom_window(51.0, 63.0, Z_BOARD_TOP - 0.8, Z_BOARD_TOP + 6.0))

    # ---- microSD slot in the right wall (board x = 110 side, CAD +X); J5 y 37..53
    xwall_out = OUT_W / 2
    sd = (cq.Workplane("YZ", origin=(xwall_out - WALL / 2, 0, 0))
          .center(by(45.0), Z_BOARD_TOP + 1.9).rect(16.0, 4.6).extrude(WALL + 2, both=True))
    base = base.cut(sd)
    # finger recess so the card can be gripped at the board edge
    finger = (cq.Workplane("YZ", origin=(xwall_out - WALL / 2, 0, 0))
              .center(by(45.0), Z_BOARD_TOP + 6.0).rect(12.0, 9.0).extrude(WALL + 2, both=True))
    base = base.cut(finger)

    # ---- vent slots in the right wall next to the BTS7002 (board y 18..34)
    for i in range(4):
        y = 20.0 + i * 4.0
        slot = (cq.Workplane("YZ", origin=(xwall_out - WALL / 2, 0, 0))
                .center(by(y), Z_BOARD_TOP + 7.0).rect(1.6, 10.0).extrude(WALL + 2, both=True))
        base = base.cut(slot)

    # ---- snap recesses in the wall inner faces (mate with lid tabs)
    for (cx, cy, along_x) in _tab_positions():
        depth = BUMP + 0.15
        if along_x:   # tab on a long wall (Y = +/-), recess cut into the wall inner face
            sign = 1 if cy > 0 else -1
            rec = (cq.Workplane("XY")
                   .center(bx(cx), sign * (CAV_D / 2 + depth / 2 - 0.01))
                   .rect(TAB_W + 0.6, depth)
                   .extrude(TAB_H * 0.55)
                   .translate((0, 0, BASE_H - LIP_H - TAB_H)))
        else:
            sign = 1 if cx > 0 else -1
            rec = (cq.Workplane("XY")
                   .center(sign * (CAV_W / 2 + depth / 2 - 0.01), by(cy))
                   .rect(depth, TAB_W + 0.6)
                   .extrude(TAB_H * 0.55)
                   .translate((0, 0, BASE_H - LIP_H - TAB_H)))
        base = base.cut(rec)

    # ---- mounting ears on the left and right ends
    for sign in (-1, 1):
        ear = (cq.Workplane("XY")
               .center(sign * (OUT_W / 2 + EAR_L / 2 - 0.01), 0)
               .rect(EAR_L, EAR_W).extrude(EAR_T)
               .edges("|Z").fillet(2.0))
        hole = (cq.Workplane("XY").center(sign * (OUT_W / 2 + EAR_L / 2 + 1.0), 0)
                .circle(EAR_HOLE / 2).extrude(EAR_T + 1))
        base = base.union(ear).cut(hole)
    return base


def _tab_positions():
    """(board x, board y, along_x) of the snap tabs / recesses.

    Two on the top wall between strip connectors, two on the bottom wall away from
    the connector windows, one on each short wall. Tabs sit on the lid lip and bump
    outward into the recesses.
    """
    return [
        (38.0, IN_Y0, True), (83.5, IN_Y0, True),      # top wall, between J12/J13 and J15/J16
        (40.0, IN_Y1, True), (78.0, IN_Y1, True),      # bottom wall, clear of XT60/USB/OBD
        (IN_X0, 66.0, False),                          # left wall, below the antenna zone
        (IN_X1, 62.0, False),                          # right wall, below the microSD
    ]


# ---------------------------------------------------------------- the lid
def make_lid():
    lid = (cq.Workplane("XY").box(OUT_W, OUT_D, LID_T, centered=(True, True, False))
           .edges("|Z").fillet(OUTER_R))
    lip_outer = (cq.Workplane("XY").rect(CAV_W - 2 * FIT, CAV_D - 2 * FIT).extrude(-LIP_H)
                 .edges("|Z").fillet(1.0))
    lip_inner = (cq.Workplane("XY").rect(CAV_W - 2 * FIT - 2 * LIP_T, CAV_D - 2 * FIT - 2 * LIP_T)
                 .extrude(-LIP_H - 1).edges("|Z").fillet(0.5))
    lid = lid.union(lip_outer.cut(lip_inner))

    # ---- wire notches over the six strip connectors (open to the +Y edge)
    for i in range(1, 7):
        x = placement._strip_x(i) + 3.96          # connector centre (pins at x, x+3.96, x+7.92)
        notch = (cq.Workplane("XY").center(bx(x), OUT_D / 2 - 6.0)
                 .rect(16.0, 12.0 + 2).extrude(-LIP_H - 1).translate((0, 0, LID_T + 0.5)))
        lid = lid.cut(notch)
    # ---- wire notch over the OBD connector (JST XH, vertical entry) at the -Y edge
    notch = (cq.Workplane("XY").center(bx(92.0 + 3.75), -OUT_D / 2 + 5.0)
             .rect(15.0, 10.0 + 2).extrude(-LIP_H - 1).translate((0, 0, LID_T + 0.5)))
    lid = lid.cut(notch)

    # ---- pin holes for BOOT / EN, light holes for the two LEDs
    for ref, d in (("SW1", 3.5), ("SW2", 3.5), ("D5", 2.0), ("D6", 2.0)):
        x, y, *_ = placement.PLACE[ref]
        lid = lid.cut(cq.Workplane("XY").center(bx(x), by(y)).circle(d / 2).extrude(LID_T + 1))

    # ---- vent slots over the strip switch (BTS7002 at board 94,26)
    for i in range(6):
        x = 86.0 + i * 3.2
        lid = lid.cut(cq.Workplane("XY").center(bx(x), by(26.0)).rect(1.6, 14.0).extrude(LID_T + 1))

    # ---- snap tabs hanging from the lip
    for (cx, cy, along_x) in _tab_positions():
        if along_x:
            sign = 1 if cy > 0 else -1
            yc = sign * (CAV_D / 2 - FIT - TAB_T / 2)
            tab = cq.Workplane("XY").center(bx(cx), yc).rect(TAB_W, TAB_T).extrude(-(LIP_H + TAB_H))
            bump = (cq.Workplane("XY").center(bx(cx), sign * (CAV_D / 2 - FIT + BUMP / 2 - 0.05))
                    .rect(TAB_W, BUMP + 0.1).extrude(-TAB_H * 0.5)
                    .translate((0, 0, -(LIP_H + TAB_H * 0.5))))
        else:
            sign = 1 if cx > 0 else -1
            xc = sign * (CAV_W / 2 - FIT - TAB_T / 2)
            tab = cq.Workplane("XY").center(xc, by(cy)).rect(TAB_T, TAB_W).extrude(-(LIP_H + TAB_H))
            bump = (cq.Workplane("XY").center(sign * (CAV_W / 2 - FIT + BUMP / 2 - 0.05), by(cy))
                    .rect(BUMP + 0.1, TAB_W).extrude(-TAB_H * 0.5)
                    .translate((0, 0, -(LIP_H + TAB_H * 0.5))))
        lid = lid.union(tab).union(bump)

    # ---- labels
    lid = lid.faces(">Z").workplane().center(bx(55.0), by(45.0)).text(
        "DriftAnalyser v2", 5.0, -0.6, combine="cut", halign="center", valign="center")
    for i in range(1, 7):
        x = placement._strip_x(i) + 3.96
        lid = lid.faces(">Z").workplane().center(bx(x), OUT_D / 2 - 15.0).text(
            f"LED{i}", 3.2, -0.5, combine="cut", halign="center", valign="center")
    lid = lid.faces(">Z").workplane().center(bx(95.75), -OUT_D / 2 + 13.0).text(
        "OBD", 3.2, -0.5, combine="cut", halign="center", valign="center")
    lid = lid.faces(">Z").workplane().center(bx(17.5), -OUT_D / 2 + 13.0).text(
        "12V", 3.2, -0.5, combine="cut", halign="center", valign="center")
    return lid


def main():
    os.makedirs(OUT, exist_ok=True)
    base = make_base()
    lid = make_lid()
    cq.exporters.export(base, os.path.join(OUT, "base.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(lid, os.path.join(OUT, "lid.stl"), tolerance=0.02, angularTolerance=0.1)

    # assembly STEP: lid seated on the base
    lid_on = lid.translate((0, 0, BASE_H))
    asm = cq.Assembly()
    asm.add(base, name="base", color=cq.Color(0.25, 0.25, 0.28))
    asm.add(lid_on, name="lid", color=cq.Color(0.85, 0.5, 0.1))
    asm.save(os.path.join(OUT, "enclosure.step"))
    # exploded preview for a quick look
    lid_up = lid.translate((0, 0, BASE_H + 25))
    cq.exporters.export(base.union(lid_up), os.path.join(OUT, "preview-iso.svg"),
                        opt={"projectionDir": (1, -1, 0.8), "width": 1400, "height": 1000,
                             "showHidden": False, "marginLeft": 20, "marginTop": 20})
    cq.exporters.export(lid.rotate((0, 0, 0), (1, 0, 0), 180), os.path.join(OUT, "preview-lid-inside.svg"),
                        opt={"projectionDir": (0.3, -0.5, 1), "width": 1400, "height": 1000,
                             "showHidden": False})
    cq.exporters.export(base, os.path.join(OUT, "preview-base-top.svg"),
                        opt={"projectionDir": (0.2, -0.3, 1), "width": 1400, "height": 1000,
                             "showHidden": False})
    print(f"outer {OUT_W:.1f} x {OUT_D:.1f} x {BASE_H + LID_T:.1f} mm, cavity {CAV_W:.1f} x {CAV_D:.1f} x {CAV_H:.1f}")
    print("written:", sorted(os.listdir(OUT)))


if __name__ == "__main__" and "--parts" not in sys.argv:
    main()


# ------------------------------------------------ extra: parts for renders
def make_vh_housing():
    """JST B3P-VH header body (no 3D model in KiCad): 14.8 x 8.6 x 11.5 mm box with
    pin-1 at the local origin, pins along +X at 3.96 pitch, wall toward -Y."""
    body = (cq.Workplane("XY").center(3.96, 0).rect(14.8, 8.6).extrude(11.5)
            .edges("|Z").fillet(0.6))
    for i in range(3):
        body = body.cut(cq.Workplane("XY").center(3.96 * i, 0).rect(2.4, 3.2).extrude(11.5).translate((0, 0, 2.0)))
    return body


def make_missing_connectors():
    """Bodies for parts KiCad has no 3D model for, in KiCad model space of a footprint
    at the board origin: X = board x, Y = -board y, Z up from the board top."""
    def box(x0, x1, y0, y1, h, z0=0.0):
        return (cq.Workplane("XY").center((x0 + x1) / 2, -(y0 + y1) / 2)
                .rect(x1 - x0, y1 - y0).extrude(h).translate((0, 0, z0)))
    j1, _ = placement.PLACE["J1"][:2], None
    xt60 = box(j1[0] - 8.3, j1[0] + 8.3, j1[1] - 2.6, j1[1] + 15.0, 8.2)      # XT60PW-M, plug toward +y edge
    j2 = placement.PLACE["J2"]
    usb = box(j2[0] - 4.5, j2[0] + 4.5, j2[1] - 4.5, j2[1] + 4.2, 3.2)          # USB-C HRO, opening toward +y edge
    j5 = placement.PLACE["J5"]
    sd = box(j5[0] - 8.5, j5[0] + 8.5, j5[1] - 7.5, j5[1] + 7.5, 1.9)           # microSD DM3BT
    return xt60.union(usb).union(sd)


def export_render_parts():
    os.makedirs(OUT, exist_ok=True)
    cq.exporters.export(make_missing_connectors(), os.path.join(OUT, "connectors.step"))
    cq.exporters.export(make_base(), os.path.join(OUT, "base.step"))
    cq.exporters.export(make_lid(), os.path.join(OUT, "lid.step"))
    cq.exporters.export(make_vh_housing(), os.path.join(OUT, "vh3.step"))
    print("render parts written")


if __name__ == "__main__" and "--parts" in sys.argv:
    export_render_parts()
