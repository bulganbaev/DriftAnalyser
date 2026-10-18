import re
from gen import model

HAND_FIT = "(hand-fit)"


def _has_lcsc(p):
    return bool(re.fullmatch(r"C\d{3,9}", p.lcsc or ""))


def test_every_part_has_lcsc():
    missing = [p.ref for p in model.PARTS if not p.dnp and HAND_FIT not in p.mpn and not _has_lcsc(p)]
    assert missing == [], missing


def test_superseal_and_stud_marked_hand_or_jlc():
    for ref in ("J1", "J2", "J5"):
        p = model.by_ref(ref)
        assert _has_lcsc(p) != (HAND_FIT in p.mpn), ref


def test_only_connectors_are_hand_fit():
    assert {p.ref for p in model.PARTS if HAND_FIT in p.mpn} <= {"J1", "J2", "J5"}
