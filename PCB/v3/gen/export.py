"""Everything the fab and the assembly house get, out of the board that is here.

Needs kicad-cli only, but lives with the rest of the generator:
    KICAD_PY -m gen.export        (cwd = PCB/v3)
"""
import csv
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gen import env, model

FAB = os.path.join(env.PROJECT_DIR, "fab")
PCB = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb")
SCH = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_sch")

# JLCPCB's 6 layer order, top to bottom: F, In1 = ground, In2 = signals,
# In3 = VBUS / VIN / LED lanes, In4 = signals, B. --subtract-soldermask keeps silk off the
# pads, --use-drill-file-origin puts every file on the board's bottom-left
# corner (the builder sets the aux origin there) so the drill lines up.
GERBER_LAYERS = ("F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,B.Cu,F.Paste,B.Paste,"
                 "F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts")


def _cli(*args):
    subprocess.run([env.KICAD_CLI, *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# KiCad stamps the moment of the run into every gerber, both drill files and the
# .gbrjob. On disk they keep it - that is the fab's record of when the files were
# made - but gerbers.zip is tracked, so the copy that goes into the zip gets a
# fixed one. Without this two runs that changed nothing still produce two zips.
FIXED_GERBER_DATE = b"2026-01-01T00:00:00+00:00"
FIXED_HUMAN_DATE = b"2026-01-01 00:00:00"
# the machine-readable attribute (every gerber, both .drl headers, the .gbrjob)
GERBER_DATE = re.compile(
    rb"(TF\.CreationDate,|\"CreationDate\": \"|; DRILL file KiCad [0-9.]+ date )"
    rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2})?")
# and the human-readable G04 comment KiCad writes next to it
GERBER_COMMENT_DATE = re.compile(
    rb"(G04 Created by KiCad \(PCBNEW [0-9.]+\) date )"
    rb"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def _undated(data):
    """The bytes of one gerber / drill / gbrjob file with its creation date fixed."""
    data = GERBER_DATE.sub(lambda m: m.group(1) + FIXED_GERBER_DATE, data)
    return GERBER_COMMENT_DATE.sub(lambda m: m.group(1) + FIXED_HUMAN_DATE, data)


def gerbers():
    gdir = os.path.join(FAB, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    _cli("pcb", "export", "gerbers", "--layers", GERBER_LAYERS,
         "--subtract-soldermask", "--no-x2", "--use-drill-file-origin",
         "-o", gdir + os.sep, PCB)
    _cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
         "--generate-map", "--map-format", "gerberx2", "--drill-origin", "plot",
         "-o", gdir + os.sep, PCB)
    out = os.path.join(FAB, "gerbers.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(gdir, "*"))):
            # fixed mtime: the file times alone would make every rebuild a new zip
            info = zipfile.ZipInfo(os.path.basename(f), date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(f, "rb") as fh:
                z.writestr(info, _undated(fh.read()))
    return out


HAND_FIT = "(hand-fit)"       # model.mpn mark: not placed by the assembly house


def _refkey(ref):
    m = re.match(r"([A-Za-z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


# parts we ship to the assembler ourselves (BOM-cn.csv 备注 column)
CONSIGNED = {
    "J1": "客供，插件，焊接",
    "J2": "客供，压接端子（不焊，压入即可）",
    "J5": "客供，压接端子（不焊，压入即可）",
}


def bom():
    """One line per orderable part. BOM.csv uses JLCPCB's column names plus an explicit
    per-board Quantity (the domestic jlc.com side and human assemblers ask for it);
    BOM-cn.csv is the same table with Chinese headers and MPN/manufacturer columns."""
    rows, rows_cn = {}, {}
    for p in model.PARTS:
        key = (p.value, p.footprint.split(":")[1], p.lcsc, p.mpn, p.mfr)
        rows_cn.setdefault(key, []).append(p.ref)
        if HAND_FIT in p.mpn:           # the studs: pressed in by hand, not JLC's
            continue
        rows.setdefault(key, []).append(p.ref)
    _sort = lambda d: sorted(d.items(), key=lambda kv: _refkey(sorted(kv[1], key=_refkey)[0]))
    ordered, ordered_cn = _sort(rows), _sort(rows_cn)
    out = os.path.join(FAB, "BOM.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "Quantity", "LCSC Part #"])
        for (val, fp, lcsc, mpn, mfr), refs in ordered:
            w.writerow([val, ",".join(sorted(refs, key=_refkey)), fp, len(refs), lcsc])
    with open(os.path.join(FAB, "BOM-cn.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["型号/值", "位号", "封装", "单套数量", "立创编号", "厂家型号", "厂家", "备注"])
        for (val, fp, lcsc, mpn, mfr), refs in ordered_cn:
            note = CONSIGNED.get(sorted(refs, key=_refkey)[0], "")
            w.writerow([val, ",".join(sorted(refs, key=_refkey)), fp, len(refs), lcsc,
                        mpn.replace(f" {HAND_FIT}", ""), mfr, note])
    return out


def cpl():
    """Pick and place, same origin as the gerbers. H1..H4 are holes, not parts."""
    pos = os.path.join(FAB, "pos.csv")
    _cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "--use-drill-file-origin", "-o", pos, PCB)
    with open(pos) as f:
        rows = list(csv.DictReader(f))
    out = os.path.join(FAB, "CPL.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        hand = {p.ref for p in model.PARTS if HAND_FIT in p.mpn}
        for r in sorted(rows, key=lambda r: _refkey(r["Ref"])):
            if r["Ref"].startswith("H") or r["Ref"] in hand:
                continue
            w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                        "Top" if r["Side"].lower().startswith("top") else "Bottom",
                        f'{float(r["Rot"]) % 360:.2f}'])
    return out


# one plot per layer that anyone reviewing the board wants to look at. Only the
# top view is tracked; the rest are regenerated by build.sh.
TOP_VIEW = ("render-top.svg", "F.Cu,F.SilkS,F.Mask,Edge.Cuts", False)
VIEWS = (("render-bottom.svg", "B.Cu,B.SilkS,B.Mask,Edge.Cuts", True),
         ("render-in1.svg", "In1.Cu,Edge.Cuts", False),
         ("render-in2.svg", "In2.Cu,Edge.Cuts", False),
         ("render-in3.svg", "In3.Cu,Edge.Cuts", False),
         ("render-in4.svg", "In4.Cu,Edge.Cuts", False))


# KiCad stamps the time of day into everything it plots. The gerbers keep theirs
# (rewriting a fab file's own date would be a lie about when it was made), but the
# plots that are tracked here get a fixed one, or every rebuild is a diff.
SVG_TITLE = re.compile(r"<title>SVG Image created as [^<]*</title>")
PDF_DATE = re.compile(rb"(/(?:CreationDate|ModDate)\s*\()([^)]*)(\))")
FIXED_PDF_DATE = b"D:2026:01:01:00:00:00"


def _fix_svg_date(path):
    with open(path) as f:
        text = f.read()
    text, n = SVG_TITLE.subn(f"<title>{os.path.basename(path)}</title>", text)
    if n:
        with open(path, "w") as f:
            f.write(text)
    return n


def _fix_pdf_dates(path):
    """Same length in, same length out: a PDF's xref table is byte offsets."""
    with open(path, "rb") as f:
        data = f.read()

    def fixed(m):
        old = m.group(2)
        return m.group(1) + FIXED_PDF_DATE[:len(old)].ljust(len(old), b"0") + m.group(3)

    out, n = PDF_DATE.subn(fixed, data)
    if len(out) != len(data):
        raise RuntimeError(f"{path}: date rewrite changed the file length")
    if n:
        with open(path, "wb") as f:
            f.write(out)
    return n


def _svg(name, layers, mirror):
    out = os.path.join(FAB, name)
    _cli("pcb", "export", "svg", "--mode-single", "--layers", layers,
         "--page-size-mode", "2", "--exclude-drawing-sheet",
         *(["--mirror"] if mirror else []), "-o", out, PCB)
    _fix_svg_date(out)


def renders():
    for view in VIEWS:
        _svg(*view)
    for side in ("top", "bottom"):
        _cli("pcb", "render", "--quality", "high", "--perspective",
             "--rotate", "-55,0,-35" if side == "top" else "55,0,-35",
             "--zoom", "0.85", "--background", "opaque", "-w", "1800", "-h", "1200",
             "--side", side, "-o", os.path.join(FAB, f"render-3d-{side}.png"), PCB)
    pdf = os.path.join(FAB, "schematic.pdf")
    _cli("sch", "export", "pdf", "-o", pdf, SCH)
    _fix_pdf_dates(pdf)


def step():
    """3D model for the enclosure. Parts without a 3D model in the KiCad library
    (the custom da3 footprints: J1, the studs, the switches) come out flat."""
    out = os.path.join(FAB, env.PROJECT_NAME + ".step")
    _cli("pcb", "export", "step", "--subst-models", "--include-tracks",
         "--include-zones", "--force", "-o", out, PCB)
    return out


README = """# Fab notes - DriftAnalyser v3

55 x 112 mm, 6 layers. Order from `fab/gerbers.zip` (gerbers + Excellon drill,
all on the board's bottom-left corner as the origin), assemble from `BOM.csv` +
`CPL.csv`. The design notes are in `../README.md`.

## JLCPCB board options

| option | value | why |
| --- | --- | --- |
| size | 55 x 112 mm, R 3 mm corners, 4 x M3 (3.2 mm NPTH) | two M6 studs (J2 +12 V, J5 battery negative) need the 112 |
| layers | 6 | F = parts, signals, power pours; In1 = solid GND; In2 = signals; In3 = VBUS / VIN planes + the outer four LED channels' lanes; In4 = signals; B = signals, VBUS copper under the four switches |
| thickness | 1.6 mm | JLC 6-layer 1.6 mm with the 1 oz inner option, **no impedance control needed** (pick whatever stackup JLC offers for that). The board file declares JLC06161H-3313 for the record only: a named JLC stack may not apply with the 1 oz inner option, and this board does not care which dielectric stack JLC builds |
| outer copper | 1 oz | |
| **inner copper** | **1 oz - must be picked** | the stock option is 0.5 oz. The strip current (8 x 5 A) runs from the drains to the switches on the In3 VBUS plane, the outer four LED channels share their current with In3 lanes, and the whole return from the J5 stud to J1's ground row is the In1 plane plus the GND fills. Every number in the design notes assumes 1 oz |
| via | 0.3 mm hole / 0.6 mm pad (signals, ties, LED lanes), 0.4 / 0.8 (VIN / VBUS / GND fields) | all through vias, no blind / buried, no via in pad |
| **surface finish** | **ENIG** | the stud press-fit holes are drawn for the chemical-finish tolerance (below); flat pads also suit the LGA-14 IMU (U3) |
| **press-fit holes** | **32 x finished 1.475 +-0.05 mm (ENIG)**, J2 + J5 | Wurth 7461059 drawing: drill 1.60 -0.03, plating 25..60 um Cu. Put in the order remark: *"press-fit holes (32 x 1.475 mm at J2/J5): finished 1.475 +-0.05 mm, ENIG"*. Standard PTH tolerance (+-0.08) is not enough; if JLC will not hold +-0.05, do not order these as press-fit (see the THR note below) |
| min hole | 0.2 mm | only the ESP32-S3-WROOM-1U footprint's own 12 heatsink vias; everything we drew is 0.3 mm or more. Largest plated: the 32 stud press-fit holes, 1.475 finished |
| min track / clearance | 0.2 mm / 0.2 mm | our own copper. Inside land patterns: **U2 (LM74700, SOT-23-8) pad to pad 0.13 mm** (drawn 0.14) is the board minimum, U3 LGA-14 0.15, other footprints 0.2 - all above JLC's 0.127 mm multilayer floor |
| silkscreen | white on green (any) | min text height on the board is 0.8 mm |

## Assembly

- Every part is on the **top** side; nothing is placed on B.Cu.
- **Through-hole:** J1 (TE 6437288-1 Superseal, 34 pos) is in the BOM with its
  LCSC code (C574787) - **JLC solders it** (THT assembly option). JLC stock was
  low at design time (14 pcs, about $18.65 each): if it is gone at order time,
  hand-fit it (`mpn` -> `6437288-1 (hand-fit)`, clear `lcsc`, rebuild).
- **J2 and J5 are not in BOM.csv / CPL.csv** - we press them in. Wurth WP-BUCF
  REDCUBE PRESS-FIT 7461059: a 13 x 13 x 13.5 mm brass block with an internal M6
  thread (the cable's ring lug is bolted on top), 16 press-fit pins. No solder (wave
  or reflow is not allowed on press-fit). Press each one in a single straight stroke
  with an arbor press, ~640 N (40 N per pin), board supported under the pin field
  (Wurth: support matrix with 1.75 mm holes under the pins), a flat stamp on the
  block - not on the thread. J2 = +12 V in (red boot), J5 = battery negative / GND
  (black). If pressing is not possible: Wurth's REDCUBE THR series with internal
  thread (WP-THRBU) is soldered instead, but it has a different pin pattern - new
  footprint, and the part number has to be picked from Wurth's catalogue (not
  checked here).
- `CPL.csv` is in mm with rotations as KiCad has them. Check JLC's preview
  before paying: their library rotates some SOT/SOIC parts 90 or 180 degrees
  from the KiCad convention, and the preview is the only place that shows it.
- **U10..U13 (BTS7008-2EPA, PG-TSDSO-14) have an exposed pad carrying VBUS**
  (pad 15) - the strip current goes through it. It needs paste on the pad, not
  just the leads. It has 12 vias (0.3 mm) into the In3 VBUS plane and
  the B.Cu VBUS copper under the switch.
- **The B.Cu copper under U10..U13 is VBUS (+12 V).** The thermal pad between
  the board and the case must be **electrically insulating** (silicone gap pad,
  not graphite or metal), and the case must not touch that copper.
- U7 (LMR36520, HSOIC-8) and Q1/Q2 (BSC016N06NS, TDSON-8) have exposed pads too:
  paste on them as well.
- U3 (LSM6DS3TR-C, LGA-14) is the finest pitch on the board (0.5 mm).

## Regenerating

`bash gen/build.sh` rebuilds everything here.

The tracked build products are date-free on purpose: the SVGs get a fixed
`<title>`, `schematic.pdf` a fixed `/CreationDate` (rewritten in place at the
same byte length, so the xref table still points where it should), `netlist.net`
a repo-relative `(source ...)`, and `gerbers.zip` both a fixed entry timestamp
and a fixed `TF.CreationDate` in every gerber, drill file and the `.gbrjob`
inside it. Two exports of the same board file therefore produce a byte-identical
zip. The loose files under `fab/gerbers/` keep the real date - they are the
fab's record of when the files were made - and are not tracked.

The STEP (for the enclosure), the 3D PNGs and the inner/bottom plots are not
tracked at all - run `KICAD_PY -m gen.export` to get them back.

## Hand check before power-up

- **Stud polarity: J2 is +12 V (silk "+12V"), J5 is battery negative (silk
  "GND -").** The LM74700 ideal diode blocks a reversed battery, but check
  anyway.
- There are no test points: probe 5 V across C11 and 3V3 across C13 (both
  0805 next to their regulator).
- CAN termination jumper JP2 fitted only if this board is an end of the bus.
- JP1 (K-line pull-up, 510 R to VBUS) fitted for K-line, left open on a
  CAN-only car.
"""


# J1 rows as TE numbers them: 1 is nearest the switches, 4 nearest the board edge
J1_ROWS = ((1, range(1, 10)), (2, range(10, 18)), (3, range(18, 26)), (4, range(26, 35)))
J1_BEGIN, J1_END = "<!-- j1-table: generated by gen/export.py, do not edit -->", "<!-- /j1-table -->"


def _j1_signal(key):
    m = re.fullmatch(r"LED(\d)_(12V|GND|DO)", key)
    if m:
        n, what = int(m.group(1)), m.group(2)
        u, out = 9 + (n + 1) // 2, (n + 1) % 2
        return {"12V": f"LED{n} +12 V (U{u} OUT{out})", "GND": f"GND, LED{n} strip return",
                "DO": f"LED{n} data"}[what]
    return {"SIG1_GND": "GND, signal return", "SIG2_GND": "GND, signal return",
            "CANH": "CAN high", "CANL": "CAN low", "KLINE": "K-line",
            "IN1": "input 1", "IN2": "input 2", "IN3": "input 3",
            "5V_SENS": "5 V sensor supply (U6, switched, ~130 mA limit)",
            "IGN": "ignition (wakes the board)"}[key]


def j1_table():
    """J1 pin -> signal, by rows, straight from model.J1_PIN."""
    by_pin = {int(p): k for k, p in model.J1_PIN.items()}
    lines = [J1_BEGIN, "", "| row | pin | net | signal |", "| --- | --- | --- | --- |"]
    for row, pins in J1_ROWS:
        for p in pins:
            key = by_pin[p]
            net = "GND" if key.endswith("_GND") else key
            lines.append(f"| {row} | {p} | `{net}` | {_j1_signal(key)} |")
    lines += ["", "Top view, J1 at the top edge (mating face toward the edge, row 4 nearest it):",
              "", "```"]
    for row, pins in reversed(J1_ROWS):
        cells = [f"{p:>2} {by_pin[p]}" for p in reversed(pins)]
        pad = "" if len(pins) == 9 else " " * 8
        lines.append(f"row {row}: " + pad + " ".join(f"{c:<15}" for c in cells).rstrip())
    lines += ["```", "", J1_END]
    return "\n".join(lines)


def readme():
    out = os.path.join(FAB, "README-fab.md")
    with open(out, "w") as f:
        f.write(README)
    # the J1 table in the design README is the model's, not typed by hand
    main = os.path.join(env.PROJECT_DIR, "README.md")
    with open(main) as f:
        text = f.read()
    a, b = text.find(J1_BEGIN), text.find(J1_END)
    if a >= 0 and b > a:
        text = text[:a] + j1_table() + text[b + len(J1_END):]
        with open(main, "w") as f:
            f.write(text)
    return out


def export_fab():
    """What the fab and the assembly house get, plus the one tracked plot.
    Seconds, no 3D: this is what the test suite runs."""
    os.makedirs(FAB, exist_ok=True)
    gerbers()
    bom()
    cpl()
    _svg(*TOP_VIEW)
    readme()


def export_heavy():
    """The 3D renders, the STEP and the other plots - half a minute and 28 MB,
    none of it tracked. build.sh runs it, the tests do not."""
    renders()
    step()


def export_all():
    export_fab()
    if os.environ.get("DA2_HEAVY", "1") == "1":
        export_heavy()


if __name__ == "__main__":
    export_all()
    print("fab/ written:", ", ".join(sorted(
        os.path.basename(f) for f in glob.glob(os.path.join(FAB, "*")) if os.path.isfile(f))))
