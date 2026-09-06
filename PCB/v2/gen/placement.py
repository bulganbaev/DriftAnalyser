"""Where every part sits on the board.

Origin is the board's top-left corner, x right, y down (KiCad convention), mm.
Rotation is KiCad's: degrees CCW on screen, so a point (x, y) of the footprint
lands at (x*cos + y*sin, -x*sin + y*cos) -> rot 90 maps +x to -y and +y to +x.

Layout follows the approved sketch: strip connectors along the top edge, power
input / USB-C / OBD along the bottom edge, ESP32 on the left with its antenna
hanging over the edge, IMU in the middle, microSD on the right edge.
"""

BOARD_W, BOARD_H = 110.0, 75.0
CORNER_R = 3.0
HOLES = [(4.0, 4.0), (106.0, 4.0), (4.0, 71.0), (106.0, 71.0)]

# U1 sits at (8, 33) rot 90, so the module's antenna end (its own -y, 12.75..6.75
# from the origin) points left and hangs over the edge. The ESP32-S3-WROOM-1
# footprint carries a 48 x 21 mm keep-out around it; rotated it covers this box.
# Nothing but copper-free board may live inside it.
ANTENNA_KEEPOUT = (-19.75, 9.0, 1.25, 57.0)   # x0, y0, x1, y1

_STRIP_X0, _STRIP_DX = 15.0, 15.3           # pin 1 (12V_LED) of J11, pitch


def _strip_x(i):
    return _STRIP_X0 + _STRIP_DX * (i - 1)


PLACE = {
    # ---- strip connectors along the top edge, rot 0 keeps pin 1 (12V_LED) left
    # and the JST VH latch wall toward the board edge
    **{f"J{10 + i}": (_strip_x(i), 6.0, 0, "F") for i in range(1, 7)},
    # series resistor + data clamp under each connector
    **{f"R{30 + i}": (_strip_x(i) + 1.5, 14.0, 0, "F") for i in range(1, 7)},
    **{f"D{10 + i}": (_strip_x(i) + 6.5, 14.0, 0, "F") for i in range(1, 7)},

    # ---- 3V3 -> 5V level shifter for the LED data lines
    "U7": (53.0, 22.0, 0, "F"), "C22": (59.0, 22.0, 90, "F"),

    # ---- strip power switch: rot 90 turns the OUT pads (8..14) toward the top
    # edge, i.e. toward the 12V_LED bus feeding the strip connectors
    "U2": (94.0, 26.0, 90, "F"), "C5": (86.0, 24.0, 90, "F"), "C6": (102.0, 24.0, 90, "F"),
    "R1": (89.0, 31.0, 0, "F"), "R2": (94.0, 31.0, 0, "F"), "R5": (99.0, 31.0, 0, "F"),
    "R6": (89.0, 34.0, 0, "F"), "C7": (94.0, 34.0, 0, "F"), "D2": (99.0, 34.5, 0, "F"),

    # ---- ESP32-S3 module, antenna over the left edge
    "U1": (8.0, 33.0, 90, "F"),
    "C16": (25.0, 26.0, 0, "F"), "C17": (25.0, 29.0, 0, "F"), "R11": (25.0, 32.0, 0, "F"),
    "C18": (25.0, 35.0, 0, "F"), "R12": (25.0, 38.0, 0, "F"),
    "SW1": (10.0, 47.0, 0, "F"), "SW2": (21.0, 47.0, 0, "F"),

    # ---- IMU in the middle of the board. LGA-14 pad 1 is the top-left pad at rot 0,
    # which is the datasheet top view, so the sensor +X points at the board's right
    # edge (+x) and +Y at the top edge (-y); +Z is out of the front copper.
    "U5": (55.0, 32.0, 0, "F"), "C20": (50.5, 32.0, 90, "F"), "C21": (59.5, 32.0, 90, "F"),
    "R22": (55.0, 36.0, 0, "F"), "R23": (55.0, 38.5, 0, "F"),

    # ---- microSD on the right edge, rot 90 puts the card slot toward it
    "J5": (96.0, 45.0, 90, "F"),
    "R16": (84.0, 34.5, 90, "F"), "R17": (84.0, 38.0, 90, "F"), "R18": (84.0, 41.5, 90, "F"),
    "R19": (84.0, 45.0, 90, "F"), "R20": (84.0, 48.5, 90, "F"), "R21": (84.0, 52.0, 90, "F"),
    "C19": (80.0, 45.0, 90, "F"),

    # ---- power input, bottom left; rot 180 turns the XT60 opening to the bottom edge
    "J1": (21.0, 57.8, 180, "F"), "D1": (32.0, 47.0, 0, "F"),
    "C1": (33.5, 58.0, 0, "F"), "C2": (33.5, 68.5, 0, "F"),
    "R7": (42.0, 45.0, 0, "F"), "R8": (42.0, 48.0, 0, "F"), "C8": (42.0, 51.0, 0, "F"),

    # ---- 12V -> 5V buck
    "C3": (42.0, 55.5, 90, "F"), "C4": (42.0, 60.5, 90, "F"),
    "R9": (42.0, 70.0, 0, "F"),
    "U3": (47.5, 57.0, 0, "F"),
    # C9 is the buck's own input cap: its pads sit ~1 mm under U3 pin 3 (VBAT) and
    # pin 4 (GND), keeping the hot loop short. C10 is the bootstrap cap.
    "C9": (46.8, 60.6, 0, "F"), "C10": (47.5, 53.5, 0, "F"),
    "R3": (51.0, 51.0, 0, "F"), "R4": (51.0, 48.5, 0, "F"),
    "R10": (47.5, 70.0, 0, "F"), "D5": (47.5, 73.0, 0, "F"),
    # L1 pin 1 lands 2.78 mm from U3 pin 5 (BUCK_SW), the switching node
    "L1": (53.5, 57.0, 0, "F"), "C11": (59.3, 55.0, 0, "F"), "C12": (59.3, 58.5, 0, "F"),

    # ---- 5V rail merge + 3V3 LDO
    "D3": (66.0, 41.0, 0, "F"), "D4": (75.0, 41.0, 0, "F"),
    "U4": (68.0, 48.0, 0, "F"), "C13": (62.0, 45.0, 90, "F"), "C14": (62.0, 50.0, 90, "F"),
    "C15": (75.0, 48.0, 90, "F"),

    # ---- USB-C at the bottom edge, opening outward, ESD next to it
    "J2": (57.0, 71.0, 0, "F"), "U6": (66.0, 70.0, 0, "F"),
    "R14": (64.5, 73.5, 0, "F"), "R15": (68.0, 73.5, 0, "F"),
    "D6": (72.0, 73.5, 0, "F"), "R13": (72.0, 70.5, 0, "F"),

    # ---- CAN + K-line, OBD connector at the bottom edge
    "R41": (63.0, 55.0, 0, "F"), "U8": (68.0, 60.0, 0, "F"), "C24": (68.0, 55.0, 0, "F"),
    "C23": (74.0, 55.0, 0, "F"), "U9": (80.0, 60.0, 0, "F"), "C25": (80.0, 55.0, 0, "F"),
    "R40": (65.0, 65.0, 0, "F"), "D20": (70.0, 66.0, 0, "F"), "JP1": (74.0, 64.0, 0, "F"),
    "R42": (80.0, 66.0, 0, "F"), "JP2": (86.5, 64.0, 0, "F"), "D21": (78.0, 71.0, 0, "F"),
    "J6": (92.0, 71.0, 0, "F"),

    # ---- debug / expansion headers, bottom right
    "J3": (95.0, 56.0, 90, "F"), "J4": (95.0, 62.0, 90, "F"),
}
