"""Protocol input checks that do not require a graphical display."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src/os'))
from amerika.shell.tray import endpoint, pixmap_rgba


class TrayInputs(unittest.TestCase):
    def test_registration_forms(self):
        self.assertEqual(endpoint('org.example.Tray'), ('org.example.Tray', '/StatusNotifierItem'))
        self.assertEqual(endpoint('/CustomTray', ':1.23'), (':1.23', '/CustomTray'))
        self.assertEqual(endpoint(':1.23/CustomTray'), (':1.23', '/CustomTray'))

    def test_invalid_endpoints(self):
        for service in ('', 'bad name', '/path-with-dashes', 'org.example.Tray/bad-path'):
            with self.subTest(service=service), self.assertRaises(ValueError):
                endpoint(service)

    def test_network_argb_conversion(self):
        self.assertEqual(pixmap_rgba([(1, 1, bytes([128, 10, 20, 30]))]), (1, 1, bytes([10, 20, 30, 128])))

    def test_selects_large_enough_icon(self):
        pixels = [(size, size, bytes(size * size * 4)) for size in (16, 32, 64)]
        self.assertEqual(pixmap_rgba(pixels)[:2], (32, 32))

    def test_malformed_or_oversize_pixmaps(self):
        for pixels in ([], [(0, 1, b'')], [(1, 1, b'123')], [(513, 1, bytes(513 * 4))]):
            with self.subTest(pixels=pixels[:1]):
                self.assertIsNone(pixmap_rgba(pixels))
