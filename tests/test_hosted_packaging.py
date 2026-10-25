"""Static image-boundary checks and optional real Compose configuration parsing.

No image is pulled, built or started by these checks. Docker-free checks do not
establish Linux runtime behavior, certificate provisioning or public reachability.
"""
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HostedPackagingTests(unittest.TestCase):
    def test_image_copies_only_public_runtime_roots_and_runs_nonroot(self):
        text = (ROOT / 'deployment' / 'Dockerfile').read_text(encoding='utf-8')
        copies = [shlex.split(row)[1:] for row in text.splitlines() if row.startswith('COPY ')]
        self.assertEqual(copies, [
            ['src', './src'],
            ['tools/serve_hosted.py', './tools/serve_hosted.py'],
            ['examples', './examples'],
            ['design/vendor/lucide.min.js', './design/vendor/lucide.min.js'],
        ])
        self.assertEqual([row for row in text.splitlines() if row.startswith('USER ')], ['USER 10001:10001'])
        self.assertIn('SIXD_LIVE_AI_ENABLED=0', text)
        self.assertNotIn('pip install', text)
        self.assertNotIn('NEBIUS_API_KEY=', text)
        self.assertNotIn('COPY . ', text)

    def test_build_context_is_allowlisted_and_explicitly_excludes_private_artifacts(self):
        rules = [row.strip() for row in (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
                 if row.strip() and not row.lstrip().startswith('#')]
        self.assertEqual(rules[0], '**')
        self.assertEqual({row for row in rules if row.startswith('!')}, {
            '!src/', '!src/**', '!tools/', '!tools/serve_hosted.py',
            '!examples/', '!examples/**', '!design/', '!design/vendor/',
            '!design/vendor/lucide.min.js', '!deployment/', '!deployment/Dockerfile',
        })
        for suffix in ['**/.env', '**/.env.*', '**/*.dpapi', '**/*.sqlite3', '**/__pycache__', '**/*.pyc']:
            self.assertIn(suffix, rules)
            self.assertGreater(rules.index(suffix), max(i for i, row in enumerate(rules) if row.startswith('!')))
        # No root or private directory is re-included after the default deny.
        for unsafe in ['!.local/', '!work/', '!artifacts/', '!.git/', '!**']:
            self.assertNotIn(unsafe, rules)

    def test_real_compose_configuration_keeps_app_port_and_keys_private(self):
        docker = shutil.which('docker')
        if not docker:
            self.skipTest('Docker CLI unavailable: native Compose parsing remains pending.')
        try:
            version = subprocess.run([docker, 'compose', 'version'],capture_output=True,timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            self.skipTest('Docker Compose CLI unavailable: native parsing remains pending.')
        if version.returncode != 0:
            self.skipTest('Docker Compose plugin unavailable: native parsing remains pending.')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'hosted.env'
            path.write_text('SIXD_DOMAIN=review.example.com\nSIXD_TLS_EMAIL=operator@example.com\nSIXD_SECRET_DIRECTORY=/outside-repository/sixd-secrets\n',encoding='utf-8')
            result = subprocess.run([docker, 'compose', '--env-file', str(path), '-f',
                str(ROOT / 'deployment' / 'compose.yaml'), 'config', '--format', 'json'],
                capture_output=True,timeout=30)
        self.assertEqual(result.returncode, 0, 'Real Compose configuration did not validate.')
        value = json.loads(result.stdout)
        self.assertEqual(set(value['services']), {'app', 'caddy'})
        app, proxy = value['services']['app'], value['services']['caddy']
        self.assertFalse(app.get('ports'))
        self.assertTrue(app['read_only'])
        self.assertEqual(app['user'], '10001:10001')
        self.assertEqual(app['environment']['SIXD_LIVE_AI_ENABLED'], '0')
        self.assertEqual(app['environment']['SIXD_PUBLIC_ORIGIN'], 'https://review.example.com')
        self.assertNotIn('NEBIUS_API_KEY', app['environment'])
        mounts = app['volumes']
        self.assertTrue(any(mount['target'] == '/run/secrets/judge-access-code' and mount['read_only'] for mount in mounts))
        self.assertEqual({int(port['target']) for port in proxy['ports']}, {80, 443})
        caddy = (ROOT / 'deployment' / 'Caddyfile').read_text(encoding='utf-8')
        self.assertIn('reverse_proxy app:8080', caddy)
        self.assertIn('admin off', caddy)


if __name__ == '__main__':
    unittest.main()
