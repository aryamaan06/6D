"""HTTP qualification and explicit export, without external service access."""
from dataclasses import asdict
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from sixd.providers import LiveConfig
from sixd.workspace_server import create_server
from test_workspace_ai_api import offline_factory, KEY


class QualityAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / 'work')
        folder = Path(cls.temp.name)
        config = LiveConfig('https://api.tokenfactory.nebius.com/v1/', 'nvidia/nemotron-3-super-120b-a12b',
            'quality-http-offline', 29.5, .3, .9, 2048, 45, 'native_no_thinking', 'forced_action_v1')
        (folder / 'token-factory.json').write_text(json.dumps({**asdict(config), 'account_verified': True,
            'model_license_reviewed': True, 'spend_approved': True}), encoding='utf-8')
        cls.uploads = []
        def upload(endpoint, headers, body):
            cls.uploads.append(body)
            return {'status': 201}
        cls.server = create_server(port=0, db_path=folder / 'workspace.sqlite3',
            provider_factory=offline_factory, observability_transport=upload)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.server.store.ensure_default()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)
        cls.temp.cleanup()

    def request(self, path, body=None, origin=None):
        c = HTTPConnection('127.0.0.1', self.server.server_port, timeout=20)
        try:
            headers = {'Content-Type': 'application/json'}
            if origin:
                headers['Origin'] = origin
            c.request('GET' if body is None else 'POST', path, body=None if body is None else json.dumps(body), headers=headers)
            response = c.getresponse()
            data = response.read()
            return response.status, json.loads(data) if 'json' in response.getheader('Content-Type', '') else data
        finally:
            c.close()

    def test_01_status_assets_invalid_authorization_no_spend(self):
        code, value = self.request('/api/ai-quality/status')
        self.assertEqual(code, 200)
        self.assertEqual(value['schema'], 'sixd.ai-quality-status.v1')
        self.assertIsNone(value['qualification']['latest'])
        self.assertFalse(value['observability']['key_present'])
        for path in ('/ai-quality.js', '/ai-quality.css'):
            self.assertEqual(self.request(path)[0], 200)
        self.assertEqual(self.request('/api/ai-quality/start', {'allow_spend': True, 'allowance_usd': .81})[0], 400)
        self.assertEqual(self.request('/api/observability/connect', {'api_key': KEY, 'region': 'https://example.org', 'workspace_id': None})[0], 400)
        self.assertEqual(self.request('/api/ai-quality/start', {'allow_spend': True, 'allowance_usd': .8}, 'https://example.org')[0], 403)
        self.assertEqual(self.uploads, [])

    def test_02_explicit_qualification_preview_and_one_export(self):
        self.assertEqual(self.request('/api/ai/connect', {'api_key': KEY})[0], 200)
        original = self.server.store.get(self.server.store.ensure_default(), 1)
        code, queued = self.request('/api/ai-quality/start', {'allow_spend': True, 'allowance_usd': .8})
        self.assertEqual(code, 200, queued)
        identity = queued['qualification_id']
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            code, record = self.request('/api/ai-quality/runs/' + identity)
            if record['state'] not in ('queued', 'running') and self.server.ai._active is None:
                break
            time.sleep(.02)
        self.assertEqual(record['state'], 'completed', record.get('error'))
        self.assertEqual(record['report']['mode'], 'offline_harness_validation')
        self.assertEqual(self.server.store.get(original['project_id'], 1), original)
        self.assertNotIn(KEY, json.dumps(record))
        code, connection = self.request('/api/observability/connect', {'api_key': 'synthetic-langsmith-http-only', 'region': 'us', 'workspace_id': None})
        self.assertEqual(code, 200, connection)
        code, preview = self.request('/api/observability/preview', {'qualification_id': identity})
        self.assertEqual(code, 200, preview)
        self.assertEqual(self.uploads, [])
        self.assertNotIn('summary', json.dumps(preview['payload']))
        code, receipt = self.request('/api/observability/export', {'qualification_id': identity, 'preview_digest': preview['preview_digest'], 'allow_upload': True})
        self.assertEqual(code, 200, receipt)
        self.assertEqual(receipt['state'], 'accepted_by_api')
        self.assertEqual(len(self.uploads), 1)
        self.assertEqual(self.request('/api/observability/export', {'qualification_id': identity,
            'preview_digest': preview['preview_digest'], 'allow_upload': True})[0], 409)
        self.assertEqual(len(self.uploads), 1)


if __name__ == '__main__':
    unittest.main()
