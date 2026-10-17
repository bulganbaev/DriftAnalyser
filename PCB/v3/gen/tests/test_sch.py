import os
from gen import sch_writer, model, env


def test_write_and_erc():
    sch_writer.write_all()
    root = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_sch")
    assert os.path.exists(root)
    rpt = os.path.join(env.PROJECT_DIR, "fab", "erc.rpt")
    r = env.run_cli("sch", "erc", "--severity-error", "--exit-code-violations", "-o", rpt, root)
    assert r.returncode == 0, open(rpt).read()
    # the report is tracked; without this every run of the suite dirties it
    sch_writer.strip_timestamp(rpt, r"ERC report \([^,]*, ", "ERC report (")


def test_netlist_matches_model():
    got = sch_writer.export_netlist()
    want = {(ref, pin): net for net, nodes in model.nets().items() for ref, pin in nodes}
    bad = {k: (got.get(k), want.get(k)) for k in
           (set(got) ^ set(want)) or [k for k in want if got.get(k) != want[k]]}
    assert got == want, bad
