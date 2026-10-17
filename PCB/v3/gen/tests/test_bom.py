import re
from gen import model

def test_every_part_has_lcsc():
    missing = [p.ref for p in model.PARTS if not re.fullmatch(r"C\d{3,9}", p.lcsc or "")]
    assert missing == [], missing
