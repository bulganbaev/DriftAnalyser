from gen import model

ROWS = [range(1, 10), range(10, 18), range(18, 26), range(26, 35)]

def row(p):
    return next(i for i, r in enumerate(ROWS) if int(p) in r)

def test_all_34_pins_assigned_once():
    assert sorted(int(p) for p in model.J1_PIN.values()) == list(range(1, 35))

def test_all_strip_supplies_in_row_1():
    """The row nearest the switches: every 5 A path is a short stub up from its switch."""
    for i in range(1, 9):
        assert row(model.J1_PIN[f"LED{i}_12V"]) == 0, i


def test_all_strip_grounds_in_row_4():
    for i in range(1, 9):
        assert row(model.J1_PIN[f"LED{i}_GND"]) == 3, i


def test_strip_ground_in_its_supply_column():
    """Row 4 has the same x grid as row 1: pin p of row 1 sits under pin p + 25."""
    for i in range(1, 9):
        assert int(model.J1_PIN[f"LED{i}_GND"]) == int(model.J1_PIN[f"LED{i}_12V"]) + 25, i


def test_can_pair_adjacent():
    h, l = model.J1_PIN["CANH"], model.J1_PIN["CANL"]
    assert abs(int(h) - int(l)) == 1 and row(h) == row(l)

def test_j1_part_matches_table():
    j1 = model.by_ref("J1")
    for key, pin in model.J1_PIN.items():
        want = "GND" if key.endswith("_GND") else key
        assert j1.pins[pin] == want, (key, pin, j1.pins[pin])


def test_readme_j1_table_is_the_models():
    import os
    from gen import env, export
    text = open(os.path.join(env.PROJECT_DIR, "README.md")).read()
    a, b = text.index(export.J1_BEGIN), text.index(export.J1_END)
    assert text[a:b + len(export.J1_END)] == export.j1_table()
