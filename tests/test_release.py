import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import publish  # noqa: E402
from board import validate  # noqa: E402


def fixture(folder):
    (folder / "lynux.cer").write_bytes(b"fixture-cert")
    (folder / "lynux.crt").write_bytes(b"fixture-cert")
    for arch in ("x86_64", "aarch64"):
        image = folder / f"lynux-test-{arch}-signed.iso"
        image.write_bytes(arch.encode())
        checksum = publish.sha(image)
        (folder / f"{arch}-build.json").write_text(json.dumps({"arch": arch, "signed": True,
            "version": "2026.11.03.1", "iso": image.name, "sha256": checksum, "rootfs_sha256": checksum,
            "certificate_sha256": publish.sha(folder / "lynux.cer")}))
        for media in ("usb", "cdrom"):
            (folder / f"{arch}-secure-{media}.json").write_text(json.dumps({"passed": True, "secure_boot": True,
                                                                         "iso_sha256": checksum}))
        for kind in ("ventoy", "bios-usb", "bios-cdrom"):
            (folder / f"{arch}-{kind}.json").write_text(json.dumps({"passed": True, "iso_sha256": checksum}))
        (folder / f"{arch}-integrity-negative.json").write_text(json.dumps({"passed": True,
            "wrong_certificate_rejected": True, "modified_uki_rejected": True, "baseline_sha256": checksum}))
        (folder / f"{arch}-harness-versions.json").write_text(json.dumps({k: {"version": "1.0.0"}
            for k in ("codex", "claude", "kimi", "dsh", "opencode")}))
        (folder / f"{arch}-provider-smoke.json").write_text(json.dumps({"mock_only": True,
            "rootfs_sha256": checksum, "results": {k: {"passed": True}
                for k in ("codex", "claude", "kimi", "dsh", "opencode")}}))


class ReleaseTests(unittest.TestCase):
    def test_mixed_architecture_certificates_block_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            path = folder / "aarch64-build.json"
            meta = json.loads(path.read_text())
            meta["certificate_sha256"] = "0" * 64
            path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "Certificate"):
                publish.collect(folder)

    def test_changed_signing_key_blocks_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            with patch.dict(publish.os.environ, {"RELEASE_SIGNING_KEY": "test.key"}), \
                 patch.object(publish.subprocess, "check_output", side_effect=[b"public A", b"public B"]):
                with self.assertRaisesRegex(ValueError, "does not match"):
                    publish.publish(folder, "owner/repo", "a" * 40)

    def test_unverified_images_and_operator_files_are_not_release_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            for filename in ("unsigned.iso", "secret.key", "operator-notes.txt"):
                (folder / filename).write_text("not a release artifact")
            files, _ = publish.collect(folder)
            names = {p.name for p in files}
            self.assertTrue(names.isdisjoint({"unsigned.iso", "secret.key", "operator-notes.txt"}))

    def test_failed_model_request_blocks_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            path = folder / "aarch64-provider-smoke.json"
            report = json.loads(path.read_text())
            report["results"]["kimi"]["passed"] = False
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "protocol smoke"):
                publish.collect(folder)
    def test_modified_image_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            next(folder.glob("*.iso")).write_bytes(b"changed after test")
            with self.assertRaisesRegex(ValueError, "digest"):
                publish.collect(folder)

    def test_missing_architecture_blocks_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            (folder / "aarch64-build.json").unlink()
            with self.assertRaises(FileNotFoundError):
                publish.collect(folder)

    def test_harness_version_drift_blocks_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            path = folder / "aarch64-harness-versions.json"
            versions = json.loads(path.read_text())
            versions["codex"]["version"] = "2.0.0"
            path.write_text(json.dumps(versions))
            with self.assertRaisesRegex(ValueError, "versions differ"):
                publish.collect(folder)

    def test_failed_boot_report_blocks_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            (folder / "aarch64-secure-usb.json").write_text('{"passed":false}')
            with self.assertRaisesRegex(ValueError, "evidence"):
                publish.collect(folder)

    def test_upload_failure_never_updates_latest_or_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            fixture(folder)
            sdk = MagicMock()
            client = sdk.client.return_value
            client.upload_file.side_effect = RuntimeError("network down")
            env = {"S3_ENDPOINT": "https://s3.example.test", "S3_BUCKET": "bucket",
                   "DOWNLOAD_BASE_URL": "https://download.example.test", "RELEASE_SIGNING_KEY": "test.key"}
            with patch.dict(sys.modules, {"boto3": sdk}), patch.dict(publish.os.environ, env):
                with patch.object(publish.subprocess, "run") as execute, \
                     patch.object(publish.subprocess, "check_output", return_value=b"fixture-cert"):
                    with self.assertRaisesRegex(RuntimeError, "network down"):
                        publish.publish(folder, "owner/repo", "a" * 40)
                    self.assertFalse(any(call.args[0][0] == "gh" for call in execute.call_args_list))
            self.assertFalse(any(call.kwargs["Key"].endswith("latest.json") for call in client.put_object.call_args_list))

    def test_unfilled_board_template_is_not_a_supported_board(self):
        profile = json.loads((ROOT / "config/boards/template.json").read_text())
        with self.assertRaisesRegex(ValueError, "Pin an exact"):
            validate(profile)
