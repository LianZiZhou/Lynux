import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qemu_boot


class FakeQemu:
    def __init__(self, code):
        self.returncode = code

    def poll(self):
        return self.returncode

    def terminate(self):
        if self.returncode is None:
            self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


class QemuRetryTests(unittest.TestCase):
    def test_kvm_segfault_retries_identical_image_with_tcg_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            iso = root / "test.iso"
            iso.write_bytes(b"unchanged image")
            report = root / "boot.json"
            commands = []

            def launch(cmd, **kwargs):
                commands.append(cmd)
                if len(commands) == 1:
                    return FakeQemu(-11)
                serial = Path(cmd[cmd.index("-serial") + 1].removeprefix("file:"))
                serial.write_text("LYNUX_BOOT_OK\n")
                return FakeQemu(None)

            with patch.object(qemu_boot.subprocess, "Popen", side_effect=launch), \
                    patch.object(qemu_boot, "screenshot"), patch.object(qemu_boot.time, "sleep"), patch("builtins.print"):
                result = qemu_boot.boot(iso, "x86_64", "bios", "cdrom", report=report, acceleration="kvm")
            self.assertTrue(result["passed"])
            self.assertTrue(result["kvm_crash_retry"])
            self.assertEqual(result["acceleration"], "tcg")
            self.assertEqual([cmd[cmd.index("-accel") + 1] for cmd in commands], ["kvm", "tcg"])
            self.assertIn(str(iso), " ".join(commands[0]))
            self.assertIn(str(iso), " ".join(commands[1]))
            original = json.loads((root / "boot-kvm-crash.json").read_text())
            self.assertFalse(original["passed"])
            self.assertEqual(original["qemu_returncode"], -11)
            self.assertTrue(json.loads(report.read_text())["passed"])

    def test_guest_exit_without_success_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            iso = Path(directory) / "test.iso"
            iso.write_bytes(b"bad guest")
            with patch.object(qemu_boot.subprocess, "Popen", return_value=FakeQemu(0)) as launch, \
                    patch.object(qemu_boot, "screenshot"), patch("builtins.print"):
                with self.assertRaisesRegex(RuntimeError, "did not produce"):
                    qemu_boot.boot(iso, "x86_64", "bios", "cdrom", acceleration="kvm")
            launch.assert_called_once()
