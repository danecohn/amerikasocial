#!/usr/bin/env python3
"""Generate the Amerika sound theme (short retro synth blips, 44.1 kHz 16-bit stereo WAV, deterministic).

    python3 flavor/tools/make_sounds.py   ->  flavor/branding/sounds/Amerika/

Only the Python standard library is used. Event names follow the freedesktop sound naming specification; anything not
provided here is inherited from the freedesktop theme (index.theme: Inherits=freedesktop).
"""
import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'branding/sounds/Amerika'
RATE = 44100


def tone(freq, dur, wave_kind='square', vol=0.30, glide=0.0):
    n = int(RATE * dur)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        f = freq * (1 + glide * t / dur)
        phase += 2 * math.pi * f / RATE
        s = math.sin(phase)
        if wave_kind == 'square':
            s = 1.0 if s >= 0 else -1.0
            s = 0.6 * s + 0.4 * math.sin(phase)  # soften the edge
        env = min(1.0, i / (RATE * 0.004)) * math.exp(-3.2 * t / dur) * min(1.0, (n - i) / (RATE * 0.01))
        out.append(vol * s * env)
    return out


def seq(notes):
    samples = []
    for freq, dur, kind, vol, glide in notes:
        samples += tone(freq, dur, kind, vol, glide) if freq else [0.0] * int(RATE * dur)
    return samples


SOUNDS = {
    'bell': [(880, 0.22, 'sine', 0.35, 0)],
    'message-new-instant': [(1046, 0.07, 'square', 0.25, 0), (1568, 0.12, 'square', 0.25, 0)],
    'message': [(784, 0.09, 'square', 0.22, 0), (988, 0.12, 'square', 0.22, 0)],
    'complete': [(523, 0.08, 'square', 0.25, 0), (659, 0.08, 'square', 0.25, 0), (784, 0.16, 'square', 0.25, 0)],
    'dialog-warning': [(440, 0.12, 'square', 0.3, 0), (0, 0.04, '', 0, 0), (440, 0.18, 'square', 0.3, 0)],
    'dialog-error': [(330, 0.14, 'square', 0.32, -0.3), (220, 0.28, 'square', 0.32, -0.3)],
    'power-plug': [(660, 0.07, 'sine', 0.3, 0), (990, 0.12, 'sine', 0.3, 0)],
    'power-unplug': [(990, 0.07, 'sine', 0.3, 0), (660, 0.12, 'sine', 0.3, 0)],
    'desktop-login': [(262, 0.10, 'square', 0.25, 0), (392, 0.10, 'square', 0.25, 0), (523, 0.10, 'square', 0.25, 0), (784, 0.35, 'sine', 0.3, 0)],
    'desktop-logout': [(784, 0.10, 'square', 0.25, 0), (523, 0.10, 'square', 0.25, 0), (392, 0.10, 'square', 0.25, 0), (262, 0.35, 'sine', 0.3, 0)],
    'screen-capture': [(1800, 0.03, 'square', 0.2, 0), (0, 0.03, '', 0, 0), (900, 0.08, 'square', 0.2, 0)],
}

INDEX = '''[Sound Theme]
Name=Amerika
Comment=Retro-futurist synth blips for AltStack Desktop
Inherits=freedesktop
Directories=stereo

[stereo]
OutputProfile=stereo
'''


def write_wav(path, mono):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = bytearray()
        for s in mono:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            frames += struct.pack('<hh', v, v)
        w.writeframes(bytes(frames))


def main():
    (OUT / 'stereo').mkdir(parents=True, exist_ok=True)
    (OUT / 'index.theme').write_text(INDEX)
    for name, notes in SOUNDS.items():
        write_wav(OUT / 'stereo' / f'{name}.wav', seq(notes))
    print('wrote', len(SOUNDS), 'sounds to', OUT)


if __name__ == '__main__':
    main()
