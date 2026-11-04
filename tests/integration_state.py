#!/usr/bin/env python3
"""Run only in a disposable privileged Linux container; creates only temporary loop files."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from lynux import common, state


def call(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def main():
    if os.environ.get("LYNUX_DISPOSABLE_TEST") != "1" or os.geteuid() != 0:
        raise RuntimeError("Use a disposable privileged container with LYNUX_DISPOSABLE_TEST=1")
    with tempfile.TemporaryDirectory(prefix="lynux-storage-test-") as folder:
        temp = Path(folder)
        disk = temp / "outer.img"
        with disk.open("wb") as stream:
            stream.truncate(2 * 1024 ** 3)
        call("mkfs.ext4", "-F", "-q", disk)
        external = temp / "external"
        external.mkdir()
        call("mount", "-o", "loop", disk, external)
        runtime = temp / "runtime"
        runtime.mkdir()
        encrypted = runtime / "state"
        container = external / "state.luks"
        target = temp / "workspace"
        target.mkdir()
        (target / "saved.txt").write_text("跨重启工作文件")

        def test_bindings(arch=None):
            return [(encrypted / "workspace", target, "directory")]

        try:
            with patch.object(state, "MOUNT", encrypted), patch.object(state, "RECORD", runtime / "state.json"), \
                 patch.object(state, "bindings", test_bindings):
                state.create(container, 300 * 1024 ** 2, "test-only-password")
                assert (target / "saved.txt").read_text() == "跨重启工作文件"
                (target / "persisted.txt").write_text("inside encrypted volume")
                state.close()
                assert not (target / "saved.txt").exists(), "Imported plaintext leaked after lock"
                assert not (target / "persisted.txt").exists()
                before = common.digest(container)
                try:
                    state.activate(container, "incorrect-password")
                    raise AssertionError("Incorrect password accepted")
                except common.LynuxError:
                    pass
                assert common.digest(container) == before
                state.activate(container, "test-only-password")
                assert (target / "persisted.txt").read_text() == "inside encrypted volume"
                (encrypted / "format.json").write_text('{"schema":999}')
                state.close()
                try:
                    state.activate(container, "test-only-password")
                    raise AssertionError("Unknown format mounted")
                except common.LynuxError:
                    pass
                assert not Path("/dev/mapper/lynux-state").exists()
            print("PASS: LUKS2, bind mounts, wrong password, reopen, schema rejection, cleanup")
        finally:
            for path in (target, encrypted):
                if os.path.ismount(path):
                    call("umount", path)
            if Path("/dev/mapper/lynux-state").exists():
                call("cryptsetup", "close", "lynux-state")
            if os.path.ismount(external):
                call("umount", external)


if __name__ == "__main__":
    main()
