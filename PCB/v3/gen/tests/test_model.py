import re
from collections import Counter
from gen import model

def test_refs_unique():
    refs = [p.ref for p in model.PARTS]
    dupes = [r for r, c in Counter(refs).items() if c > 1]
    assert not dupes, dupes

# MCU-side ends and Task 6 loads not in the model yet - removed in Task 6
PENDING_NETS = {"CAN_TERM_EN", "STATUS_LED", *(f"LED{i}_DATA" for i in range(1, 9))}

def test_every_net_has_two_or_more_pins():
    single = {n: v for n, v in model.nets().items() if len(v) < 2 and n not in PENDING_NETS}
    assert not single, single

def test_net_names_are_clean():
    bad = [n for n in model.nets() if not re.fullmatch(r"[A-Z0-9_]+", n)]
    assert not bad, bad

def test_sheets_valid():
    assert {p.sheet for p in model.PARTS} <= {"power", "outputs", "mcu", "comms"}
