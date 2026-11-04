#!/usr/bin/env python3
"""Validate SquashFS support from the target ARM kernel's embedded configuration."""
import argparse
from pathlib import Path
import zlib


def check(kernel, compression):
    payload = kernel.read_bytes()
    marker = b"IKCFG_ST"
    offset = payload.find(marker + b"\x1f\x8b\x08")
    if offset < 0:
        raise RuntimeError("Target ARM kernel has no readable embedded config; review SquashFS support")
    config = zlib.decompress(payload[offset + len(marker):], wbits=31).decode()
    option = {"xz": "XZ", "zstd": "ZSTD", "gzip": "ZLIB"}[compression]
    if f"CONFIG_SQUASHFS_{option}=y" not in config.splitlines():
        raise RuntimeError(f"Target kernel does not support SquashFS {compression}")
    print(f"Target kernel confirms CONFIG_SQUASHFS_{option}=y", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel", type=Path)
    parser.add_argument("compression", choices=("xz", "zstd", "gzip"))
    check(**vars(parser.parse_args()))
