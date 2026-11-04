import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build  # noqa: E402


class BuildTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Linux profile file modes and symlinks")
    def test_profile_replaces_releng_users_and_preserves_boot_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            template = temp / "template"
            (template / "airootfs/etc").mkdir(parents=True)
            (template / "airootfs/etc/resolv.conf").symlink_to("/missing/target")
            (template / "airootfs/etc/passwd").write_text("obsolete-user")
            lock = temp / "lock"
            lock.mkdir()
            (lock / "manifest.json").write_text("{}")
            executable = temp / "mkarchiso"
            executable.write_text("_make_bootmode_uefi.systemd-boot() {}")
            with patch.object(build.shutil, "which", return_value=str(executable)):
                meta = build.prepare_profile("x86_64", "2026.11.03.test", temp / "profile", lock, template=template)
            profile = temp / "profile"
            self.assertFalse((profile / "airootfs/etc/passwd").exists())
            self.assertTrue((profile / "airootfs/usr/local/bin/lynux-state").stat().st_mode & 0o111)
            permissions = (profile / "profiledef.sh").read_text()
            for entry in ("lynux-state", "lynux-iso", "lynux-harness", "lynux-welcome", "lynux-browser"):
                self.assertIn(f"['/usr/local/bin/{entry}']='0:0:755'", permissions)
            self.assertIn("['/usr/local/lib/lynux/test-mode']='0:0:755'", permissions)
            self.assertIn("archisolabel=" + meta["label"], (profile / "efiboot/loader/entries/lynux.conf").read_text())
            self.assertNotIn("lynux.test=1", meta["cmdline"])
            self.assertIn("pyside6", (profile / "packages.x86_64").read_text())

    def test_both_architectures_keep_required_desktop_and_harness_runtime(self):
        for arch in ("x86_64", "aarch64"):
            self.assertTrue({"plasma-desktop", "nodejs", "pyside6", "cryptsetup", "fcitx5-mozc"}
                            .issubset(build.packages(arch)))
