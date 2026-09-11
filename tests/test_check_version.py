import importlib.util
import io
import json
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "plugins" / "click" / "common" / "scripts" / "check_version.py"
SPEC = importlib.util.spec_from_file_location("check_version", MODULE_PATH)
check_version = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(check_version)


class VersionCheckTests(unittest.TestCase):
    def test_reads_version_from_local_plugin_manifest(self):
        manifest = ROOT / "plugins" / "click" / ".codex-plugin" / "plugin.json"
        expected = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        self.assertEqual(check_version.read_local_version(manifest), expected)

    def test_fetches_version_from_remote_manifest(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self):
                return b'{"version":"1.2.3-rc.1"}'

        with mock.patch.object(check_version.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual(check_version.fetch_latest_version(), "1.2.3-rc.1")

    def test_main_distinguishes_current_outdated_and_failed_checks(self):
        cases = [
            ("1.0.0", "1.0.0", 0),
            ("1.0.0", "1.1.0", 10),
        ]
        for current, latest, expected in cases:
            with self.subTest(current=current, latest=latest), mock.patch.object(
                check_version, "read_local_version", return_value=current
            ), mock.patch.object(check_version, "fetch_latest_version", return_value=latest), mock.patch(
                "sys.stdout", new=io.StringIO()
            ):
                self.assertEqual(check_version.main(), expected)

        with mock.patch.object(
            check_version,
            "read_local_version",
            side_effect=check_version.VersionCheckError("offline"),
        ), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(check_version.main(), 2)
