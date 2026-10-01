"""Exercise the real Festival installer and Camp dispatcher; run only in Docker."""

import functools
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import tarfile
import threading
from pathlib import Path

ROOT = Path("/fixture")
ROOT.mkdir()
profile = ROOT / "profile"
profile.mkdir()
managed = profile / "installer/bin"
# Python drives the test but is deliberately unavailable to the installed plugin.
# Debian's git and its helpers remain available. No source checkout is in this image.
env = {
    **os.environ, "HOME": str(profile), "XDG_CONFIG_HOME": str(profile / ".config"),
    "OBEY_INSTALLER_HOME": str(profile / "installer"),
    "PATH": f"{managed}:/tools:/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Example Developer", "GIT_COMMITTER_NAME": "Example Developer",
    "GIT_AUTHOR_EMAIL": "developer@example.com", "GIT_COMMITTER_EMAIL": "developer@example.com",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}
for name in ("python", "python3", "scc", "uv"):
    assert shutil.which(name, path=env["PATH"]) is None, f"test must not expose {name}"


def run(*args: str, cwd: Path = ROOT, expected: int = 0, overrides=None) -> str:
    result = subprocess.run(args, check=False, cwd=cwd, env={**env, **(overrides or {})},
                            text=True, capture_output=True, timeout=120)
    assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
    return result.stdout


def commit(path: Path) -> None:
    run("git", "add", ".", cwd=path)
    run("git", "commit", "-qm", "Fixture", cwd=path)


archive = next(Path("/artifacts").glob("*.tar.gz"))
checksum = archive.with_suffix(".gz.sha256").read_text().split()[0]
assert hashlib.sha256(archive.read_bytes()).hexdigest() == checksum
with tarfile.open(archive) as tar:
    info = json.load(tar.extractfile("assets/build-info.json"))
    assert tar.getmember("camp-leverage-all").mode & 0o111
    assert tar.getmember("assets/licenses/Python-LICENSE.txt").size > 0
version = info["version"]

# Use the same git-tag/checksums release resolver as the official marketplace.
release_repo = ROOT / "release"
release_repo.mkdir()
run("git", "init", "-qb", "main", cwd=release_repo)
(release_repo / "README.md").write_text("Local release fixture\n")
commit(release_repo)
run("git", "tag", f"v{version}", cwd=release_repo)
Path("/artifacts/checksums.txt").write_text(f"{checksum}  {archive.name}\n")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory="/artifacts")
server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}"
market = ROOT / "marketplace"
market.mkdir()
run("git", "init", "-qb", "main", cwd=market)
(market / "obey-marketplace.json").write_text(json.dumps({
    "id": "fixture/plugins", "name": "Release fixture", "schema_version": "1",
    "packages": [{
        "id": "fixture/camp-leverage-all", "display_name": "Camp Leverage All",
        "class": "plugin", "host_runtimes": ["camp-cli"], "channels": ["stable"],
        "targets": [{"package": "obedience-corp/festival", "runtime": "camp-cli"}],
        "release_source": {
            "type": "git", "repo": str(release_repo),
            "asset_url": url + "/camp-leverage-all-{version}-{os}-{arch}.tar.gz",
            "checksums_url": url + "/checksums.txt",
        },
    }],
}))
commit(market)
run("festival", "marketplace", "add", str(market), "--name", "fixture")
# The unsigned local fixture requires explicit opt-in; public instructions do not.
run("festival", "install", "camp-leverage-all", "--allow-unverified", "--json")
installed = managed / "camp-leverage-all"
assert installed.is_file()
assert run("camp", "leverage-all", "--version").strip() == f"camp leverage-all {version}"
assert (profile / ".obey/plugins/camp-leverage-all/licenses/Python-LICENSE.txt").is_file()
assert "leverage-all" in run("camp", "plugins")

run("git", "config", "--global", "user.email", "developer@example.com")
run("git", "config", "--global", "user.name", "Example Developer")
# Real registered Camps, with distinct checkouts of the same origin.
for name in ("studio", "client"):
    camp = ROOT / name
    run("camp", "init", str(camp), "--name", name, "--no-git",
        "--description", "Isolated release fixture", "--mission", "Verify plugin installation")
    project = camp / "projects/shared"
    project.mkdir()
    run("git", "init", "-qb", "main", cwd=project)
    (project / "app.py").write_text("def greeting(name):\n    return 'Hello ' + name\n")
    commit(project)
    run("git", "remote", "add", "origin", "https://github.com/example/shared.git", cwd=project)
report = json.loads(run("camp", "leverage-all", "--json"))
assert report["complete"], report
assert report["camp_count"] == 2, report
assert report["unique_repository_count"] == 1, report
assert report["repositories"][0]["camps"] == ["client", "studio"], report
assert report["summary"]["full_leverage"] > 0, report
assert report["summary"]["estimated_cost_usd"] > 0, report
assert report["summary"]["estimated_cost_usd"] == report["repositories"][0]["estimated_cost_usd"]
assert report["timeline"]["periods"][-1]["cumulative_estimated_cost_usd"] == report["summary"]["estimated_cost_usd"]
text = run("camp", "leverage-all")
assert "estimated COCOMO cost (USD)" in text
assert "CUM. USD" in text
assert "COST USD" in text.split("REPOSITORIES", 1)[1]
assert report["timeline"]["periods"][-1]["cumulative_leverage"] == report["summary"]["full_leverage"]
# Camp dispatch sets CAMP_ROOT; scanning all Camps must still work from inside one.
inside = json.loads(run("camp", "leverage-all", "--json", cwd=ROOT / "studio"))
assert inside["summary"] == report["summary"]
assert inside["camp_count"] == 2
(ROOT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print("PASS: real Festival install, Camp discovery, bundled runtime and scc, dedup and timeline")

# External prerequisites must still produce a useful error, not a frozen-runtime traceback.
isolated_path = ROOT / "no-tools"
isolated_path.mkdir()
result = subprocess.run(check=False, args=[str(installed), "--json"], cwd=ROOT,
                        env={**env, "PATH": str(isolated_path)}, capture_output=True, text=True)
assert result.returncode == 2 and "camp" in result.stderr and "git" in result.stderr, result
assert "scc" not in result.stderr, result.stderr

run("festival", "uninstall", "camp-leverage-all", "--json")
assert not installed.exists()
assert not (profile / ".obey/plugins/camp-leverage-all").exists()
# A corrupt artifact must never leave an executable installed.
with archive.open("ab") as output:
    output.write(b"corrupted")
result = subprocess.run(check=False, args=["festival", "install", "camp-leverage-all", "--allow-unverified", "--json"],
                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
assert result.returncode != 0, result
assert json.loads(result.stdout)["error"]["code"] == "E_ARTIFACT_SHA256", result
assert not installed.exists()
print("PASS: missing prerequisites, uninstall cleanup, checksum rejection")
server.shutdown()
