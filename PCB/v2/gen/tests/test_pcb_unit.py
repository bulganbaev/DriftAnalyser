"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import json, os, re, subprocess, sys, unittest

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


# nets that reach their pads through a pour, not through a routed track: the
# autorouter never sees them, so the builder has to finish them itself
POUR_NETS = ("GND", "VBAT", "12V_LED")


class TestPcb(unittest.TestCase):
    _drc_cache = {}

    @classmethod
    def setUpClass(cls):
        # the routed board is the artifact under test - only rebuild on demand
        if os.environ.get("DA2_REBUILD") == "1" or not os.path.exists(PCB):
            pcb_builder.build(PCB)
        cls.board = pcbnew.LoadBoard(PCB)

    @classmethod
    def _drc(cls, name="drc.json", extra=()):
        if name in cls._drc_cache:
            return cls._drc_cache[name]
        rpt = os.path.join(env.PROJECT_DIR, "fab", name)
        if os.path.exists(rpt):        # never let a stale report pass a test
            os.remove(rpt)
        r = subprocess.run([env.KICAD_CLI, "pcb", "drc", "--format", "json",
                            "--severity-error", *extra, "-o", rpt, PCB],
                           capture_output=True, text=True)
        # 0 = clean, 5 = kicad-cli's "DRC violations found"
        assert r.returncode in (0, 5), r.stdout[-800:] + r.stderr[-800:]
        with open(rpt) as f:
            cls._drc_cache[name] = json.load(f)
        return cls._drc_cache[name]

    @staticmethod
    def _nets_of(violation):
        return {m for i in violation["items"]
                for m in re.findall(r"\[([^\]]+)\]", i["description"])}

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
        """The power vias are ours: 0.8/0.4, or the 0.6/0.3 Default one where a
        pour island came out too tight for the big one."""
        vias = [t for t in self.board.Tracks() if t.GetClass() == "PCB_VIA"]
        power = [v for v in vias if v.GetNetname() in POUR_NETS]
        self.assertGreaterEqual(len(power), 40)
        for v in power:
            size = (pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)),
                    pcbnew.ToMM(v.GetDrillValue()))
            self.assertIn(size, ((0.8, 0.4), (0.6, 0.3)),
                          f"{v.GetNetname()} via at {pcbnew.ToMM(v.GetPosition().x)}, "
                          f"{pcbnew.ToMM(v.GetPosition().y)}")
            self.assertEqual(pcbnew.ToMM(v.GetWidth(pcbnew.B_Cu)), size[0])

    def test_no_via_sits_on_a_foreign_pad(self):
        """A via dropped on a pad of another net is silently swallowed by it."""
        pads = [(fp.GetReference(), pad) for fp in self.board.GetFootprints()
                for pad in fp.Pads()]
        for v in self.board.Tracks():
            if v.GetClass() != "PCB_VIA":
                continue
            p = v.GetPosition()
            for ref, pad in pads:
                if pad.GetNetname() != v.GetNetname() and pad.HitTest(p):
                    self.fail(f"{v.GetNetname()} via at {pcbnew.ToMM(p.x):.2f}, "
                              f"{pcbnew.ToMM(p.y):.2f} is on {ref} pad "
                              f"{pad.GetNumber()} [{pad.GetNetname()}]")

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

    def test_no_gnd_pad_is_stranded_on_an_island(self):
        """Signal traces cut the top pour into islands. A ground pad whose only
        copper is an island the rest of the board never reaches has no return
        path: the island needs a via of its own, or a track that leaves it."""
        vias = [t for t in self.board.Tracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
        runs = [t for t in self.board.Tracks()
                if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND"
                and t.IsOnLayer(pcbnew.F_Cu)]
        pads = [(fp.GetReference() + "." + pad.GetNumber(), pad)
                for fp in self.board.GetFootprints() for pad in fp.Pads()
                if pad.GetNetname() == "GND" and pad.IsOnLayer(pcbnew.F_Cu)]
        for z in self.board.Zones():
            if z.GetIsRuleArea() or z.GetNetname() != "GND" or not z.IsOnLayer(pcbnew.F_Cu):
                continue
            sp = z.GetFilledPolysList(pcbnew.F_Cu)
            for i in range(sp.OutlineCount()):
                island = pcbnew.SHAPE_POLY_SET()
                island.AddOutline(sp.Outline(i))
                held = [name for name, pad in pads if island.Collide(pad.GetPosition())]
                if not held:
                    continue
                if any(island.Collide(v.GetPosition()) for v in vias):
                    continue
                if any(island.Collide(t.GetStart()) != island.Collide(t.GetEnd())
                       for t in runs):
                    continue
                bb = island.BBox()
                self.fail(f"{', '.join(held)} sit on an F.Cu island at "
                          f"{pcbnew.ToMM(bb.GetLeft()):.1f}, {pcbnew.ToMM(bb.GetTop()):.1f} "
                          f"({island.Area() / 1e12:.1f} mm2) with no via and no track out")

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
            bb = t.GetBoundingBox()          # a track crossing it has both ends outside
            hit = _rect(*(pcbnew.ToMM(v) for v in
                          (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())))
            self.assertFalse(_intersects(hit, keepout),
                             f"{t.GetClass()} [{t.GetNetname()}] reaches into the "
                             f"antenna keep-out at {pcbnew.ToMM(t.GetPosition().x):.1f}, "
                             f"{pcbnew.ToMM(t.GetPosition().y):.1f}")
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

    def test_final_drc_with_parity(self):
        """The board as it ships: nothing unrouted, nothing off the schematic."""
        data = self._drc("drc-final.json", ("--schematic-parity",))
        self.assertEqual(data["violations"], [],
                         json.dumps(data["violations"][:5], indent=1, ensure_ascii=False))
        self.assertEqual(data.get("unconnected_items", []), [],
                         json.dumps(data.get("unconnected_items", [])[:5], indent=1,
                                    ensure_ascii=False))
        self.assertEqual(data.get("schematic_parity", []), [],
                         json.dumps(data.get("schematic_parity", [])[:5], indent=1,
                                    ensure_ascii=False))

    def test_drc_no_errors_except_unrouted(self):
        data = self._drc()
        viol = [v for v in data["violations"] if v["type"] != "unconnected_items"]
        self.assertEqual(viol, [], json.dumps(viol[:5], indent=1))

    def test_power_pads_reach_their_pour(self):
        """No pad of a poured net is left for the autorouter: it would try to reach
        it at the netclass width (3 mm on VBAT) through gaps that cannot take it."""
        stuck = [v for v in self._drc().get("unconnected_items", [])
                 if self._nets_of(v) & set(POUR_NETS)]
        self.assertEqual(stuck, [], json.dumps(stuck[:5], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
