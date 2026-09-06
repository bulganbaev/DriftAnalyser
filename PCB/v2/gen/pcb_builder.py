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
        "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5,
                  "min_via_annular_width": 0.15, "min_through_hole_diameter": 0.3,
                  "min_copper_edge_clearance": 0.3,
                  "solder_mask_clearance": 0.0, "solder_mask_min_width": 0.0},
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
        assert fp is not None, "MountingHole_3.2mm_M3"
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
        assert fp is not None, f"{p.ref}: {p.footprint}"
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        if p.lcsc and hasattr(fp, "SetField"):
            fp.SetField("LCSC", p.lcsc)
            f = fp.GetField("LCSC")         # lands visible on F.SilkS otherwise
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
    _footprints(board, _nets(board))
    # aSkipSettings=True: a plain SaveBoard() also rewrites the .kicad_pro from the
    # board's empty in-memory project and drops the schematic's sheet list
    pcbnew.SaveBoard(path, board, True)
    write_project_netclasses()


if __name__ == "__main__":
    build(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb"))
