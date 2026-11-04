import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import download  # noqa: E402

spec = importlib.util.spec_from_file_location("install_harnesses", ROOT / "scripts/install-harnesses.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class DownloadTests(unittest.TestCase):
    def test_aria2_multiconnection_and_tls_defaults(self):
        args = download.options()
        self.assertIn("--max-connection-per-server=16", args)
        self.assertIn("--split=16", args)
        self.assertIn("--max-concurrent-downloads=8", args)
        self.assertIn("--check-certificate=true", args)
        self.assertIn("--auto-file-renaming=false", args)

    def test_metadata_never_resumes_a_stale_response(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "meta.json"
            with patch.object(download.subprocess, "run") as execute:
                download.download("https://example.test/latest", path, fresh=True)
            self.assertIn("--continue=false", execute.call_args.args[0])

    def test_corrupt_transfer_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binary"
            path.write_bytes(b"corrupt")
            expected = "sha-256=" + hashlib.sha256(b"correct").hexdigest()
            with patch.object(download.subprocess, "run"):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    download.download("https://example.test/binary", path, expected)

    def test_verified_cache_does_not_contact_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binary"
            path.write_bytes(b"correct")
            expected = "sha-256=" + hashlib.sha256(b"correct").hexdigest()
            with patch.object(download.subprocess, "run") as execute:
                download.download_many([("https://example.test/binary", path, expected)])
                execute.assert_not_called()

    def test_aria_input_injection_and_http_are_rejected(self):
        for url in ("http://example.test/x", "https://example.test/x\n  out=/etc/passwd"):
            with self.assertRaises(ValueError):
                download.validate(url, Path("asset"))

    def test_npm_platform_filter_includes_only_compatible_artifacts(self):
        self.assertTrue(installer.supports(["linux"], "linux"))
        self.assertFalse(installer.supports(["!linux"], "linux"))
        self.assertFalse(installer.supports(["arm64"], "x64"))
        self.assertTrue(installer.supports([], "x64"))
