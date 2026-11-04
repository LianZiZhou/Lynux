import json
from pathlib import Path
import tempfile
import unittest

from image_matrix import firmware


class FirmwareTests(unittest.TestCase):
    def test_excludes_microvm_and_mixed_ia32_and_selects_requested_security(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for filename in ("code.fd", "secure.fd", "vars.fd"):
                (root / filename).touch()
            normal = {"features": ["amd-sev"], "targets": [{"architecture": "x86_64"}],
                      "mapping": {"device": "flash", "executable": {"filename": str(root / "code.fd")},
                                  "nvram-template": {"filename": str(root / "vars.fd")}}}
            (root / "00-microvm.json").write_text(json.dumps({"features": [],
                "targets": [{"architecture": "x86_64"}], "mapping": {"device": "memory", "filename": "bogus"}}))
            (root / "01-ia32.json").write_text(json.dumps(normal))
            (root / "50-normal.json").write_text(json.dumps(normal))
            secure = json.loads(json.dumps(normal))
            secure["features"].append("secure-boot")
            secure["mapping"]["executable"]["filename"] = str(root / "secure.fd")
            (root / "40-secure.json").write_text(json.dumps(secure))
            self.assertEqual(firmware("x86_64", False, [root])[0], root / "code.fd")
            self.assertEqual(firmware("x86_64", True, [root])[0], root / "secure.fd")
            with self.assertRaises(RuntimeError):
                firmware("aarch64", True, [root])
