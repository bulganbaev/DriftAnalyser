# Fab notes - DriftAnalyser v3

55 x 112 mm, 6 layers. Order from `fab/gerbers.zip` (gerbers + Excellon drill,
all on the board's bottom-left corner as the origin), assemble from `BOM.csv` +
`CPL.csv`. The design notes are in `../README.md`.

## JLCPCB board options

| option | value | why |
| --- | --- | --- |
| size | 55 x 112 mm, R 3 mm corners, 4 x M3 (3.2 mm NPTH) | two M6 studs (J2 +12 V, J5 battery negative) need the 112 |
| layers | 6 | F = parts, signals, power pours; In1 = solid GND; In2 = signals; In3 = VBUS / VIN planes + the outer four LED channels' lanes; In4 = signals; B = signals, VBUS copper under the four switches |
| thickness | 1.6 mm | stackup **JLC06161H-3313** (JLC's default 6 layer build, the one the board file declares): 3313 0.0994 / core 0.55 / 2116 0.1164 / core 0.55 / 3313 0.0994 |
| outer copper | 1 oz | |
| **inner copper** | **1 oz - must be picked** | the stock option is 0.5 oz. The strip current (8 x 5 A) runs from the drains to the switches on the In3 VBUS plane, the outer four LED channels share their current with In3 lanes, and the whole return from the J5 stud to J1's ground row is the In1 plane plus the GND fills. Every number in the design notes assumes 1 oz |
| via | 0.3 mm hole / 0.6 mm pad (signals, ties, LED lanes), 0.4 / 0.8 (VIN / VBUS / GND fields) | all through vias, no blind / buried, no via in pad |
| surface finish | HASL lead free or ENIG | ENIG if the LGA-14 IMU (U3) is hand-reworked |
| min hole | 0.2 mm | only the ESP32-S3-WROOM-1U footprint's own 12 heatsink vias; everything we drew is 0.3 mm or more. Largest: the two stud holes, 6.4 mm plated, each ringed by 8 x 0.5 mm |
| min track / clearance | 0.2 mm / 0.2 mm | our own copper. Inside land patterns: **U2 (LM74700, SOT-23-8) pad to pad 0.13 mm** (drawn 0.14) is the board minimum, U3 LGA-14 0.15, other footprints 0.2 - all above JLC's 0.127 mm multilayer floor |
| silkscreen | white on green (any) | min text height on the board is 0.8 mm |

## Assembly

- Every part is on the **top** side; nothing is placed on B.Cu.
- **Through-hole:** J1 (TE 6437288-1 Superseal, 34 pos) is in the BOM with its
  LCSC code (C574787) - **JLC solders it** (THT assembly option). JLC stock was
  low at design time (14 pcs, about $18.65 each): if it is gone at order time,
  hand-fit it (`mpn` -> `6437288-1 (hand-fit)`, clear `lcsc`, rebuild).
- **J2 and J5 are hand-fit**: Wurth WP-BUCF 7461059 M6 press-fit studs, no LCSC code
  in the BOM (the `Stud_M6` line). They are in the CPL; tell JLC "do not place"
  for that line. J2 = +12 V in (red boot), J5 = battery negative / GND (black).
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
  0603 next to their regulator).
- CAN termination jumper JP2 fitted only if this board is an end of the bus.
- JP1 (K-line pull-up, 510 R to VBUS) fitted for K-line, left open on a
  CAN-only car.
