"""Design model: every part and every pin's net. Source of truth for sch + pcb."""
from dataclasses import dataclass, field

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
    # VCAP >= 10 x Ciss (SNOSD17G 10.1.1.2.3): 2 x 4.6 nF (BSC010N04LS6) -> >= 92 nF, use 220 nF.
    # Cap sits VCAP-ANODE (VCAP-ANODE abs max 15 V).
    C("C2", "220nF 25V", "LM_VCAP", "VIN", "power", "0603"),
    # BSC010N04LS6 (Infineon OptiMOS 6, Rev 2.0 2018-07-31): 40 V, 1.0 mOhm @10 V / 1.4 mOhm @4.5 V,
    # VGS +-20 V (LM74700 drives <= 13 V), Vth 1.3-2.3 V, Ciss 4.6 nF, PG-TDSON-8 FL.
    # Pins 1-3 S, 4 G, 5-8 + tab D -> KiCad TDSON-8-1 pad 5 = drain. Source on VIN (anode),
    # drain on VBUS (cathode); two in parallel for the strip current.
    Part("Q1", "BSC010N04LS6", pins={"1": "VIN", "2": "VIN", "3": "VIN", "4": "LM_GATE", "5": "VBUS"},
         sheet="power", mpn="BSC010N04LS6ATMA1", mfr="Infineon", **_FET),
    Part("Q2", "BSC010N04LS6", pins={"1": "VIN", "2": "VIN", "3": "VIN", "4": "LM_GATE", "5": "VBUS"},
         sheet="power", mpn="BSC010N04LS6ATMA1", mfr="Infineon", **_FET),
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
    # OR-ing into 5V as v2 D3; the USB-C VBUS diode comes with the connector in Task 6.
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
         {"1": "5V", "2": "GND", "3": "SENS_5V_EN", "4": "SENS_5V_FLT", "5": "SENS_ILIM", "6": "5V_SENS"},
         "power", mpn="TPS2553DBVR", mfr="Texas Instruments"),
    R("R11", "210k", "SENS_ILIM", "GND", "power", "0603"),
    R("R12", "100k", "SENS_5V_EN", "GND", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),  # off until firmware enables (PCA9555 powers up as input)
    R("R13", "100k", "SENS_5V_FLT", "3V3", "power", "0603", lcsc="C25803", mpn="0603WAF1003T5E", mfr="UNI-ROYAL"),
    C("C14", "100nF", "5V", "GND", "power", "0603", lcsc="C14663", mpn="CC0603KRX7R9BB104", mfr="YAGEO"),
    C("C15", "1uF", "5V_SENS", "GND", "power", "0603", lcsc="C15849", mpn="CL10A105KB8NNNC", mfr="Samsung Electro-Mechanics"),
)
