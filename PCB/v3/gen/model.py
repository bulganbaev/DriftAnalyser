"""Design model: every part and every pin's net. Source of truth for sch + pcb."""
from dataclasses import dataclass, field
from gen import pinmap

@dataclass
class Part:
    ref: str
    value: str
    symbol: str
    footprint: str
    pins: dict
    sheet: str
    lcsc: str = ""
    mpn: str = ""
    mfr: str = ""
    rot: int = 0
    dnp: bool = False

POWER_NETS = ("VIN", "VBUS", "GND", "5V", "5V_SENS", "3V3")

PARTS: list = []

def _add(*parts):
    PARTS.extend(parts)

def R(ref, value, n1, n2, sheet, size="0603", lcsc="", mpn="", mfr=""):
    fp = {"0402": "Resistor_SMD:R_0402_1005Metric", "0603": "Resistor_SMD:R_0603_1608Metric",
          "0805": "Resistor_SMD:R_0805_2012Metric", "1206": "Resistor_SMD:R_1206_3216Metric",
          "2512": "Resistor_SMD:R_2512_6332Metric"}[size]
    return Part(ref, value, "Device:R", fp, {"1": n1, "2": n2}, sheet, lcsc, mpn, mfr)

def C(ref, value, n1, n2, sheet, size="0603", lcsc="", mpn="", mfr=""):
    fp = {"0402": "Capacitor_SMD:C_0402_1005Metric", "0603": "Capacitor_SMD:C_0603_1608Metric",
          "0805": "Capacitor_SMD:C_0805_2012Metric", "1210": "Capacitor_SMD:C_1210_3225Metric"}[size]
    return Part(ref, value, "Device:C", fp, {"1": n1, "2": n2}, sheet, lcsc, mpn, mfr)

def nets():
    out = {}
    for p in PARTS:
        for pin, net in p.pins.items():
            if net != "NC":
                out.setdefault(net, []).append((p.ref, pin))
    return out

def by_ref(ref):
    return next(p for p in PARTS if p.ref == ref)

def parts_on(sheet):
    return [p for p in PARTS if p.sheet == sheet]

# ---------------- power sheet ----------------
# Stud -> TVS -> LM74700-Q1 ideal diode (VIN -> VBUS) -> buck 12->5 V -> LDO 3V3.
# Buck EN (PWR_EN) = IGN (divided) OR HOLD (GPIO41); 100k pull-downs so a blank board sleeps.
_FET = dict(symbol="Transistor_FET:Q_NMOS_SSSGD_AvalancheRated", footprint="Package_TO_SOT_SMD:TDSON-8-1")
_add(
    # Wurth 7461059 M6 stud, single pad = +12 V in. GND returns through J1 (Task 7).
    Part("J2", "Stud_M6", "Connector_Generic:Conn_01x01", "da3:Stud_M6",
         {"1": "VIN"}, "power", mpn="7461059", mfr="Wurth"),
    # Bidirectional TVS per LM74700-Q1 SNOSD17G Fig 10-2 (12 V battery, single bi-dir TVS).
    # SMCJ24CA: VBR 26.7 V min > 24 V jump start; 1500 W SMC.
    Part("D1", "SMCJ24CA", "Device:D_TVS", "Diode_SMD:D_SMC",
         {"1": "VIN", "2": "GND"}, "power", mpn="SMCJ24CA", mfr="Littelfuse"),
    C("C1", "100nF 50V", "VIN", "GND", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),  # CIN >= 22 nF (SNOSD17G 10.1.1.2.3)

    # LM74700-Q1 (TI SNOSD17G, Dec 2020), DDF SOT-23-8: 1 EN, 2 GND, 3 NC, 4 VCAP, 5 ANODE,
    # 6 GATE, 7 NC, 8 CATHODE. EN tied to ANODE as in Fig 10-2 (always on, IQ 80 uA typ).
    Part("U2", "LM74700-Q1", "da3:LM74700-Q1", "Package_TO_SOT_SMD:SOT-23-8",
         {"1": "VIN", "2": "GND", "3": "NC", "4": "LM_VCAP", "5": "VIN", "6": "LM_GATE",
          "7": "NC", "8": "VBUS"},
         "power", mpn="LM74700QDDFRQ1", mfr="Texas Instruments"),
    # VCAP >= 10 x Ciss (SNOSD17G 10.1.1.2.3): 2 x 5.2 nF typ / 6.5 nF max (BSC016N06NS)
    # -> >= 130 nF worst case, use 220 nF. Cap sits VCAP-ANODE (VCAP-ANODE abs max 15 V).
    C("C2", "220nF 25V", "LM_VCAP", "VIN", "power", "0603"),
    # BSC016N06NS (Infineon OptiMOS 5, datasheet Rev 2.6 2025-05-11): 60 V (TI SNOSD17G
    # 10.1.1.2.2 recommends 60 V: ISO 7637 pulse 1 puts TVS clamp + VBUS ~55 V across the FET),
    # RDS(on) 1.4/1.6 mOhm @10 V, 1.9/2.4 mOhm @6 V, VGS +-20 V (LM74700 drives <= 13 V),
    # Vth 2.1/2.8/3.3 V, Ciss 5.2 nF typ, PG-TDSON-8. Pins 1-3 S, 4 G, 5-8 + tab D -> KiCad
    # TDSON-8-1 pad 5 = drain. Source on VIN (anode), drain on VBUS (cathode); two in parallel.
    Part("Q1", "BSC016N06NS", pins={"1": "VIN", "2": "VIN", "3": "VIN", "4": "LM_GATE", "5": "VBUS"},
         sheet="power", mpn="BSC016N06NSATMA1", mfr="Infineon", **_FET),
    Part("Q2", "BSC016N06NS", pins={"1": "VIN", "2": "VIN", "3": "VIN", "4": "LM_GATE", "5": "VBUS"},
         sheet="power", mpn="BSC016N06NSATMA1", mfr="Infineon", **_FET),
    # COUT: 47 uF typ in Fig 10-2; v2 bulk + MLCC.
    Part("C3", "100uF 50V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10.5",
         {"1": "VBUS", "2": "GND"}, "power", lcsc="C2983550", mpn="GVZ1H107M0810CNVC", mfr="HRK"),
    C("C4", "10uF 50V", "VBUS", "GND", "power", "1210", lcsc="C2918502", mpn="CS3225X7R106K500NRL", mfr="SAMWHA"),

    # battery sense, as v2: 47k/10k from VBUS -> 16 V = 2.81 V; BAT54S clamp to GND/3V3.
    R("R1", "47k", "VBUS", "VBAT_SENSE", "power", "0603", lcsc="C25819", mpn="0603WAF4702T5E", mfr="UNI-ROYAL"),
    R("R2", "10k", "VBAT_SENSE", "GND", "power", "0603", lcsc="C25804", mpn="0603WAF1002T5E", mfr="UNI-ROYAL"),
    C("C5", "100nF", "VBAT_SENSE", "GND", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),
    # BAT54S (KiCad Diode:BAT54S, SOT-23): 1 = A of lower diode, 2 = K of upper diode, 3 = common.
    Part("D2", "BAT54S", "Diode:BAT54S", "Package_TO_SOT_SMD:SOT-23",
         {"1": "GND", "2": "3V3", "3": "VBAT_SENSE"}, "power", mpn="BAT54S", mfr="Nexperia"),

    # ignition detect (GPIO40, digital): 100k/47k -> 9 V = 2.88 V > VIH 2.475 V (0.75 x 3.3 V,
    # ESP32-S3 datasheet DC characteristics); higher IGN clamped by BAT54S to 3V3 / GND.
    R("R3", "100k", "IGN", "IGN_DET", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),
    R("R4", "47k", "IGN_DET", "GND", "power", "0603", lcsc="C25819", mpn="0603WAF4702T5E", mfr="UNI-ROYAL"),
    C("C6", "100nF", "IGN_DET", "GND", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),
    Part("D3", "BAT54S", "Diode:BAT54S", "Package_TO_SOT_SMD:SOT-23",
         {"1": "GND", "2": "3V3", "3": "IGN_DET"}, "power", mpn="BAT54S", mfr="Nexperia"),

    # wake: PWR_EN = (IGN via 100k/33k) OR HOLD, each through a BAT54W.
    # AP63200 (Diodes DS41322): EN abs max 35 V, VEN_H 1.18 V typ / 1.23 V max, internal 1.5 uA pull-up.
    # With R7 100k load: IGN 9 V -> EN ~1.6 V (on), 24 V -> ~4.6 V; HOLD 3.3 V -> ~3.0 V.
    # 1.5 uA x 100k = 0.15 V < VEN_L 1.05 V, so with IGN off and HOLD low the buck is off (ISHDN 1 uA).
    R("R5", "100k", "IGN", "IGN_EN", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),
    R("R6", "33k", "IGN_EN", "GND", "power", "0603"),
    # BAT54W (KiCad Diode:BAT54W, SOT-323): 1 A, 2 NC, 3 K - as v2 D2.
    Part("D4", "BAT54W", "Diode:BAT54W", "Package_TO_SOT_SMD:SOT-323_SC-70",
         {"1": "IGN_EN", "2": "NC", "3": "PWR_EN"}, "power", lcsc="C77328", mpn="BAT54W", mfr="JSCJ"),
    Part("D5", "BAT54W", "Diode:BAT54W", "Package_TO_SOT_SMD:SOT-323_SC-70",
         {"1": "HOLD", "2": "NC", "3": "PWR_EN"}, "power", lcsc="C77328", mpn="BAT54W", mfr="JSCJ"),
    R("R7", "100k", "PWR_EN", "GND", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),
    R("R8", "100k", "HOLD", "GND", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),  # blank flash -> HOLD low -> sleep

    # logic buck 12 V -> 5.4 V: v2 U3 design unchanged (AP63200WU-7, symbol pins 1 FB, 2 EN,
    # 3 IN, 4 GND, 5 SW, 6 BST; FB 57.6k/10k), EN now from PWR_EN.
    Part("U7", "AP63200WU-7", "Regulator_Switching:AP63200WU", "Package_TO_SOT_SMD:TSOT-23-6",
         {"1": "BUCK_FB", "2": "PWR_EN", "3": "VBUS", "4": "GND", "5": "BUCK_SW", "6": "BUCK_BST"},
         "power", lcsc="C2071868", mpn="AP63200WU-7", mfr="Diodes Incorporated"),
    C("C7", "10uF 50V", "VBUS", "GND", "power", "1210", lcsc="C2918502", mpn="CS3225X7R106K500NRL", mfr="SAMWHA"),
    C("C8", "100nF", "BUCK_SW", "BUCK_BST", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),
    Part("L1", "6.8uH", "Device:L", "Inductor_SMD:L_Bourns_SRN6045TA",
         {"1": "BUCK_SW", "2": "5V_BUCK"}, "power", lcsc="C341066", mpn="YNR6045-6R8M", mfr="YJYCOIN"),
    C("C9", "22uF 10V", "5V_BUCK", "GND", "power", "0805", lcsc="C45783", mpn="CL21A226MAQNNNE", mfr="Samsung Electro-Mechanics"),
    C("C10", "22uF 10V", "5V_BUCK", "GND", "power", "0805", lcsc="C45783", mpn="CL21A226MAQNNNE", mfr="Samsung Electro-Mechanics"),
    R("R9", "57.6k", "5V_BUCK", "BUCK_FB", "power", "0603", lcsc="C2933240", mpn="FRC0603F5762TS", mfr="FOJAN"),
    R("R10", "10k", "BUCK_FB", "GND", "power", "0603", lcsc="C25804", mpn="0603WAF1002T5E", mfr="UNI-ROYAL"),
    # OR-ing into 5V as v2 D3; USB-C VBUS_USB has its own SS34 (D8, mcu sheet).
    Part("D6", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA",
         {"1": "5V", "2": "5V_BUCK"}, "power", lcsc="C8678", mpn="SS34", mfr="MDD"),
    C("C11", "22uF 10V", "5V", "GND", "power", "0805", lcsc="C45783", mpn="CL21A226MAQNNNE", mfr="Samsung Electro-Mechanics"),

    # 3V3 LDO: v2 U4 unchanged. AP7361C-33E SOT223 per Diodes DS37274 Rev 5-2: 1 IN, 2 GND, 3 OUT.
    Part("U8", "AP7361C-33E", "da3:AP7361C-33E", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
         {"1": "5V", "2": "GND", "3": "3V3"}, "power", lcsc="C500795", mpn="AP7361C-33E-13", mfr="Diodes Incorporated"),
    C("C12", "10uF", "5V", "GND", "power", "0805", lcsc="C15850", mpn="CL21A106KAYNNNE", mfr="Samsung Electro-Mechanics"),
    C("C13", "10uF", "3V3", "GND", "power", "0805", lcsc="C15850", mpn="CL21A106KAYNNNE", mfr="Samsung Electro-Mechanics"),

    # sensor 5 V: TPS2553DBV (TI SLVS841F): 1 IN, 2 GND, 3 EN (active high), 4 /FAULT, 5 ILIM, 6 OUT.
    # RILIM 210k -> IOS 110/130/150 mA (Electrical Characteristics table); IN cap >= 0.1 uF.
    Part("U6", "TPS2553DBV", "da3:TPS2553DBV", "Package_TO_SOT_SMD:SOT-23-6",
         {"1": "5V", "2": "GND", "3": "SENS_5V_EN", "4": "SENS_5V_FLT", "5": "SENS_ILIM", "6": "5V_SENS_SW"},
         "power", mpn="TPS2553DBVR", mfr="Texas Instruments"),
    # reverse block: a harness short of 5V_SENS to +12 V must not back-drive U6 (OUT abs max 7 V).
    # SS34 40 V / 3 A; ~0.3 V drop at 100 mA -> ~4.7 V at the sensor.
    Part("D7", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA",
         {"1": "5V_SENS", "2": "5V_SENS_SW"}, "power", lcsc="C8678", mpn="SS34", mfr="MDD"),
    R("R11", "210k", "SENS_ILIM", "GND", "power", "0603"),
    # off until firmware enables; 10k, not 100k: PCA9555 P17 has an internal pull-up (>= 55k), see outputs sheet
    R("R12", "10k", "SENS_5V_EN", "GND", "power", "0603", lcsc="C25804", mpn="0603WAF1002T5E", mfr="UNI-ROYAL"),
    R("R13", "100k", "SENS_5V_FLT", "3V3", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),
    C("C14", "100nF", "5V", "GND", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),
    C("C15", "1uF", "5V_SENS", "GND", "power", "0603", lcsc="C15849", mpn="CL10A105KB8NNNC", mfr="Samsung Electro-Mechanics"),
)

# ---------------- outputs sheet ----------------
# 4 x BTS7008-2EPA (Infineon PROFET+2 12V dual, datasheet Rev 1.21 2024-07-29). Pin table p.6 Table 2:
# EP VS (symbol pin 15), 1 GND, 2 IN0, 6 IN1, 3 DEN, 4 IS, 5 DSEL, 7/11 n.c., 12-14 OUT0, 8-10 OUT1.
# External parts per p.55 Table 24: RIN/RDEN/RDSEL 4.7k (needed to switch off on loss of ground, protect the
# driver), CVS 100 nF, COUT 10 nF per output (ESD/BCI), RSENSE 1.2k. RGND 47R / CVSGND skipped: the ideal diode
# (U2) blocks reverse battery and the strips are not inductive loads; GND pin straight to GND.
# Pull-downs are 10k, not 100k: PCA9555 inputs have an internal pull-up to VDD (NXP PCA9555 Rev 10 p.8 6.2/6.4,
# ILIL <= 100 uA p.18 -> >= 55k), 100k/55k would sit ~2.1 V > VDI(TH) max 2 V (BTS p.14 P_5.4.0.1) at reset.
# 10k -> <= 0.51 V < VDI(TH) min 0.8 V, so every switch is off until firmware writes the expander.
_R10K = dict(lcsc="C25804", mpn="0603WAF1002T5E", mfr="UNI-ROYAL")
_R4K7 = dict(lcsc="C23162", mpn="0603WAF4701T5E", mfr="UNI-ROYAL")
_C100N = dict(lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO")
_C10N = dict(lcsc="C57112", mpn="CL10B103KB8NNNC", mfr="Samsung Electro-Mechanics")
_ri, _ci = iter(range(20, 100)), iter(range(20, 100))

def _ro(value, n1, n2, **kw):
    return R(f"R{next(_ri)}", value, n1, n2, "outputs", "0603", **kw)

def _co(value, n1, n2, **kw):
    return C(f"C{next(_ci)}", value, n1, n2, "outputs", "0603", **kw)

for _i in range(1, 9):
    _add(_ro("10k", f"LED{_i}_IN", "GND", **_R10K), _ro("4.7k", f"LED{_i}_IN", f"LED{_i}_IN_R", **_R4K7))
_add(_ro("10k", "DSEL", "GND", **_R10K))
for _k in range(1, 5):
    _a, _b = 2 * _k - 1, 2 * _k
    _add(
        Part(f"U{9 + _k}", "BTS7008-2EPA", "da3:BTS7008-2EPA", "da3:PG-TSDSO-14",
             {"1": "GND", "2": f"LED{_a}_IN_R", "3": f"DEN{_k}_R", "4": "LED_ISENSE_RAW", "5": f"DSEL_R{_k}",
              "6": f"LED{_b}_IN_R", "7": "NC", "8": f"LED{_b}_12V", "9": f"LED{_b}_12V", "10": f"LED{_b}_12V",
              "11": "NC", "12": f"LED{_a}_12V", "13": f"LED{_a}_12V", "14": f"LED{_a}_12V", "15": "VBUS"},
             "outputs", mpn="BTS70082EPAXUMA1", mfr="Infineon"),
        _ro("10k", f"DEN{_k}", "GND", **_R10K), _ro("4.7k", f"DEN{_k}", f"DEN{_k}_R", **_R4K7),
        _ro("4.7k", "DSEL", f"DSEL_R{_k}", **_R4K7),
        _co("100nF", "VBUS", "GND", **_C100N),
        _co("10nF 50V", f"LED{_a}_12V", "GND", **_C10N), _co("10nF 50V", f"LED{_b}_12V", "GND", **_C10N),
    )

# Shared current sense. IS is high-Z while DEN is low (BTS p.42 ch.9, IIS(OFF) <= 0.5 uA P_9.6.0.2), so firmware
# raises one DENk and picks the channel with DSEL; the four IS pins share one RSENSE (p.42: > 820 R, typ 1.2k).
# kILIS 5450 (p.53 Table 22): 5 A -> 1.10 V, 2 x IL(NOM) 15 A -> 3.3 V. IIS(FAULT) 4.4..10 mA (p.51 P_9.6.1.1)
# -> 5.3..12 V on LED_ISENSE_RAW: 4.7k (RIS_PROT, Table 24) + BAT54S clamp keep the ADC pin in 3V3 + 0.3 V,
# ~1.8 mA worst case into 3V3. 4.7k x 10 nF = 47 us (Table 24: RADC x CSENSE > 1 us).
_add(
    _ro("1.2k", "LED_ISENSE_RAW", "GND", lcsc="C22765", mpn="0603WAF1201T5E", mfr="UNI-ROYAL"),
    _ro("4.7k", "LED_ISENSE_RAW", "LED_ISENSE", **_R4K7),
    _co("10nF", "LED_ISENSE", "GND", **_C10N),
    Part("D10", "BAT54S", "Diode:BAT54S", "Package_TO_SOT_SMD:SOT-23",
         {"1": "GND", "2": "3V3", "3": "LED_ISENSE"}, "outputs", mpn="BAT54S", mfr="Nexperia"),
)

# PCA9555PW (NXP Rev 10, p.5 Table 3, TSSOP24): 1 INT (open-drain), 2 A1, 3 A2, 4-11 IO0_0..7, 12 VSS,
# 13-20 IO1_0..7, 21 A0, 22 SCL, 23 SDA, 24 VDD. A0..A2 = GND -> 0x20. No reset pin: internal POR (p.8 6.3),
# all ports come up as inputs. The bus pull-ups live here (only ones on I2C; Task 6 must not add more).
def _exp_pin(port):
    return str((4 if port[1] == "0" else 13) + int(port[2]))

_add(
    Part("U14", "PCA9555PW", "da3:PCA9555", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm",
         {"1": "EXP_INT", "2": "GND", "3": "GND", "12": "GND", "21": "GND", "22": "I2C_SCL", "23": "I2C_SDA",
          "24": "3V3", **{_exp_pin(p): net for p, net in pinmap.EXP.items()}},
         "outputs", mpn="PCA9555PW,118", mfr="NXP"),
    _co("100nF", "3V3", "GND", **_C100N),
    _ro("10k", "EXP_INT", "3V3", **_R10K),
    _ro("4.7k", "I2C_SDA", "3V3", **_R4K7), _ro("4.7k", "I2C_SCL", "3V3", **_R4K7),
)

# Data: 74HCT245 3V3 -> 5 V as v2 (symbol 74xx:74HC245, same pinout: 1 DIR, 2-9 A0-A7, 10 GND, 11-18 B7-B0,
# 19 ~OE, 20 VCC). DIR high = A -> B, ~OE low. 4 lines per buffer, spare A inputs to GND.
# Then 33R series + PESD5V0S1BA per line (v2 pattern; Device:D_TVS stands in, no PESD symbol in KiCad).
for _u, _first in (("U15", 1), ("U16", 5)):
    _p = {"1": "5V", "10": "GND", "19": "GND", "20": "5V"}
    for _j in range(8):
        _p[str(2 + _j)] = f"LED{_first + _j}_DATA" if _j < 4 else "GND"
        _p[str(18 - _j)] = f"LED{_first + _j}_BUF" if _j < 4 else "NC"
    _add(Part(_u, "74HCT245PW", "74xx:74HC245", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", _p,
              "outputs", lcsc="C5980", mpn="74HCT245PW,118", mfr="Nexperia"),
         _co("100nF", "5V", "GND", **_C100N))
for _i in range(1, 9):
    _add(_ro("33", f"LED{_i}_BUF", f"LED{_i}_DO", lcsc="C23140", mpn="0603WAF330JT5E", mfr="UNI-ROYAL"),
         Part(f"D{10 + _i}", "PESD5V0S1BA", "Device:D_TVS", "Diode_SMD:D_SOD-323",
              {"1": f"LED{_i}_DO", "2": "GND"}, "outputs", lcsc="C19224", mpn="PESD5V0S1BA,115", mfr="Nexperia"))

# ---------------- mcu sheet ----------------
# ESP32-S3-WROOM-1U-N16R2: same pinout as WROOM-1 (Espressif WROOM-1/1U datasheet "Pin Definitions"),
# u.FL antenna -> no PCB keep-out. KiCad has no -1U symbol: WROOM-1 symbol + RF_Module:ESP32-S3-WROOM-1U
# footprint. Every GPIO pad comes from pinmap; the rest is power or NC.
# IO3/IO45/IO46 are straps left floating (internal defaults), IO48 is spare.
_U1 = {"1": "GND", "2": "3V3", "3": "EN", "40": "GND", "41": "GND",
       **{pinmap.module_pin(g): net for g, net in pinmap.GPIO.items()}}
_U1.update({str(n): "NC" for n in range(4, 40) if str(n) not in _U1})
_add(
    Part("U1", "ESP32-S3-WROOM-1U-N16R2", "RF_Module:ESP32-S3-WROOM-1", "RF_Module:ESP32-S3-WROOM-1U",
         _U1, "mcu", mpn="ESP32-S3-WROOM-1U-N16R2", mfr="Espressif"),
    # v2 support parts: 22 uF + 100 nF on 3V3, EN RC 10k/1 uF (Espressif: RC delay on CHIP_PU),
    # BOOT (IO0) 10k pull-up, both buttons to GND.
    C("C16", "22uF 10V", "3V3", "GND", "mcu", "0805", lcsc="C45783", mpn="CL21A226MAQNNNE", mfr="Samsung Electro-Mechanics"),
    C("C17", "100nF", "3V3", "GND", "mcu", "0603", **_C100N),
    R("R14", "10k", "3V3", "EN", "mcu", "0603", **_R10K),
    C("C18", "1uF", "EN", "GND", "mcu", "0603", lcsc="C15849", mpn="CL10A105KB8NNNC", mfr="Samsung Electro-Mechanics"),
    R("R15", "10k", "3V3", "BOOT", "mcu", "0603", **_R10K),
    Part("SW1", "BOOT", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
         {"1": "BOOT", "2": "GND"}, "mcu", lcsc="C221880", mpn="PTS645SM43SMTR92LFS", mfr="C&K"),
    Part("SW2", "EN", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
         {"1": "EN", "2": "GND"}, "mcu", lcsc="C221880", mpn="PTS645SM43SMTR92LFS", mfr="C&K"),

    # status LED on PCA9555 P16 (push-pull, 3V3): (3.3 - ~2 V) / 1k ~ 1.3 mA.
    Part("D9", "GREEN", "Device:LED", "LED_SMD:LED_0603_1608Metric",
         {"1": "GND", "2": "STATUS_LED_A"}, "mcu", lcsc="C22371299", mpn="PSC-1608U49GC-G4", mfr="HONGLITRONIC"),
    R("R16", "1k", "STATUS_LED", "STATUS_LED_A", "mcu", "0603", lcsc="C21190", mpn="0603WAF1001T5E", mfr="UNI-ROYAL"),

    # USB-C, flashing only (inside the case), v2 pattern. Connector:USB_C_Receptacle_USB2.0_16P pins A1..B12 + SH.
    # VBUS_USB, not VBUS (that is the 12 V bus). 5.1k Rd on CC1/CC2 -> sink, 5 V default.
    Part("J3", "USB-C 16P", "Connector:USB_C_Receptacle_USB2.0_16P",
         "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
         {"A1": "GND", "A4": "VBUS_USB", "A5": "USB_CC1", "A6": "USB_DP", "A7": "USB_DN", "A8": "NC",
          "A9": "VBUS_USB", "A12": "GND", "B1": "GND", "B4": "VBUS_USB", "B5": "USB_CC2", "B6": "USB_DP",
          "B7": "USB_DN", "B8": "NC", "B9": "VBUS_USB", "B12": "GND", "SH": "GND"},
         "mcu", lcsc="C2765186", mpn="TYPE-C 16PIN 2MD(073)", mfr="SHOU HAN"),
    R("R17", "5.1k", "USB_CC1", "GND", "mcu", "0603", lcsc="C23186", mpn="0603WAF5101T5E", mfr="UNI-ROYAL"),
    R("R18", "5.1k", "USB_CC2", "GND", "mcu", "0603", lcsc="C23186", mpn="0603WAF5101T5E", mfr="UNI-ROYAL"),
    # USBLC6-2SC6 (Power_Protection symbol): 1/6 I/O1, 3/4 I/O2, 2 GND, 5 VBUS.
    Part("U9", "USBLC6-2SC6", "Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
         {"1": "USB_DN", "2": "GND", "3": "USB_DP", "4": "USB_DP", "5": "VBUS_USB", "6": "USB_DN"},
         "mcu", lcsc="C7519", mpn="USBLC6-2SC6", mfr="STMicroelectronics"),
    # USB alone powers the logic for flashing: OR-ed into 5V like D6 from the buck (v2 D4).
    Part("D8", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA",
         {"1": "5V", "2": "VBUS_USB"}, "mcu", lcsc="C8678", mpn="SS34", mfr="MDD"),

    # UART0 debug header (GPIO43/44), v2 J3.
    Part("J4", "UART0", "Connector_Generic:Conn_01x04", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
         {"1": "3V3", "2": "GND", "3": "UART0_TX", "4": "UART0_RX"}, "mcu",
         lcsc="C2691448", mpn="PZ254V-11-04P", mfr="XFCN"),

    # IMU, v2 U5 unchanged. LSM6DS3TR-C LGA-14 (ST DS11224 table 2): 1 SDO/SA0, 2 SDx, 3 SCx, 4 INT1,
    # 5 VDDIO, 6/7 GND, 8 VDD, 9 INT2, 10/11 NC, 12 CS, 13 SCL, 14 SDA. CS high = I2C, SA0 low -> 0x6A
    # (no clash with PCA9555 0x20). SDx/SCx unused in I2C mode, tied to GND per table 2.
    # Bus pull-ups are on the outputs sheet.
    Part("U3", "LSM6DS3TR-C", "da3:LSM6DS3TR-C", "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
         {"1": "GND", "2": "GND", "3": "GND", "4": "IMU_INT1", "5": "3V3", "6": "GND", "7": "GND",
          "8": "3V3", "9": "NC", "10": "NC", "11": "NC", "12": "3V3", "13": "I2C_SCL", "14": "I2C_SDA"},
         "mcu", lcsc="C967633", mpn="LSM6DS3TR-C", mfr="STMicroelectronics"),
    C("C19", "100nF", "3V3", "GND", "mcu", "0603", **_C100N),  # VDD
    C("C36", "100nF", "3V3", "GND", "mcu", "0603", **_C100N),  # VDDIO
)

# ---------------- comms sheet ----------------
_rc, _cc = iter(range(70, 100)), iter(range(40, 60))

def _rk(value, n1, n2, size="0603", **kw):
    return R(f"R{next(_rc)}", value, n1, n2, "comms", size, **kw)

def _ck(value, n1, n2, **kw):
    return C(f"C{next(_cc)}", value, n1, n2, "comms", "0603", **kw)

# CAN, v2 U8. Interface_CAN_LIN:TJA1051T-3: 1 TXD, 2 GND, 3 VCC, 4 RXD, 5 VIO, 6 CANL, 7 CANH, 8 S.
# S on PCA9555 P15 (CAN_S) with 10k pull-up: high = silent / listen-only (TJA1051 datasheet: S high -> silent
# mode, transmitter off), so the board never drives a car bus until firmware pulls S low for normal mode.
# Unpowered (5V off in sleep) the TJA1051 is passive on the bus.
_add(
    Part("U4", "TJA1051T/3", "Interface_CAN_LIN:TJA1051T-3", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
         {"1": "CAN_TX", "2": "GND", "3": "5V", "4": "CAN_RX", "5": "3V3", "6": "CANL", "7": "CANH", "8": "CAN_S"},
         "comms", lcsc="C58988", mpn="TJA1051T/3,118", mfr="NXP"),
    _ck("100nF", "5V", "GND", **_C100N),
    _ck("100nF", "3V3", "GND", **_C100N),
    _rk("10k", "CAN_S", "3V3", **_R10K),
    # 120R terminator through jumper JP2 (v2 R40 + JP1).
    _rk("120", "CANH", "CAN_TERM", "1206", lcsc="C17909", mpn="1206W4F1200T5E", mfr="UNI-ROYAL"),
    Part("JP2", "CAN TERM", "Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
         {"1": "CAN_TERM", "2": "CANL"}, "comms", lcsc="C492401", mpn="PZ254V-11-02P", mfr="XFCN"),
    # PESD1CAN as v2 D20: Device:D_TVS_Dual_AAC, 1 A1, 2 A2, 3 common.
    Part("D20", "PESD1CAN", "Device:D_TVS_Dual_AAC", "Package_TO_SOT_SMD:SOT-23",
         {"1": "CANH", "2": "CANL", "3": "GND"}, "comms", lcsc="C15771", mpn="PESD1CAN,215", mfr="Nexperia"),
)

# K-line, v2 U9. TJA1027T/20 (NXP Rev 3 Table 3, SO8): 1 RXD, 2 SLP_N, 3 n.c., 4 TXD, 5 GND, 6 LIN, 7 VBAT, 8 n.c.
# SLP_N on 3V3: normal mode while the logic is up, sleep when 3V3 drops. RXD is open-drain -> 10k to 3V3.
# 510R K-line pull-up to VBUS only when JP1 is fitted (v2 JP2).
_add(
    Part("U5", "TJA1027T/20", "da3:TJA1027T", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
         {"1": "K_RX", "2": "3V3", "3": "NC", "4": "K_TX", "5": "GND", "6": "KLINE", "7": "VBUS", "8": "NC"},
         "comms", lcsc="C112994", mpn="TJA1027T/20,118", mfr="NXP"),
    _ck("100nF 50V", "VBUS", "GND", **_C100N),
    _rk("10k", "K_RX", "3V3", **_R10K),
    _rk("510 0.5W", "K_PU", "KLINE", "2512", lcsc="C2934121", mpn="FRC2512J511TS", mfr="FOJAN"),
    Part("JP1", "K PULLUP", "Connector_Generic:Conn_01x02", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
         {"1": "VBUS", "2": "K_PU"}, "comms", lcsc="C492401", mpn="PZ254V-11-02P", mfr="XFCN"),
    # SMAJ24A as v2 D21 (24 V jump start): unidirectional, drawn with Device:D_TVS; D_SMA pad 1 = cathode
    # (band) on the line side, pad 2 anode on GND.
    Part("D21", "SMAJ24A", "Device:D_TVS", "Diode_SMD:D_SMA",
         {"1": "KLINE", "2": "GND"}, "comms", lcsc="C148222", mpn="SMAJ24A", mfr="Littelfuse"),
)

# Universal inputs IN1..IN3: J1 - TVS SMAJ24A to GND - 10k series - INn_DIV - 33k - INn_SENSE - 10k - GND.
# INn_PULL (GPIO) - 10k - INn_SENSE (the ADC node): output 1 = pull-up to 3V3, 0 = pull-down, input = no pull
# (INn_SENSE <= 3.02 V at 16 V in, below the pad's ESD clamp, so the hi-Z GPIO draws nothing and the
# analog range stays linear). SMAJ24A (not 18A): stays off at a 24 V jump start.
# Hi-Z: 16 V -> 3.02 V, 12 V -> 2.26 V, 5 V -> 0.94 V on the ADC (11 dB).
# Pull-up: IN open 1.65 V, IN to GND 1.48 V (10k || 43k vs 10k), IN at 12 V 2.73 V.
# Pull-down: IN open 0 V, IN at 12 V 1.25 V (43k vs 10k || 10k).
for _i in range(1, 4):
    _add(
        # unidirectional SMAJ24A drawn with Device:D_TVS: pad 1 = cathode (band) on IN, pad 2 anode on GND
        Part(f"D{21 + _i}", "SMAJ24A", "Device:D_TVS", "Diode_SMD:D_SMA",
             {"1": f"IN{_i}", "2": "GND"}, "comms", lcsc="C148222", mpn="SMAJ24A", mfr="Littelfuse"),
        _rk("10k", f"IN{_i}", f"IN{_i}_DIV", **_R10K),
        _rk("33k", f"IN{_i}_DIV", f"IN{_i}_SENSE", mpn="0603WAF3302T5E", mfr="UNI-ROYAL"),
        _rk("10k", f"IN{_i}_SENSE", "GND", **_R10K),
        _rk("10k", f"IN{_i}_PULL", f"IN{_i}_SENSE", **_R10K),
    )

# ---------------- J1 harness connector (comms sheet) ----------------
# TE 6437288-1 Superseal 1.0, 34 pos, rows 1-9 / 10-17 / 18-25 / 26-34. Key -> pin; "*_GND" keys sit on net GND.
# Strip triplets are 12V | DO | GND so the data line runs between its own supply and return.
# Power in rows 1, 2 (first half) and 4; signals in rows 2-3, each IN / 5V_SENS beside a signal GND.
J1_PIN = {
    **{f"LED{i}_{s}": str(3 * (i - 1) + k + 1) for i in range(1, 6) for k, s in enumerate(("12V", "DO", "GND"))},
    "CANH": "16", "CANL": "17", "KLINE": "18", "IGN": "19", "SIG1_GND": "20", "5V_SENS": "21",
    "IN1": "22", "IN2": "23", "SIG2_GND": "24", "IN3": "25",
    **{f"LED{i}_{s}": str(26 + 3 * (i - 6) + k) for i in range(6, 9) for k, s in enumerate(("12V", "DO", "GND"))},
}

_add(Part("J1", "6437288-1", "da3:TE_6437288-1", "da3:TE_6437288-1",
          {p: ("GND" if k.endswith("_GND") else k) for k, p in J1_PIN.items()},
          "comms", mpn="6437288-1", mfr="TE Connectivity"))
