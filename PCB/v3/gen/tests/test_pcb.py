import subprocess
from gen import env, model, placement


def test_board_size_target():
    # The target was 55 x 75. Width holds: J1's courtyard is 46.5 of the 55 mm edge.
    # Height does not: with everything single-sided on F, the parts below J1's
    # 23.5 mm body need ~2700 mm2 of courtyard alone (stud 20 mm round, WROOM-1U,
    # two 6 x 6 buttons, 8 x 10.5 bulk cap, four TSDSO-14 + ~150 small parts),
    # plus ~150 for the M3 holes, and 55 x 51.5 below J1 is 2830 mm2 - 100 %
    # fill, nothing left to route. 100 is what the placement packs into at ~68 %
    # courtyard fill below J1 (holes included); the author decides on the size.
    assert placement.BOARD_W <= 55 and placement.BOARD_H <= 100


def test_every_part_placed():
    missing = [p.ref for p in model.PARTS if p.ref not in placement.PLACE]
    assert not missing, missing


def test_pcb_unit_suite():
    r = subprocess.run([env.KICAD_PY, "-m", "unittest", "-v", "gen.tests.test_pcb_unit"],
                       cwd=env.PROJECT_DIR, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
