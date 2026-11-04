import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from lynux import common, iso, state  # noqa: E402


class RuntimeTests(unittest.TestCase):
    def test_ventoy_metadata_checksum_and_disk_identity(self):
        blob = bytearray(512)
        blob[:16] = bytes.fromhex("20207777772e76656e746f792e6e6574")
        blob[17:33] = bytes(range(16))
        blob[41:43] = (1).to_bytes(2, "little")
        path = "/ISO/系统.iso".encode()
        blob[45:45 + len(path)] = path
        blob[16] = (-sum(blob)) % 256
        result = state.parse_ventoy_param(blob)
        self.assertEqual(result["partition"], 1)
        self.assertEqual(result["iso_path"], "/ISO/系统.iso")
        blob[45] ^= 1
        self.assertIsNone(state.parse_ventoy_param(blob))

    def test_existing_container_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.luks"
            path.write_bytes(b"valuable data")
            with self.assertRaisesRegex(common.LynuxError, "已存在"):
                state.validate_container(path, creating=True)
            self.assertEqual(path.read_bytes(), b"valuable data")

    @unittest.skipIf(os.name == "nt", "Unix symlinks")
    def test_symlink_container_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            real = Path(folder) / "real"
            real.write_bytes(b"data")
            link = Path(folder) / "link"
            link.symlink_to(real)
            with self.assertRaises(common.LynuxError):
                state.validate_container(link)

    def test_missing_container_does_not_create(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "absent.luks"
            with self.assertRaises(common.LynuxError):
                state.validate_container(path)
            self.assertFalse(path.exists())

    def test_iso_inspection_accepts_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "我的 镜像.iso"
            path.write_bytes(b"image contents")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            stdout = io.StringIO()
            with patch.object(sys, "argv", ["lynux-iso", "inspect", str(path), "--sha256", checksum]):
                with contextlib.redirect_stdout(stdout):
                    iso.main()
            self.assertEqual(json.loads(stdout.getvalue())["sha256"], checksum)
            with patch.object(sys, "argv", ["lynux-iso", "inspect", str(path), "--sha256", "0" * 64]):
                with self.assertRaisesRegex(common.LynuxError, "不匹配"):
                    iso.main()

    def test_state_allowlist_excludes_system_and_caches(self):
        with patch.object(common, "CONFIG", ROOT / "config/harnesses.json"):
            bound = state.bindings("x86_64")
            targets = [target.as_posix() for _, target, _ in bound]
            # Directory mounts permit Claude's atomic rename of .claude.json.
            self.assertIn("/root/.lynux/claude", targets)
            self.assertIn("/workspace", targets)
            self.assertFalse(any(t.startswith(("/etc", "/usr", "/root/.cache")) for t in targets))
            other = state.bindings("aarch64")
            self.assertNotEqual(bound[0][0], other[0][0])
            self.assertEqual(bound[-1][0], other[-1][0])

    def test_wrong_schema_prevents_any_bind_mount(self):
        with tempfile.TemporaryDirectory() as folder:
            mount = Path(folder)
            (mount / "format.json").write_text('{"schema":999}')
            with patch.object(state, "MOUNT", mount), patch.object(state, "run") as execute:
                with self.assertRaisesRegex(common.LynuxError, "未知"):
                    state.mount_bindings()
                execute.assert_not_called()

    def test_readonly_and_fat32_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.luks"
            table = json.dumps({"filesystems": [{"fstype": "vfat", "options": "rw,relatime"}]})
            with patch.object(state, "run", return_value=table):
                with self.assertRaisesRegex(common.LynuxError, "FAT32"):
                    state.check_capacity(path, 8 * state.GIB)
            table = json.dumps({"filesystems": [{"fstype": "ext4", "options": "ro"}]})
            with patch.object(state, "run", return_value=table):
                with self.assertRaisesRegex(common.LynuxError, "只读"):
                    state.check_capacity(path, state.GIB)

    @unittest.skipIf(os.name == "nt", "Linux flock")
    def test_running_harness_prevents_state_switch(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(common, "RUN", Path(folder)):
            with common.session_lock(shared=True):
                with self.assertRaisesRegex(common.LynuxError, "CLI"):
                    with common.session_lock():
                        self.fail("Acquired exclusive lock while harness is running")

    @unittest.skipIf(os.name == "nt", "Unix symlinks")
    def test_persisted_symlink_cannot_redirect_bind_source(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "cli").symlink_to("/etc", target_is_directory=True)
            with self.assertRaises(common.LynuxError):
                state.ensure_safe_tree(base / "cli/passwd", base)
