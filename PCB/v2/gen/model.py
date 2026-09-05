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

POWER_NETS = ("VBAT", "GND", "12V_LED", "5V", "3V3", "VBUS_USB")

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

# ---- parts are added by sheet below (Tasks 4-7) ----

# ---------------- power sheet ----------------
_add(
    Part("J1", "XT60PW-M", "Connector_Generic:Conn_01x02",
         "Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal",
         {"1": "VBAT", "2": "GND"}, "power", mpn="XT60PW-M", mfr="AMASS"),
    # D_Zener: pin1 = K (cathode), pin2 = A (anode) -> cathode on VBAT clamps to GND on overvoltage
    Part("D1", "SMDJ18A", "Device:D_Zener", "Diode_SMD:D_SMC",
         {"1": "VBAT", "2": "GND"}, "power", mpn="SMDJ18A", mfr="Littelfuse"),
    Part("C1", "100uF 35V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10.5",
         {"1": "VBAT", "2": "GND"}, "power"),
    Part("C2", "100uF 35V", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10.5",
         {"1": "VBAT", "2": "GND"}, "power"),
    C("C3", "10uF 50V", "VBAT", "GND", "power", "1210"),
    C("C4", "10uF 50V", "VBAT", "GND", "power", "1210"),
    C("C5", "10uF 50V", "12V_LED", "GND", "power", "1210"),
    C("C6", "10uF 50V", "12V_LED", "GND", "power", "1210"),

    # strip power switch: BTS7002-1EPP (Infineon PROFET+2 12V, PG-TSDSO-14).
    # Pinout confirmed from Infineon datasheet Rev 1.11 (2024-07-29), Table 2 / Figure 4:
    # 1 GND, 2 IN, 3 DEN, 4 IS, 5-7 n.c., 8-10 OUT, 11 n.c., 12-14 OUT, EP (exposed pad) = VS.
    # Note: pin 11 is n.c. (not an OUT pin) - the brief's "8..14 all OUT" assumption was wrong.
    Part("U2", "BTS7002-1EPP", "da2:BTS7002-1EPP", "da2:PG-TSDSO-14",
         {"1": "GND", "2": "LED_PWR_EN", "3": "DEN", "4": "IS_RAW", "5": "NC", "6": "NC", "7": "NC",
          "8": "12V_LED", "9": "12V_LED", "10": "12V_LED", "11": "NC", "12": "12V_LED",
          "13": "12V_LED", "14": "12V_LED", "15": "VBAT"},
         "power", mpn="BTS7002-1EPP", mfr="Infineon"),
    R("R1", "10k", "LED_PWR_EN", "GND", "power", "0603"),        # switch off until firmware says otherwise
    R("R2", "10k", "DEN", "3V3", "power", "0603"),               # diagnosis always enabled
    R("R5", "470", "IS_RAW", "GND", "power", "0603"),            # IS sense: 30 A -> 0.62 V (kILIS 22700)
    R("R6", "1k", "IS_RAW", "LED_ISENSE", "power", "0603"),
    C("C7", "100nF", "LED_ISENSE", "GND", "power", "0603"),
    # BAT54W (Nexperia): single Schottky, SOT323/SC-70, pin1 = A, pin2 = n.c., pin3 = K.
    # Confirmed against Diode.kicad_sym (pin1 A / pin2 NC / pin3 K, footprint SOT-323_SC-70)
    # and Nexperia BAT54W_SER datasheet Table 2. Clamp: anode on LED_ISENSE, cathode on 3V3.
    Part("D2", "BAT54W", "Diode:BAT54W", "Package_TO_SOT_SMD:SOT-323_SC-70",
         {"1": "LED_ISENSE", "2": "NC", "3": "3V3"}, "power", mpn="BAT54W", mfr="Nexperia"),

    # battery voltage sense: 18 V -> 3.16 V
    R("R7", "47k", "VBAT", "VBAT_SENSE", "power", "0603"),
    R("R8", "10k", "VBAT_SENSE", "GND", "power", "0603"),
    C("C8", "100nF", "VBAT_SENSE", "GND", "power", "0603"),

    # logic buck 12 V -> 5.4 V. Symbol is "AP63200WU" in Regulator_Switching.kicad_sym
    # (the "-7" is a Diodes Inc. tape-and-reel suffix, not part of the symbol name).
    # Pins confirmed from the symbol: 1 FB, 2 EN, 3 IN(VIN), 4 GND, 5 SW, 6 BST.
    Part("U3", "AP63200WU-7", "Regulator_Switching:AP63200WU",
         "Package_TO_SOT_SMD:TSOT-23-6",
         {"1": "BUCK_FB", "2": "BUCK_EN", "3": "VBAT", "4": "GND", "5": "BUCK_SW", "6": "BUCK_BST"},
         "power", mpn="AP63200WU-7", mfr="Diodes Incorporated"),
    C("C9", "10uF 50V", "VBAT", "GND", "power", "1210"),
    C("C10", "100nF", "BUCK_SW", "BUCK_BST", "power", "0603"),
    Part("L1", "6.8uH", "Device:L", "Inductor_SMD:L_Bourns_SRN6045TA",
         {"1": "BUCK_SW", "2": "5V_BUCK"}, "power"),
    C("C11", "22uF 10V", "5V_BUCK", "GND", "power", "0805"),
    C("C12", "22uF 10V", "5V_BUCK", "GND", "power", "0805"),
    R("R3", "57.6k", "5V_BUCK", "BUCK_FB", "power", "0603"),
    R("R4", "10k", "BUCK_FB", "GND", "power", "0603"),
    R("R9", "100k", "VBAT", "BUCK_EN", "power", "0603"),

    # OR-ing into 5V
    Part("D3", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA",
         {"1": "5V", "2": "5V_BUCK"}, "power", mpn="SS34", mfr="MDD"),
    Part("D4", "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA",
         {"1": "5V", "2": "VBUS_USB"}, "power", mpn="SS34", mfr="MDD"),
    C("C13", "22uF 10V", "5V", "GND", "power", "0805"),

    # 3V3 LDO: AP7361C-33E, symbol "Regulator_Linear:AP7361C-33E" exists (extends the
    # generic SPX2920M3-3.3_SOT223 template with NO pin override, so it inherits that
    # template's pin *numbers* 1/2/3 but its generic pin *names* (VI/GND/VO) do not match
    # this chip - see report). Real AP7361C SOT-223 pinout per Diodes datasheet DS37274
    # Rev 5-2 (page 2, Pin Assignments / Pin Descriptions): pin1 OUT, pin2 GND, pin3 IN.
    # Footprint SOT-223-3_TabPin2 -> tab shares pin2 = GND, matching the datasheet's
    # middle-lead-is-GND SOT223 pinout.
    Part("U4", "AP7361C-33E", "Regulator_Linear:AP7361C-33E", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
         {"1": "3V3", "2": "GND", "3": "5V"}, "power", mpn="AP7361C-33E-13", mfr="Diodes Incorporated"),
    C("C14", "10uF", "5V", "GND", "power", "0805"),
    C("C15", "10uF", "3V3", "GND", "power", "0805"),

    # power LED
    Part("D5", "BLUE", "Device:LED", "LED_SMD:LED_0603_1608Metric",
         {"1": "GND", "2": "PWR_LED_A"}, "power"),
    R("R10", "1k", "5V", "PWR_LED_A", "power", "0603"),
)

# ---------------- mcu sheet ----------------
# ESP32-S3-WROOM-1 symbol pin numbers verified against RF_Module.kicad_sym (KiCad 10.0.6):
# they match the datasheet-derived table from Task 3 exactly (1 GND, 2 3V3, 3 EN, 4 IO4 ...
# 36 RXD0, 37 TXD0, 40/41 GND), so the GPIO map below needed no changes.
_add(
    Part("U1", "ESP32-S3-WROOM-1-N16R2", "RF_Module:ESP32-S3-WROOM-1", "RF_Module:ESP32-S3-WROOM-1",
         {"1": "GND", "2": "3V3", "3": "EN",
          "4": "LED1_IN", "5": "LED2_IN", "6": "LED3_IN", "7": "LED4_IN", "8": "LED5_IN", "9": "LED6_IN",
          "10": "IMU_INT1", "11": "CAN_TX", "12": "I2C_SDA", "13": "USB_DN", "14": "USB_DP",
          "15": "NC", "16": "NC", "17": "I2C_SCL", "18": "LED_PWR_EN", "19": "STATUS_LED",
          "20": "K_RX", "21": "K_TX", "22": "CAN_STB", "23": "CAN_RX", "24": "SD_D3", "25": "SD_CD",
          "26": "NC", "27": "BOOT", "28": "UART2_TX", "29": "UART2_RX", "30": "NC",
          "31": "SD_CMD", "32": "SD_CLK", "33": "SD_D0", "34": "SD_D1", "35": "SD_D2",
          "36": "UART0_RX", "37": "UART0_TX", "38": "LED_ISENSE", "39": "VBAT_SENSE",
          "40": "GND", "41": "GND"},
         "mcu", lcsc="C2913205", mpn="ESP32-S3-WROOM-1-N16R2", mfr="Espressif"),
    C("C16", "22uF 10V", "3V3", "GND", "mcu", "0805"),
    C("C17", "100nF", "3V3", "GND", "mcu", "0603"),
    R("R11", "10k", "3V3", "EN", "mcu", "0603"),
    C("C18", "1uF", "EN", "GND", "mcu", "0603"),
    # Switch:SW_Push pins 1/2 confirmed. Button_Switch_SMD:SW_SPST_PTS645 doesn't exist in this
    # KiCad; closest match is SW_SPST_PTS645Sx43SMTR92 (pads 1/2, each duplicated).
    Part("SW1", "EN", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
         {"1": "EN", "2": "GND"}, "mcu"),
    R("R12", "10k", "3V3", "BOOT", "mcu", "0603"),
    Part("SW2", "BOOT", "Switch:SW_Push", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
         {"1": "BOOT", "2": "GND"}, "mcu"),
    Part("D6", "GREEN", "Device:LED", "LED_SMD:LED_0603_1608Metric",
         {"1": "GND", "2": "STATUS_LED_A"}, "mcu"),
    R("R13", "1k", "STATUS_LED", "STATUS_LED_A", "mcu", "0603"),

    # USB-C. Connector:USB_C_Receptacle_USB2.0_16P confirmed: pins A1..B12 plus shield pin "SH"
    # (not "S1" as in the draft brief).
    Part("J2", "USB-C 16P", "Connector:USB_C_Receptacle_USB2.0_16P",
         "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
         {"A1": "GND", "A4": "VBUS_USB", "A5": "USB_CC1", "A6": "USB_DP", "A7": "USB_DN", "A8": "NC",
          "A9": "VBUS_USB", "A12": "GND", "B1": "GND", "B4": "VBUS_USB", "B5": "USB_CC2", "B6": "USB_DP",
          "B7": "USB_DN", "B8": "NC", "B9": "VBUS_USB", "B12": "GND", "SH": "GND"},
         "mcu", lcsc="C2765186", mpn="TYPE-C 16PIN 2MD(073)", mfr="SHOU HAN"),
    R("R14", "5.1k", "USB_CC1", "GND", "mcu", "0603"),
    R("R15", "5.1k", "USB_CC2", "GND", "mcu", "0603"),
    Part("U6", "USBLC6-2SC6", "Power_Protection:USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
         {"1": "USB_DN", "2": "GND", "3": "USB_DP", "4": "USB_DP", "5": "VBUS_USB", "6": "USB_DN"},
         "mcu", mpn="USBLC6-2SC6", mfr="STMicroelectronics"),

    # headers
    Part("J3", "UART0", "Connector_Generic:Conn_01x04", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
         {"1": "3V3", "2": "GND", "3": "UART0_TX", "4": "UART0_RX"}, "mcu"),
    Part("J4", "EXT", "Connector_Generic:Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
         {"1": "3V3", "2": "GND", "3": "UART2_TX", "4": "UART2_RX", "5": "I2C_SDA", "6": "I2C_SCL"}, "mcu"),

    # microSD, SDMMC 4-bit. "Connector:Micro_SD_Card_Det" doesn't exist in this KiCad; closest
    # match with two card-detect pins (needed to put SD_CD on one and GND on the other) is
    # Micro_SD_Card_Det_Hirose_DM3AT, which extends Micro_SD_Card_Det2 (pins 1-10 + shield "SH"),
    # and its ki_fp_filters ("microSD*") matches the chosen Hirose DM3BT footprint family.
    # Pin order confirmed: 1 DAT2, 2 DAT3/CD, 3 CMD, 4 VDD, 5 CLK, 6 VSS, 7 DAT0, 8 DAT1,
    # 9 DET_B, 10 DET_A, SH SHIELD.
    Part("J5", "microSD", "Connector:Micro_SD_Card_Det_Hirose_DM3AT",
         "Connector_Card:microSD_HC_Hirose_DM3BT-DSF-PEJS",
         {"1": "SD_D2", "2": "SD_D3", "3": "SD_CMD", "4": "3V3", "5": "SD_CLK", "6": "GND", "7": "SD_D0",
          "8": "SD_D1", "9": "SD_CD", "10": "GND", "SH": "GND"},
         "mcu"),
    R("R16", "10k", "3V3", "SD_CMD", "mcu", "0603"),
    R("R17", "10k", "3V3", "SD_D0", "mcu", "0603"),
    R("R18", "10k", "3V3", "SD_D1", "mcu", "0603"),
    R("R19", "10k", "3V3", "SD_D2", "mcu", "0603"),
    R("R20", "10k", "3V3", "SD_D3", "mcu", "0603"),
    R("R21", "10k", "3V3", "SD_CD", "mcu", "0603"),
    C("C19", "10uF", "3V3", "GND", "mcu", "0805"),

    # IMU. No Sensor_Motion:LSM6DS3TR-C symbol exists in this KiCad (only generic LSM6DS3/LSM6DSL),
    # so U5 stays a custom symbol (da2:LSM6DS3TR-C, drawn in Task 8). Pin map per LSM6DS3TR-C
    # LGA-14 datasheet DS11224 table 2 (to be reconfirmed in Task 8 when the symbol is drawn):
    # 1 SDO/SA0, 2 SDx, 3 SCx, 4 INT1, 5 VDDIO, 6 GND, 7 GND, 8 VDD, 9 INT2, 10 NC, 11 NC,
    # 12 CS, 13 SCL, 14 SDA.
    Part("U5", "LSM6DS3TR-C", "da2:LSM6DS3TR-C", "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
         {"1": "GND", "2": "NC", "3": "NC", "4": "IMU_INT1", "5": "3V3", "6": "GND", "7": "GND",
          "8": "3V3", "9": "NC", "10": "NC", "11": "NC", "12": "3V3", "13": "I2C_SCL", "14": "I2C_SDA"},
         "mcu", mpn="LSM6DS3TR-C", mfr="STMicroelectronics"),
    C("C20", "100nF", "3V3", "GND", "mcu", "0603"),
    C("C21", "100nF", "3V3", "GND", "mcu", "0603"),
    R("R22", "4.7k", "3V3", "I2C_SDA", "mcu", "0603"),
    R("R23", "4.7k", "3V3", "I2C_SCL", "mcu", "0603"),
)
