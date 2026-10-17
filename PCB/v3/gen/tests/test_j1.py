from gen import model

ROWS = [range(1, 10), range(10, 18), range(18, 26), range(26, 35)]

def row(p):
    return next(i for i, r in enumerate(ROWS) if int(p) in r)

def test_all_34_pins_assigned_once():
    assert sorted(int(p) for p in model.J1_PIN.values()) == list(range(1, 35))

def test_strip_triplets_adjacent():
    for i in range(1, 9):
        ps = sorted(int(model.J1_PIN[k]) for k in (f"LED{i}_12V", f"LED{i}_DO", f"LED{i}_GND"))
        assert ps[2] - ps[0] == 2 and row(ps[0]) == row(ps[2]), i

def test_can_pair_adjacent():
    assert abs(int(model.J1_PIN["CANH"]) - int(model.J1_PIN["CANL"])) == 1

def test_j1_part_matches_table():
    j1 = model.by_ref("J1")
    for key, pin in model.J1_PIN.items():
        want = "GND" if key.endswith("_GND") else key
        assert j1.pins[pin] == want, (key, pin, j1.pins[pin])
