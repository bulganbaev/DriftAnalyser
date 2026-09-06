# Fab notes - DriftAnalyser v2

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
- **U2 (BTS7002-1EPP) has an exposed pad** (pad 15) carrying VS - the whole
  strip current goes through it. It needs paste on the pad, not just the leads.
  What we ship is a **single 2.65 x 4.0 mm aperture**, not a split one; JLC may
  split the stencil window themselves, and the datasheet (Fig. 39) suggests a
  split window for a hand-cut stencil. Either is fine - the point is that the
  pad gets paste.
- U5 (LSM6DS3TR-C, LGA-14) is the finest pitch on the board (0.5 mm).
- R31..R36 / D11..D16 have no reference on the silk (no room between the strip
  connectors and the LED legend) - they are the series resistor and the data
  clamp of the strip above them, one pair per strip, and they are in the CPL.
- J1 is an XT60PW-M: **+ is pin 2**, the hole on the left as the board is drawn,
  marked on the silk over its own pad. The XT60 housing's chamfered end is the
  negative contact and its straight end the positive one, and on this footprint
  the chamfered end is pin 1 - so pin 1 is GND. The footprint's own "+"/"-"
  silk is deleted by the generator; the two marks on the board are ours.

## Regenerating

`bash gen/build.sh` rebuilds everything here.

The tracked build products are date-free on purpose: the SVGs get a fixed
`<title>`, `schematic.pdf` a fixed `/CreationDate` (rewritten in place at the
same byte length, so the xref table still points where it should), `netlist.net`
a repo-relative `(source ...)`, and `gerbers.zip` both a fixed entry timestamp
and a fixed `TF.CreationDate` in every gerber, drill file and the `.gbrjob`
inside it. Two exports of the same board file therefore produce a byte-identical
zip. A full `build.sh` still moves it: `pcbnew` hands every footprint a fresh
random KIID, that reorders the board file, and the order of the flashes in the
gerbers follows. The loose files under `fab/gerbers/` keep the real date - they
are the fab's record of when the files were made - and are not tracked.

The STEP, the 3D PNGs and the inner/bottom plots are not tracked at all - run
`KICAD_PY -m gen.export` to get them back.

## What the 20 A rating rests on

- Every ampacity number in this board's tests and notes is **IPC-2221** (the
  external/internal `k` split at a 20 K rise). That is the conservative curve:
  IPC-2152 rates an internal layer with a solid plane under it considerably
  higher, so the real margin is better than the numbers say, not worse.
- **U2 dissipates about 1.1-1.8 W at 20 A** (R_DS(on) 2.8-4.5 mOhm hot). It gets
  rid of that through its exposed pad into the F.Cu tab pour and the 24 vias
  that ring the pad in that pour, down into the In2 VBAT plane. **This was not thermally modelled** - it is
  the standard "pad + via field + plane" construction sized by area, not a
  simulated junction temperature. If the strips really pull 20 A continuously,
  measure the tab before trusting it.

## Hand check before power-up

- 12V IN polarity (silk + / -), then the rails. **There are no test points on
  this board**: probe 5 V across C13 (x 62, y 45) and 3V3 across C15 (x 75,
  y 48), both 0603 next to their regulator.
- CAN termination jumper JP1 fitted only if this board is an end of the bus.
- JP2 (K PULLUP) fitted for K-line, left open on a CAN-only car.
