import re
from collections import Counter
from gen import model

def test_refs_unique():
    refs = [p.ref for p in model.PARTS]
    dupes = [r for r, c in Counter(refs).items() if c > 1]
    assert not dupes, dupes

def test_every_net_has_two_or_more_pins():
    single = {n: v for n, v in model.nets().items() if len(v) < 2}
    assert not single, single

def test_net_names_are_clean():
    bad = [n for n in model.nets() if not re.fullmatch(r"[A-Z0-9_]+", n)]
    assert not bad, bad

def test_sheets_valid():
    assert {p.sheet for p in model.PARTS} <= {"power", "mcu", "leds", "comms"}

def test_gpio_map_matches_spec():
    mcu = model.by_ref("U1")
    expect = {"4": "LED1_IN", "5": "LED2_IN", "6": "LED3_IN", "7": "LED4_IN", "8": "LED5_IN", "9": "LED6_IN",
              "12": "I2C_SDA", "17": "I2C_SCL", "18": "LED_PWR_EN", "19": "STATUS_LED",
              "20": "K_RX", "21": "K_TX", "22": "CAN_STB", "10": "IMU_INT1", "11": "CAN_TX", "23": "CAN_RX",
              "13": "USB_DN", "14": "USB_DP", "28": "UART2_TX", "29": "UART2_RX",
              "31": "SD_CMD", "32": "SD_CLK", "33": "SD_D0", "34": "SD_D1", "35": "SD_D2", "24": "SD_D3", "25": "SD_CD",
              "37": "UART0_TX", "36": "UART0_RX", "27": "BOOT", "39": "VBAT_SENSE", "38": "LED_ISENSE",
              "15": "NC", "26": "NC", "16": "NC"}
    for pin, net in expect.items():
        assert mcu.pins[pin] == net, (pin, mcu.pins[pin], net)

def test_power_topology():
    n = model.nets()
    assert ("J1", "1") in n["VBAT"] and ("J1", "2") in n["GND"]          # XT60
    assert ("U2", "2") in n["LED_PWR_EN"] and ("U2", "4") in n["IS_RAW"]  # BTS7002 IN, IS
    # BTS7002-1EPP OUT pins per Infineon datasheet Table 2: 8-10,12-14 (pin 11 is n.c., not bonded)
    assert all(("U2", str(p)) in n["12V_LED"] for p in (8, 9, 10, 12, 13, 14))
    assert model.by_ref("U2").pins["11"] == "NC"
    assert ("U2", "15") in n["VBAT"]                                      # exposed pad = VS
    assert ("D3", "1") in n["5V"] and ("D4", "1") in n["5V"]              # OR diodes cathodes
    assert ("D3", "2") in n["5V_BUCK"] and ("D4", "2") in n["VBUS_USB"]
    for net in ("VBAT", "GND", "5V", "3V3", "12V_LED"):
        assert net in n

def test_buck_feedback_sets_5v4():
    top = float(model.by_ref("R3").value.rstrip("k")) * 1000
    bot = float(model.by_ref("R4").value.rstrip("k")) * 1000
    vout = 0.8 * (1 + top / bot)
    assert 5.3 <= vout <= 5.5, vout
