"""Everything the fab and the assembly house get, out of the board that is here.

Needs kicad-cli only, but lives with the rest of the generator:
    KICAD_PY -m gen.export        (cwd = PCB/v2)
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

# JLCPCB's 4 layer order: the two inner layers go in the middle of the stack,
# In1 = ground, In2 = VBAT / 12V_LED. --subtract-soldermask keeps silk off the
# pads, --use-drill-file-origin puts every file on the board's bottom-left
# corner (the builder sets the aux origin there) so the drill lines up.
GERBER_LAYERS = ("F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,"
                 "F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts")


def _cli(*args):
    subprocess.run([env.KICAD_CLI, *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
            z.write(f, os.path.basename(f))
    return out


def _refkey(ref):
    m = re.match(r"([A-Za-z]+)(\d+)", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def bom():
    """One line per orderable part, JLCPCB's column names."""
    rows = {}
    for p in model.PARTS:
        rows.setdefault((p.value, p.footprint.split(":")[1], p.lcsc), []).append(p.ref)
    out = os.path.join(FAB, "BOM.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fp, lcsc), refs in sorted(rows.items(),
                                            key=lambda kv: _refkey(sorted(kv[1], key=_refkey)[0])):
            w.writerow([val, ",".join(sorted(refs, key=_refkey)), fp, lcsc])
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
        for r in sorted(rows, key=lambda r: _refkey(r["Ref"])):
            if r["Ref"].startswith("H"):
                continue
            w.writerow([r["Ref"], f'{float(r["PosX"]):.4f}mm', f'{float(r["PosY"]):.4f}mm',
                        "Top" if r["Side"].lower().startswith("top") else "Bottom",
                        f'{float(r["Rot"]) % 360:.2f}'])
    return out


# one plot per layer that anyone reviewing the board wants to look at
VIEWS = (("render-top.svg", "F.Cu,F.SilkS,F.Mask,Edge.Cuts", False),
         ("render-bottom.svg", "B.Cu,B.SilkS,B.Mask,Edge.Cuts", True),
         ("render-in1.svg", "In1.Cu,Edge.Cuts", False),
         ("render-in2.svg", "In2.Cu,Edge.Cuts", False))


def renders():
    for name, layers, mirror in VIEWS:
        _cli("pcb", "export", "svg", "--mode-single", "--layers", layers,
             "--page-size-mode", "2", "--exclude-drawing-sheet",
             *(["--mirror"] if mirror else []),
             "-o", os.path.join(FAB, name), PCB)
    for side in ("top", "bottom"):
        _cli("pcb", "render", "--quality", "high", "--perspective",
             "--rotate", "-55,0,-35" if side == "top" else "55,0,-35",
             "--zoom", "0.85", "--background", "opaque", "-w", "1800", "-h", "1200",
             "--side", side, "-o", os.path.join(FAB, f"render-3d-{side}.png"), PCB)
    _cli("sch", "export", "pdf", "-o", os.path.join(FAB, "schematic.pdf"), SCH)


def step():
    """3D model for the enclosure. The JST VH strip connectors have no model in
    the KiCad library, so their footprints come out flat - everything else is there."""
    out = os.path.join(FAB, env.PROJECT_NAME + ".step")
    _cli("pcb", "export", "step", "--subst-models", "--include-tracks",
         "--include-zones", "--force", "-o", out, PCB)
    return out


README = """# Fab notes - DriftAnalyser v2

Order from `fab/gerbers.zip` (gerbers + Excellon drill, all on the board's
bottom-left corner as the origin), assemble from `BOM.csv` + `CPL.csv`.

## JLCPCB board options

| option | value | why |
| --- | --- | --- |
| layers | 4 | In1.Cu = solid GND, In2.Cu = VBAT / 12V_LED |
| thickness | 1.6 mm | stackup **JLC04161H-7628** (the one the board file declares) |
| outer copper | 1 oz | |
| **inner copper** | **1 oz - must be picked** | the VBAT path to U2 runs on In2. At the stock 0.5 oz the plane carries about half its rated current and the 20 A strip load runs the copper hot; 1 oz is what every number in the report assumes |
| surface finish | HASL lead free or ENIG | ENIG if the LGA-14 IMU is hand-reworked |
| min hole | 0.2 mm | the ESP32-S3-WROOM-1 footprint brings its own 0.2 mm thermal vias under the module - JLC surcharges these, everything we drew is 0.4 mm |
| min clearance | 0.15 mm | only U5's LGA-14 land pattern goes that low; our own copper keeps 0.25 mm |
| silkscreen | white on green (any) | min text height on the board is 0.8 mm |

## Assembly

- Every part is on the **top** side; nothing is placed on B.Cu.
- `CPL.csv` is in mm with rotations as KiCad has them. Check JLC's preview
  before paying: their library rotates some SOT/SOIC parts 90 or 180 degrees
  from the KiCad convention, and the preview is the only place that shows it.
- **U2 (BTS7002-1EPP) has an exposed pad** carrying VS - the whole strip
  current goes through it. It needs paste on the pad, not just the leads; the
  stencil aperture is already split in the paste layer.
- U5 (LSM6DS3TR-C, LGA-14) is the finest pitch on the board (0.5 mm).
- R31..R36 / D11..D16 have no reference on the silk (no room between the strip
  connectors and the LED legend) - they are the series resistor and the data
  clamp of the strip above them, one pair per strip, and they are in the CPL.
- J1 is an XT60PW-M: **+ is pin 1**, marked on the silk next to the pad.

## Hand check before power-up

- 12V IN polarity (silk + / -), then 5 V and 3V3 on the test points of U3 / U4.
- CAN termination jumper JP1 fitted only if this board is an end of the bus.
- JP2 (K PULLUP) fitted for K-line, left open on a CAN-only car.
"""


def readme():
    out = os.path.join(FAB, "README-fab.md")
    with open(out, "w") as f:
        f.write(README)
    return out


def export_all():
    os.makedirs(FAB, exist_ok=True)
    gerbers()
    bom()
    cpl()
    renders()
    step()
    readme()


if __name__ == "__main__":
    export_all()
    print("fab/ written:", ", ".join(sorted(
        os.path.basename(f) for f in glob.glob(os.path.join(FAB, "*")) if os.path.isfile(f))))
