#!/usr/bin/env python3
"""Render the real CLI in a PTY and write pyte evidence for the VHS bundle."""

from __future__ import annotations

import fcntl
import importlib.metadata
import json
import os
import pty
import select
import struct
import sys
import termios
import time
from pathlib import Path

import pyte

COLUMNS = 96
ROWS = 32
PIXEL_WIDTH = 1040
PIXEL_HEIGHT = 680
FIXTURE_ID = "camp-leverage-demo-v1"


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    evidence = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/camp-leverage-evidence")
    evidence.mkdir(parents=True, exist_ok=True)

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(repo)
        command = (
            'eval "$(./scripts/demo-fixture.sh)"; '
            "exec ./camp_leverage.py --author-name demo-agent --color always"
        )
        environment = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "COLUMNS": str(COLUMNS),
            "LINES": str(ROWS),
        }
        environment.pop("NO_COLOR", None)
        os.execve("/bin/bash", ["bash", "-lc", command], environment)

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLUMNS, 0, 0))
    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.ByteStream(screen)
    raw = bytearray()
    deadline = time.time() + 30

    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.25)
        if not ready:
            reaped, status = os.waitpid(pid, os.WNOHANG)
            if reaped:
                if status != 0:
                    print(f"CLI exited with status {status}", file=sys.stderr)
                    return 1
                break
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        raw.extend(data)
        stream.feed(data)
    else:
        os.kill(pid, 9)
        print("CLI did not finish within 30 seconds", file=sys.stderr)
        return 1

    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass

    display = list(screen.display)
    rendered = "\n".join(line.rstrip() for line in display)
    expected = (
        "CAMP LEVERAGE",
        "full leverage",
        "CONTRIBUTION",
        "SCOPE",
        "REPOSITORIES",
        "github.com/example/automation-toolkit",
        "github.com/example/client-portal",
        "github.com/example/shared-platform",
        "IDENTITY",
        "demo-agent",
    )
    missing = [text for text in expected if text not in rendered]
    failures = []
    if missing:
        failures.append("missing rendered text: " + ", ".join(missing))
    if "/tmp/" in rendered or "/private/" in rendered or "/Users/" in rendered:
        failures.append("rendered report leaked a host or fixture path")
    if "\ufffd" in rendered:
        failures.append("terminal renderer found invalid UTF-8 replacement characters")
    if not 0 <= screen.cursor.x < COLUMNS or not 0 <= screen.cursor.y < ROWS:
        failures.append("cursor is outside the terminal bounds")

    terminal = {
        "columns": COLUMNS,
        "rows": ROWS,
        "pixel_width": PIXEL_WIDTH,
        "pixel_height": PIXEL_HEIGHT,
        "mode": "dark/adaptive truecolor",
    }
    snapshot = {
        "name": "report",
        "display": display,
        "cursor": {"x": screen.cursor.x, "y": screen.cursor.y},
    }
    (evidence / "pty-transcript.txt").write_text(rendered + "\n")
    (evidence / "screen-snapshots.json").write_text(json.dumps({
        "renderer": "pyte",
        "terminal": terminal,
        "snapshots": [snapshot],
    }, indent=2))
    (evidence / "pty-metadata.json").write_text(json.dumps({
        "transport": "pty",
        "renderer": "pyte",
        "pyte_version": importlib.metadata.version("pyte"),
        "fake_home": True,
        "fixture_id": FIXTURE_ID,
        "terminal": terminal,
    }, indent=2))

    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        return 1
    print("terminal-render: real CLI fits 96x32 with all report sections visible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
