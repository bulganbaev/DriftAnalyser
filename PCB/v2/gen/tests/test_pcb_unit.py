"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import json, os, subprocess, sys, unittest

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


def _covers(outer, inner):
    """True if the inner polygon lies entirely inside the outer one."""
    rest = pcbnew.SHAPE_POLY_SET()
    rest.BooleanSubtract(inner, outer)
    return rest.IsEmpty()


def _inside(box, x, y):
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


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

    def test_power_zones_exist(self):
        # ZONE.GetLayerName() answers "F.Cu" for back-side zones in KiCad 10
        zones = {(z.GetNetname(), self.board.GetLayerName(z.GetLayer()))
                 for z in self.board.Zones() if not z.GetIsRuleArea()}
        for want in (("GND", "B.Cu"), ("GND", "F.Cu"), ("12V_LED", "F.Cu"),
                     ("12V_LED", "B.Cu"), ("VBAT", "F.Cu"), ("VBAT", "B.Cu")):
            self.assertIn(want, zones)

    def test_zones_filled(self):
        n = 0
        for z in self.board.Zones():
            if z.GetIsRuleArea():
                continue
            n += 1
            self.assertTrue(z.IsFilled(), z.GetNetname())
            self.assertGreater(z.GetFilledArea(), 0, z.GetNetname())
        self.assertGreaterEqual(n, 6)

    def test_stitching_vias(self):
        """Every via we place is a power stitch: one sitting on a foreign pad would
        silently be swallowed by that pad's net."""
        vias = [t for t in self.board.Tracks() if t.GetClass() == "PCB_VIA"]
        self.assertGreaterEqual(len(vias), 40)
        self.assertEqual({v.GetNetname() for v in vias}, {"GND", "VBAT", "12V_LED"})
        for v in vias:
            self.assertEqual(pcbnew.ToMM(v.GetDrillValue()), 0.4)
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                self.assertEqual(pcbnew.ToMM(v.GetWidth(layer)), 0.8)

    def test_vbat_tab_via_field(self):
        """U2's tab is fed only through vias out of the back-side VBAT run."""
        tab = (86.0, 22.0, 101.0, 31.0)
        n = 0
        for t in self.board.Tracks():
            if t.GetClass() != "PCB_VIA" or t.GetNetname() != "VBAT":
                continue
            p = t.GetPosition()
            if _inside(tab, pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)):
                n += 1
        self.assertGreaterEqual(n, 18, f"only {n} VBAT vias into U2's tab area")

    def test_ground_plane_has_no_floating_island(self):
        """A GND island that no track reaches is a pad with no return path."""
        for z in self.board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != "GND":
                continue
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not z.IsOnLayer(layer):
                    continue
                n = z.GetFilledPolysList(layer).OutlineCount()
                self.assertEqual(n, 1, f"GND on {self.board.GetLayerName(layer)} "
                                       f"fills as {n} disconnected pieces")

    def test_no_copper_in_antenna_keepout(self):
        """The rule area is the intent; this is the filled result."""
        x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
        box = (max(x0, 0.0), y0, x1, y1)
        keepout = _rect(*box)
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            poured = pcbnew.SHAPE_POLY_SET()
            for z in self.board.Zones():
                if z.GetIsRuleArea() or not z.IsOnLayer(layer):
                    continue
                poured.BooleanAdd(z.GetFilledPolysList(layer))
            hit = pcbnew.SHAPE_POLY_SET()
            hit.BooleanIntersection(poured, keepout)
            self.assertTrue(hit.IsEmpty(),
                            f"copper poured into the antenna keep-out on "
                            f"{self.board.GetLayerName(layer)}")
        for t in self.board.Tracks():
            p = t.GetPosition()
            self.assertFalse(_inside(box, pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)),
                             f"{t.GetClass()} inside the antenna keep-out")
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                p = pad.GetPosition()
                self.assertFalse(_inside(box, pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)),
                                 f"{fp.GetReference()} pad {pad.GetNumber()} "
                                 f"inside the antenna keep-out")

    def test_antenna_keepout_rule_area(self):
        """Spec: nothing metallic under the ESP32 antenna, on either copper layer."""
        x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
        want = _rect(max(x0, 0.0), y0, x1, y1)      # the part that is on the board
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            hit = [z for z in self.board.Zones()
                   if z.GetIsRuleArea() and z.IsOnLayer(layer)
                   and z.GetDoNotAllowZoneFills() and z.GetDoNotAllowTracks()
                   and z.GetDoNotAllowVias() and _covers(z.Outline(), want)]
            self.assertTrue(hit, f"no antenna rule area on {pcbnew.LayerName(layer)}")

    def test_drc_no_errors_except_unrouted(self):
        rpt = os.path.join(env.PROJECT_DIR, "fab", "drc.json")
        if os.path.exists(rpt):        # never let a stale report pass the test
            os.remove(rpt)
        r = subprocess.run([env.KICAD_CLI, "pcb", "drc", "--format", "json",
                            "--severity-error", "-o", rpt, PCB],
                           capture_output=True, text=True)
        # 0 = clean, 5 = kicad-cli's "DRC violations found"
        self.assertIn(r.returncode, (0, 5), r.stdout[-800:] + r.stderr[-800:])
        with open(rpt) as f:
            data = json.load(f)
        viol = [v for v in data["violations"] if v["type"] != "unconnected_items"]
        self.assertEqual(viol, [], json.dumps(viol[:5], indent=1))


if __name__ == "__main__":
    unittest.main()
