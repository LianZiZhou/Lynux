#!/usr/bin/env python3
"""Fail before image construction if the native QEMU device modules cannot initialize."""
import subprocess
import sys


def check(arch):
    if arch not in ("x86_64", "aarch64"):
        raise ValueError("Unsupported QEMU architecture")
    machine = "q35" if arch == "x86_64" else "virt"
    display = "virtio-vga" if arch == "x86_64" else "virtio-gpu-pci"
    command = [f"qemu-system-{arch}", "-machine", machine, "-accel", "tcg", "-cpu", "max",
               "-m", "128", "-display", "none", "-serial", "none", "-monitor", "none",
               "-nodefaults", "-S", "-device", display]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = process.communicate(timeout=2)
        raise RuntimeError(f"QEMU device initialization exited {process.returncode}: {output}. "
                           "Install the base virtio GPU module and the native VGA/PCI frontend module.")
    except subprocess.TimeoutExpired:
        print(f"QEMU {arch} virtio GPU device initialization passed", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    check(sys.argv[1])
