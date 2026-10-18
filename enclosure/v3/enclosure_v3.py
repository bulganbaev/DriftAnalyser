"""DriftAnalyser v3 enclosure CONCEPT: milled aluminium base (heat sink) + stepped lid, like pdm30.

Second pass, fitted to the routed 55 x 112 board: shapes and sizes, not a fab model.

Board frame (KiCad): x right, y down, origin at the board's top-left corner, mm.
CAD frame here: X = board x, Y = -board y (so +Y is the J1 end), Z up, base bottom at Z = 0.

Layout: J1 (Superseal 34, right angle) on the board's top short edge drops into a U-slot in the
front end wall, the wall web sits in the header's groove between the flange plates. The seam is
flat at Z_SEAM; the lid is a flat plate over the low rear part plus a hood over J1 (J1 is
27.9 mm tall, the rest of the board ~10.5). The two Wurth 7461059 REDCUBE
terminals (J2 +12 V, J5 battery negative, 13 mm square brass blocks 13.5 high) poke 1 mm into a pocket
in the lid underside; a 12 mm brass riser through an insulating cup/sleeve brings each to the lid top,
ring lug + washer + M6x20 bolt into the block's thread, red / black boot over it. Fingers on the sleeve flange
keep both lugs pointing to the rear so they can't swing into each other. SMA bulkhead in the
right wall next to the u.FL. The four switches and the ideal-diode FETs sink into pedestals on
the base floor through an insulating thermal pad (their exposed pads are VBUS).

Run:  enclosure/.venv/bin/python enclosure/v3/enclosure_v3.py [--no-render] [--clash]
Out:  enclosure/v3/out/{base,lid}.stl, enclosure.step, render-*.png (incl. render-board-mated-*: bare board with all mating parts)
"""
import math
import os
import sys

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "PCB", "v3"))
from gen import placement as P  # noqa: E402

OUT = os.path.join(HERE, "out")
BOARD_STEP = os.path.join(OUT, "board.step")   # optional, kicad-cli export of the v3 board

# ---------------------------------------------------------------- parameters (mm)
BW, BH = P.BOARD_W, P.BOARD_H   # 55 x 112
PCB_T = 1.6

CLR = 0.5             # board edge -> inner wall
WALL = 4.0            # side and rear walls (rim carries the seam O-ring groove)
FLOOR = 4.0           # base floor, the heat sink
STANDOFF = 3.0        # board bottom above the floor
PAD_T = 1.0           # insulating thermal pad (compressed) between pedestal and board bottom
CAV_R = 3.5           # cavity vertical corner radius (board corner R3 + CLR)
OUT_R = 4.0           # outer vertical corner radius

REAR_H = 12.5         # board top -> rear lid underside: C3 8x10.5 is 10.54; REDCUBE block 13.5 pokes 1.0 into a lid pocket
LID_T = 4.0           # rear lid plate
HOOD_T = 3.5          # hood walls and roof over J1
HOOD_CLR = 1.0        # J1 top -> hood roof
HOOD_BACK = 1.5       # J1 body rear -> hood back wall
HOOD_SLOPE = 16.0     # length of the hood's sloped back (pdm30-style step)

# J1 TE 6437288-1, footprint at rot 180 so footprint y -> board y = 6 - y (fpgen.te_superseal_34)
J1_X = P.J1_AT[0]
J1_H = 27.9           # housing above the board (pdm30 notes)
J1_BODY_W, J1_BODY_Y = 38.5, (-1.0, 23.0)       # housing body, flange to rear plate
J1_FL_W = 45.5                                  # flange plates with ears
J1_FL_IN, J1_FL_OUT = (-2.0, -1.0), (-4.0, -3.0)  # inner / outer flange plate (board y)
J1_FL_Z = (0.5, 27.4)                           # plate bottom / top above the board (top assumed)
J1_SH_W, J1_SH_Y = 35.0, (-13.5, -4.0)          # shroud to the mating face
J1_SH_Z = (2.0, 25.0)                           # shroud bottom / top above the board (assumed)
J1_FIT = 0.5          # slot clearance per side

# front end wall = J1 panel: web 1.0 in the header groove (board y -2..-3), the outer flange
# plate sits flush in a recess in the outer face
FRONT_IN, FRONT_OUT = -CLR, J1_FL_OUT[0]        # board y -0.5 .. -4.0 (3.5 thick)
WEB = (-3.0, -2.0)

# seam O-ring: cord 1.5 in a 1.5 x 1.2 groove on the rim centreline
GASKET_W, GASKET_D = 1.5, 1.2

# lid screws M3 into external pilasters on the long walls, outside the O-ring
LID_SCREW_Y = (2.0, 63.0, 110.0)   # middle pair clear of the SMA spot face at y 50.2
PIL_D, PIL_OFF = 10.0, 3.5     # pilaster dia, screw axis outside the outer wall face
TAP_D, CLEAR_D = 2.5, 3.4

# mounting ears on the base bottom, M5
EAR_Y = (32.0, 88.0)
EAR_L, EAR_W, EAR_T, EAR_HOLE = 12.0, 12.0, 6.0, 5.5

# board standoffs M3
STANDOFF_D = 7.0

# heat pedestals (board x0, x1, y0, y1), from the routed board:
# - one per switch under its B.Cu VBUS patch (zones 6 x 5: x 10.1/19.7/29.3/38.9 +6, y 25.9..30.9),
#   inset 0.3 so the pedestal stays inside the patch
# - one under the Q1/Q2 drain tabs (F.Cu pads x 13.64..23.91, y 61.77..66.33) and the VBUS via
#   column at x 18.77 between them; B.Cu there is the GND pour (no VBUS patch on B.Cu)
PED_INSET = 0.3
PEDESTALS = [(x0 + PED_INSET, x0 + 6.0 - PED_INSET, 25.9 + PED_INSET, 30.9 - PED_INSET)
             for x0 in (10.1, 19.7, 29.3, 38.9)] + [(13.65, 23.9, 61.8, 66.3)]

# M6 terminals Würth WP-BUCF 7461059 REDCUBE press-fit (internal M6)
STUDS = {"J2": P.PLACE["J2"][:2],    # (14, 86.5) +12 V, red
         "J5": P.PLACE["J5"][:2]}    # (44.4, 96.3) battery negative / GND, black
STUD_COL = {"J2": (0.85, 0.06, 0.06), "J5": (0.07, 0.07, 0.08)}
CABLE_COL = {"J2": (0.75, 0.08, 0.08), "J5": (0.10, 0.10, 0.11)}
BLOCK, BLOCK_H, THREAD_DEPTH = 13.0, 13.5, 12.5   # Wurth 7461059 (drawing rev 001.003); thread depth read off the section, ~full height
BOLT_ENGAGE = 10.4                     # M6x20 thread engagement into the block (>= 1.5 d)
LUG_T = 1.6
LUG_OD, LUG_TONGUE_W = 14.0, 8.0       # M6 ring lug for 16-25 mm2, tongue points to the rear (+board y)
STUD_BOSS_D, STUD_BOSS_H = 26.0, 2.0   # raised boss on the lid around the stud
SLEEVE_OD, SLEEVE_ID = 16.0, 12.4      # PA66/PEEK insulating sleeve in the lid hole, round the 12 mm riser
SLEEVE_FL_D, SLEEVE_FL_T = 22.0, 1.5
FINGER = (4.3, 5.5, 5.8, 8.6)          # anti-rotation fingers on the flange: |x| range, y range from the stud
POCKET_D = 22.2                        # lid underside pocket round the block (corners reach 18.4)
SPACER_D = 12.0                        # brass spacer stud top -> above the sleeve flange
CAP_D, CAP_H = 24.0, 12.0              # red boot over lug + bolt

# SMA bulkhead (1/4-36) in the right wall at the u.FL's y, nut AF8 inside
UFL_XY = (51.1, 50.2)  # U1 u.FL (fab circle of ESP32-S3-WROOM-1U at (45.1, 57.3))
SMA_Z = 7.5            # above the board top: nut AF8 clears U1 (3.2) and the lid (12.5)
SMA_HOLE = 6.5

# USB-C (J3, HRO TYPE-C-31-M-12): only for the first flash with the lid off, updates go over the air,
# so the case is closed. USB_OPENING = True cuts a rear-wall slot with room for the plug overmold.
USB_OPENING = False
J3_X = P.PLACE["J3"][0]
USB_SLOT = (13.0, 7.5)   # length x height, rounded ends

# ------------------------------------------------------------- derived sizes
Z_PCB_BOT = FLOOR + STANDOFF
T = Z_PCB_BOT + PCB_T            # board top
Z_SEAM = T + REAR_H
Z_LID_TOP = Z_SEAM + LID_T
Z_POCKET = T + 14.8              # lid pocket ceiling: block top T+13.5, insulating cup roof 1.1 thick
HOOD_TOP = T + J1_H + HOOD_CLR + HOOD_T
X0, X1 = -CLR - WALL, BW + CLR + WALL                 # outer X
Y0, Y1 = FRONT_OUT, BH + CLR + WALL                   # outer board-y (front, rear)
HOOD_Y1 = J1_BODY_Y[1] + HOOD_BACK                    # hood cavity back (board y)


# ---------------------------------------------------------------- helpers (board coords)
def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, abs(y1 - y0), z1 - z0, centered=False).translate(
        (min(x0, x1), -max(y0, y1), z0))


def rbox(x0, x1, y0, y1, z0, z1, r):
    return box(x0, x1, y0, y1, z0, z1).edges("|Z").fillet(r)


def cyl(x, y, z0, z1, d):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, -y, z0))


def cyl_x(x0, x1, y, z, d):
    return cq.Workplane("YZ").circle(d / 2).extrude(x1 - x0).translate((x0, -y, z))


def cyl_y(y0, y1, x, z, d):
    """cylinder along board y from y0 to y1."""
    return cq.Workplane("XZ").circle(d / 2).extrude(y1 - y0).translate((x, -y0, z))


def hex_x(x0, x1, y, z, af):
    return cq.Workplane("YZ").polygon(6, af / math.cos(math.pi / 6)).extrude(x1 - x0).translate((x0, -y, z))


def hex_z(x, y, z0, z1, af):
    return cq.Workplane("XY").polygon(6, af / math.cos(math.pi / 6)).extrude(z1 - z0).translate((x, -y, z0))


def ring(x, y, z0, z1, od, idia):
    return cyl(x, y, z0, z1, od).cut(cyl(x, y, z0 - 1, z1 + 1, idia))


def union(*shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.union(o)
    return s


def pilaster_xy():
    return [(x, y) for y in LID_SCREW_Y for x in (X0 - PIL_OFF, X1 + PIL_OFF)]


def pilaster(x, y, z0, z1):
    wall_x = X0 if x < 0 else X1
    bridge = box(min(x, wall_x - math.copysign(1.0, x - wall_x)), max(x, wall_x - math.copysign(1.0, x - wall_x)),
                 y - PIL_D / 2, y + PIL_D / 2, z0, z1)
    return cyl(x, y, z0, z1, PIL_D).union(bridge)


def j1_cuts(z_top_pockets, z_top_window, z_from):
    """U-slot of the J1 panel: inner pocket + outer recess for the flange plates, window in the web."""
    w = J1_FL_W / 2 + J1_FIT
    s = J1_SH_W / 2 + J1_FIT
    inner = box(J1_X - w, J1_X + w, WEB[1], FRONT_IN + 0.1, max(z_from, T), z_top_pockets)
    outer = box(J1_X - w, J1_X + w, FRONT_OUT - 0.1, WEB[0], max(z_from, T), z_top_pockets)
    window = box(J1_X - s, J1_X + s, WEB[0] - 0.1, WEB[1] + 0.1, max(z_from, T + J1_SH_Z[0] - J1_FIT), z_top_window)
    return inner.union(outer).union(window)


def gasket_ring(z0, z1):
    xc0, xc1 = X0 + WALL / 2, X1 - WALL / 2
    yc0, yc1 = (FRONT_IN + FRONT_OUT) / 2, Y1 - WALL / 2
    h = GASKET_W / 2
    o = rbox(xc0 - h, xc1 + h, yc0 - h, yc1 + h, z0, z1, 2.0 + h)
    i = rbox(xc0 + h, xc1 - h, yc0 + h, yc1 - h, z0 - 1, z1 + 1, 2.0 - h)
    return o.cut(i)


# ---------------------------------------------------------------- base
def make_base():
    base = rbox(X0, X1, Y0, Y1, 0, Z_SEAM, OUT_R)
    for x, y in pilaster_xy():
        base = base.union(pilaster(x, y, 0, Z_SEAM))
    for y in EAR_Y:
        for side in (-1, 1):
            xw = X0 if side < 0 else X1
            ear = rbox(min(xw, xw + side * EAR_L), max(xw, xw + side * EAR_L) + (1 if side < 0 else -1) * 0,
                       y - EAR_W / 2, y + EAR_W / 2, 0, EAR_T, 2.5)
            base = base.union(ear.union(box(min(xw, xw - side * 2), max(xw, xw - side * 2), y - EAR_W / 2,
                                            y + EAR_W / 2, 0, EAR_T)))
            base = base.cut(cyl(xw + side * EAR_L / 2, y, -1, EAR_T + 1, EAR_HOLE))
    base = base.cut(rbox(-CLR, BW + CLR, -CLR, BH + CLR, FLOOR, Z_SEAM + 1, CAV_R))
    for x, y in P.HOLES:
        base = base.union(cyl(x, y, FLOOR - 0.5, Z_PCB_BOT, STANDOFF_D)).cut(cyl(x, y, FLOOR - 2, Z_PCB_BOT + 1, TAP_D))
    for x0, x1, y0, y1 in PEDESTALS:
        base = base.union(rbox(x0, x1, y0, y1, FLOOR - 0.5, Z_PCB_BOT - PAD_T, 1.0))
    base = base.cut(j1_cuts(Z_SEAM + 1, Z_SEAM + 1, 0))
    base = base.cut(gasket_ring(Z_SEAM - GASKET_D, Z_SEAM + 1))
    for x, y in pilaster_xy():
        base = base.cut(cyl(x, y, Z_SEAM - 12, Z_SEAM + 1, TAP_D))
    # SMA bulkhead hole + outside spot face
    base = base.cut(cyl_x(BW, X1 + 1, UFL_XY[1], T + SMA_Z, SMA_HOLE))
    base = base.cut(cyl_x(X1 - 0.5, X1 + 1, UFL_XY[1], T + SMA_Z, 12.0))
    if not USB_OPENING:
        return base
    L, H = USB_SLOT
    usb = (cq.Workplane("XZ").slot2D(L, H).extrude(WALL + 2)
           .translate((J3_X, -(BH + CLR - 1), T + 1.6)))
    return base.cut(usb)


# ---------------------------------------------------------------- lid
def make_lid():
    plate = rbox(X0, X1, Y0, Y1, Z_SEAM, Z_LID_TOP, OUT_R)
    yb = HOOD_Y1 + HOOD_T - 2.5           # slope starts here (board y)
    prof = (cq.Workplane("YZ").polyline([(-Y0, Z_SEAM), (-Y0, HOOD_TOP), (-yb, HOOD_TOP),
                                         (-(yb + HOOD_SLOPE), Z_LID_TOP), (-(yb + HOOD_SLOPE), Z_SEAM)])
            .close().extrude(X1 - X0).translate((X0, 0, 0)))
    hood = prof.intersect(rbox(X0, X1, Y0, Y1, Z_SEAM, HOOD_TOP + 1, OUT_R))
    lid = plate.union(hood)
    try:
        lid = lid.faces(">Z").edges().fillet(1.5)
    except Exception:
        pass
    lid = lid.cut(rbox(-CLR, BW + CLR, -CLR, HOOD_Y1, Z_SEAM - 1, HOOD_TOP - HOOD_T, CAV_R))
    lid = lid.cut(j1_cuts(T + J1_FL_Z[1] + J1_FIT, T + J1_SH_Z[1] + J1_FIT, Z_SEAM - 1))
    for x, y in pilaster_xy():
        lid = lid.union(pilaster(x, y, Z_SEAM, Z_LID_TOP)).cut(cyl(x, y, Z_SEAM - 1, Z_LID_TOP + 1, CLEAR_D))
    for sx, sy in STUDS.values():
        lid = lid.union(cyl(sx, sy, Z_LID_TOP - 0.5, Z_LID_TOP + STUD_BOSS_H, STUD_BOSS_D))
        lid = lid.cut(cyl(sx, sy, Z_SEAM - 1, Z_POCKET, POCKET_D)).cut(
            cyl(sx, sy, Z_SEAM - 1, Z_LID_TOP + STUD_BOSS_H + 1, SLEEVE_OD))
    return lid


# ---------------------------------------------------------------- board and mating parts
def make_j1():
    w = J1_X
    body = box(w - J1_BODY_W / 2, w + J1_BODY_W / 2, J1_BODY_Y[0], J1_BODY_Y[1], T, T + J1_H)
    fin = box(w - J1_FL_W / 2, w + J1_FL_W / 2, *J1_FL_IN, T + J1_FL_Z[0], T + J1_FL_Z[1])
    fout = box(w - J1_FL_W / 2, w + J1_FL_W / 2, *J1_FL_OUT, T + J1_FL_Z[0], T + J1_FL_Z[1])
    core = box(w - J1_SH_W / 2, w + J1_SH_W / 2, WEB[0], WEB[1], T + J1_SH_Z[0], T + J1_SH_Z[1])
    sh = box(w - J1_SH_W / 2, w + J1_SH_W / 2, *J1_SH_Y, T + J1_SH_Z[0], T + J1_SH_Z[1])
    sh = sh.cut(box(w - J1_SH_W / 2 + 1.5, w + J1_SH_W / 2 - 1.5, J1_SH_Y[0] - 0.1, J1_SH_Y[1] - 1.0,
                    T + J1_SH_Z[0] + 1.5, T + J1_SH_Z[1] - 1.5))
    ramp = box(w - 4, w + 4, -10.0, -7.0, T + J1_SH_Z[1], T + J1_SH_Z[1] + 1.2)
    return union(body, fin, fout, core, sh, ramp)


def make_plug():
    """TE 4-1437290-0 Superseal 1.0 34-way plug housing, upper lever latch, wires out the back."""
    w = J1_X
    y_front, y_rear = J1_FL_OUT[0] - 1.0, -34.0
    zb, zt = T + 0.2, T + 26.8
    body = rbox(w - 19.5, w + 19.5, y_rear, y_front, zb, zt, 2.0)
    body = body.cut(box(w - J1_SH_W / 2 - 0.3, w + J1_SH_W / 2 + 0.3, J1_SH_Y[0] - 0.5, y_front + 0.1,
                        T + J1_SH_Z[0] - 0.3, T + J1_SH_Z[1] + 0.3))
    body = body.cut(box(w - 4.3, w + 4.3, -10.3, -6.7, T + J1_SH_Z[1], T + J1_SH_Z[1] + 1.4))   # J1 latch ramp
    body = body.cut(box(w - 3.2, w + 3.2, -12.2, -7.8, zt - 1.0, zt + 0.1))                   # latch hook
    cover = rbox(w - 17.0, w + 17.0, y_rear - 4.0, y_rear, zb + 1.8, zt - 1.8, 1.5)
    latch = union(box(w - 6, w + 6, -30.0, -8.0, zt, zt + 1.6),
                  box(w - 6, w + 6, -32.0, -26.0, zt, zt + 3.0),           # press pad
                  box(w - 3, w + 3, -12.0, -8.0, zt - 0.5, zt + 2.2))     # hook over the ramp
    wires = []
    rows = ((T + 20.5, 9, -12.0), (T + 16.0, 8, -10.5), (T + 11.0, 8, -10.5), (T + 6.5, 9, -12.0))
    for z, n, x0 in rows:
        for i in range(n):
            x = w + x0 + 3.0 * i
            wires.append(cyl_y(y_rear - 4.0, y_rear - 12.0 + 1.5 * abs(x - w) / 12, x, z, 1.6))
    loom = cyl_y(y_rear - 11.0, y_rear - 70.0, w, T + 13.5, 18.0)
    loom = loom.union(cq.Workplane("XZ").circle(9.0).workplane(offset=-6).circle(16.0)
                      .loft().translate((w, -(y_rear - 11.0), T + 13.5)))
    return body.union(cover), latch, union(*wires).cut(loom), loom


def make_block(sx, sy):
    """Wurth 7461059 REDCUBE: 13.0 square brass block, 13.5 high, M6 thread from the top (bore drawn 5.0, 12.5 deep)."""
    h = BLOCK / 2
    blk = box(sx - h, sx + h, sy - h, sy + h, T, T + BLOCK_H)
    return blk.cut(cyl(sx, sy, T + BLOCK_H - THREAD_DEPTH, T + BLOCK_H + 1, 5.0))


def make_lugset(sx, sy, z0, shank):
    """ring lug lying on z0, tongue + barrel + cable to the rear, washer, M6 bolt of `shank` mm under the head."""
    z_lug = z0 + LUG_T
    tw = LUG_TONGUE_W / 2
    lug = ring(sx, sy, z0, z_lug, LUG_OD, 6.5).union(box(sx - tw, sx + tw, sy + 4.0, sy + 15.0, z0, z_lug))
    lug = lug.union(cyl_y(sy + 14.0, sy + 26.0, sx, z_lug + 3.0, 8.5)).union(
        box(sx - 3, sx + 3, sy + 12, sy + 15, z0, z_lug + 3.0))
    cable = cyl_y(sy + 26.0, sy + 75.0, sx, z_lug + 3.0, 7.5)
    washer = ring(sx, sy, z_lug, z_lug + 1.2, 12.0, 6.4)
    bolt = hex_z(sx, sy, z_lug + 1.2, z_lug + 5.2, 10.0).union(cyl(sx, sy, z_lug + 1.2 - shank, z_lug + 1.2, 6.0))
    return dict(lug=lug, cable=cable, washer=washer, bolt=bolt)


def make_stud_stack(sx, sy):
    """block (drawn separately) -> brass riser through the lid sleeve -> ring lug -> washer -> M6x20 into the block thread."""
    z_fl = Z_LID_TOP + STUD_BOSS_H
    z_ft = z_fl + SLEEVE_FL_T
    sleeve = ring(sx, sy, Z_SEAM, Z_POCKET, POCKET_D - 0.2, POCKET_D - 2.6)                  # wall round the block
    sleeve = sleeve.union(ring(sx, sy, T + BLOCK_H + 0.2, Z_POCKET, POCKET_D - 0.2, SLEEVE_ID))  # roof over the block
    sleeve = sleeve.union(ring(sx, sy, Z_POCKET, z_fl, SLEEVE_OD - 0.1, SLEEVE_ID))
    sleeve = sleeve.union(ring(sx, sy, z_fl, z_ft, SLEEVE_FL_D, SLEEVE_ID))
    z_sp = z_ft + 0.3
    spacer = ring(sx, sy, T + BLOCK_H, z_sp, SPACER_D, 6.4)
    fx0, fx1, fy0, fy1 = FINGER
    z_lug = z_sp + LUG_T
    for side in (-1, 1):   # fingers either side of the lug tongue: the lug can't turn toward the other stud
        xa, xb = sorted((sx + side * fx0, sx + side * fx1))
        sleeve = sleeve.union(box(xa, xb, sy + fy0, sy + fy1, z_ft - 0.1, z_lug + 0.5))
    ls = make_lugset(sx, sy, z_sp, z_sp + LUG_T + 1.2 - (T + BLOCK_H - BOLT_ENGAGE))
    tw = LUG_TONGUE_W / 2
    z_cap = z_ft + 0.1     # boot sits on the sleeve flange
    cap = (cyl(sx, sy, z_cap, z_cap + CAP_H, CAP_D).union(
        cq.Workplane("XY").sphere(CAP_D / 2).translate((sx, -sy, z_cap + CAP_H)).intersect(
            box(sx - CAP_D, sx + CAP_D, sy - CAP_D, sy + CAP_D, z_cap + CAP_H, z_cap + CAP_H + 5.0)))
           .union(rbox(sx - 6.0, sx + 6.0, sy, sy + 22.0, z_cap, z_lug + 8.5, 2.0)))
    cap = cap.union(cyl_y(sy + 18.0, sy + 30.0, sx, z_lug + 3.0, 11.0))
    cap = cap.cut(cyl(sx, sy, z_cap - 1, z_cap + CAP_H - 1.5, CAP_D - 3.0)).cut(
        cyl_y(sy + 8.0, sy + 31.0, sx, z_lug + 3.0, 9.0)).cut(
        box(sx - tw - 0.3, sx + tw + 0.3, sy, sy + 16.0, z_cap - 1, z_lug + 3.0))    # tongue channel
    return dict(stud=make_block(sx, sy), sleeve=sleeve, spacer=spacer, cap=cap, **ls)


def make_usb_plug():
    """USB-C plug into J3 (receptacle opens to +board y, axis z = T + 1.6): metal shell, overmold, strain relief, cable."""
    x, z = J3_X, T + 1.6
    shell = box(x - 4.15, x + 4.15, 111.3, 112.6, z - 1.3, z + 1.3)
    mold = box(x - 6.0, x + 6.0, 112.6, 131.0, z - 3.25, z + 3.25).edges("|Y").fillet(1.5)
    relief = cyl_y(131.0, 145.0, x, z, 6.0)
    cable = cyl_y(145.0, 165.0, x, z, 4.2).union(cyl_x(x - 45.0, x + 2.1, 165.0, z, 4.2))   # elbows off to the side, clear of J2's cable
    return union(shell, mold, relief), cable


def make_jumpers():
    """shunts on JP1/JP2 (vertical 1x02, pins along +y) and a 4-way Dupont housing + 4 wires on J4 (1x04)."""
    pins = {"JP1": (53.05, 69.6, 2), "JP2": (49.3, 69.6, 2), "J4": (53.1, 77.7, 4)}
    shunts = []
    for ref in ("JP1", "JP2"):
        x, y, n = pins[ref]
        shunts.append(box(x - 1.25, x + 1.25, y - 1.27, y + 2.54 + 1.27, T + 2.5, T + 9.0))
    x, y, n = pins["J4"]
    housing = box(x - 1.3, x + 1.3, y - 1.27, y + 2.54 * 3 + 1.27, T + 2.5, T + 11.5)
    wires = []
    for i in range(4):
        yy = y + 2.54 * i
        wires.append(cyl(x, yy, T + 11.5, T + 21.0, 1.4).union(cyl_x(x, x + 70.0, yy, T + 21.0, 1.4)))
    return union(*shunts), housing, union(*wires)


def make_sma():
    y, z = UFL_XY[1], T + SMA_Z
    xi = BW + CLR                      # wall inner face
    inside = hex_x(xi - 2.0, xi, y, z, 8.0).union(cyl_x(xi - 5.0, xi - 2.0, y, z, 6.0))
    pig = cyl(UFL_XY[0] + 0.8, y, T + 2.0, z, 1.2).union(cyl(UFL_XY[0], y, T + 0.8, T + 2.4, 2.2))
    pig = pig.union(cyl_x(UFL_XY[0] + 0.2, xi - 5.0, y, z, 1.2))
    outside = hex_x(X1, X1 + 2.5, y, z, 8.0).union(cyl_x(X1 + 2.5, X1 + 8.0, y, z, 6.35))
    ant_nut = cyl_x(X1 + 7.0, X1 + 15.0, y, z, 8.5)
    knuckle = cyl_y(y - 4.5, y + 4.5, X1 + 19.0, z, 9.0).union(box(X1 + 14.0, X1 + 19.0, y - 4.0, y + 4.0, z - 4.0, z + 4.0))
    whip = (cq.Workplane("XY").circle(5.0).workplane(offset=95.0).circle(3.5).loft()
            .translate((X1 + 19.0, -y, z + 2.0)))
    whip = whip.union(cq.Workplane("XY").sphere(3.5).translate((X1 + 19.0, -y, z + 97.0)))
    body = inside.union(outside)
    ant = ant_nut.union(knuckle).cut(body)
    return body, pig.cut(body), ant, whip.cut(ant)


def make_board_boxes():
    """Fallback board: green slab + coloured blocks for the main parts."""
    board = rbox(0, BW, 0, BH, Z_PCB_BOT, T, P.CORNER_R)
    for x, y in P.HOLES:
        board = board.cut(cyl(x, y, Z_PCB_BOT - 1, T + 1, 3.2))
    comps = [box(35.75, 53.75, 72.6, 91.8, T, T + 3.2),                           # U1 ESP32-S3-WROOM-1U
             box(2.5, 10.5, 60.0, 68.0, T, T + 10.5),                             # C3 8x10.5
             box(14.5, 20.5, 48.6, 54.6, T, T + 4.5)]                             # L1
    return board, union(*comps)


def make_onboard_extras():
    """Parts with no 3D model in the KiCad export: switches, U1 (module PCB + can, u.FL corner
    open), J3 shell. Outlines from the F.Fab layer of the routed board."""
    parts = [box(x - 2.5, x + 2.5, P.SW_Y - 3.0, P.SW_Y + 3.0, T, T + 1.2) for x in P.SW_X.values()]
    parts.append(box(36.05, 54.15, 47.65, 66.95, T, T + 0.8))          # U1 module PCB
    parts.append(box(36.05, 54.15, 52.0, 66.95, T + 0.8, T + 3.2))     # U1 can
    parts.append(box(36.05, 48.8, 47.65, 52.0, T + 0.8, T + 3.2))      # can left of the u.FL
    parts.append(box(9.48, 18.52, 103.9, 111.3, T, T + 3.26))          # J3 shell
    return union(*parts)


def load_board():
    if os.path.exists(BOARD_STEP):
        shp = cq.importers.importStep(BOARD_STEP).val().translate((0, 0, Z_PCB_BOT))
        slab, comps = [], []
        for s in shp.Solids():
            bb = s.BoundingBox()
            (slab if bb.xlen > 50 and bb.ylen > 100 else comps).append(s)
        return cq.Workplane().add(cq.Compound.makeCompound(slab)), cq.Workplane().add(cq.Compound.makeCompound(comps))
    return make_board_boxes()


# ---------------------------------------------------------------- build
STUD_PARTS = (  # name, colour (None: per-stud), exploded z
    ("spacer", (0.85, 0.66, 0.28), 60), ("sleeve", (0.93, 0.92, 0.88), 82), ("lug", (0.78, 0.78, 0.80), 105),
    ("cable", None, 105), ("washer", (0.65, 0.65, 0.68), 118), ("bolt", (0.55, 0.55, 0.58), 135), ("cap", None, 150))


def build():
    os.makedirs(OUT, exist_ok=True)
    base, lid = make_base(), make_lid()
    board, comps = load_board()
    plug_body, plug_latch, plug_wires, loom = make_plug()
    studs = {ref: make_stud_stack(*xy) for ref, xy in STUDS.items()}
    sma_body, pig, ant_nut, whip = make_sma()
    screws = union(*[hex_z(x, y, Z_LID_TOP, Z_LID_TOP + 3.0, 5.5).union(cyl(x, y, Z_LID_TOP - 10, Z_LID_TOP, 3.0))
                     for x, y in pilaster_xy()])
    gasket = gasket_ring(Z_SEAM - GASKET_D, Z_SEAM).cut(j1_cuts(Z_SEAM + 2, Z_SEAM + 2, 0))
    tpads = union(*[box(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, Z_PCB_BOT - PAD_T, Z_PCB_BOT)
                    for x0, x1, y0, y1 in PEDESTALS])
    # (name, shape, colour, exploded offset)
    parts = [
        ("base", base, (0.60, 0.62, 0.65), (0, 0, 0)),
        ("lid", lid, (0.70, 0.72, 0.75), (0, 0, 70)),
        ("gasket", gasket, (0.08, 0.08, 0.08), (0, 0, 52)),
        ("screws", screws, (0.15, 0.15, 0.17), (0, 0, 95)),
        ("tpads", tpads, (0.45, 0.70, 0.90), (0, 0, 14)),
        ("board", board, (0.04, 0.36, 0.16), (0, 0, 28)),
        ("comps", comps, (0.18, 0.18, 0.20), (0, 0, 28)),
        ("extras", make_onboard_extras(), (0.75, 0.75, 0.78), (0, 0, 28)),
        ("j1", make_j1(), (0.10, 0.10, 0.11), (0, 0, 28)),
        ("plug", plug_body, (0.12, 0.12, 0.13), (0, 55, 28)),
        ("latch", plug_latch, (0.30, 0.30, 0.32), (0, 55, 28)),
        ("wires", plug_wires, (0.05, 0.05, 0.05), (0, 55, 28)),
        ("loom", loom, (0.06, 0.06, 0.07), (0, 55, 28)),
        ("sma", sma_body, (0.85, 0.70, 0.30), (30, 0, 0)),
        ("pigtail", pig, (0.55, 0.55, 0.55), (0, 0, 28)),
        ("antnut", ant_nut, (0.10, 0.10, 0.10), (60, 0, 0)),
        ("whip", whip, (0.08, 0.08, 0.09), (60, 0, 0)),
    ]
    for ref, st in studs.items():
        parts.append((f"stud_{ref}", st["stud"], (0.80, 0.62, 0.25), (0, 0, 28)))
        for name, col, dz in STUD_PARTS:
            col = col or (CABLE_COL[ref] if name == "cable" else STUD_COL[ref])
            parts.append((f"{name}_{ref}", st[name], col, (0, 0, dz)))
    cq.exporters.export(base, os.path.join(OUT, "base.stl"), tolerance=0.05, angularTolerance=0.2)
    cq.exporters.export(lid, os.path.join(OUT, "lid.stl"), tolerance=0.05, angularTolerance=0.2)
    asm = cq.Assembly(name="driftanalyser_v3_enclosure")
    for name, shp, col, _ in parts:
        if name in ("board", "comps"):     # the KiCad board is in board.step, keeps this file small
            continue
        asm.add(shp, name=name, color=cq.Color(*col))
    asm.save(os.path.join(OUT, "enclosure.step"))
    bb = base.union(lid).val().BoundingBox()
    print(f"body {X1 - X0:.1f} x {Y1 - Y0:.1f} mm, rear height {Z_LID_TOP:.1f}, hood {HOOD_TOP:.1f}"
          f" (+{STUD_BOSS_H:.0f} stud boss), over pilasters/ears {bb.xlen:.1f} x {bb.ylen:.1f} x {bb.zlen:.1f}")
    print(f"board top Z {T:.1f}, seam Z {Z_SEAM:.1f}, J1 top Z {T + J1_H:.1f}, hood roof underside Z {HOOD_TOP - HOOD_T:.1f}")
    a, b = studs["J2"], studs["J5"]
    print("stud J2-J5: centres {:.1f}, lug-lug {:.1f}, bolt-bolt {:.1f}, boot-boot {:.1f} mm".format(
        math.dist(*STUDS.values()), a["lug"].val().distance(b["lug"].val()),
        a["bolt"].val().distance(b["bolt"].val()), a["cap"].val().distance(b["cap"].val())))
    return parts


def build_mated():
    """bare board with every mating part in place: no base, no lid (renders only)."""
    board, comps = load_board()
    plug_body, plug_latch, plug_wires, loom = make_plug()
    sma_body, pig, ant_nut, whip = make_sma()
    usb, usb_cable = make_usb_plug()
    shunts, dup, dup_wires = make_jumpers()
    parts = [("board", board, (0.04, 0.36, 0.16), (0, 0, 0)), ("comps", comps, (0.18, 0.18, 0.20), (0, 0, 0)),
             ("extras", make_onboard_extras(), (0.75, 0.75, 0.78), (0, 0, 0)), ("j1", make_j1(), (0.10, 0.10, 0.11), (0, 0, 0)),
             ("plug", plug_body, (0.12, 0.12, 0.13), (0, 0, 0)), ("latch", plug_latch, (0.30, 0.30, 0.32), (0, 0, 0)),
             ("wires", plug_wires, (0.05, 0.05, 0.05), (0, 0, 0)), ("loom", loom, (0.06, 0.06, 0.07), (0, 0, 0)),
             ("sma", sma_body, (0.85, 0.70, 0.30), (0, 0, 0)), ("pigtail", pig, (0.55, 0.55, 0.55), (0, 0, 0)),
             ("antnut", ant_nut, (0.10, 0.10, 0.10), (0, 0, 0)), ("whip", whip, (0.08, 0.08, 0.09), (0, 0, 0)),
             ("usb", usb, (0.55, 0.57, 0.60), (0, 0, 0)), ("usbcable", usb_cable, (0.07, 0.07, 0.08), (0, 0, 0)),
             ("shunts", shunts, (0.08, 0.08, 0.09), (0, 0, 0)), ("dupont", dup, (0.12, 0.12, 0.13), (0, 0, 0)),
             ("dupwires", dup_wires, (0.85, 0.75, 0.10), (0, 0, 0))]
    for ref, (sx, sy) in STUDS.items():
        parts.append((f"block_{ref}", make_block(sx, sy), (0.80, 0.62, 0.25), (0, 0, 0)))
        ls = make_lugset(sx, sy, T + BLOCK_H, 12.0)
        parts += [(f"lug_{ref}", ls["lug"], (0.78, 0.78, 0.80), (0, 0, 0)), (f"cable_{ref}", ls["cable"], CABLE_COL[ref], (0, 0, 0)),
                  (f"washer_{ref}", ls["washer"], (0.65, 0.65, 0.68), (0, 0, 0)), (f"bolt_{ref}", ls["bolt"], (0.55, 0.55, 0.58), (0, 0, 0))]
    return parts


# pairs allowed to overlap: screws in their tap holes, the M6 bolts in the studs' threads
CLASH_OK = {("base", "screws")} | {(f"bolt_{r}", f"stud_{r}") for r in STUDS}


def clash(parts, tol=1e-3):
    solids = [(n, s.val() if isinstance(s, cq.Workplane) else s) for n, s, _, _ in parts]
    bad = []
    for i, (na, a) in enumerate(solids):
        ba = a.BoundingBox()
        for nb, b in solids[i + 1:]:
            bb = b.BoundingBox()
            if (ba.xmin > bb.xmax or bb.xmin > ba.xmax or ba.ymin > bb.ymax or bb.ymin > ba.ymax
                    or ba.zmin > bb.zmax or bb.zmin > ba.zmax):
                continue
            v = a.intersect(b).Volume()
            if v > tol:
                ok = tuple(sorted((na, nb))) in {tuple(sorted(p)) for p in CLASH_OK}
                print(f"  {'ok  ' if ok else 'CLASH'} {na} x {nb}: {v:.3f} mm3")
                if not ok:
                    bad.append((na, nb, v))
    print("clash check:", "clean" if not bad else f"{len(bad)} clashes")
    return bad


if __name__ == "__main__":
    parts = build()
    if "--clash" in sys.argv:
        clash(parts)
    if "--mated" in sys.argv or "--no-render" not in sys.argv:
        mated = build_mated()
        if "--clash" in sys.argv:
            CLASH_OK.update({(f"bolt_{r}", f"block_{r}") for r in STUDS} | {("comps", "shunts"), ("comps", "dupont")})  # plugs sit over header pins
            print("mated board:")
            clash(mated)
    if "--no-render" not in sys.argv:
        sys.path.insert(0, HERE)
        import render_v3
        render_v3.render_all(parts, OUT)
        render_v3.render_mated(mated, OUT)
