#!/usr/bin/env python3
"""Build a disposable Ventoy USB file and boot it with Secure Boot disabled."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import shutil
import sys
import re
import os
import signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from download import download  # noqa: E402

from image_matrix import firmware
from qemu_boot import boot, sha


def ventoy(iso, arch, report):
    # Public git refs avoid GitHub's unauthenticated REST API rate limit on shared runners.
    refs = subprocess.check_output(["git", "ls-remote", "--tags", "https://github.com/ventoy/Ventoy.git"], text=True)
    versions = [tuple(map(int, m.groups())) for m in re.finditer(r"refs/tags/v(\d+)\.(\d+)\.(\d+)(?:\^\{\})?\s*$", refs, re.M)]
    version = ".".join(map(str, max(versions)))
    url = f"https://github.com/ventoy/Ventoy/releases/download/v{version}/ventoy-{version}-linux.tar.gz"
    with tempfile.TemporaryDirectory(prefix="lynux-ventoy-") as folder:
        temp = Path(folder)
        archive = temp / "ventoy.tar.gz"
        download(url, archive)
        subprocess.run(["bsdtar", "-xf", str(archive), "-C", str(temp)], check=True)
        tool = next(temp.glob("ventoy-*/Ventoy2Disk.sh"))
        disk = temp / "ventoy.img"
        with disk.open("wb") as stream:
            stream.truncate(((iso.stat().st_size // (1024 ** 3)) + 3) * 1024 ** 3)
        loop = subprocess.check_output(["losetup", "--find", "--show", "--partscan", str(disk)], text=True).strip()
        mount = temp / "data"
        mount.mkdir()
        mounted = False
        try:
            # The only device passed to the installer was allocated from our newly created file.
            installer = subprocess.Popen(["bash", str(tool), "-I", "-g", loop], cwd=tool.parent,
                                         stdin=subprocess.PIPE, text=True, start_new_session=True)
            try:
                # Ventoy includes its own udev-less mknod fallback; don't race its partition table edits.
                installer.communicate("y\ny\n", timeout=180)
                if installer.returncode:
                    raise RuntimeError(f"Ventoy installer exited {installer.returncode}")
            finally:
                if installer.poll() is None:
                    os.killpg(installer.pid, signal.SIGTERM)
                    try:
                        installer.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(installer.pid, signal.SIGKILL)
                        installer.wait()
            subprocess.run(["partprobe", loop], check=True)
            subprocess.run(["udevadm", "settle"], check=True)
            subprocess.run(["mount", loop + "p1", str(mount)], check=True)
            mounted = True
            relative_iso = Path("ISO images") / "系统" / iso.name
            (mount / relative_iso).parent.mkdir(parents=True)
            shutil.copy2(iso, mount / relative_iso)
            (mount / "ventoy").mkdir()
            (mount / "ventoy/ventoy.json").write_text(json.dumps({"control": [
                {"VTOY_MENU_TIMEOUT": "3"}, {"VTOY_SECONDARY_TIMEOUT": "3"}]}))
            subprocess.run(["sync"], check=True)
        finally:
            if mounted:
                subprocess.run(["umount", str(mount)], check=True)
            subprocess.run(["losetup", "-d", loop], check=True)
        code, variables = firmware(arch, secure=False)
        result = boot(disk, arch, "uefi", "usb", code, variables, report=report)
        result.update({"iso_sha256": sha(iso), "iso_path": "/" + relative_iso.as_posix(),
                       "ventoy_version": version, "ventoy_sha256": sha(archive)})
        report.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--report", type=Path, required=True)
    ventoy(**vars(parser.parse_args()))
