#!/usr/bin/env python3
"""Front page of 25 November 2026 - deterministic, stdlib-only PNG renderer.

Everything drawn on the canvas is registered in TEXT_LOG.  run_sweep() checks
that registry for stray dates, clipping and unsupported glyphs before the PNG
is written, so the image cannot silently acquire a second date or a clipped
headline.
"""

import os
import re
import struct
import zlib

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
CREAM = (244, 241, 232)
CARD = (255, 253, 247)
INK = (20, 24, 28)
MUTED = (72, 79, 86)
RED = (180, 31, 40)
WHITE = (255, 253, 247)
PANEL = (234, 228, 212)
PANEL_EDGE = (180, 172, 156)
STEEL = (74, 80, 86)
BLUE = (47, 95, 138)
SAND = (198, 156, 70)
WAR = (148, 32, 40)
COURTS = (31, 58, 95)
DISASTER = (166, 90, 20)
ECONOMY = (36, 92, 66)
SCIENCE = (59, 52, 112)
SPORT = (122, 82, 20)

# ---------------------------------------------------------------------------
# 5x7 bitmap font.  The zero has a diagonal slash so it cannot read as "O".
# ---------------------------------------------------------------------------
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10011", "10101", "10101", "11001", "11001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ",": ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
}
DIGITS = frozenset("0123456789")

TEXT_LOG = []


def text_width(value, scale):
    """Pixel width of the inked part of a string (last 1px gap excluded)."""
    return len(value) * 6 * scale - scale


def text_height(scale):
    return 7 * scale


# ---------------------------------------------------------------------------
# Canvas primitives
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, width, height, color):
        self.w = width
        self.h = height
        self.pixels = bytearray(bytes(color) * (width * height))

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            offset = (y * self.w + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def rect(self, x0, y0, x1, y1, color):
        if x0 > x1 or y0 > y1:
            return
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(self.w - 1, x1)
        y1 = min(self.h - 1, y1)
        row = bytes(color) * (x1 - x0 + 1)
        for y in range(y0, y1 + 1):
            start = (y * self.w + x0) * 3
            self.pixels[start:start + len(row)] = row

    def outline(self, x0, y0, x1, y1, color, thick=1):
        self.rect(x0, y0, x1, y0 + thick - 1, color)
        self.rect(x0, y1 - thick + 1, x1, y1, color)
        self.rect(x0, y0, x0 + thick - 1, y1, color)
        self.rect(x1 - thick + 1, y0, x1, y1, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.rect(x0 - thick // 2, y0 - thick // 2,
                      x0 + thick // 2, y0 + thick // 2, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def poly(self, points, color):
        ys = [p[1] for p in points]
        for y in range(min(ys), max(ys) + 1):
            xs = []
            for i, (xa, ya) in enumerate(points):
                xb, yb = points[(i + 1) % len(points)]
                if ya == yb:
                    continue
                if min(ya, yb) <= y < max(ya, yb):
                    xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(round(xs[i])), y, int(round(xs[i + 1])) - 1, y, color)

    def disc(self, cx, cy, radius, color):
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    self.set(x, y, color)

    def ring(self, cx, cy, radius, color, thick=1):
        inner = (radius - thick) ** 2
        outer = radius ** 2
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if inner <= d <= outer:
                    self.set(x, y, color)


def draw_text(canvas, value, x, y, scale, color, box, tag):
    """Draw a registered text line; refuse anything unfit or unsupported."""
    missing = sorted(set(value) - set(FONT))
    if missing:
        raise ValueError(f"missing glyphs {missing} in {value!r}")
    width = text_width(value, scale)
    height = text_height(scale)
    bx0, by0, bx1, by1 = box
    if x < bx0 or y < by0 or x + width > bx1 or y + height > by1:
        raise ValueError(
            f"clipped {value!r}: ink ({x},{y})-({x + width},{y + height}) "
            f"outside {box} [{tag}]"
        )
    for index, char in enumerate(value):
        glyph = FONT[char]
        if len(glyph) != 7 or any(len(r) != 5 for r in glyph):
            raise ValueError(f"bad glyph for {char!r}")
        gx = x + index * 6 * scale
        for gy, bits in enumerate(glyph):
            for gxx, bit in enumerate(bits):
                if bit == "1":
                    canvas.rect(gx + gxx * scale, y + gy * scale,
                                gx + (gxx + 1) * scale - 1,
                                y + (gy + 1) * scale - 1, color)
    TEXT_LOG.append({
        "text": value,
        "box": tuple(box),
        "x": x, "y": y,
        "w": width, "h": height,
        "scale": scale,
        "tag": tag,
    })


# ---------------------------------------------------------------------------
# Layout constants: 2 columns x 4 rows of cards, masthead above, ticker below.
# ---------------------------------------------------------------------------
W = H = 1024
MARGIN = 20
COL_X = (20, 520)
ROW_Y = (146, 334, 522, 710)
CARD_W = 484
CARD_H = 176
HEADER_H = 28
TEXT_X = 122
PANEL_BOX = (10, 36, 110, 168)
COL_TEXT_BOX_DX = (122, 474)


def card(canvas, index, label, band_color, pictogram,
         headline, detail):
    cx = COL_X[index % 2]
    cy = ROW_Y[index // 2]
    canvas.rect(cx, cy, cx + CARD_W - 1, cy + CARD_H - 1, CARD)
    canvas.outline(cx, cy, cx + CARD_W - 1, cy + CARD_H - 1, INK, 2)
    canvas.rect(cx + 2, cy + 2, cx + CARD_W - 3, cy + HEADER_H, band_color)
    draw_text(canvas, label, cx + 10, cy + 6, 3, WHITE,
              (cx + 10, cy + 4, cx + CARD_W - 10, cy + HEADER_H + 2),
              f"card-{index}-region")

    px0 = cx + PANEL_BOX[0]
    py0 = cy + PANEL_BOX[1]
    pw = PANEL_BOX[2] - PANEL_BOX[0]
    ph = PANEL_BOX[3] - PANEL_BOX[1]
    canvas.rect(px0, py0, px0 + pw - 1, py0 + ph - 1, PANEL)
    canvas.outline(px0, py0, px0 + pw - 1, py0 + ph - 1, PANEL_EDGE)
    pictogram(canvas, px0, py0)

    box = (cx + COL_TEXT_BOX_DX[0], cy + 32,
           cx + COL_TEXT_BOX_DX[1], cy + CARD_H - 6)
    head_box = (box[0], cy + 34, box[2], cy + 98)
    draw_text(canvas, headline[0], box[0], cy + 36, 4, INK, head_box,
              f"card-{index}-head-1")
    draw_text(canvas, headline[1], box[0], cy + 68, 4, INK, head_box,
              f"card-{index}-head-2")
    for line_no, line in enumerate(detail):
        dy = cy + 102 + line_no * 22
        draw_text(canvas, line, box[0], dy, 3, MUTED,
                  (box[0], dy - 2, box[2], dy + 23),
                  f"card-{index}-detail-{line_no + 1}")


# ---------------------------------------------------------------------------
# Pictograms - flat shapes, sized to fill the 100x132 panel.
# ---------------------------------------------------------------------------
def pic_power(c, ox, oy):
    c.line(ox + 22, oy + 118, ox + 48, oy + 22, INK, 3)
    c.line(ox + 78, oy + 118, ox + 48, oy + 22, INK, 3)
    for yy, half in ((52, 9), (76, 15), (100, 21)):
        c.line(ox + 48 - half, oy + yy, ox + 48 + half, oy + yy, INK, 2)
    c.line(ox + 6, oy + 120, ox + 94, oy + 120, INK, 2)
    c.poly([(ox + 76, oy + 12), (ox + 58, oy + 58), (ox + 70, oy + 58),
            (ox + 54, oy + 100), (ox + 88, oy + 48), (ox + 74, oy + 48),
            (ox + 86, oy + 12)], RED)


def pic_strike(c, ox, oy):
    c.rect(ox + 8, oy + 72, ox + 40, oy + 118, STEEL)
    c.rect(ox + 48, oy + 54, ox + 90, oy + 118, STEEL)
    for row in range(3):
        for col in range(2):
            c.rect(ox + 14 + col * 14, oy + 80 + row * 12,
                   ox + 21 + col * 14, oy + 87 + row * 12, PANEL)
            c.rect(ox + 55 + col * 15, oy + 62 + row * 15,
                   ox + 63 + col * 15, oy + 70 + row * 15, PANEL)
    c.poly([(ox + 68, oy + 8), (ox + 76, oy + 24), (ox + 94, oy + 20),
            (ox + 80, oy + 36), (ox + 86, oy + 54), (ox + 68, oy + 44),
            (ox + 50, oy + 54), (ox + 56, oy + 36), (ox + 42, oy + 20),
            (ox + 60, oy + 24)], RED)
    c.disc(ox + 22, oy + 52, 7, PANEL_EDGE)


def pic_drone(c, ox,oy):
    c.rect(ox + 38, oy + 54, ox + 62, oy + 74, INK)
    for x0, y0 in ((16, 40), (84, 40), (16, 88), (84, 88)):
        c.line(ox + 50, oy + 64, ox + x0, oy + y0, INK, 2)
        c.line(ox + x0 - 10, oy + y0, ox + x0 + 10, oy + y0, INK, 3)
        c.disc(ox + x0, oy + y0, 4, RED)
    c.line(ox + 50, oy + 74, ox + 50, oy + 90, INK, 2)
    c.poly([(ox + 44, oy + 90), (ox + 56, oy + 90),
            (ox + 53, oy + 104), (ox + 47, oy + 104)], RED)
    c.line(ox + 8, oy + 120, ox + 92, oy + 120, INK, 2)
    c.poly([(ox + 34, oy + 112), (ox + 42, oy + 98), (ox + 48, oy + 112)],
           PANEL_EDGE)


def pic_scales(c, ox, oy):
    c.rect(ox + 34, oy + 114, ox + 66, oy + 122, RED)
    c.line(ox + 50, oy + 26, ox + 50, oy + 114, INK, 3)
    c.line(ox + 14, oy + 36, ox + 86, oy + 36, INK, 3)
    c.disc(ox + 50, oy + 24, 5, INK)
    for arm_x in (20, 80):
        c.line(ox + arm_x, oy + 38, ox + arm_x, oy + 66, INK, 2)
        c.poly([(ox + arm_x - 13, oy + 66), (ox + arm_x + 13, oy + 66),
                (ox + arm_x + 8, oy + 82), (ox + arm_x - 8, oy + 82)], INK)
    c.line(ox + 38, oy + 108, ox + 62, oy + 108, INK, 2)


def pic_fire(c, ox, oy):
    c.poly([(ox + 8, oy + 70), (ox + 62, oy + 70),
            (ox + 62, oy + 106), (ox + 8, oy + 106)], STEEL)
    c.rect(ox + 62, oy + 78, ox + 88, oy + 106, STEEL)
    c.disc(ox + 24, oy + 108, 7, INK)
    c.disc(ox + 76, oy + 108, 7, INK)
    c.poly([(ox + 16, oy + 68), (ox + 10, oy + 46), (ox + 24, oy + 52),
            (ox + 28, oy + 26), (ox + 42, oy + 54), (ox + 38, oy + 68)], RED)
    c.poly([(ox + 38, oy + 70), (ox + 34, oy + 38), (ox + 50, oy + 50),
            (ox + 56, oy + 22), (ox + 70, oy + 54), (ox + 64, oy + 70)], RED)
    c.poly([(ox + 58, oy + 70), (ox + 60, oy + 48), (ox + 72, oy + 56),
            (ox + 74, oy + 70)], SAND)
    c.disc(ox + 40, oy + 18, 6, PANEL_EDGE)
    c.disc(ox + 64, oy + 12, 5, PANEL_EDGE)


def pic_trade(c, ox, oy):
    c.poly([(ox + 8, oy + 92), (ox + 92, oy + 92),
            (ox + 80, oy + 114), (ox + 20, oy + 114)], INK)
    for x0 in (18, 41, 64):
        c.rect(ox + x0, oy + 70, ox + x0 + 19, oy + 90, ECONOMY)
        c.line(ox + x0, oy + 78, ox + x0 + 19, oy + 78, PANEL, 1)
    for x0 in (30, 53):
        c.rect(ox + x0, oy + 48, ox + x0 + 19, oy + 68, RED)
        c.line(ox + x0, oy + 56, ox + x0 + 19, oy + 56, PANEL, 1)
    c.line(ox + 10, oy + 122, ox + 34, oy + 122, BLUE, 2)
    c.line(ox + 40, oy + 122, ox + 64, oy + 122, BLUE, 2)
    c.line(ox + 70, oy + 122, ox + 92, oy + 122, BLUE, 2)
    c.line(ox + 50, oy + 10, ox + 50, oy + 40, INK, 3)
    c.poly([(ox + 42, oy + 32), (ox + 58, oy + 32),
            (ox + 50, oy + 46)], INK)


def pic_space(c, ox, oy):
    c.rect(ox + 38, oy + 54, ox + 62, oy + 78, INK)
    for x0 in (6, 68):
        c.rect(ox + x0, oy + 56, ox + x0 + 26, oy + 74, BLUE)
        for sx in range(x0 + 6, x0 + 26, 7):
            c.line(ox + sx, oy + 56, ox + sx, oy + 74, WHITE, 1)
        c.line(ox + x0 + 26 if x0 == 6 else ox + x0,
               oy + 64, ox + 38 if x0 == 6 else ox + 62, oy + 64, INK, 2)
    c.line(ox + 50, oy + 54, ox + 50, oy + 26, INK, 2)
    c.disc(ox + 50, oy + 22, 6, RED)
    c.line(ox + 44, oy + 78, ox + 36, oy + 96, INK, 2)
    c.line(ox + 56, oy + 78, ox + 64, oy + 96, INK, 2)
    c.ring(ox + 50, oy + 64, 54, PANEL_EDGE, 1)


def pic_trophy(c, ox, oy):
    c.poly([(ox + 30, oy + 30), (ox + 70, oy + 30),
            (ox + 66, oy + 66), (ox + 54, oy + 80),
            (ox + 46, oy + 80), (ox + 34, oy + 66)], SAND)
    c.ring(ox + 27, oy + 46, 10, INK, 3)
    c.ring(ox + 73, oy + 46, 10, INK, 3)
    c.rect(ox + 46, oy + 80, ox + 54, oy + 98, INK)
    c.rect(ox + 32, oy + 98, ox + 68, oy + 108, INK)
    c.rect(ox + 26, oy + 108, ox + 74, oy + 116, RED)
    c.poly([(ox + 50, oy + 38), (ox + 55, oy + 48), (ox + 66, oy + 48),
            (ox + 57, oy + 55), (ox + 60, oy + 66), (ox + 50, oy + 59),
            (ox + 40, oy + 66), (ox + 43, oy + 55), (ox + 34, oy + 48),
            (ox + 45, oy + 48)], INK)
    c.disc(ox + 50, oy + 18, 7, RED)


CARDS = (
    ("UKRAINE", WAR, pic_power,
     ("RUSSIAN STRIKE", "CUTS POWER"),
     ("FIVE REGIONS HIT", "DTEK PLANT HALTED", "NAFTOGAZ SITE BURNS")),
    ("MIDDLE EAST", WAR, pic_strike,
     ("HAMAS SECURITY", "CHIEF KILLED"),
     ("ISRAELI STRIKE HITS", "GAZA CITY APARTMENT", "WIFE, TWO CHILDREN")),
    ("SUDAN", WAR, pic_drone,
     ("RSF DRONES", "KILL 19"),
     ("DAMAZIN, ROSEIRES", "HIT; 20 WOUNDED IN", "BLUE NILE STATE")),
    ("SOUTH AFRICA", COURTS, pic_scales,
     ("COURT SETS", "ASIDE FINDINGS"),
     ("WESTERN CAPE COURT", "VOIDS RAMAPHOSA", "FARMGATE FINDINGS")),
    ("EGYPT", DISASTER, pic_fire,
     ("AT LEAST 30", "KILLED"),
     ("FUEL TRUCK FIRE", "ON CAIRO RING ROAD", "25 HURT; CARS BURNT")),
    ("ECONOMY", ECONOMY, pic_trade,
     ("US PROPOSES", "TARIFFS"),
     ("DUTIES UP TO 20", "PERCENT ON EU AND", "CHINA; 14 PARTNERS")),
    ("SCIENCE", SCIENCE, pic_space,
     ("PAKISTANI", "ON TIANGONG"),
     ("ZEESHAN ALI FIRST", "FOREIGNER ABOARD", "THREE-MAN CREW")),
    ("SPORT", SPORT, pic_trophy,
     ("SENEGAL", "CUP CHAMPIONS"),
     ("CAS UPHOLDS 1-0", "FINAL WIN OVER", "MOROCCO; APPEAL")),
)

TICKER = (
    ("SPAIN CLOSES", "PUIGDEMONT CASE"),
    ("COLOMBIA FREES", "STORE HOSTAGES"),
    ("CHINA PROBES", "SHANGHAI CHIEF"),
    ("FCC OKAYS", "1M SATELLITES"),
    ("IOWA BLAST", "NEARLY 5 TONS"),
    ("ROMA HOLD PSG", "2-2 DRAW"),
)

DATE = "25 NOVEMBER 2026"
MONTHS = ("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
          "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER")
SCORES = frozenset(("1-0", "2-2"))


def masthead(canvas):
    canvas.rect(0, 0, W - 1, 7, INK)
    title = "WORLD NEWS"
    tw = text_width(title, 9)
    draw_text(canvas, title, (W - tw) // 2, 16, 9, INK,
              (MARGIN, 12, W - MARGIN, 84), "masthead-title")
    canvas.rect(MARGIN, 86, W - MARGIN - 1, 132, RED)
    dw = text_width(DATE, 5)
    draw_text(canvas, DATE, (W - dw) // 2, 96, 5, WHITE,
              (MARGIN, 90, W - MARGIN, 133), "masthead-date")
    canvas.rect(MARGIN, 140, W - MARGIN - 1, 141, INK)


def ticker(canvas):
    y0 = 894
    y1 = 1018
    canvas.rect(MARGIN, y0, W - MARGIN - 1, y1, INK)
    canvas.rect(MARGIN, y0, 103, y1, RED)
    for i, word in enumerate(("MORE", "NEWS", "WIRE")):
        draw_text(canvas, word, 28, y0 + 12 + i * 36, 3, WHITE,
                  (26, y0 + 8 + i * 36, 100, y0 + 36 + i * 36),
                  f"ticker-label-{i}")
    for index, lines in enumerate(TICKER):
        col = index % 3
        row = index // 3
        x0 = 104 + col * 300
        ty = y0 + row * 62
        for line_no, line in enumerate(lines):
            ly = ty + 10 + line_no * 26
            draw_text(canvas, line, x0 + 10, ly, 3, WHITE,
                      (x0 + 8, ly - 2, x0 + 292, ly + 23),
                      f"ticker-{index}-line-{line_no + 1}")
        if col > 0:
            canvas.rect(x0, y0 + 4, x0, y1 - 4, (96, 101, 106))
    canvas.rect(104, y0 + 62, W - MARGIN - 1, y0 + 62, (96, 101, 106))


def render():
    canvas = Canvas(W, H, CREAM)
    masthead(canvas)
    for index, (label, color, pictogram, headline, detail) in enumerate(CARDS):
        card(canvas, index, label, color, pictogram, headline, detail)
    ticker(canvas)
    return canvas


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_digits():
    if "0" not in FONT or set("0123456789") - set(FONT):
        raise AssertionError("digit glyph missing")
    if FONT["0"] == FONT["O"]:
        raise AssertionError("zero must differ from O")
    # Slashed zero must differ visually in at least a few raster rows.
    diff = sum(sum(a != b for a, b in zip(r0, rO))
               for r0, rO in zip(FONT["0"], FONT["O"]))
    if diff < 4:
        raise AssertionError(f"slashed zero too similar to O ({diff} cells)")
    for sample in ("3-2", "31", "129", "0O"):
        probe = Canvas(6 * 6 * 4 + 20, 7 * 4 + 20, WHITE)
        for i, char in enumerate(sample):
            glyph = FONT[char]
            for gy, bits in enumerate(glyph):
                for gx, bit in enumerate(bits):
                    if bit == "1":
                        probe.rect(10 + i * 24 + gx * 4, 10 + gy * 4,
                                   10 + i * 24 + gx * 4 + 3,
                                   10 + gy * 4 + 3, INK)
        for i, char in enumerate(sample):
            inked = sum(1 for y in range(10, 10 + 28)
                        for x in range(10 + i * 24, 10 + i * 24 + 20)
                        if probe.pixels[(y * probe.w + x) * 3] == INK[0])
            if char != " " and inked == 0:
                raise AssertionError(f"empty digit glyph {char!r} in {sample}")
    return diff


def run_sweep():
    verify_digits()
    dates = [item for item in TEXT_LOG if item["text"] == DATE]
    if len(dates) != 1 or dates[0]["tag"] != "masthead-date":
        raise AssertionError("contest date must appear exactly once in masthead")
    for item in TEXT_LOG:
        value = item["text"]
        if value == DATE:
            continue
        for month in MONTHS:
            if month in value:
                raise AssertionError(f"extra month name in {value!r}")
        if re.search(r"\b\d{4}\b", value):
            raise AssertionError(f"year-like number in {value!r}")
        for token in re.findall(r"\b\d{1,2}[-/]\d{1,2}(?:[-/]\d{1,4})?\b", value):
            if token not in SCORES:
                raise AssertionError(f"date-like token {token!r} in {value!r}")
        bx0, by0, bx1, by1 = item["box"]
        if not (bx0 <= item["x"] and by0 <= item["y"]
                and item["x"] + item["w"] <= bx1
                and item["y"] + item["h"] <= by1):
            raise AssertionError(f"text outside its box: {value!r}")
        if not (0 <= bx0 < bx1 <= W and 0 <= by0 < by1 <= H):
            raise AssertionError(f"container off canvas: {value!r}")
        if any(ch in DIGITS for ch in value) and not set(value) <= set(FONT):
            raise AssertionError(f"digit string uses unsupported glyphs: {value!r}")
    return {
        "strings": len(TEXT_LOG),
        "dates": len(dates),
        "zero_vs_O_cells": verify_digits(),
        "max_width": max(item["w"] for item in TEXT_LOG),
    }


def png_bytes(canvas):
    raw = bytearray()
    for y in range(canvas.h):
        raw.append(0)
        start = y * canvas.w * 3
        raw.extend(canvas.pixels[start:start + canvas.w * 3])

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("OUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    TEXT_LOG.clear()
    canvas = render()
    report = run_sweep()
    data = png_bytes(canvas)
    if len(data) > 1024 * 1024:
        raise AssertionError("PNG exceeds 1 MiB")
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as handle:
        handle.write(data)
    print(f"wrote {path}: {W}x{H}, {len(data)} bytes, "
          f"{report['strings']} text lines, {report['dates']} date")


if __name__ == "__main__":
    main()
