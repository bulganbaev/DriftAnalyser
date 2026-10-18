"""DriftAnalyser v3 customer datasheet (RU) -> datasheet.html, PDF and page PNGs.

Pinout from PCB/v3/gen/model.py (J1_PIN), enclosure sizes from enclosure/v3/enclosure_v3.py.
Run with the enclosure venv (needs cadquery for the enclosure import):
    enclosure/.venv/bin/python PCB/v3/docs/datasheet/gen_datasheet.py
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "PCB", "v3"))
sys.path.insert(0, os.path.join(ROOT, "enclosure", "v3"))
from gen.model import J1_PIN  # noqa: E402
import enclosure_v3 as E  # noqa: E402

VERSION = "v3.0 (предварительная) · 2026-10"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HTML = os.path.join(HERE, "datasheet.html")
PDF = os.path.join(HERE, "DriftAnalyser_v3_datasheet.pdf")

# ------------------------------------------------------------------ pin groups
GROUPS = [  # key, legend text, fill, text colour
    ("p12", "+12V ленты (выход 5 А)", "#7b2a2c", "#fff"),
    ("data", "Данные ленты (DATA)", "#c9a227", "#111"),
    ("gled", "GND ленты", "#3d7fd6", "#fff"),
    ("can", "CAN", "#2ea43a", "#fff"),
    ("kline", "K-line", "#a03cb0", "#fff"),
    ("ign", "Зажигание IGN", "#e8751a", "#fff"),
    ("in", "Универсальные входы IN1–IN3", "#bdbdbd", "#111"),
    ("v5", "+5V датчиков", "#17a2a2", "#fff"),
    ("gsig", "GND сигнальная", "#111111", "#fff"),
]
GC = {g[0]: g for g in GROUPS}


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


# ------------------------------------------------------------------ page 1: header face
def pin_xy(n):
    """Face view of the header (mating side), mm. Pin 1 top-left, rows 1-9 / 10-17 / 18-25 / 26-34."""
    if n <= 9:
        return (n - 1) * 3.0, 0.0
    if n <= 17:
        return 1.5 + (n - 10) * 3.0, 2.5
    if n <= 25:
        return 1.5 + (n - 18) * 3.0, 5.5
    return (n - 26) * 3.0, 8.0


def svg_face():
    o = []
    # housing / unit front, dark like the pdm30 drawing
    o.append('<path d="M-17 4 L-12.5 -6.5 Q-12 -7.6 -10.8 -7.6 L34.8 -7.6 Q36 -7.6 36.5 -6.5 L41 4 '
             'L41 17.4 Q41 18.6 39.8 18.6 L-15.8 18.6 Q-17 18.6 -17 17.4 Z" fill="#2b2b2d" stroke="#000" stroke-width="0.15"/>')
    o.append('<path d="M-17 4 L41 4" stroke="#444" stroke-width="0.12"/>')
    # flange with screw ears
    o.append('<rect x="-10.5" y="-5.6" width="45" height="21.4" rx="1.6" fill="#1e1e20" stroke="#5a5a5e" stroke-width="0.18"/>')
    for x in (-8.2, 32.2):
        o.append(f'<circle cx="{x}" cy="4" r="1.15" fill="#0d0d0e" stroke="#6a6a6e" stroke-width="0.15"/>')
    # shroud: outer wall + inner cavity (double outline)
    o.append('<rect x="-4.6" y="-3.6" width="33.2" height="17.4" rx="3.2" fill="#18181a" stroke="#8a8a8f" stroke-width="0.25"/>')
    o.append('<rect x="-3.2" y="-2.3" width="30.4" height="14.8" rx="2.4" fill="#232326" stroke="#6a6a6e" stroke-width="0.18"/>')
    # latch (top) and polarising keys
    o.append('<rect x="9.6" y="-5.2" width="4.8" height="2.0" rx="0.3" fill="#18181a" stroke="#8a8a8f" stroke-width="0.18"/>')
    o.append('<rect x="3.3" y="-2.3" width="1.6" height="1.2" fill="#18181a" stroke="#6a6a6e" stroke-width="0.12"/>')
    o.append('<rect x="19.1" y="11.3" width="1.6" height="1.2" fill="#18181a" stroke="#6a6a6e" stroke-width="0.12"/>')
    for n in range(1, 35):
        x, y = pin_xy(n)
        _, g, _ = PIN[n]
        _, _, fill, tc = GC[g]
        ring = "#ffffff" if g == "gsig" else "#e8e8ea"
        o.append(f'<circle cx="{x}" cy="{y}" r="1.18" fill="{fill}" stroke="{ring}" stroke-width="0.16"/>')
        o.append(f'<text x="{x}" y="{y + 0.42}" font-size="1.12" font-weight="700" fill="{tc}" '
                 f'text-anchor="middle" font-family="Helvetica Neue, Arial, sans-serif">{n}</text>')
    return ('<svg class="face" viewBox="-19 -10 62 30.5" xmlns="http://www.w3.org/2000/svg">'
            + "".join(o) + "</svg>")


def legend_table():
    rows = "".join(
        f'<tr><td class="sw"><span class="dot" style="background:{fill}"></span></td>'
        f'<td>{text}</td><td class="pins">{", ".join(str(n) for n in sorted(PIN) if PIN[n][1] == g)}</td></tr>'
        for g, text, fill, _ in GROUPS)
    return f'<table class="legend"><tr><th></th><th>Назначение</th><th class="pins">Контакты J1</th></tr>{rows}</table>'


# ------------------------------------------------------------------ page 2: pin table
def pin_table(blocks):
    """blocks: [(group label, [pin numbers])]."""
    rows = []
    for i, (label, pins) in enumerate(blocks):
        cls = "odd" if i % 2 else "even"
        for j, n in enumerate(pins):
            _, g, name = PIN[n]
            first = f'<td class="grp" rowspan="{len(pins)}">{label}</td>' if j == 0 else ""
            rows.append(f'<tr class="{cls}">{first}<td class="num">{n}</td><td>{name}</td>'
                        f'<td class="swc" style="background:{GC[g][2]}"></td></tr>')
    return ('<table class="pint"><tr><th>Группа</th><th>#</th><th>Назначение</th><th class="swh"></th></tr>'
            + "".join(rows) + "</table>")


def led(i):
    return (f"Лента {i}", [KEY2PIN[f"LED{i}_12V"], KEY2PIN[f"LED{i}_DO"], KEY2PIN[f"LED{i}_GND"]])


LEFT = [led(i) for i in range(1, 5)] + [
    ("CAN", [KEY2PIN["CANH"], KEY2PIN["CANL"]]),
    ("K-line", [KEY2PIN["KLINE"]]),
    ("IGN", [KEY2PIN["IGN"]]),
    ("Датчики", [KEY2PIN["5V_SENS"]]),
]
RIGHT = [led(i) for i in range(5, 9)] + [
    ("Входы", [KEY2PIN["IN1"], KEY2PIN["IN2"], KEY2PIN["IN3"]]),
    ("Масса", [KEY2PIN["SIG1_GND"], KEY2PIN["SIG2_GND"]]),
]
assert sorted(n for _, ps in LEFT + RIGHT for n in ps) == list(range(1, 35))


# ------------------------------------------------------------------ diagrams
def box(x, y, w, h, text, sub="", fill="#d9d9d9"):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="#444" stroke-width="1"/>'
         f'<text x="{x + w / 2}" y="{y + h / 2 + (0 if sub else 5)}" text-anchor="middle" font-size="14">{text}</text>')
    if sub:
        s += f'<text x="{x + w / 2}" y="{y + h / 2 + 16}" text-anchor="middle" font-size="11" fill="#444">{sub}</text>'
    return s


def bus(x1, x2, y, label="", lc="#333"):
    s = (f'<line x1="{x1}" y1="{y - 3}" x2="{x2}" y2="{y - 3}" stroke="{lc}" stroke-width="1.3"/>'
         f'<line x1="{x1}" y1="{y + 3}" x2="{x2}" y2="{y + 3}" stroke="{lc}" stroke-width="1.3"/>')
    if label:
        s += f'<text x="{(x1 + x2) / 2}" y="{y - 8}" text-anchor="middle" font-size="11" fill="#333">{label}</text>'
    return s


def vbus(x, y1, y2, lc="#333"):
    return (f'<line x1="{x - 3}" y1="{y1}" x2="{x - 3}" y2="{y2}" stroke="{lc}" stroke-width="1.3"/>'
            f'<line x1="{x + 3}" y1="{y1}" x2="{x + 3}" y2="{y2}" stroke="{lc}" stroke-width="1.3"/>')


def nodes(x, y):
    return (f'<circle cx="{x - 3}" cy="{y - 3}" r="2" fill="#333"/><circle cx="{x + 3}" cy="{y + 3}" r="2" fill="#333"/>')


def svg_can1():
    s = [box(10, 70, 80, 46, "ЭБУ"), box(225, 10, 110, 46, "DriftAnalyser", "CAN 18/19", "#f1d9d9"),
         box(225, 130, 110, 46, "Другие блоки", "шина авто")]
    s.append(bus(90, 280, 93, "CAN 500 кбит/с"))
    s.append(vbus(280, 56, 130))
    s.append(nodes(280, 93))
    return '<svg class="dia" viewBox="0 0 345 186" xmlns="http://www.w3.org/2000/svg">' + "".join(s) + "</svg>"


def svg_can2():
    s = [box(10, 10, 80, 46, "ЭБУ"), box(10, 130, 80, 46, "Панель", "eDash"),
         box(225, 130, 110, 46, "DriftAnalyser", "CAN 18/19", "#f1d9d9")]
    s.append(vbus(50, 56, 130))
    s.append('<text x="60" y="98" font-size="11" fill="#333">CAN1</text>')
    s.append(bus(90, 225, 153, "CAN2 · 1 Мбит/с"))
    return '<svg class="dia" viewBox="0 0 345 186" xmlns="http://www.w3.org/2000/svg">' + "".join(s) + "</svg>"


def svg_power():
    s = []
    # battery
    s.append('<rect x="10" y="40" width="120" height="80" rx="6" fill="#e6e6e6" stroke="#444"/>')
    s.append('<text x="70" y="86" text-anchor="middle" font-size="15" font-weight="700">АКБ 12 В</text>')
    s.append('<rect x="28" y="28" width="22" height="12" fill="#c62828" stroke="#444"/>'
             '<text x="39" y="22" text-anchor="middle" font-size="14" fill="#c62828" font-weight="700">+</text>')
    s.append('<rect x="90" y="28" width="22" height="12" fill="#222" stroke="#444"/>'
             '<text x="101" y="22" text-anchor="middle" font-size="16" font-weight="700">−</text>')
    # engine block
    s.append('<rect x="10" y="165" width="150" height="40" rx="4" fill="#f4f4f4" stroke="#444" stroke-dasharray="4 3"/>'
             '<text x="75" y="190" text-anchor="middle" font-size="12">блок двигателя</text>')
    s.append('<path d="M101 28 L101 20 L145 20 L145 165" fill="none" stroke="#222" stroke-width="2.5"/>')
    # unit
    s.append('<rect x="250" y="40" width="190" height="165" rx="8" fill="#f1d9d9" stroke="#444"/>')
    s.append('<text x="345" y="125" text-anchor="middle" font-size="15" font-weight="700">DriftAnalyser v3</text>')
    s.append('<circle cx="285" cy="62" r="13" fill="#c62828" stroke="#444"/><text x="285" y="67" text-anchor="middle" '
             'font-size="12" fill="#fff" font-weight="700">+</text>')
    s.append('<circle cx="285" cy="183" r="13" fill="#222" stroke="#444"/><text x="285" y="188" text-anchor="middle" '
             'font-size="13" fill="#fff" font-weight="700">−</text>')
    s.append('<text x="305" y="66" font-size="11">M6 +12V</text><text x="305" y="187" font-size="11">M6 GND</text>')
    # thick cables
    s.append('<path d="M39 28 L39 12 L210 12 L210 62 L272 62" fill="none" stroke="#c62828" stroke-width="5"/>')
    s.append('<path d="M101 205 L101 222 L210 222 L210 183 L272 183" fill="none" stroke="#222" stroke-width="5"/>')
    s.append('<text x="152" y="34" font-size="11" fill="#c62828">~40 А, M6</text>')
    s.append('<text x="125" y="236" font-size="11">масса: на минус АКБ или блок двигателя</text>')
    # connector + strips
    s.append('<rect x="440" y="95" width="18" height="60" fill="#2b2b2d"/><text x="449" y="88" text-anchor="middle" font-size="11">J1</text>')
    for i, y in enumerate((80, 125, 170)):
        s.append(f'<line x1="458" y1="{105 + i * 20}" x2="520" y2="{y + 15}" stroke="#7b2a2c" stroke-width="2"/>')
        s.append(f'<line x1="458" y1="{110 + i * 20}" x2="520" y2="{y + 22}" stroke="#3d7fd6" stroke-width="2"/>')
        s.append(f'<line x1="458" y1="{107 + i * 20}" x2="520" y2="{y + 18}" stroke="#c9a227" stroke-width="1.4"/>')
        s.append(f'<rect x="520" y="{y + 8}" width="70" height="20" rx="3" fill="#fff" stroke="#444"/>'
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

MSTYLE = ('<style>.o{fill:none;stroke:#111;stroke-width:0.3}.f{fill:#f2f2f2;stroke:#111;stroke-width:0.3}'
          '.h{fill:none;stroke:#111;stroke-width:0.18}.ext{stroke:#555;stroke-width:0.13}'
          '.dim{stroke:#111;stroke-width:0.16}.dt{font:2.9px "Jura","Helvetica Neue",Arial,sans-serif;fill:#111}'
          '.lb{font:2.5px "Helvetica Neue",Arial,sans-serif;fill:#333}.cl{stroke:#888;stroke-width:0.12;'
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
        col = "#c62828" if ref == "J2" else "#222"
        o.append(f'<circle class="h" cx="{X(sx)}" cy="{Y(sy)}" r="{E.STUD_BOSS_D / 2}"/>')
        o.append(f'<circle cx="{X(sx)}" cy="{Y(sy)}" r="{E.CAP_D / 2 - 0.5}" fill="{col}" fill-opacity="0.18" '
                 f'stroke="#111" stroke-width="0.3"/>')
        o.append(f'<text class="lb" x="{X(sx)}" y="{Y(sy) + 1.2}" text-anchor="middle" font-weight="700">'
                 f'{"+12V" if ref == "J2" else "GND"}</text>')
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
        col = "#c62828" if ref == "J2" else "#222"
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
:root { --grey:#bfbfbf; --row:#efefef; --ink:#111; --red:#d0201c; }
html, body { margin:0; padding:0; background:#fff; color:var(--ink);
  font-family:"Helvetica Neue", Helvetica, Arial, sans-serif; font-size:10.5pt; line-height:1.38; }
.page { width:210mm; height:297mm; position:relative; padding:13mm 10mm 0 10mm; overflow:hidden;
  page-break-after:always; break-after:page; }
.page:last-child { page-break-after:auto; break-after:auto; }
.hdr { background:var(--grey); height:11mm; display:flex; align-items:center; justify-content:space-between;
  padding:0 3mm; font-weight:700; font-size:11pt; letter-spacing:0.2px; }
.hdr .v { font-size:10pt; }
.title { display:flex; align-items:baseline; justify-content:space-between; margin:5mm 6mm 0 6mm;
  padding-bottom:3mm; border-bottom:1.6px solid #111; }
.brand { white-space:nowrap; font-family:"Jura", "Helvetica Neue", sans-serif; font-weight:700; font-size:22pt; letter-spacing:0.5px; }
.brand b { color:#c62828; }
.prod { white-space:nowrap; font-family:"Jura", "Helvetica Neue", sans-serif; font-size:16pt; letter-spacing:0.6px; }
.ftr { position:absolute; left:10mm; right:10mm; bottom:9mm; display:flex; justify-content:space-between;
  font-family:"Jura", "Helvetica Neue", sans-serif; font-size:11pt; }
.cap { text-align:center; font-weight:700; font-size:9pt; margin:4mm 0 1mm; }
.face { display:block; width:168mm; margin:0 auto; }
.note { text-align:center; font-size:8pt; color:#555; margin-top:0; }
table { border-collapse:collapse; width:100%; }
.legend { margin-top:4mm; border:1px solid #c8c8c8; }
.legend th { background:var(--grey); text-align:left; font-size:9pt; padding:1.2mm 3mm; }
.legend td { padding:0 3mm; height:9.2mm; border-top:1px solid #d6d6d6; font-size:10.5pt; }
.legend tr:nth-child(odd) td:not(.sw) { background:var(--row); }
.legend td.sw { width:15mm; background:#2b2b2d; text-align:center; padding:0; }
.legend .pins { width:52mm; color:#333; font-size:9.5pt; }
.dot { display:inline-block; width:7.4mm; height:7.4mm; border-radius:50%; border:1.6px solid #e8e8ea; vertical-align:middle; }
.warn { color:var(--red); text-align:center; font-size:12.5pt; line-height:1.3; margin-top:4mm; }
.pint { font-size:9.6pt; }
.pint th { background:var(--grey); text-align:left; padding:1.6mm 2mm; font-size:9.5pt; }
.pint td { border:1px solid #d0d0d0; padding:0 2mm; height:6.95mm; }
.pint td.grp { font-weight:700; text-align:center; width:19mm; background:#e4e4e4; }
.pint td.num { width:9mm; text-align:right; }
.pint tr.odd td:not(.swc):not(.grp) { background:var(--row); }
.pint td.swc, .pint th.swh { width:9mm; padding:0; }
.cols { display:flex; gap:4mm; margin-top:3mm; }
.cols > * { flex:1; }
.cols > .wide { flex:1.45; }
.nw { white-space:nowrap; }
h2 { font-size:13pt; margin:6mm 0 2mm; }
h2:first-child { margin-top:5mm; }
p { margin:0 0 2.2mm; }
.small { font-size:9pt; color:#333; }
.spec td, .spec th, .tbl td, .tbl th { border:1px solid #cfcfcf; padding:1.3mm 2.4mm; vertical-align:top; font-size:9.6pt; }
.spec th, .tbl th { background:var(--grey); text-align:left; }
.spec td:first-child { width:46mm; font-weight:600; background:#f4f4f4; }
.tbl tr:nth-child(even) td { background:var(--row); }
.redbox { border:1.6px solid var(--red); color:var(--red); padding:2.4mm 3.5mm; margin:3mm 0; font-size:10.5pt; }
.redbox b { color:var(--red); }
.pwr { display:block; width:160mm; margin:2mm auto 0; font-family:"Helvetica Neue", Arial, sans-serif; }
.dias { display:flex; justify-content:space-between; margin-top:3mm; }
.dias > div { width:88mm; }
.dia { display:block; width:86mm; font-family:"Helvetica Neue", Arial, sans-serif; }
.dcap { font-weight:600; font-size:10pt; margin:0 0 2mm 2mm; }
.dtxt { font-size:9pt; margin:2mm 0 0 2mm; line-height:1.4; }
.mount { display:flex; gap:4mm; align-items:flex-start; }
.top { width:106mm; display:block; flex:none; }
.side { width:184mm; display:block; margin-top:2mm; }
.mnote { font-weight:700; font-size:10pt; margin-top:8mm; }
.mnote p { margin-bottom:3.4mm; }
.iso { width:72mm; display:block; margin-top:2mm; }
code { font-family:Menlo, monospace; font-size:9pt; }
"""


def page(n, body, title=False):
    head = (f'<div class="hdr"><span>ТЕХНИЧЕСКАЯ ДОКУМЕНТАЦИЯ</span><span class="v">{VERSION}</span></div>')
    if title:
        head += ('<div class="title"><span class="brand">Drift<b>Analyser</b> v3</span>'
                 '<span class="prod">Контроллер светодиодных лент</span></div>')
    return (f'<section class="page">{head}{body}'
            f'<div class="ftr"><span>DriftAnalyser 2026</span><span>Страница {n}</span></div></section>')


def build_html():
    iso = base64.b64encode(open(os.path.join(HERE, "iso.jpg"), "rb").read()).decode()
    pages = []

    pages.append(page(1, f"""
<div class="cap">Разъём J1 — вид спереди на блок (со стороны ответной части)</div>
{svg_face()}
<div class="note">Нумерация контактов — по отливке на корпусе разъёма. TE Superseal 1.0, 34 конт.: 6437288-1 (блок), 4-1437290-0 (ответная часть)</div>
{legend_table()}
<div class="warn">Провода GND лент подключать обязательно — масса лент идёт через разъём!<br>
Чёрная клемма GND — толстым кабелем на минус АКБ или блок двигателя.<br>
Оба контакта GND сигнальной (5 и 30) — в одну точку массы.</div>
""", title=True))

    pages.append(page(2, f"""
<div class="cols">{pin_table(LEFT)}{pin_table(RIGHT)}</div>
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
<tr><td>Настройка</td><td>Wi-Fi (ESP32-S3), внешняя антенна SMA; USB-C на задней стенке — сервис и прошивка</td></tr>
<tr><td>Разъём</td><td>TE Superseal 1.0, 34 конт.: 6437288-1, ответная часть 4-1437290-0</td></tr>
<tr><td>Силовые клеммы</td><td>2 × Würth REDCUBE 7461059, внутренняя резьба M6</td></tr>
<tr><td>Габариты</td><td>{fmt(E.X1 - E.X0)} × {fmt(E.Y1 - E.Y0)} мм, высота {fmt(E.HOOD_TOP)} мм; {fmt(E.X1 - E.X0 + 2 * E.EAR_L)} мм по крепёжным ушам (предварительно)</td></tr>
</table>

<h2>Выходы лент</h2>
<p>8 каналов. Каждый канал — свой ключ +12V (ряд 1), линия данных DATA (ряд 2 или 3) и GND (ряд 4, под
своим +12V). Ток канала — до <b>5 А</b>: это предел контакта Superseal, а не ключа. Каналы включаются
независимо, ток каждого канала измеряется. Линии DATA — логика 5 В, для адресных лент WS2812.</p>

<h2>Зажигание IGN</h2>
<p>Контакт 24. +12 В на IGN будит блок. Когда IGN снимается, ленты выключаются и блок засыпает;
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
<div class="redbox"><b>Масса.</b> Обратный ток каждой ленты идёт по её проводу GND через разъём J1 на плату и
дальше на чёрную клемму. Поэтому чёрная клемма GND подключается толстым кабелем к минусу АКБ или блоку
двигателя, а провода GND лент — только в разъём, не на кузов рядом с лентой. Оба контакта GND сигнальной
(5 и 30) — в одну точку массы с датчиками.</div>

<h2>Универсальные входы IN1–IN3</h2>
<p>Контакты 14, 21, 22. Режим каждого входа выбирается в настройках. Вход защищён TVS-диодом 24 В,
диапазон измерения 0–16 В, входное сопротивление без подтяжки ≈ 53 кОм (делитель 10k + 33k + 10k).</p>
<table class="tbl">
<tr><th>Режим</th><th>Подтяжка</th><th>Пример</th></tr>
<tr><td>Цифровой, замыкание на GND</td><td>к +3,3 В, 10 кОм (за делителем)</td><td>кнопка, концевик, датчик «на массу»</td></tr>
<tr><td>Цифровой, подача +12V</td><td>к GND, 10 кОм</td><td>стоп-сигнал, габариты, задний ход</td></tr>
<tr><td>Аналоговый 0–16 В</td><td>нет</td><td>напряжение в бортсети, аналоговые сигналы</td></tr>
<tr><td>Аналоговый датчик 0–5 В</td><td>нет</td><td>датчик давления / положения с питанием от +5V датчиков</td></tr>
</table>

<h2>Питание датчиков +5V</h2>
<p>Контакт 23. Около <b>4,7 В</b>, включается программно, с ограничением тока ≈ 130 мА и отключением при
перегрузке (рекомендуемая нагрузка — до 100 мА). Масса датчиков — GND сигнальная, контакты 5 и 30.</p>
"""))

    pages.append(page(5, f"""
<h2>Шина связи CAN</h2>
<p>Контакты 18 (CAN High) и 19 (CAN Low), витая пара. Один канал, скорость задаётся в настройках:
<b class="nw">500 кбит/с</b> — шина ЭБУ, <b>1 Мбит/с</b> — CAN2 панели eDash. Пока CAN не настроен, блок работает
только на приём (silent) и ничего не передаёт в шину.</p>
<p>Терминатор 120 Ом — перемычка <b>JP2 внутри корпуса</b>, отдельного контакта терминатора на разъёме нет. JP2 ставится, только если DriftAnalyser — крайнее устройство на шине. На уже
терминированной шине автомобиля (обычный случай) JP2 не ставится.</p>
<div class="dias">
<div><div class="dcap">Вариант 1: без панели — DriftAnalyser на шине ЭБУ</div>{svg_can1()}
<div class="dtxt">ЭБУ → шина CAN автомобиля<br>DriftAnalyser → та же шина, 500 кбит/с<br>JP2 — обычно не ставится</div></div>
<div><div class="dcap">Вариант 2: с панелью eDash — DriftAnalyser на CAN2 панели</div>{svg_can2()}
<div class="dtxt">ЭБУ → eDash (CAN1)<br>DriftAnalyser → eDash (CAN2), 1 Мбит/с<br>JP2 — если DriftAnalyser на конце CAN2</div></div>
</div>

<h2>K-line</h2>
<p>Контакт 20. Для ЭБУ без CAN-рассылки данных, например BMW MS43 (протокол DS2). Подтяжка 510 Ом к +12 В
— перемычка <b>JP1 внутри корпуса</b>. Ставить JP1 только если линию больше никто не подтягивает
(большинство ЭБУ подтягивают K-line сами). Если JP1 стоит, а ЭБУ держит линию в нуле, в режиме сна через
подтяжку течёт ~24 мА — в этом случае JP1 снять.</p>

<h2>Перемычки внутри корпуса</h2>
<table class="tbl">
<tr><th>Перемычка</th><th>Установлена</th><th>Снята</th></tr>
<tr><td><b>JP1</b> K-LINE</td><td>подтяжка K-line 510 Ом к +12 В: в машине нет своей подтяжки</td><td>только CAN, или линия уже подтянута</td></tr>
<tr><td><b>JP2</b> CAN TERM</td><td>120 Ом между CAN H и CAN L: блок на конце шины</td><td>блок — ответвление на терминированной шине</td></tr>
</table>
"""))

    pages.append(page(6, """
<h2>Wi-Fi</h2>
<p>Настройка — по Wi-Fi через веб-интерфейс (параметры точки доступа см. в прошивке).
Антенна Wi-Fi — внешняя, разъём SMA на боковой стенке корпуса.</p>

<h2>Провода</h2>
<p>Контакты разъёма: TE Superseal 1.0, контакт <b>3-1447221-3</b> для провода 0,75–1,25 мм².</p>
<div class="cols">
<table class="tbl wide">
<tr><th>Цепь</th><th>Сечение</th><th class="nw">AWG</th></tr>
<tr><td>+12V и GND лент (на контакт)</td><td>0,75–1,25 мм²</td><td class="nw">18–16</td></tr>
<tr><td>DATA, CAN, K-line, IGN, входы, +5V, GND сигнальная</td><td>0,5 мм²</td><td class="nw">20–22</td></tr>
<tr><td>Силовые кабели на клеммы +12V / GND (~40 А)</td><td>по току ~40 А, наконечник M6</td><td class="nw">8–6</td></tr>
</table>
<table class="tbl">
<tr><th>Деталь</th><th>Номер</th></tr>
<tr><td>Разъём на блоке</td><td>TE 6437288-1</td></tr>
<tr><td>Ответная часть</td><td>TE 4-1437290-0</td></tr>
<tr><td>Контакт 0,75–1,25 мм²</td><td>TE 3-1447221-3</td></tr>
<tr><td>Клеммы питания</td><td>Würth 7461059, M6, ≤ 3,9 Н·м</td></tr>
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
<p>Силовые кабели к клеммам +12V / GND подходят сзади; USB-C — на задней стенке, антенна SMA — на боковой стенке.</p>
</div>
<img class="iso" src="data:image/jpeg;base64,{iso}" alt="DriftAnalyser v3">
</div>
</div>
{svg_wrap(svb, sbody, "side")}
"""))

    html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>DriftAnalyser v3 Datasheet</title>'
            '<link href="https://fonts.googleapis.com/css2?family=Jura:wght@400;600;700&display=swap" rel="stylesheet">'
            f'<style>{CSS}</style></head><body>' + "".join(pages) + "</body></html>")
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return len(pages)


def render():
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--virtual-time-budget=5000", f"--print-to-pdf={PDF}", "file://" + HTML],
                   check=True, capture_output=True, timeout=90)
    for n in (1, 2):
        subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", str(n), "-l", str(n), "-singlefile", PDF,
                        os.path.join(HERE, f"page{n}")], check=True)


if __name__ == "__main__":
    print("pages:", build_html())
    render()
