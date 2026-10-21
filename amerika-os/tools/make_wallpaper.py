#!/usr/bin/python3
"""Renders the Amerika OS retro-futurist wallpaper (horizon sun, neon perspective grid, stars)."""
import math
import random
import sys

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen, QRadialGradient

W, H = 3840, 2160
app = QGuiApplication(['x', '-platform', 'offscreen'])
img = QImage(W, H, QImage.Format.Format_RGB32)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
hz = int(H * 0.60)

sky = QLinearGradient(0, 0, 0, hz)
sky.setColorAt(0, QColor('#07070c'))
sky.setColorAt(0.62, QColor('#17101f'))
sky.setColorAt(1, QColor('#4a1427'))
p.fillRect(0, 0, W, hz, sky)

random.seed(26)
for _ in range(260):
    x, y = random.randrange(W), random.randrange(int(hz * 0.75))
    a = random.randint(50, 170)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, a))
    r = random.choice((1.5, 2, 2.5, 3))
    p.drawEllipse(QPointF(x, y), r, r)

# striped sun disc
cx, cy, R = W / 2, hz - 40, 520
glow = QRadialGradient(cx, cy, R * 2.1)
glow.setColorAt(0, QColor(224, 36, 58, 120))
glow.setColorAt(1, QColor(224, 36, 58, 0))
p.setBrush(QBrush(glow))
p.setPen(Qt.PenStyle.NoPen)
p.drawEllipse(QPointF(cx, cy), R * 2.1, R * 2.1)
sun = QLinearGradient(0, cy - R, 0, cy + R)
sun.setColorAt(0, QColor('#ffd9df'))
sun.setColorAt(0.45, QColor('#ff5d73'))
sun.setColorAt(1, QColor('#b0143a'))
p.setClipRect(QRectF(0, 0, W, hz))
p.setBrush(QBrush(sun))
p.drawEllipse(QPointF(cx, cy), R, R)
p.setBrush(QColor('#17101f'))
for i in range(8):  # horizontal cut stripes, thicker toward the horizon
    y = cy - R * 0.62 + i * R * 0.085
    p.drawRect(QRectF(cx - R, y, 2 * R, 4 + i * 3.4))
p.setClipping(False)

# floor
floor = QLinearGradient(0, hz, 0, H)
floor.setColorAt(0, QColor('#1d0b19'))
floor.setColorAt(1, QColor('#07070c'))
p.fillRect(0, hz, W, H - hz, floor)
vp = QPointF(W / 2, hz)
for i in range(-34, 35):
    x = W / 2 + i * 340
    c = QColor('#ff2e63') if i % 5 == 0 else QColor('#c0306e')
    c.setAlpha(190 if i % 5 == 0 else 110)
    p.setPen(QPen(c, 2.4))
    p.drawLine(vp, QPointF(W / 2 + (x - W / 2) * 6.0, H + 400))
n = 22
for k in range(1, n):
    t = (k / n) ** 2.2
    y = hz + t * (H - hz)
    c = QColor('#ff5d9a')
    c.setAlpha(int(40 + 160 * t))
    p.setPen(QPen(c, 1.4 + 2.2 * t))
    p.drawLine(QPointF(0, y), QPointF(W, y))
p.setPen(QPen(QColor(255, 120, 150, 230), 3))
p.drawLine(QPointF(0, hz), QPointF(W, hz))

# vignette
vig = QRadialGradient(W / 2, H * 0.55, W * 0.75)
vig.setColorAt(0.55, QColor(0, 0, 0, 0))
vig.setColorAt(1, QColor(0, 0, 0, 170))
p.fillRect(0, 0, W, H, vig)
p.end()
out = sys.argv[1] if len(sys.argv) > 1 else 'wallpaper-retro.png'
img.save(out)
img.scaled(2560, 1600, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation).save(
    out.replace('.png', '-2560.png'))
print('wrote', out)
