from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("cc"), "Linux C compiler")
class BootHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="lynux-handoff-")
        cls.binary = Path(cls.build.name) / "ventoy-find"
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(ROOT / "boot/ventoy-find.c"), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def run_fixture(self, path, corrupt=False, wrong_disk=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "sys/disk0/disk0p1").mkdir(parents=True)
            (root / "sys/disk0/disk0p1/partition").write_text("1\n")
            (root / "dev").mkdir()
            guid = bytes(range(16))
            sector = bytearray(512)
            sector[384:400] = bytes(16) if wrong_disk else guid
            (root / "dev/disk0").write_bytes(sector)
            record = bytearray(512)
            record[:16] = bytes.fromhex("20207777772e76656e746f792e6e6574")
            record[17:33] = guid
            record[41] = 1
            encoded = path.encode()
            record[45:45 + len(encoded)] = encoded
            record[16] = (-sum(record)) % 256
            if corrupt:
                record[30] ^= 1
            (root / "param").write_bytes(bytes([7, 0, 0, 0]) + record)
            result = subprocess.run([self.binary, root / "param", root / "sys", root / "dev"],
                                    capture_output=True, text=True)
            return result, str(root / "dev/disk0p1")

    def test_space_unicode_and_shell_characters_remain_data(self):
        path = "/ISO/中文 $(not-a-command).iso"
        result, device = self.run_fixture(path)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [device, path])

    def test_invalid_checksum_and_wrong_disk_are_rejected(self):
        self.assertNotEqual(self.run_fixture("/live.iso", corrupt=True)[0].returncode, 0)
        self.assertNotEqual(self.run_fixture("/live.iso", wrong_disk=True)[0].returncode, 0)

    def test_control_characters_and_parent_traversal_are_rejected(self):
        for path in ("/ISO/bad\nname.iso", "/ISO/../secret.iso", "/ISO/.."):
            self.assertNotEqual(self.run_fixture(path)[0].returncode, 0)
