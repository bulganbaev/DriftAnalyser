"""GPIO / PCA9555 pin map for the v3 board (ESP32-S3-WROOM-1U-N16R2, quad PSRAM)."""

GPIO: dict[int, str] = {
    0: "BOOT",
    1: "VBAT_SENSE",
    2: "LED_ISENSE",
    4: "IN1_SENSE",
    5: "IN2_SENSE",
    6: "IN3_SENSE",
    7: "IN1_PULL",
    8: "I2C_SDA",
    9: "I2C_SCL",
    10: "IN2_PULL",
    11: "LED1_DATA",
    12: "LED2_DATA",
    13: "LED3_DATA",
    14: "LED4_DATA",
    15: "LED5_DATA",
    16: "LED6_DATA",
    17: "LED7_DATA",
    18: "LED8_DATA",
    19: "USB_DN",
    20: "USB_DP",
    21: "IN3_PULL",
    35: "K_TX",
    36: "K_RX",
    37: "EXP_INT",
    38: "CAN_TX",
    39: "CAN_RX",
    40: "IGN_DET",  # not _SENSE: digital input, GPIO40 is not ADC1
    41: "HOLD",
    42: "IMU_INT1",
    43: "UART0_TX",
    44: "UART0_RX",
    47: "SENS_5V_FLT",  # TPS2553 /FAULT (open-drain, R13 pull-up)
}

EXP: dict[str, str] = {
    **{f"P0{i}": f"LED{i + 1}_IN" for i in range(8)},
    **{f"P1{i}": f"DEN{i + 1}" for i in range(4)},
    "P14": "DSEL",
    "P15": "CAN_TERM_EN",
    "P16": "STATUS_LED",
    "P17": "SENS_5V_EN",
}

# Source: KiCad symbol RF_Module:ESP32-S3-WROOM-1 (KiCad 10.0.6 RF_Module.kicad_sym), which
# follows the Espressif ESP32-S3-WROOM-1/1U datasheet "Pin Definitions" (WROOM-1 and -1U share
# the pinout). Cross-checked against v2 U1 pad numbers (PCB/v2/gen/model.py).
_MODULE_PIN: dict[int, str] = {
    4: "4", 5: "5", 6: "6", 7: "7", 15: "8", 16: "9", 17: "10", 18: "11", 8: "12",
    19: "13", 20: "14", 3: "15", 46: "16", 9: "17", 10: "18", 11: "19", 12: "20",
    13: "21", 14: "22", 21: "23", 47: "24", 48: "25", 45: "26", 0: "27",
    35: "28", 36: "29", 37: "30", 38: "31", 39: "32", 40: "33", 41: "34", 42: "35",
    44: "36", 43: "37", 2: "38", 1: "39",
}


def module_pin(gpio: int) -> str:
    return _MODULE_PIN[gpio]
