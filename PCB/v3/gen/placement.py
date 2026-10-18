"""Where every part sits on the board.

Origin is the board's top-left corner, x right, y down (KiCad convention), mm.
Rotation is KiCad's: degrees CCW on screen, so a point (x, y) of the footprint
lands at (x*cos + y*sin, -x*sin + y*cos) -> rot 90 maps +x to -y and +y to +x.

J1 (Superseal 34) sits on the top short edge, mating face out through the case
end wall. Right under it the four high-side switches, then their control
passives, the expander and the data buffers. Below that the board splits:
power on the left (stud in the bottom-left corner, ideal diode above it, buck
and LDO above that), logic on the right: the ESP32 right under the expander and
the buffers' resistor rows (u.FL toward the right wall), the CAN / K-line /
input block below it, comms between them.
"""

BOARD_W, BOARD_H = 55.0, 100.0
CORNER_R = 3.0

# M3, 3.2 mm. The top pair sits below J1's body: the connector's courtyard is
# 46.5 mm of the 55 mm edge, which leaves no room for a hole beside it.
# The bottom pair keeps >= 0.5 mm from the stud's and U1's courtyards (screw head / washer).
HOLES = [(3.8, 27.4), (51.2, 27.4), (3.5, BOARD_H - 3.5), (51.5, BOARD_H - 3.5)]

# WROOM-1U has a u.FL, not a PCB antenna: no keep-out on this board.
ANTENNA_KEEPOUT = None

# J1 at rot 180: footprint y = +6 (the flange, "board edge <= here") lands on y = 0.
J1_AT = (27.5, 6.0)

# ---- the four BTS7008-2EPA, rot 90 turns OUT0/OUT1 (pins 8..14) toward J1.
# x of each switch, left to right; ordered so each sits under its strips' J1 pins.
SW_Y = 27.7
SW_X = {"U13": 13.1, "U11": 22.7, "U12": 32.3, "U10": 41.9}
ROW_A, ROW_B = 33.6, 36.8              # series 4.7k row, pull-down / VS cap row
_DX = (-2.55, -0.85, 0.85, 2.55)       # under pins IN0, DEN, DSEL, IN1


def _switch(u):
    k = int(u[1:]) - 9                  # U10 -> 1
    a, b = 2 * k - 1, 2 * k             # LEDa on OUT0 (left), LEDb on OUT1 (right)
    x = SW_X[u]
    out = {u: (x, SW_Y, 90, "F"),
           # 10 nF per output, beside its own output pins
           f"C{21 + 3 * (k - 1)}": (x - 3.65, SW_Y, 90, "F"),
           f"C{22 + 3 * (k - 1)}": (x + 3.65, SW_Y, 90, "F")}
    series = (f"R{19 + 2 * a}", f"R{38 + 3 * (k - 1)}", f"R{39 + 3 * (k - 1)}", f"R{19 + 2 * b}")
    pulls = (f"R{18 + 2 * a}", f"R{37 + 3 * (k - 1)}", f"R{18 + 2 * b}", f"C{20 + 3 * (k - 1)}")
    for dx, s, p in zip(_DX, series, pulls):
        out[s] = (x + dx, ROW_A, 90, "F")
        out[p] = (x + dx, ROW_B, 90, "F")
    return out


PLACE = {
    "J1": (*J1_AT, 180, "F"),
    **{k: v for u in SW_X for k, v in _switch(u).items()},

    # ---- shared current sense + DSEL pull-down + I2C pull-ups, left of the control rows
    "D10": (2.6, 33.0, 0, "F"), "R49": (5.6, 33.4, 90, "F"), "R50": (7.4, 33.4, 90, "F"),
    "R36": (5.6, 36.8, 90, "F"), "C32": (7.4, 36.8, 90, "F"),
    "R52": (2.0, 35.8, 0, "F"), "R53": (2.0, 37.5, 0, "F"),
    # K-line and input clamps, right of the control rows: as close to J1 as it gets
    "D21": (51.2, 33.0, 0, "F"), "D24": (51.2, 36.75, 0, "F"),
    "D22": (51.2, 40.6, 0, "F"), "D23": (51.2, 44.4, 0, "F"),

    # ---- data buffers, series 33R + clamp per line, expander
    "U15": (6.0, 42.8, 0, "F"), "C34": (10.75, 40.4, 90, "F"),
    "U16": (17.0, 42.8, 0, "F"), "C35": (21.95, 40.4, 90, "F"),
    **{f"R{53 + i}": (24.9 + 6.7 * ((i - 1) // 4), 40.0 + 2.1 * ((i - 1) % 4), 0, "F") for i in range(1, 9)},
    **{f"D{10 + i}": (28.3 + 6.7 * ((i - 1) // 4), 40.0 + 2.1 * ((i - 1) % 4), 0, "F") for i in range(1, 9)},
    "U14": (41.6, 43.0, 0, "F"), "C33": (46.6, 40.0, 90, "F"), "R51": (46.6, 45.5, 90, "F"),

    # ---- buck 12 -> 5.4 V, top of the power column. C8 (bootstrap) has its BST
    # pad down, facing U7 pin 7, and its SW pad up, where the switch node comes in.
    "U7": (7.9, 51.6, 0, "F"), "C7": (1.9, 51.0, 90, "F"), "C37": (2.0, 55.7, 90, "F"),
    "C8": (12.95, 49.1, 270, "F"), "C38": (7.9, 55.9, 0, "F"),
    "L1": (17.5, 51.6, 0, "F"), "C9": (22.4, 50.2, 90, "F"), "C10": (24.6, 50.2, 90, "F"),
    "R9": (13.0, 56.1, 0, "F"), "R10": (13.0, 57.9, 0, "F"),
    "D6": (19.4, 57.0, 0, "F"), "C11": (24.4, 57.2, 90, "F"),

    # ---- the power path reads bottom to top: stud -> D1 (TVS on VIN) -> Q1/Q2
    # sources -> drain tabs -> VBUS (C3 bulk beside them, then up to the switches).
    # The FETs at rot 90 turn local -x (sources 1..3, gate 4) down to the stud and
    # the drain tab up. U2 sits left of D1: ANODE/GATE/CATHODE (pins 5..8) face the
    # FETs' gates and sources, VCAP (pin 4) faces C2.
    "J2": (14.0, BOARD_H - 13.5, 0, "F"),
    "D1": (18.8, 72.9, 0, "F"),
    "Q1": (15.85, 65.1, 90, "F"), "Q2": (21.7, 65.1, 90, "F"),
    "C3": (6.5, 64.0, 0, "F"), "C4": (2.0, 73.6, 90, "F"),
    "U2": (10.5, 71.0, 0, "F"), "C1": (10.5, 74.4, 0, "F"), "C2": (7.6, 71.0, 90, "F"),

    # ---- IMU near the board centre, LDO, sensor 5 V switch, wake: middle column
    "U3": (29.8, 49.3, 0, "F"), "C19": (26.6, 49.3, 90, "F"), "C36": (33.0, 49.3, 90, "F"),
    "U8": (30.2, 55.0, 0, "F"), "C12": (27.4, 59.8, 0, "F"), "C13": (32.0, 59.8, 0, "F"),
    "U6": (27.0, 63.0, 0, "F"), "D7": (30.0, 66.8, 0, "F"),
    "R11": (30.3, 63.0, 90, "F"), "R12": (32.0, 63.0, 90, "F"), "R13": (33.7, 63.0, 90, "F"),
    "C14": (25.4, 66.8, 90, "F"), "C15": (34.4, 66.8, 90, "F"),
    "R5": (25.4, 70.4, 90, "F"), "R6": (27.1, 70.4, 90, "F"), "R7": (28.8, 70.4, 90, "F"),
    "R8": (30.5, 70.4, 90, "F"), "R19": (32.2, 70.4, 90, "F"),
    "D4": (2.0, 69.9, 0, "F"), "D5": (5.2, 69.9, 0, "F"),

    # ---- ESP32 right under U14 and the data resistor rows, u.FL (module top right)
    # at the right wall. It used to sit in the bottom-right corner, and the eight
    # DATA lines, I2C, IMU INT, ISENSE and CAN TX all had to cross the board to it:
    # the autorouter stalled at ~50 open links (task 11).
    "U1": (45.1, 57.3, 0, "F"),
    "R14": (26.1, 72.9, 0, "F"), "C18": (29.4, 72.9, 0, "F"), "C17": (32.7, 72.9, 0, "F"),
    "SW2": (29.6, 78.0, 0, "F"),
    "D8": (28.5, 83.6, 0, "F"), "C16": (33.9, 83.6, 90, "F"),
    "U9": (27.0, 87.8, 0, "F"), "R17": (30.5, 87.9, 90, "F"), "R18": (32.2, 87.9, 90, "F"),
    "R15": (33.9, 87.9, 90, "F"),
    "J3": (29.6, BOARD_H - 4.4, 0, "F"),
    "SW1": (41.4, BOARD_H - 3.7, 0, "F"),

    # ---- CAN, K-line, battery / ignition sense, input dividers, headers: below the
    # ESP32 (COMMS_SHIFT moves the whole block down as one, see the end of the file)
    "U4": (39.4, 50.6, 0, "F"), "C40": (44.2, 49.3, 90, "F"), "C41": (45.9, 49.3, 90, "F"),
    "R70": (44.2, 52.5, 90, "F"),
    "R71": (39.4, 55.0, 0, "F"), "D20": (45.2, 56.0, 0, "F"),
    "U5": (39.4, 60.0, 0, "F"), "C42": (44.2, 59.6, 90, "F"), "R72": (45.9, 59.6, 90, "F"),
    "JP2": (49.3, 49.3, 0, "F"), "JP1": (53.05, 49.3, 0, "F"),
    "R73": (49.25, 58.4, 90, "F"), "J4": (53.1, 57.4, 0, "F"),
    "D9": (52.2, 69.7, 90, "F"), "R16": (53.9, 69.7, 90, "F"),
    "R1": (36.4, 64.6, 90, "F"), "R2": (38.1, 64.6, 90, "F"), "C5": (39.8, 64.6, 90, "F"),
    "R3": (41.5, 64.6, 90, "F"), "R4": (36.4, 67.77, 90, "F"), "C6": (38.1, 67.77, 90, "F"),
    "D2": (45.3, 63.6, 0, "F"), "D3": (45.3, 67.4, 0, "F"),
    **{f"R{74 + i}": (48.4 + 1.7 * (i % 2), 64.0 + 3.2 * (i // 2), 90, "F") for i in range(6)},
    "R80": (39.8, 67.77, 90, "F"), "R81": (41.5, 67.77, 90, "F"),
    **{f"R{82 + i}": (36.4 + 1.7 * i, 70.82, 90, "F") for i in range(4)},
}

# The CAN / K-line / sense / input block, laid out where the ESP32 is now and moved
# down below it as one piece, so its internal spacing stays what it was.
COMMS_BLOCK = ("U4", "C40", "C41", "R70", "R71", "D20", "U5", "C42", "R72", "JP2", "JP1",
               "R73", "J4", "D9", "R16", "R1", "R2", "C5", "R3", "R4", "C6", "D2", "D3",
               *(f"R{74 + i}" for i in range(6)), "R80", "R81", *(f"R{82 + i}" for i in range(4)))
COMMS_SHIFT = 20.3
for _ref in COMMS_BLOCK:
    _x, _y, _rot, _side = PLACE[_ref]
    PLACE[_ref] = (_x, round(_y + COMMS_SHIFT, 3), _rot, _side)
