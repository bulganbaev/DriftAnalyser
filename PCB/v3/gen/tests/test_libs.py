import os
from gen import libs, model


def test_all_part_symbols_resolve():
    assert libs.all_symbols_resolve() == []


def test_all_footprints_exist():
    missing = []
    for p in model.PARTS:
        d, name = libs.footprint_path(p.footprint)
        if not os.path.exists(os.path.join(d, name + ".kicad_mod")):
            missing.append(p.footprint)
    assert missing == []


def test_pins_match_symbol():
    """Every pin number in the model exists in the symbol and vice versa."""
    bad = []
    for p in model.PARTS:
        sym_pins = set(libs.symbol_pins(p.symbol))
        if sym_pins != set(p.pins):
            bad.append((p.ref, sorted(sym_pins ^ set(p.pins))))
    assert bad == [], bad


def test_bts7002_footprint_pin_count():
    d, name = libs.footprint_path("da3:PG-TSDSO-14")
    text = open(os.path.join(d, name + ".kicad_mod")).read()
    assert text.count("(pad ") == 15


def test_v3_custom_parts_resolve():
    for sym in ("da3:BTS7008-2EPA", "da3:LM74700-Q1", "da3:PCA9555", "da3:TE_6437288-1"):
        assert libs.symbol_exists(sym), sym
    for fp in ("da3:TE_6437288-1", "da3:Stud_M6", "da3:PG-TSDSO-14"):
        assert libs.footprint_exists(fp), fp


def test_superseal_has_34_pads():
    assert libs.footprint_pad_names("da3:TE_6437288-1") == {str(i) for i in range(1, 35)}
    assert len(libs.symbol_pins("da3:TE_6437288-1")) == 34


def test_pin_counts():
    assert len(libs.symbol_pins("da3:BTS7008-2EPA")) == 15
    assert len(libs.symbol_pins("da3:LM74700-Q1")) == 8
    assert len(libs.symbol_pins("da3:PCA9555")) == 24
