"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pcbnew
from gen import env, model, placement, pcb_builder, route, sch_writer

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
        # sch_writer (and kicad-cli) rewrite the .kicad_pro without the board's
        # netclasses; put them back or DRC checks this board against KiCad's
        # defaults and every number in these tests means something else
        pcb_builder.write_project_netclasses()
        pcb_builder.write_design_rules()
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
            fp = self.fps[ref]
            self.assertAlmostEqual(fp.GetOrientationDegrees() % 360, rot % 360, delta=0.001, msg=ref)
            self.assertEqual(fp.GetLayer(), pcbnew.F_Cu if side == "F" else pcbnew.B_Cu, ref)

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

    def test_bottom_holes_clear_of_stud_and_module(self):
        """>= 0.5 mm between the hole courtyard (r 3.45) and J2 / U1: room for a washer."""
        r = 3.45 + 0.5
        sx, sy, _, _ = placement.PLACE["J2"]
        bb = self.fps["U1"].GetCourtyard(pcbnew.F_CrtYd).BBox()
        ux0, uy0, ux1, uy1 = (_mm(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
        for hx, hy in placement.HOLES[2:]:
            self.assertGreaterEqual(((hx - sx) ** 2 + (hy - sy) ** 2) ** 0.5, 10.0 + r)
            dx = max(ux0 - hx, 0.0, hx - ux1)
            dy = max(uy0 - hy, 0.0, hy - uy1)
            self.assertGreaterEqual((dx * dx + dy * dy) ** 0.5, r)

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
                     "BOOT", "EN", "USB", "IMU", "X", "Y"):
            self.assertIn(want, texts)


    # ---- routing / DRC -----------------------------------------------------

    _drc_cache = {}

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
        sch_writer.strip_timestamp(rpt, r'"date": "[^"]*"', '"date": ""')
        with open(rpt) as f:
            cls._drc_cache[name] = json.load(f)
        return cls._drc_cache[name]

    def test_drc_clean(self):
        """The board as it ships: no DRC error, nothing unrouted."""
        data = self._drc()
        self.assertEqual(data["violations"], [],
                         json.dumps(data["violations"][:5], indent=1, ensure_ascii=False))
        self.assertEqual(data.get("unconnected_items", []), [],
                         json.dumps(data.get("unconnected_items", [])[:5], indent=1,
                                    ensure_ascii=False))

    def test_routed(self):
        tracks = [t for t in self.board.Tracks() if t.GetClass() == "PCB_TRACK"]
        self.assertGreater(len(tracks), route.BUILDER_TRACKS)

    def test_led_channels_on_pours(self):
        """Every LED channel's switch outputs and J1 pin sit in a pour of their own
        net on F.Cu (the cap stubs are the only tracks on these nets)."""
        for net in pcb_builder.LED_NETS:
            zones = [z for z in self.board.Zones() if z.GetNetname() == net
                     and not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.F_Cu)]
            self.assertTrue(zones, net)
            for fp in self.board.GetFootprints():
                for pad in fp.Pads():
                    if pad.GetNetname() != net or fp.GetReference().startswith("C"):
                        continue
                    self.assertTrue(any(z.GetFilledPolysList(pcbnew.F_Cu).Collide(pad.GetPosition())
                                        for z in zones), f"{net} {fp.GetReference()}.{pad.GetNumber()}")

    def test_six_layers(self):
        """JLC06161H-3313, six copper layers, declared in the board file."""
        self.assertEqual(self.board.GetCopperLayerCount(), 6)
        with open(PCB) as f:
            text = f.read()
        stack = text[text.index("(stackup"):text.index("(copper_finish")]
        self.assertEqual(stack.count('(type "copper")'), 6)
        self.assertIn('(material "3313")', stack)

    def _channel_width(self, net, layer):
        """Narrowest width of the net's fill on `layer` between the middle switch
        output pin and its J1 pin: the widest disc that still gets through."""
        j1 = [p for p in self.fps["J1"].Pads() if p.GetNetname() == net][0]
        outs = sorted((p for r, fp in self.fps.items() if r in placement.SW_X
                       for p in fp.Pads() if p.GetNetname() == net),
                      key=lambda p: p.GetPosition().x)
        mid = outs[len(outs) // 2]
        a = pcbnew.VECTOR2I(mid.GetPosition().x, mid.GetBoundingBox().GetTop())
        fill = pcbnew.SHAPE_POLY_SET()
        for z in self.board.Zones():
            if not z.GetIsRuleArea() and z.GetNetname() == net and z.IsOnLayer(layer):
                fill.BooleanAdd(z.GetFilledPolysList(layer))
        best, w = 0.0, 0.5
        while not fill.IsEmpty() and w < 4:
            p = pcbnew.SHAPE_POLY_SET(fill)
            p.Deflate(pcbnew.FromMM(w / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
            p.Inflate(pcbnew.FromMM(w / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
            through = False
            for i in range(p.OutlineCount()):
                o = pcbnew.SHAPE_POLY_SET()
                o.AddOutline(p.Outline(i))
                through |= o.Collide(a, pcbnew.FromMM(0.35)) and o.Collide(j1.GetPosition(), pcbnew.FromMM(0.35))
            if not through:
                break
            best, w = w, w + 0.05
        return best

    def test_led_channel_width(self):
        """Every LED channel carries 5 A through >= 2 mm of copper: F.Cu alone for
        the inner four, F.Cu plus its In3 lane (stitched to it) for the outer four."""
        for net in pcb_builder.LED_NETS:
            w = self._channel_width(net, pcbnew.F_Cu)
            if net in pcb_builder.LED_IN3:
                w += self._channel_width(net, pcbnew.In3_Cu)
                vias = [t for t in self.board.Tracks() if t.GetClass() == "PCB_VIA"
                        and t.GetNetname() == net]
                self.assertGreaterEqual(len(vias), 2, net)
            self.assertGreaterEqual(w, 2.0, net)

    def test_switch_exposed_pads_stitched(self):
        """12 vias in each BTS7008's exposed pad, down to the B.Cu VBUS copper."""
        for u in placement.SW_X:
            ep = self.fps[u].FindPadByNumber("15")
            vias = [t for t in self.board.Tracks() if t.GetClass() == "PCB_VIA"
                    and t.GetNetname() == "VBUS" and ep.HitTest(t.GetPosition())]
            self.assertGreaterEqual(len(vias), 12, u)


def _normalised(path):
    """The board file without what changes on every save: uuids and the like."""
    with open(path) as f:
        text = f.read()
    text = re.sub(r'\((uuid|tstamp)\s+"?[0-9a-fA-F-]+"?\)', "", text)
    text = re.sub(r'\(generator_version "[^"]*"\)', "", text)
    return text


class TestDeterministic(unittest.TestCase):
    def test_build_deterministic(self):
        """Two builds from scratch (builder + replayed session) give the same board,
        and the same as the committed one. Freerouting is never run here: the
        session the build replays is the committed fab/route.ses."""
        tmp = tempfile.mkdtemp(prefix="da3-det-")
        try:
            outs = []
            for k in (1, 2):
                # each build in a process of its own, as build.sh runs them: two
                # builds in one process do not get the same KIIDs (the seeded
                # generator is not the only source of them inside pcbnew)
                pcb = os.path.join(tmp, f"b{k}.kicad_pcb")
                # the routed board is filled against the project's netclasses and
                # rules, which pcbnew finds next to the board by name
                for ext in (".kicad_pro", ".kicad_dru"):
                    shutil.copy(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ext),
                                os.path.join(tmp, f"b{k}{ext}"))
                code = ("import sys; sys.path.insert(0, '.'); "
                        "from gen import pcb_builder, route; "
                        f"pcb_builder.build({pcb!r}); "
                        f"route.route(pcb={pcb!r}, dsn={os.path.join(tmp, f'b{k}.dsn')!r}, "
                        "ses=route.SES, reroute=False)")
                r = subprocess.run([env.KICAD_PY, "-c", code], cwd=env.PROJECT_DIR,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr[-2000:])
                outs.append(_normalised(pcb))
            self.assertEqual(outs[0], outs[1], "two builds differ")
            self.assertEqual(outs[0], _normalised(PCB),
                             "the committed board is not what the generator builds")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            # the builds above rewrote the project's netclasses into the .kicad_pro;
            # that is the same content, but leave it as the real build left it
            pcb_builder.write_project_netclasses()


if __name__ == "__main__":
    unittest.main()
