# DriftAnalyser PCB v2

## BOM sources

All LCSC codes below were looked up live in this session (2026-09-06) via the
JLCPCB parts mirror `jlcsearch.tscircuit.com` (JSON API, `/list?...` query
params per category: `resistance`/`capacitance` in base units + `package`
for passives) and/or `lcsc.com/product-detail/<code>.html` product pages
(via WebFetch) and `WebSearch "<MPN>" site:lcsc.com`. Stock is a snapshot at
lookup time and will drift.

| Ref(s) | Value | MPN | LCSC | JLC type | Stock seen | Date |
|---|---|---|---|---|---|---|
| J1 | XT60PW-M | XT60PW-M | C98732 | Extended | 27,130 | 2026-09-06 |
| D1 | SMDJ18A | 5.0SMDJ18A (DOWO) | C284071 | Extended | 2,925 | 2026-09-06 |
| C1, C2 | 100uF 35V | GVZ1H107M0810CNVC (HRK) | C2983550 | Extended | 66,426 | 2026-09-06 |
| C3, C4, C5, C6, C9 | 10uF 50V | CS3225X7R106K500NRL (SAMWHA) | C2918502 | Extended | 114,648 | 2026-09-06 |
| U2 | BTS7002-1EPP | BTS70021EPPXUMA1 (Infineon) | C2680407 | Extended | 273 | 2026-09-06 |
| U2 fallback | BTS7004-1EPP | BTS7004-1EPP (Infineon) | C534825 | Extended | 3,100 (4.4mOhm, 15A, same TSDSO-14 pkg/pinout, drop-in if 7002 out at order time) | 2026-09-06 |
| R1, R2, R4, R8, R11, R12, R16-R21, R41 | 10k | 0603WAF1002T5E (UNI-ROYAL) | C25804 | Basic | 37,165,617 | 2026-09-06 |
| R5 | 470 | 0603WAF4700T5E (UNI-ROYAL) | C23179 | Basic | 2,964,915 | 2026-09-06 |
| R6, R10, R13 | 1k | 0603WAF1001T5E (UNI-ROYAL) | C21190 | Basic | 15,873,089 | 2026-09-06 |
| C7, C8, C10, C17, C20, C21, C22, C23, C24, C25 | 100nF | CC0603KRX7R9BB104 (YAGEO) | C14663 | Basic | 81,299,425 | 2026-09-06 |
| D2 | BAT54W | BAT54W (JSCJ) | C77328 | Extended | 4,671-7,360 | 2026-09-06 |
| R7 | 47k | 0603WAF4702T5E (UNI-ROYAL) | C25819 | Basic | 5,115,474 | 2026-09-06 |
| U3 | AP63200WU-7 | AP63200WU-7 (Diodes Inc) | C2071868 | Extended | lcsc.com retail: 0/Out of Stock; JLC assembly mirror: 2,599 - kept, two pools differ | 2026-09-06 |
| U3 fallback | TPS54302DDCR | TPS54302DDCR (TI) | C311983 | Extended | 84,590 (adjustable 4.5-28V; needs FB divider 80.6k/10k for 5.4V @ 0.596V ref + EN divider; requires redrawing U3, not done) | 2026-09-06 |
| L1 | 6.8uH | YNR6045-6R8M (YJYCOIN) | C341066 | Extended | 8,265 | 2026-09-06 |
| C11, C12, C13, C16 | 22uF 10V | CL21A226MAQNNNE (Samsung Electro-Mechanics) | C45783 | Basic | 5,389,915 | 2026-09-06 |
| R3 | 57.6k | FRC0603F5762TS (FOJAN) | C2933240 | Extended | 25,989 | 2026-09-06 |
| R9 | 100k | 0603WAF1003T5E (UNI-ROYAL) | C25803 | Basic | 14,797,688 | 2026-09-06 |
| D3, D4 | SS34 | SS34 (MDD) | C8678 | Basic | 3,282,802 | 2026-09-06 |
| U4 | AP7361C-33E | AP7361C-33E-13 (Diodes Inc) | C500795 | Extended | 5,442 | 2026-09-06 |
| C14, C15, C19 | 10uF | CL21A106KAYNNNE (Samsung Electro-Mechanics) | C15850 | Basic | 12,668,317 | 2026-09-06 |
| D5 | BLUE | XL-1608UBC-04 (XINGLIGHT) | C965807 | Extended | 1,829,633 | 2026-09-06 |
| U1 | ESP32-S3-WROOM-1-N16R2 | ESP32-S3-WROOM-1-N16R2 (Espressif) | C2913205 | Extended | 8,701 | 2026-09-06 |
| C18 | 1uF | CL10A105KB8NNNC (Samsung Electro-Mechanics) | C15849 | Basic | 11,240,988 | 2026-09-06 |
| SW1, SW2 | EN/BOOT tactile | PTS645SM43SMTR92LFS (C&K) | C221880 | Extended | 5,900 | 2026-09-06 |
| D6 | GREEN | PSC-1608U49GC-G4 (HONGLITRONIC) | C22371299 | Extended | 24,430 | 2026-09-06 |
| J2 | USB-C 16P | TYPE-C 16PIN 2MD(073) (SHOU HAN) | C2765186 | Extended | (known-good, reused from old BOM) | 2026-09-06 |
| R14, R15 | 5.1k | 0603WAF5101T5E (UNI-ROYAL) | C23186 | Basic | 7,571,904 | 2026-09-06 |
| U6 | USBLC6-2SC6 | USBLC6-2SC6 (ST) | C7519 | Extended | 44,150 | 2026-09-06 |
| J3 | 1x4 header | PZ254V-11-04P (XFCN) | C2691448 | Extended | 1,087,760 | 2026-09-06 |
| J4 | 1x6 header | PZ254V-11-06P (XFCN) | C492405 | Extended | 79,320 | 2026-09-06 |
| J5 | microSD | DM3BT-DSF-PEJS (Hirose) | C597972 | Extended | 1,271 | 2026-09-06 |
| U5 | LSM6DS3TR-C | LSM6DS3TR-C (STMicroelectronics) | C967633 | Extended | 24,304 | 2026-09-06 |
| R22, R23 | 4.7k | 0603WAF4701T5E (UNI-ROYAL) | C23162 | Basic | 9,126,951 | 2026-09-06 |
| U7 | 74HCT245PW | 74HCT245PW,118 (Nexperia) | C5980 | Extended | 6,106 | 2026-09-06 |
| R31-R36 | 220 | 0603WAF2200T5E (UNI-ROYAL) | C22962 | Basic | 3,413,507 | 2026-09-06 |
| D11-D16 | PESD5V0S1BA | PESD5V0S1BA,115 (Nexperia) | C19224 | Extended | 50,425 | 2026-09-06 |
| J11-J16 | LED1-LED6 (JST VH 3-pin) | B3P-VH(LF)(SN) (JST) | C160316 | Extended | 27,734 | 2026-09-06 |
| J6 | OBD (JST XH 4-pin) | B4B-XH-A(LF)(SN) (JST) | C144395 | Extended | 611 | 2026-09-06 |
| U8 | TJA1051T/3 | TJA1051T/3,118 (NXP) | C58988 | Extended | 15,240 | 2026-09-06 |
| R40 | 120 | 1206W4F1200T5E (UNI-ROYAL) | C17909 | Basic | 475,116 | 2026-09-06 |
| JP1, JP2 | 1x2 header | PZ254V-11-02P (XFCN) | C492401 | Extended | 1,279,800 | 2026-09-06 |
| D20 | PESD1CAN | PESD1CAN,215 (Nexperia) | C15771 | Extended | 279,780 | 2026-09-06 |
| U9 | TJA1027T/20 | TJA1027T/20,118 (NXP) | C112994 | Extended | 2,196 | 2026-09-06 |
| R42 | 510 0.5W | FRC2512J511TS (FOJAN) | C2934121 | Extended | 30,852 | 2026-09-06 |
| D21 | SMAJ24A | SMAJ24A (Littelfuse) | C148222 | Extended | 25,930 | 2026-09-06 |

### Substitutions made this task (Task 10)

- **D1** `SMDJ18A` (Littelfuse) is not listed on lcsc.com/JLCPCB at all. Substituted
  DOWO `5.0SMDJ18A` (C284071): same SMC(DO-214AB) package, same 18V standoff voltage,
  3000W-class TVS. `mfr` changed Littelfuse -> DOWO.
- **D2** `BAT54W` (Nexperia, C8657) is out of stock. Substituted JSCJ's `BAT54W`
  (C77328), same SOT-323 package, LCSC describes it as "1 Independent" (single diode),
  which matches this design's pin-2-NC single-diode use better than Nexperia's own
  dual-diode BAT54W/AW/CW/SW family. `mfr` changed Nexperia -> JSCJ.
- **L1** Bourns `SRN6045TA-6R8M` (C2041457) has 1 unit in stock. Substituted YJYCOIN
  `YNR6045-6R8M` (C341066): identical 6.8uH / SMD 6x6mm / 3A shielded spec, same "6045"
  case as the Bourns part the footprint is named for. `mpn`/`mfr` filled in (were empty).
- **J5** microSD: the real Hirose `DM3BT-DSF-PEJS` is itself on LCSC as C597972 (1,271
  in stock) - the exact part the KiCad footprint is named for, so no substitution was
  needed. (This is a better source than the old board's SHOU HAN "TF PUSH" clone,
  C393941, which is only 8 contacts with no separate card-detect pins.)

### Resolved concerns (controller rulings, fix round after Task 10)

1. **U3 `AP63200WU-7`** (C2071868, Diodes Inc): lcsc.com's retail storefront page shows
   "Out of Stock", but the JLC parts mirror (jlcsearch.tscircuit.com) shows this same
   LCSC code has 2,599 units available for SMT assembly - LCSC's retail stock and
   JLCPCB's assembly-reel stock are separate pools, and assembly is what matters for
   this board. **Controller ruling: keep C2071868.** Fallback recorded above
   (`TPS54302DDCR`, C311983) if assembly stock is actually empty at order time - not
   applied, needs an FB divider (80.6k/10k for 5.4V against its 0.596V reference), an
   EN divider, and redrawing U3's pinout (its symbol pins differ from AP63200WU).
2. **U2 `BTS7002-1EPP`**: `C534824` (used in the original Task 10 pass) 404s on
   lcsc.com because it isn't the live JLC listing for this part. The JLC parts mirror
   (`jlcsearch.tscircuit.com/api/search?q=BTS7002-1EPP`) resolves it to **LCSC
   `C2680407`** (mfr code `BTS70021EPPXUMA1`, TSSOP-14-EP package, 273 in stock,
   $3.77). **Controller ruling: set `U2.lcsc = "C2680407"`, `mpn =
   "BTS70021EPPXUMA1"`.** Fallback recorded above (`BTS7004-1EPP`, C534825, same
   TSDSO-14 package/pinout, 4.4mOhm/15A, 3,100 in stock) if 7002 is out at order time.
3. **J6 / D20 stock**: `B4B-XH-A(LF)(SN)` (C144395, 611 units) and the rest are fine
   for a small hobby-quantity JLCPCB order but are thin; re-check before a larger run.
   (Still open, not part of the controller rulings above.)
