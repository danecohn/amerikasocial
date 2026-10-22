import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import ingest_ai_icons as ing

INDEX = '[Icon Theme]\nName=T\nDirectories=scalable/apps\n\n[scalable/apps]\nSize=256\nType=Scalable\n'


def squircle(path, size=1024, transparent=True, square=True):
    im = Image.new('RGBA', (size, size if square else size // 2), (0, 0, 0, 0 if transparent else 255))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((40, 40, size - 40, (size if square else size // 2) - 40), radius=200, fill=(30, 33, 40, 255))
    im.save(path)


class Ingest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)
        (self.d / 'theme').mkdir()
        (self.d / 'theme/index.theme').write_text(INDEX)
        (self.d / 'in').mkdir()

    def test_good_icon_is_resized_and_indexed(self):
        squircle(self.d / 'in/amerika-files.png')
        ok, bad = ing.ingest(self.d / 'in', self.d / 'theme')
        self.assertEqual((ok, bad), (['amerika-files'], []))
        for n in ing.SIZES:
            self.assertEqual(Image.open(self.d / f'theme/{n}x{n}/apps/amerika-files.png').size, (n, n))
        text = (self.d / 'theme/index.theme').read_text()
        self.assertIn('512x512/apps', text.splitlines()[2])
        ing.ingest(self.d / 'in', self.d / 'theme')  # idempotent
        self.assertEqual(text.count('[512x512/apps]'), 1)
        self.assertEqual((self.d / 'theme/index.theme').read_text().count('[512x512/apps]'), 1)

    def test_rejects_opaque_corners_non_square_small_and_bad_names(self):
        squircle(self.d / 'in/opaque.png', transparent=False)
        squircle(self.d / 'in/wide.png', square=False)
        squircle(self.d / 'in/tiny.png', size=256)
        squircle(self.d / 'in/bad name!.png')
        (self.d / 'in/broken.png').write_bytes(b'not a png')
        ok, bad = ing.ingest(self.d / 'in', self.d / 'theme')
        self.assertEqual(ok, [])
        self.assertEqual(len(bad), 5)
        self.assertFalse((self.d / 'theme/512x512').exists())


if __name__ == '__main__':
    unittest.main()
