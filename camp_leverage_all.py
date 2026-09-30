#!/usr/bin/env python3
"""Personal COCOMO leverage across Camps, with repository deduplication."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
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
REQUIRED_COMMANDS = ("camp", "git", "scc")
VERSION = "0.2.0"
MINIMUM_SCC_VERSION = (3, 7)
DEFAULT_ANNUAL_WAGE = 56_286
DEFAULT_OVERHEAD = 2.4
DEFAULT_JOBS = max(1, min(8, os.cpu_count() or 1))
COMMAND_TIMEOUT_SECONDS = 15 * 60
TIMELINE_INTERVALS = ("auto", "month", "quarter", "year", "none")
TIMELINE_METHOD = "current-owned-effort-allocated-by-authored-lines/v1"


class ScanError(Exception):
    """A Camp or repository could not be fully measured."""


@dataclass(frozen=True)
class TerminalStyle:
    accent: str = ""
    bold: str = ""
    dim: str = ""
    green: str = ""
    yellow: str = ""
    red: str = ""
    reset: str = ""


def terminal_style(mode: str, stream: Any) -> TerminalStyle:
    enabled = mode == "always" or (
        mode == "auto"
        and "NO_COLOR" not in os.environ
        and bool(getattr(stream, "isatty", lambda: False)())
    )
    if not enabled:
        return TerminalStyle()
    return TerminalStyle(
        accent="\033[38;2;242;114;28m",
        bold="\033[1m",
        dim="\033[2m",
        green="\033[38;2;80;250;123m",
        yellow="\033[38;2;254;188;46m",
        red="\033[38;2;255;95;87m",
        reset="\033[0m",
    )


def shortened_repository(key: str) -> str:
    if key.startswith("remote:"):
        return key.removeprefix("remote:")
    if key.startswith("gitdir:"):
        return "local/" + Path(key.removeprefix("gitdir:")).name
    return key


def clipped(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[: max(1, width - 1)] + "…"


def dollars(value: float, width: int | None = None) -> str:
    text = f"${value:,.0f}"
    if width and len(text) > width:
        return f"${value:.2e}"
    return text


def display_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%b %d, %Y")


def collapsed_labels(labels: list[str]) -> list[str]:
    """Collapse display-name/key variants such as ``demo agent``/``demo-agent``."""
    chosen: dict[str, str] = {}
    for label in labels:
        identity = re.sub(r"[^a-z0-9]", "", label.lower())
        current = chosen.get(identity)
        if current is None or ("-" in label and "-" not in current):
            chosen[identity] = label
    return sorted(chosen.values())


def render_text_report(
    report: dict[str, Any],
    *,
    stream: Any = sys.stdout,
    error_stream: Any = sys.stderr,
    color: str = "auto",
    width: int | None = None,
) -> None:
    """Render a responsive, evidence-rich terminal report."""
    style = terminal_style(color, stream)
    error_style = terminal_style(color, error_stream)
    columns = width or shutil.get_terminal_size(fallback=(96, 30)).columns
    columns = max(48, min(columns, 120))
    content_width = columns - 4
    rule_width = min(content_width, 88)

    def section(label: str) -> None:
        print(file=stream)
        print(f"  {style.bold}{label}{style.reset}", file=stream)

    print(file=stream)
    print(f"  {style.bold}{style.accent}CAMP LEVERAGE ALL{style.reset}", file=stream)
    print(f"  {style.accent}{'━' * rule_width}{style.reset}", file=stream)

    summary = report["summary"]
    if summary:
        print(file=stream)
        print(
            f"  {style.bold}{style.accent}{summary['full_leverage']:.1f}×{style.reset}"
            f"  {style.bold}full leverage{style.reset}",
            file=stream,
        )
        print(
            f"  {summary['estimated_person_months']:.1f} estimated person-months"
            f"  {style.dim}/{style.reset}  {summary['actual_person_months']:.1f} calendar months",
            file=stream,
        )

        print(
            f"  {style.bold}{style.accent}{dollars(summary['estimated_cost_usd'])}"
            f"{style.reset}  estimated COCOMO cost (USD)", file=stream,
        )
        assumptions = report["cost_model"]
        print(
            f"  {style.dim}{dollars(assumptions['annual_wage_usd'])}/year wage"
            f" · {assumptions['overhead_multiplier']:g}× overhead · organic{style.reset}",
            file=stream,
        )

        section("CONTRIBUTION")
        if columns >= 78:
            cell_width = (content_width - 2) // 2
            metrics = (
                (summary["current_owned_lines"], "current lines owned"),
                (summary["lines_added"], "lifetime lines added"),
                (summary["estimated_current_code_lines"], "estimated code LOC"),
                (summary["lines_deleted"], "lifetime lines deleted"),
            )
            for left, right in ((metrics[0], metrics[1]), (metrics[2], metrics[3])):
                left_text = f"{left[0]:,}  {left[1]}"
                right_text = f"{right[0]:,}  {right[1]}"
                print(
                    f"  {left_text:<{cell_width}}  {right_text}",
                    file=stream,
                )
        else:
            for value, label in (
                (summary["current_owned_lines"], "current lines owned"),
                (summary["estimated_current_code_lines"], "estimated code LOC"),
                (summary["lines_added"], "lifetime lines added"),
                (summary["lines_deleted"], "lifetime lines deleted"),
            ):
                print(f"  {value:,}  {label}", file=stream)

        section("SCOPE")
        camp_label = "Camp" if report["camp_count"] == 1 else "Camps"
        repo_label = "repo" if report["unique_repository_count"] == 1 else "repos"
        commit_label = "commit" if summary["commit_count"] == 1 else "commits"
        print(
            f"  {report['camp_count']} {camp_label}"
            f"  {style.dim}·{style.reset}  {report['unique_repository_count']} unique {repo_label}"
            f"  {style.dim}·{style.reset}  {summary['commit_count']:,} matching {commit_label}",
            file=stream,
        )
        print(
            f"  {display_date(summary['first_commit'])}"
            f"  {style.dim}→{style.reset}  {display_date(summary['last_commit'])}",
            file=stream,
        )

    timeline = report.get("timeline")
    if timeline and timeline["periods"]:
        section(f"TIMELINE · {timeline['interval'].upper()}")
        print(
            f"  {style.dim}Current owned effort allocated by authored lines added.{style.reset}",
            file=stream,
        )
        if columns >= 96:
            headings = (
                f"{'PERIOD':<10}  {'ADDED':>11}  {'OUTPUT':>10}"
                f"  {'COST USD':>12}  {'RATE':>9}  {'CUMULATIVE':>12}  {'CUM. USD':>12}"
            )
            print(f"  {style.dim}{headings}{style.reset}", file=stream)
            for period in timeline["periods"]:
                print(
                    f"  {period['label']:<10}  {period['lines_added']:>11,}"
                    f"  {period['estimated_person_months']:>7.1f} PM"
                    f"  {dollars(period['estimated_cost_usd'], 12):>12}"
                    f"  {style.accent}{period['full_leverage']:>8.1f}×{style.reset}"
                    f"  {period['cumulative_leverage']:>11.1f}×"
                    f"  {dollars(period['cumulative_estimated_cost_usd'], 12):>12}",
                    file=stream,
                )
        else:
            for period in timeline["periods"]:
                print(
                    f"  {style.bold}{period['label']}{style.reset}"
                    f"  {period['estimated_person_months']:.1f} PM"
                    f" {style.dim}·{style.reset} {period['full_leverage']:.1f}× period"
                    f" {style.dim}·{style.reset} {period['cumulative_leverage']:.1f}× cumulative",
                    file=stream,
                )
                print(
                    f"    {dollars(period['estimated_cost_usd'], 12)} period"
                    f" · {dollars(period['cumulative_estimated_cost_usd'], 12)} cumulative USD",
                    file=stream,
                )

    if report["repositories"]:
        section("REPOSITORIES")
        if columns >= 78:
            effort_width = 9
            camp_width = 22
            status_width = 8
            repo_width = content_width - effort_width - camp_width - status_width - 6
            headings = (
                f"{'REPOSITORY':<{repo_width}}  {'EFFORT':>{effort_width}}"
                f"  {'CAMPS':<{camp_width}}  {'STATUS':<{status_width}}"
            )
            print(f"  {style.dim}{headings}{style.reset}", file=stream)
            for row in report["repositories"]:
                statuses = []
                if row["dirty"]:
                    statuses.append("dirty")
                if row["weak_identity"]:
                    statuses.append("local")
                status = ",".join(statuses) if statuses else "clean"
                status_color = style.yellow if statuses else style.green
                repository = clipped(shortened_repository(row["repository"]), repo_width)
                camps = clipped(", ".join(row["camps"]), camp_width)
                print(
                    f"  {style.accent}{repository:<{repo_width}}{style.reset}"
                    f"  {row['estimated_person_months']:>{effort_width - 3}.1f} PM"
                    f"  {camps:<{camp_width}}"
                    f"  {status_color}{status}{style.reset}",
                    file=stream,
                )
        else:
            for row in report["repositories"]:
                statuses = []
                if row["dirty"]:
                    statuses.append("dirty")
                if row["weak_identity"]:
                    statuses.append("local identity")
                suffix = f" · {', '.join(statuses)}" if statuses else ""
                repository = clipped(shortened_repository(row["repository"]), content_width)
                camps = ", ".join(row["camps"])
                print(f"  {style.accent}{repository}{style.reset}", file=stream)
                print(
                    f"    {row['estimated_person_months']:.1f} PM"
                    f" {style.dim}·{style.reset} {camps}{suffix}",
                    file=stream,
                )

    section("IDENTITY")
    print(f"  {style.dim}Emails{style.reset}  {', '.join(report['author_emails'])}", file=stream)
    if report["author_names"]:
        print(
            f"  {style.dim}Names {style.reset}  {', '.join(report['author_names'])}",
            file=stream,
        )
    if report["author_groups"]:
        groups = collapsed_labels(report["author_groups"])
        print(
            f"  {style.dim}Groups{style.reset}  {', '.join(groups)}",
            file=stream,
        )
    print(file=stream)

    for error in report["errors"]:
        print(f"{error_style.red}Skipped:{error_style.reset} {error}", file=error_stream)
    for warning in report["warnings"]:
        print(f"{error_style.yellow}Excluded:{error_style.reset} {warning}", file=error_stream)
    if not report["complete"]:
        print(
            f"{error_style.red}Incomplete score:{error_style.reset}"
            " some Camps or repositories could not be measured.",
            file=error_stream,
        )


def command(
    *args: str,
    cwd: Path | None = None,
    allow_failure: bool = False,
    environment: dict[str, str] | None = None,
) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, **environment} if environment else None,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"{args[0]} timed out after {COMMAND_TIMEOUT_SECONDS} seconds") from exc
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


def json_command(
    *args: str,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> Any:
    raw = command(*args, cwd=cwd, environment=environment)
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
    camp: str
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
        chosen = min(group, key=lambda c: (not c.standalone, -c.head_time, str(c.scan_path)))
        result.append((chosen, group))
    return result


def normalize_author_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def expand_author_identity(
    seed_emails: set[str],
    seed_names: set[str],
    author_configs: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    """Expand explicit emails and author/group names through Camp identity groups."""
    emails = {email.strip().lower() for email in seed_emails if email.strip()}
    selectors = {normalize_author_name(name) for name in seed_names if name.strip()}
    matched_groups: set[str] = set()
    changed = True
    while changed:
        changed = False
        for cfg in author_configs:
            for key, group in cfg.get("authors", {}).items():
                if group.get("exclude"):
                    continue
                group_names = {
                    normalize_author_name(str(key)),
                    normalize_author_name(str(group.get("name", ""))),
                } - {""}
                members = {str(e).strip().lower() for e in group.get("emails", []) if str(e).strip()}
                if not (members & emails or group_names & selectors):
                    continue
                before = len(emails)
                emails.update(members)
                matched_groups.update(group_names)
                changed = changed or len(emails) != before
    return emails, matched_groups


def expand_author_emails(seeds: set[str], author_configs: list[dict[str, Any]]) -> set[str]:
    """Backward-compatible email-only identity expansion."""
    emails, _ = expand_author_identity(seeds, set(), author_configs)
    return emails


def git_author_pairs(
    git_roots: set[Path], emails: set[str], names: set[str],
) -> set[tuple[str, str]]:
    selectors = sorted(emails | names)
    if not selectors:
        return set()
    author_pattern = "(?:" + "|".join(re.escape(selector) for selector in selectors) + ")"
    pairs: set[tuple[str, str]] = set()
    for git_root in sorted(git_roots):
        try:
            raw = command(
                "git", "log", "--all", "--perl-regexp", "--regexp-ignore-case",
                f"--author={author_pattern}", "--format=%an%x09%ae", cwd=git_root,
            )
        except ScanError:
            # Some Git builds omit PCRE. Preserve correctness with a slower
            # full-author scan and the same exact matching below.
            raw = command("git", "log", "--all", "--format=%an%x09%ae", cwd=git_root)
        for line in raw.splitlines():
            name, separator, email = line.partition("\t")
            normalized_email = email.strip().lower()
            if separator and normalized_email and (
                normalized_email in emails or normalize_author_name(name) in names
            ):
                pairs.add((name.strip(), normalized_email))
    return pairs


def discover_named_author_emails(
    emails: set[str], names: set[str], pairs: set[tuple[str, str]],
) -> set[str]:
    """Add emails used by exact selected Git author names."""
    discovered = set(emails)
    for name, email in pairs:
        if normalize_author_name(name) in names:
            discovered.add(email)
    return discovered


def seed_author_emails(cli_emails: list[str], default_email: str) -> set[str]:
    seeds = {email for email in cli_emails if email.strip()}
    if default_email.strip():
        seeds.add(default_email)
    return seeds


def project_entries(root: Path) -> list[dict[str, Any]]:
    discovered = json_command(
        "camp", "project", "list", "--json", cwd=root,
        environment={"CAMP_ROOT": str(root)},
    )
    if not isinstance(discovered, list):
        raise ScanError(f"{root}: camp project list returned a non-list")
    config = json_file(root / ".campaign/leverage/config.json")
    configured = config.get("projects", {})
    if not configured:
        return [item for item in discovered if not WORKTREE_DIRS.intersection(Path(item.get("Path", "")).parts)]
    by_path = {item.get("Path"): item for item in discovered}
    entries = []
    configured_names = set(configured)
    configured_paths = {
        entry.get("path") for entry in configured.values() if entry.get("path")
    }
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
    for item in discovered:
        name = item.get("Name")
        path = item.get("Path", "")
        if name in configured_names or path in configured_paths:
            continue
        if WORKTREE_DIRS.intersection(Path(path).parts):
            continue
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


def checkout_for_project(root: Path, camp: str, item: dict[str, Any]) -> Checkout:
    relative = item.get("Path", "")
    declared_path = root / relative
    if not relative or not declared_path.absolute().is_relative_to(root.resolve()) or ".." in Path(relative).parts:
        raise ScanError(f"{camp}/{item.get('Name')}: invalid project path {relative!r}")
    path = declared_path.resolve()
    if not path.is_relative_to(root.resolve()) and item.get("Source") != "linked":
        raise ScanError(f"{camp}/{item.get('Name')}: project escapes its Camp without a link")
    if not path.is_dir():
        raise ScanError(f"{camp}/{item.get('Name')}: missing directory {path}")
    top = command("git", "rev-parse", "--show-toplevel", cwd=path)
    git_root = Path(top).resolve()
    if not path.is_relative_to(git_root):
        raise ScanError(f"{camp}/{item.get('Name')}: Git root does not contain project")

    # A Camp-owned folder is a distinct scan scope in its Camp repo.
    # A monorepo child resolves to its parent repo unless it is a real submodule.
    monorepo_root = item.get("MonorepoRoot", "")
    camp_owned = git_root == root.resolve() and path != git_root and not monorepo_root
    if item.get("Source") == "submodule" and path != git_root and not monorepo_root:
        raise ScanError(f"{camp}/{item.get('Name')}: submodule is not initialized: {path}")
    scan_path = path if camp_owned else git_root
    origin = command("git", "remote", "get-url", "origin", cwd=git_root, allow_failure=True)
    identity = normalize_remote(origin or item.get("URL", ""))
    weak = identity is None
    if identity is None:
        common = command("git", "rev-parse", "--git-common-dir", cwd=git_root)
        identity = "gitdir:" + str((git_root / common).resolve())
    if camp_owned:
        identity += "::" + str(path.relative_to(git_root))
    head_raw = command("git", "log", "-1", "--format=%ct", cwd=git_root, allow_failure=True)
    return Checkout(
        key=identity, scan_path=scan_path, git_root=git_root, camp=camp,
        project=str(item.get("Name", path.name)), standalone=not bool(monorepo_root),
        head_time=int(head_raw) if head_raw.isdigit() else 0, weak_identity=weak,
    )


def author_history_stats(git_root: Path, scan_path: Path, emails: set[str]) -> dict[str, Any]:
    """Count selected-author commits and textual lines added/deleted in this scope."""
    args = [
        "git", "log", "--all", "--find-renames", "--numstat",
        "--format=@@CAMP_LEVERAGE@@%ae%x09%cI",
    ]
    try:
        relative = scan_path.resolve().relative_to(git_root.resolve())
    except ValueError as exc:
        raise ScanError(f"{scan_path}: outside Git root {git_root}") from exc
    if relative != Path("."):
        args.extend(("--", str(relative)))
    raw = command(*args, cwd=git_root)
    selected = False
    selected_month = ""
    dates: list[datetime] = []
    added = deleted = commits = 0
    activity: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"commit_count": 0, "lines_added": 0, "lines_deleted": 0}
    )
    marker = "@@CAMP_LEVERAGE@@"
    for line in raw.splitlines():
        if line.startswith(marker):
            identity = line[len(marker):]
            email, separator, stamp = identity.partition("\t")
            selected = bool(separator and email.strip().lower() in emails)
            if selected:
                try:
                    commit_date = datetime.fromisoformat(stamp)
                except ValueError as exc:
                    raise ScanError(f"{git_root}: invalid Git date {stamp!r}") from exc
                dates.append(commit_date)
                selected_month = commit_date.astimezone(UTC).strftime("%Y-%m")
                activity[selected_month]["commit_count"] += 1
                commits += 1
            else:
                selected_month = ""
            continue
        if not selected or not line:
            continue
        added_text, separator, remainder = line.partition("\t")
        deleted_text, separator2, file_name = remainder.partition("\t")
        if any(part in EXCLUDE_DIRS for part in Path(file_name).parts):
            continue
        if separator and separator2 and added_text.isdigit() and deleted_text.isdigit():
            added += int(added_text)
            deleted += int(deleted_text)
            activity[selected_month]["lines_added"] += int(added_text)
            activity[selected_month]["lines_deleted"] += int(deleted_text)
    return {
        "commit_count": commits,
        "lines_added": added,
        "lines_deleted": deleted,
        "first_commit": min(dates).isoformat() if dates else None,
        "last_commit": max(dates).isoformat() if dates else None,
        "activity": [
            {"month": month, **activity[month]}
            for month in sorted(activity)
        ],
    }


def blame_counts(scan_path: Path, jobs: int = DEFAULT_JOBS) -> Counter[str]:
    try:
        raw = subprocess.run(
            ("git", "ls-files", "-z"),
            cwd=scan_path,
            capture_output=True,
            check=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"{scan_path}: git ls-files timed out") from exc
    except OSError as exc:
        raise ScanError(f"{scan_path}: git ls-files: {exc}") from exc
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
        try:
            result = subprocess.run(
                ("git", "blame", "--line-porcelain", "--", file),
                cwd=scan_path,
                capture_output=True,
                check=False,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ScanError(f"{scan_path / file}: git blame timed out") from exc
        except OSError as exc:
            raise ScanError(f"{scan_path / file}: git blame: {exc}") from exc
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
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for file_counts in pool.map(blame_one, files):
            counts.update(file_counts)
    return counts


def score_checkout(
    checkout: Checkout,
    emails: set[str],
    jobs: int = DEFAULT_JOBS,
    *,
    annual_wage: int = DEFAULT_ANNUAL_WAGE,
    overhead: float = DEFAULT_OVERHEAD,
) -> dict[str, Any] | None:
    history = author_history_stats(checkout.git_root, checkout.scan_path, emails)
    if not history["commit_count"]:
        return None
    args = [
        "scc", "--format", "json2", "--cocomo-project-type", "organic",
        "--avg-wage", str(annual_wage), "--overhead", str(overhead),
    ]
    for dirname in EXCLUDE_DIRS:
        args.extend(("--exclude-dir", dirname))
    args.append(str(checkout.scan_path))
    result = json_command(*args)
    people = float(result["estimatedPeople"])
    months = float(result["estimatedScheduleMonths"])
    cost = float(result["estimatedCost"])
    if not math.isfinite(cost) or cost < 0:
        raise ScanError("scc returned an invalid estimated cost")
    code_lines = sum(int(language.get("Code", 0)) for language in result.get("languageSummary", []))
    counts = blame_counts(checkout.scan_path, jobs)
    total_lines = sum(counts.values())
    owned_lines = sum(count for email, count in counts.items() if email in emails)
    share = owned_lines / total_lines if total_lines else 0.0
    status = command("git", "status", "--porcelain", "--untracked-files=no", cwd=checkout.git_root)
    return {
        "repository": checkout.key,
        "path": str(checkout.scan_path),
        "estimated_person_months": people * months * share,
        "unscaled_estimated_person_months": people * months,
        "estimated_cost_usd": cost * share,
        "unscaled_estimated_cost_usd": cost,
        "author_share": share,
        "owned_lines": owned_lines,
        "estimated_owned_code_lines": round(code_lines * share),
        "code_lines": code_lines,
        "blamed_lines": total_lines,
        **history,
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
        "estimated_cost_usd": sum(row["estimated_cost_usd"] for row in rows),
        "actual_person_months": actual,
        "first_commit": first.isoformat(),
        "last_commit": last.isoformat(),
        "commit_count": sum(row.get("commit_count", 0) for row in rows),
        "lines_added": sum(row.get("lines_added", 0) for row in rows),
        "lines_deleted": sum(row.get("lines_deleted", 0) for row in rows),
        "current_owned_lines": sum(row.get("owned_lines", 0) for row in rows),
        "estimated_current_code_lines": sum(row.get("estimated_owned_code_lines", 0) for row in rows),
        "current_code_lines": sum(row.get("code_lines", 0) for row in rows),
    }


def resolved_timeline_interval(first: datetime, last: datetime, requested: str) -> str:
    if requested != "auto":
        return requested
    months = max(MIN_AUTHOR_MONTHS, (last - first).total_seconds() / SECONDS_PER_MONTH)
    if months <= 18:
        return "month"
    if months <= 72:
        return "quarter"
    return "year"


def period_start(value: datetime, interval: str) -> datetime:
    value = value.astimezone(UTC)
    if interval == "month":
        month = value.month
    elif interval == "quarter":
        month = ((value.month - 1) // 3) * 3 + 1
    elif interval == "year":
        month = 1
    else:
        raise ValueError(f"unsupported timeline interval: {interval}")
    return datetime(value.year, month, 1, tzinfo=UTC)


def next_period(value: datetime, interval: str) -> datetime:
    months = {"month": 1, "quarter": 3, "year": 12}[interval]
    absolute_month = value.year * 12 + value.month - 1 + months
    return datetime(absolute_month // 12, absolute_month % 12 + 1, 1, tzinfo=UTC)


def period_label(value: datetime, interval: str) -> str:
    if interval == "month":
        return value.strftime("%Y-%m")
    if interval == "quarter":
        return f"{value.year} Q{((value.month - 1) // 3) + 1}"
    return str(value.year)


def build_timeline(rows: list[dict[str, Any]], requested: str = "auto") -> dict[str, Any] | None:
    """Allocate current owned effort across commit periods without claiming snapshots."""
    if requested == "none" or not rows:
        return None
    first = min(datetime.fromisoformat(row["first_commit"]) for row in rows).astimezone(UTC)
    last = max(datetime.fromisoformat(row["last_commit"]) for row in rows).astimezone(UTC)
    interval = resolved_timeline_interval(first, last, requested)
    starts = []
    cursor = period_start(first, interval)
    while cursor <= last:
        starts.append(cursor)
        cursor = next_period(cursor, interval)
    buckets = {
        start: {
            "commit_count": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "estimated_person_months": 0.0,
            "estimated_cost_usd": 0.0,
        }
        for start in starts
    }

    for row in rows:
        activities = list(row.get("activity", []))
        if not activities:
            activities = [{
                "month": datetime.fromisoformat(row["last_commit"]).astimezone(UTC).strftime("%Y-%m"),
                "commit_count": row.get("commit_count", 0),
                "lines_added": row.get("lines_added", 0),
                "lines_deleted": row.get("lines_deleted", 0),
            }]
        added_total = sum(item.get("lines_added", 0) for item in activities)
        commit_total = sum(item.get("commit_count", 0) for item in activities)
        denominator = added_total or commit_total or 1
        for item in activities:
            month = datetime.strptime(item["month"], "%Y-%m").replace(tzinfo=UTC)
            start = period_start(month, interval)
            bucket = buckets[start]
            bucket["commit_count"] += item.get("commit_count", 0)
            bucket["lines_added"] += item.get("lines_added", 0)
            bucket["lines_deleted"] += item.get("lines_deleted", 0)
            weight = item.get("lines_added", 0) if added_total else item.get("commit_count", 0)
            bucket["estimated_person_months"] += (
                row["estimated_person_months"] * weight / denominator
            )
            bucket["estimated_cost_usd"] += row["estimated_cost_usd"] * weight / denominator

    periods = []
    cumulative_estimated = 0.0
    cumulative_cost = 0.0
    for start in starts:
        end = min(next_period(start, interval), last)
        active_start = max(start, first)
        elapsed = max(MIN_AUTHOR_MONTHS, (end - active_start).total_seconds() / SECONDS_PER_MONTH)
        cumulative_elapsed = max(
            MIN_AUTHOR_MONTHS, (end - first).total_seconds() / SECONDS_PER_MONTH
        )
        bucket = buckets[start]
        estimated = bucket["estimated_person_months"]
        cumulative_estimated += estimated
        cumulative_cost += bucket["estimated_cost_usd"]
        periods.append({
            "label": period_label(start, interval),
            "start": active_start.isoformat(),
            "end": end.isoformat(),
            "calendar_months": elapsed,
            "estimated_person_months": estimated,
            "estimated_cost_usd": bucket["estimated_cost_usd"],
            "cumulative_estimated_cost_usd": cumulative_cost,
            "full_leverage": estimated / elapsed,
            "cumulative_estimated_person_months": cumulative_estimated,
            "cumulative_calendar_months": cumulative_elapsed,
            "cumulative_leverage": cumulative_estimated / cumulative_elapsed,
            "commit_count": bucket["commit_count"],
            "lines_added": bucket["lines_added"],
            "lines_deleted": bucket["lines_deleted"],
        })
    return {
        "interval": interval,
        "method": TIMELINE_METHOD,
        "allocation_basis": "selected-author textual lines added; commits when no text was added",
        "historical_snapshot": False,
        "periods": periods,
    }


def calculate(
    camp_filters: list[str],
    seed_emails: set[str],
    seed_names: set[str] | None = None,
    *,
    progress: bool = True,
    jobs: int = DEFAULT_JOBS,
    timeline_interval: str = "auto",
    annual_wage: int = DEFAULT_ANNUAL_WAGE,
    overhead: float = DEFAULT_OVERHEAD,
) -> dict[str, Any]:
    camps = json_command("camp", "list", "--format", "json")
    if not isinstance(camps, list):
        raise ScanError("camp list returned a non-list")
    selected = [c for c in camps if not camp_filters or c["name"] in camp_filters or c["id"] in camp_filters]
    missing = set(camp_filters) - {c["name"] for c in selected} - {c["id"] for c in selected}
    if missing:
        raise ScanError("unknown Camp: " + ", ".join(sorted(missing)))
    if not selected:
        raise ScanError("no registered Camps")

    errors: list[str] = []
    warnings: list[str] = []
    checkouts: list[Checkout] = []
    author_configs: list[dict[str, Any]] = []
    for camp in selected:
        root = Path(camp["path"]).expanduser().resolve()
        try:
            author_configs.append(json_file(root / ".campaign/leverage/authors.json"))
            for item in project_entries(root):
                try:
                    checkouts.append(checkout_for_project(root, camp["name"], item))
                except ScanError as exc:
                    if stale_absent_project(root, item):
                        warnings.append(f"{camp['name']}/{item.get('Name')}: absent from current Git tree; stale project entry")
                    else:
                        errors.append(str(exc))
        except ScanError as exc:
            errors.append(f"{camp['name']}: {exc}")

    chosen = select_checkouts(checkouts)
    names = {normalize_author_name(name) for name in (seed_names or set()) if name.strip()}
    emails, author_groups = expand_author_identity(seed_emails, names, author_configs)
    git_roots = {checkout.git_root for checkout, _ in chosen}
    pairs: set[tuple[str, str]] = set()
    # A selected Git name can reveal an address missing from Camp's author
    # files; that address can then connect another Camp identity group.
    while True:
        try:
            pairs.update(git_author_pairs(git_roots, emails, names))
        except ScanError as exc:
            errors.append(f"author identity discovery: {exc}")
            break
        expanded = discover_named_author_emails(emails, names, pairs)
        expanded, expanded_groups = expand_author_identity(expanded, names, author_configs)
        if expanded == emails and expanded_groups == author_groups:
            break
        emails, author_groups = expanded, expanded_groups
    if not emails:
        raise ScanError("no author email; use --author-email or configure git user.email")
    matched_pairs = sorted(
        ({"name": name, "email": email} for name, email in pairs if email in emails),
        key=lambda pair: (pair["name"].lower(), pair["email"]),
    )
    rows = []
    for index, (checkout, group) in enumerate(chosen, 1):
        if progress:
            print(f"Scoring {index}/{len(chosen)}: {checkout.project}", file=sys.stderr)
        try:
            scored = score_checkout(
                checkout, emails, jobs, annual_wage=annual_wage, overhead=overhead,
            )
        except (ScanError, KeyError, ValueError, TypeError) as exc:
            errors.append(f"{checkout.key}: {exc}")
            continue
        if scored is None:
            continue
        scored["camps"] = sorted({c.camp for c in group})
        scored["checkouts"] = sorted({str(c.scan_path) for c in group})
        rows.append(scored)

    summary = {}
    if rows:
        summary = aggregate(rows)
        timeline = build_timeline(rows, timeline_interval)
    else:
        errors.append("no selected-author commits in the scored repositories")
        timeline = None
    return {
        "complete": not errors,
        "camp_count": len(selected),
        "unique_repository_count": len(rows),
        "discovered_repository_count": len(chosen),
        "author_emails": sorted(emails),
        "author_names": sorted(names),
        "author_groups": sorted(author_groups),
        "matched_git_identities": matched_pairs,
        "cost_model": {
            "currency": "USD", "project_type": "organic",
            "annual_wage_usd": annual_wage, "overhead_multiplier": overhead,
            "source": "scc.estimatedCost",
        },
        "summary": summary,
        "timeline": timeline,
        "repositories": rows,
        "errors": errors,
        "warnings": warnings,
    }


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def missing_commands() -> list[str]:
    return [name for name in REQUIRED_COMMANDS if shutil.which(name) is None]


def validate_scc_version() -> None:
    raw = command("scc", "--version")
    match = re.search(r"\b(\d+)\.(\d+)(?:\.\d+)?\b", raw)
    if not match:
        raise ScanError(f"could not parse scc version from {raw!r}")
    version = tuple(int(part) for part in match.groups())
    if version < MINIMUM_SCC_VERSION:
        minimum = ".".join(str(part) for part in MINIMUM_SCC_VERSION)
        raise ScanError(f"scc {minimum} or newer is required; found {raw}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="camp leverage-all", description=__doc__)
    parser.add_argument(
        "--camp", action="append", dest="camps", default=[],
        help="exact Camp name or ID (repeatable)",
    )
    parser.add_argument(
        "--campaign", action="append", dest="camps", help=argparse.SUPPRESS,
    )
    parser.add_argument("--author-email", action="append", default=[], help="author email (repeatable)")
    parser.add_argument(
        "--author-name", action="append", default=[],
        help="exact Git author name or Camp author-group name (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument(
        "--annual-wage", type=positive_int, default=DEFAULT_ANNUAL_WAGE,
        help=f"annual wage in USD for COCOMO cost (default: {DEFAULT_ANNUAL_WAGE})",
    )
    parser.add_argument(
        "--overhead", type=positive_float, default=DEFAULT_OVERHEAD,
        help=f"COCOMO cost overhead multiplier (default: {DEFAULT_OVERHEAD})",
    )
    parser.add_argument(
        "--timeline", choices=TIMELINE_INTERVALS, default="auto",
        help="timeline interval: auto, month, quarter, year, or none (default: auto)",
    )
    parser.add_argument(
        "--jobs", type=positive_int, default=DEFAULT_JOBS,
        help=f"parallel Git blame workers (default: {DEFAULT_JOBS})",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="terminal color mode (default: auto)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    seed_names = set(args.author_name)
    try:
        missing = missing_commands()
        if missing:
            raise ScanError(
                "missing required command" + ("s" if len(missing) > 1 else "")
                + ": " + ", ".join(missing)
                + "; see the installation prerequisites in README.md"
            )
        validate_scc_version()
        default = command("git", "config", "user.email", allow_failure=True)
        seeds = seed_author_emails(args.author_email, default)
        report = calculate(
            args.camps, seeds, seed_names, progress=not args.json, jobs=args.jobs,
            timeline_interval=args.timeline,
            annual_wage=args.annual_wage, overhead=args.overhead,
        )
    except ScanError as exc:
        print(f"camp leverage-all: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        render_text_report(report, color=args.color)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
