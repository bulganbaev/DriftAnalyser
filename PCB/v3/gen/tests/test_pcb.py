import subprocess
from gen import env, model, placement


def test_board_size_target():
    # The target was 55 x 75. Width holds: J1's courtyard is 46.5 of the 55 mm edge.
    # Height does not. Everything is single-sided on F, and below J1's 23.5 mm body
    # the parts need ~2700 mm2 of courtyard (a 20 mm stud, WROOM-1U, two 6 x 6
    # buttons, the 8 x 10.5 bulk cap, four TSDSO-14, ~150 small parts) plus ~150
    # for the M3 holes, against 2830 mm2 in 55 x 51.5: nothing left to route.
    # One stud packed into 100 (~68 % courtyard fill). 112 is for two studs
    # (author ruling, task 11): the battery-negative stud J5 is a second 20 mm
    # courtyard, it does not fit in 100, and 112 is what it takes in the bottom
    # right with USB / BOOT moved under J2.
    assert placement.BOARD_W <= 55 and placement.BOARD_H <= 112


def test_every_part_placed():
    missing = [p.ref for p in model.PARTS if p.ref not in placement.PLACE]
    assert not missing, missing


def test_pcb_unit_suite():
    r = subprocess.run([env.KICAD_PY, "-m", "unittest", "-v", "gen.tests.test_pcb_unit"],
                       cwd=env.PROJECT_DIR, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
