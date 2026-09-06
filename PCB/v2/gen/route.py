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

# The power pours are copper the router must not cut: the VBAT run on B.Cu is the
# 30 A path to the switch, and one signal crossing it breaks the board. They go
# into the DSN as keep-outs, and their nets are split pad by pad so the router
# never tries to reach a pad the pour already holds - the split keeps every pad
# in its netclass, which is what sets the clearance the router leaves around it.
BUS = ("VBAT", "12V_LED")
POURED = ("GND",) + BUS

# Freerouting reads these on top of its own config file (FREEROUTING__ROUTER__*)
ROUTER_ENV = {
    # fanout drops a via next to every SMD pad: on a 2 layer board with planes
    # that is 100+ extra holes and nothing gained
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
DSN = os.path.join(env.PROJECT_DIR, "fab", "route.dsn")
SES = os.path.join(env.PROJECT_DIR, "fab", "route.ses")

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


def split_bus_nets(dsn, nets=BUS):
    """One net per pad, all of them still in the netclass the original was in.
    The pour connects these pads; the router has nothing to do for them and must
    not try - VBAT is a 3 mm netclass and no gap on this board takes 3 mm."""
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
                 # back-side copper and the vias down it carry the current.
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
    """Fence the power pours off. KiCad exports zones as `(plane ...)`, which tells
    Freerouting the net is connected but not that the copper matters, so without
    this it drives signal traces straight through the VBAT run on the back side
    and cuts the 30 A path into pieces."""
    board = pcbnew.LoadBoard(pcb)
    outs = []
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() not in nets:
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
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


def drop_gnd_planes(dsn):
    """Take both ground pours out of the DSN. KiCad exports zones as `(plane ...)`,
    and a plane tells Freerouting the whole net is already connected, so it routes
    no GND at all. On two layers that is a lie the moment its own traces cross a
    pour: with the top plane held back it ties every F.Cu ground pad down to the
    back plane, and with the back plane held back too it actually routes ground,
    which is the only way the net comes out in one piece. The pours go back on top
    of that copper afterwards and only add to it."""
    with open(dsn) as f:
        text = f.read()
    dropped = 0
    while "(plane GND (polygon" in text:
        i = text.index("(plane GND (polygon")
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    break
        start = text.rindex("\n", 0, i) + 1
        end = text.index("\n", j) + 1
        text = text[:start] + text[end:]
        dropped += 1
    with open(dsn, "w") as f:
        f.write(text)
    return dropped


def keepout_layers(dsn):
    """Layers whose board-level keepout covers the antenna box, by DSN geometry."""
    with open(dsn) as f:
        text = f.read()
    structure = text.split("(placement", 1)[0]     # board scope only, not the images
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
        r = subprocess.run([JAVA, f"-Duser.home={workdir}", "-jar", JAR,
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
    x0, y0, x1, y1 = placement.ANTENNA_KEEPOUT
    x0 = max(x0, 0.0)
    box = pcbnew.BOX2I(MM(x0, y0), pcbnew.VECTOR2I(pcbnew.FromMM(x1 - x0),
                                                   pcbnew.FromMM(y1 - y0)))
    doomed = [t for t in board.Tracks() if box.Intersects(t.GetBoundingBox())]
    for t in doomed:
        board.Remove(t)
    return len(doomed)


# The fill already keeps 0.4 mm from foreign copper, so a via whose edge lands on
# the fill boundary still clears everything: the margin only has to be the via
# radius. The small via is the Default netclass one, for pockets 0.8 cannot enter.
STITCH_VIAS = ((0.8, 0.4, 0.45), (0.6, 0.3, 0.35))


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


def _spot(island, other, pads, margin, step=0.3):
    """A point that sits `margin` inside this island and inside same-net copper on
    the other layer. The fill already keeps its distance from foreign copper, so a
    point that deep in it is a legal via position."""
    m = pcbnew.FromMM(margin)
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
                    and not any(pad.HitTest(p, m) for pad in pads)):
                return x, y
            x += step
        y += step
    return None


def _islands(board, net):
    """[(layer, poly)] for every filled island of the net, both layers."""
    return [(layer, poly) for layer in (pcbnew.F_Cu, pcbnew.B_Cu)
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

    for t in board.Tracks():
        if t.GetNetname() != net:
            continue
        if t.GetClass() == "PCB_VIA":
            union(which(pcbnew.F_Cu, t.GetPosition()), which(pcbnew.B_Cu, t.GetPosition()))
        else:
            layer = pcbnew.F_Cu if t.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            union(which(layer, t.GetStart()), which(layer, t.GetEnd()))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != net:
                continue
            if pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.B_Cu):
                union(which(pcbnew.F_Cu, pad.GetPosition()),
                      which(pcbnew.B_Cu, pad.GetPosition()))
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
    for _ in range(6):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        progress = False
        for net in nets:
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
                        spot = _spot(poly, far, pads, margin)
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


def import_ses(pcb, ses):
    board = pcbnew.LoadBoard(pcb)
    ok = pcbnew.ImportSpecctraSES(board, ses)
    if not ok:
        raise RuntimeError(f"SES import of {ses} failed")
    n = strip_keepout(board)
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
    return n, len(vias), len(tracks), added, stranded


def route(pcb=PCB, dsn=DSN, ses=SES, passes=PASSES):
    export_dsn(pcb, dsn)
    kept = protect_existing(dsn)
    split = split_bus_nets(dsn)
    fenced = bus_keepouts(PCB, dsn)
    planes = drop_gnd_planes(dsn)
    layers = keepout_layers(dsn)
    print(f"dsn: {dsn} ({os.path.getsize(dsn) // 1024} kB), {kept} wires/vias protected, "
          f"{split} bus pads split off, {fenced} pour keep-outs, "
          f"{planes} GND planes held back, "
          f"antenna keep-out on {sorted(layers)}")
    if layers != {"F.Cu", "B.Cu"}:
        raise RuntimeError("the antenna keep-out is missing from the DSN")
    secs, log = run_freerouting(dsn, ses, passes)
    print(summarize(log))
    print(f"freerouting: {passes} passes, {secs:.0f} s")
    stripped, vias, tracks, added, stranded = import_ses(pcb, ses)
    print(f"imported: {tracks} tracks, {vias} vias, {stripped} removed from the keep-out")
    print(f"stitched: {len(added)} vias into cut-off pour islands"
          + (f", {len(stranded)} islands left stranded: {stranded}" if stranded else ""))


if __name__ == "__main__":
    route()
