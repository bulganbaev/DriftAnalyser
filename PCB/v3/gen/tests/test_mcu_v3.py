from gen import model, pinmap


def test_mcu_pins_follow_pinmap():
    u1 = model.by_ref("U1")
    for gpio, net in pinmap.GPIO.items():
        assert u1.pins[pinmap.module_pin(gpio)] == net, (gpio, net)


def test_can_terminator_on_jumper():
    jp2 = model.by_ref("JP2")
    assert sorted(jp2.pins.values()) == ["CANL", "CAN_TERM"]
    r = [p for p in model.PARTS if p.symbol == "Device:R" and sorted(p.pins.values()) == ["CANH", "CAN_TERM"]]
    assert r and r[0].value == "120"


def test_can_silent_pin_pulled_up():
    assert model.by_ref("U4").pins["8"] == "CAN_S"
    assert any(p.symbol == "Device:R" and sorted(p.pins.values()) == ["3V3", "CAN_S"] for p in model.PARTS)
    assert "CAN_TERM_EN" not in model.nets()


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
