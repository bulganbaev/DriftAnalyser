"""DriftAnalyser v3 customer datasheet (RU) -> datasheet.html, PDF and page PNGs.

Pinout from PCB/v3/gen/model.py (J1_PIN), enclosure sizes from enclosure/v3/enclosure_v3.py.
Run with the enclosure venv (needs cadquery for the enclosure import):
    enclosure/.venv/bin/python PCB/v3/docs/datasheet/gen_datasheet.py
"""
import base64
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "PCB", "v3"))
sys.path.insert(0, os.path.join(ROOT, "enclosure", "v3"))
from gen.model import J1_PIN  # noqa: E402
import enclosure_v3 as E  # noqa: E402

DOC = "DA3-TD-001"
REV = "rev 0.3"
DATE = "2026-10"
STATUS = "предварительная"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HTML = os.path.join(HERE, "datasheet.html")
PDF = os.path.join(HERE, "DriftAnalyser_v3_datasheet.pdf")

INK = "#15171A"
ACC = "#FF5A1F"  # signal orange, used sparingly
SANS = '"IBM Plex Sans","Helvetica Neue",Arial,sans-serif'
MONO = '"IBM Plex Mono",Menlo,monospace'

# ------------------------------------------------------------------ pin groups
# shape: sq = power (solid square), gnd = ground (hatched square), hex = signal
GROUPS = [  # key, name, tag, fill, text colour, shape
    ("p12", "+12V ленты", "+12V", "#D52B1E", "#fff", "sq"),
    ("data", "DATA ленты", "DATA", "#F2C200", "#111", "hex"),
    ("gled", "GND ленты", "GND-L", "#55636F", "#fff", "gnd"),
    ("can", "CAN", "CAN", "#1E9E5A", "#fff", "hex"),
    ("kline", "K-line", "K", "#7A3FC0", "#fff", "hex"),
    ("ign", "Зажигание IGN", "IGN", "#C2185B", "#fff", "sq"),
    ("in", "Входы IN1–IN3", "IN", "#C5CBD3", "#111", "hex"),
    ("v5", "+5V датчиков", "+5V", "#0097A7", "#fff", "sq"),
    ("gsig", "GND сигнальная", "GND-S", "#1A1D21", "#fff", "gnd"),
]
GC = {g[0]: g for g in GROUPS}
HATCH = {"gled": "#8593A0", "gsig": "#5A626C"}
RED = GC["p12"][3]


def pin_info(key):
    """J1_PIN key -> (group, name)."""
    if key.endswith("_12V"):
        return "p12", f"Лента {key[3]}: +12V"
    if key.endswith("_DO"):
        return "data", f"Лента {key[3]}: DATA"
    if key.startswith("LED") and key.endswith("_GND"):
        return "gled", f"Лента {key[3]}: GND"
    return {
        "SIG1_GND": ("gsig", "GND сигнальная"),
        "SIG2_GND": ("gsig", "GND сигнальная"),
        "CANH": ("can", "CAN High"),
        "CANL": ("can", "CAN Low"),
        "KLINE": ("kline", "K-line"),
        "IGN": ("ign", "Зажигание IGN (+12V)"),
        "IN1": ("in", "Вход IN1"),
        "IN2": ("in", "Вход IN2"),
        "IN3": ("in", "Вход IN3"),
        "5V_SENS": ("v5", "+5V питание датчиков"),
    }[key]


PIN = {int(p): (k, *pin_info(k)) for k, p in J1_PIN.items()}
assert sorted(PIN) == list(range(1, 35)), "J1 must use all 34 pins"
KEY2PIN = {k: int(p) for k, p in J1_PIN.items()}
GPINS = {g[0]: sorted(n for n in PIN if PIN[n][1] == g[0]) for g in GROUPS}


def ranges(ns):
    """[1,2,3,4,6] -> '1–4, 6'"""
    ns, out, i = sorted(ns), [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(str(ns[i]) if i == j else f"{ns[i]}, {ns[j]}" if j == i + 1 else f"{ns[i]}–{ns[j]}")
        i = j + 1
    return ", ".join(out)


def css_bg(g):
    _, _, _, fill, _, shape = GC[g]
    if shape == "gnd":
        return f"repeating-linear-gradient(45deg,{fill} 0 1.3px,{HATCH[g]} 1.3px 2.4px)"
    return fill


def chip(g, cls="ch"):
    shape = GC[g][5]
    return f'<span class="{cls} {shape}" style="background:{css_bg(g)}"></span>'


# ------------------------------------------------------------------ page 1: J1 face, line art
def pin_xy(n):
    """Face view of the header (mating side), mm. Pin 1 top-left, rows 1-9 / 10-17 / 18-25 / 26-34."""
    if n <= 9:
        return (n - 1) * 3.0, 0.0
    if n <= 17:
        return 1.5 + (n - 10) * 3.0, 2.5
    if n <= 25:
        return 1.5 + (n - 18) * 3.0, 5.5
    return (n - 26) * 3.0, 8.0


def row(n):
    return 1 if n <= 9 else 2 if n <= 17 else 3 if n <= 25 else 4


def glyph(g, x, y, r=1.05, num=None):
    _, _, _, fill, tc, shape = GC[g]
    paint = f"url(#ht-{g})" if shape == "gnd" else fill
    if shape == "hex":
        R = r * 1.15
        pts = " ".join(f"{x + R * math.cos(math.radians(a)):.3f},{y + R * math.sin(math.radians(a)):.3f}"
                       for a in range(-90, 270, 60))
        s = f'<polygon points="{pts}" fill="{paint}" stroke="{INK}" stroke-width="0.11"/>'
    else:
        s = (f'<rect x="{x - r:.3f}" y="{y - r:.3f}" width="{2 * r:.3f}" height="{2 * r:.3f}" rx="0.18" '
             f'fill="{paint}" stroke="{INK}" stroke-width="0.11"/>')
    if num is not None:
        halo = f' stroke="{fill}" stroke-width="0.32" paint-order="stroke"' if shape == "gnd" else ""
        s += (f'<text class="fpn" x="{x}" y="{y + 0.34}" fill="{tc}"{halo} text-anchor="middle">{num}</text>')
    return s


def label(g, cx, cy, name, pins, side):
    """chip at (cx, cy) + two text lines; side: top / bottom / left / right."""
    s = glyph(g, cx, cy, r=0.62)
    if side == "top":
        s += (f'<text class="fl" x="{cx}" y="{cy - 2.55}" text-anchor="middle">{name}</text>'
              f'<text class="fp" x="{cx}" y="{cy - 1.1}" text-anchor="middle">{pins}</text>')
    elif side == "bottom":
        s += (f'<text class="fl" x="{cx}" y="{cy + 2.25}" text-anchor="middle">{name}</text>'
              f'<text class="fp" x="{cx}" y="{cy + 3.7}" text-anchor="middle">{pins}</text>')
    else:
        a, tx = ("end", cx - 1.2) if side == "left" else ("start", cx + 1.2)
        s += (f'<text class="fl" x="{tx}" y="{cy + 0.05}" text-anchor="{a}">{name}</text>'
              f'<text class="fp" x="{tx}" y="{cy + 1.5}" text-anchor="{a}">{pins}</text>')
    return s


def poly(pts):
    return '<polyline class="ld" points="' + " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>'


def svg_face():
    defs = "".join(
        f'<pattern id="ht-{g}" width="0.62" height="0.62" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        f'<rect width="0.62" height="0.62" fill="{GC[g][3]}"/><rect width="0.24" height="0.62" fill="{HATCH[g]}"/></pattern>'
        for g in HATCH)
    o = [f"<defs>{defs}</defs>"]
    # unit front / flange, shroud, latch, keys — outline drawing
    o.append('<rect class="ol" x="-10.5" y="-5.6" width="45" height="21.4" rx="1.6"/>')
    for x in (-8.2, 32.2):
        o.append(f'<circle class="ol" cx="{x}" cy="4" r="0.95"/>'
                 f'<line class="cl" x1="{x - 1.7}" y1="4" x2="{x + 1.7}" y2="4"/>'
                 f'<line class="cl" x1="{x}" y1="2.6" x2="{x}" y2="5.4"/>')
    o.append('<rect class="ol" x="-4.6" y="-3.6" width="33.2" height="17.4" rx="3.2" stroke-width="0.26"/>')
    o.append('<rect class="cav" x="-3.2" y="-2.3" width="30.4" height="14.8" rx="2.4"/>')
    o.append('<rect class="ol" x="9.6" y="-5.2" width="4.8" height="1.6" rx="0.3"/>')
    o.append('<rect class="ol" x="3.3" y="-2.3" width="1.6" height="1.1"/>')
    o.append('<rect class="ol" x="19.1" y="11.4" width="1.6" height="1.1"/>')

    leaders, labels = [], []
    # top: +12V combs over row 1, plus single non-+12V pins of rows 1-2 (leader up through the gaps)
    r1 = [n for n in GPINS["p12"] if row(n) == 1]
    runs, cur = [], [r1[0]]
    for n in r1[1:]:
        if n == cur[-1] + 1:
            cur.append(n)
        else:
            runs.append(cur)
            cur = [n]
    runs.append(cur)
    top = [("run", run, (pin_xy(run[0])[0] + pin_xy(run[-1])[0]) / 2) for run in runs]
    top += [("pin", n, pin_xy(n)[0]) for n in PIN
            if (row(n) == 1 and PIN[n][1] != "p12") or (row(n) == 2 and PIN[n][1] != "data")]
    top.sort(key=lambda t: t[2])
    BAR, CY = -7.4, -10.7
    tcx = [12 + (i - (len(top) - 1) / 2) * 9.5 for i in range(len(top))]
    tl = [i for i in range(len(top)) if tcx[i] < top[i][2]]
    tr = [i for i in reversed(range(len(top))) if tcx[i] >= top[i][2]]
    for i, ((kind, item, x), cx) in enumerate(zip(top, tcx)):
        k = tl.index(i) if i in tl else tr.index(i)
        ye = -8.2 - 0.75 * k
        if kind == "run":
            for n in item:
                px, py = pin_xy(n)
                leaders.append(poly([(px, py), (px, BAR)]))
            leaders.append(poly([(pin_xy(item[0])[0], BAR), (pin_xy(item[-1])[0], BAR)]))
            leaders.append(poly([(x, BAR), (x, ye), (cx, ye), (cx, CY)]))
            labels.append(label("p12", cx, CY, "+12V ленты", f"{ranges(item)} · 5 А", "top"))
        else:
            px, py = pin_xy(item)
            g = PIN[item][1]
            leaders.append(poly([(px, py), (px, ye), (cx, ye), (cx, CY)]))
            nm = "GND сигнальная" if g == "gsig" else PIN[item][2].replace("Вход ", "")
            pins = ranges(GPINS[g]) if g == "gsig" else str(item)
            labels.append(label(g, cx, CY, nm, pins, "top"))

    # bottom: row-3 pins that are not DATA/CAN + row-4 pins that are not GND ленты
    bot = sorted((n for n in PIN if (row(n) == 3 and PIN[n][1] not in ("data", "can"))
                  or (row(n) == 4 and PIN[n][1] != "gled")), key=lambda n: pin_xy(n)[0])
    CYB = 20.6
    short = {"kline": "K-line", "v5": "+5V датчиков", "ign": "IGN", "gsig": "GND сигнальная"}
    cxs = [12 + (i - (len(bot) - 1) / 2) * 10.4 for i in range(len(bot))]
    left = [n for n, cx in zip(bot, cxs) if cx < pin_xy(n)[0]]
    right = [n for n, cx in zip(bot, cxs) if cx >= pin_xy(n)[0]]
    for n, cx in zip(bot, cxs):
        px, py = pin_xy(n)
        k = left.index(n) if n in left else list(reversed(right)).index(n)
        ye = 16.7 + 0.75 * k
        leaders.append(poly([(px, py), (px, ye), (cx, ye), (cx, CYB)]))
        g = PIN[n][1]
        nm = PIN[n][2].replace("Вход ", "") if g == "in" else short.get(g, GC[g][1])
        pins = ranges(GPINS[g]) if g == "gsig" else str(n)
        labels.append(label(g, cx, CYB, nm, pins, "bottom"))

    # left: CAN (first pin of row 3) and GND ленты (first pin of row 4)
    can0 = min(n for n in PIN if row(n) == 3)
    gl0 = min(n for n in PIN if row(n) == 4)
    assert PIN[can0][1] == "can" and PIN[gl0][1] == "gled"
    XL = -13.4
    px, py = pin_xy(can0)
    leaders.append(poly([(px, py), (-11.8, py), (-11.8, 2.4), (XL, 2.4)]))
    labels.append(label("can", XL, 2.4, "CAN H / CAN L", " / ".join(str(n) for n in GPINS["can"]), "left"))
    px, py = pin_xy(gl0)
    leaders.append(poly([(px, py), (XL, py)]))
    labels.append(label("gled", XL, py, "GND ленты", ranges(GPINS["gled"]), "left"))

    # right: DATA (last pins of rows 2 and 3), bracket
    d2, d3 = max(n for n in PIN if row(n) == 2), max(n for n in PIN if row(n) == 3)
    assert PIN[d2][1] == "data" and PIN[d3][1] == "data"
    XB, XR = 36.0, 37.6
    (x2, y2), (x3, y3) = pin_xy(d2), pin_xy(d3)
    leaders.append(poly([(x2, y2), (XB, y2), (XB, y3), (x3, y3)]))
    leaders.append(poly([(XB, (y2 + y3) / 2), (XR, (y2 + y3) / 2)]))
    labels.append(label("data", XR, (y2 + y3) / 2, "DATA ленты", ranges(GPINS["data"]), "right"))

    o += leaders
    for n in range(1, 35):
        x, y = pin_xy(n)
        o.append(glyph(PIN[n][1], x, y, num=n))
    o += labels
    return ('<svg class="face" viewBox="-25 -15.6 75 41.6" xmlns="http://www.w3.org/2000/svg">'
            + "".join(o) + "</svg>")


SHAPE_KEY = (f'<div class="skey">{chip("p12")} питание &nbsp; {chip("gled")} масса (штриховка) &nbsp; '
             f'{chip("data")} сигнал &nbsp;·&nbsp; цвет — группа, номер — контакт J1</div>')


# ------------------------------------------------------------------ page 2: pin list + strip cards
def pin_list(ns):
    rows = "".join(
        f'<tr><td class="gb" style="background:{css_bg(PIN[n][1])}"></td><td class="pn">{n}</td>'
        f'<td>{PIN[n][2]}</td><td class="tg">{GC[PIN[n][1]][2]}</td></tr>' for n in ns)
    return f'<table class="pl"><tr><th></th><th class="pn">№</th><th>Сигнал</th><th class="tg">Группа</th></tr>{rows}</table>'


def strip_cards():
    cards = []
    for i in range(1, 9):
        rs = ""
        for lbl, g, key in (("+12V", "p12", f"LED{i}_12V"), ("DATA", "data", f"LED{i}_DO"), ("GND", "gled", f"LED{i}_GND")):
            n = KEY2PIN[key]
            rs += f'<div class="cr">{chip(g)}<span class="cl">{lbl}</span><span class="rw">ряд {row(n)}</span><span class="pn">{n}</span></div>'
        cards.append(f'<div class="card"><div class="ct"><span>Лента</span><b>{i}</b></div>{rs}</div>')
    return '<div class="cards">' + "".join(cards) + "</div>"


# ------------------------------------------------------------------ diagrams
def box(x, y, w, h, text, sub="", dark=False):
    fill, tc, sc = (INK, "#fff", "#B8BEC5") if dark else ("#fff", INK, "#5B6470")
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{INK}" stroke-width="1.2"/>'
         f'<text x="{x + w / 2}" y="{y + h / 2 + (0 if sub else 5)}" text-anchor="middle" font-size="14" '
         f'font-weight="600" fill="{tc}">{text}</text>')
    if dark:
        s += f'<rect x="{x}" y="{y}" width="5" height="{h}" fill="{ACC}"/>'
    if sub:
        s += f'<text x="{x + w / 2}" y="{y + h / 2 + 16}" text-anchor="middle" font-size="11" fill="{sc}">{sub}</text>'
    return s


def bus(x1, x2, y, label="", lc=INK):
    s = (f'<line x1="{x1}" y1="{y - 3}" x2="{x2}" y2="{y - 3}" stroke="{lc}" stroke-width="1.3"/>'
         f'<line x1="{x1}" y1="{y + 3}" x2="{x2}" y2="{y + 3}" stroke="{lc}" stroke-width="1.3"/>')
    if label:
        s += f'<text x="{(x1 + x2) / 2}" y="{y - 8}" text-anchor="middle" font-size="11" fill="{INK}">{label}</text>'
    return s


def vbus(x, y1, y2, lc=INK):
    return (f'<line x1="{x - 3}" y1="{y1}" x2="{x - 3}" y2="{y2}" stroke="{lc}" stroke-width="1.3"/>'
            f'<line x1="{x + 3}" y1="{y1}" x2="{x + 3}" y2="{y2}" stroke="{lc}" stroke-width="1.3"/>')


def nodes(x, y):
    return (f'<circle cx="{x - 3}" cy="{y - 3}" r="2" fill="{INK}"/><circle cx="{x + 3}" cy="{y + 3}" r="2" fill="{INK}"/>')


def svg_can1():
    s = [box(10, 70, 80, 46, "ЭБУ"), box(225, 10, 110, 46, "DriftAnalyser", "CAN 18/19", True),
         box(225, 130, 110, 46, "Другие блоки", "шина авто")]
    s.append(bus(90, 280, 93, "CAN 500 кбит/с"))
    s.append(vbus(280, 56, 130))
    s.append(nodes(280, 93))
    return '<svg class="dia" viewBox="0 0 345 186" xmlns="http://www.w3.org/2000/svg">' + "".join(s) + "</svg>"


def svg_can2():
    s = [box(10, 10, 80, 46, "ЭБУ"), box(10, 130, 80, 46, "Панель", "eDash"),
         box(225, 130, 110, 46, "DriftAnalyser", "CAN 18/19", True)]
    s.append(vbus(50, 56, 130))
    s.append(f'<text x="60" y="98" font-size="11" fill="{INK}">CAN1</text>')
    s.append(bus(90, 225, 153, "CAN2 · 1 Мбит/с"))
    return '<svg class="dia" viewBox="0 0 345 186" xmlns="http://www.w3.org/2000/svg">' + "".join(s) + "</svg>"


def svg_power():
    s = []
    blk, gl, dt = INK, GC["gled"][3], GC["data"][3]
    # battery
    s.append(f'<rect x="10" y="40" width="120" height="80" fill="#fff" stroke="{blk}" stroke-width="1.2"/>')
    s.append(f'<text x="70" y="86" text-anchor="middle" font-size="15" font-weight="700" fill="{blk}">АКБ 12 В</text>')
    s.append(f'<rect x="28" y="28" width="22" height="12" fill="{RED}" stroke="{blk}"/>'
             f'<text x="39" y="22" text-anchor="middle" font-size="14" fill="{RED}" font-weight="700">+</text>')
    s.append(f'<rect x="90" y="28" width="22" height="12" fill="{blk}" stroke="{blk}"/>'
             '<text x="101" y="22" text-anchor="middle" font-size="16" font-weight="700">−</text>')
    # engine block
    s.append(f'<rect x="10" y="165" width="150" height="40" fill="#fff" stroke="{blk}" stroke-dasharray="4 3"/>'
             '<text x="75" y="190" text-anchor="middle" font-size="12">блок двигателя</text>')
    s.append(f'<path d="M101 28 L101 20 L145 20 L145 165" fill="none" stroke="{blk}" stroke-width="2.5"/>')
    # unit
    s.append(f'<rect x="250" y="40" width="190" height="165" fill="#F4F5F6" stroke="{blk}" stroke-width="1.6"/>')
    s.append(f'<rect x="250" y="40" width="190" height="6" fill="{blk}"/>')
    s.append(f'<text x="345" y="125" text-anchor="middle" font-size="15" font-weight="700" fill="{blk}">DriftAnalyser v3</text>')
    s.append(f'<rect x="272" y="49" width="26" height="26" fill="{RED}" stroke="{blk}"/><text x="285" y="67" text-anchor="middle" '
             'font-size="13" fill="#fff" font-weight="700">+</text>')
    s.append(f'<rect x="272" y="170" width="26" height="26" fill="{blk}" stroke="{blk}"/><text x="285" y="188" text-anchor="middle" '
             'font-size="14" fill="#fff" font-weight="700">−</text>')
    s.append('<text x="305" y="66" font-size="11">M6 +12V</text><text x="305" y="187" font-size="11">M6 GND</text>')
    # thick cables
    s.append(f'<path d="M39 28 L39 12 L210 12 L210 62 L272 62" fill="none" stroke="{RED}" stroke-width="5"/>')
    s.append(f'<path d="M101 205 L101 222 L210 222 L210 183 L272 183" fill="none" stroke="{blk}" stroke-width="5"/>')
    s.append(f'<text x="152" y="34" font-size="11" fill="{RED}">~40 А, M6</text>')
    s.append('<text x="125" y="236" font-size="11">масса: на минус АКБ или блок двигателя</text>')
    # connector + strips
    s.append(f'<rect x="440" y="95" width="18" height="60" fill="{blk}"/><text x="449" y="88" text-anchor="middle" font-size="11">J1</text>')
    for i, y in enumerate((80, 125, 170)):
        s.append(f'<line x1="458" y1="{105 + i * 20}" x2="520" y2="{y + 15}" stroke="{RED}" stroke-width="2"/>')
        s.append(f'<line x1="458" y1="{110 + i * 20}" x2="520" y2="{y + 22}" stroke="{gl}" stroke-width="2"/>')
        s.append(f'<line x1="458" y1="{107 + i * 20}" x2="520" y2="{y + 18}" stroke="{dt}" stroke-width="1.4"/>')
        s.append(f'<rect x="520" y="{y + 8}" width="70" height="20" fill="#fff" stroke="{blk}"/>'
                 f'<text x="555" y="{y + 22}" text-anchor="middle" font-size="11">лента</text>')
    s.append('<text x="555" y="226" text-anchor="middle" font-size="11">+12V / DATA / GND</text>')
    s.append('<text x="555" y="240" text-anchor="middle" font-size="11">каждой ленты — через J1</text>')
    return '<svg class="pwr" viewBox="0 0 650 258" xmlns="http://www.w3.org/2000/svg"><g transform="translate(0 13)">' + "".join(s) + "</g></svg>"


# ------------------------------------------------------------------ mounting drawing (mm)
ST = 0.25  # outline stroke, mm


def dim_h(x1, x2, y, y_ref1, y_ref2, text, above=True):
    """horizontal dimension line at y, extension lines from y_ref1 / y_ref2."""
    t = y - 1.2 if above else y + 3.6
    return (f'<line class="ext" x1="{x1}" y1="{y_ref1}" x2="{x1}" y2="{y + (-1.5 if above else 1.5) * -1}"/>'
            f'<line class="ext" x1="{x2}" y1="{y_ref2}" x2="{x2}" y2="{y + (-1.5 if above else 1.5) * -1}"/>'
            f'<line class="dim" x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" marker-start="url(#a)" marker-end="url(#a)"/>'
            f'<text class="dt" x="{(x1 + x2) / 2}" y="{t}" text-anchor="middle">{text}</text>')


def dim_v(y1, y2, x, x_ref1, x_ref2, text, left=True):
    tx = x - 1.3 if left else x + 1.3
    rot = -90
    cy = (y1 + y2) / 2
    return (f'<line class="ext" x1="{x_ref1}" y1="{y1}" x2="{x + (-1.5 if left else 1.5)}" y2="{y1}"/>'
            f'<line class="ext" x1="{x_ref2}" y1="{y2}" x2="{x + (-1.5 if left else 1.5)}" y2="{y2}"/>'
            f'<line class="dim" x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" marker-start="url(#a)" marker-end="url(#a)"/>'
            f'<text class="dt" x="{tx}" y="{cy}" text-anchor="middle" '
            f'transform="rotate({rot} {tx} {cy})">{text}</text>')


def fmt(v):
    return f"{v:.1f}".replace(".", ",")


DEFS = ('<defs><marker id="a" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="3" markerHeight="3" '
        'orient="auto-start-reverse" markerUnits="userSpaceOnUse"><path d="M0 1.5 L10 5 L0 8.5 Z" fill="#111"/>'
        '</marker></defs>')

MSTYLE = ('<style>.o{fill:none;stroke:#111;stroke-width:0.3}.f{fill:#f4f5f6;stroke:#111;stroke-width:0.3}'
          '.h{fill:none;stroke:#111;stroke-width:0.18}.ext{stroke:#555;stroke-width:0.13}'
          '.dim{stroke:#111;stroke-width:0.16}.dt{font:500 2.9px "IBM Plex Mono",Menlo,monospace;fill:#111}'
          '.lb{font:2.5px "IBM Plex Sans","Helvetica Neue",Arial,sans-serif;fill:#333}.cl{stroke:#888;stroke-width:0.12;'
          'stroke-dasharray:2 0.6 0.4 0.6}.dash{fill:none;stroke:#777;stroke-width:0.2;stroke-dasharray:1.2 0.8}</style>')


def rrect(x0, y0, x1, y1, r, cls="o"):
    return (f'<rect class="{cls}" x="{min(x0, x1)}" y="{min(y0, y1)}" width="{abs(x1 - x0)}" '
            f'height="{abs(y1 - y0)}" rx="{r}"/>')


def svg_top():
    """Top view turned 180 deg so the front (J1) is at the bottom: drawing x = X0 + X1 - board x,
    drawing y = Y1 - board y."""
    X0, X1, Y0, Y1 = E.X0, E.X1, E.Y0, E.Y1
    X = lambda x: X0 + X1 - x  # noqa: E731
    Y = lambda y: Y1 - y  # noqa: E731
    o = []
    ear_x = []
    for ey in E.EAR_Y:
        for side in (-1, 1):
            xw = X0 if side < 0 else X1
            xe = xw + side * E.EAR_L
            o.append(rrect(min(xw, xe), Y(ey - E.EAR_W / 2), max(xw, xe), Y(ey + E.EAR_W / 2), 2.5, "f"))
            hx = xw + side * E.EAR_L / 2
            ear_x.append(hx)
            o.append(f'<circle class="o" cx="{hx}" cy="{Y(ey)}" r="{E.EAR_HOLE / 2}"/>')
            o.append(f'<line class="cl" x1="{hx - 4.5}" y1="{Y(ey)}" x2="{hx + 4.5}" y2="{Y(ey)}"/>'
                     f'<line class="cl" x1="{hx}" y1="{Y(ey) - 4.5}" x2="{hx}" y2="{Y(ey) + 4.5}"/>')
    for x, y in E.pilaster_xy():
        xw = X0 if x < 0 else X1
        o.append(f'<rect class="f" x="{min(X(x), X(xw))}" y="{Y(y) - E.PIL_D / 2}" width="{abs(xw - x)}" height="{E.PIL_D}"/>')
        o.append(f'<circle class="f" cx="{X(x)}" cy="{Y(y)}" r="{E.PIL_D / 2}"/>')
        o.append(f'<circle class="h" cx="{X(x)}" cy="{Y(y)}" r="2.75"/>')
    # J1 shroud out of the front + mating plug (dashed)
    jx = X(E.J1_X)
    o.append(rrect(jx - E.J1_SH_W / 2, Y(E.Y0), jx + E.J1_SH_W / 2, Y(E.J1_SH_Y[0]), 1.0, "f"))
    o.append(rrect(jx - 19.5, Y(E.J1_SH_Y[0]), jx + 19.5, Y(-40.0), 2.0, "dash"))
    o.append(f'<text class="lb" x="{jx}" y="{Y(-24)}" text-anchor="middle">ответная часть</text>')
    o.append(f'<text class="lb" x="{jx}" y="{Y(-29)}" text-anchor="middle">4-1437290-0</text>')
    # SMA on the side wall (board x1 -> drawing left)
    o.append(f'<rect class="f" x="{X(E.X1) - 7.5}" y="{Y(E.UFL_XY[1]) - 3.2}" width="7.5" height="6.4"/>')
    o.append(f'<text class="lb" x="{X(E.X1) - 9}" y="{Y(E.UFL_XY[1]) + 1.2}" text-anchor="end">SMA</text>')
    # body
    o.append(rrect(X0, Y(Y1), X1, Y(Y0), E.OUT_R, "f"))
    yb = E.HOOD_Y1 + E.HOOD_T - 2.5
    o.append(f'<line class="h" x1="{X0}" y1="{Y(yb)}" x2="{X1}" y2="{Y(yb)}"/>')
    o.append(f'<line class="h" x1="{X0}" y1="{Y(yb + E.HOOD_SLOPE)}" x2="{X1}" y2="{Y(yb + E.HOOD_SLOPE)}"/>')
    o.append(f'<text class="lb" x="{(X0 + X1) / 2}" y="{Y(yb / 2) + 1.2}" text-anchor="middle">J1</text>')
    for ref, (sx, sy) in E.STUDS.items():
        col = RED if ref == "J2" else "#222"
        o.append(f'<circle class="h" cx="{X(sx)}" cy="{Y(sy)}" r="{E.STUD_BOSS_D / 2}"/>')
        o.append(f'<circle cx="{X(sx)}" cy="{Y(sy)}" r="{E.CAP_D / 2 - 0.5}" fill="{col}" fill-opacity="0.18" '
                 f'stroke="#111" stroke-width="0.3"/>')
        o.append(f'<text class="lb" x="{X(sx)}" y="{Y(sy) + 1.2}" text-anchor="middle" font-weight="700">'
                 f'{"+12V" if ref == "J2" else "GND"}</text>')
    if E.USB_OPENING:
        ux = X(E.J3_X)
        o.append(f'<rect x="{ux - 6.5}" y="{Y(Y1) - 0.6}" width="13" height="1.2" fill="#111"/>')
        o.append(f'<text class="lb" x="{ux}" y="{Y(Y1) + 4.2}" text-anchor="middle">USB-C</text>')
    # dimensions
    oy = Y(Y1)
    o.append(dim_h(X0, X1, oy - 9, oy - 1, oy - 1, fmt(X1 - X0) + " мм"))
    xl, xr = min(ear_x), max(ear_x)
    yf = Y(-40) + 9
    o.append(dim_h(X0 - E.EAR_L, X1 + E.EAR_L, yf, Y(E.EAR_Y[0]) + 7, Y(E.EAR_Y[0]) + 7,
                   fmt(X1 - X0 + 2 * E.EAR_L) + " мм по ушам", above=False))
    o.append(dim_h(xl, xr, Y(E.EAR_Y[0]) - 9, Y(E.EAR_Y[0]) - 3, Y(E.EAR_Y[0]) - 3, fmt(xr - xl) + " мм"))
    o.append(dim_v(Y(Y1), Y(Y0), X1 + E.EAR_L + 8, X1 + 1, X1 + 1, fmt(Y1 - Y0) + " мм", left=False))
    xd = X0 - E.EAR_L - 6
    o.append(dim_v(Y(E.EAR_Y[1]), Y(E.EAR_Y[0]), xd, xl - 3.5, xl - 3.5, fmt(E.EAR_Y[1] - E.EAR_Y[0]) + " мм"))
    o.append(dim_v(Y(E.EAR_Y[0]), Y(Y0), xd, xl - 3.5, X0 - 1, fmt(E.EAR_Y[0] - Y0) + " мм"))
    hx, hy = X1 + E.EAR_L / 2, Y(E.EAR_Y[1])
    o.append(f'<line class="dim" x1="{hx + 2}" y1="{hy - 2}" x2="{hx + 7}" y2="{hy - 9}"/>'
             f'<text class="dt" x="{hx + 2}" y="{hy - 10}">4 × Ø{fmt(E.EAR_HOLE)} (M5)</text>')
    vb = (X0 - E.EAR_L - 16, Y(Y1) - 17, (X1 - X0) + 2 * E.EAR_L + 38, (Y1 - Y0) + 40 + 34)
    return vb, "".join(o)


def svg_side():
    """Right side view: drawing x = board y (front J1 at left), drawing y = -z."""
    Y0, Y1 = E.Y0, E.Y1
    Z = lambda z: -z  # noqa: E731
    o = []
    yb = E.HOOD_Y1 + E.HOOD_T - 2.5
    boot_top = 45.7  # REPORT.md, boot tops
    boss = E.Z_LID_TOP + E.STUD_BOSS_H
    for ref, (sx, sy) in E.STUDS.items():
        col = RED if ref == "J2" else "#222"
        o.append(f'<rect x="{sy - E.CAP_D / 2 + 0.5}" y="{Z(boot_top)}" width="{E.CAP_D - 1}" '
                 f'height="{boot_top - boss}" rx="2" fill="{col}" fill-opacity="0.18" stroke="#111" stroke-width="0.3"/>')
    o.append(f'<rect class="f" x="{E.STUDS["J2"][1] - E.STUD_BOSS_D / 2}" y="{Z(boss)}" width="{E.STUDS["J5"][1] - E.STUDS["J2"][1] + E.STUD_BOSS_D}" height="{E.STUD_BOSS_H}"/>')
    # J1 shroud + plug
    o.append(rrect(E.J1_SH_Y[0], Z(E.T + E.J1_SH_Z[0]), Y0, Z(E.T + E.J1_SH_Z[1]), 0.6, "f"))
    o.append(rrect(-40.0, Z(E.T + E.J1_SH_Z[0] - 1), E.J1_SH_Y[0], Z(E.T + E.J1_SH_Z[1] + 1), 1.5, "dash"))
    # body outline: base + lid + hood
    pts = [(Y0, 0), (Y0, E.HOOD_TOP), (yb, E.HOOD_TOP), (yb + E.HOOD_SLOPE, E.Z_LID_TOP), (Y1, E.Z_LID_TOP), (Y1, 0)]
    o.append('<path class="f" d="M' + " L".join(f"{y} {Z(z)}" for y, z in pts) + ' Z"/>')
    o.append(f'<line class="h" x1="{Y0}" y1="{Z(E.Z_SEAM)}" x2="{Y1}" y2="{Z(E.Z_SEAM)}"/>')
    # pilasters
    for y in E.LID_SCREW_Y:
        o.append(f'<rect class="h" x="{y - E.PIL_D / 2}" y="{Z(E.Z_LID_TOP)}" width="{E.PIL_D}" height="{E.Z_LID_TOP}"/>')
    # ears
    for ey in E.EAR_Y:
        o.append(f'<rect class="f" x="{ey - E.EAR_W / 2}" y="{Z(E.EAR_T)}" width="{E.EAR_W}" height="{E.EAR_T}"/>')
    # dims
    o.append(dim_h(Y0, Y1, Z(0) + 9, Z(0) + 0.5, Z(0) + 0.5, fmt(Y1 - Y0) + " мм", above=False))
    xr = Y1 + 6
    o.append(dim_v(Z(E.Z_LID_TOP), Z(0), xr, Y1 + 0.5, Y1 + 0.5, fmt(E.Z_LID_TOP) + " мм", left=False))
    o.append(dim_v(Z(boot_top), Z(0), xr + 9, E.STUDS["J5"][1] + E.CAP_D / 2, Y1 + 0.5, fmt(boot_top) + " мм", left=False))
    xl = -40 - 6
    o.append(dim_v(Z(E.HOOD_TOP), Z(0), xl, Y0 - 0.5, Y0 - 0.5, fmt(E.HOOD_TOP) + " мм"))
    o.append(dim_v(Z(E.EAR_T), Z(0), E.EAR_Y[0] - E.EAR_W / 2 - 4, E.EAR_Y[0] - 6, E.EAR_Y[0] - 6, fmt(E.EAR_T) + " мм"))
    o.append(f'<text class="lb" x="{-27}" y="{Z(E.T + E.J1_SH_Z[1] + 3)}" text-anchor="middle">≈ 40 мм + жгут</text>')
    vb = (-52, -56, Y1 + 52 + 22, 56 + 16)
    return vb, "".join(o)


def svg_wrap(vb, body, cls, k=1.0):
    st = MSTYLE.replace("2.9px", f"{2.9 * k:.2f}px").replace("2.5px", f"{2.5 * k:.2f}px")
    return (f'<svg class="{cls}" viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}" xmlns="http://www.w3.org/2000/svg">'
            + DEFS + st + body + "</svg>")


# ------------------------------------------------------------------ html
CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
:root { --ink:#15171A; --acc:#FF5A1F; --mut:#646B75; --hair:#D3D7DC; --soft:#F3F4F6; }
html, body { margin:0; padding:0; background:#fff; color:var(--ink);
  font-family:"IBM Plex Sans","Helvetica Neue",Helvetica,Arial,sans-serif; font-size:10pt; line-height:1.45;
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body { counter-reset:sec; }
.m, .pn, code { font-family:"IBM Plex Mono",Menlo,monospace; }
.page { width:210mm; height:297mm; position:relative; padding:21mm 12mm 0 19mm; overflow:hidden;
  page-break-after:always; break-after:page; }
.page:last-child { page-break-after:auto; break-after:auto; }

/* frame: left band, running head, footer */
.band { position:absolute; left:0; top:0; bottom:0; width:9mm; background:var(--ink); }
.band .vt { position:absolute; left:0; bottom:30mm; width:9mm; writing-mode:vertical-rl; transform:rotate(180deg);
  line-height:9mm; color:#fff; font:600 6.8pt/9mm "IBM Plex Mono",Menlo,monospace; letter-spacing:2.4px; white-space:nowrap; }
.band .vt i { font-style:normal; color:var(--acc); }
.rh { position:absolute; top:8.5mm; left:19mm; right:12mm; display:flex; justify-content:space-between;
  align-items:baseline; padding-bottom:1.6mm; border-bottom:0.7pt solid var(--ink); }
.rh b { font:700 9pt "IBM Plex Sans","Helvetica Neue",sans-serif; letter-spacing:1.6px; text-transform:uppercase; }
.rh span { font:7.4pt "IBM Plex Mono",Menlo,monospace; color:var(--mut); }
.ftr { position:absolute; left:19mm; right:12mm; bottom:8mm; display:flex; justify-content:space-between; align-items:flex-end;
  border-top:0.5pt solid var(--hair); padding-top:2mm; }
.ftr .meta { font:7.2pt/1.55 "IBM Plex Mono",Menlo,monospace; color:var(--mut); }
.ftr .meta b { color:var(--ink); font-weight:600; }
.ftr .pg { font:700 26pt/0.8 "IBM Plex Mono",Menlo,monospace; letter-spacing:-0.5px; }
.ftr .pg small { font-size:10pt; font-weight:500; color:var(--mut); letter-spacing:0; }
.ftr .pg small i { font-style:normal; color:var(--acc); }

/* cover */
.cover { display:flex; margin:-21mm -12mm 0 -19mm; height:52mm; }
.mast { width:122mm; background:var(--ink); color:#fff; padding:8mm 7mm 0 19mm; position:relative; }
.mast .k { font:500 7.2pt "IBM Plex Mono",Menlo,monospace; color:#9AA1AA; letter-spacing:1px; }
.mast .nm { font:700 26.5pt/1 "IBM Plex Sans","Helvetica Neue",sans-serif; letter-spacing:0.6px; margin-top:4.5mm; white-space:nowrap; }
.mast .nm i { font-style:normal; color:var(--acc); margin-left:2mm; }
.mast .sub { font-size:11.5pt; color:#D9DDE1; margin-top:2mm; }
.mast .st { position:absolute; left:19mm; bottom:5mm; font:500 6.8pt "IBM Plex Mono",Menlo,monospace; color:#9AA1AA;
  letter-spacing:1px; text-transform:uppercase; }
.kf { flex:1; display:grid; grid-template-columns:repeat(3,1fr); column-gap:3.5mm; row-gap:4mm; padding:8mm 12mm 0 6mm; align-content:start; }
.kf > div { border-top:1.6pt solid var(--ink); padding-top:1.3mm; }
.kf .v { font:700 14pt/1.1 "IBM Plex Mono",Menlo,monospace; white-space:nowrap; }
.kf .l { font-size:7.6pt; color:var(--mut); line-height:1.25; margin-top:0.6mm; }

/* headings */
h2 { counter-increment:sec; display:flex; align-items:center; gap:3mm; margin:6.5mm 0 2.6mm;
  font:700 12pt/1.2 "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:uppercase; letter-spacing:0.9px; }
h2::before { content:counter(sec, decimal-leading-zero); font:600 9.5pt "IBM Plex Mono",Menlo,monospace; color:#fff;
  background:var(--ink); padding:0.5mm 1.6mm; letter-spacing:0; }
h2::after { content:""; flex:1; border-bottom:0.6pt solid var(--hair); }
h2 span { font:400 9pt "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:none; letter-spacing:0; color:var(--mut); }
.cover + h2 { margin-top:7mm; }
p { margin:0 0 2.3mm; }
.small { font-size:8.8pt; color:var(--mut); }
.nw { white-space:nowrap; }

/* J1 face */
.face { display:block; width:179mm; margin:1mm 0 0; }
.face .ol { fill:#fff; stroke:var(--ink); stroke-width:0.2; }
.face .cav { fill:var(--soft); stroke:var(--ink); stroke-width:0.13; }
.face .cl { stroke:#9AA1AA; stroke-width:0.07; stroke-dasharray:0.9 0.3 0.2 0.3; }
.face .ld { fill:none; stroke:var(--ink); stroke-width:0.085; }
.face .fpn { font:700 0.98px "IBM Plex Mono",Menlo,monospace; }
.face .fl { font:600 1.12px "IBM Plex Sans","Helvetica Neue",sans-serif; fill:var(--ink); }
.face .fp { font:500 0.98px "IBM Plex Mono",Menlo,monospace; fill:var(--mut); }
.fnote { display:flex; gap:3mm; margin-top:2mm; font-size:8.6pt; color:var(--mut); border-left:1.6pt solid var(--ink); padding-left:2.5mm; }
.fnote b { color:var(--ink); }
.skey { font-size:8.4pt; color:var(--mut); margin-top:2mm; display:flex; align-items:center; gap:1.2mm; }

/* chips */
.ch { display:inline-block; width:3.1mm; height:3.1mm; vertical-align:-0.5mm; flex:none; border:0.5pt solid var(--ink); }
.ch.hex { border:none; clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%); width:3.2mm; height:3.5mm; }

/* callout box */
.alert { display:flex; gap:3.5mm; border:0.9pt solid var(--ink); margin:5mm 0 3mm; padding:3mm 4mm 3mm 0; align-items:flex-start; }
.alert::before { content:""; flex:none; width:4.2mm; align-self:stretch; margin:-3mm 0;
  background:repeating-linear-gradient(-45deg, var(--acc) 0 1.6mm, var(--ink) 1.6mm 3.2mm); }
.alert svg { flex:none; width:7mm; height:7mm; margin-top:0.3mm; }
.alert .at { font:700 9pt "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:uppercase; letter-spacing:1.2px; margin-bottom:1mm; }
.alert ul { margin:0; padding-left:4.2mm; }
.alert li { margin-bottom:0.8mm; }
.alert li::marker { color:var(--acc); }
.alert p { margin:0; }

/* pin list + strip cards */
table { border-collapse:collapse; width:100%; }
.two { display:flex; gap:6mm; }
.two > * { flex:1; }
.pl { font-size:9.2pt; border-top:1.6pt solid var(--ink); }
.pl th { font:600 7.4pt "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:uppercase; letter-spacing:0.8px;
  color:var(--mut); text-align:left; padding:1.2mm 1.6mm 1mm; border-bottom:0.6pt solid var(--ink); }
.pl td { height:6.15mm; padding:0 1.6mm; border-bottom:0.5pt solid var(--hair); }
.pl td.gb { width:2.6mm; padding:0; border-bottom-color:#fff; }
.pl .pn { width:9mm; text-align:right; font-weight:600; font-size:9.6pt; }
.pl td.tg, .pl th.tg { width:14mm; font:500 7.6pt "IBM Plex Mono",Menlo,monospace; color:var(--mut); text-align:right; }
.cards { display:grid; grid-template-columns:repeat(4,1fr); gap:3mm; }
.card { border:0.8pt solid var(--ink); padding:0 2.2mm 1.4mm; }
.card .ct { display:flex; justify-content:space-between; align-items:baseline; margin:0 -2.2mm 1.2mm; padding:0.9mm 2.2mm;
  background:var(--soft); border-bottom:0.6pt solid var(--ink); }
.card .ct span { font:600 7.6pt "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:uppercase; letter-spacing:1.2px; }
.card .ct b { font:700 12pt/1 "IBM Plex Mono",Menlo,monospace; }
.cr { display:flex; align-items:center; gap:1.6mm; height:5.4mm; font-size:8.8pt; }
.cr .cl { flex:none; width:10mm; font-weight:600; }
.cr .rw { flex:1; font-size:7.4pt; color:var(--mut); }
.cr .pn { font-weight:700; font-size:10pt; }

/* spec + generic tables */
.spec { border-top:1.6pt solid var(--ink); }
.spec td { border-bottom:0.5pt solid var(--hair); padding:1.5mm 2mm; vertical-align:top; font-size:9.3pt; }
.spec td:first-child { width:42mm; padding-top:1.9mm; font:600 7.6pt/1.35 "IBM Plex Sans","Helvetica Neue",sans-serif;
  text-transform:uppercase; letter-spacing:0.7px; color:var(--mut); }
.tbl { border-top:1.6pt solid var(--ink); }
.tbl th { font:600 7.6pt "IBM Plex Sans","Helvetica Neue",sans-serif; text-transform:uppercase; letter-spacing:0.8px;
  color:var(--mut); text-align:left; padding:1.3mm 2mm 1.1mm; border-bottom:0.6pt solid var(--ink); }
.tbl td { border-bottom:0.5pt solid var(--hair); padding:1.4mm 2mm; vertical-align:top; font-size:9.3pt; }
.cols { display:flex; gap:5mm; margin-top:3mm; }
.cols > * { flex:1; }
.cols > .wide { flex:1.45; }

/* diagrams */
.pwr { display:block; width:160mm; margin:2mm auto 0; font-family:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif; }
.pwr text { fill:var(--ink); }
.dias { display:flex; justify-content:space-between; margin-top:3mm; }
.dias > div { width:86mm; border-top:0.6pt solid var(--hair); padding-top:2mm; }
.dia { display:block; width:84mm; font-family:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif; }
.dcap { font-weight:600; font-size:9.4pt; margin:0 0 2mm; }
.dcap b { font:600 8pt "IBM Plex Mono",Menlo,monospace; color:var(--acc); margin-right:1.5mm; }
.dtxt { font-size:8.8pt; margin:2mm 0 0; line-height:1.45; }
.mount { display:flex; gap:5mm; align-items:flex-start; }
.top { width:102mm; display:block; flex:none; }
.side { width:179mm; display:block; margin-top:2mm; }
.mnote { font-size:9.6pt; margin-top:6mm; }
.mnote p { margin-bottom:3mm; padding-left:3mm; border-left:1.6pt solid var(--ink); }
.iso { width:72mm; display:block; margin-top:2mm; }
code { font-size:9pt; }
"""

WARN_ICON = (f'<svg viewBox="0 0 24 24"><path d="M12 2 L23 21 L1 21 Z" fill="{ACC}" stroke="{INK}" stroke-width="1.4" '
             f'stroke-linejoin="round"/><rect x="11" y="8.5" width="2" height="7" fill="{INK}"/>'
             f'<rect x="11" y="17" width="2" height="2" fill="{INK}"/></svg>')


def alert(title, body):
    return f'<div class="alert">{WARN_ICON}<div><div class="at">{title}</div>{body}</div></div>'


def page(n, body, cover=False):
    band = (f'<div class="band"><div class="vt">DRIFTANALYSER V3 <i>■</i> {DOC}</div></div>')
    head = "" if cover else (f'<div class="rh"><b>DriftAnalyser v3</b>'
                             f'<span>{DOC} · {REV} · {DATE}</span></div>')
    return (f'<section class="page">{band}{head}{body}'
            f'<div class="ftr"><div class="meta"><b>{DOC}</b> · {REV} · {DATE} · {STATUS}<br>'
            f'Контроллер светодиодных лент · техническое описание</div>'
            f'<div class="pg">{n:02d}<small><i>/</i>@@TOTAL@@</small></div></div></section>')


def cover():
    kf = [("8", "каналов лент"), ("5 А", "на канал"), ("~40 А", "суммарный ток лент"),
          ("9–16 В", "питание, номинал 12 В"), ("≤1 мА", "ток покоя, IGN выкл."), ("34", "конт. J1, Superseal 1.0")]
    cells = "".join(f'<div><div class="v">{v}</div><div class="l">{lbl}</div></div>' for v, lbl in kf)
    return (f'<div class="cover"><div class="mast"><div class="k">ТЕХНИЧЕСКОЕ ОПИСАНИЕ · {DOC}</div>'
            f'<div class="nm">DRIFTANALYSER<i>V3</i></div>'
            f'<div class="sub">Контроллер светодиодных лент</div>'
            f'<div class="st">{REV} · {DATE} · {STATUS}</div></div>'
            f'<div class="kf">{cells}</div></div>')


def build_html():
    iso = base64.b64encode(open(os.path.join(HERE, "iso.jpg"), "rb").read()).decode()
    pages = []

    pages.append(page(1, f"""{cover()}
<h2>Разъём J1 <span>вид спереди на блок, со стороны ответной части</span></h2>
{svg_face()}
{SHAPE_KEY}
<div class="fnote"><div><b>Нумерация контактов — по отливке на корпусе разъёма.</b>
TE Superseal 1.0, 34 конт.: <span class="m">6437288-1</span> (блок), <span class="m">4-1437290-0</span> (ответная часть)</div></div>
{alert("Внимание — масса", '''<ul>
<li>Провода GND лент подключать обязательно — масса лент идёт через разъём!</li>
<li>Чёрная клемма GND — толстым кабелем на минус АКБ или блок двигателя.</li>
<li>Оба контакта GND сигнальной (5 и 30) — в одну точку массы.</li></ul>''')}
""", cover=True))

    pages.append(page(2, f"""
<h2>Распиновка J1 <span>по номерам контактов</span></h2>
<div class="two">{pin_list(range(1, 18))}{pin_list(range(18, 35))}</div>
<h2>Каналы лент <span>три контакта на ленту</span></h2>
{strip_cards()}
<h2>Жгут</h2>
<p>Обжимать по номерам контактов, а не по положению или цвету провода. Каждая лента — три провода на
фиксированных контактах: +12V в ряду 1, её GND в ряду 4 точно под ним, DATA в ряду 2 или 3.
Провода +12V и GND одной ленты вести в одном кабеле. CAN High / CAN Low (18/19) — витая пара.
Все 34 гнезда заняты, заглушки не нужны.</p>
"""))

    pages.append(page(3, f"""
<h2>Основные характеристики</h2>
<table class="spec">
<tr><td>Назначение</td><td>Контроллер 12 В адресных светодиодных лент: 8 каналов, CAN, K-line, датчик движения, 3 входа, Wi-Fi</td></tr>
<tr><td>Напряжение питания</td><td>9–16 В (номинал 12 В); выдерживает пуск от 24 В и переполюсовку (идеальный диод)</td></tr>
<tr><td>Выходы лент</td><td>8 каналов +12 В, включение каждого канала отдельно, до 5 А на канал (предел контакта Superseal); ток каждого канала измеряется</td></tr>
<tr><td>Суммарный ток лент</td><td>до ~40 А</td></tr>
<tr><td>Данные лент</td><td>8 линий DATA, уровень 5 В</td></tr>
<tr><td>Ток покоя</td><td>≤ 1 мА при выключенном зажигании (IGN)</td></tr>
<tr><td>CAN</td><td>1 канал, 500 кбит/с или 1 Мбит/с (в настройках); терминатор 120 Ом — перемычка JP2 внутри корпуса</td></tr>
<tr><td>K-line</td><td>1 линия; подтяжка 510 Ом к +12 В — перемычка JP1 внутри корпуса</td></tr>
<tr><td>Входы</td><td>IN1–IN3: цифровые (на GND / на +12V) или аналоговые 0–16 В</td></tr>
<tr><td>Питание датчиков</td><td>+5V датчиков ≈ 4,7 В, с ограничением тока</td></tr>
<tr><td>Датчик движения</td><td>акселерометр + гироскоп (6 осей), встроенный</td></tr>
<tr><td>Настройка</td><td>Wi-Fi (ESP32-S3), внешняя антенна SMA; обновление прошивки по воздуху. USB-C внутри корпуса — только для первой прошивки и восстановления (снять крышку)</td></tr>
<tr><td>Разъём</td><td>TE Superseal 1.0, 34 конт.: <span class="m">6437288-1</span>, ответная часть <span class="m">4-1437290-0</span></td></tr>
<tr><td>Силовые клеммы</td><td>2 × Würth REDCUBE <span class="m">7461059</span>, внутренняя резьба M6</td></tr>
<tr><td>Габариты</td><td>{fmt(E.X1 - E.X0)} × {fmt(E.Y1 - E.Y0)} мм, высота {fmt(E.HOOD_TOP)} мм; {fmt(E.X1 - E.X0 + 2 * E.EAR_L)} мм по крепёжным ушам (предварительно)</td></tr>
</table>

<h2>Выходы лент</h2>
<p>8 каналов. Каждый канал — свой ключ +12V (ряд 1), линия данных DATA (ряд 2 или 3) и GND (ряд 4, под
своим +12V). Ток канала — до <b>5 А</b>: это предел контакта Superseal, а не ключа. Каналы включаются
независимо, ток каждого канала измеряется. Линии DATA — логика 5 В, для адресных лент WS2812.</p>

<h2>Зажигание IGN</h2>
<p>Контакт <span class="m">24</span>. +12 В на IGN будит блок. Когда IGN снимается, ленты выключаются и блок засыпает;
ток покоя в этом состоянии ≤ 1 мА. IGN подключать к цепи, на которой +12 В есть только при включённом
зажигании, а не к постоянному +12 В.</p>
"""))

    pages.append(page(4, f"""
<h2>Питание и масса</h2>
<p>Питание подаётся на две клеммы M6 на крышке: <b>+12V</b> (красный колпачок) и <b>GND</b>, минус АКБ
(чёрный колпачок). Через клеммы идёт весь ток лент, до ~40 А, поэтому кабели рассчитываются на этот ток,
наконечники — кольцевые M6. Момент затяжки болта M6 — <b>не более 3,9 Н·м</b> (ограничение клеммы Würth),
затягивать динамометрическим ключом, с гровером или стопорной шайбой.</p>
{svg_power()}
{alert("Масса", '''<p>Обратный ток каждой ленты идёт по её проводу GND через разъём J1 на плату и
дальше на чёрную клемму. Поэтому чёрная клемма GND подключается толстым кабелем к минусу АКБ или блоку
двигателя, а провода GND лент — только в разъём, не на кузов рядом с лентой. Оба контакта GND сигнальной
(5 и 30) — в одну точку массы с датчиками.</p>''')}

<h2>Универсальные входы IN1–IN3</h2>
<p>Контакты <span class="m">14, 21, 22</span>. Режим каждого входа выбирается в настройках. Вход защищён TVS-диодом 24 В,
диапазон измерения 0–16 В, входное сопротивление без подтяжки ≈ 53 кОм (делитель 10k + 33k + 10k).</p>
<table class="tbl">
<tr><th>Режим</th><th>Подтяжка</th><th>Пример</th></tr>
<tr><td>Цифровой, замыкание на GND</td><td>к +3,3 В, 10 кОм (за делителем)</td><td>кнопка, концевик, датчик «на массу»</td></tr>
<tr><td>Цифровой, подача +12V</td><td>к GND, 10 кОм</td><td>стоп-сигнал, габариты, задний ход</td></tr>
<tr><td>Аналоговый 0–16 В</td><td>нет</td><td>напряжение в бортсети, аналоговые сигналы</td></tr>
<tr><td>Аналоговый датчик 0–5 В</td><td>нет</td><td>датчик давления / положения с питанием от +5V датчиков</td></tr>
</table>

<h2>Питание датчиков +5V</h2>
<p>Контакт <span class="m">23</span>. Около <b>4,7 В</b>, включается программно, с ограничением тока ≈ 130 мА и отключением при
перегрузке (рекомендуемая нагрузка — до 100 мА). Масса датчиков — GND сигнальная, контакты <span class="m">5</span> и <span class="m">30</span>.</p>
"""))

    pages.append(page(5, f"""
<h2>Шина связи CAN</h2>
<p>Контакты <span class="m">18</span> (CAN High) и <span class="m">19</span> (CAN Low), витая пара. Один канал, скорость задаётся в настройках:
<b class="nw">500 кбит/с</b> — шина ЭБУ, <b>1 Мбит/с</b> — CAN2 панели eDash. Пока CAN не настроен, блок работает
только на приём (silent) и ничего не передаёт в шину.</p>
<p>Терминатор 120 Ом — перемычка <b>JP2 внутри корпуса</b>, отдельного контакта терминатора на разъёме нет. JP2 ставится, только если DriftAnalyser — крайнее устройство на шине. На уже
терминированной шине автомобиля (обычный случай) JP2 не ставится.</p>
<div class="dias">
<div><div class="dcap"><b>А</b>Без панели — DriftAnalyser на шине ЭБУ</div>{svg_can1()}
<div class="dtxt">ЭБУ → шина CAN автомобиля<br>DriftAnalyser → та же шина, 500 кбит/с<br>JP2 — обычно не ставится</div></div>
<div><div class="dcap"><b>Б</b>С панелью eDash — DriftAnalyser на CAN2 панели</div>{svg_can2()}
<div class="dtxt">ЭБУ → eDash (CAN1)<br>DriftAnalyser → eDash (CAN2), 1 Мбит/с<br>JP2 — если DriftAnalyser на конце CAN2</div></div>
</div>

<h2>K-line</h2>
<p>Контакт <span class="m">20</span>. Для ЭБУ без CAN-рассылки данных, например BMW MS43 (протокол DS2). Подтяжка 510 Ом к +12 В
— перемычка <b>JP1 внутри корпуса</b>. Ставить JP1 только если линию больше никто не подтягивает
(большинство ЭБУ подтягивают K-line сами). Если JP1 стоит, а ЭБУ держит линию в нуле, в режиме сна через
подтяжку течёт ~24 мА — в этом случае JP1 снять.</p>

<h2>Перемычки внутри корпуса</h2>
<table class="tbl">
<tr><th>Перемычка</th><th>Установлена</th><th>Снята</th></tr>
<tr><td><b class="m">JP1</b> K-LINE</td><td>подтяжка K-line 510 Ом к +12 В: в машине нет своей подтяжки</td><td>только CAN, или линия уже подтянута</td></tr>
<tr><td><b class="m">JP2</b> CAN TERM</td><td>120 Ом между CAN H и CAN L: блок на конце шины</td><td>блок — ответвление на терминированной шине</td></tr>
</table>
"""))

    pages.append(page(6, """
<h2>Wi-Fi</h2>
<p>Настройка — по Wi-Fi через веб-интерфейс (параметры точки доступа см. в прошивке).
Антенна Wi-Fi — внешняя, разъём SMA на боковой стенке корпуса.</p>

<h2>Провода</h2>
<p>Контакты разъёма: TE Superseal 1.0, контакт <b class="m">3-1447221-3</b> для провода 0,75–1,25 мм².</p>
<div class="cols">
<table class="tbl wide">
<tr><th>Цепь</th><th>Сечение</th><th class="nw">AWG</th></tr>
<tr><td>+12V и GND лент (на контакт)</td><td>0,75–1,25 мм²</td><td class="nw m">18–16</td></tr>
<tr><td>DATA, CAN, K-line, IGN, входы, +5V, GND сигнальная</td><td>0,5 мм²</td><td class="nw m">20–22</td></tr>
<tr><td>Силовые кабели на клеммы +12V / GND (~40 А)</td><td>по току ~40 А, наконечник M6</td><td class="nw m">8–6</td></tr>
</table>
<table class="tbl">
<tr><th>Деталь</th><th>Номер</th></tr>
<tr><td>Разъём на блоке</td><td class="m">TE 6437288-1</td></tr>
<tr><td>Ответная часть</td><td class="m">TE 4-1437290-0</td></tr>
<tr><td>Контакт 0,75–1,25 мм²</td><td class="m">TE 3-1447221-3</td></tr>
<tr><td>Клеммы питания</td><td><span class="m">Würth 7461059</span>, M6, ≤ 3,9 Н·м</td></tr>
</table>
</div>
<p class="small" style="margin-top:3mm">Провода +12V и GND одной ленты — в одном кабеле. CAN High / CAN Low — витая пара.</p>
"""))

    tvb, tbody = svg_top()
    svb, sbody = svg_side()
    pages.append(page(7, f"""
<h2>Монтаж и расположение</h2>
<div class="mount">
{svg_wrap(tvb, tbody, "top", 1.35)}
<div>
<div class="mnote">
<p>Размеры корпуса предварительные.</p>
<p>Крепление — 4 болта M5 через уши на основании. Монтировать на ровную площадку, по возможности
подальше от источников тепла и в сухом месте.</p>
<p>Спереди оставить место под ответную часть разъёма и жгут: ≈ 40 мм + изгиб жгута.</p>
<p>Силовые кабели к клеммам +12V / GND подходят сзади, антенна SMA — на боковой стенке. Корпус закрытый: USB-C внутри, доступ — со снятой крышкой.</p>
</div>
<img class="iso" src="data:image/jpeg;base64,{iso}" alt="DriftAnalyser v3">
</div>
</div>
{svg_wrap(svb, sbody, "side")}
"""))

    fonts = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700"
             "&family=IBM+Plex+Sans:wght@400;500;600;700&display=block")
    html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>DriftAnalyser v3 · {DOC}</title>'
            f'<link href="{fonts.replace("&", "&amp;")}" rel="stylesheet">'
            f'<style>{CSS}</style></head><body>' + "".join(pages).replace("@@TOTAL@@", f"{len(pages):02d}")
            + "</body></html>")
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return len(pages)


def render():
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=8000", f"--print-to-pdf={PDF}", "file://" + HTML],
                   check=True, capture_output=True, timeout=90)
    for n in (1, 2):
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", str(n), "-l", str(n), "-singlefile", PDF,
                        os.path.join(HERE, f"page{n}")], check=True)


if __name__ == "__main__":
    print("pages:", build_html())
    render()
