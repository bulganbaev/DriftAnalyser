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
        # JLCPCB 2 oz capability, not the KiCad defaults
        # 0.13 clearance / 0.2 hole are JLCPCB's 2 layer floor: the fine pitch land
        # patterns (LGA-14, USB-C, TSDSO-14) and the ESP32 module's own thermal vias
        # need them. What we draw ourselves keeps the netclass clearance.
        "rules": {"min_clearance": 0.13, "min_track_width": 0.2, "min_via_diameter": 0.6,
                  "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.2,
                  "min_copper_edge_clearance": 0.3,
                  "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.1},
        "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2,
                     "silk_line_width": 0.15, "silk_text_size_h": 1.0,
                     "silk_text_size_v": 1.0, "silk_text_thickness": 0.15},
    }
    pro["net_settings"] = {
        "classes": [
            _netclass("Default", 0.2, 0.25, 0.6, 0.3),
            _netclass("Power", 0.3, 1.0, 0.8, 0.4),
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

# Pad to pad spacing inside a land pattern (LGA-14, USB-C, TSDSO-14, SOT-23-6) is
# the part maker's, not ours: hold those pairs to the fab floor and keep the
# netclass clearance for the copper we draw - tracks, vias and zones.
(rule "land pattern pad spacing"
	(constraint clearance (min 0.13mm))
	(condition "A.Type == 'Pad' && B.Type == 'Pad'"))
"""


def write_design_rules():
    path = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_dru")
    with open(path, "w") as f:
        f.write(DRU)


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
        board.Add(fp)


# The board is built without the project loaded, so the fill cannot see the
# netclasses: give every zone the widest netclass clearance (Bus12V, 0.4) as a
# local override, otherwise DRC re-checks the fill against 0.4 and fails.
GND_CLEAR = 0.4
BUS_CLEAR = 0.4


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


def _rule_area(board, pts):
    """Keep-out on both copper layers: no pour, no track, no via."""
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
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

    # ---- GND over the whole board, lowest priority: everything else cuts into it
    full = _rect(0.5, 0.5, W - 0.5, H - 0.5)
    _zone(board, nets["GND"], pcbnew.F_Cu, full, priority=0)
    _zone(board, nets["GND"], pcbnew.B_Cu, full, priority=0)

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
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        _zone(board, nets["12V_LED"], layer, bus, priority=2, clearance=BUS_CLEAR,
              connection=pcbnew.ZONE_CONNECTION_FULL)
    bus_geo = (bx0, bx1, band_bot)

    # ---- VBAT input copper on F.Cu: XT60 pin 1, the TVS, the bulk caps and the
    # buck input caps. The notch keeps the R7 / R8 / C8 sense divider out of it.
    vx0, _, _, _ = _pad_box(board, "J1", "1")
    d1_top = _pad_box(board, "D1", "1")[1]
    col_x = _pad_box(board, "R7", "1")[0] - 0.6
    mid_y = _pad_box(board, "C8", "1")[3] + 0.5
    c34 = _pads_box(board, [("C3", "1"), ("C4", "1")])
    c2_bot = _pad_box(board, "C2", "1")[3]
    sw = _fp_pads_box(board, ("SW1", "SW2"))
    sw_x, sw_y = sw[2] + 0.75, sw[3] + 0.4      # the boot / reset buttons sit in the way
    left, top, bot = vx0 - 0.5, d1_top - 0.4, c2_bot + 0.4
    vbat_f = [(sw_x, top), (col_x, top), (col_x, mid_y),
              (c34[2] + 0.4, mid_y), (c34[2] + 0.4, c34[3] + 0.5),
              (col_x, c34[3] + 0.5), (col_x, bot), (left, bot), (left, sw_y), (sw_x, sw_y)]
    _zone(board, nets["VBAT"], pcbnew.F_Cu, vbat_f, priority=1, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)

    # ---- VBAT copper around U2's tab on F.Cu: an L that clears the OUT row above
    # and the control row below, widening to the right of U2 for the stitching vias
    tab_x0 = _pad_box(board, "U2", "15")[0]
    ctl_top = _pads_box(board, [("U2", n) for n in "1234567"])[1]
    r5_top = _pad_box(board, "R5", "1")[1]
    tab_right = ox1 + 3.8                    # stops 0.4+ short of C6's pads
    vbat_tab = [(tab_x0 - 0.5, oy1 + 0.5), (tab_right, oy1 + 0.5),
                (tab_right, r5_top - 0.5), (ox1 + 0.45, r5_top - 0.5),
                (ox1 + 0.45, ctl_top - 0.5), (tab_x0 - 0.5, ctl_top - 0.5)]
    _zone(board, nets["VBAT"], pcbnew.F_Cu, vbat_tab, priority=1, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)

    # ---- VBAT on B.Cu: input block (tied through the XT60 / C1 / C2 through holes
    # and a via field), a corridor across the empty back side, a riser to U2's tab
    c1_right = _pad_box(board, "C1", "1")[2]
    bx_l, bx_r = vx0 - 2.0, c1_right + 2.5       # input block, tied through the XT60 /
    by_t, by_b = top, c2_bot + 0.8               # C1 / C2 through holes and a via field
    cy_t, cy_b = 43.5, 49.5                      # corridor: only SMD parts sit over it
    vbat_b = [(86.0, 18.0), (tab_right, 18.0), (tab_right, cy_b), (bx_r, cy_b),
              (bx_r, by_b), (bx_l, by_b), (bx_l, sw_y), (sw_x, sw_y), (sw_x, by_t),
              (30.0, by_t), (30.0, cy_t), (86.0, cy_t)]
    _zone(board, nets["VBAT"], pcbnew.B_Cu, vbat_b, priority=1, clearance=BUS_CLEAR,
          connection=pcbnew.ZONE_CONNECTION_FULL)
    return {"bus": bus_geo, "arm": (ox0, ox1, oy1)}


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
    # VBAT: next to U2's tab, never under it (no via in pad, JLC assembles this)
    for x in (ox1 + 1.4, ox1 + 2.9):
        for y in (oy1 + 1.1, oy1 + 2.6, oy1 + 4.1, oy1 + 5.6):
            _via(board, nets["VBAT"], x, y)
    # VBAT: F <-> B in the gap between the TVS and the bulk caps
    for x in [19.5 + 2.0 * i for i in range(8)]:
        for y in (51.0, 53.0):
            _via(board, nets["VBAT"], x, y)
    # 12V_LED: F <-> B along the run at the top edge
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
    for x, y in ((30.0, 24.0), (40.0, 30.0), (52.0, 38.0), (70.0, 20.0),
                 (75.0, 30.0), (8.0, 65.0), (105.0, 60.0)):
        _via(board, nets["GND"], x, y)


def _fill(board):
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def build(path):
    board = pcbnew.BOARD()
    board.SetFileName(path)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    # gerbers / pick-and-place are exported relative to the bottom-left corner
    ds.SetAuxOrigin(MM(0.0, placement.BOARD_H))
    _outline(board)
    _holes(board)
    nets = _nets(board)
    _footprints(board, nets)
    geo = _zones(board, nets)
    _stitch(board, nets, geo)
    _fill(board)
    # aSkipSettings=True: a plain SaveBoard() also rewrites the .kicad_pro from the
    # board's empty in-memory project and drops the schematic's sheet list
    pcbnew.SaveBoard(path, board, True)
    write_project_netclasses()
    write_design_rules()


if __name__ == "__main__":
    build(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb"))
