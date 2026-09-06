"""Board checks that need pcbnew -> run with KiCad's python: KICAD_PY -m unittest gen.tests.test_pcb_unit"""
import json, math, os, re, subprocess, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pcbnew
from gen import env, model, placement, pcb_builder, sch_writer

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

# F.Cu / In1.Cu (solid GND) / In2.Cu (VBAT + 12V_LED + GND) / B.Cu
CU = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
INNER = (pcbnew.In1_Cu, pcbnew.In2_Cu)


def _fill_of(board, net, layer):
    """The filled copper of one net on one layer, as a single poly set."""
    out = pcbnew.SHAPE_POLY_SET()
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(layer):
            continue
        out.BooleanAdd(z.GetFilledPolysList(layer))
    return out


def _slice(copper, box, w):
    """Millimetres of copper inside a thin box: its area over the slice width."""
    cut = pcbnew.SHAPE_POLY_SET()
    cut.BooleanIntersection(copper, _rect(*box))
    return cut.Area() / 1e12 / w, cut.OutlineCount()


def _across(copper, x, y0, y1, w=0.2):
    """Copper a vertical cut at x meets between y0 and y1 - for a run in x."""
    return _slice(copper, (x - w / 2, y0, x + w / 2, y1), w)


def _down(copper, y, x0, x1, w=0.2):
    """Copper a horizontal cut at y meets between x0 and x1 - for a run in y."""
    return _slice(copper, (x0, y - w / 2, x1, y + w / 2), w)


# JLCPCB 4 layer with the 1 oz inner option: 0.035 mm on every copper layer
OZ = 0.035


def _amps(inner, outer, dT=20.0, t=OZ):
    """IPC-2221 ampacity of `inner` mm of plane plus `outer` mm of outer-layer
    copper at a dT K rise: I = k * dT^0.44 * A^0.725 with A in mil^2, k = 0.024
    for an internal layer and 0.048 for an external one. 30 mm of 1 oz internal
    copper is 19.2 A at 20 K, which is why widths alone are not the test."""
    def one(w, k):
        return 0.0 if w <= 0 else k * dT ** 0.44 * (w * t * 1550.0) ** 0.725
    return one(inner, 0.024) + one(outer, 0.048)


class TestPcb(unittest.TestCase):
    _drc_cache = {}

    @classmethod
    def setUpClass(cls):
        # the routed board is the artifact under test - only rebuild on demand
        if os.environ.get("DA2_REBUILD") == "1" or not os.path.exists(PCB):
            pcb_builder.build(PCB)
        # sch_writer (and kicad-cli) rewrite the .kicad_pro without the board's
        # netclasses; put them back or DRC checks this board against KiCad's
        # defaults and every number in these tests means something else
        pcb_builder.write_project_netclasses()
        pcb_builder.write_design_rules()
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
        # the report is tracked, and its only changing field is the time of day
        sch_writer.strip_timestamp(rpt, r'"date": "[^"]*"', '"date": ""')
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

    def test_project_carries_the_netclasses(self):
        """kicad-cli rewrites the .kicad_pro whenever it loads it and throws away
        what it does not recognise. If that ever wins, DRC quietly starts checking
        the board against KiCad's defaults instead of ours."""
        with open(os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pro")) as f:
            pro = json.load(f)
        classes = {c["name"]: (c["clearance"], c["track_width"])
                   for c in pro["net_settings"]["classes"]}
        self.assertEqual(classes, {"Default": (0.2, 0.25), "Power": (0.25, 0.5),
                                   "Bus12V": (0.4, 3.0)})
        patterns = {p["pattern"]: p["netclass"]
                    for p in pro["net_settings"]["netclass_patterns"]}
        self.assertEqual(patterns.get("VBAT"), "Bus12V")
        self.assertEqual(patterns.get("GND"), "Power")
        rules = pro["board"]["design_settings"]["rules"]
        self.assertEqual(rules["min_copper_edge_clearance"], 0.3)
        self.assertEqual(rules["min_track_width"], 0.2)

    def test_board_is_four_layer(self):
        """F.Cu / In1.Cu / In2.Cu / B.Cu on JLCPCB's stock 1.6 mm stack."""
        self.assertEqual(self.board.GetCopperLayerCount(), 4)
        for layer in CU:
            self.assertTrue(self.board.IsLayerEnabled(layer),
                            pcbnew.LayerName(layer))
        with open(PCB) as f:
            text = f.read()
        self.assertIn("(stackup", text)
        # 1 oz outside, 0.5 oz inside - the numbers the current ratings assume.
        # KiCad reformats the block when it rewrites the board, so read it, do
        # not string-match it.
        # 1 oz on all four: the inner weight is a JLCPCB option and it is what
        # lets the In2 plane carry the strip current
        for name, thickness in (("F.Cu", 0.035), ("In1.Cu", 0.035),
                                ("In2.Cu", 0.035), ("B.Cu", 0.035)):
            m = re.search(r'\(layer "%s"\s*\(type "copper"\)\s*\(thickness ([\d.]+)\)'
                          % re.escape(name), text)
            self.assertTrue(m, f"{name} is not a copper layer in the stackup")
            self.assertAlmostEqual(float(m.group(1)), thickness, places=4, msg=name)

    def test_power_zones_exist(self):
        """The layer plan: signals and pad-level power copper outside, a solid
        ground plane on In1, the power plane on In2."""
        zones = set()
        for z in self.board.Zones():
            if z.GetIsRuleArea():
                continue
            for layer in CU:
                if z.IsOnLayer(layer):
                    zones.add((z.GetNetname(), self.board.GetLayerName(layer)))
        self.assertEqual(zones, {
            ("GND", "F.Cu"), ("GND", "In1.Cu"), ("GND", "In2.Cu"), ("GND", "B.Cu"),
            ("VBAT", "F.Cu"), ("VBAT", "In2.Cu"),
            ("12V_LED", "F.Cu"), ("12V_LED", "In2.Cu")})

    def test_in1_is_a_solid_ground_plane(self):
        """Nothing but GND is ever poured on In1: it is the reference every
        signal on F.Cu is drawn against, and the strips' return path."""
        others = [z.GetNetname() for z in self.board.Zones()
                  if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.In1_Cu)
                  and z.GetNetname() != "GND"]
        self.assertEqual(others, [])
        gnd = _fill_of(self.board, "GND", pcbnew.In1_Cu)
        # the board is 110 x 75 with a 0.5 mm inset; the vias and the antenna
        # keep-out are the only things that take copper out of it
        self.assertGreater(gnd.Area() / 1e12,
                           0.9 * (placement.BOARD_W - 1) * (placement.BOARD_H - 1)
                           - 21.0 * 48.0)

    def test_inner_layers_have_no_signal_tracks(self):
        """In1 and In2 are planes. Freerouting is told so in the DSN
        (`(type power)`), and this is the result on the board: tracks only on
        F.Cu and B.Cu. Vias are what reaches the planes and are allowed."""
        stray = [(t.GetNetname(), self.board.GetLayerName(t.GetLayer()),
                  round(pcbnew.ToMM(t.GetPosition().x), 1),
                  round(pcbnew.ToMM(t.GetPosition().y), 1))
                 for t in self.board.Tracks()
                 if t.GetClass() == "PCB_TRACK" and t.GetLayer() in INNER]
        self.assertEqual(stray, [])

    def test_zones_filled(self):
        n = 0
        for z in self.board.Zones():
            if z.GetIsRuleArea():
                continue
            n += 1
            self.assertTrue(z.IsFilled(), z.GetNetname())
            self.assertGreater(z.GetFilledArea(), 0, z.GetNetname())
        self.assertGreaterEqual(n, 8)

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

    def test_ground_pads_are_tied_to_the_plane(self):
        """Every ground pad that lives only on F.Cu should have its own via down
        to In1.Cu, placed by the builder before routing. This is what four layers
        buy: on two layers eighteen of these pads ended up stranded on islands
        the routed copper cut out of the top pour, with nowhere to stitch them."""
        vias = [v.GetPosition() for v in self.board.Tracks()
                if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"]
        near = pcbnew.FromMM(pcb_builder.TIE_NEAR)
        tied, total = [], 0
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                if (pad.GetNetname() != "GND" or not pad.IsOnLayer(pcbnew.F_Cu)
                        or pad.IsOnLayer(pcbnew.B_Cu)):
                    continue
                total += 1
                c = pad.GetPosition()
                if any(abs(v.x - c.x) < near and abs(v.y - c.y) < near
                       for v in vias):
                    tied.append(fp.GetReference() + "." + pad.GetNumber())
        self.assertGreaterEqual(total, 50)
        # not every pad can have one - some are inside the VBAT or 12V pours,
        # some are hemmed in by their own footprint (U5's LGA ground pads, the
        # module's thermal pad, J5's shield legs) - so this is a floor, not a
        # rule. The pads that end up without a tie are covered by
        # test_no_gnd_pad_is_stranded_on_an_island.
        self.assertGreaterEqual(len(tied), 40, f"only {len(tied)} of {total} tied")

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

    def test_vbat_carries_the_current(self):
        """The XT60 -> U2 path has to carry 20 A, which is where the BTS7002
        sits, and it is cut two ways because it turns a corner.

        The corridor runs east across the lower half of the board, so its cross
        section is a vertical cut. The riser turns north into U2's tab, so its
        cross section is a *horizontal* cut - and that is the one that was wrong
        the first time round: x-slices never cross the riser at all, and its
        narrowest transverse cut was 21.8 mm, 15.2 A, not the 20 the switch
        needs.

        Both are scanned on 0.1 / 0.25 mm lines and asserted in amps, not
        millimetres: 30 mm of 1 oz internal copper is 19.2 A at 20 K, so a width
        that sounds generous is not automatically enough."""
        inner = _fill_of(self.board, "VBAT", pcbnew.In2_Cu)
        outer = _fill_of(self.board, "VBAT", pcbnew.F_Cu)
        W, H = placement.BOARD_W, placement.BOARD_H

        worst, y = (999.0, None, 0, 0), 24.6      # U2's tab pour starts at 24.26
        while y <= 34.5:                          # ... the corridor takes over
            a = _down(inner, y, 0.0, W, w=0.1)[0]
            b = _down(outer, y, 0.0, W, w=0.1)[0]
            worst = min(worst, (_amps(a, b), round(y, 2), round(a, 2), round(b, 2)))
            y += 0.1
        self.assertGreaterEqual(worst[0], 20.0,
                                f"riser: {worst[0]:.1f} A at y = {worst[1]} "
                                f"({worst[2]} mm In2 + {worst[3]} mm F.Cu)")

        worst, x = (999.0, None, 0, 0), 24.0      # east of the XT60's own barrel
        while x <= 99.0:                          # ... to the tab
            a = _across(inner, x, 30.0, H, w=0.1)[0]
            b = _across(outer, x, 30.0, H, w=0.1)[0]
            worst = min(worst, (_amps(a, b), round(x, 2), round(a, 2), round(b, 2)))
            x += 0.25
        self.assertGreaterEqual(worst[0], 20.0,
                                f"corridor: {worst[0]:.1f} A at x = {worst[1]} "
                                f"({worst[2]} mm In2 + {worst[3]} mm F.Cu)")

        self.assertEqual(_fill_of(self.board, "VBAT", pcbnew.B_Cu).Area(), 0,
                         "VBAT is on In2 now, nothing of it belongs on B.Cu")
        # In2 in one piece, and the F.Cu half is the two pad-level pours plus the
        # spread that fills the open ground between and above them
        self.assertEqual(inner.OutlineCount(), 1)
        self.assertGreater(outer.Area() / 1e12, 700.0)

    def test_vbat_planes_are_stitched_together(self):
        """The In2 plane and the F.Cu pours are one conductor only through vias,
        so there have to be plenty, and they have to be the big ones."""
        vias = [v for v in self.board.Tracks()
                if v.GetClass() == "PCB_VIA" and v.GetNetname() == "VBAT"]
        self.assertGreaterEqual(len(vias), 90)
        for v in vias:
            self.assertEqual(pcbnew.ToMM(v.GetWidth(pcbnew.F_Cu)), 0.8)

    def test_12v_bus_carries_the_branches(self):
        """1 oz on every layer, so In2 counts at the internal k and F.Cu at the
        external one. Per branch: the comb tooth that feeds each connector's pin
        1 is >= 3 mm of F.Cu. The arm out of U2's OUT pads carries all six.

        And the run along the top edge tapers: it is fed at the arm on the right
        and sheds a sixth of the load at every connector going west, so what it
        has to carry at a given x is (connectors still to the west) / 6 of 20 A.
        The stretch between J15 and the arm is the tight one - five branches
        through the part of the comb that has no tooth to widen it."""
        front = _fill_of(self.board, "12V_LED", pcbnew.F_Cu)
        inner = _fill_of(self.board, "12V_LED", pcbnew.In2_Cu)
        pins = sorted(pcbnew.ToMM(self.board.FindFootprintByReference(f"J1{i}")
                                  .FindPadByNumber("1").GetPosition().x)
                      for i in range(1, 7))
        for i, cx in enumerate(pins, 1):
            # just below the connector pad row, where the tooth is on its own
            width, _ = _down(front, 7.5, cx - 4.5, cx + 2.6)
            self.assertGreaterEqual(width, 3.0,
                                    f"J1{i}'s comb tooth is {width:.1f} mm")
        # the arm, below the lane cut out of the keep-out and above U2's OUT pads
        f_arm, _ = _down(front, 21.0, 85.0, 101.0)
        i_arm, _ = _down(inner, 21.0, 85.0, 101.0)
        self.assertGreaterEqual(_amps(i_arm, f_arm), 20.0,
                                f"the 12V arm is {f_arm:.1f} mm on F.Cu and "
                                f"{i_arm:.1f} mm on In2")
        # from the first connector east to where the arm joins the run: J16's
        # tooth is the arm, and everything east of it is the arm's own copper
        worst, x = (999.0, None, 0, 0, 0), pins[0] + 0.5
        while x <= pins[-1] - 4.5:
            left = sum(1 for p in pins if p < x)  # branches still to be fed
            a = _across(inner, x, 0.0, 25.0, w=0.1)[0]
            b = _across(front, x, 0.0, 25.0, w=0.1)[0]
            worst = min(worst, (_amps(a, b) - 20.0 * left / 6.0, round(x, 2),
                                left, round(a, 2), round(b, 2)))
            x += 0.2
        self.assertGreaterEqual(worst[0], 0.0,
                                f"the 12V run is {-worst[0]:.1f} A short at "
                                f"x = {worst[1]} with {worst[2]} branches left "
                                f"({worst[3]} mm In2 + {worst[4]} mm F.Cu)")
        self.assertEqual(_fill_of(self.board, "12V_LED", pcbnew.B_Cu).Area(), 0)

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
        path: the island needs a via or a through-hole pad of its own, or a track
        that leaves it. On four layers the via always has somewhere to land -
        In1.Cu is solid ground under every square millimetre of the board."""
        vias = [t for t in self.board.Tracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
        vias = list(vias)
        runs = [t for t in self.board.Tracks()
                if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND"
                and t.IsOnLayer(pcbnew.F_Cu)]
        pads = [(fp.GetReference() + "." + pad.GetNumber(), pad)
                for fp in self.board.GetFootprints() for pad in fp.Pads()
                if pad.GetNetname() == "GND" and pad.IsOnLayer(pcbnew.F_Cu)]
        # a through-hole pad is itself the way to the other layer
        holes = [pad for _, pad in pads if pad.IsOnLayer(pcbnew.B_Cu)]
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
                if any(island.Collide(v.GetPosition()) for v in vias + holes):
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
        for layer in CU:
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
        """Spec: nothing metallic under the ESP32 antenna, on any copper layer -
        the two planes included, or the module radiates into a sheet of copper."""
        x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
        want = _rect(max(x0, 0.0), y0, x1, y1)      # the part that is on the board
        for layer in CU:
            hit = [z for z in self.board.Zones()
                   if z.GetIsRuleArea() and z.IsOnLayer(layer)
                   and z.GetDoNotAllowZoneFills() and z.GetDoNotAllowTracks()
                   and z.GetDoNotAllowVias() and _covers(z.Outline(), want)]
            self.assertTrue(hit, f"no antenna rule area on {pcbnew.LayerName(layer)}")

    # ---- silkscreen -------------------------------------------------------

    def _silk_texts(self):
        return {t.GetText() for t in self.board.GetDrawings()
                if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() == pcbnew.F_SilkS}

    def test_silk_labels_present(self):
        """Every connector, jumper and button says what it is without the schematic."""
        texts = self._silk_texts()
        want = ["DriftAnalyser v2", "2026-09", "12V DATA GND", "12V IN", "+", "-",
                "USB", "OBD", "CANH", "CANL", "K", "GND", "CAN TERM", "K PULLUP",
                "UART0: 3V3 GND TX RX", "EXT: 3V3 GND TX2 RX2 SDA SCL",
                "X", "Y", "nose = +X", "BOOT", "EN"]
        want += [f"LED{i}" for i in range(1, 7)]
        self.assertEqual([w for w in want if w not in texts], [])

    def test_xt60_polarity_marked_once(self):
        """The XT60's own footprint prints a "+" and a "-" beside the other two
        pads: leave both pairs on and the board tells you to wire it backwards.
        Exactly one of each survives, and the "+" is over the VBAT hole."""
        j1 = self.board.FindFootprintByReference("J1")
        near = []
        for t in list(self.board.GetDrawings()) + list(j1.GraphicalItems()):
            if not isinstance(t, pcbnew.PCB_TEXT) or t.GetLayer() != pcbnew.F_SilkS:
                continue
            if t.GetText() in ("+", "-"):
                p = t.GetPosition()
                near.append((t.GetText(), pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)))
        self.assertEqual(sorted(t for t, _, _ in near), ["+", "-"], near)
        pads = {p.GetNumber(): p for p in j1.Pads() if p.GetNumber()}
        self.assertEqual(pads["2"].GetNetname(), "VBAT")   # the straight-side contact
        self.assertEqual(pads["1"].GetNetname(), "GND")    # the chamfered-side one
        def gap(x, y, pad):
            """Distance from a point to the pad's copper, 0 inside it. The pads
            are 4.1 mm across and 7.2 mm apart, so centre distance says little."""
            bb = pad.GetBoundingBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in
                              (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))

        for mark, net in (("+", "VBAT"), ("-", "GND")):
            x, y = next((x, y) for t, x, y in near if t == mark)
            mine = next(p for p in j1.Pads() if p.GetNetname() == net)
            other = next(p for p in j1.Pads()
                         if p.GetNumber() and p.GetNetname() != net)
            d, far = gap(x, y, mine), gap(x, y, other)
            self.assertLess(d, 3.0, f"{mark} is {d:.1f} mm from its {net} pad")
            self.assertLess(d + 3.0, far,
                            f"{mark} is {d:.1f} mm from {net} and {far:.1f} mm from "
                            f"the other pad - not clearly at one of them")

    def test_no_silk_warnings(self):
        """Silk that overlaps a pad, another label or the outline is silk the fab
        drops or smears: the whole legend has to survive the panel."""
        silk = [v for v in self._drc("drc-silk.json", ("--severity-all",))["violations"]
                if v["type"].startswith("silk")]
        self.assertEqual(silk, [], json.dumps(silk[:5], indent=1, ensure_ascii=False))

    def test_values_hidden(self):
        """Only references stay on the board; values would just crowd the silk."""
        shown = [fp.GetReference() for fp in self.board.GetFootprints()
                 if fp.Value().IsVisible()]
        self.assertEqual(shown, [])

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


    # ---- fab outputs ------------------------------------------------------

    def test_fab_files(self):
        """One command has to produce everything the fab is sent, from this board."""
        import csv
        from gen import export
        export.export_fab()
        fab = os.path.join(env.PROJECT_DIR, "fab")

        def path(name):
            f = os.path.join(fab, name)
            self.assertTrue(os.path.exists(f) and os.path.getsize(f) > 0, name)
            return f

        import zipfile
        with zipfile.ZipFile(path("gerbers.zip")) as z:
            names = z.namelist()
        for want in ("F_Cu", "In1_Cu", "In2_Cu", "B_Cu", "F_Silkscreen", "B_Silkscreen",
                     "F_Mask", "B_Mask", "F_Paste", "B_Paste", "Edge_Cuts",
                     "PTH.drl", "NPTH.drl"):
            self.assertTrue([n for n in names if want in n], f"{want} missing from gerbers.zip")

        bom = list(csv.DictReader(open(path("BOM.csv"))))
        self.assertEqual(list(bom[0].keys()), ["Comment", "Designator", "Footprint", "LCSC Part #"])
        refs = [r for row in bom for r in row["Designator"].split(",")]
        self.assertEqual(sorted(refs), sorted(p.ref for p in model.PARTS))
        self.assertEqual([r for r in bom if not r["LCSC Part #"]], [])

        cpl = list(csv.DictReader(open(path("CPL.csv"))))
        self.assertEqual(list(cpl[0].keys()), ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        self.assertEqual({r["Designator"] for r in cpl}, {p.ref for p in model.PARTS})
        self.assertEqual({r["Layer"] for r in cpl}, {"Top"})

        for name in ("render-top.svg", "README-fab.md"):
            path(name)


if __name__ == "__main__":
    unittest.main()
