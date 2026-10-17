from gen import pinmap

STRAPS = {0, 3, 45, 46}
FLASH_PSRAM = set(range(26, 33))  # SPI flash/PSRAM на модуле
ADC1 = set(range(1, 11))

# v2 U1 pad numbers (PCB/v2/gen/model.py) for GPIOs v2 used
V2_PADS = {4: "4", 5: "5", 6: "6", 7: "7", 15: "8", 16: "9", 8: "12", 9: "17", 10: "18",
           11: "19", 12: "20", 13: "21", 14: "22", 21: "23", 0: "27", 2: "38", 1: "39",
           38: "31", 39: "32", 40: "33", 41: "34", 42: "35", 19: "13", 20: "14",
           43: "37", 44: "36"}


def test_no_gpio_used_twice():
    nets = list(pinmap.GPIO.values())
    assert len(nets) == len(set(nets))


def test_no_flash_pins():
    assert not set(pinmap.GPIO) & FLASH_PSRAM


def test_straps_only_boot():
    assert {g for g in pinmap.GPIO if g in STRAPS} <= {0}


def test_analog_on_adc1():
    for g, net in pinmap.GPIO.items():
        if net.endswith("_SENSE"):
            assert g in ADC1, (g, net)


def test_expander_has_switch_controls():
    vals = set(pinmap.EXP.values())
    assert {f"LED{i}_IN" for i in range(1, 9)} <= vals
    assert {f"DEN{i}" for i in range(1, 5)} <= vals and "DSEL" in vals


def test_module_pins_exist():
    for g in pinmap.GPIO:
        assert pinmap.module_pin(g)


def test_module_pin_matches_v2():
    for g, pad in V2_PADS.items():
        assert pinmap.module_pin(g) == pad, g


def test_expander_pins_valid_and_unique():
    assert set(pinmap.EXP) <= {f"P{p}{b}" for p in (0, 1) for b in range(8)}
    assert len(set(pinmap.EXP.values())) == len(pinmap.EXP)
