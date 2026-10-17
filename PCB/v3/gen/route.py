"""Autoroute the signal nets with Freerouting and bring the result back.

The power nets are already done: the pours plus the stubs pcb_builder draws reach
every pad of GND / VBAT / 12V_LED, so what is left here is signal copper.

Needs pcbnew, so run it with KiCad's python:
    KICAD_PY -m gen.route              (cwd = PCB/v2)
    DA2_PASSES=100 KICAD_PY -m gen.route
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pcbnew
from pcbnew import VECTOR2I_MM as MM

from gen import env, pcb_builder, placement

JAR = os.path.expanduser("~/.local/freerouting/freerouting.jar")
# Freerouting 2.4.1 wants Java >= 25; macOS /usr/bin/java is usually older or absent
JAVA = os.environ.get("JAVA", "/opt/homebrew/opt/openjdk/bin/java")
PASSES = int(os.environ.get("DA2_PASSES", "200"))

# The power pours are copper the router must not cut. On the outer layers they go
# into the DSN as keep-outs, and their nets are split pad by pad so the router
# never tries to reach a pad the pour already holds - the split keeps every pad
# in its netclass, which is what sets the clearance the router leaves around it.
# The In2 halves of VBAT and 12V_LED need no fence: nothing routes on In2 (see
# dedicate_power_layers), so only the router's vias ever cross them.
BUS = ("VBAT", "12V_LED")
POURED = ("GND",) + BUS

# F.Cu and B.Cu carry the signals; In1.Cu is the solid ground plane and In2.Cu
# the VBAT / 12V_LED power plane, and nothing is ever routed on either of them.
OUTER = (pcbnew.F_Cu, pcbnew.B_Cu)
CU = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
INNER = ("In1.Cu", "In2.Cu")

# Freerouting reads these on top of its own config file (FREEROUTING__ROUTER__*)
ROUTER_ENV = {
    # fanout drops a via next to every SMD pad: with two plane layers under every
    # pad that is 100+ extra holes and nothing gained
    "FREEROUTING__ROUTER__FANOUT__ENABLED": "false",
    # it necks traces down to 0.15 mm to enter fine pads; the board minimum is 0.2
    "FREEROUTING__ROUTER__NECK_WIDTH_UM": "200",
}

# Freerouting 2.4.1 keeps its settings in the user profile and, with the GUI
# enabled (the default), the batch worker never hands the routed board to the
# writer: it saves a 0 byte .ses and says nothing. Run it against a config of our
# own with the GUI off - that is also what keeps the user's profile untouched.
CONFIG = {
    # it dereferences the id without checking, so it has to be there
    "profile": {"id": "da2b0a2d-0000-4000-8000-000000000001",
                "email": "", "allow_telemetry": False, "allow_contact": False},
    "gui": {"enabled": False},
    "router": {"fanout": {"enabled": False}},
    "usage_and_diagnostic_data": {"disable_analytics": True},
    "logging": {"console": {"enabled": True, "level": "INFO"},
                "file": {"enabled": False}},
}


PCB = os.path.join(env.PROJECT_DIR, env.PROJECT_NAME + ".kicad_pcb")
# scratch, not fab/: the DSN carries an absolute path on its first line and the
# plane scopes come out in whatever order the zones were built, so a tracked copy
# is dirty after every build even when nothing changed. DA2_DSN puts it back
# somewhere useful when it needs reading.
DSN = os.environ.get("DA2_DSN") or os.path.join(
    tempfile.gettempdir(), env.PROJECT_NAME + "-route.dsn")
# The session file is committed, and it is what makes this build reproducible:
# Freerouting has no seed, so a fresh draw of the same input lands somewhere else
# every time (26 draws of this board came out at between 0 and 5 open links).
# With fab/route.ses present, `route()` replays it instead of drawing again;
# DA2_REROUTE=1 asks for a new draw, and DA2_SES points somewhere else.
SES = os.path.join(env.PROJECT_DIR, os.environ.get("DA2_SES", "fab/route.ses"))
REROUTE = os.environ.get("DA2_REROUTE") == "1"

# what the builder leaves on the board: the power stubs and the U5 / U1 escapes
BUILDER_TRACKS = 100

_KEEPOUT = re.compile(r'\(keepout\s+""\s+\(polygon\s+(\S+)\s+\d+\s+([-\d.\s]+)\)')


def _profile_home(root):
    """A throwaway $HOME holding just freerouting.json."""
    for sub in ("Library/Application Support/freerouting", ".config/freerouting"):
        d = os.path.join(root, sub)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "freerouting.json"), "w") as f:
            json.dump(CONFIG, f, indent=1)
    return root


def export_dsn(pcb, dsn):
    board = pcbnew.LoadBoard(pcb)
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    if not ok or not os.path.exists(dsn):
        raise RuntimeError(f"DSN export to {dsn} failed")


def dedicate_power_layers(dsn, layers=INNER):
    """Tell Freerouting the two inner layers are planes, not routing layers.

    KiCad writes `(type signal)` for all four copper layers and has no setting
    that says otherwise, so without this the router treats In1 and In2 as two
    more signal layers and buries traces in the ground plane. Freerouting reads
    `(type power)` (Layer.isSignal) and says so on startup: "Layer 'In1.Cu' is a
    dedicated power plane and cannot be routed. Forcing active state to false."

    A Specctra `wire_keepout` would be the other way to say it, but Freerouting's
    keyword table only knows `keepout`, `via_keepout` and `place_keepout` - and a
    plain `keepout` would also bar the vias, which is exactly what the planes
    need to be reachable at all."""
    with open(dsn) as f:
        text = f.read()
    for name in layers:
        want = f"(layer {name}\n      (type signal)"
        if want not in text:
            raise RuntimeError(f"no signal layer {name} in the DSN")
        text = text.replace(want, f"(layer {name}\n      (type power)")
    with open(dsn, "w") as f:
        f.write(text)
    return len(layers)


def protect_existing(dsn):
    """Every wire and via in the DSN is ours (the power stubs and the stitching).
    KiCad exports them as `route`, which Freerouting is free to rip up and redraw
    at the netclass width - 3 mm on VBAT, which fits nowhere. Nail them down."""
    with open(dsn) as f:
        text = f.read()
    out = text.replace("(type route)", "(type protect)")
    with open(dsn, "w") as f:
        f.write(out)
    return text.count("(type route)")


def split_bus_nets(dsn, nets=POURED):
    """One net per pad, all of them still in the netclass the original was in.

    The pours connect these pads; the router has nothing to do for them and must
    not try - VBAT is a 3 mm netclass and no gap on this board takes 3 mm. GND is
    in here for the other half of the reason: a single-pad net is still a pad, so
    the router keeps the netclass clearance around it, which is exactly what it
    stops doing when the pad is swallowed by a declared plane."""
    with open(dsn) as f:
        text = f.read()
    added = 0
    for name in nets:
        m = re.search(r"( *)\(net %s\s*\n\s*\(pins ([^)]*)\)\n *\)\n"
                      % re.escape(name), text)
        if not m:
            raise RuntimeError(f"no (net {name}) in the DSN")
        pad, rest = m.group(2).split()[0], m.group(2).split()[1:]
        extra = [f"{name}_pad{i}" for i in range(2, len(rest) + 2)]
        pre = m.group(1)
        block = f"{pre}(net {name}\n{pre}  (pins {pad})\n{pre})\n"
        block += "".join(f"{pre}(net {e}\n{pre}  (pins {p})\n{pre})\n"
                         for e, p in zip(extra, rest))
        text = text[:m.start()] + block + text[m.end():]
        # the class list is a run of bare tokens between the class name and (circuit
        cm = re.search(r"\(class (\S+)((?:[^()]*?\b%s\b[^()]*?))\(circuit"
                       % re.escape(name), text)
        if not cm:
            raise RuntimeError(f"{name} is in no netclass")
        text = (text[:cm.end(2)] + " ".join(extra) + "\n      " + text[cm.end(2):])
        added += len(extra)
    with open(dsn, "w") as f:
        f.write(text)
    return added


# The J16 arm of the 12V comb reaches down to U2 across the whole corner where
# R36, D16 and J16's data pin live, so fencing the pour off there would leave the
# sixth LED channel with nowhere to go. These two boxes are cut out of the fence:
# what stays protected is the left 3.5 mm of the arm, which is the current path.
KEEPOUT_LANES = [(91.0, 9.0, 100.0, 20.0, None), (93.5, 4.0, 100.0, 9.0, None),
                 # and a slit across the protected part, or the sixth channel's
                 # series resistor can only be reached the long way round. Front
                 # only: a trace may cut the front pour there because the arm's
                 # In2 copper and the twelve vias down it carry the current.
                 (87.0, 15.0, 91.0, 18.0, "F.Cu")]


def _lane_mask(layer):
    mask = pcbnew.SHAPE_POLY_SET()
    for x0, y0, x1, y1, only in KEEPOUT_LANES:
        if only and only != layer:
            continue
        mask.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            mask.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return mask


def bus_keepouts(pcb, dsn, nets=BUS):
    """Fence the power pours off on the routing layers. KiCad exports zones as
    `(plane ...)`, which tells Freerouting the net is connected but not that the
    copper matters, so without this it drives signal traces straight through the
    12V comb and the VBAT tab pour and cuts the current path into pieces."""
    board = pcbnew.LoadBoard(pcb)
    outs = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in nets:
            continue
        for layer in OUTER:
            if not z.IsOnLayer(layer):
                continue
            fence = pcbnew.SHAPE_POLY_SET()
            fence.BooleanSubtract(z.Outline(), _lane_mask(board.GetLayerName(layer)))
            for n in range(fence.OutlineCount()):
                o = fence.Outline(n)
                pts = [(pcbnew.ToMM(o.CPoint(k).x), pcbnew.ToMM(o.CPoint(k).y))
                       for k in range(o.PointCount())]
                path = "  ".join(f"{round(x * 1000)} {round(-y * 1000)}"
                                 for x, y in pts + pts[:1])
                outs.append(f'    (keepout "" (polygon {board.GetLayerName(layer)} 0'
                            f'  {path}))')
    with open(dsn) as f:
        text = f.read()
    # in after the antenna keep-out, which is the last one in the board scope
    cut = text.index("\n", text.rindex('    (keepout "" (polygon', 0,
                                       text.index("(placement"))) + 1
    text = text[:cut] + "\n".join(outs) + "\n" + text[cut:]
    with open(dsn, "w") as f:
        f.write(text)
    return len(outs)


def drop_plane(dsn, net, layer):
    """Take one `(plane ...)` scope out of the DSN.

    All four ground pours go. Freerouting treats a plane as copper a trace may
    cross, and it extends that licence to the pads sitting inside it: with the
    pours declared it put twelve vias between 0.14 and 0.22 mm from D21's and
    C17's ground pads, and KiCad's DRC called every one of them. Leaving the
    pours out and splitting the ground pads off net by net (split_bus_nets)
    turns them back into ordinary pads that get their 0.25 mm, and still gives
    the router nothing to route: ground is finished by the pours and by the vias
    stitch_islands adds afterwards, all of which land on In1.Cu.

    Declaring them and routing ground properly instead was measured and is
    worse: 222 items instead of 148, 63 of them still unrouted after 180 s, and
    Freerouting died in the optimiser without writing a session file."""
    with open(dsn) as f:
        text = f.read()
    head = f"(plane {net} (polygon {layer}"
    dropped = 0
    while head in text:
        i = text.index(head)
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
        text = text[:text.rindex("\n", 0, i) + 1] + text[text.index("\n", j) + 1:]
        dropped += 1
    with open(dsn, "w") as f:
        f.write(text)
    return dropped


def check_planes(dsn):
    """The planes still in the DSN, for the log and for a sanity read: VBAT and
    12V_LED, which the router must see so it does not try to reach their pads."""
    with open(dsn) as f:
        text = f.read()
    return sorted(re.findall(r"\(plane (\S+) \(polygon (\S+)", text))


def keepout_layers(dsn):
    """Layers whose board-level keepout covers the antenna box, by DSN geometry."""
    with open(dsn) as f:
        text = f.read()
    structure = text.split("(placement", 1)[0]     # board scope only, not the images
    if not placement.ANTENNA_KEEPOUT:              # WROOM-1U: u.FL, no antenna box
        return set()
    x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
    want = (max(x0, 0.0) * 1000, -y1 * 1000, x1 * 1000, -y0 * 1000)
    found = set()
    for layer, coords in _KEEPOUT.findall(structure):
        v = [float(n) for n in coords.split()]
        xs, ys = v[0::2], v[1::2]
        if (min(xs) <= want[0] and min(ys) <= want[1]
                and max(xs) >= want[2] and max(ys) >= want[3]):
            found.add(layer)
    return found


def run_freerouting(dsn, ses, passes=PASSES):
    if not os.path.exists(JAR):
        raise RuntimeError(f"no freerouting jar at {JAR}")
    if os.path.exists(ses):
        os.remove(ses)
    t0 = time.time()
    workdir = _profile_home(tempfile.mkdtemp(prefix="freerouting-"))
    try:
        # -mt 1: the multi threaded optimizer is known to shove traces into each
        # other (it says so itself on startup) and it did short 5V_BUCK to BUCK_FB
        # -Xmx3g: the default max heap is a quarter of RAM, and two runs were
        # killed outright by the OS mid-pass on a loaded machine. The router's
        # own peak is around 1.2 GB, so this only stops it reaching for more.
        r = subprocess.run([JAVA, f"-Duser.home={workdir}", "-Xmx3g", "-jar", JAR,
                            "-de", dsn, "-do", ses, "-mp", str(passes),
                            "-mt", "1", "-l", "en"],
                           capture_output=True, text=True, timeout=7200,
                           cwd=workdir, env={**os.environ, **ROUTER_ENV})
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    log = (r.stdout or "") + (r.stderr or "")
    if not os.path.exists(ses):
        raise RuntimeError(log[-3000:])
    return time.time() - t0, log


def summarize(log):
    """The lines worth keeping out of Freerouting's chatter."""
    keep = ("Starting", "pass", "unrouted", "incomplete", "environment variable",
            "Routing", "was completed", "stage completed", "Freerouting v")
    lines = [l.strip() for l in log.splitlines()
             if any(k.lower() in l.lower() for k in keep)]
    return "\n".join(lines[-25:])


def strip_keepout(board):
    """Anything the router put under the ESP32 antenna, gone. The DSN carries the
    keep-out, so this should never find work; it is here because a track there
    would be a radio problem long before DRC noticed it."""
    if not placement.ANTENNA_KEEPOUT:
        return 0
    x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
    x0 = max(x0, 0.0)
    box = pcbnew.BOX2I(MM(x0, y0), pcbnew.VECTOR2I(pcbnew.FromMM(x1 - x0),
                                                   pcbnew.FromMM(y1 - y0)))
    doomed = [t for t in board.Tracks() if box.Intersects(t.GetBoundingBox())]
    for t in doomed:
        board.Remove(t)
    return len(doomed)


# The fill keeps 0.4 mm from foreign copper on the island's own layer, so the
# margin there only has to be the via radius. It says nothing about the other
# three layers, though, and a stitching via is a through via: hence _blockers.
# The small via is the Default netclass one, for pockets 0.8 cannot enter.
# (diameter, drill, how far inside the fill the centre has to sit). The fill is
# already 0.4 mm clear of foreign copper on the island's own layer, so the last
# entry - a small via whose barrel pokes 0.1 mm past the fill edge and still
# keeps 0.25 mm to anything else - is the one that gets into a 2 mm2 pocket.
STITCH_VIAS = ((0.8, 0.4, 0.45), (0.6, 0.3, 0.35), (0.6, 0.3, 0.2))
# what the Power netclass asks between a via and anything else
CLEARANCE = pcbnew.FromMM(0.25)


def _blockers(board, net, cell=4.0):
    """Everything a through via must not land on, bucketed 4 mm at a time.

    Foreign tracks, vias and pads on *any* layer, plus every via of any net (two
    vias in the same hole is not a connection, it is a mess). Without this the
    stitcher reads its own layer's fill, sees 0.45 mm of clear ground copper, and
    drops a via straight through a signal trace on the other side - after which
    KiCad's net propagation quietly renames the via to that signal's net and the
    island it was meant to rescue is still adrift."""
    grid = {}
    items = [t for t in board.Tracks()
             if t.GetClass() == "PCB_VIA" or t.GetNetname() != net]
    items += [pad for fp in board.GetFootprints() for pad in fp.Pads()
              if pad.GetNetname() != net]
    for it in items:
        bb = it.GetBoundingBox()
        for cx in range(int(pcbnew.ToMM(bb.GetLeft()) // cell),
                        int(pcbnew.ToMM(bb.GetRight()) // cell) + 1):
            for cy in range(int(pcbnew.ToMM(bb.GetTop()) // cell),
                            int(pcbnew.ToMM(bb.GetBottom()) // cell) + 1):
                grid.setdefault((cx, cy), []).append(it)
    return grid, cell


def _blocked(blockers, p, reach):
    grid, cell = blockers
    cx, cy = int(pcbnew.ToMM(p.x) // cell), int(pcbnew.ToMM(p.y) // cell)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for it in grid.get((cx + dx, cy + dy), ()):
                if it.HitTest(p, reach):
                    return True
    return False


def _fills(board, net, layer):
    """One SHAPE_POLY_SET per filled island of `net` on `layer`."""
    out = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != net or not z.IsOnLayer(layer):
            continue
        sp = z.GetFilledPolysList(layer)
        for i in range(sp.OutlineCount()):
            poly = pcbnew.SHAPE_POLY_SET()
            poly.AddOutline(sp.Outline(i))
            out.append(poly)
    return out


def _spot(island, other, pads, margin, blockers, dia, step=0.1):
    """A point that sits `margin` inside this island and inside same-net copper on
    some other layer, with nothing of another net within reach of the barrel on
    any of the four."""
    m = pcbnew.FromMM(margin)
    reach = pcbnew.FromMM(dia / 2) + CLEARANCE
    inner = pcbnew.SHAPE_POLY_SET(island)
    inner.Deflate(m, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
    if inner.IsEmpty():
        return None
    bb = inner.BBox()
    x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
    x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
    deep = []
    for o in other:
        d = pcbnew.SHAPE_POLY_SET(o)
        d.Deflate(m, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.01))
        if not d.IsEmpty():
            deep.append(d)
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            p = MM(x, y)
            if (inner.Contains(p) and any(d.Contains(p) for d in deep)
                    and not any(pad.HitTest(p, m) for pad in pads)
                    and not _blocked(blockers, p, reach)):
                return x, y
            x += step
        y += step
    return None


def _islands(board, net):
    """[(layer, poly)] for every filled island of the net, on all four layers."""
    return [(layer, poly) for layer in CU
            for poly in _fills(board, net, layer)]


def _groups(board, net, islands):
    """Islands grouped into what is actually one piece of copper. Vias tie an
    island on one layer to the island under them on the other; tracks and
    through-hole pads tie islands together the same way."""
    parent = list(range(len(islands)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        if a is None or b is None:
            return
        ra, rb = find(a), find(b)
        parent[ra] = rb

    def which(layer, pos):
        for i, (lay, poly) in enumerate(islands):
            if lay == layer and poly.Collide(pos):
                return i
        return None

    def tie(pos, layers):
        """One piece of copper: everything this item touches, on every layer."""
        hits = [which(layer, pos) for layer in layers]
        hits = [h for h in hits if h is not None]
        for h in hits[1:]:
            union(hits[0], h)

    for t in board.Tracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == "PCB_VIA":
            tie(t.GetPosition(), [l for l in CU if t.IsOnLayer(l)])
        else:
            layer = t.GetLayer()
            union(which(layer, t.GetStart()), which(layer, t.GetEnd()))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != net:
                continue
            on = [l for l in CU if pad.IsOnLayer(l)]
            if len(on) > 1:                     # a through hole ties every layer
                tie(pad.GetPosition(), on)
    out = {}
    for i in range(len(islands)):
        out.setdefault(find(i), []).append(islands[i])
    return list(out.values())


def _add_via(board, net, spot, d, drill):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(MM(*spot))
    v.SetWidth(pcbnew.FromMM(d))
    v.SetDrill(pcbnew.FromMM(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.FindNet(net))
    board.Add(v)


def stitch_islands(board, nets=POURED):
    """Signal traces cut the pours into islands. Anything that is not part of the
    main body of the pour needs a via into it, or the pads sitting on it have no
    return path. Returns (vias added, groups left stranded)."""
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    added = []
    for _ in range(10):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        progress = False
        for net in nets:
            blockers = _blockers(board, net)
            islands = _islands(board, net)
            groups = _groups(board, net, islands)
            if len(groups) < 2:
                continue
            groups.sort(key=lambda g: -sum(p.Area() for _, p in g))
            main = groups[0]
            for g in groups[1:]:
                for layer, poly in sorted(g, key=lambda lp: -lp[1].Area()):
                    far = [p for lay, p in main if lay != layer]
                    spot = None
                    for d, drill, margin in STITCH_VIAS:
                        spot = _spot(poly, far, pads, margin, blockers, d)
                        if spot:
                            break
                    if spot:
                        _add_via(board, net, spot, d, drill)
                        added.append((net, spot, d))
                        progress = True
                        break
        if not progress:
            break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    stranded = []
    for net in nets:
        islands = _islands(board, net)
        groups = _groups(board, net, islands)
        groups.sort(key=lambda g: -sum(p.Area() for _, p in g))
        for g in groups[1:]:
            layer, poly = max(g, key=lambda lp: lp[1].Area())
            bb = poly.BBox()
            stranded.append((net, board.GetLayerName(layer),
                             round(pcbnew.ToMM(bb.GetLeft()), 1),
                             round(pcbnew.ToMM(bb.GetTop()), 1),
                             round(sum(p.Area() for _, p in g) / 1e12, 1)))
    return added, stranded


# What the autorouter would not finish, drawn by hand along free copper found on
# the routed board. Each entry is (net, width, [(x, y, layer), ...]); a via goes in
# wherever the layer changes, so the two points either side of it are the same
# point. Only F and B: In1 and In2 are planes here too. Default netclass:
# 0.25 mm track, 0.6/0.3 via.
HAND_ROUTES = []


def finish_by_hand(board, routes=HAND_ROUTES):
    """Lay the hand-routed connections. They go in after the session import, so
    they are drawn against copper that already exists, and before the fill."""
    layers = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
    for name, width, path in routes:
        net = board.FindNet(name)
        if net is None:
            raise KeyError(f"no net {name}")
        for a, b in zip(path, path[1:]):
            if a[2] == b[2]:
                pcb_builder._track(board, net, layers[a[2]], a[:2], b[:2], width)
            else:
                if a[:2] != b[:2]:
                    raise ValueError(f"{name}: layer change needs one point, not {a} {b}")
                pcb_builder._via(board, net, a[0], a[1], d=0.6, drill=0.3)
    return len(routes)


# the only two vias this board uses: the power one and the Default netclass one
VIA_SIZES = {0.8: 0.4, 0.6: 0.3}


def normalise_via_drills(board):
    """Put the drills back after the session import.

    ImportSpecctraSES drops every via's own drill and leaves it reading the
    netclass default, so the 0.6 mm ground ties the builder drew with a 0.3 mm
    hole come back with the Power class' 0.4 mm one - a 0.10 mm annular ring
    against a 0.15 mm board minimum, and 44 DRC violations. Both of our via
    sizes have exactly one drill, so this just says so again."""
    fixed = 0
    for t in board.Tracks():
        if t.GetClass() != "PCB_VIA":
            continue
        want = VIA_SIZES.get(round(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)), 3))
        if want is None:
            raise RuntimeError(f"via of {pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))} mm "
                               f"at {pcbnew.ToMM(t.GetPosition().x)}, "
                               f"{pcbnew.ToMM(t.GetPosition().y)} is not one of ours")
        if round(pcbnew.ToMM(t.GetDrillValue()), 3) != want:
            t.SetDrill(pcbnew.FromMM(want))
            fixed += 1
    return fixed


def drop_foreign_pad_wires(board):
    """Replayed wires that end on a pad of another net.

    The session is a recording: it was drawn against the netlist of the day, and
    a pad that changes net (J1's two power pins swapped when the XT60's polarity
    was corrected) turns a wire that was fine into a short. The router itself
    cannot be asked again without redrawing the whole board, so the replay drops
    those wires and says so - DRC then has to still come back with nothing
    unconnected, which is what says the copper was redundant."""
    # a plated pad only: an NPTH slot or a mounting hole is a drilled hole with
    # no copper on it, and a wire crossing one is the board outline's problem,
    # not a short
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and pad.IsOnCopperLayer()]
    doomed, dropped = [], []
    for t in board.Tracks():                    # scan first: removing mid-walk
        if t.GetClass() != "PCB_TRACK":         # leaves board.Tracks() unusable
            continue
        for pad in pads:
            if pad.GetNetname() == t.GetNetname() or not pad.IsOnLayer(t.GetLayer()):
                continue
            if pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()):
                doomed.append(t)
                dropped.append((t.GetNetname(), pad.GetParentFootprint().GetReference()
                                + "." + pad.GetNumber(),
                                round(pcbnew.ToMM(t.GetStart().x), 2),
                                round(pcbnew.ToMM(t.GetStart().y), 2)))
                break
    for t in doomed:
        board.RemoveNative(t)       # Remove() hands the C++ object to Python and
    for net, pad, x, y in dropped:  # freeing it here leaves board.Tracks() broken
        print(f"dropped a replayed [{net}] wire off {pad} at {x}, {y}")
    return dropped


def import_ses(pcb, ses):
    board = pcbnew.LoadBoard(pcb)
    ok = pcbnew.ImportSpecctraSES(board, ses)
    if not ok:
        raise RuntimeError(f"SES import of {ses} failed")
    foreign = drop_foreign_pad_wires(board)
    n = strip_keepout(board)
    drills = normalise_via_drills(board)
    stitched = pcb_builder.vbat_stitch(board)
    hand = finish_by_hand(board)
    board.BuildConnectivity()
    added, stranded = stitch_islands(board)
    # aSkipSettings=True, same reason as in pcb_builder: keep the .kicad_pro.
    # kicad-cli normalises that file when it loads it and drops netclasses it does
    # not recognise, so write ours back - DRC after routing has to see them.
    pcbnew.SaveBoard(pcb, board, True)
    pcb_builder.write_project_netclasses()
    pcb_builder.write_design_rules()
    tracks = [t for t in board.Tracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.Tracks() if t.GetClass() == "PCB_VIA"]
    return n, len(vias), len(tracks), added, stranded, hand, drills, stitched, foreign


def already_routed(pcb):
    """True if this board has been through import_ses already. Running route()
    on it a second time would import the same session on top of itself."""
    board = pcbnew.LoadBoard(pcb)
    return sum(1 for t in board.Tracks() if t.GetClass() == "PCB_TRACK") > BUILDER_TRACKS


def route(pcb=PCB, dsn=DSN, ses=SES, passes=PASSES, reroute=REROUTE):
    if already_routed(pcb):
        raise RuntimeError(f"{pcb} is already routed - run gen.pcb_builder first")
    export_dsn(pcb, dsn)
    kept = protect_existing(dsn)
    split = split_bus_nets(dsn, POURED)
    fenced = bus_keepouts(PCB, dsn)
    inner = dedicate_power_layers(dsn)
    for layer in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        drop_plane(dsn, "GND", layer)
    planes = check_planes(dsn)
    layers = keepout_layers(dsn)
    print(f"dsn: {dsn} ({os.path.getsize(dsn) // 1024} kB), {kept} wires/vias protected, "
          f"{split} bus pads split off, {fenced} pour keep-outs, "
          f"{inner} inner layers marked as power planes, "
          f"{len(planes)} planes: {planes}, "
          f"antenna keep-out on {sorted(layers)}")
    if placement.ANTENNA_KEEPOUT and layers != set(INNER) | {"F.Cu", "B.Cu"}:
        raise RuntimeError("the antenna keep-out is missing from the DSN")
    if reroute or not os.path.exists(ses):
        secs, log = run_freerouting(dsn, ses, passes)
        print(summarize(log))
        print(f"freerouting: {passes} passes, {secs:.0f} s")
    else:
        print(f"replaying {ses} ({os.path.getsize(ses) // 1024} kB) - "
              f"set DA2_REROUTE=1 to draw a new one")
    (stripped, vias, tracks, added, stranded, hand, drills, stitched,
     foreign) = import_ses(pcb, ses)
    print(f"imported: {tracks} tracks, {vias} vias, {stripped} removed from the "
          f"keep-out, {drills} via drills restored, "
          f"{hand} connections finished by hand, "
          f"{len(stitched)} extra VBAT vias F.Cu <-> In2"
          + (f", {len(foreign)} replayed wires dropped off foreign pads: {foreign}"
             if foreign else ""))
    print(f"stitched: {len(added)} vias into cut-off pour islands"
          + (f", {len(stranded)} islands left stranded: {stranded}" if stranded else ""))


if __name__ == "__main__":
    route()
