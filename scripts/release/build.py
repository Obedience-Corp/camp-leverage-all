"""Build a Festival-compatible archive on the target OS and architecture."""

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def main() -> None:
    os.chdir(ROOT)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    system = {"Linux": "linux", "Darwin": "macOS"}[platform.system()]
    arch = {"x86_64": "x86_64", "AMD64": "x86_64", "arm64": "arm64",
            "aarch64": "arm64"}[platform.machine()]
    if (os.environ.get("GITHUB_REF_TYPE") == "tag"
            and os.environ["GITHUB_REF_NAME"] != f"v{version}"):
        raise SystemExit("release tag must match pyproject.toml version")
    inputs = ROOT / "build/release-input"
    helper = inputs / "bin/scc"
    if not helper.is_file() or not (inputs / "licenses/scc-dependencies.csv").is_file():
        raise SystemExit("run bash scripts/release/build-scc.sh first")
    package = ROOT / "build/release-package"
    if package.exists():
        shutil.rmtree(package)
    licenses = package / "assets/licenses"
    shutil.copytree(inputs / "licenses", licenses)
    shutil.copyfile(Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
                    licenses / "Python-LICENSE.txt")
    pyinstaller = importlib.metadata.distribution("pyinstaller")
    for notice in pyinstaller.files or []:
        if notice.name == "COPYING.txt":
            shutil.copyfile(pyinstaller.locate_file(notice), licenses / "PyInstaller-COPYING.txt")
    # Retain distribution notices for shared libraries collected by PyInstaller.
    if system == "linux":
        docs = Path("/usr/share/doc")
        for notice in docs.glob("*/copyright"):
            shutil.copyfile(notice, licenses / f"debian-{notice.parent.name}-copyright")
    else:
        # macOS release builds use Homebrew Python and its dependency closure.
        formulae = ["python@3.11", *run("brew", "deps", "python@3.11").splitlines()]
        for formula in formulae:
            prefix = Path(run("brew", "--prefix", formula)).resolve()
            for notice in prefix.rglob("*"):
                if notice.is_file() and notice.name.upper().startswith(("LICENSE", "COPYING")):
                    target = licenses / "homebrew" / formula / notice.relative_to(prefix)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(notice, target)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
        "--name", "camp-leverage-all", "--distpath", str(package),
        "--workpath", str(ROOT / "build/pyinstaller"), "--specpath", str(ROOT / "build"),
        "--add-binary", f"{helper}:helpers", "camp_leverage_all.py",
    ], check=True)
    binary_version = run(str(package / "camp-leverage-all"), "--version")
    if binary_version != f"camp leverage-all {version}":
        raise SystemExit(f"binary version mismatch: {binary_version}")
    for name in ("LICENSE", "NOTICE", "README.md"):
        shutil.copyfile(ROOT / name, package / name)
    (package / "assets/build-info.json").write_text(json.dumps({
        "version": version, "os": system, "arch": arch,
        "python": platform.python_version(), "scc": run(str(helper), "--version"),
        "pyinstaller": run(sys.executable, "-m", "PyInstaller", "--version"),
        "commit": os.environ.get("GITHUB_SHA", "local"),
    }, indent=2) + "\n")
    output = ROOT / "dist/release"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"camp-leverage-all-{version}-{system}-{arch}.tar.gz"
    with tarfile.open(archive, "w:gz", dereference=True) as tar:
        for item in sorted(package.iterdir()):
            tar.add(item, arcname=item.name)
    digest = hashlib.file_digest(archive.open("rb"), "sha256").hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
    print(f"Built {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
