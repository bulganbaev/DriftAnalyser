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
- **U2 (BTS7002-1EPP) has an exposed pad** carrying VS - the whole strip
  current goes through it. It needs paste on the pad, not just the leads; the
  stencil aperture is already split in the paste layer.
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

`bash gen/build.sh` rebuilds everything here. `gerbers.zip` uses a fixed entry
timestamp, but KiCad stamps a `CreationDate` into every gerber, the drill files
and the `.gbrjob`, so the zip's bytes still change on each run even when the
board does not. The STEP, the 3D PNGs and the inner/bottom plots are not tracked
at all - run `KICAD_PY -m gen.export` to get them back.

## Hand check before power-up

- 12V IN polarity (silk + / -), then 5 V and 3V3 on the test points of U3 / U4.
- CAN termination jumper JP1 fitted only if this board is an end of the bus.
- JP2 (K PULLUP) fitted for K-line, left open on a CAN-only car.
