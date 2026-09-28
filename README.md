# Campaign Leverage

Campaign Leverage calculates one personal leverage score across every Camp workspace you use. It discovers registered campaigns and projects, identifies all of your configured Git identities, and counts each repository once even when the same repo appears in several campaigns or worktrees.

```console
$ leverage
Scoring 1/12: api
Scoring 2/12: website
...
Full leverage: 18.4x
Estimated effort: 76.2 person-months
Actual effort: 4.1 person-months
Current lines owned: 42,608
Estimated current code LOC: 31,954
Lifetime lines added: 182,147
Lifetime lines deleted: 61,398
Matching commits: 1,284
Campaigns: 4  Unique scored repos: 12
```

The exact result depends on your repositories and author identities. Campaign Leverage is read-only: it does not modify Git history, Camp configuration, or project files.

## What it measures

The report combines two different views of your work:

- **Current ownership:** lines currently attributed to your email addresses by `git blame`, plus your proportional share of `scc`'s current code count and COCOMO estimate.
- **Lifetime production:** commits and textual lines added or deleted by those email addresses across all branches.
- **Full leverage:** your share of COCOMO-estimated project effort divided by the calendar span between your first and last matching commits.

Repository identities come from normalized Git remotes. SSH aliases, SSH URLs, and HTTPS URLs for the same remote collapse to one repository. Camp worktree directories are excluded, and duplicate checkouts report all of their campaign memberships. See [SPEC.md](SPEC.md) for the complete selection and calculation rules.

This is a comparative engineering metric for personal tracking. It is not a valuation, a productivity target, or a measure of hours worked.

## Requirements

Campaign Leverage supports macOS and Linux with Python 3.11 or newer. It expects these commands on `PATH`:

- [`camp`](https://github.com/Obedience-Corp/camp), installed as part of the [Festival suite](https://github.com/Obedience-Corp/festival), which supplies registered campaigns and projects
- [`git`](https://git-scm.com/)
- [`scc`](https://github.com/boyter/scc), version 3.7 or newer, which supplies code counts and COCOMO estimates

Install Festival to get the matched `camp`, `fest`, and `festival` binaries. On macOS:

```sh
brew install --cask Obedience-Corp/tap/festival
brew install scc
festival doctor
```

The Festival suite is also available through npm, pnpm, bun, Linux packages, and release archives. Follow the [Festival installation guide](https://github.com/Obedience-Corp/festival#install) for the supported command on your platform, then install `scc` separately if your package method did not provide it.

Festival's shell integration provides Camp navigation commands such as `cgo`. The [Festival navigation guide](https://github.com/Obedience-Corp/festival#navigation) documents setup for zsh, bash, fish, and POSIX sh.

## Install

Until the first PyPI release, install directly from GitHub with an isolated Python tool installer:

```sh
uv tool install git+https://github.com/Obedience-Corp/campaign-leverage.git
```

or:

```sh
pipx install git+https://github.com/Obedience-Corp/campaign-leverage.git
```

Contributors working from a clone can run:

```sh
uv tool install --editable .
```

The package installs the short `leverage` command. `campaign-leverage` is also available as a descriptive alias.

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

Both options are repeatable. An explicit email is added to `git config user.email`. An author name may also match a key in `.campaign/leverage/authors.json`; Campaign Leverage expands linked email groups across the selected campaigns until the identity set is stable.

Limit a scan to one or more exact campaign names or IDs:

```sh
leverage --campaign personal --campaign consulting
```

Produce stable machine-readable output and suppress progress messages:

```sh
leverage --json > leverage.json
```

Tune parallel Git blame work for a large machine or constrained environment:

```sh
leverage --jobs 4
```

Run `leverage --help` for every option.

## Output and exit status

The text report includes the aggregate score, author identities, campaign and repository counts, and each scored repository. Dirty repositories and repos without a remote are labeled because they weaken reproducibility.

JSON output contains the same aggregate and per-repository evidence. Local checkout paths and author email addresses are included, so review the file before publishing it.

The process exits:

- `0` when every selected campaign and repository was measured
- `2` for invalid arguments, missing dependencies, unknown campaigns, unreadable data, failed Git or `scc` commands, or any incomplete scan

A partial scan may still print measured rows, but it is labeled incomplete and exits `2` so automation cannot mistake it for the full result.

## Develop

From a Camp workspace, `cgo leverage` opens the project. Then run:

```sh
python3 -m unittest -v
python3 -m compileall -q campaign_leverage.py
uv build
docker build -f tests/integration/Dockerfile -t campaign-leverage-integration .
docker run --rm --network none campaign-leverage-integration
```

The project has no runtime Python dependencies. GitHub Actions checks the supported Python versions on macOS and Linux, then runs the end-to-end deduplication fixture in an isolated container. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and sign-off requirements.

Campaign Leverage is pre-1.0 software. Review [RELEASING.md](RELEASING.md) before changing repository visibility or publishing a release. Security reports should follow [SECURITY.md](SECURITY.md).

## License

Copyright 2026 Obedience Corp. Licensed under the [Apache License 2.0](LICENSE).
