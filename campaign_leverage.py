#!/usr/bin/env python3
"""Personal COCOMO leverage across Camp campaigns, with repository deduplication."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit


EXCLUDE_DIRS = (
    "node_modules", "vendor", ".venv", "venv", "dist", "build", "target",
    "__pycache__", ".next", ".nuxt", "bower_components", "Pods", ".tox",
    ".eggs", ".mypy_cache", ".pytest_cache", ".cargo", "worktrees",
    ".worktrees", ".camp-worktrees",
)
MIN_AUTHOR_MONTHS = 0.1
SECONDS_PER_MONTH = 30.44 * 24 * 60 * 60
WORKTREE_DIRS = {"worktrees", ".worktrees", ".camp-worktrees"}


class ScanError(Exception):
    """A campaign or repository could not be fully measured."""


def command(*args: str, cwd: Path | None = None, allow_failure: bool = False) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise ScanError(f"{args[0]}: {exc}") from exc
    if result.returncode and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ScanError(f"{' '.join(args[:3])}: {detail}")
    return result.stdout.strip() if not result.returncode else ""


def json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ScanError(f"{path}: {exc}") from exc


def json_command(*args: str, cwd: Path | None = None) -> Any:
    raw = command(*args, cwd=cwd)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScanError(f"{' '.join(args)}: invalid JSON: {exc}") from exc


def normalize_remote(remote: str) -> str | None:
    """Equate scp SSH and URL remotes without leaking credentials."""
    remote = remote.strip()
    if not remote:
        return None
    if remote.startswith(("/", "./", "../")):
        return "local:" + str(Path(remote).expanduser().resolve())
    if "://" in remote:
        parsed = urlsplit(remote)
        host, path = parsed.hostname, parsed.path
    else:
        match = re.fullmatch(r"(?:[^@]+@)?([^:]+):(.+)", remote)
        if not match:
            return None
        host, path = match.groups()
        host = canonical_ssh_host(host)
    if not host or not path:
        return None
    path = path.strip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    return f"remote:{host.lower()}/{path.lower()}" if path else None


@lru_cache(maxsize=128)
def canonical_ssh_host(host: str) -> str:
    """Resolve SSH Host aliases without opening a connection."""
    try:
        config = command("ssh", "-G", host, allow_failure=True)
    except ScanError:
        return host
    for line in config.splitlines():
        key, _, value = line.partition(" ")
        if key.lower() == "hostname" and value.strip():
            return value.strip()
    return host


@dataclass(frozen=True)
class Checkout:
    key: str
    scan_path: Path
    git_root: Path
    campaign: str
    project: str
    standalone: bool
    head_time: int
    weak_identity: bool


def select_checkouts(checkouts: list[Checkout]) -> list[tuple[Checkout, list[Checkout]]]:
    grouped: dict[str, list[Checkout]] = defaultdict(list)
    for checkout in checkouts:
        grouped[checkout.key].append(checkout)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        chosen = sorted(group, key=lambda c: (not c.standalone, -c.head_time, str(c.scan_path)))[0]
        result.append((chosen, group))
    return result


def expand_author_emails(seeds: set[str], author_configs: list[dict[str, Any]]) -> set[str]:
    emails = {email.strip().lower() for email in seeds if email.strip()}
    changed = True
    while changed:
        changed = False
        for cfg in author_configs:
            for group in cfg.get("authors", {}).values():
                if group.get("exclude"):
                    continue
                members = {str(e).strip().lower() for e in group.get("emails", [])}
                if members & emails and not members <= emails:
                    emails.update(members)
                    changed = True
    return emails


def project_entries(root: Path) -> list[dict[str, Any]]:
    discovered = json_command("camp", "project", "list", "--json", cwd=root)
    if not isinstance(discovered, list):
        raise ScanError(f"{root}: camp project list returned a non-list")
    config = json_file(root / ".campaign/leverage/config.json")
    configured = config.get("projects", {})
    if not configured:
        return [item for item in discovered if not WORKTREE_DIRS.intersection(Path(item.get("Path", "")).parts)]
    by_path = {item.get("Path"): item for item in discovered}
    entries = []
    for name, entry in sorted(configured.items()):
        if not entry.get("include"):
            continue
        path = entry.get("path")
        if not path:
            raise ScanError(f"{root}: configured project {name} has no path")
        if WORKTREE_DIRS.intersection(Path(path).parts):
            continue
        item = dict(by_path.get(path, {}))
        item.update(Name=name, Path=path)
        if entry.get("in_monorepo"):
            item["MonorepoRoot"] = entry.get("monorepo_path", "")
        entries.append(item)
    return entries


def stale_absent_project(root: Path, item: dict[str, Any]) -> bool:
    """A configured missing path with no HEAD tree entry has no current code."""
    path = root / item.get("Path", "")
    if path.exists():
        return False
    owner = root / item.get("MonorepoRoot", "")
    if not owner.is_dir():
        return False
    try:
        git_root = Path(command("git", "rev-parse", "--show-toplevel", cwd=owner)).resolve()
        relative = path.resolve().relative_to(git_root)
        tracked = command("git", "ls-tree", "HEAD", "--", str(relative), cwd=git_root)
    except (ScanError, ValueError):
        return False
    return not tracked


def checkout_for_project(root: Path, campaign: str, item: dict[str, Any]) -> Checkout:
    relative = item.get("Path", "")
    declared_path = root / relative
    if not relative or not declared_path.absolute().is_relative_to(root.resolve()) or ".." in Path(relative).parts:
        raise ScanError(f"{campaign}/{item.get('Name')}: invalid project path {relative!r}")
    path = declared_path.resolve()
    if not path.is_relative_to(root.resolve()) and item.get("Source") != "linked":
        raise ScanError(f"{campaign}/{item.get('Name')}: project escapes campaign without a link")
    if not path.is_dir():
        raise ScanError(f"{campaign}/{item.get('Name')}: missing directory {path}")
    top = command("git", "rev-parse", "--show-toplevel", cwd=path)
    git_root = Path(top).resolve()
    if not path.is_relative_to(git_root):
        raise ScanError(f"{campaign}/{item.get('Name')}: Git root does not contain project")

    # A campaign-owned folder is a distinct scan scope in its campaign repo.
    # A monorepo child resolves to its parent repo unless it is a real submodule.
    monorepo_root = item.get("MonorepoRoot", "")
    campaign_owned = git_root == root.resolve() and path != git_root and not monorepo_root
    if item.get("Source") == "submodule" and path != git_root and not monorepo_root:
        raise ScanError(f"{campaign}/{item.get('Name')}: submodule is not initialized: {path}")
    scan_path = path if campaign_owned else git_root
    origin = command("git", "remote", "get-url", "origin", cwd=git_root, allow_failure=True)
    identity = normalize_remote(origin or item.get("URL", ""))
    weak = identity is None
    if identity is None:
        common = command("git", "rev-parse", "--git-common-dir", cwd=git_root)
        identity = "gitdir:" + str((git_root / common).resolve())
    if campaign_owned:
        identity += "::" + str(path.relative_to(git_root))
    head_raw = command("git", "log", "-1", "--format=%ct", cwd=git_root, allow_failure=True)
    return Checkout(
        key=identity, scan_path=scan_path, git_root=git_root, campaign=campaign,
        project=str(item.get("Name", path.name)), standalone=not bool(monorepo_root),
        head_time=int(head_raw) if head_raw.isdigit() else 0, weak_identity=weak,
    )


def author_dates(git_root: Path, emails: set[str]) -> tuple[datetime, datetime] | None:
    raw = command("git", "log", "--all", "--format=%ae%x09%cI", cwd=git_root)
    dates = []
    for line in raw.splitlines():
        email, sep, stamp = line.partition("\t")
        if sep and email.lower() in emails:
            try:
                dates.append(datetime.fromisoformat(stamp))
            except ValueError as exc:
                raise ScanError(f"{git_root}: invalid Git date {stamp!r}") from exc
    return (min(dates), max(dates)) if dates else None


def blame_counts(scan_path: Path) -> Counter[str]:
    raw = subprocess.run(
        ("git", "ls-files", "-z"), cwd=scan_path, capture_output=True, check=False,
    )
    if raw.returncode:
        raise ScanError(f"{scan_path}: git ls-files: {raw.stderr.decode(errors='replace').strip()}")
    files = []
    for entry in raw.stdout.split(b"\0"):
        if not entry:
            continue
        file = os.fsdecode(entry)
        if any(part in EXCLUDE_DIRS for part in Path(file).parts):
            continue
        if not (scan_path / file).is_file():
            continue  # Includes nested Git submodule pointers.

        files.append(file)

    def blame_one(file: str) -> Counter[str]:
        result = subprocess.run(
            ("git", "blame", "--line-porcelain", "--", file), cwd=scan_path,
            capture_output=True, check=False,
        )
        if result.returncode:
            raise ScanError(f"{scan_path / file}: git blame: {result.stderr.decode(errors='replace').strip()}")
        file_counts: Counter[str] = Counter()
        email = ""
        for line in result.stdout.splitlines():
            if line.startswith(b"author-mail "):
                email = line[12:].decode(errors="replace").strip().strip("<>").lower()
            elif line.startswith(b"\t") and email:
                file_counts[email] += 1
        return file_counts

    counts: Counter[str] = Counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        for file_counts in pool.map(blame_one, files):
            counts.update(file_counts)
    return counts


def score_checkout(checkout: Checkout, emails: set[str]) -> dict[str, Any] | None:
    dates = author_dates(checkout.git_root, emails)
    if dates is None:
        return None
    args = ["scc", "--format", "json2", "--cocomo-project-type", "organic"]
    for dirname in EXCLUDE_DIRS:
        args.extend(("--exclude-dir", dirname))
    args.append(str(checkout.scan_path))
    result = json_command(*args)
    people = float(result["estimatedPeople"])
    months = float(result["estimatedScheduleMonths"])
    counts = blame_counts(checkout.scan_path)
    total_lines = sum(counts.values())
    owned_lines = sum(count for email, count in counts.items() if email in emails)
    share = owned_lines / total_lines if total_lines else 0.0
    status = command("git", "status", "--porcelain", "--untracked-files=no", cwd=checkout.git_root)
    return {
        "repository": checkout.key,
        "path": str(checkout.scan_path),
        "estimated_person_months": people * months * share,
        "unscaled_estimated_person_months": people * months,
        "author_share": share,
        "owned_lines": owned_lines,
        "blamed_lines": total_lines,
        "first_commit": dates[0].isoformat(),
        "last_commit": dates[1].isoformat(),
        "dirty": bool(status),
        "weak_identity": checkout.weak_identity,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ScanError("no selected-author commits in the scored repositories")
    first = min(datetime.fromisoformat(row["first_commit"]) for row in rows)
    last = max(datetime.fromisoformat(row["last_commit"]) for row in rows)
    actual = max(MIN_AUTHOR_MONTHS, (last - first).total_seconds() / SECONDS_PER_MONTH)
    estimated = sum(row["estimated_person_months"] for row in rows)
    return {
        "full_leverage": estimated / actual,
        "estimated_person_months": estimated,
        "actual_person_months": actual,
        "first_commit": first.isoformat(),
        "last_commit": last.isoformat(),
    }


def calculate(campaign_filters: list[str], seed_emails: set[str], *, progress: bool = True) -> dict[str, Any]:
    campaigns = json_command("camp", "list", "--format", "json")
    if not isinstance(campaigns, list):
        raise ScanError("camp list returned a non-list")
    selected = [c for c in campaigns if not campaign_filters or c["name"] in campaign_filters or c["id"] in campaign_filters]
    missing = set(campaign_filters) - {c["name"] for c in selected} - {c["id"] for c in selected}
    if missing:
        raise ScanError("unknown campaign: " + ", ".join(sorted(missing)))
    if not selected:
        raise ScanError("no registered campaigns")

    errors: list[str] = []
    warnings: list[str] = []
    checkouts: list[Checkout] = []
    author_configs: list[dict[str, Any]] = []
    for campaign in selected:
        root = Path(campaign["path"]).expanduser().resolve()
        try:
            author_configs.append(json_file(root / ".campaign/leverage/authors.json"))
            for item in project_entries(root):
                try:
                    checkouts.append(checkout_for_project(root, campaign["name"], item))
                except ScanError as exc:
                    if stale_absent_project(root, item):
                        warnings.append(f"{campaign['name']}/{item.get('Name')}: absent from current Git tree; stale project entry")
                    else:
                        errors.append(str(exc))
        except ScanError as exc:
            errors.append(f"{campaign['name']}: {exc}")

    emails = expand_author_emails(seed_emails, author_configs)
    if not emails:
        raise ScanError("no author email; use --author-email or configure git user.email")
    chosen = select_checkouts(checkouts)
    rows = []
    for index, (checkout, group) in enumerate(chosen, 1):
        if progress:
            print(f"Scoring {index}/{len(chosen)}: {checkout.project}", file=sys.stderr)
        try:
            scored = score_checkout(checkout, emails)
        except (ScanError, KeyError, ValueError, TypeError) as exc:
            errors.append(f"{checkout.key}: {exc}")
            continue
        if scored is None:
            continue
        scored["campaigns"] = sorted({c.campaign for c in group})
        scored["checkouts"] = sorted({str(c.scan_path) for c in group})
        rows.append(scored)

    summary = {}
    if rows:
        summary = aggregate(rows)
    else:
        errors.append("no selected-author commits in the scored repositories")
    return {
        "complete": not errors,
        "campaign_count": len(selected),
        "unique_repository_count": len(rows),
        "discovered_repository_count": len(chosen),
        "author_emails": sorted(emails),
        "summary": summary,
        "repositories": rows,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", action="append", default=[], help="exact campaign name or ID (repeatable)")
    parser.add_argument("--author-email", action="append", default=[], help="author email (repeatable)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args()
    seeds = set(args.author_email)
    try:
        if not seeds:
            default = command("git", "config", "user.email", allow_failure=True)
            if default:
                seeds.add(default)
        report = calculate(args.campaign, seeds, progress=not args.json)
    except ScanError as exc:
        print(f"campaign-leverage: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        summary = report["summary"]
        if summary:
            print(f"Full leverage: {summary['full_leverage']:.1f}x")
            print(f"Estimated effort: {summary['estimated_person_months']:.1f} person-months")
            print(f"Actual effort: {summary['actual_person_months']:.1f} person-months")
        print(f"Campaigns: {report['campaign_count']}  Unique scored repos: {report['unique_repository_count']}")
        print("Author emails: " + ", ".join(report["author_emails"]))
        for row in report["repositories"]:
            flags = (" dirty" if row["dirty"] else "") + (" local-identity" if row["weak_identity"] else "")
            print(f"  {row['repository']}  {row['estimated_person_months']:.1f} PM  [{', '.join(row['campaigns'])}]{flags}")
        for error in report["errors"]:
            print("Skipped: " + error, file=sys.stderr)
        for warning in report["warnings"]:
            print("Excluded: " + warning, file=sys.stderr)
        if not report["complete"]:
            print("Incomplete score: some campaigns or repositories could not be measured.", file=sys.stderr)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
