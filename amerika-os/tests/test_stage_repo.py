"""Release redirect reuse must match bytes, not just a reused name/size."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stage_repo',ROOT/'tools/stage-for-social.py')
stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)


class Redirects(unittest.TestCase):
    def test_same_size_different_bytes_get_new_release_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'source';social=root/'social';dest=social/'apt-repo'
            (repo/'dists/stable').mkdir(parents=True);(repo/'dists/stable/InRelease').write_text('fake signed fixture')
            pool=repo/'pool';pool.mkdir();deb=pool/'amerika-agent.deb';deb.write_bytes(b'BBBB')
            dest.mkdir(parents=True)
            (dest/'pool-redirects.json').write_text(json.dumps({deb.name:{'url':'https://example.invalid/old','size':4}}))
            (dest/'manifest.json').write_text(json.dumps({'packages':{deb.name:{'sha256':hashlib.sha256(b'AAAA').hexdigest()}}}))
            with unittest.mock.patch.object(stage,'LIMIT',1):
                result=stage.stage(social,repo,'os-new')
                redirect=json.loads((dest/'pool-redirects.json').read_text())[deb.name]
                self.assertIn('/os-new/',redirect['url']);self.assertEqual(result['new_assets'],[str(deb)])
                # A second staging of identical bytes can safely reuse that URL.
                result=stage.stage(social,repo,'os-next')
                self.assertEqual(result['new_assets'],[])
