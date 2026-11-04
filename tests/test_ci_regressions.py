import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import seal  # noqa: E402

spec = importlib.util.spec_from_file_location("prefetch_packages", ROOT / "scripts/prefetch-packages.py")
prefetch_packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prefetch_packages)
qemu_spec = importlib.util.spec_from_file_location("check_qemu", ROOT / "scripts/check-qemu.py")
check_qemu = importlib.util.module_from_spec(qemu_spec)
qemu_spec.loader.exec_module(check_qemu)


class CIRegressions(unittest.TestCase):
    def test_device_preflight_rejects_emulator_crash_before_image_build(self):
        with patch.object(check_qemu.subprocess, "Popen") as launch:
            process = launch.return_value
            process.communicate.return_value = ("", None)
            process.poll.return_value = -11
            process.returncode = -11
            with self.assertRaisesRegex(RuntimeError, "exited -11"):
                check_qemu.check("x86_64")

    def test_device_preflight_cleans_up_paused_emulator(self):
        with patch.object(check_qemu.subprocess, "Popen") as launch, patch("builtins.print"):
            process = launch.return_value
            process.communicate.side_effect = [subprocess.TimeoutExpired([], 2), ("", None)]
            process.poll.return_value = None
            check_qemu.check("aarch64")
            process.terminate.assert_called_once()
            self.assertIn("virtio-gpu-pci", launch.call_args.args[0])

    def test_builder_prefetch_skips_an_already_installed_set(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(prefetch_packages.subprocess, "check_output", side_effect=[directory + "\n", ""]) as query, \
                    patch.object(prefetch_packages.subprocess, "run") as refresh, \
                    patch.object(prefetch_packages, "download_many") as downloads:
                prefetch_packages.prefetch(Path(directory) / "pacman.conf", ["python"], installed=True)
            self.assertIn("--needed", query.call_args.args[0])
            self.assertNotIn("--dbpath", query.call_args.args[0])
            refresh.assert_not_called()
            downloads.assert_not_called()

    def test_prefetch_uses_profile_cache_instead_of_host_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "profile.conf"
            target_cache = root / "profile-cache"
            digest = "a" * 64

            def query(args, **kwargs):
                if args[0] == "pacman-conf":
                    self.assertEqual(args, ["pacman-conf", "--config", str(config), "CacheDir"])
                    return str(target_cache) + "\n"
                return f"{digest} https://example.test/package.pkg.tar.xz\n"

            with patch.object(prefetch_packages.subprocess, "check_output", side_effect=query), \
                    patch.object(prefetch_packages.subprocess, "run"), \
                    patch.object(prefetch_packages, "download_many") as downloads:
                prefetch_packages.prefetch(config, ["base"])
            self.assertEqual(downloads.call_args.args[0][0][1], target_cache / "package.pkg.tar.xz")

    @unittest.skipIf(os.name == "nt", "POSIX certificate permissions")
    def test_public_certificate_does_not_inherit_private_input_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination = Path(directory) / "input.crt", Path(directory) / "public.crt"
            source.write_bytes(b"public certificate")
            source.chmod(0o600)
            seal.copy_public_certificate(source, destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o644)
            self.assertEqual(source.stat().st_mode & 0o777, 0o600)

    @unittest.skipIf(os.name == "nt", "Bash runner")
    def test_stage_logger_preserves_command_failure_and_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(["bash", str(ROOT / "scripts/ci-stage.sh"), "smoke", "bash", "-c",
                                     "echo diagnostic; exit 17"], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 17)
            self.assertIn("diagnostic", (Path(directory) / "out/native-smoke.log").read_text())
