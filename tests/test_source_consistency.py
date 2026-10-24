"""Canonical checkout checks do not mask bytes or rewrite evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from check_source_consistency import check

class SourceConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'src/sixd').mkdir(parents=True)
        (self.root/'.gitattributes').write_bytes(b'* text=auto eol=lf\n')
        self.source=self.root/'src/sixd/example.py';self.source.write_bytes(b'x = 1\n')
    def test_lf_sources_pass_without_mutation(self):
        before=self.source.read_bytes();r=check(self.root);self.assertTrue(r['passed']);self.assertEqual(r['files_checked'],1)
        self.assertEqual(self.source.read_bytes(),before)
    def test_crlf_is_detected_not_silently_normalized(self):
        self.source.write_bytes(b'x = 1\r\n');r=check(self.root);self.assertFalse(r['passed']);self.assertFalse(r['files'][0]['lf_only'])
        self.assertIn(b'\r',self.source.read_bytes())
    def test_missing_lf_policy_or_missing_sources_fails(self):
        (self.root/'.gitattributes').unlink();self.assertFalse(check(self.root)['passed'])
        self.source.unlink();self.assertFalse(check(self.root)['passed'])
    def test_explicit_unavailable_git_ref_fails_closed(self):
        self.assertFalse(check(self.root,'nonexistent-ref')['passed'])

if __name__=='__main__':unittest.main()
