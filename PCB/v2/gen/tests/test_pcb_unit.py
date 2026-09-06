"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pcbnew
from gen import env, model, placement, pcb_builder

PCB = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb")


def _rect(x0, y0, x1, y1):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        poly.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return poly


def _intersects(a, b):
    out = pcbnew.SHAPE_POLY_SET()
    out.BooleanIntersection(a, b)
    return not out.IsEmpty()


class TestPcb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pcb_builder.build(PCB)
        cls.board = pcbnew.LoadBoard(PCB)

    def test_every_part_placed(self):
        # H* are the mounting holes: footprints without a model part
        refs = {fp.GetReference() for fp in self.board.GetFootprints()
                if not fp.GetReference().startswith("H")}
        self.assertEqual(refs, {p.ref for p in model.PARTS})
        self.assertEqual(set(placement.PLACE), {p.ref for p in model.PARTS})

    def test_pad_nets_match_model(self):
        want = {(ref, pin): net for net, nodes in model.nets().items() for ref, pin in nodes}
        got = {}
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname():
                    # several pads may share a number (shields, thermal tabs) - same net
                    got[(fp.GetReference(), pad.GetNumber())] = pad.GetNetname()
        self.assertEqual(got, want)

    def test_outline_and_holes(self):
        bb = self.board.GetBoardEdgesBoundingBox()
        self.assertAlmostEqual(pcbnew.ToMM(bb.GetWidth()), placement.BOARD_W, delta=0.2)
        self.assertAlmostEqual(pcbnew.ToMM(bb.GetHeight()), placement.BOARD_H, delta=0.2)
        holes = [fp for fp in self.board.GetFootprints() if fp.GetReference().startswith("H")]
        self.assertEqual(len(holes), 4)

    def test_footprints_inside_board(self):
        for fp in self.board.GetFootprints():
            if fp.GetReference() == "U1":      # antenna hangs over the edge on purpose
                continue
            c = fp.GetBoundingBox(False, False)
            ref = fp.GetReference()
            self.assertGreaterEqual(pcbnew.ToMM(c.GetLeft()), -0.5, ref)
            self.assertLessEqual(pcbnew.ToMM(c.GetRight()), placement.BOARD_W + 0.5, ref)
            self.assertGreaterEqual(pcbnew.ToMM(c.GetTop()), -0.5, ref)
            self.assertLessEqual(pcbnew.ToMM(c.GetBottom()), placement.BOARD_H + 0.5, ref)

    def test_antenna_keepout_is_clear(self):
        """Nothing but bare board inside the ESP32 module's own antenna keep-out."""
        keepout = _rect(*placement.ANTENNA_KEEPOUT)
        for fp in self.board.GetFootprints():
            if fp.GetReference() == "U1":       # the keep-out belongs to U1
                continue
            court = fp.GetCourtyard(pcbnew.F_CrtYd)
            if not court.OutlineCount():
                bb = fp.GetBoundingBox(False, False)
                court = _rect(*(pcbnew.ToMM(v) for v in
                                (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())))
            self.assertFalse(_intersects(court, keepout),
                             f"{fp.GetReference()} is inside the antenna keep-out")

    def test_no_courtyard_overlaps(self):
        """No two footprints share any area. U1's courtyard is L-shaped (module +
        antenna keep-out), so this has to be a polygon boolean, not a bounding box."""
        courts = {}
        for fp in self.board.GetFootprints():
            poly = fp.GetCourtyard(pcbnew.F_CrtYd)
            self.assertTrue(poly.OutlineCount(), f"{fp.GetReference()} has no F.CrtYd")
            courts[fp.GetReference()] = poly
        refs = sorted(courts)
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                self.assertFalse(_intersects(courts[a], courts[b]), f"{a} overlaps {b}")


if __name__ == "__main__":
    unittest.main()
