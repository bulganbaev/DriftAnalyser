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
    d, name = libs.footprint_path("da2:PG-TSDSO-14")
    text = open(os.path.join(d, name + ".kicad_mod")).read()
    assert text.count("(pad ") == 15
