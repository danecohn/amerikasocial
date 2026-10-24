#!/usr/bin/python3
"""Renders the AltStack Desktop wallpapers (horizon, grid, dusk) with Qt's painter into src/os/wallpapers."""
import math
import random
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient

W, H = 3840, 2160
OUT = Path(__file__).resolve().parent.parent / 'src/os/wallpapers'
app = QGuiApplication(['x', '-platform', 'offscreen'])


def canvas():
    img = QImage(W, H, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return img, p


def stars(p, hz, n=300, seed=26):
    random.seed(seed)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(n):
        x, y = random.randrange(W), random.randrange(int(hz * 0.8))
        p.setBrush(QColor(255, 255, 255, random.randint(50, 180)))
        r = random.choice((1.5, 2, 2.5, 3))
        p.drawEllipse(QPointF(x, y), r, r)


def floor_grid(p, hz, c1, c2, spacing=340):
    vp = QPointF(W / 2, hz)
    for i in range(-34, 35):
        c = QColor(c1) if i % 5 == 0 else QColor(c2)
        c.setAlpha(190 if i % 5 == 0 else 110)
        p.setPen(QPen(c, 2.4))
        p.drawLine(vp, QPointF(W / 2 + i * spacing * 6.0, H + 400))
    for k in range(1, 22):
        t = (k / 22) ** 2.2
        c = QColor(c2)
        c.setAlpha(int(40 + 160 * t))
        p.setPen(QPen(c, 1.4 + 2.2 * t))
        y = hz + t * (H - hz)
        p.drawLine(QPointF(0, y), QPointF(W, y))
    p.setPen(QPen(QColor(c1), 3))
    p.drawLine(QPointF(0, hz), QPointF(W, hz))


def vignette(p):
    v = QRadialGradient(W / 2, H * 0.55, W * 0.75)
    v.setColorAt(0.55, QColor(0, 0, 0, 0))
    v.setColorAt(1, QColor(0, 0, 0, 170))
    p.fillRect(0, 0, W, H, v)


def sun(p, cx, cy, r, top, mid, bot, bg, stripes=8):
    g = QRadialGradient(cx, cy, r * 2.1)
    g.setColorAt(0, QColor(mid.red(), mid.green(), mid.blue(), 120))
    g.setColorAt(1, QColor(mid.red(), mid.green(), mid.blue(), 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(cx, cy), r * 2.1, r * 2.1)
    lg = QLinearGradient(0, cy - r, 0, cy + r)
    lg.setColorAt(0, top)
    lg.setColorAt(0.5, mid)
    lg.setColorAt(1, bot)
    p.setClipRect(QRectF(0, 0, W, cy))
    p.setBrush(QBrush(lg))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setBrush(bg)
    for i in range(stripes):
        p.drawRect(QRectF(cx - r, cy - r * 0.62 + i * r * 0.085, 2 * r, 4 + i * 3.4))
    p.setClipping(False)


def horizon():
    img, p = canvas()
    hz = int(H * 0.60)
    sky = QLinearGradient(0, 0, 0, hz)
    sky.setColorAt(0, QColor('#07070c'))
    sky.setColorAt(0.62, QColor('#17101f'))
    sky.setColorAt(1, QColor('#4a1427'))
    p.fillRect(0, 0, W, hz, sky)
    stars(p, hz)
    sun(p, W / 2, hz - 40, 520, QColor('#ffd9df'), QColor('#ff5d73'), QColor('#b0143a'), QColor('#17101f'))
    fl = QLinearGradient(0, hz, 0, H)
    fl.setColorAt(0, QColor('#1d0b19'))
    fl.setColorAt(1, QColor('#07070c'))
    p.fillRect(0, hz, W, H - hz, fl)
    floor_grid(p, hz, '#ff2e63', '#ff5d9a')
    vignette(p)
    p.end()
    return img


def grid():
    img, p = canvas()
    hz = int(H * 0.52)
    sky = QLinearGradient(0, 0, 0, hz)
    sky.setColorAt(0, QColor('#04060f'))
    sky.setColorAt(0.7, QColor('#0b1230'))
    sky.setColorAt(1, QColor('#17306a'))
    p.fillRect(0, 0, W, hz, sky)
    stars(p, hz, 420, 7)
    # ringed planet
    cx, cy, r = int(W * 0.72), int(hz * 0.52), 300
    pl = QRadialGradient(cx - r * 0.3, cy - r * 0.3, r * 1.4)
    pl.setColorAt(0, QColor('#ff9ad8'))
    pl.setColorAt(0.6, QColor('#8a2be2'))
    pl.setColorAt(1, QColor('#1b0a3a'))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(pl))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for k, a in enumerate((190, 120)):
        p.setPen(QPen(QColor(25, 227, 255, a), 7 - 2 * k))
        p.save()
        p.translate(cx, cy)
        p.rotate(-18)
        p.drawEllipse(QPointF(0, 0), r * (1.9 - 0.25 * k), r * (0.42 - 0.05 * k))
        p.restore()
    fl = QLinearGradient(0, hz, 0, H)
    fl.setColorAt(0, QColor('#0a1230'))
    fl.setColorAt(1, QColor('#04060f'))
    p.fillRect(0, hz, W, H - hz, fl)
    floor_grid(p, hz, '#19e3ff', '#7a5cff')
    vignette(p)
    p.end()
    return img


def dusk():
    img, p = canvas()
    hz = int(H * 0.66)
    sky = QLinearGradient(0, 0, 0, hz)
    sky.setColorAt(0, QColor('#120a2a'))
    sky.setColorAt(0.45, QColor('#5b1a5e'))
    sky.setColorAt(0.8, QColor('#e0436a'))
    sky.setColorAt(1, QColor('#ffb02e'))
    p.fillRect(0, 0, W, hz, sky)
    stars(p, int(hz * 0.55), 160, 11)
    sun(p, W * 0.5, hz, 640, QColor('#fff2c9'), QColor('#ffb02e'), QColor('#ff3d6e'), QColor('#e0436a'), 9)
    # layered chrome mountains
    random.seed(5)
    for layer, (col, amp, base) in enumerate((('#2a1038', 260, hz - 90), ('#170a26', 340, hz - 30), ('#0b0616', 420, hz + 40))):
        pts = [QPointF(0, H)]
        x = 0
        while x <= W + 160:
            y = base - amp * (0.5 + 0.5 * math.sin(x / (420 + layer * 90) + layer * 2)) * (0.6 + 0.4 * random.random())
            pts.append(QPointF(x, y))
            x += 80
        pts.append(QPointF(W, H))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col))
        p.drawPolygon(QPolygonF(pts))
        p.setPen(QPen(QColor(255, 120, 160, 140 - layer * 30), 3))
        p.drawPolyline(QPolygonF(pts[1:-1]))
    vignette(p)
    p.end()
    return img


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (('horizon', horizon), ('grid', grid), ('dusk', dusk)):
        fn().save(str(OUT / f'{name}.png'))
        print('wrote', OUT / f'{name}.png')
