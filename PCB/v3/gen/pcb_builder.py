"""Build driftanalyser-v3.kicad_pcb from the model + the placement table.

Needs pcbnew, so run it with KiCad's python:
    KICAD_PY -m gen.pcb_builder        (cwd = PCB/v3)
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pcbnew
from pcbnew import VECTOR2I_MM as MM

from gen import env, libs, model, placement, sch_writer

EDGE_W = pcbnew.FromMM(0.1)

# Six layers, in stack order: F.Cu / In1.Cu (solid GND) / In2.Cu (signals + GND) /
# In3.Cu (VBUS / VIN planes, LED lanes, GND) / In4.Cu (signals + GND) / B.Cu.
# pcbnew numbers them 0, 4, 6, 8, 10, 2 - never assume the ids are ordered.
CU = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu)
INNER = (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu)
# the inner layer the power planes live on
PWR = pcbnew.In3_Cu


def _pro_path():
    return os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pro")


def _netclass(name, clearance, track, via_d, via_drill):
    return {"name": name, "clearance": clearance, "track_width": track,
            "via_diameter": via_d, "via_drill": via_drill,
            "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "wire_width": 6, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)"}


def write_project_netclasses():
    """Merge board rules + netclasses into the existing .kicad_pro (sch_writer wrote it)."""
    with open(_pro_path()) as f:
        pro = json.load(f)
    pro.setdefault("board", {})["design_settings"] = {
        # JLCPCB 6 layer, 1 oz outer and 1 oz inner - the inner weight is an
        # order option, not JLC's stock 0.5 oz - not the KiCad defaults. 0.15 mm clearance is above that process' floor (0.127 mm); it
        # is only U3 (IMU)'s LGA-14 land pattern that ever needs to go that low.
        "rules": {"min_clearance": 0.15, "min_track_width": 0.2, "min_via_diameter": 0.6,
                  "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.3,
                  "min_copper_edge_clearance": 0.3,
                  "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.1},
        "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2,
                     "silk_line_width": 0.15, "silk_text_size_h": 1.0,
                     "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
    }
    pro["net_settings"] = {
        "classes": [
            _netclass("Default", 0.2, 0.25, 0.6, 0.3),
            # 0.4 mm at 1 oz is ~1.4 A: the 5 V and 3V3 rails carry under 1 A.
            # 0.5 / 0.25 / 0.8 mm vias (v2's) left the autorouter ~50 links short
            _netclass("Power", 0.2, 0.4, 0.6, 0.3),
            # the input and the 12 V bus: 8 x 7.5 A peak. Only the stubs are drawn
            # at this width; the pours carry the current
            _netclass("Bus", 0.3, 1.0, 0.8, 0.4),
            # one strip channel, 5 A by default: 2 mm of 1 oz outer is ~5.4 A at 20 K
            _netclass("Led12V", 0.3, 2.0, 0.8, 0.4),
        ],
        "meta": {"version": 4},
        "netclass_patterns": [
            {"netclass": "Bus", "pattern": "VIN"},
            {"netclass": "Bus", "pattern": "VBUS"},
            {"netclass": "Led12V", "pattern": "LED*_12V"},
            {"netclass": "Power", "pattern": "GND"},
            {"netclass": "Power", "pattern": "5V*"},
            {"netclass": "Power", "pattern": "3V3"},
            {"netclass": "Power", "pattern": "VBUS_USB"},
            {"netclass": "Power", "pattern": "BUCK_SW"},
        ],
    }
    with open(_pro_path(), "w") as f:
        json.dump(pro, f, indent=2)


DRU = """(version 1)

# Pad to pad spacing inside a land pattern is the part maker's, not ours. Measured
# gaps (measured on v2, refs there differ): LGA-14 0.15 mm, USB-C and TSDSO-14 0.20, buck 0.25 -
# all of them clear JLCPCB's multilayer 1 oz floor (0.127 mm), none of them clear the
# 0.25 mm we ask of our own copper. Both rules are scoped to pads of one footprint,
# so the netclass clearance still governs everything we draw.
(rule "same footprint pad spacing"
\t(constraint clearance (min 0.2mm))
\t(condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Reference == B.Reference"))

# U2 (LM74700, SOT-23-8, 0.65 mm pitch): 0.14 mm between its pads as drawn,
# above the fab's 0.127 mm floor
(rule "U2 SOT-23-8 land pattern"
	(constraint clearance (min 0.13mm))
	(condition "A.Type == 'Pad' && B.Type == 'Pad' && A.memberOfFootprint('U2') && B.memberOfFootprint('U2')"))

# U2's ground pin has no way out but the 0.66 mm gap between C2's pads: a
# 0.2 mm run there keeps 0.23 mm to each of them. Only that run: a ground track
# inside C2's courtyard
(rule "U2 ground escape between C2 pads"
	(constraint clearance (min 0.2mm))
	(condition "A.memberOfFootprint('C2') && B.Type == 'Track' && B.NetName == 'GND' && B.intersectsCourtyard('C2')"))

(rule "U3 LGA-14 land pattern"
\t(constraint clearance (min 0.15mm))
\t(condition "A.Type == 'Pad' && B.Type == 'Pad' && A.memberOfFootprint('U3') && B.memberOfFootprint('U3')"))

# Getting a trace out of a 0.5 mm pitch land pattern costs the netclass margin:
# 0.35 mm pads leave 0.15 mm between them, so a 0.2 mm escape out of one pad runs
# 0.225 mm from the next. That is well clear of the fab's floor (0.127 mm), it is
# just below the 0.25 mm we ask of ourselves everywhere else, and it is scoped to
# U3's own pads - the autorouter never sees it, it routes to the netclass.
(rule "U3 LGA-14 escapes"
	(constraint clearance (min 0.2mm))
	(condition "A.Type == 'Pad' && A.memberOfFootprint('U3') && B.Type == 'Track'"))

# The ESP32 module footprint brings its own 0.2 mm heatsink vias. The board minimum
# stays 0.3 mm: JLCPCB surcharges holes below that, and ours are 0.4 mm.
(rule "ESP32 module heatsink vias"
\t(constraint hole_size (min 0.2mm))
\t(condition "A.memberOfFootprint('U1')"))
"""


def write_design_rules():
    path = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_dru")
    with open(path, "w") as f:
        f.write(DRU)


# JLCPCB's 6 layer 1.6 mm stack JLC06161H-3313 (their default 6 layer build) with
# the **1 oz inner copper** option: 3313 prepreg (0.0994) / 0.55 core / 2116 prepreg
# (0.1164) / 0.55 core / 3313 prepreg (0.0994). In1 (GND) sits 0.1 mm under F, so
# every F.Cu signal has its return right under it; In2 / In3 are the tight pair in
# the middle, In4 sits 0.1 mm over B. The inner weight is what lets the In3 VBUS
# plane carry the strip current; at the stock 0.5 oz it is half of everything below.
# pcbnew does not wrap BOARD_STACKUP usefully, so this goes into the saved file
# as text - without it KiCad spreads the 1.6 mm evenly and the fab has to guess.
STACKUP = """	(stackup
		(layer "F.SilkS" (type "Top Silk Screen"))
		(layer "F.Paste" (type "Top Solder Paste"))
		(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
		(layer "F.Cu" (type "copper") (thickness 0.035))
		(layer "dielectric 1" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
		(layer "In1.Cu" (type "copper") (thickness 0.03))
		(layer "dielectric 2" (type "core") (thickness 0.55) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
		(layer "In2.Cu" (type "copper") (thickness 0.03))
		(layer "dielectric 3" (type "prepreg") (thickness 0.1164) (material "2116") (epsilon_r 4.16) (loss_tangent 0.02))
		(layer "In3.Cu" (type "copper") (thickness 0.03))
		(layer "dielectric 4" (type "core") (thickness 0.55) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
		(layer "In4.Cu" (type "copper") (thickness 0.03))
		(layer "dielectric 5" (type "prepreg") (thickness 0.0994) (material "3313") (epsilon_r 4.1) (loss_tangent 0.02))
		(layer "B.Cu" (type "copper") (thickness 0.035))
		(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
		(layer "B.Paste" (type "Bottom Solder Paste"))
		(layer "B.SilkS" (type "Bottom Silk Screen"))
		(copper_finish "ENIG")
		(dielectric_constraints no)
	)
"""


def write_stackup(path):
    """Put the JLC stack into the saved board, or leave the one already there."""
    with open(path) as f:
        text = f.read()
    if "(stackup" in text:
        return False
    i = text.index("\n", text.index("\t(setup")) + 1
    with open(path, "w") as f:
        f.write(text[:i] + STACKUP + text[i:])
    return True


def _edge(board, shape):
    shape.SetLayer(pcbnew.Edge_Cuts)
    shape.SetWidth(EDGE_W)
    board.Add(shape)


def _outline(board):
    """Rounded rectangle: four straight sides shortened by r, four corner arcs."""
    w, h, r = placement.BOARD_W, placement.BOARD_H, placement.CORNER_R
    pts = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = x1 - x0, y1 - y0
        n = max(abs(dx), abs(dy))
        ux, uy = dx / n, dy / n
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(MM(x0 + ux * r, y0 + uy * r))
        seg.SetEnd(MM(x1 - ux * r, y1 - uy * r))
        _edge(board, seg)
    for cx, cy, a0 in ((r, r, 180.0), (w - r, r, 270.0), (w - r, h - r, 0.0), (r, h - r, 90.0)):
        def pt(a):
            return MM(cx + math.cos(math.radians(a)) * r, cy + math.sin(math.radians(a)) * r)
        arc = pcbnew.PCB_SHAPE(board)
        arc.SetShape(pcbnew.SHAPE_T_ARC)
        arc.SetArcGeometry(pt(a0), pt(a0 + 45), pt(a0 + 90))
        _edge(board, arc)


def _link(fp, part):
    """Point the footprint at its schematic symbol.

    Two things have to line up or `pcb drc --schematic-parity` (and Update PCB
    from Schematic) treats them as unrelated: the footprint's own library id has
    to carry the nickname the symbol's Footprint field names, and its path has to
    be /root-sheet-uuid/sheet-uuid/symbol-uuid.

    Naming the library is also what lets DRC compare the board's copy of a
    footprint with the library's, so U1 and J2 - the two the generator edits the
    silk of - now report a `lib_footprint_mismatch` warning. That is the check
    working, not a fault: severity-error DRC is still clean."""
    fp.SetFPID(pcbnew.LIB_ID(*part.footprint.split(":", 1)))
    fp.SetPath(pcbnew.KIID_PATH(
        f"/{sch_writer.ROOT_UUID}/{sch_writer.SHEET_UUID[part.sheet]}/"
        f"{sch_writer.symbol_uuid(part)}"))


def _fab_field(fp, name, value):
    """A footprint field the parity check compares against the symbol's. They go
    on F.Fab and hidden - visible they would land in the middle of the silk."""
    if not hasattr(fp, "SetField"):
        return
    fp.SetField(name, value)
    f = fp.GetField(name)
    if f is not None:
        f.SetLayer(pcbnew.F_Fab)
        f.SetVisible(False)


def _holes(board):
    libdir = os.path.join(env.FOOTPRINT_DIR, "MountingHole.pretty")
    for i, (x, y) in enumerate(placement.HOLES, 1):
        fp = pcbnew.FootprintLoad(libdir, "MountingHole_3.2mm_M3")
        if fp is None:
            raise RuntimeError(f"MountingHole_3.2mm_M3 not found in {libdir}")
        fp.SetReference(f"H{i}")
        fp.SetValue("M3")
        _link(fp, sch_writer._hole_parts()[i - 1])
        fp.SetPosition(MM(x, y))
        fp.SetAttributes(fp.GetAttributes()
                         | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        board.Add(fp)


def _nets(board):
    out = {}
    for name in model.nets():
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        out[name] = n
    return out


# Pads that take the ground plane solid instead of through thermal spokes. The
# USB shield's legs and the UART header's ground pin sit where routed traces
# leave the plane in shreds, and a spoke into a shred is a starved thermal relief.
SOLID_TO_ZONE = {("J3", "SH"), ("J4", "2"),
                 # and the stud: the whole board current comes in through it
                 ("J2", "1"), ("J5", "1"),
                 # the buck's exposed-pad vias are vias, not something to solder
                 ("U7", "9")}
# J1's ground pins sit in a 0.7 mm pad grid: no thermal relief survives in it
# (DRC calls them starved), so they take the planes solid. JLC solders J1.
SOLID_TO_ZONE |= {("J1", p) for k, p in model.J1_PIN.items() if k.endswith("_GND")}


def _footprints(board, nets):
    for p in model.PARTS:
        libdir, name = libs.footprint_path(p.footprint)
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise RuntimeError(f"{p.ref}: footprint {p.footprint} not found in {libdir}")
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        _link(fp, p)
        # the fields the symbol carries, so schematic parity has nothing left to
        # report: LCSC is what the assembly house reads off the board, MPN and
        # Manufacturer are what the parity check misses without them
        for name, value in (("LCSC", p.lcsc), ("MPN", p.mpn),
                            ("Manufacturer", p.mfr)):
            if value:
                _fab_field(fp, name, value)
        x, y, rot, side = placement.PLACE[p.ref]
        fp.SetPosition(MM(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(MM(x, y), False)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:                     # unnamed mechanical pad
                continue
            if num not in p.pins:
                raise KeyError(f"{p.ref} ({p.footprint}): pad {num!r} is not in the model")
            # footprints may repeat a pad number (shields, thermal tabs): all get the net
            if p.pins[num] != "NC":
                pad.SetNet(nets[p.pins[num]])
            # the USB shield's four through-hole legs are wide and close to the
            # board edge: routed traces steal the room the thermal spokes need, so
            # they take the plane solid instead
            if (p.ref, num) in SOLID_TO_ZONE:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(fp)


# ---------------------------------------------------------------- copper
#
# Layer use:
#   F.Cu   power copper next to the parts (the VIN input block, the VBUS drain
#          block, the LED channel pours from the switches up into J1 row 1),
#          signals elsewhere
#   In1.Cu solid GND, nothing else ever (0.1 mm under F: the return of every
#          F.Cu signal, the strip data lines and the buck included)
#   In2.Cu signals, GND fill in what is left
#   In3.Cu VBUS over the middle of the board (drains -> switches) and under the
#          CAN / K-line block, VIN under the stud, the outer four LED channels'
#          lanes (in parallel with their F.Cu necks), GND in what is left
#   In4.Cu signals, GND fill in what is left
#   B.Cu   signals; VBUS copper under each switch's exposed pad (thermal pad side)
#
# The board is built without the project loaded, so the fill cannot see the
# netclasses: every zone carries the largest netclass clearance (0.3) itself.
ZONE_CLEAR = 0.3
GND_CLEAR = ZONE_CLEAR

# nets the pours (plus the stubs and ties below) finish on their own; route.py
# splits them pad by pad so the autorouter never tries to reach them
LED_NETS = tuple(f"LED{i}_12V" for i in range(1, 9))
POWER_NETS = ("VIN", "VBUS") + LED_NETS
POURED = ("GND",) + POWER_NETS

# x of each switch, and where its pins land (rot 90: OUT up, EP in the middle)
SW = placement.SW_X
SW_Y = placement.SW_Y


def _pad_box(board, ref, num):
    """Bounding box of one pad on the built board, in mm (x0, y0, x1, y1)."""
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        raise KeyError(f"no footprint {ref}")
    pad = fp.FindPadByNumber(num)
    if pad is None:
        raise KeyError(f"{ref} has no pad {num}")
    bb = pad.GetBoundingBox()
    return tuple(pcbnew.ToMM(v) for v in
                 (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _outline_pts(zone, pts):
    o = zone.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))


def _poly(rects):
    """A SHAPE_POLY_SET over a list of boxes in mm."""
    poly = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in rects:
        part = pcbnew.SHAPE_POLY_SET()
        part.NewOutline()
        for x, y in _rect(x0, y0, x1, y1):
            part.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        poly.BooleanAdd(part)
    poly.Simplify()
    return poly


def _poly_outline(zone, poly):
    """Give a zone an arbitrary outline, holes and all."""
    o = zone.Outline()
    for i in range(poly.OutlineCount()):
        o.NewOutline()
        src = poly.Outline(i)
        for k in range(src.PointCount()):
            o.Append(src.CPoint(k).x, src.CPoint(k).y)
        for h in range(poly.HoleCount(i)):
            idx = o.NewHole(i)
            hole = poly.Hole(i, h)
            for k in range(hole.PointCount()):
                o.Append(hole.CPoint(k).x, hole.CPoint(k).y, i, idx)


def _zone(board, net, layer, rects, priority=0, clearance=ZONE_CLEAR, min_w=0.25,
          connection=pcbnew.ZONE_CONNECTION_FULL):
    """One pour over the union of `rects` (mm boxes). Power pours connect FULL:
    a thermal relief in the middle of a 5 A path is a fuse. GND passes THT_THERMAL
    so the strip connector and the stud's neighbours can still be soldered."""
    poly = _poly(rects)
    # one zone per separate region: a zone saves only its first outline
    for i in range(poly.OutlineCount()):
        part = pcbnew.SHAPE_POLY_SET()
        part.AddOutline(poly.Outline(i))
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net)
        z.SetAssignedPriority(priority)
        z.SetLocalClearance(pcbnew.FromMM(clearance))
        z.SetMinThickness(pcbnew.FromMM(min_w))
        z.SetPadConnection(connection)
        z.SetIsRuleArea(False)
        _poly_outline(z, part)
        board.Add(z)


def _zone_pts(board, net, layer, pts, priority=0, clearance=ZONE_CLEAR):
    """One solid (FULL) pour with an arbitrary outline."""
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(pcbnew.FromMM(clearance))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    _outline_pts(z, pts)
    board.Add(z)


def _rule_area(board, pts):
    """Keep-out on every copper layer: no pour, no track, no via."""
    for layer in CU:
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        _outline_pts(z, pts)
        board.Add(z)


# ---- the LED channels. J1 row 1 (the row nearest the switches) holds all eight
# LEDn_12V pins, each above its own switch output (model.J1_PIN), so every channel
# is one F.Cu pour from the switch's output pins up into its pin. The inner four
# (LED3..6) go straight up; the outer pairs shift 3.7..4.1 mm sideways in the
# 2.6 mm band between the outputs and row 1, one above the other: LED2 / LED7 in
# the upper lane straight into their pin, LED1 / LED8 in the lower lane and up
# beside it. Every box is mm on the board; the fill trims each to its
# clearances. A box has to take in the centre of each pad it is meant to connect:
# that is how the filler decides the pad belongs to the pour.
LED_F = {
    "LED7_12V": [(10.6, 20.5, 16.4, 22.6), (10.6, 22.6, 12.8, 25.7)],
    "LED8_12V": [(13.3, 23.0, 19.4, 25.7), (17.6, 20.5, 19.4, 23.0)],
    "LED3_12V": [(19.9, 20.5, 23.0, 25.7)],
    "LED4_12V": [(23.2, 20.5, 25.6, 25.7)],
    "LED5_12V": [(29.4, 20.5, 32.0, 25.7)],
    "LED6_12V": [(32.4, 20.5, 34.6, 25.7)],
    "LED1_12V": [(35.6, 23.0, 41.7, 25.7), (35.6, 20.5, 37.4, 23.0)],
    "LED2_12V": [(38.6, 20.5, 44.4, 22.6), (42.2, 22.6, 44.4, 25.7)],
}

# The outer four channels shift sideways past a neighbour; their F.Cu is
# 1.75..2.05 mm at the narrowest. Each gets the same lane again on In3 (no pads
# there to neck it), joined to the F pour by vias wherever both overlap (the
# Led12V 0.8 / 0.4 where they fit, 0.6 / 0.3 in what is left), and to the J1 pin
# through the pin's own barrel.
LED_IN3 = {
    "LED7_12V": [(10.6, 19.6, 16.4, 22.6), (10.6, 22.6, 12.8, 25.0)],
    "LED8_12V": [(13.3, 23.0, 19.4, 25.0), (17.6, 19.6, 19.4, 23.0)],
    "LED1_12V": [(35.6, 23.0, 41.7, 25.0), (35.6, 19.6, 37.4, 23.0)],
    "LED2_12V": [(38.6, 19.6, 44.4, 22.6), (42.2, 22.6, 44.4, 25.0)],
}

# ---- VIN: stud -> TVS -> the two FET sources, on F.Cu and on In3 under it.
# The F pour stops east of U2 (its VBUS sense pin and the gate pin are there)
# and west of D1's ground pad.
# (the stud's eight small ring pads are separate copper of the same pad: the
# pours have to take all of them)
VIN_F = [(13.3, 67.2, 23.0, 70.9), (13.3, 67.2, 20.6, 79.0), (4.8, 77.5, 23.3, 95.9)]
VIN_IN3 = [(7.0, 67.3, 24.5, 99.2), (4.8, 78.6, 24.5, 99.2)]
# ---- VBUS: the two drain tabs and the strip north of them (In3 vias), west
# over the top of C3's ground pad to C3's and C37's VBUS pads.
VBUS_F = [(13.4, 58.6, 24.2, 66.6), (0.8, 59.6, 13.6, 62.35), (3.4, 57.9, 11.2, 59.6),
          (0.8, 59.6, 5.3, 66.0), (0.8, 55.6, 3.2, 59.6)]
# In3: the whole middle of the board from just under the switches down to the
# drains, and a strip down the west edge to C4 and U2's sense pin
# and under the CAN / K-line block below the ESP32 (the K-line pull-up, the
# transceiver's battery pin, the battery sense divider)
VBUS_IN3 = [(0.8, 26.3, 54.2, 66.9), (0.8, 66.9, 6.6, 78.0), (35.0, 66.0, 54.2, 85.9)]
# ---- battery negative: J5, the strips' 35..40 A return. A GND disc on every
# layer over its courtyard (r 10 - nothing else sits there), fenced off for the
# router, with a ring of vias round the 14 mm pad on top of the pad's own eight.
# From there In1 (solid GND, full width) and the GND fills carry it up to J1.
J5_DISC_R = 9.9
J5_VIA_R, J5_VIA_STEP = 9.3, 10.0       # ring radius (mm), angular step (deg)


def _disc(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
            for k in range(n)]
# B.Cu under each switch: the exposed pad's vias land here, and this is the
# side the case's thermal pad presses on (it has to be an insulating one)
# Half width, top, bottom: the whole package outline. The top stops below the
# LED pours' bottom edge (25.7), so the LED lanes' F-In3 vias stay clear of it,
# the bottom above the ground pin 1's tie,
# and 3.6 mm of B.Cu stays free between neighbours for J1's signals.
SW_B = (3.0, 25.9, 30.9)
# 12 vias in each switch's exposed pad (4 x 3, 0.6 / 0.3): that pad is VS, so
# they are also how VBUS gets from In3 into the switch
EP_VIA_DX = (-1.35, -0.45, 0.45, 1.35)
EP_VIA_DY = (-0.8, 0.0, 0.8)


def _zones(board, nets):
    """Every pour on the board. Returns the zones in groups route.py needs."""
    W, H = placement.BOARD_W, placement.BOARD_H
    if placement.ANTENNA_KEEPOUT:
        ax0, ay0, ax1, ay1 = placement.ANTENNA_KEEPOUT
        _rule_area(board, _rect(max(ax0, 0.0), ay0, ax1, ay1))

    # GND under everything, lowest priority; In1 is never anything else
    full = [(0.5, 0.5, W - 0.5, H - 0.5)]
    for layer in CU:
        _zone(board, nets["GND"], layer, full, priority=0,
              connection=pcbnew.ZONE_CONNECTION_THT_THERMAL)

    # one priority per channel, so two neighbours never tie for the same copper
    for k, name in enumerate(LED_NETS):
        _zone(board, nets[name], pcbnew.F_Cu, LED_F[name], priority=3 + k)
        if name in LED_IN3:
            _zone(board, nets[name], PWR, LED_IN3[name], priority=3 + k)

    _zone(board, nets["VIN"], pcbnew.F_Cu, VIN_F, priority=2)
    _zone(board, nets["VIN"], PWR, VIN_IN3, priority=2)
    _zone(board, nets["VBUS"], pcbnew.F_Cu, VBUS_F, priority=2)
    _zone(board, nets["VBUS"], PWR, VBUS_IN3, priority=2)
    gx, gy, _, _ = placement.PLACE["J5"]
    for layer in CU:
        _zone_pts(board, nets["GND"], layer, _disc(gx, gy, J5_DISC_R), priority=2)
    hw, top, bot = SW_B
    for x in SW.values():
        _zone(board, nets["VBUS"], pcbnew.B_Cu, [(x - hw, top, x + hw, bot)], priority=2)


def _via(board, net, x, y, d=0.8, drill=0.4):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(MM(x, y))
    v.SetWidth(pcbnew.FromMM(d))
    v.SetDrill(pcbnew.FromMM(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)
    return v


def _track(board, net, layer, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetStart(MM(*a))
    t.SetEnd(MM(*b))
    t.SetWidth(pcbnew.FromMM(width))
    t.SetNet(net)
    board.Add(t)


def _cap_stubs():
    """Each switch output's 10 nF sits beside the switch, level with the exposed
    pad, with its own ground pad between it and the output pins. The stub runs
    from its live pad up the 1.2 mm lane between that ground pad and the exposed
    pad, into the outermost output pin."""
    out = []
    for u, x in SW.items():
        k = int(u[1:]) - 9
        for side, cap in ((-1, f"C{21 + 3 * (k - 1)}"), (1, f"C{22 + 3 * (k - 1)}")):
            a = 2 * k - 1 if side < 0 else 2 * k
            lane = x + side * 2.55
            pin = x + side * 1.95
            out.append((f"LED{a}_12V", 0.4, "F",
                        [(x + side * 3.65, SW_Y + 0.78), (lane, SW_Y + 0.78),
                         (lane, SW_Y - 2.7), (pin, SW_Y - 2.85)]))
    return out


# Short runs drawn by hand where nothing else will do. (net, width, layer, points)
STUBS = [
    # U2 (LM74700) sits in a knot: VIN on pins 1 and 5, the VBUS sense on pin 8
    # between them and the pour, the gate on pin 6. Pin 1 takes C2 and a via to
    # the In3 VIN plane; pin 5 goes east into the F.Cu pour under the gate pin.
    ("VIN", 0.3, "F", [(7.9, 69.95), (9.1, 69.95)]),
    ("VIN", 0.3, "F", [(9.36, 69.9), (9.36, 69.0)]),
    ("VIN", 0.25, "F", [(11.64, 72.0), (13.6, 72.0)]),
    # C1, the controller's own VIN decoupling, drops to In3 VIN south of itself
    ("VIN", 0.4, "F", [(9.72, 74.4), (9.72, 75.6)]),
    # the VBUS sense pin goes north, past C3's ground pad, to an In3 via
    ("VBUS", 0.3, "F", [(11.64, 69.9), (11.64, 69.3), (11.9, 66.4)]),
    # LM_GATE: out of pin 6 between the VIN and the VBUS runs, down to B.Cu, and
    # along under the VIN pour to both gates (Q2's is 12 mm from U2). Never on
    # F.Cu across the source pour.
    ("LM_GATE", 0.2, "F", [(12.35, 71.25), (13.2, 70.73)]),
    ("LM_GATE", 0.3, "B", [(13.2, 70.73), (16.6, 70.73), (17.75, 69.6),
                           (24.1, 69.6), (24.1, 69.05)]),
    ("LM_GATE", 0.3, "F", [(17.75, 68.0), (17.75, 69.6)]),
    ("LM_GATE", 0.3, "F", [(23.61, 68.0), (24.1, 69.05)]),
    # The buck's switch node, short and fat: out of U7 pin 8 north, along to C8's
    # SW pad (now on top), on to L1. The bootstrap cap's other pad faces pin 7.
    ("BUCK_SW", 0.6, "F", [(11.4, 49.7), (11.4, 48.33), (14.9, 48.33), (14.9, 49.6)]),
    ("BUCK_BST", 0.3, "F", [(10.78, 50.97), (12.25, 50.97), (12.95, 50.27)]),
    # ground pads with no room for a tie of their own. U2 pin 2 is boxed in by
    # pins 1 / 3 and C2: out through the gap between C2's pads to a via west of it
    ("GND", 0.2, "F", [(8.75, 70.7), (8.5, 70.7), (8.25, 71.0), (6.4, 71.0)]),
    # the IMU's two ground pads in the middle of its south row: joined, and out
    # south to a via
    ("GND", 0.2, "F", [(29.8, 50.21), (30.3, 50.21)]),
    ("GND", 0.2, "F", [(30.05, 50.21), (30.05, 51.3)]),
    # C6 sits between R4's and R80's ground pads: joined to R80's
    ("GND", 0.25, "F", [(placement.PLACE["C6"][0], placement.PLACE["C6"][1] - 0.77),
                        (placement.PLACE["R80"][0], placement.PLACE["R80"][1] - 0.83)]),
]
STUB_VIAS = [("VIN", 9.36, 69.0), ("VIN", 9.72, 75.6), ("VBUS", 11.9, 66.4),
             ("LM_GATE", 13.2, 70.73), ("LM_GATE", 17.75, 69.6), ("LM_GATE", 24.1, 69.05),
             ("GND", 6.4, 71.0), ("GND", 30.05, 51.3)]
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}


def _stub_tracks(board, nets):
    for name, width, layer, pts in STUBS + _cap_stubs():
        for a, b in zip(pts, pts[1:]):
            _track(board, nets[name], LAYER[layer], a, b, width)
    for name, x, y in STUB_VIAS:
        if name in POWER_NETS:
            _via(board, nets[name], x, y)
        else:
            _via(board, nets[name], x, y, 0.6, 0.3)


# VBUS F.Cu <-> In3 at the two drain tabs (no via in the tabs: JLC assembles
# this board): two rows of nine right above them, a column of four in the gap
# between them, and (power_stitch, VBUS_WEST) a grid in the strip west of them
# over C3: 46 x 0.8 / 0.4 in all, ~1.3 A each at the 60 A peak.
DRAIN_VIAS = ([(14.0 + 1.2 * i, y) for y in (59.45, 60.65) for i in range(9)]
              + [(18.775, y) for y in (62.3, 63.5, 64.7, 65.9)])
VBUS_WEST = (0.8, 57.9, 13.4, 62.4)


def _j5_vias(board, nets):
    """The ring round J5's pad, wherever it misses the pad's own small vias."""
    gx, gy, _, _ = placement.PLACE["J5"]
    reach = pcbnew.FromMM(0.4 + 0.2)
    out = []
    a = 0.0
    while a < 360.0 - 1e-6:
        x = round(gx + J5_VIA_R * math.cos(math.radians(a)), 3)
        y = round(gy + J5_VIA_R * math.sin(math.radians(a)), 3)
        if _inside_board(x, y, 0.9) and _clear_of_everything(board, MM(x, y), reach, "GND"):
            _via(board, nets["GND"], x, y)
            out.append((x, y))
        a += J5_VIA_STEP
    return out


def _fixed_vias(board, nets):
    _j5_vias(board, nets)
    for x, y in DRAIN_VIAS:
        _via(board, nets["VBUS"], x, y)
    for x in SW.values():
        for dx in EP_VIA_DX:
            for dy in EP_VIA_DY:
                _via(board, nets["VBUS"], x + dx, SW_Y + dy, 0.6, 0.3)


def _zones_of(board, net, layer):
    return [z for z in board.Zones() if not z.GetIsRuleArea()
            and z.GetNetname() == net and z.IsOnLayer(layer)]


def _clear_of_everything(board, p, reach, net, keep_pad=None):
    """No pad (of any net: no via in a pad), no track of another net and no via
    at all within reach. `keep_pad` is the one pad a tie may touch."""
    # every pad, our own net's too: no via in a pad (JLC assembles this board)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.HitTest(p, reach) and not (keep_pad is not None and pad.m_Uuid.AsString()
                                                 == keep_pad.m_Uuid.AsString() and not pad.HitTest(p)):
                return False
    for t in board.Tracks():
        if (t.GetClass() == "PCB_VIA" or t.GetNetname() != net) and t.HitTest(p, reach):
            return False
    return True


def _foreign_pours(board, net):
    """Pours this net's vias must stay out of: another net's power pour on an
    outer layer, or an LED lane on In3. The In3 VBUS / VIN planes are not on the
    list - they are big enough that an anti-pad costs them nothing."""
    return [z for z in board.Zones() if not z.GetIsRuleArea()
            and z.GetNetname() in POWER_NETS and z.GetNetname() != net
            and (z.GetNetname() in LED_NETS or not z.IsOnLayer(PWR))]


def stitch(board, net, upper, lower, box=None, step=1.2, d=0.8, drill=0.4):
    """A grid of vias wherever `upper` and `lower` (layers) both carry a pour of
    `net`, inside `box` if given, clear of everything. Returns the spots."""
    r = d / 2
    reach = pcbnew.FromMM(r + ZONE_CLEAR + 0.05)
    deep = pcbnew.FromMM(r + 0.35)

    def shrunk(zones):
        out = []
        for z in zones:
            p = pcbnew.SHAPE_POLY_SET(z.Outline())
            p.Deflate(deep, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
            if not p.IsEmpty():
                out.append(p)
        return out

    tops, bots = shrunk(_zones_of(board, net, upper)), shrunk(_zones_of(board, net, lower))
    foreign = _foreign_pours(board, net)
    edge = pcbnew.FromMM(0.5 + r)
    W, H = placement.BOARD_W, placement.BOARD_H
    netinfo = board.FindNet(net)
    added = []
    for top in tops:
        bb = top.BBox()
        x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
        if box:
            x0, y0, x1, y1 = max(x0, box[0]), max(y0, box[1]), min(x1, box[2]), min(y1, box[3])
        y = y0
        while y <= y1 + 1e-6:
            x = x0
            while x <= x1 + 1e-6:
                p = MM(x, y)
                if (top.Contains(p) and any(b.Contains(p) for b in bots)
                        and _inside_board(x, y, r + 0.5)
                        and not any(z.Outline().Collide(p, reach) for z in foreign)
                        and _clear_of_everything(board, p, reach, net)):
                    _via(board, netinfo, x, y, d, drill)
                    added.append((round(x, 2), round(y, 2)))
                x += step
            y += step
    return added


def _inside_board(x, y, keep):
    """Inside the rounded outline with `keep` mm to spare."""
    W, H, R = placement.BOARD_W, placement.BOARD_H, placement.CORNER_R
    if not (keep <= x <= W - keep and keep <= y <= H - keep):
        return False
    cx = R if x < R else (W - R if x > W - R else None)
    cy = R if y < R else (H - R if y > H - R else None)
    if cx is not None and cy is not None:
        return math.hypot(x - cx, y - cy) <= R - keep
    return True


def power_stitch(board):
    """The vias between the outer power pours and their inner planes."""
    out = {}
    out["VIN F-In3"] = stitch(board, "VIN", pcbnew.F_Cu, PWR)
    # the strip west of the drain tabs, over C3: the drain rows alone are 18 vias
    # for up to 60 A
    out["VBUS F-In3"] = stitch(board, "VBUS", pcbnew.F_Cu, PWR, box=VBUS_WEST)
    for name in LED_IN3:
        out[f"{name} F-In3"] = (stitch(board, name, pcbnew.F_Cu, PWR, step=0.5)
                                + stitch(board, name, pcbnew.F_Cu, PWR, step=0.5, d=0.6, drill=0.3))
    return out


# a 0.6/0.3 via and the clearance it keeps
TIE_D, TIE_DRILL, TIE_CLEAR = 0.6, 0.3, 0.3
# the run from the pad to its tie: 0.25 wide, 0.25 (the Power netclass) to the
# next pin, which is what gets it out of a 0.65 mm pitch row
TIE_W, TIE_TRACK_CLEAR = 0.25, 0.25
# which inner plane a tie for each net lands on
TIE_PLANE = {"GND": pcbnew.In1_Cu, "VBUS": PWR, "VIN": PWR}


def _covered(board, pad, net):
    """True if a same-net pour on F.Cu already overlaps this pad, or a via of the
    net sits on it / right next to it."""
    c = pad.GetPosition()
    for z in _zones_of(board, net, pcbnew.F_Cu):
        if z.GetAssignedPriority() > 0 and z.Outline().Collide(c):
            return True
    reach = pcbnew.FromMM(0.9)
    for t in board.Tracks():
        if t.GetNetname() == net and pad.HitTest(t.GetPosition(), reach if
                                                 t.GetClass() == "PCB_VIA" else 0):
            return True
    return False


def _ties(board, nets, names=("GND", "VBUS", "VIN")):
    """A via from every F.Cu-only pad of these nets down to its inner plane, with
    a short track when it cannot touch the pad. On two layers v2 lost eighteen
    ground pads to islands the routed traces cut out of the top pour; here every
    one of them is tied before routing, so the router plans around the ties."""
    r = TIE_D / 2
    reach = pcbnew.FromMM(r + TIE_CLEAR)
    ties, missed = [], []
    planes = {n: [pcbnew.SHAPE_POLY_SET(z.Outline()) for z in
                  _zones_of(board, n, TIE_PLANE[n]) if n == "GND" or z.GetAssignedPriority() > 0]
              for n in names}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if (net not in names or not pad.IsOnLayer(pcbnew.F_Cu)
                    or pad.IsOnLayer(pcbnew.B_Cu)):
                continue
            if _covered(board, pad, net) or any(
                    o.GetNetname() == net and o.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                    and pad.HitTest(o.GetPosition()) for o in fp.Pads()):
                continue
            c = pad.GetPosition()
            cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            bb = pad.GetBoundingBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in
                              (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            foreign = _foreign_pours(board, net)
            spot = None
            for g in (0.05, 0.3, 0.6, 1.0):
                d = r + g
                for s in ((cx, y1 + d), (cx, y0 - d), (x1 + d, cy), (x0 - d, cy),
                          (x1 + d, y1 + d), (x0 - d, y1 + d), (x1 + d, y0 - d), (x0 - d, y0 - d)):
                    p = MM(*s)
                    if not _inside_board(s[0], s[1], r + 0.5):
                        continue
                    if not any(pl.Contains(p) for pl in planes[net]):
                        continue
                    if any(z.Outline().Collide(p, reach) for z in foreign):
                        continue
                    if not _clear_of_everything(board, p, reach, net, keep_pad=pad):
                        continue
                    if not _track_clear(board, net, (cx, cy), s, TIE_W):
                        continue
                    spot = s
                    break
                if spot:
                    break
            if spot is None:
                missed.append(fp.GetReference() + "." + pad.GetNumber())
                continue
            _track(board, nets[net], pcbnew.F_Cu, (cx, cy), spot, TIE_W)
            _via(board, nets[net], spot[0], spot[1], TIE_D, TIE_DRILL)
            ties.append((fp.GetReference() + "." + pad.GetNumber(), spot))
    return ties, missed


def _track_clear(board, net, a, b, width):
    """A straight F.Cu run from a to b keeps TIE_CLEAR to every foreign pad and
    track along its length (sampled every 0.1 mm)."""
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.1) + 1)
    reach = pcbnew.FromMM(width / 2 + TIE_TRACK_CLEAR)
    items = [pad for fp in board.GetFootprints() for pad in fp.Pads()
             if pad.GetNetname() != net and pad.IsOnLayer(pcbnew.F_Cu)]
    items += [t for t in board.Tracks() if t.GetNetname() != net
              and t.IsOnLayer(pcbnew.F_Cu)]
    for i in range(n):
        f = i / (n - 1)
        p = MM(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        if any(it.HitTest(p, reach) for it in items):
            return False
    return True


def _thin_j1_pads(board):
    """J1's pads keep their copper on F and B only, and on an inner layer only
    where a pour or a track of their own net meets them. On In2 / In4 the
    signals run between those holes; with 2.2 mm pads on every layer the gaps
    there would be 0.7 mm instead of ~1 mm, and on In1 / In3 the planes and the
    LED lanes get the same room."""
    fp = board.FindFootprintByReference("J1")
    for pad in fp.Pads():
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            pad.SetUnconnectedLayerMode(
                pcbnew.UNCONNECTED_LAYER_MODE_REMOVE_EXCEPT_START_AND_END)


# ---------------------------------------------------------------- silkscreen

# how far silk stays from the board outline, and the size every reference gets:
# the stock 1.0 mm references collide with each other all over the dense corners
SILK_EDGE_KEEP = 0.4
REF_SIZE = 0.8
REF_THICK = 0.12

# mounting holes: their references say nothing. The switch control rows and
# the 33R / clamp pairs are a repeating pattern packed edge to edge with no spot
# left for a legible reference; they are on the CPL, so they lose it.
REF_HIDE = (("H1", "H2", "H3", "H4")
            + tuple(f"R{n}" for n in range(20, 49))
            + tuple(f"C{n}" for n in range(20, 32))
            + tuple(f"R{n}" for n in range(54, 62))
            + tuple(f"D{n}" for n in range(11, 19)))

# references the stock offset drops on a neighbour's pad or silk. Absolute mm,
# text unrotated - the free spot was picked off the silk + pad map of the board.
REF_AT = {}


def _text(board, s, x, y, size=1.0, rot=0, bold=False, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(0.25 * size if bold else 0.15 * size))
    t.SetTextAngleDegrees(rot)
    t.SetPosition(MM(x, y))
    board.Add(t)
    return t


def _seg(board, x0, y0, x1, y1, w=0.2, layer=pcbnew.F_SilkS):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(layer)
    s.SetWidth(pcbnew.FromMM(w))
    s.SetStart(MM(x0, y0))
    s.SetEnd(MM(x1, y1))
    board.Add(s)


def _dot(board, x, y, d=0.7):
    c = pcbnew.PCB_SHAPE(board)
    c.SetShape(pcbnew.SHAPE_T_CIRCLE)
    c.SetLayer(pcbnew.F_SilkS)
    c.SetFilled(True)
    c.SetWidth(pcbnew.FromMM(0.1))
    c.SetCenter(MM(x, y))
    c.SetEnd(MM(x + d / 2.0, y))
    board.Add(c)


def _arrow(board, x0, y0, x1, y1, head=0.8):
    """A segment with a two-stroke head at (x1, y1)."""
    _seg(board, x0, y0, x1, y1)
    ux, uy = x1 - x0, y1 - y0
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    for sx, sy in ((-uy, ux), (uy, -ux)):
        _seg(board, x1, y1,
             x1 - ux * head + sx * head * 0.5, y1 - uy * head + sy * head * 0.5)


def _silk(board):
    """Everything a person needs to wire the board up without the schematic."""
    W = placement.BOARD_W
    # the strips beside J1's body are the only free silk on the board: name and
    # date on the left, the jumper legend on the right (no room beside them)
    _text(board, "DriftAnalyser v3", 1.6, 13.0, size=1.3, rot=90, bold=True)
    _text(board, "2026-10", 3.4, 13.0, size=0.8, rot=90)
    _text(board, "JP1 K-LINE", W - 3.4, 13.0, size=0.8, rot=90, bold=True)
    _text(board, "JP2 CAN TERM", W - 1.8, 13.0, size=0.8, rot=90, bold=True)

    # ---- J1 pin 1 (LED1 12V): its own dot sits on U10, so mark it inside the body
    jx, jy = placement.J1_AT
    _text(board, "1", jx + 12.0 + 2.3, jy + 14.5, size=1.2, bold=True)

    # ---- studs: +12 V in, battery negative beside it
    sx, sy, _, _ = placement.PLACE["J2"]
    _text(board, "+12V", 1.8, sy, size=1.4, rot=90, bold=True)
    gx, gy, _, _ = placement.PLACE["J5"]
    _text(board, "GND", gx - 3.5, gy + 12.7, size=1.4, bold=True)
    _text(board, "\u2212", gx + 0.5, gy + 12.7, size=1.4, bold=True)

    # ---- IMU axes. U3 sits at rot 0 with LGA pad 1 top-left, which is the
    # LSM6DS3TR-C datasheet's top view: sensor +X points at the board's right
    # edge, +Y at J1 (top edge), +Z out of the front. No free silk beside U3
    # itself, so the legend sits in the open corner left of the stud.
    ox, oy = 1.4, sy - 5.5
    _arrow(board, ox, oy, ox + 3.2, oy)
    _text(board, "X", ox + 4.1, oy, size=0.8, bold=True)
    _arrow(board, ox, oy, ox, oy - 3.0)
    _text(board, "Y", ox, oy - 3.8, size=0.8, bold=True)
    _text(board, "IMU", ox + 2.2, oy + 1.4, size=0.8)

    # ---- buttons and USB: their bodies cover their own footprints, so beside them
    x, y, _, _ = placement.PLACE["SW1"]
    _text(board, "BOOT", x - 5.75, y, size=0.8, rot=90, bold=True)
    x, y, _, _ = placement.PLACE["SW2"]
    _text(board, "EN", x - 5.9, y + 1.2, size=1.0, rot=90, bold=True)
    x, y, _, _ = placement.PLACE["J3"]
    _text(board, "USB", x - 6.4, y, size=1.0, rot=90, bold=True)


def _clip_silk(board):
    """Silk off the board is silk printed on the panel: the ESP32 module's outline
    runs out over the left edge with its antenna. Pull segment ends back inside."""
    lo, hi = SILK_EDGE_KEEP, (placement.BOARD_W - SILK_EDGE_KEEP,
                              placement.BOARD_H - SILK_EDGE_KEEP)
    def clamp(p):
        return pcbnew.VECTOR2I(
            min(max(p.x, pcbnew.FromMM(lo)), pcbnew.FromMM(hi[0])),
            min(max(p.y, pcbnew.FromMM(lo)), pcbnew.FromMM(hi[1])))
    n = 0
    for fp in board.GetFootprints():
        for it in list(fp.GraphicalItems()):
            if it.GetLayer() != pcbnew.F_SilkS or not isinstance(it, pcbnew.PCB_SHAPE) \
                    or it.GetShape() != pcbnew.SHAPE_T_SEGMENT:
                continue
            a, b = clamp(it.GetStart()), clamp(it.GetEnd())
            if (a.x, a.y) == (it.GetStart().x, it.GetStart().y) and \
               (b.x, b.y) == (it.GetEnd().x, it.GetEnd().y):
                continue
            n += 1
            if a == b:
                fp.Remove(it)
            else:
                it.SetStart(a)
                it.SetEnd(b)
    return n


# footprint-native silk text we draw ourselves instead (none on v3 so far)
DROP_FP_TEXT = {}
# footprint-native pin-1 dots that land on a neighbour: J1's sits on U10's pads
DROP_FP_DOT = ("J1",)


def _fields(board):
    """Values off the board, references small and out of everyone's way."""
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for it in list(fp.GraphicalItems()):
            if isinstance(it, pcbnew.PCB_TEXT) and it.GetLayer() == pcbnew.F_SilkS \
                    and it.GetText() in DROP_FP_TEXT.get(ref, ()):
                fp.Remove(it)
            elif ref in DROP_FP_DOT and isinstance(it, pcbnew.PCB_SHAPE) \
                    and it.GetLayer() == pcbnew.F_SilkS and it.GetShape() == pcbnew.SHAPE_T_CIRCLE:
                fp.Remove(it)
        fp.Value().SetVisible(False)
        f = fp.Reference()
        f.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(REF_SIZE), pcbnew.FromMM(REF_SIZE)))
        f.SetTextThickness(pcbnew.FromMM(REF_THICK))
        if ref in REF_HIDE:
            f.SetVisible(False)
        elif ref in REF_AT:
            f.SetTextAngleDegrees(0)
            f.SetPosition(MM(*REF_AT[ref]))


def _fill(board):
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def build(path):
    # Every footprint, track and zone gets a fresh KIID, and the board file lists
    # them in KIID order: with random ones two builds of the same board differ
    # in item order. Seeded, they come out the same every time.
    pcbnew.KIID.SeedGenerator(3)
    board = pcbnew.BOARD()
    board.SetFileName(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(6)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    # gerbers / pick-and-place are exported relative to the bottom-left corner
    ds.SetAuxOrigin(MM(0.0, placement.BOARD_H))
    _outline(board)
    _holes(board)
    nets = _nets(board)
    _footprints(board, nets)
    _thin_j1_pads(board)
    _zones(board, nets)
    _stub_tracks(board, nets)
    _fixed_vias(board, nets)
    stitched = power_stitch(board)
    ties, missed = _ties(board, nets)
    _silk(board)
    _fields(board)
    _clip_silk(board)
    _fill(board)
    print("stitched: " + ", ".join(f"{k} {len(v)}" for k, v in stitched.items()))
    print(f"{len(ties)} pads tied to their inner plane"
          + (f", no room for a tie at {missed}" if missed else ""))
    # aSkipSettings=True: a plain SaveBoard() also rewrites the .kicad_pro from the
    # board's empty in-memory project and drops the schematic's sheet list
    pcbnew.SaveBoard(path, board, True)
    write_stackup(path)
    write_project_netclasses()
    write_design_rules()


if __name__ == "__main__":
    build(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb"))
