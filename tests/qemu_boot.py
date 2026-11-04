#!/usr/bin/env python3
"""Boot the actual ISO and require an in-guest success marker, never infer success from timeout."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import shlex
import socket
import subprocess
import tempfile
import time


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def screenshot(sockpath, output):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(5)
            client.connect(str(sockpath))
            channel = client.makefile("rwb")
            channel.readline()
            for request in ({"execute": "qmp_capabilities"},
                            {"execute": "screendump", "arguments": {"filename": str(output), "format": "png"}}):
                channel.write(json.dumps(request).encode() + b"\n")
                channel.flush()
                while True:
                    reply = json.loads(channel.readline())
                    if "return" in reply or "error" in reply:
                        break
    except (OSError, ValueError):
        pass  # Diagnostics must not obscure the actual boot error.


def boot(iso, arch, mode, media, firmware=None, variables=None, timeout=600, extra_disk=None,
         expect="LYNUX_BOOT_OK", report=None, secure=False, acceleration=None):
    if mode == "bios" and arch != "x86_64":
        raise ValueError("BIOS is only supported on x86_64")
    if mode == "uefi" and (not firmware or not variables):
        raise ValueError("UEFI tests need matching firmware CODE and VARS files")
    with tempfile.TemporaryDirectory(prefix="lynux-qemu-") as directory:
        temp = Path(directory)
        serial = temp / "serial.log"
        # WSL can expose /dev/kvm without a reliable nested virtualization path.
        default_accel = "kvm" if ("microsoft" not in platform.release().lower()
                                  and Path("/dev/kvm").exists()
                                  and os.access("/dev/kvm", os.R_OK | os.W_OK)) else "tcg"
        accel = acceleration or os.environ.get("LYNUX_QEMU_ACCEL", default_accel)
        if accel not in ("kvm", "tcg"):
            raise ValueError("LYNUX_QEMU_ACCEL must be kvm or tcg")
        machine = "q35" if arch == "x86_64" else "virt"
        if mode == "uefi" and arch == "x86_64":
            machine += ",smm=on"
        cmd = [f"qemu-system-{'x86_64' if arch == 'x86_64' else 'aarch64'}", "-machine", machine,
               "-accel", accel, "-cpu", "host" if accel == "kvm" else ("max" if arch == "x86_64" else "cortex-a72"),
               "-m", "4096", "-smp", "2", "-display", "none", "-serial", f"file:{serial}", "-no-reboot",
               "-device", "virtio-gpu-pci", "-device", "qemu-xhci", "-device", "usb-kbd",
               "-device", "usb-tablet", "-nic", "user,model=virtio-net-pci",
               "-fw_cfg", "name=opt/lynux-test,string=1",
               "-qmp", f"unix:{temp / 'qmp.sock'},server=on,wait=off"]
        if arch == "x86_64":
            # An explicit virtio-gpu does not suppress QEMU's default VGA. A second phantom
            # screen makes screenshots capture the wrong monitor and changes Plasma layout.
            cmd += ["-vga", "none"]
        if mode == "uefi":
            shutil.copy2(variables, temp / "vars.fd")
            cmd += ["-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={firmware}",
                    "-drive", f"if=pflash,format=raw,unit=1,file={temp / 'vars.fd'}"]
            if secure and arch == "x86_64":
                cmd += ["-global", "driver=cfi.pflash01,property=secure,value=on"]
        if media == "usb":
            cmd += ["-drive", f"if=none,id=live,format=raw,readonly=on,file={iso}",
                    "-device", "usb-storage,drive=live,bootindex=1"]
        else:
            cmd += ["-device", "virtio-scsi-pci,id=scsi", "-drive",
                    f"if=none,id=live,format=raw,media=cdrom,readonly=on,file={iso}",
                    "-device", "scsi-cd,drive=live,bootindex=1"]
        if extra_disk:
            cmd += ["-drive", f"if=virtio,format=raw,snapshot=on,file={extra_disk}"]
        started = time.monotonic()
        print("QEMU command: " + shlex.join(cmd), flush=True)
        with (temp / "qemu.log").open("w") as errors:
            process = subprocess.Popen(cmd, stderr=errors, stdout=errors)
            success = False
            try:
                while time.monotonic() - started < timeout:
                    text = serial.read_text(errors="replace") if serial.exists() else ""
                    if expect in text and (not secure or "LYNUX_SECURE_BOOT=1" in text
                                           or expect == "LYNUX_INTEGRITY_FAILED"):
                        success = True
                        if expect == "LYNUX_BOOT_OK":
                            time.sleep(4)  # Allow the compositor to present the first painted welcome frame.
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(2)
            finally:
                if report:
                    report.parent.mkdir(parents=True, exist_ok=True)
                    screenshot(temp / "qmp.sock", report.with_suffix(".png"))
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        result = {"schema": 1, "arch": arch, "mode": mode, "media": media, "passed": success,
                  "iso_sha256": sha(iso), "expected_marker": expect,
                  "secure_boot": secure, "duration_seconds": round(time.monotonic() - started, 1),
                  "acceleration": accel, "qemu_returncode": process.returncode}
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(result, indent=2) + "\n")
            if serial.exists():
                shutil.copy2(serial, report.with_suffix(".serial.log"))
            shutil.copy2(temp / "qemu.log", report.with_suffix(".qemu.log"))
        if not success:
            print(json.dumps(result, indent=2), flush=True)
            for log in (temp / "qemu.log", serial):
                if log.exists():
                    print(f"--- Last 80 lines of {log.name} ---", flush=True)
                    print("\n".join(log.read_text(errors="replace").splitlines()[-80:]), flush=True)
            if process.returncode == -11 and os.environ.get("LYNUX_QEMU_DEBUG") == "1":
                trace = subprocess.run(["timeout", "--kill-after=5", "30", "gdb", "--batch",
                                        "-ex", "set debuginfod enabled off", "-ex", "run",
                                        "-ex", "thread apply all bt", "--args", *cmd],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                print(trace.stdout, flush=True)
                if report:
                    report.with_suffix(f".{accel}.gdb.log").write_text(trace.stdout)
            if accel == "kvm" and process.returncode == -11:
                # Some hosted nested-KVM combinations crash QEMU itself before
                # firmware runs. Preserve the crash evidence and retry the exact
                # same image under software emulation. Guest failures/timeouts
                # are not eligible for this fallback.
                if report:
                    for suffix in (".json", ".serial.log", ".qemu.log", ".png"):
                        source = report.with_suffix(suffix)
                        if source.exists():
                            shutil.copy2(source, report.with_name(report.stem + "-kvm-crash" + suffix))
                print("QEMU crashed with SIGSEGV under KVM; retrying identical boot test with TCG.", flush=True)
                retry = boot(iso, arch, mode, media, firmware, variables, timeout, extra_disk,
                             expect, report, secure, acceleration="tcg")
                retry["kvm_crash_retry"] = True
                if report:
                    report.write_text(json.dumps(retry, indent=2) + "\n")
                return retry
            raise RuntimeError(f"QEMU did not produce {expect!r}; see {report}")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--arch", choices=("x86_64", "aarch64"), required=True)
    parser.add_argument("--mode", choices=("bios", "uefi"), required=True)
    parser.add_argument("--media", choices=("cdrom", "usb"), default="cdrom")
    parser.add_argument("--firmware", type=Path)
    parser.add_argument("--variables", type=Path)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--extra-disk", type=Path)
    parser.add_argument("--expect", default="LYNUX_BOOT_OK")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--secure", action="store_true")
    print(json.dumps(boot(**vars(parser.parse_args())), indent=2))
