"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pcbnew
from gen import env, model, placement, pcb_builder

PCB = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb")
THT = ("J1", "J2")          # the only through-hole parts; everything else is JLC one-side SMD


def _intersects(a, b):
    out = pcbnew.SHAPE_POLY_SET()
    out.BooleanIntersection(a, b)
    return not out.IsEmpty()


def _mm(v):
    return round(pcbnew.ToMM(v), 3)


class TestPcb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # the board is the artifact under test - only rebuild on demand
        if os.environ.get("DA3_REBUILD") == "1" or not os.path.exists(PCB):
            pcb_builder.build(PCB)
        cls.board = pcbnew.LoadBoard(PCB)
        cls.fps = {fp.GetReference(): fp for fp in cls.board.GetFootprints()}

    def test_every_part_placed(self):
        # H* are the mounting holes: footprints without a model part
        refs = {r for r in self.fps if not r.startswith("H")}
        self.assertEqual(refs, {p.ref for p in model.PARTS})
        self.assertEqual(set(placement.PLACE), {p.ref for p in model.PARTS})

    def test_board_matches_placement(self):
        """A stale .kicad_pcb would pass every other test here: rebuild after editing placement."""
        for ref, (x, y, rot, side) in placement.PLACE.items():
            pos = self.fps[ref].GetPosition()
            self.assertAlmostEqual(_mm(pos.x), x, delta=0.001, msg=ref)
            self.assertAlmostEqual(_mm(pos.y), y, delta=0.001, msg=ref)

    def test_outline_and_holes(self):
        bb = self.board.GetBoardEdgesBoundingBox()
        self.assertAlmostEqual(pcbnew.ToMM(bb.GetWidth()), placement.BOARD_W, delta=0.2)
        self.assertAlmostEqual(pcbnew.ToMM(bb.GetHeight()), placement.BOARD_H, delta=0.2)
        holes = [fp for r, fp in self.fps.items() if r.startswith("H")]
        self.assertEqual(len(holes), 4)

    def test_all_parts_on_front(self):
        for ref, fp in self.fps.items():
            if ref in THT:
                continue
            self.assertEqual(fp.GetLayer(), pcbnew.F_Cu, f"{ref} is not on F")
            self.assertEqual(placement.PLACE.get(ref, (0, 0, 0, "F"))[3], "F", ref)

    def test_no_courtyard_overlaps(self):
        courts = {}
        for ref, fp in self.fps.items():
            poly = fp.GetCourtyard(pcbnew.F_CrtYd)
            self.assertTrue(poly.OutlineCount(), f"{ref} has no F.CrtYd")
            courts[ref] = poly
        refs = sorted(courts)
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                self.assertFalse(_intersects(courts[a], courts[b]), f"{a} overlaps {b}")

    def test_holes_clear_of_j1_screw_ears(self):
        """J1's two flange screws carry nuts on the back (its B.CrtYd circles)."""
        ears = self.fps["J1"].GetCourtyard(pcbnew.B_CrtYd)
        self.assertTrue(ears.OutlineCount())
        for ref, fp in self.fps.items():
            if ref.startswith("H"):
                self.assertFalse(_intersects(fp.GetCourtyard(pcbnew.F_CrtYd), ears), ref)

    def test_courtyards_inside_board(self):
        for ref, fp in self.fps.items():
            if ref == "J1":          # its mating end goes out through the case wall
                continue
            bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            self.assertGreaterEqual(_mm(bb.GetLeft()), 0.0, ref)
            self.assertGreaterEqual(_mm(bb.GetTop()), 0.0, ref)
            self.assertLessEqual(_mm(bb.GetRight()), placement.BOARD_W, ref)
            self.assertLessEqual(_mm(bb.GetBottom()), placement.BOARD_H, ref)

    def test_j1_flange_on_board_edge(self):
        """The footprint's F.Fab 'board edge <= here' line (local y = +6) sits on y = 0."""
        fp = self.fps["J1"]
        edge = [it for it in fp.GraphicalItems()
                if it.GetLayer() == pcbnew.F_Fab and isinstance(it, pcbnew.PCB_SHAPE)
                and it.GetShape() == pcbnew.SHAPE_T_SEGMENT
                and abs(pcbnew.ToMM(it.GetLength()) - 46.0) < 0.01]
        self.assertEqual(len(edge), 1)
        self.assertAlmostEqual(_mm(edge[0].GetStart().y), 0.0, delta=0.01)
        self.assertAlmostEqual(_mm(edge[0].GetEnd().y), 0.0, delta=0.01)

    def test_silk_labels_present(self):
        texts = {t.GetText() for t in self.board.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT)}
        for want in ("DriftAnalyser v3", "1", "+12V", "JP1 K-LINE", "JP2 CAN TERM",
                     "BOOT", "EN", "USB"):
            self.assertIn(want, texts)


if __name__ == "__main__":
    unittest.main()
