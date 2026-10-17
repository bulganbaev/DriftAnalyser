from gen import model

def n():
    return model.nets()

def test_stud_feeds_vin_and_tvs():
    assert ("J2", "1") in n()["VIN"]
    assert {r for r, _ in n()["VIN"]} >= {"J2", "D1", "U2", "Q1", "Q2"}

def test_nothing_but_ideal_diode_bridges_vin_to_vbus():
    vin = {r for r, _ in n()["VIN"]}
    vbus = {r for r, _ in n()["VBUS"]}
    assert vin & vbus <= {"U2", "Q1", "Q2"}

def test_hold_pulled_down():
    pulls = [p for p in model.PARTS if p.symbol == "Device:R" and set(p.pins.values()) == {"HOLD", "GND"}]
    assert pulls, "HOLD needs a pull-down so a blank board sleeps"

def test_sensor_supply_behind_current_limiter():
    # 5V -> U6 -> 5V_SENS_SW -> D7 -> 5V_SENS: only the limiter, then only the diode
    assert {r for r, _ in n()["5V"]} & {r for r, _ in n()["5V_SENS"]} == set()
    assert {r for r, _ in n()["5V"]} & {r for r, _ in n()["5V_SENS_SW"]} == {"U6"}
    assert {r for r, _ in n()["5V_SENS_SW"]} & {r for r, _ in n()["5V_SENS"]} == {"D7"}

def test_limiter_output_behind_reverse_diode():
    u6 = model.by_ref("U6")
    assert u6.pins["6"] != "5V_SENS"
    d = model.by_ref("D7")
    assert d.symbol == "Device:D_Schottky" and d.pins == {"1": "5V_SENS", "2": u6.pins["6"]}  # K out, A from U6
