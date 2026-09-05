"""Generate the KiCad schematic (root + one sheet per functional block) from model.py.

Layout is deterministic, not artistic: parts flow left-to-right in model order, each in
its own cell, every pin gets a short wire stub ending in a global label with the net name
and every "NC" pin gets a no-connect marker. Nothing is drawn as a direct wire between two
parts - connectivity lives entirely in the labels, which is what makes the netlist an exact
mirror of model.nets().
"""
import copy
import json
import math
import os
import uuid

from gen import env, libs, model, sexp
from gen.sexp import Str, Sym

# Format tokens copied from the KiCad 10 demo pic_programmer.kicad_sch
# (~/Library/Application Support/kicad/demos/pic_programmer/), which is the newest
# .kicad_sch shipped with this install.
SCH_VERSION = "20260101"
GENERATOR_VERSION = "10.0"

GRID = 2.54
STUB = 5.08         # stub length: 2 grid steps keeps labels clear of small symbol bodies
GAP = 7.62          # free space between neighbouring cells
MARGIN = 12.7       # page border to first cell
TEXT_H = 1.27
CHAR_W = 1.05       # rough advance of the stroke font at size 1.27
LABEL_PAD = 4.0     # global label leader/box around the text

# (name, width, height) - smallest first; the first page the sheet fits on wins.
PAPERS = [("A4", 297.0, 210.0), ("A3", 420.0, 297.0), ("A2", 594.0, 420.0),
          ("A1", 841.0, 594.0), ("A0", 1189.0, 841.0)]

SHEETS = ["power", "mcu", "leds", "comms"]
ROOT_UUID = "0d6f1c2a-0000-4000-8000-000000000001"
SHEET_UUID = {s: f"0d6f1c2a-0000-4000-8000-00000000001{i}" for i, s in enumerate(SHEETS)}
DOC_UUID = {s: f"0d6f1c2a-0000-4000-8000-00000000002{i}" for i, s in enumerate(SHEETS)}

# One power:PWR_FLAG per net here, placed on the power sheet, so ERC sees a driver for
# nets that only have power_in pins on them. Nets that already own a power_out pin
# (3V3 from U4, 12V_LED from U2) must NOT get a flag: two power outputs on one net is
# an ERC error.
FLAG_NETS = ("VBAT", "GND", "5V", "VBUS_USB", "5V_BUCK")


def _u():
    return Str(str(uuid.uuid4()))


def _effects(size=TEXT_H, hide=False, justify=None):
    eff = ["effects", ["font", ["size", size, size]]]
    if justify:
        eff.append(["justify", *[Sym(j) for j in justify]])
    if hide:
        eff.append(["hide", Sym("yes")])
    return eff


def _prop(name, value, x, y, hide=False, justify=None):
    return ["property", Str(name), Str(value), ["at", round(x, 4), round(y, 4), 0],
            *([["hide", Sym("yes")]] if hide else []),
            _effects(hide=False, justify=justify)]


def _snap(v, grid=GRID):
    return round(round(v / grid) * grid, 4)


def _rot(px, py, rot):
    """Symbol space (y up) -> sheet offset (y down), for a symbol placed at angle `rot`."""
    a = math.radians(rot)
    rx = px * math.cos(a) - py * math.sin(a)
    ry = px * math.sin(a) + py * math.cos(a)
    return round(rx, 4), round(-ry, 4)


# stub direction on the sheet, indexed by the pin angle (which points toward the body)
AWAY = {0: (-1.0, 0.0), 180: (1.0, 0.0), 90: (0.0, 1.0), 270: (0.0, -1.0)}
LABEL_ANGLE = {(-1.0, 0.0): 180, (1.0, 0.0): 0, (0.0, 1.0): 270, (0.0, -1.0): 90}
LABEL_JUSTIFY = {180: ("right",), 0: ("left",), 90: ("left",), 270: ("right",)}


def _label_len(net):
    return len(net) * CHAR_W + LABEL_PAD


def _graphic_extent(lib_id):
    """(x0, x1, y0, y1) of the symbol's drawing in symbol space."""
    node = libs.symbol_def(lib_id)
    xs, ys = [], []

    def pt(n, tag):
        p = sexp.find1(n, tag)
        if p:
            xs.append(float(p[1]))
            ys.append(float(p[2]))

    def walk(n):
        tag = n[0] if n and not isinstance(n[0], list) else None
        if tag == "rectangle":
            pt(n, "start")
            pt(n, "end")
        elif tag in ("polyline", "bezier"):
            for p in sexp.find(sexp.find1(n, "pts") or [], "xy"):
                xs.append(float(p[1]))
                ys.append(float(p[2]))
        elif tag == "circle":
            c = sexp.find1(n, "center")
            r = float(sexp.find1(n, "radius")[1])
            xs.extend([float(c[1]) - r, float(c[1]) + r])
            ys.extend([float(c[2]) - r, float(c[2]) + r])
        elif tag == "arc":
            for t in ("start", "mid", "end"):
                pt(n, t)
        elif tag == "pin":
            pt(n, "at")
        else:
            for x in n:
                if isinstance(x, list):
                    walk(x)

    walk(node)
    if not xs:
        return 0.0, 0.0, 0.0, 0.0
    return min(xs), max(xs), min(ys), max(ys)


def _lib_symbol(lib_id):
    """symbol_def(), but with sub-unit names de-prefixed the way a .kicad_sch wants them.

    In a symbol library a unit is "<Name>_1_1"; libs.symbol_def renames it to
    "<Lib:Name>_1_1" so the top-level name and its units stay in sync. Inside a
    schematic's lib_symbols block KiCad writes the parent as "Lib:Name" but the units
    as plain "Name_1_1" - keep the library prefix on the units and eeschema refuses to
    load the file at all ("Failed to load schematic", no line number).
    """
    node = copy.deepcopy(libs.symbol_def(lib_id))
    bare = lib_id.split(":", 1)[1]
    for child in node:
        if isinstance(child, list) and child and child[0] == "symbol":
            child[1] = Str(child[1].replace(lib_id, bare, 1))
    return node


def _pin_geometry(part):
    """[(number, net, end_x, end_y, away)] in sheet coords relative to the symbol origin."""
    out = []
    for num, (px, py, ang, _name, _etype) in libs.symbol_pins(part.symbol).items():
        ex, ey = _rot(px, py, part.rot)
        away = AWAY[int((ang + part.rot) % 360)]
        out.append((num, part.pins[num], ex, ey, away))
    return out


def _extents(part):
    """(lo_x, hi_x, lo_y, hi_y) of the whole cell, relative to the symbol origin."""
    gx0, gx1, gy0, gy1 = _graphic_extent(part.symbol)
    sx0, sx1 = min(gx0, gx1), max(gx0, gx1)
    sy0, sy1 = -max(gy0, gy1), -min(gy0, gy1)     # sheet y is flipped
    xs, ys = [sx0, sx1], [sy0, sy1]
    for _num, net, ex, ey, away in _pin_geometry(part):
        reach = STUB if net == "NC" else STUB + _label_len(net)
        xs.extend([ex, ex + away[0] * reach])
        ys.extend([ey, ey + away[1] * reach])
        if away[0]:                                # horizontal label: text height
            ys.extend([ey - TEXT_H, ey + TEXT_H])
        else:
            xs.extend([ex - TEXT_H, ex + TEXT_H])
    lo_x, hi_x = min(xs), max(xs)
    lo_y, hi_y = min(ys), max(ys)
    # room for the Reference / Value text printed under the cell
    text_w = max(len(part.ref), len(part.value)) * CHAR_W
    mid = (lo_x + hi_x) / 2
    lo_x = min(lo_x, mid - text_w / 2)
    hi_x = max(hi_x, mid + text_w / 2)
    return lo_x, hi_x, lo_y, hi_y + 7.0


def _place_part(part, x, y, sheet):
    """sexp nodes for one placed part: the symbol, its stubs, labels and no-connects."""
    nodes = []
    lo_x, hi_x, _lo_y, hi_y = _extents(part)
    mid = round((lo_x + hi_x) / 2, 4)
    hidden = part.ref.startswith("#")
    sym = ["symbol",
           ["lib_id", Str(part.symbol)],
           ["at", round(x, 4), round(y, 4), part.rot],
           ["unit", 1],
           ["body_style", 1],
           ["exclude_from_sim", Sym("no")],
           ["in_bom", Sym("no" if part.dnp or hidden else "yes")],
           ["on_board", Sym("no" if hidden else "yes")],
           ["in_pos_files", Sym("no" if hidden else "yes")],
           ["dnp", Sym("yes" if part.dnp else "no")],
           ["uuid", _u()],
           _prop("Reference", part.ref, x + mid, y + hi_y - 5.0, hide=hidden),
           _prop("Value", part.value, x + mid, y + hi_y - 1.5, hide=hidden),
           _prop("Footprint", part.footprint, x, y, hide=True),
           _prop("Datasheet", "", x, y, hide=True),
           _prop("Description", "", x, y, hide=True),
           _prop("LCSC", part.lcsc, x, y, hide=True),
           _prop("MPN", part.mpn, x, y, hide=True),
           _prop("Manufacturer", part.mfr, x, y, hide=True)]
    for num, _net, _ex, _ey, _away in _pin_geometry(part):
        sym.append(["pin", Str(num), ["uuid", _u()]])
    sym.append(["instances",
                ["project", Str(env.PROJECT_NAME),
                 ["path", Str(f"/{ROOT_UUID}/{SHEET_UUID[sheet]}"),
                  ["reference", Str(part.ref)], ["unit", 1]]]])
    nodes.append(sym)

    for _num, net, ex, ey, away in _pin_geometry(part):
        px, py = round(x + ex, 4), round(y + ey, 4)
        if net == "NC":
            nodes.append(["no_connect", ["at", px, py], ["uuid", _u()]])
            continue
        wx, wy = round(px + away[0] * STUB, 4), round(py + away[1] * STUB, 4)
        nodes.append(["wire", ["pts", ["xy", px, py], ["xy", wx, wy]],
                      ["stroke", ["width", 0], ["type", Sym("default")]], ["uuid", _u()]])
        ang = LABEL_ANGLE[away]
        nodes.append(["global_label", Str(net), ["shape", Sym("passive")],
                      ["at", wx, wy, ang], ["fields_autoplaced", Sym("yes")],
                      _effects(justify=LABEL_JUSTIFY[ang]), ["uuid", _u()],
                      ["property", Str("Intersheetrefs"), Str("${INTERSHEET_REFS}"),
                       ["at", wx, wy, 0], ["hide", Sym("yes")], _effects()]])
    return nodes


def _flag_parts():
    return [model.Part(f"#FLG{i:02d}", "PWR_FLAG", "power:PWR_FLAG", "", {"1": net}, "power")
            for i, net in enumerate(FLAG_NETS)]


def _sheet_parts(sheet):
    parts = list(model.parts_on(sheet))
    if sheet == "power":
        parts += _flag_parts()
    return parts


def _layout(parts, page_w):
    """[(part, x, y)] flowed into rows no wider than page_w; plus the height used."""
    placed = []
    cur_x, cur_y, row_h = MARGIN, MARGIN, 0.0
    for p in parts:
        lo_x, hi_x, lo_y, hi_y = _extents(p)
        w, h = hi_x - lo_x, hi_y - lo_y
        if placed and cur_x + w > page_w - MARGIN:
            cur_x, cur_y, row_h = MARGIN, cur_y + row_h + GAP, 0.0
        placed.append((p, _snap(cur_x - lo_x), _snap(cur_y - lo_y)))
        cur_x += w + GAP
        row_h = max(row_h, h)
    return placed, cur_y + row_h + MARGIN


def _pick_paper(parts):
    for name, w, h in PAPERS:
        placed, used_h = _layout(parts, w)
        if used_h <= h:
            return name, placed
    name, w, _h = PAPERS[-1]
    return name, _layout(parts, w)[0]


def _sheet_doc(sheet):
    parts = _sheet_parts(sheet)
    paper, placed = _pick_paper(parts)
    doc = ["kicad_sch",
           ["version", Sym(SCH_VERSION)],
           ["generator", Str("da2")],
           ["generator_version", Str(GENERATOR_VERSION)],
           ["uuid", Str(DOC_UUID[sheet])],
           ["paper", Str(paper)]]
    lib_symbols = ["lib_symbols"]
    for lib_id in dict.fromkeys(p.symbol for p in parts):
        lib_symbols.append(_lib_symbol(lib_id))
    doc.append(lib_symbols)
    for part, x, y in placed:
        doc += _place_part(part, x, y, sheet)
    doc.append(["embedded_fonts", Sym("no")])
    return doc


def _root_doc():
    doc = ["kicad_sch",
           ["version", Sym(SCH_VERSION)],
           ["generator", Str("da2")],
           ["generator_version", Str(GENERATOR_VERSION)],
           ["uuid", Str(ROOT_UUID)],
           ["paper", Str("A4")],
           ["lib_symbols"]]
    for i, s in enumerate(SHEETS):
        x, y = 40.64 + (i % 2) * 106.68, 45.72 + (i // 2) * 76.2
        w, h = 76.2, 50.8
        doc.append(["sheet", ["at", x, y], ["size", w, h],
                    ["exclude_from_sim", Sym("no")], ["in_bom", Sym("yes")],
                    ["on_board", Sym("yes")], ["dnp", Sym("no")],
                    ["stroke", ["width", 0.1524], ["type", Sym("solid")]],
                    ["fill", ["color", 0, 0, 0, 0.0]],
                    ["uuid", Str(SHEET_UUID[s])],
                    ["property", Str("Sheetname"), Str(s), ["at", x, y - 0.7625, 0],
                     _effects(1.524, justify=("left", "bottom"))],
                    ["property", Str("Sheetfile"), Str(f"{s}.kicad_sch"),
                     ["at", x, y + h + 0.7625, 0],
                     _effects(1.524, justify=("left", "top"))],
                    ["instances", ["project", Str(env.PROJECT_NAME),
                                   ["path", Str(f"/{ROOT_UUID}"), ["page", Str(str(i + 2))]]]]])
    doc.append(["sheet_instances", ["path", Str("/"), ["page", Str("1")]]])
    doc.append(["embedded_fonts", Sym("no")])
    return doc


def _write(path, doc):
    with open(path, "w") as f:
        f.write(sexp.dumps(doc) + "\n")


SYM_LIB_TABLE = ('(sym_lib_table\n  (version 7)\n'
                 '  (lib (name "da2")(type "KiCad")(uri "${KIPRJMOD}/lib/da2.kicad_sym")'
                 '(options "")(descr "DriftAnalyser v2 custom symbols"))\n)\n')
FP_LIB_TABLE = ('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "da2")(type "KiCad")(uri "${KIPRJMOD}/lib/da2.pretty")'
                '(options "")(descr "DriftAnalyser v2 custom footprints"))\n)\n')


def write_all():
    os.makedirs(os.path.join(env.PROJECT_DIR, "fab"), exist_ok=True)
    for s in SHEETS:
        _write(os.path.join(env.PROJECT_DIR, f"{s}.kicad_sch"), _sheet_doc(s))
    _write(os.path.join(env.PROJECT_DIR, f"{env.PROJECT_NAME}.kicad_sch"), _root_doc())
    with open(os.path.join(env.PROJECT_DIR, "sym-lib-table"), "w") as f:
        f.write(SYM_LIB_TABLE)
    with open(os.path.join(env.PROJECT_DIR, "fp-lib-table"), "w") as f:
        f.write(FP_LIB_TABLE)
    pro = os.path.join(env.PROJECT_DIR, f"{env.PROJECT_NAME}.kicad_pro")
    if not os.path.exists(pro):
        with open(pro, "w") as f:
            json.dump({"board": {"design_settings": {}},
                       "meta": {"filename": f"{env.PROJECT_NAME}.kicad_pro", "version": 3},
                       "sheets": [[ROOT_UUID, "Root"]] +
                                 [[SHEET_UUID[s], s] for s in SHEETS]}, f, indent=2)


def export_netlist():
    """{(ref, pin): netname} straight out of kicad-cli.

    Power symbols (#FLGxx) are dropped, and so are the "unconnected-(...)" pseudo-nets
    eeschema invents for pins carrying a no-connect marker. A pin whose stub missed its
    connection point lands in one of those pseudo-nets too, so it simply disappears from
    the result and test_netlist_matches_model still fails on the missing key.
    """
    root = os.path.join(env.PROJECT_DIR, f"{env.PROJECT_NAME}.kicad_sch")
    out = os.path.join(env.PROJECT_DIR, "fab", "netlist.net")
    r = env.run_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, root)
    assert r.returncode == 0, r.stderr
    doc = sexp.parse(open(out).read())[0]
    got = {}
    for net in sexp.find(sexp.find1(doc, "nets"), "net"):
        name = sexp.find1(net, "name")[1].split("/")[-1]
        for node in sexp.find(net, "node"):
            ref = sexp.find1(node, "ref")[1]
            if ref.startswith("#") or name.startswith("unconnected-"):
                continue
            got[(ref, sexp.find1(node, "pin")[1])] = name
    return got
