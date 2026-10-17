from gen import model, pinmap

SWITCHES = {"U10", "U11", "U12", "U13"}


def test_each_strip_has_its_own_channel():
    n = model.nets()
    for i in range(1, 9):
        refs = {r for r, _ in n[f"LED{i}_12V"]}
        assert len(refs & SWITCHES) == 1, i
        # J1 assertion added in Task 7 (model.J1_PIN appears there)


def test_switch_controls_pulled_down():
    pulled = {net for p in model.PARTS if p.symbol == "Device:R"
              for net in p.pins.values() if set(p.pins.values()) >= {"GND"}}
    for net in [f"LED{i}_IN" for i in range(1, 9)] + [f"DEN{k}" for k in range(1, 5)] + ["DSEL"]:
        assert net in pulled, net


def test_is_shared_through_one_resistor():
    n = model.nets()
    assert {r for r, _ in n["LED_ISENSE_RAW"]} >= SWITCHES
    r_is = [p for p in model.PARTS if p.symbol == "Device:R" and set(p.pins.values()) == {"LED_ISENSE_RAW", "GND"}]
    assert len(r_is) == 1 and r_is[0].value == "1.2k"


def test_isense_clamped_to_rails():
    clamps = [p for p in model.PARTS if p.value == "BAT54S" and p.pins.get("3") == "LED_ISENSE"]
    assert clamps and clamps[0].pins["1"] == "GND" and clamps[0].pins["2"] == "3V3"


def test_expander_follows_pinmap():
    u = model.by_ref("U14")
    for port, net in pinmap.EXP.items():
        pin = str((4 if port[1] == "0" else 13) + int(port[2]))
        assert u.pins[pin] == net, port
    assert u.pins["1"] == "EXP_INT"
    assert {u.pins[a] for a in ("21", "2", "3")} == {"GND"}  # A0..A2 -> 0x20


def test_data_buffered_series_and_esd():
    n = model.nets()
    for i in range(1, 9):
        assert {r for r, _ in n[f"LED{i}_DATA"]} & {"U15", "U16"}
        do = {r for r, _ in n[f"LED{i}_DO"]}
        assert any(model.by_ref(r).value == "33" for r in do), i
        assert any(model.by_ref(r).value == "PESD5V0S1BA" for r in do), i
