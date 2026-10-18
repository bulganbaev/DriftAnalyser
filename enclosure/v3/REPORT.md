# v3 enclosure concept, second pass (2026-10-18)

Generator `enclosure/v3/enclosure_v3.py` (CadQuery), renders `enclosure/v3/render_v3.py` (VTK).
Run: `enclosure/.venv/bin/python enclosure/v3/enclosure_v3.py` (~20 s; `--no-render` skips PNGs, `--clash` runs the clash check).
Fitted to the routed board (`PCB/v3/driftanalyser-v3.kicad_pcb`, commit 8f96087, 55 × 112).
`out/board.step` is a kicad-cli export (`--subst-models`) of a temp copy of that board; U1 and J3 have no 3D model in this KiCad install, so they are drawn as blocks from their F.Fab outlines, like the switches, J1 and both studs.

## Size
| | mm |
|---|---|
| body | 64.0 × 120.5 (was 64.0 × 108.5) |
| over lid-screw pilasters and ears | 88.0 × 120.5 |
| rear (base + flat lid) | 25.1 high |
| hood over J1 | 41.0 high |
| boot tops (both studs) | 45.7 |
| lug/boot past the rear wall | J5 boot ~10, J2 flush; cables continue to the rear |
| plug + loom out of the front | ~40 + cable |

## Changes from the first pass
- Board 55 × 112, holes from `placement.HOLES`: (3.8, 27.4), (51.2, 27.4), (3.5, 108.5), (51.5, 108.5).
- Second M6 stud J5 (battery negative, GND) at (44.4, 96.3), same stack as J2 at (14, 86.5): brass spacer through a PA66/PEEK sleeve, ring lug, washer, M6 bolt, boot. J2 boot and cable red, J5 black.
- Both lug tongues point to the rear (+board y). Two fingers on each sleeve flange (|x| 4.3–5.5, 5.8–8.6 behind the stud axis) flank the tongue so a lug can't swing toward the other stud; they're on the insulating sleeve, not the aluminium lid, since the lug is live. The boot has a matching tongue channel.
- Stud spacing: centres 31.9, ring lug to ring lug 17.9, bolt head to bolt head 21.2, boot to boot 7.9 (measured on the solids).
- USB-C J3 now at x 14 on the bottom edge (shell 9.5–18.5, front at y 111.3); the 13 × 7.5 rear-wall slot follows it.
- U1 at (45.1, 57.3); u.FL at (51.1, 50.2) from the footprint's fab circle. The SMA bulkhead hole moved to y 50.2, still 7.5 above the board top. Inner nut (AF8, flats up): 0.3 above the U1 can's corner (overlaps it by 0.65 in x), 1.0 under the lid.
- Middle lid-screw pilasters moved to y 63 (clear of the SMA spot face), rear pair to y 110; ears to y 32 / 88.
- Heat pedestals from the routed copper, 2 mm high with a 1.0 mm insulating pad (drawn, light blue):
  - four, one per switch, each inside its B.Cu VBUS patch (zones 6 × 5 at x 10.1 / 19.7 / 29.3 / 38.9, y 25.9–30.9), inset 0.3 → 5.4 × 4.4;
  - one under the Q1/Q2 drain tabs (x 13.65–23.9, y 61.8–66.3). B.Cu there is the GND pour with VBUS via barrels (column at x 18.77); there's no B.Cu VBUS patch under the FETs.
- Clash check (`--clash`, every pair of parts, volume > 0.001 mm³): clean; the only overlap is the lid screws in their tap holes. Plug/latch/J1 ramp, SMA/antenna threads, pigtail and the gasket (now drawn compressed) were trimmed so mating parts don't overlap.
- Renders: `out/render-closed-connector.png`, `out/render-closed-stud-antenna.png`, `out/render-open.png`, `out/render-exploded.png`, and the new `out/render-top-studs.png` (top view, both studs).

## Clearances checked
- Tallest parts: C3 10.5 (2.0 under the lid), pin headers JP1/JP2/J4 8.5; THT pins 1.4 below the board, 1.1 above the floor.
- Stud spacer to lid 3.0 (through the sleeve); lug to lid 1.8.

## Assumptions (not verified)
- J1 27.9 mm tall (pdm30 note); flange/shroud/groove heights are guesses, not from the TE drawing.
- 7461059 stud 10 mm high, Ø14 body (the fab circle).
- WROOM-1U can is 3.2 high and leaves the u.FL corner (x > 48.8, y < 52) open.
- M6 ring lugs 14 OD with an 8 mm tongue (16–25 mm² cable).
- Plug 4-1437290-0 drawn as a block over the shroud.

## Open questions
1. J1 panel cutout/thickness from TE drawing ENG_CD_9-1437287-8; how the U-slot is sealed (header seal, U gasket or bolted front plate).
2. Q1/Q2 pedestal sits under the B.Cu GND pour, not a VBUS patch: heat goes only through the via barrels. Keep it, or add a B.Cu VBUS patch under the drains (PCB change)?
3. Do both battery cables really come in from the rear? J5's boot sticks out ~10 past the rear wall; a side exit would need other finger positions. Stud height, and spacer + sleeve vs a taller stud, are still open.
