import os, subprocess
from gen import env

def test_paths_exist():
    for p in (env.KICAD_CLI, env.KICAD_PY, env.SYMBOL_DIR, env.FOOTPRINT_DIR, env.DEMO_DIR):
        assert os.path.exists(p), p

def test_cli_runs():
    out = env.run_cli("version")
    assert out.returncode == 0 and out.stdout.strip().startswith(("9.", "10."))

def test_kicad_python_has_pcbnew():
    r = subprocess.run([env.KICAD_PY, "-c", "import pcbnew; print(pcbnew.GetBuildVersion())"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.startswith(("9.", "10.")), r.stderr
