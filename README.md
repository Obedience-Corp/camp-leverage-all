<h1 align="center">Leverage</h1>

<p align="center"><strong>Your engineering output across every Camp, counted once.</strong></p>

<p align="center">
  <a href="https://github.com/Obedience-Corp/camp-leverage/actions/workflows/ci.yml"><img src="https://github.com/Obedience-Corp/camp-leverage/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-F2721C" alt="Python 3.11 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-F2721C" alt="Apache 2.0 license"></a>
</p>

<p align="center">
  <a href="https://gist.github.com/lancekrogers/1d596e89c22ea39e59c40e4c38a54bfc"><img src="https://gist.githubusercontent.com/lancekrogers/1d596e89c22ea39e59c40e4c38a54bfc/raw/camp-leverage-terminal.gif" width="960" alt="Leverage terminal report showing a deduplicated score, contribution metrics, repositories, and identities"></a>
</p>

<p align="center"><em>Recorded from the real CLI with two sanitized Camps; the shared repository is counted once.</em></p>

Leverage is an experimental companion CLI for Camp. It discovers registered Camps and projects, joins your configured Git identities, and calculates one personal leverage score without counting the same repository or worktree twice.

| Deduplicated | Identity-aware | Auditable |
| --- | --- | --- |
| One remote contributes once across every Camp and checkout. | Personal, work, bot, and agent emails can resolve into one author set. | Every score includes its repositories, commit span, ownership, and failures. |

The exact result depends on your repositories and author identities. Leverage is read-only: it does not modify Git history, Camp configuration, or project files.

> **Status:** This is a private pre-release prototype for validating cross-Camp scoring. Its packaging and command contract may change before a public release.

## Quick start

Leverage depends on the `camp` binary from [Festival](https://github.com/Obedience-Corp/festival), plus `git`, `scc` 3.7 or newer, and Python 3.11 or newer. On macOS, install Festival and `scc` first:

```sh
brew install --cask Obedience-Corp/tap/festival
brew install scc
festival doctor
```

Then install Leverage with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and run it:

```sh
uv tool install git+https://github.com/Obedience-Corp/camp-leverage.git
leverage
```

That first report scans every registered Camp, combines your configured Git identities, and counts each repository once.

Festival supplies the Camp registry; Leverage remains a separate, read-only program. Its command does not replace Camp's native command:

| Command | Scope | State |
| --- | --- | --- |
| `leverage` | All registered Camps by default | Read-only aggregate with repository deduplication |
| `camp leverage` | Projects in the current Camp | Maintains configuration, cache, snapshots, and history in `.campaign/leverage/` |

The package intentionally installs only `leverage`. It does not install `camp-leverage`, because that executable name conflicts conceptually with the existing `camp leverage` command.

For npm, pnpm, bun, Linux packages, or release archives, install Festival using its [installation guide](https://github.com/Obedience-Corp/festival#install), then install `scc` separately. Festival's [navigation guide](https://github.com/Obedience-Corp/festival#navigation) explains optional shell commands such as `cgo`.

## Install alternatives

Until the first PyPI release, installation comes directly from GitHub. If your GitHub access uses SSH:

```sh
uv tool install git+ssh://git@github.com/Obedience-Corp/camp-leverage.git
```

`pipx` also works:

```sh
pipx install git+https://github.com/Obedience-Corp/camp-leverage.git
```

Contributors working from a clone can run:

```sh
uv tool install --editable .
```

The package installs one command: `leverage`.

## Use

Run the complete report using your current Git email and all matching identity groups found in Camp:

```sh
leverage
```

Add an email or an exact Git author name when work was committed under another identity:

```sh
leverage --author-email me@work.example
leverage --author-name my-automation-account
```

Both options are repeatable. An explicit email is added to `git config user.email`. An author name may also match a key in `.campaign/leverage/authors.json`; Leverage expands linked email groups across the selected Camps until the identity set is stable.

Limit a scan to one or more exact Camp names or IDs:

```sh
leverage --camp personal --camp consulting
```

Produce stable machine-readable output and suppress progress messages:

```sh
leverage --json > leverage.json
```

Tune parallel Git blame work for a large machine or constrained environment:

```sh
leverage --jobs 4
```

Color is automatic in a terminal and respects [`NO_COLOR`](https://no-color.org/). Use `--color always` when recording output or `--color never` for plain text.

Run `leverage --help` for every option.

## What it measures

The report combines two different views of your work:

- **Current ownership:** lines currently attributed to your email addresses by `git blame`, plus your proportional share of `scc`'s current code count and COCOMO estimate.
- **Lifetime production:** commits and textual lines added or deleted by those email addresses across all branches.
- **Full leverage:** your share of COCOMO-estimated project effort divided by the calendar span between your first and last matching commits.

Repository identities come from normalized Git remotes. SSH aliases, SSH URLs, and HTTPS URLs for the same remote collapse to one repository. Camp worktree directories are excluded, and duplicate checkouts report all of their Camp memberships. See [SPEC.md](SPEC.md) for the complete selection and calculation rules.

This is a comparative engineering metric for personal tracking. It is not a valuation, a productivity target, or a measure of hours worked.

## Output and exit status

The text report includes the aggregate score, author identities, Camp and repository counts, and each scored repository. Dirty repositories and repos without a remote are labeled because they weaken reproducibility.

JSON output contains the same aggregate and per-repository evidence. Local checkout paths and author email addresses are included, so review the file before publishing it.

The process exits:

- `0` when every selected Camp and repository was measured
- `2` for invalid arguments, missing dependencies, unknown Camps, unreadable data, failed Git or `scc` commands, or any incomplete scan

A partial scan may still print measured rows, but it is labeled incomplete and exits `2` so automation cannot mistake it for the full result.

## Develop

From a Camp workspace, `cgo leverage` navigates to this project; it does not calculate a report. Then run:

```sh
python3 -m unittest -v
python3 -m compileall -q camp_leverage.py
uv build
docker build -f tests/integration/Dockerfile -t camp-leverage-integration .
docker run --rm --network none camp-leverage-integration
docker run --rm --network none --entrypoint python camp-leverage-integration /app/tests/terminal/render_pty.py
```

The project has no runtime Python dependencies. GitHub Actions checks the supported Python versions on macOS and Linux, then runs the end-to-end deduplication fixture in an isolated container. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and sign-off requirements.

Leverage is pre-1.0 software. Review [RELEASING.md](RELEASING.md) before changing repository visibility or publishing a release. Security reports should follow [SECURITY.md](SECURITY.md).

## License

Copyright 2026 Obedience Corp. Licensed under the [Apache License 2.0](LICENSE).
