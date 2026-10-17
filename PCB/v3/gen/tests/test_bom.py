import re
import pytest
from gen import model

@pytest.mark.xfail(strict=True, reason="new v3 parts get LCSC numbers in Task 9; drop this mark there")
def test_every_part_has_lcsc():
    missing = [p.ref for p in model.PARTS if not re.fullmatch(r"C\d{3,9}", p.lcsc or "")]
    assert missing == [], missing
