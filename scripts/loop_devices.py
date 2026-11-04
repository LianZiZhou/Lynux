"""Create nodes for our own allocated loop partitions when a container has no udev daemon."""
import os
from pathlib import Path
import re
import stat
import time


def ensure_partition_nodes(loop, count=2):
    if not re.fullmatch(r"/dev/loop[0-9]+", loop):
        raise ValueError("Expected a loop device allocated from a disposable image")
    created = []
    for number in range(1, count + 1):
        node = Path(f"{loop}p{number}")
        identity = Path("/sys/class/block") / node.name / "dev"
        if not identity.exists():
            continue
        major, minor = map(int, identity.read_text().strip().split(":"))
        device = os.makedev(major, minor)
        try:
            os.mknod(node, stat.S_IFBLK | 0o600, device)
            created.append(node)
        except FileExistsError:
            current = node.stat()
            if not stat.S_ISBLK(current.st_mode) or current.st_rdev != device:
                raise ValueError(f"Unexpected existing partition node: {node}")
    return created


def wait_partitions(loop, count=2, timeout=10):
    created = []
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        created.extend(ensure_partition_nodes(loop, count))
        if all(Path(f"{loop}p{i}").exists() for i in range(1, count + 1)):
            return created
        time.sleep(0.1)
    raise RuntimeError(f"Partitions did not appear for {loop}")
