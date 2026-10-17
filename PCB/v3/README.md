# DriftAnalyser PCB v3

Generated from `gen/model.py` (`python3 -c 'from gen import sch_writer; sch_writer.write_all()'`,
tests: `python3 -m pytest gen/tests -q`). Do not hand-edit the `.kicad_sch` files.
Task 12 expands this README.

## BOM sources

LCSC codes checked on 2026-10-18 against the JLCPCB assembly parts API
(`POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`,
body `{"keyword": "<MPN or C-code>", "currentPage": 1, "pageSize": 10}`). The `jlcsearch.tscircuit.com`
mirror v2 used returns junk for text search now, so it was not used. Stock is the JLC assembly
stock at lookup time and will drift. 49 unique LCSC parts: 17 Basic, 32 Extended (each Extended
part is a JLC feeder fee). "Source" = code reused from v2, from an earlier v3 task, or new here.

| Ref(s) | Value | MPN (mfr) | LCSC | JLC type | Stock seen | Source | Date |
|---|---|---|---|---|---|---|---|
| C1, C5, C6, C8, C14, C17, C19, C20, C23, C26, C29, C33, C34, C35, C36, C40, C41, C42 | 100nF / 100nF 50V | CC0603KRX7R9BB104 (YAGEO) | C14663 | Basic | 31,903,698 | v2 | 2026-10-18 |
| C2 | 220nF 25V | CL10B224KA8NNNC (Samsung Electro-Mechanics) | C21120 | Basic | 1,189,050 | new (Task 9) | 2026-10-18 |
| C3 | 100uF 50V | GVZ1H107M0810CNVC (HRK) | C2983550 | Extended | 3,291 | v2 | 2026-10-18 |
| C4, C7 | 10uF 50V | CS3225X7R106K500NRL (SAMWHA) | C2918502 | Extended | 45,258 | v2 | 2026-10-18 |
| C9, C10, C11, C16 | 22uF 10V | CL21A226MAQNNNE (Samsung Electro-Mechanics) | C45783 | Basic | 3,776,309 | v2 | 2026-10-18 |
| C12, C13 | 10uF | CL21A106KAYNNNE (Samsung Electro-Mechanics) | C15850 | Basic | 6,503,669 | v2 | 2026-10-18 |
| C15, C18, C38 | 1uF | CL10A105KB8NNNC (Samsung Electro-Mechanics) | C15849 | Basic | 9,281,706 | v2 | 2026-10-18 |
| C21, C22, C24, C25, C27, C28, C30, C31, C32 | 10nF / 10nF 50V | 0603B103K500NT (FH) | C57112 | Basic | 5,457,448 | v3 earlier task | 2026-10-18 |
| C37 | 220nF 100V | CC0805KKX7R0BB224 (YAGEO) | C513710 | Extended | 142,185 | new (Task 9) | 2026-10-18 |
| D1 | SMCJ24CA | SMCJ24CA (Littelfuse) | C151279 | Extended | 6,785 | new (Task 9) | 2026-10-18 |
| D2, D3, D10 | BAT54S | BAT54S,215 (Nexperia) | C47546 | Extended | 337,344 | new (Task 9) | 2026-10-18 |
| D4, D5 | BAT54W | BAT54W (JSCJ) | C77328 | Extended | 3,803 | v2 | 2026-10-18 |
| D6, D7, D8 | SS34 | SS34 (MDD) | C8678 | Basic | 3,876,002 | v2 | 2026-10-18 |
| D9 | GREEN | PSC-1608U49GC-G4 (HONGLITRONIC) | C22371299 | Extended | 24,983 | v2 | 2026-10-18 |
| D11, D12, D13, D14, D15, D16, D17, D18 | PESD5V0S1BA | PESD5V0S1BA,115 (Nexperia) | C19224 | Extended | 102,594 | v2 | 2026-10-18 |
| D20 | PESD1CAN | PESD1CAN,215 (Nexperia) | C15771 | Extended | 177,855 | v2 | 2026-10-18 |
| D21, D22, D23, D24 | SMAJ24A | SMAJ24A (Littelfuse) | C148222 | Extended | 16,530 | v2 | 2026-10-18 |
| J1 | 6437288-1 | 6437288-1 (TE Connectivity) | C574787 | Extended | 14 | new (Task 9) | 2026-10-18 |
| J2 | Stud_M6 | 7461059 (Wurth) | — | hand-fit | JLC C5525467: 0 | — | 2026-10-18 |
| J3 | USB-C 16P | TYPE-C 16PIN 2MD(073) (SHOU HAN) | C2765186 | Extended | 949,892 | v2 | 2026-10-18 |
| J4 | UART0 | PZ254V-11-04P (XFCN) | C2691448 | Extended | 890,157 | v2 | 2026-10-18 |
| JP1, JP2 | CAN TERM / K PULLUP | PZ254V-11-02P (XFCN) | C492401 | Extended | 1,093,386 | v2 | 2026-10-18 |
| L1 | 10uH | SRN6045TA-100M (Bourns) | C2046332 | Extended | 798 | new (Task 9) | 2026-10-18 |
| Q1, Q2 | BSC016N06NS | BSC016N06NS (Infineon) | C454269 | Extended | 10,577 | new (Task 9) | 2026-10-18 |
| R1, R4 | 47k | 0603WAF4702T5E (UNI-ROYAL) | C25819 | Basic | 1,887,562 | v2 | 2026-10-18 |
| R2, R12, R14, R15, R19, R20, R22, R24, R26, R28, R30, R32, R34, R36, R37, R40, R43, R46, R51, R70, R72, R74, R76, R77, R78, R80, R81, R82, R84, R85 | 10k | 0603WAF1002T5E (UNI-ROYAL) | C25804 | Basic | 31,147,494 | v2 | 2026-10-18 |
| R3, R5, R7, R8, R9, R13 | 100k | 0603WAF1003T5E (UNI-ROYAL) | C25803 | Basic | 19,378,358 | v2 | 2026-10-18 |
| R6, R75, R79, R83 | 33k | 0603WAF3302T5E (UNI-ROYAL) | C4216 | Basic | 3,602,591 | new (Task 9) | 2026-10-18 |
| R10 | 22.6k | CR0603FA2262G (LIZ Elec) | C100874 | Extended | 4,947 | new (Task 9) | 2026-10-18 |
| R11 | 210k | 0603WAF2103T5E (UNI-ROYAL) | C22952 | Extended | 30,792 | new (Task 9) | 2026-10-18 |
| R16 | 1k | 0603WAF1001T5E (UNI-ROYAL) | C21190 | Basic | 23,268,402 | v2 | 2026-10-18 |
| R17, R18 | 5.1k | 0603WAF5101T5E (UNI-ROYAL) | C23186 | Basic | 23,526,533 | v2 | 2026-10-18 |
| R21, R23, R25, R27, R29, R31, R33, R35, R38, R39, R41, R42, R44, R45, R47, R48, R50, R52, R53 | 4.7k | 0603WAF4701T5E (UNI-ROYAL) | C23162 | Basic | 18,649,768 | v2 | 2026-10-18 |
| R49 | 1.2k | 0603WAF1201T5E (UNI-ROYAL) | C22765 | Basic | 2,483,524 | v3 earlier task | 2026-10-18 |
| R54, R55, R56, R57, R58, R59, R60, R61 | 33 | 0603WAF330JT5E (UNI-ROYAL) | C23140 | Basic | 4,963,587 | v3 earlier task | 2026-10-18 |
| R71 | 120 | 1206W4F1200T5E (UNI-ROYAL) | C17909 | Basic | 625,494 | v2 | 2026-10-18 |
| R73 | 510 0.5W | FRC2512J511TS (FOJAN) | C2934121 | Extended | 28,440 | v2 | 2026-10-18 |
| SW1, SW2 | BOOT / EN | PTS645SM43SMTR92LFS (C&K) | C221880 | Extended | 1,604 | v2 | 2026-10-18 |
| U1 | ESP32-S3-WROOM-1U-N16R2 | ESP32-S3-WROOM-1U-N16R2 (Espressif) | C3013945 | Extended | 2,455 | new (Task 9) | 2026-10-18 |
| U2 | LM74700-Q1 | LM74700QDDFRQ1 (Texas Instruments) | C3236229 | Extended | 180 | new (Task 9) | 2026-10-18 |
| U3 | LSM6DS3TR-C | LSM6DS3TR-C (STMicroelectronics) | C967633 | Extended | 14,183 | v2 | 2026-10-18 |
| U4 | TJA1051T/3 | TJA1051T/3,118 (NXP) | C58988 | Extended | 6,255 | v2 | 2026-10-18 |
| U5 | TJA1027T/20 | TJA1027T/20,118 (NXP) | C112994 | Extended | 23 | v2 | 2026-10-18 |
| U6 | TPS2553DBV | TPS2553DBVR (Texas Instruments) | C55266 | Extended | 53,261 | new (Task 9) | 2026-10-18 |
| U7 | LMR36520ADDAR | LMR36520ADDAR (Texas Instruments) | C2879422 | Extended | 7,712 | new (Task 9) | 2026-10-18 |
| U8 | AP7361C-33E | AP7361C-33E-13 (Diodes Incorporated) | C500795 | Extended | 575 | v2 | 2026-10-18 |
| U9 | USBLC6-2SC6 | USBLC6-2SC6 (STMicroelectronics) | C7519 | Extended | 34,585 | v2 | 2026-10-18 |
| U10, U11, U12, U13 | BTS7008-2EPA | BTS7008-2EPA (Infineon) | C534830 | Extended | 3,207 | new (Task 9) | 2026-10-18 |
| U14 | PCA9555PW | PCA9555PW,118 (NXP) | C128392 | Extended | 15,079 | new (Task 9) | 2026-10-18 |
| U15, U16 | 74HCT245PW | 74HCT245PW,118 (Nexperia) | C5980 | Extended | 253 | v2 | 2026-10-18 |

### Notes

- **J2** (Würth 7461059 M6 stud) is listed at JLC (C5525467) with 0 stock: we fit it by hand.
  The model marks it with `(hand-fit)` in `mpn`; `test_bom.py` lets only J1/J2 carry that mark.
- **J1** (TE 6437288-1 Superseal, THT) is at JLC (C574787) with only 14 in stock, about $18.65 each.
  If it runs out before the order, hand-fit it too: change the `mpn` to `6437288-1 (hand-fit)`
  and clear `lcsc`.
- Low stock (1 per board, fine for a 5-board run, check again at order time): U2 LM74700QDDFRQ1 (180),
  U5 TJA1027T/20 (23), U15/U16 74HCT245PW (253, 2 per board), U8 AP7361C (575), L1 SRN6045TA-100M (798).
- **BTS7008-2EPA**: the JLC listing with Infineon's full order code (BTS70082EPAXUMA1, C2150060)
  has 0 stock. The listing with the short name (C534830) is the same part and has 3,207.
- **Q1/Q2**: same story. BSC016N06NSATMA1 (C150938) has 0 stock. C454269 "BSC016N06NS" (TDSON-8FL) has 10,577.
- **C21..C32 10 nF**: C57112 is FH 0603B103K500NT (50 V X7R). The model used to say Samsung CL10B103KB8NNNC.
  Changed the MPN to match the code.

## Logic buck: LMR36520 instead of AP63200

The SMCJ24CA input TVS clamps at 38.9 V at peak pulse current. That is above the AP63200's VIN abs
max (~35 V) on VBUS. U7 is now the TI **LMR36520ADDAR** (C2879422, 7,712 in stock, $1.20). It is a
synchronous buck: VIN 4.2-65 V, abs max 70 V, 2 A, 400 kHz, PFM at light load, internal compensation,
HSOIC-8 (datasheet SNVSBF0C, Nov 2025). External parts come from Fig 8-1 / Table 8-1 (5 V row):

- 10 µH (Bourns SRN6045TA-100M, Isat 4.6 A ≥ ISC 3.6 A max)
- 2 × 22 µF out
- FB divider 100k / 22.6k → 5.42 V (VREF 1 V)
- 10 µF 50 V + 220 nF 100 V in
- 100 nF BOOT cap
- 1 µF VCC cap
- PG left open

The symbol `da3:LMR36520ADDA` is a copy of KiCad's LMR36510ADDA (the datasheet says the two are
pin-to-pin compatible). It is checked against Table 5-1 by `test_lmr36520_pinout_per_datasheet`.
Shutdown current is 5.3 µA typ at EN = 0 V, and EN has no internal pull-up (2.7 nA leakage).
R7 holds EN at 0 V, so the buck adds about 5 µA to the stud current in sleep.

The EN pin must not exceed VIN + 0.3 V (Recommended Operating Conditions, note 2). On USB-only power
HOLD can be at 3.3 V while VBUS is ~0 V. R19 (10k, PWR_EN → EN) limits what EN can push into VIN
to ~0.25 mA. Firmware should still keep HOLD low when VBAT_SENSE shows no battery.

Footprint is KiCad `Texas_HTSOP-8-1EP_..._EP2.95x4.9mm_Mask2.4x3.1mm_ThermalVias`, the default of
KiCad's LMR3x DDA symbols. TI's DDA0008B example layout has a 2.71 × 3.4 mm mask opening on the EP.
KiCad's is 2.4 × 3.1 mm, so slightly less pad is soldered. Fine for this load, but look at it during layout.
