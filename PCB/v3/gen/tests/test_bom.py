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


def test_hand_fit_parts_not_in_jlc_files():
    """The studs are pressed in by us: not in what JLC gets."""
    import csv, os
    from gen import env
    fab = os.path.join(env.PROJECT_DIR, "fab")
    hand = {p.ref for p in model.PARTS if HAND_FIT in p.mpn}
    with open(os.path.join(fab, "CPL.csv")) as f:
        assert not hand & {r["Designator"] for r in csv.DictReader(f)}
    with open(os.path.join(fab, "BOM.csv")) as f:
        refs = {x for r in csv.DictReader(f) for x in r["Designator"].split(",")}
    assert not hand & refs
