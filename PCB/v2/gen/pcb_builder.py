"""Build driftanalyser-v2.kicad_pcb from the model + the placement table.

Needs pcbnew, so run it with KiCad's python:
    KICAD_PY -m gen.pcb_builder        (cwd = PCB/v2)
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pcbnew
from pcbnew import VECTOR2I_MM as MM

from gen import env, libs, model, placement

EDGE_W = pcbnew.FromMM(0.1)

# F.Cu / In1.Cu (solid GND) / In2.Cu (VBAT + 12V_LED + GND) / B.Cu, in stack order.
# pcbnew numbers them 0, 4, 6, 2 - never assume the ids are ordered.
CU = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
INNER = (pcbnew.In1_Cu, pcbnew.In2_Cu)


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
        # JLCPCB 4 layer, 1 oz outer / 0.5 oz inner capability, not the KiCad
        # defaults. 0.15 mm clearance is above that process' floor (0.127 mm); it
        # is only U5's LGA-14 land pattern that ever needs to go that low.
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
            # 0.5 mm at 1 oz is ~1.7 A: the 5 V and 3V3 rails carry under 1 A and
            # BUCK_SW is 3 mm long. 1 mm was unroutable - the autorouter could not
            # get it into a 0.5 mm pad pitch and gave up on 22 connections.
            _netclass("Power", 0.25, 0.5, 0.8, 0.4),
            # only the pre-routed stubs are drawn at this width; the pours carry
            # the current, so the number is a statement of intent for hand edits
            _netclass("Bus12V", 0.4, 3.0, 1.0, 0.5),
        ],
        "meta": {"version": 4},
        "netclass_patterns": [
            {"netclass": "Bus12V", "pattern": "VBAT"},
            {"netclass": "Bus12V", "pattern": "12V_LED"},
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
# gaps: U5 (LGA-14) 0.15 mm, J2 (USB-C) and U2 (TSDSO-14) 0.20, U7 0.25, U3 0.35 -
# all of them clear JLCPCB's 4 layer 1 oz floor (0.127 mm), none of them clear the
# 0.25 mm we ask of our own copper. Both rules are scoped to pads of one footprint,
# so the netclass clearance still governs everything we draw.
(rule "same footprint pad spacing"
\t(constraint clearance (min 0.2mm))
\t(condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Reference == B.Reference"))

(rule "U5 LGA-14 land pattern"
\t(constraint clearance (min 0.15mm))
\t(condition "A.Type == 'Pad' && B.Type == 'Pad' && A.memberOfFootprint('U5') && B.memberOfFootprint('U5')"))

# Getting a trace out of a 0.5 mm pitch land pattern costs the netclass margin:
# 0.35 mm pads leave 0.15 mm between them, so a 0.2 mm escape out of one pad runs
# 0.225 mm from the next. That is well clear of the fab's floor (0.127 mm), it is
# just below the 0.25 mm we ask of ourselves everywhere else, and it is scoped to
# U5's own pads - the autorouter never sees it, it routes to the netclass.
(rule "U5 LGA-14 escapes"
	(constraint clearance (min 0.2mm))
	(condition "A.Type == 'Pad' && A.memberOfFootprint('U5') && B.Type == 'Track'"))

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


# JLCPCB's 4 layer 1.6 mm stack (JLC04161H-7628) with the **1 oz inner copper**
# option: 1 oz on all four layers, one 7628 prepreg either side of a 1.065 mm
# core. The inner weight is the whole reason the VBAT plane can carry the strip
# current - see the report; at the stock 0.5 oz it is half of everything below.
# pcbnew does not wrap BOARD_STACKUP usefully, so this goes into the saved file
# as text - without it KiCad spreads the 1.6 mm evenly and the fab has to guess.
STACKUP = """	(stackup
		(layer "F.SilkS" (type "Top Silk Screen"))
		(layer "F.Paste" (type "Top Solder Paste"))
		(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
		(layer "F.Cu" (type "copper") (thickness 0.035))
		(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
		(layer "In1.Cu" (type "copper") (thickness 0.035))
		(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
		(layer "In2.Cu" (type "copper") (thickness 0.035))
		(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "7628") (epsilon_r 4.4) (loss_tangent 0.02))
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


def _holes(board):
    libdir = os.path.join(env.FOOTPRINT_DIR, "MountingHole.pretty")
    for i, (x, y) in enumerate(placement.HOLES, 1):
        fp = pcbnew.FootprintLoad(libdir, "MountingHole_3.2mm_M3")
        if fp is None:
            raise RuntimeError(f"MountingHole_3.2mm_M3 not found in {libdir}")
        fp.SetReference(f"H{i}")
        fp.SetValue("M3")
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
# USB shield's legs and the two debug headers' ground pins sit where routed traces
# leave the plane in shreds, and a spoke into a shred is a starved thermal relief;
# all three are 2.54 mm-class pins that still solder by hand off a solid pour.
SOLID_TO_ZONE = {("J2", "SH"), ("J3", "2"), ("J4", "2"),
                 # and the XT60's ground pin: it is the return of the whole 20 A
                 # the board can draw, so it takes the plane solid. Four thermal
                 # spokes into a 2.7 mm barrel is both a starved relief here and
                 # the wrong thing electrically.
                 ("J1", "1")}


def _footprints(board, nets):
    for p in model.PARTS:
        libdir, name = libs.footprint_path(p.footprint)
        fp = pcbnew.FootprintLoad(libdir, name)
        if fp is None:
            raise RuntimeError(f"{p.ref}: footprint {p.footprint} not found in {libdir}")
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        if p.lcsc and hasattr(fp, "SetField") and hasattr(fp, "GetField"):
            fp.SetField("LCSC", p.lcsc)
            f = fp.GetField("LCSC")         # lands visible on F.SilkS otherwise
            if f is not None:
                f.SetLayer(pcbnew.F_Fab)
                f.SetVisible(False)
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


# The board is built without the project loaded, so the fill cannot see the
# netclasses: give every zone the widest netclass clearance (Bus12V, 0.4) as a
# local override, otherwise DRC re-checks the fill against 0.4 and fails.
GND_CLEAR = 0.4
BUS_CLEAR = 0.4

# In2.Cu extents. The 12V slab stops at IN2_BUS_BOT, clear of the LED series
# resistor row at y = 14; its arm reaches IN2_ARM_BOT, 0.4 past the last via of
# the F.Cu arm and 1.9 short of the VBAT riser. The VBAT corridor is 13 mm tall
# and runs under the 3V3 block and the microSD resistor column - both all SMD, so
# it only pays for the signal vias the router drops through it.
IN2_BUS_BOT, IN2_ARM_BOT = 12.0, 22.3
# The stretch of the 12V run between J15 and the arm carries five of the six
# branches through the thinnest part of the F.Cu comb (the 3.75 mm band, with no
# tooth to widen it), so In2 goes deep there instead.
IN2_BUS_DEEP = (75.5, 0.5, 88.0, 22.3)

# The VBAT plane. In2 carries the whole XT60 -> U2 path and nothing routes on it,
# so it is as large as the board allows: the entire lower band, starting at
# IN2_VBAT_TOP east of the ESP32 module's pin row and dropping to x = 15 once the
# module is out of the way at IN2_VBAT_WEST_Y. GND keeps the top half of In2,
# which is what the module and the IMU sit over. The riser to U2's tab is 20 mm
# wide now, not 12.
IN2_VBAT_TOP, IN2_VBAT_BOT = 34.6, 74.5
# 10.5 (not 15) so the plane covers the whole of J1 pad 2, the VBAT barrel:
# the XT60's positive contact is its pad 2, 7.2 mm west of pad 1
IN2_VBAT_WEST_X, IN2_VBAT_WEST_Y = 10.5, 44.0
IN2_VBAT_EAST_X = 22.0
# The riser is the whole path's bottleneck: current turns north here and every
# horizontal cut of it has to carry the full 20 A. 62 mm, not the 74 it started
# at - In1 is solid ground underneath, so the only thing the extra 12 mm costs is
# In2 ground, and In2 ground is a bonus layer, not the reference.
IN2_RISER_X = 60.0
# nothing new drills through the riser: a 0.8 mm ground tie there is 1.6 mm off
# every transverse cut
RISER_BOX = (IN2_RISER_X, 24.2, 100.0, 37.5)
IN2_J6_X, IN2_J6_Y = 82.0, 67.5

# The same rail on F.Cu, at a lower priority than the pad-level pours so those
# keep their shape: a band across the middle of the lower half that stops short
# of the ESP32 / the boot buttons on the west and of the USB and OBD connector
# row on the south, where hand-soldered ground matters more than copper.
F_SPREAD = [(46.0, 43.0, 100.0, 62.0),
            # and the bridge over the riser: the tab pour stops at y = 30.02 and
            # the band above starts at 43, so without this the riser is In2 only
            # exactly where it is narrowest
            (74.0, 29.8, 100.0, 43.5)]
# how far that pour keeps away from a ground pad that has no tie via: such a pad
# reaches ground only through the top pour, so pouring VBAT around it strands it
# on its own fringe - measured, four of them
SPREAD_KEEP = 1.2


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


def _pads_box(board, pads):
    boxes = [_pad_box(board, ref, num) for ref, num in pads]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _fp_pads_box(board, refs):
    """Box around every pad of these footprints - FindPadByNumber only ever answers
    the first of a repeated pad number, and the tactile switches have two of each."""
    boxes = []
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            raise KeyError(f"no footprint {ref}")
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            boxes.append(tuple(pcbnew.ToMM(v) for v in
                               (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())))
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _outline_pts(zone, pts):
    o = zone.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))


def _zone(board, net, layer, pts, priority=0, clearance=GND_CLEAR, min_w=0.25,
          connection=pcbnew.ZONE_CONNECTION_THT_THERMAL):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(pcbnew.FromMM(clearance))
    z.SetMinThickness(pcbnew.FromMM(min_w))
    # default (GND): solid on SMD pads, thermal relief on the through-hole connectors
    # so they can still be soldered by hand. The power pours pass FULL instead - a
    # thermal relief in the middle of a 10 A path is a fuse.
    z.SetPadConnection(connection)
    z.SetIsRuleArea(False)
    _outline_pts(z, pts)
    board.Add(z)
    return z


def _union(rects):
    """One outline around a set of axis-aligned boxes, in mm."""
    poly = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in rects:
        part = pcbnew.SHAPE_POLY_SET()
        part.NewOutline()
        for x, y in _rect(x0, y0, x1, y1):
            part.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        poly.BooleanAdd(part)
    poly.Simplify()
    if poly.OutlineCount() != 1:
        raise ValueError(f"{rects} do not make one connected region")
    o = poly.Outline(0)
    return [(pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y))
            for k in range(o.PointCount())]


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


def _zones(board, nets):
    """Power copper. Every polygon is derived from where the pads actually landed."""
    W, H = placement.BOARD_W, placement.BOARD_H

    # ---- nothing metallic under the ESP32 antenna, on either layer. U1's own
    # footprint carries the same keep-out; this is the board's statement of it,
    # clipped to the board (the module hangs over the left edge).
    ax0, ay0, ax1, ay1 = placement.ANTENNA_KEEPOUT
    _rule_area(board, _rect(max(ax0, 0.0), ay0, ax1, ay1))

    # ---- GND over the whole board on every layer, lowest priority: everything
    # else cuts into it. In1.Cu is the point of the four layer stack - nothing
    # else is ever poured there, so it stays a solid reference under every signal
    # on F.Cu and the return path for the strip connectors' pin 3.
    full = _rect(0.5, 0.5, W - 0.5, H - 0.5)
    for layer in CU:
        _zone(board, nets["GND"], layer, full, priority=0)

    # ---- 12V_LED, a comb rather than a band across the connector row: a run along
    # the top edge
    # with a tooth down over each pin 1. The lanes between the teeth are what lets
    # the GND plane reach pin 3 (the strip return current) and the data lines reach
    # pin 2 - a solid band would strand all twelve of those pads inside 12V copper.
    pin1 = [_pad_box(board, f"J1{i}", "1") for i in range(1, 7)]
    band_bot = min(b[1] for b in pin1) - 0.4
    tooth_bot = max(b[3] for b in pin1) + 0.4
    ox0, _, ox1, oy1 = _pads_box(board, [("U2", n) for n in ("8", "9", "10", "12", "13", "14")])
    teeth = []
    for k, pb in enumerate(pin1):
        cx = (pb[0] + pb[2]) / 2             # left stops 0.4+ short of the previous pin 3,
        t = (cx - 4.0, cx + 2.15)            # right 0.4+ short of this connector's pin 2
        teeth.append(t + ((oy1,) if k == len(pin1) - 1 else (tooth_bot,)))
    # J16's tooth is also the arm down to U2's OUT pads (U2 is rotated 90, OUT up)
    teeth[-1] = (min(teeth[-1][0], ox0 - 0.8), max(teeth[-1][1], ox1 + 0.15), oy1)
    bx0, bx1 = teeth[0][0] - 1.5, teeth[-1][1] + 1.0
    bus = [(bx0, 0.5), (bx1, 0.5), (bx1, band_bot)]
    for tx0, tx1, tb in reversed(teeth):
        bus += [(tx1, band_bot), (tx1, tb), (tx0, tb), (tx0, band_bot)]
    bus.append((bx0, band_bot))
    _zone(board, nets["12V_LED"], pcbnew.F_Cu, bus, priority=3, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)
    bus_geo = (bx0, bx1, band_bot)

    # ---- 12V_LED on In2.Cu, in parallel with the comb above it. There are no
    # pads down here, only barrels, so it is a plain slab: it runs past the
    # connector row (pin 1 is a through hole on this net, so the slab bonds to
    # all six of them; pins 2 and 3 only cost an anti-pad) and sends the same arm
    # down to U2, where the twelve vias of the arm tie the two layers together.
    _zone(board, nets["12V_LED"], pcbnew.In2_Cu,
          _union([(bx0, 0.5, bx1, IN2_BUS_BOT), IN2_BUS_DEEP,
                  (teeth[-1][0], 0.5, teeth[-1][1], IN2_ARM_BOT)]),
          priority=3, clearance=BUS_CLEAR, connection=pcbnew.ZONE_CONNECTION_FULL)

    # ---- VBAT input copper on F.Cu: the input barrel, the TVS, the bulk caps
    # and the buck input caps. It starts 0.5 mm west of J1 pin 2 - the XT60's
    # positive contact, see the note on J1 in the model - so the barrel pours
    # into the top layer as well as into the In2 plane; on In2 alone the first
    # 6 mm east of it was a 29 mm cut of one layer, 18.7 A, under the 20 the
    # switch is rated for. Pin 1, the ground barrel, is 7.2 mm east of it inside
    # this pour and keeps the filler's clearance ring.
    # The notch keeps the R7 / R8 / C8 sense divider out of it.
    vx0, _, _, _ = _pad_box(board, "J1", "2")
    d1_top = _pad_box(board, "D1", "1")[1]
    col_x = _pad_box(board, "R7", "1")[0] - 0.6
    mid_y = _pad_box(board, "C8", "1")[3] + 0.5
    c34 = _pads_box(board, [("C3", "1"), ("C4", "1")])
    c2_bot = _pad_box(board, "C2", "1")[3]
    sw = _fp_pads_box(board, ("SW1", "SW2"))
    sw_x, sw_y = sw[2] + 0.75, sw[3] + 0.4      # the boot / reset buttons sit in the way
    # C1 / C2 are SMD cans: their GND pads only exist on F.Cu, so the pour has to leave
    # them a lane to the ground plane instead of burying them (a 30 A bulk cap return)
    c1_gnd = _pad_box(board, "C1", "2")
    gnd_x, gnd_y = c1_gnd[0] - 0.45, c1_gnd[1] - 0.4
    # The lobe that reaches C3 stops above C4's ground pad: only 0.45 mm of copper fits
    # between C1's and C4's GND pads, and burying either of those two SMD ground pads
    # costs more than the short VBAT track C4 needs instead.
    lobe_r = c34[2] + 0.4                       # C3's GND pad grounds through this edge
    lobe_b = _pad_box(board, "C4", "2")[1] - 0.4
    left, top, bot = vx0 - 0.5, d1_top - 0.4, c2_bot + 0.4
    vbat_f = [(sw_x, top), (col_x, top), (col_x, mid_y),
              (lobe_r, mid_y), (lobe_r, lobe_b), (col_x, lobe_b),
              (col_x, gnd_y), (gnd_x, gnd_y), (gnd_x, bot),
              (left, bot), (left, sw_y), (sw_x, sw_y)]
    _zone(board, nets["VBAT"], pcbnew.F_Cu, vbat_f, priority=2, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)

    # ---- VBAT copper around U2's tab on F.Cu: an L that clears the OUT row above
    # and the control row below, widening to the right of U2 for the stitching vias
    ctl = _pads_box(board, [("U2", n) for n in "1234567"])
    r5_top = _pad_box(board, "R5", "1")[1]
    c5_right = _pad_box(board, "C5", "1")[2]
    tab_left, tab_right = c5_right + 0.45, ox1 + 3.8   # 0.4+ clear of C5's and C6's pads
    bar_top, bar_bot = oy1 + 0.45, ctl[1] - 0.5        # between U2's OUT and control rows
    leg_l, leg_r = ctl[0] - 0.425, ctl[2] + 0.45       # legs skirt the control row
    leg_bot = r5_top - 0.5
    vbat_tab = [(tab_left, bar_top), (tab_right, bar_top), (tab_right, leg_bot),
                (leg_r, leg_bot), (leg_r, bar_bot), (leg_l, bar_bot),
                (leg_l, leg_bot), (tab_left, leg_bot)]
    _zone(board, nets["VBAT"], pcbnew.F_Cu, vbat_tab, priority=2, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)

    # ---- VBAT on In2.Cu: the whole path from the XT60 to U2's tab, and as much
    # of the board around it as there is. Nothing routes on In2, so the only
    # thing this costs is an anti-pad per signal via, and the only thing it buys
    # is cross section - which is what the 20 A the switch is rated for needs.
    # It is the lower band of the board (the buck, the LDO, the CAN and K-line
    # block, the USB corner), which starts east of the ESP32's pin row and drops
    # to the west edge once the module is above it, plus a 20 mm riser up to
    # U2's tab via field. GND keeps the top half of In2, under the module and
    # the IMU. On two layers this was 8 mm of B.Cu split into two bands with a
    # channel between them so signals could cross the board at all.
    corridor = (IN2_VBAT_EAST_X, IN2_VBAT_TOP, IN2_J6_X, IN2_VBAT_BOT)
    west = (IN2_VBAT_WEST_X, IN2_VBAT_WEST_Y, IN2_VBAT_EAST_X + 1.0, IN2_VBAT_BOT)
    # the OBD connector's pin row is the one thing in the lower band that has to
    # keep its ground: J6 pin 4 lost a thermal spoke on In2 with VBAT around it
    east = (IN2_J6_X, IN2_VBAT_TOP, tab_right, IN2_J6_Y)
    riser = (IN2_RISER_X, oy1 + 0.4, tab_right, IN2_VBAT_TOP)
    _zone(board, nets["VBAT"], pcbnew.In2_Cu, _union([west, corridor, east, riser]),
          priority=2, clearance=BUS_CLEAR, connection=pcbnew.ZONE_CONNECTION_FULL)
    return {"bus": bus_geo, "arm": (ox0, ox1, oy1),
            "tab": (tab_left, tab_right, leg_l, leg_r, bar_top, leg_bot),
            "cap_gnd": (gnd_x, col_x, c1_gnd[3], _pad_box(board, "C2", "2")[1])}


def _via(board, net, x, y, d=0.8, drill=0.4):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(MM(x, y))
    v.SetWidth(pcbnew.FromMM(d))
    v.SetDrill(pcbnew.FromMM(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)


def _stitch(board, nets, geo):
    ox0, ox1, oy1 = geo["arm"]
    # VBAT: a leg of vias either side of U2's control row, never under the tab itself
    # (no via in pad, JLC assembles this board). 24 x 0.8/0.4 ~= 40 A.
    tab_left, tab_right, leg_l, leg_r, bar_top, leg_bot = geo["tab"]
    cols = [leg_l - 0.6 - 1.2 * k for k in range(3)]
    cols += [leg_r + 0.575 + 1.15 * k for k in range(3)]
    for x in cols:
        for k in range(4):
            _via(board, nets["VBAT"], x, bar_top + 0.6 + 1.5 * k)
    # VBAT: F.Cu <-> In2 under the XT60, between the TVS and the bulk caps. The
    # XT60's own barrel is worth about five of these; the pour above them is the
    # 30 A input. They sit in the pour, west of J1's ground barrel and east of
    # it: the field is protected wiring in the session, so it has to stay where
    # the session recorded it.
    for x in [19.5 + 2.0 * i for i in range(8)]:
        for y in (51.0, 53.0, 54.8):
            _via(board, nets["VBAT"], x, y)
    # 12V_LED: F.Cu <-> the In2 slab along the run at the top edge
    bx0, bx1, band_bot = geo["bus"]
    x = bx0 + 1.5
    while x < bx1 - 1.5:
        _via(board, nets["12V_LED"], x, band_bot - 1.85)
        x += 6.0
    # and down the arm: above the R36 / D16 row at y = 14, then below it
    for vx in (ox0 + 0.5, (ox0 + ox1) / 2, ox1 - 0.5):
        for vy in (10.5, 16.5, 19.0, 21.5):
            _via(board, nets["12V_LED"], vx, vy)
    # GND: right under each strip connector's pin 3, where the return current is
    for i in range(1, 7):
        pin3 = _pad_box(board, f"J1{i}", "3")
        _via(board, nets["GND"], (pin3[0] + pin3[2]) / 2, pin3[3] + 2.15)
    # GND: in the lane the VBAT pour leaves open for C1 / C2's SMD ground pads, so
    # the bulk cap return reaches the In1 plane too
    gnd_x, gnd_r, c1_bot, c2_top = geo["cap_gnd"]
    for x in (gnd_x + 1.5, gnd_x + 4.0):
        for y in (c1_bot + 2.25, c1_bot + 5.25):
            _via(board, nets["GND"], x, y)
    for x, y in ((44.0, 24.0), (40.0, 30.0), (52.0, 38.0), (70.0, 20.0),
                 (75.0, 30.0), (8.0, 65.0), (105.0, 60.0)):
        _via(board, nets["GND"], x, y)


# Short runs drawn by hand where the autorouter cannot help itself: power pads the
# pours do not reach (a foreign pad in the way, or the wrong side of the board),
# and the escapes out of U5's land pattern. Widths are what each gap allows with
# 0.4 mm (Bus12V) / 0.25 mm (Power) / 0.2 mm (Default) kept to the next pad.
# Drawn before the fill so the pours flow around them, and exported to Freerouting
# as protected wiring so it routes up to them instead of over them.
STUBS = [
    # net, width, points
    # C4's ground pad blocks the way up to the pour, so C4 goes right to C9's
    # VBAT pad, C9 up to U3's VIN pad, and U3 west into the pour lobe
    ("VBAT", 1.0, [(42.0, 61.6), (45.3, 61.6)]),
    ("VBAT", 0.9, [(45.8, 60.5), (45.8, 58.2)]),
    ("VBAT", 0.6, [(46.3, 58.05), (44.5, 58.05), (43.7, 57.6)]),
    # R7 (the VBAT_SENSE divider) sits 0.6 mm right of the pour's edge column
    ("VBAT", 0.8, [(41.175, 45.0), (40.0, 45.0)]),
    # R9 (the buck enable divider) is below the pour: out under C2's ground pad
    # and up into C2's own VBAT pad (the pour's corner there is 0.4 from that pad)
    ("VBAT", 0.8, [(41.175, 70.0), (40.6, 70.6), (31.5, 70.6), (31.0, 69.5)]),
    # the K-line transceiver's battery branch: JP2 / U9 / C25 are 10 mm past the
    # end of every VBAT pour on F.Cu, so they drop to the In2 corridor
    ("VBAT", 0.6, [(86.5, 64.0), (85.5, 62.5), (85.5, 51.0)]),
    ("VBAT", 0.6, [(82.475, 59.365), (84.0, 59.365), (85.5, 58.0)]),
    ("VBAT", 0.5, [(79.225, 55.0), (79.225, 51.4)]),
    # the two 12V decoupling caps at the switch: C5 reaches the bus arm directly,
    # C6 has to skirt the top edge of U2's VBAT tab to get to the OUT pads
    ("12V_LED", 0.5, [(86.0, 25.475), (87.9, 23.6)]),
    # C6: the lane between U2's OUT pads and the tab's via field is 0.75 mm wide,
    # so C6 goes the long way round - right of its own ground pad, over the top of
    # the via field, and back into the 12V arm
    ("12V_LED", 0.5, [(102.0, 25.475), (104.1, 24.6), (104.1, 20.8),
                      (96.9, 20.8), (96.2, 21.4)]),
    # U7 pin 19: 0.25 mm of pad pitch either side, the plane cannot get in
    ("GND", 0.3, [(56.3, 19.725), (57.4, 19.725)]),
    # D1's ground pad sits inside the VBAT pour with the VBAT run underneath it,
    # so it has neither plane to fall back on: out of the pour to the north, into
    # the ground above it, and down to the back plane through the via below
    ("GND", 0.5, [(35.4, 46.0), (35.4, 43.0)]),
    # U2's control row is a 0.65 mm pitch of seven pins in a 1 mm pocket: the
    # VBAT tab bar closes it to the north, the tab's two legs to west and east,
    # and R1 / R2 / R5 to the south. Two of those pins have to be drawn by hand
    # or nothing else fits.
    # Pin 1 is ground. It used to drop into a via 0.75 mm below the pad, which
    # put an 0.8 mm barrel in the middle of the pocket and left pin 2 with no way
    # out at all - in four draws of the router LED_PWR_EN never once connected.
    # It now runs south past R1 and takes its via in the lane between the pad
    # row and R2 - as far north as it will go, because anything in y 30..37 is a
    # 1.6 mm bite out of the VBAT riser's cross section.
    ("GND", 0.3, [(92.05, 29.3), (92.05, 30.7)]),
    # Pin 2 is the enable, and its pull-down R1 is 4.5 mm west, on the far side of
    # that ground run. There is no path on F.Cu, so it drops to B.Cu right here:
    # 0.75 mm of track into the lane between the pad row and R2, and a via. The
    # gap it sits in is 1.02 mm tall and the via wants 1.0 of it.
    ("LED_PWR_EN", 0.2, [(92.7, 29.2), (92.8, 29.95)]),
    # U7's supply pin has its ground pin 0.25 mm away: every time the router got
    # itself into that gap it broke the clearance, so the decoupling loop to C22
    # is drawn here instead.
    ("5V", 0.3, [(56.3, 19.075), (58.0, 19.075), (58.0, 22.775), (58.9, 22.775)]),
    # U5 is an LGA-14 on a 0.5 mm pitch: the autorouter cannot get a trace out of
    # the land pattern, so every pad that has to leave gets its own escape. 0.2 mm
    # is the board minimum and the only width that keeps 0.2 mm to the next pad.
    # Each escape ends clear of the land pattern, and the ones the router still
    # could not pick up end on a via, so it can take them on the back side.
    # pad 4, west - and then all the way past C20, because stopping beside it is
    # no good: C20's two pads are a 2.45 mm wall on F.Cu with 0.65 mm between
    # them, and in draw after draw the router came east to x = 49.7 and gave up
    # there. The run turns south under C20 and lands in open board.
    ("IMU_INT1", 0.2, [(53.9, 32.8), (52.8, 32.8), (52.8, 34.2), (49.3, 34.2)]),
    # the other end of the same net. U1's pin field is a 1.27 mm pitch row and
    # the router escapes each pin northward across its neighbours' exits; pin 10
    # ends up fenced in by pin 9's, and in six draws in a row IMU_INT1 came back
    # with no copper on it at all. It gets its own way out to the south instead,
    # into the 1.6 mm gap between the module's pins and SW1.
    ("IMU_INT1", 0.2, [(14.17, 42.0), (14.17, 43.3)]),
    ("I2C_SDA", 0.2, [(54.5, 30.9), (54.5, 29.8), (53.6, 29.0)]),  # pad 14, north
    ("I2C_SCL", 0.2, [(55.0, 30.9), (55.0, 29.8), (56.4, 28.4)]),  # pad 13, north
    # 3V3 lands on three pads of U5 on three different sides: the rail round the
    # south-east corner joins them, so the router only has to reach one of them
    ("3V3", 0.2, [(55.5, 30.9), (55.5, 30.0)]),                    # pad 12, north
    ("3V3", 0.25, [(55.5, 30.0), (57.3, 29.5), (57.3, 34.4), (54.5, 34.4)]),
    ("3V3", 0.2, [(54.5, 33.1), (54.5, 34.4)]),                    # pad 5, south
    ("3V3", 0.2, [(56.3, 32.75), (57.3, 32.75)]),                  # pad 8, east
    # and on to C21, the IMU's other decoupling cap: 1.7 mm of empty board that
    # the router kept leaving open because everything else around U5 got there
    # first
    ("3V3", 0.25, [(57.3, 32.75), (59.2, 32.75)]),
]

# vias that take a stub to the copper on the other side. The GND one is the way
# out of the pocket C6's detour fences off: C6's ground pad and the strip of plane
# around it would otherwise be an island the rest of the board never reaches.
STUB_VIAS = [("VBAT", 85.5, 51.0), ("VBAT", 79.225, 51.4), ("GND", 101.5, 23.9),
             ("GND", 35.4, 43.0),
             ("GND", 92.05, 30.7), ("LED_PWR_EN", 92.8, 29.95),
             ("IMU_INT1", 49.3, 34.2), ("IMU_INT1", 14.17, 43.3),
             ("I2C_SDA", 53.6, 29.0),
             ("I2C_SCL", 56.4, 28.4)]


def _track(board, net, layer, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetLayer(layer)
    t.SetStart(MM(*a))
    t.SetEnd(MM(*b))
    t.SetWidth(pcbnew.FromMM(width))
    t.SetNet(net)
    board.Add(t)


def _stub_tracks(board, nets):
    for name, width, pts in STUBS:
        for a, b in zip(pts, pts[1:]):
            _track(board, nets[name], pcbnew.F_Cu, a, b, width)
    for name, x, y in STUB_VIAS:
        big = name in ("GND", "VBAT", "12V_LED")
        _via(board, nets[name], x, y, *(0.8, 0.4) if big else (0.6, 0.3))


# a 0.6/0.3 via, its clearance, and how far a ground pad's own tie may sit from
# another ground via before it counts as already tied down
TIE_D, TIE_DRILL, TIE_CLEAR, TIE_NEAR = 0.6, 0.3, 0.3, 1.6


def _gnd_ties(board, nets):
    """A via down to the In1 plane beside every ground pad that lives only on F.Cu.

    This is the thing four layers buy. On two layers the back side was VBAT
    copper exactly where it was needed, and eighteen ground pads ended up
    stranded on islands the routed traces cut out of the top pour, with nowhere
    to stitch them to. Here In1.Cu is solid ground under the whole board, so each
    of these pads gets its own via before routing, and the autorouter has to plan
    around it instead of fencing the pad in.

    A tie is skipped where one is not needed (the pad already has a ground via or
    a through hole within TIE_NEAR) or where none fits: no spot outside the pad
    that clears every other pad and every existing track by TIE_CLEAR, stays
    0.5 mm inside the board, keeps out of the antenna box, and does not land in
    the VBAT or 12V_LED pours, whose copper is worth more than the tie."""
    r = TIE_D / 2
    reach = pcbnew.FromMM(r + TIE_CLEAR)
    ax0, ay0, ax1, ay1 = placement.ANTENNA_KEEPOUT
    # only the F.Cu pours: a tie via inside one of those eats pad-level power
    # copper, but inside an In2 plane it is one anti-pad in 1500 mm2
    power = [z for z in board.Zones()
             if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.F_Cu)
             and z.GetNetname() in ("VBAT", "12V_LED")]
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    ties = []

    rx0, ry0, rx1, ry1 = RISER_BOX

    def free(x, y):
        if not (0.5 + r <= x <= placement.BOARD_W - 0.5 - r
                and 0.5 + r <= y <= placement.BOARD_H - 0.5 - r):
            return False
        if rx0 - r <= x <= rx1 + r and ry0 - r <= y <= ry1 + r:
            return False
        if ax0 - 1.0 <= x <= ax1 + 1.0 and ay0 - 1.0 <= y <= ay1 + 1.0:
            return False
        p = MM(x, y)
        if any(pad.HitTest(p, reach) for pad in pads):
            return False
        if any(t.HitTest(p, reach) for t in board.Tracks()):
            return False
        return not any(z.Outline().Collide(p, reach) for z in power)

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if (pad.GetNetname() != "GND" or not pad.IsOnLayer(pcbnew.F_Cu)
                    or pad.IsOnLayer(pcbnew.B_Cu)):
                continue
            c = pad.GetPosition()
            cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            near = pcbnew.FromMM(TIE_NEAR)
            if any(t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
                   and abs(t.GetPosition().x - c.x) < near
                   and abs(t.GetPosition().y - c.y) < near
                   for t in board.Tracks()):
                continue
            bb = pad.GetBoundingBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in
                              (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            d = r + TIE_CLEAR
            spot = next((s for s in ((cx, y1 + d), (cx, y0 - d), (x1 + d, cy),
                                     (x0 - d, cy), (x1 + d, y1 + d), (x0 - d, y1 + d),
                                     (x1 + d, y0 - d), (x0 - d, y0 - d))
                         if free(*s)), None)
            if spot is None:
                continue
            _via(board, nets["GND"], spot[0], spot[1], TIE_D, TIE_DRILL)
            ties.append((fp.GetReference() + "." + pad.GetNumber(), spot))
    return ties


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


def _poly(rects):
    """A SHAPE_POLY_SET over a list of boxes in mm."""
    poly = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1 in rects:
        part = pcbnew.SHAPE_POLY_SET()
        part.NewOutline()
        for x, y in _rect(x0, y0, x1, y1):
            part.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        poly.BooleanAdd(part)
    return poly


def _loose_gnd_pads(board):
    """Bounding boxes of the F.Cu-only ground pads that did not get a tie via.
    Their only route to ground is the top pour, so nothing else may pour over
    them."""
    vias = [v.GetPosition() for v in board.Tracks()
            if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"]
    near = pcbnew.FromMM(TIE_NEAR)
    out = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if (pad.GetNetname() != "GND" or not pad.IsOnLayer(pcbnew.F_Cu)
                    or pad.IsOnLayer(pcbnew.B_Cu)):
                continue
            c = pad.GetPosition()
            if any(abs(v.x - c.x) < near and abs(v.y - c.y) < near for v in vias):
                continue
            bb = pad.GetBoundingBox()
            out.append(tuple(pcbnew.ToMM(v) for v in
                             (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())))
    return out


def _vbat_spread(board, nets):
    """A second VBAT pour on F.Cu, under the two pad-level ones.

    In2 is where the current goes, but F.Cu is 1 oz too and most of the band
    between the input block and U2's tab is ground pour that nothing needs. This
    zone takes whatever of it is free; priority 1 keeps it under the pad-level
    pours (priority 2) so those still decide the shape around the pads, and over
    the ground pour (priority 0). It stops short of the ESP32 and the boot
    buttons and the C3 / C4 ground lane on the west, and of the USB / OBD
    connector row on the south, where a
    hand-solderable ground pour is worth more than copper.

    Two things keep it out of the ground pour's way: a 1 mm minimum thickness, so
    it only takes copper where it is actually wide, and a hole punched round
    every ground pad that has no tie via of its own."""
    loose = _loose_gnd_pads(board)
    poly = _poly(F_SPREAD)
    poly.BooleanSubtract(_poly([(x0 - SPREAD_KEEP, y0 - SPREAD_KEEP,
                                 x1 + SPREAD_KEEP, y1 + SPREAD_KEEP)
                                for x0, y0, x1, y1 in loose]))
    poly.Simplify()
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.F_Cu)
    z.SetNet(nets["VBAT"])
    z.SetAssignedPriority(1)
    z.SetLocalClearance(pcbnew.FromMM(BUS_CLEAR))
    z.SetMinThickness(pcbnew.FromMM(1.0))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIsRuleArea(False)
    _poly_outline(z, poly)
    board.Add(z)
    return len(loose)


def vbat_stitch(board, step=1.6):
    """Extra In2 <-> F.Cu vias wherever both layers hold VBAT copper.

    The two pad-level F.Cu pours are the input block and U2's tab, and both sit
    over the In2 plane; every via between them is another parallel path, and the
    grid finds them without anyone having to place them by hand.

    This runs from route.import_ses, *after* the session comes back, not from the
    builder: a through via has to clear the routed copper on B.Cu too, and the
    builder cannot see it. Placed at build time instead, six of these landed on
    top of I2C_SDA's via and track."""
    r = 0.4
    net = board.FindNet("VBAT")
    # VBAT is the Bus12V class: 0.4 mm to anything, plus the barrel radius
    reach = pcbnew.FromMM(r + BUS_CLEAR + 0.05)
    inner = [z for z in board.Zones()
             if not z.GetIsRuleArea() and z.GetNetname() == "VBAT"
             and z.IsOnLayer(pcbnew.In2_Cu)]
    outer = [z for z in board.Zones()
             if not z.GetIsRuleArea() and z.GetNetname() == "VBAT"
             and z.IsOnLayer(pcbnew.F_Cu) and z.GetAssignedPriority() > 1]
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    deep = pcbnew.FromMM(r + 0.45)
    added = []
    def deflated(zone):
        poly = pcbnew.SHAPE_POLY_SET(zone.Outline())
        poly.Deflate(deep, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS,
                     pcbnew.FromMM(0.01))
        return poly

    for z in outer:
        room = deflated(z)
        if room.IsEmpty():
            continue
        deep_inner = [deflated(i) for i in inner]
        bb = room.BBox()
        x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
        x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
        y = y0
        while y <= y1:
            x = x0
            while x <= x1:
                p = MM(x, y)
                if (room.Contains(p) and any(d.Contains(p) for d in deep_inner)
                        and not any(pad.HitTest(p, reach) for pad in pads)
                        and not any(t.HitTest(p, reach) for t in board.Tracks())):
                    _via(board, net, x, y)
                    added.append((round(x, 2), round(y, 2)))
                x += step
            y += step
    return added


# ---------------------------------------------------------------- silkscreen

# how far silk stays from the board outline, and the size every reference gets:
# the stock 1.0 mm references collide with each other all over the dense corners
SILK_EDGE_KEEP = 0.4
REF_SIZE = 0.8
REF_THICK = 0.12

# mounting holes: their references sit off the board edge and say nothing.
# The LED strip row is the one place with no legible spot left: 1.8 mm between
# the connector silk and the resistor row goes to the pin legend, the rest to
# LED1..LED6. R31..R36 / D11..D16 are a repeating pair per strip and are on the
# CPL, so they lose their reference rather than the legend losing its place.
REF_HIDE = (("H1", "H2", "H3", "H4")
            + tuple(f"R{30 + i}" for i in range(1, 7))
            + tuple(f"D{10 + i}" for i in range(1, 7)))

# references the stock offset drops on a neighbour's pad or silk. Absolute mm,
# text unrotated - the free spot was picked off the silk + pad map of the board.
REF_AT = {
    "J1": (6.5, 62.0),          # was off the bottom edge
    "U1": (11.0, 22.0),         # was on SW2 and on the module's own pad row
    "SW1": (4.6, 51.6), "SW2": (27.5, 51.6),   # the row under the buttons says EN / BOOT
    "R22": (58.0, 36.0), "R23": (58.0, 38.5),
    "C9": (46.8, 63.6), "U3": (45.5, 51.0),
    "R3": (54.0, 51.0), "R2": (91.5, 32.6),
    "J4": (35.0, 36.3),
    "R40": (61.5, 65.0), "R14": (61.0, 63.5), "R15": (65.0, 63.5),
}


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
    _text(board, "DriftAnalyser v2", 72.0, 28.0, size=1.5, bold=True)
    _text(board, "2026-09", 72.0, 30.5, size=1.0)

    # ---- LED strip connectors: pin 1 (12V) is the left one of the three
    for i in range(1, 7):
        cx = placement._strip_x(i) + 3.96          # over pin 2, the middle pin
        _text(board, "12V DATA GND", cx, 12.3, size=0.8)
        _text(board, f"LED{i}", cx, 17.0, size=1.4, bold=True)

    # ---- power in. J1 pin 2 is the XT60's positive contact and sits at x 13.8
    # (the connector is rot 180), pin 1 is GND at x 21 - each mark goes over its
    # own hole. The footprint brings its own "+"/"-" pair, on the other pads;
    # _fields() deletes those so there is exactly one of each on the board.
    _text(board, "EN", 10.0, 51.6, size=1.2, bold=True)
    _text(board, "BOOT", 21.5, 51.6, size=1.2, bold=True)
    _text(board, "+", 13.8, 53.7, size=1.3, bold=True)
    _text(board, "12V IN", 17.4, 53.7, size=0.9, bold=True)
    _text(board, "-", 21.0, 53.7, size=1.3, bold=True)

    _text(board, "USB", 57.0, 63.5, size=1.2, bold=True)

    # ---- OBD side: the header names the connector, each pin name stands over
    # its own pin (2.5 mm pitch, so they run up the board rather than across)
    _text(board, "OBD", 95.75, 62.0, size=1.1, bold=True)
    for name, px in zip(("CANH", "CANL", "K", "GND"), (92.0, 94.5, 97.0, 99.5)):
        _text(board, name, px, 65.6, size=0.8, rot=90)
    _text(board, "CAN TERM", 72.6, 58.6, size=0.8, rot=90)
    _text(board, "K PULLUP", 85.1, 58.6, size=0.8, rot=90)

    # ---- debug + expansion headers. The legend runs down the header, pin 1
    # first, and a dot sits beside pin 1; 0.8 mm is the fab's floor for silk, so
    # neither string fits the 1.25 mm gap left of J3 - UART0 goes between them.
    _text(board, "UART0: 3V3 GND TX RX", 32.25, 27.0, size=0.8, rot=-90)
    _dot(board, 26.9, 22.0, d=0.5)
    _text(board, "EXT: 3V3 GND TX2 RX2 SDA SCL", 38.6, 27.5, size=0.8, rot=-90)
    _dot(board, 37.25, 21.0, d=0.5)

    # ---- IMU axes. U5 sits at rot 0, so the sensor's +X points at the board's
    # right edge and +Y at the top edge; the firmware calls +X the car's nose.
    _arrow(board, 46.0, 39.0, 50.5, 39.0)
    _text(board, "X", 51.8, 39.0, size=1.0, bold=True)
    _arrow(board, 46.0, 39.0, 46.0, 34.5)
    _text(board, "Y", 46.0, 33.3, size=1.0, bold=True)
    _text(board, "nose = +X", 48.3, 41.5, size=0.8)


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


# footprint-native silk text we draw ourselves instead: the XT60's "+" / "-" pair
# sits beside the wrong pads for this board's netlist, and two of each on one
# connector is how a board gets wired backwards
DROP_FP_TEXT = {"J1": ("+", "-")}


def _fields(board):
    """Values off the board, references small and out of everyone's way."""
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for it in list(fp.GraphicalItems()):
            if isinstance(it, pcbnew.PCB_TEXT) and it.GetLayer() == pcbnew.F_SilkS \
                    and it.GetText() in DROP_FP_TEXT.get(ref, ()):
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
    board = pcbnew.BOARD()
    board.SetFileName(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    # gerbers / pick-and-place are exported relative to the bottom-left corner
    ds.SetAuxOrigin(MM(0.0, placement.BOARD_H))
    _outline(board)
    _holes(board)
    nets = _nets(board)
    _footprints(board, nets)
    geo = _zones(board, nets)
    _stitch(board, nets, geo)
    _stub_tracks(board, nets)
    ties = _gnd_ties(board, nets)
    kept = _vbat_spread(board, nets)
    _silk(board)
    _fields(board)
    _clip_silk(board)
    _fill(board)
    print(f"{len(ties)} ground pads tied to the In1 plane by their own via, "
          f"{kept} untied ones kept clear of the F.Cu VBAT spread")
    # aSkipSettings=True: a plain SaveBoard() also rewrites the .kicad_pro from the
    # board's empty in-memory project and drops the schematic's sheet list
    pcbnew.SaveBoard(path, board, True)
    write_stackup(path)
    write_project_netclasses()
    write_design_rules()


if __name__ == "__main__":
    build(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb"))
