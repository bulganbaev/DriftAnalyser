from gen import model, pinmap


def test_mcu_pins_follow_pinmap():
    u1 = model.by_ref("U1")
    for gpio, net in pinmap.GPIO.items():
        assert u1.pins[pinmap.module_pin(gpio)] == net, (gpio, net)


def test_can_terminator_switched():
    n = model.nets()
    assert "CAN_TERM_EN" in n and any(r.startswith("Q") for r, _ in n["CAN_TERM_EN"])


def test_inputs_protected():
    n = model.nets()
    for i in (1, 2, 3):
        tvs = [r for r, _ in n[f"IN{i}"] if model.by_ref(r).symbol == "Device:D_TVS"]
        assert tvs, f"IN{i} has no TVS"


def test_sens_5v_fault_read():
    assert pinmap.GPIO[47] == "SENS_5V_FLT"


def test_usb_powers_5v_through_schottky():
    d = [p for p in model.PARTS if p.symbol == "Device:D_Schottky" and p.pins == {"1": "5V", "2": "VBUS_USB"}]
    assert d
