import subprocess
from gen import env


def test_pcb_unit_suite():
    r = subprocess.run([env.KICAD_PY, "-m", "unittest", "-v", "gen.tests.test_pcb_unit"],
                       cwd=env.PROJECT_DIR, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
