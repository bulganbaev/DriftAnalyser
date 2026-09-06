"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pcbnew
from gen import env, model, placement, pcb_builder

PCB = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb")


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


if __name__ == "__main__":
    unittest.main()
