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
    assert {p.sheet for p in model.PARTS} <= {"power", "outputs", "mcu", "comms"}
