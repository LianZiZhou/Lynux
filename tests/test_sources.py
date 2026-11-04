"""Builds download only from official upstream sources over valid HTTPS."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALARM_KEY = "68B3537F39A313B3E574D06777193F152BDBE6A6"


def servers(config):
    found = {}
    section = None
    for line in (ROOT / "config" / config).read_text().splitlines():
        if line.startswith("[") and line != "[options]":
            section = line.strip("[]")
        elif line.startswith("Server = ") and section:
            found.setdefault(section, []).append(line.split(" = ", 1)[1])
    return found


class SourceTests(unittest.TestCase):
    def test_no_third_party_mirrors(self):
        files = [*(ROOT / "config").glob("*.conf"), *(ROOT / "scripts").glob("*.sh"), *(ROOT / "scripts").glob("*.py")]
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"https?://[^\s\"']*\.(cn|edu\.cn)\b|tuna|tsinghua|ustc|aliyun", text), path)

    def test_arch_linux_arm_uses_several_official_https_mirrors(self):
        repos = servers("pacman.aarch64.conf")
        self.assertEqual(set(repos), {"core", "extra", "alarm"})
        for urls in repos.values():
            self.assertGreaterEqual(len(urls), 2)
            for url in urls:
                self.assertRegex(url, r"^https://[a-z0-9.]+\.mirror\.archlinuxarm\.org/\$arch/\$repo$")

    def test_arch_linux_uses_the_official_mirror(self):
        for urls in servers("pacman.x86_64.conf").values():
            self.assertTrue(all(url.startswith("https://geo.mirror.pkgbuild.com/") for url in urls), urls)

    def test_rootfs_signature_is_checked_against_the_pinned_build_key(self):
        script = (ROOT / "scripts/fetch-alarm-rootfs.sh").read_text()
        self.assertIn(f"fingerprint={ALARM_KEY}", script)
        self.assertIn("VALIDSIG $fingerprint", script)
        for name in ("ci-container.sh", "run-builder.sh"):
            self.assertIn("fetch-alarm-rootfs.sh", (ROOT / "scripts" / name).read_text())

    @unittest.skipUnless(shutil.which("gpg"), "gpg reads the pinned key")
    def test_pinned_key_is_the_arch_linux_arm_build_key(self):
        listing = subprocess.run(["gpg", "--show-keys", "--with-colons", str(ROOT / "config/keys/archlinuxarm-build.asc")],
                                 capture_output=True, text=True, check=True).stdout
        primary = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr:"))
        self.assertEqual(primary, ALARM_KEY)
        self.assertIn("Arch Linux ARM Build System", listing)


if __name__ == "__main__":
    unittest.main()
