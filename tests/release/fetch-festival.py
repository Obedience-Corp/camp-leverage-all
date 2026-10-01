"""Fetch a pinned, digest-verified public Festival suite for the container test."""

import hashlib
import io
import platform
import tarfile
import urllib.request
from pathlib import Path

VERSION = "0.3.14"
DIGESTS = {
    "x86_64": "8545548c5dd055f0c8ebea09ade4610c78ddc95fcfffbb2cbae7e13344554df3",
    "aarch64": "f008ee3fef8e52aa7eae7dcd6fc537f4ff80c6883d189f40a248d518fe4a4dcc",
}
arch = {"x86_64": "x86_64", "aarch64": "arm64"}[platform.machine()]
url = (f"https://github.com/Obedience-Corp/festival/releases/download/v{VERSION}/"
       f"festival-{VERSION}-linux-{arch}.tar.gz")
with urllib.request.urlopen(url, timeout=120) as response:
    data = response.read()
assert hashlib.sha256(data).hexdigest() == DIGESTS[platform.machine()], "suite digest mismatch"
destination = Path("/tools")
destination.mkdir()
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    for name in ("camp", "fest", "festival"):
        member = next(m for m in archive.getmembers() if m.name.removeprefix("./") == name)
        assert member.isfile(), name
        (destination / name).write_bytes(archive.extractfile(member).read())
        (destination / name).chmod(0o755)
