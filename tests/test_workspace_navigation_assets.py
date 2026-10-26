"""Navigation assets are public static resources, not access to workspace state.

Browser behaviour is exercised by tools/check_navigation_browser.mjs against an
isolated server. These HTTP checks cover the production asset boundary.
"""
from html.parser import HTMLParser
from http.client import HTTPConnection
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sixd.workspace_server import create_server


class _Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.styles = [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.styles.append(attrs["href"])


class WorkspaceNavigationAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        folder = Path(cls.temporary.name)
        def forbidden(*args, **kwargs):
            raise AssertionError("Static navigation assets must not call services")
        cls.server = create_server(port=0, db_path=folder / "workspace.sqlite3",
            ai_local_directory=folder, provider_factory=forbidden,
            research_transport=forbidden, observability_transport=forbidden)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()
        cls.temporary.cleanup()

    def request(self, path):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=20)
        client.request("GET", path)
        response = client.getresponse()
        result = response.status, response.getheader("Content-Type"), response.read()
        client.close()
        return result

    def test_navigation_and_font_assets_are_served_without_project_or_provider_side_effects(self):
        before = self.server.store.list_projects()
        status, mime, body = self.request("/")
        self.assertEqual(status, 200)
        assets = _Assets()
        assets.feed(body.decode("utf-8"))
        self.assertLess(assets.scripts.index("/workspace-navigation.js"), assets.scripts.index("/workspace.js"))
        self.assertLess(assets.scripts.index("/workspace-shell.js"), assets.scripts.index("/workspace.js"))
        self.assertLess(assets.scripts.index("/rocket-assistant.js"), assets.scripts.index("/workspace.js"))
        self.assertLess(assets.scripts.index("/rocket-renderer.js"), assets.scripts.index("/rocket-assistant.js"))
        self.assertLess(assets.scripts.index("/source-targets.js"), assets.scripts.index("/source-library.js"))
        self.assertLess(assets.styles.index("/typography.css"), assets.styles.index("/rocket-assistant.css"))
        self.assertEqual(assets.styles[-1], "/rocket-assistant.css")
        self.assertIn("/navigation.css", assets.styles)
        self.assertTrue(all(path.startswith("/") and not path.startswith("//")
                            for path in assets.scripts + assets.styles))
        for path in ["/workspace-navigation.js", "/workspace-shell.js", "/navigation.css", "/typography.css", "/rocket-renderer.js", "/rocket-assistant.js", "/rocket-assistant.css", "/source-targets.js"]:
            status, mime, body = self.request(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(body, path)
            self.assertIn("javascript" if path.endswith(".js") else "text/css", mime)
        self.assertEqual(self.server.store.list_projects(), before)

    def test_static_allowlist_does_not_expose_repository_or_private_state(self):
        for path in ["/AGENTS.md", "/.local/workspace.sqlite3", "/../AGENTS.md", "/private-navigation.js"]:
            status, _, _ = self.request(path)
            self.assertIn(status, {400, 403, 404}, path)


if __name__ == "__main__":
    unittest.main()
