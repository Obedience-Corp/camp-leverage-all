<h1 align="center">Camp Leverage All</h1>

<p align="center"><strong>Your engineering output across every Camp, counted once.</strong></p>

<p align="center">
  <a href="https://github.com/Obedience-Corp/camp-leverage-all/actions/workflows/ci.yml"><img src="https://github.com/Obedience-Corp/camp-leverage-all/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-F2721C" alt="Python 3.11 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-F2721C" alt="Apache 2.0 license"></a>
</p>

<p align="center">
  <a href="https://gist.github.com/lancekrogers/2b93401425db6daaeba3b6f36849a9bf"><img src="https://gist.githubusercontent.com/lancekrogers/2b93401425db6daaeba3b6f36849a9bf/raw/camp-leverage-all-terminal.gif" width="960" alt="Camp Leverage All terminal report showing a deduplicated score, contribution metrics, timeline, repositories, and identities"></a>
</p>

<p align="center"><em>Recorded from the real CLI with two sanitized Camps; the shared repository is counted once and the cumulative timeline ends at the headline score.</em></p>

Camp Leverage All is an experimental Python plugin for Camp. It discovers registered Camps and projects, joins your configured Git identities, and calculates one personal leverage score without counting the same repository or worktree twice.

| Deduplicated | Identity-aware | Time-aware |
| --- | --- | --- |
| One remote contributes once across every Camp and checkout. | Personal, work, bot, and agent emails can resolve into one author set. | The report shows period output, period rate, and cumulative leverage through time. |

The exact result depends on your repositories and author identities. Camp Leverage All is read-only: it does not modify Git history, Camp configuration, or project files.

> **Status:** Camp Leverage All is pre-1.0 software. Its calculation contract is documented, but its command and output schemas may evolve before 1.0.

## Quick start

Camp Leverage All depends on the `camp` binary from [Festival](https://github.com/Obedience-Corp/festival), plus `git`, `scc` 3.7 or newer, and Python 3.11 or newer. On macOS, install Festival and `scc` first:

```sh
brew install --cask Obedience-Corp/tap/festival
brew install scc
festival doctor
```

Then install the plugin with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and run it through Camp:

```sh
uv tool install git+https://github.com/Obedience-Corp/camp-leverage-all.git
camp leverage-all
```

That first report scans every registered Camp, combines your configured Git identities, counts each repository once, and shows how the aggregate score develops over time.

Festival supplies the Camp registry and discovers the plugin executable on `PATH`. The plugin remains a separate, read-only Python program; Camp does not import it.

| Command | Scope | State |
| --- | --- | --- |
| `camp leverage-all` | All registered Camps by default | Read-only plugin with repository deduplication |
| `camp leverage` | Projects in the current Camp | Maintains configuration, cache, snapshots, and history in `.campaign/leverage/` |

The package installs the `camp-leverage-all` executable. Camp's plugin dispatcher exposes it as `camp leverage-all`, keeping it distinct from the native `camp leverage` command.

For npm, pnpm, bun, Linux packages, or release archives, install Festival using its [installation guide](https://github.com/Obedience-Corp/festival#install), then install `scc` separately. Festival's [navigation guide](https://github.com/Obedience-Corp/festival#navigation) explains optional shell commands such as `cgo`.

## Who it works for

Camp Leverage All works for any Festival user with one or more Camps registered on the machine. It has no built-in author names, email addresses, Camp names, or filesystem paths.

By default, it starts with `git config user.email`. If a Camp has `.campaign/leverage/authors.json`, matching identity groups expand that email to the user's other personal, work, bot, or agent addresses. Users without an author file still get a report for their configured Git email. The repeatable `--author-email` and `--author-name` options cover additional identities without changing Camp state.

## Install alternatives

Until the first PyPI release, installation comes directly from GitHub. If your GitHub access uses SSH:

```sh
uv tool install git+ssh://git@github.com/Obedience-Corp/camp-leverage-all.git
```

`pipx` also works:

```sh
pipx install git+https://github.com/Obedience-Corp/camp-leverage-all.git
```

Contributors working from a clone can run:

```sh
uv tool install --editable .
```

The package installs one plugin executable: `camp-leverage-all`.

## Use

Run the complete report using your current Git email and all matching identity groups found in Camp:

```sh
camp leverage-all
```

Add an email or an exact Git author name when work was committed under another identity:

```sh
camp leverage-all --author-email me@work.example
camp leverage-all --author-name my-automation-account
```

Both options are repeatable. An explicit email is added to `git config user.email`. An author name may also match a key in `.campaign/leverage/authors.json`; Camp Leverage All expands linked email groups across the selected Camps until the identity set is stable.

Limit a scan to one or more exact Camp names or IDs:

```sh
camp leverage-all --camp personal --camp consulting
```

Produce stable machine-readable output and suppress progress messages:

```sh
camp leverage-all --json > leverage.json
```

The timeline chooses monthly buckets for spans up to 18 months, quarters up to 72 months, and years for longer histories. Override or disable it when needed:

```sh
camp leverage-all --timeline month
camp leverage-all --timeline quarter
camp leverage-all --timeline year
camp leverage-all --timeline none
```

Tune parallel Git blame work for a large machine or constrained environment:

```sh
camp leverage-all --jobs 4
```

Color is automatic in a terminal and respects [`NO_COLOR`](https://no-color.org/). Use `--color always` when recording output or `--color never` for plain text.

Run `camp leverage-all --help` for every option.

## What it measures

The report combines two different views of your work:

- **Current ownership:** lines currently attributed to your email addresses by `git blame`, plus your proportional share of `scc`'s current code count and COCOMO estimate.
- **Lifetime production:** commits and textual lines added or deleted by those email addresses across all branches.
- **Full leverage:** your share of COCOMO-estimated project effort divided by the calendar span between your first and last matching commits.
- **Timeline:** the same current, deduplicated personal effort allocated to periods according to authored textual lines added, with commits used when a repository has no textual additions. Each row shows that period's allocated output and rate plus the cumulative rate through that period.

Repository identities come from normalized Git remotes. SSH aliases, SSH URLs, and HTTPS URLs for the same remote collapse to one repository. Camp worktree directories are excluded, and duplicate checkouts report all of their Camp memberships. See [SPEC.md](SPEC.md) for the complete selection and calculation rules.

This is a comparative engineering metric for personal tracking. It is not a valuation, a productivity target, or a measure of hours worked.

The aggregate is a ratio, not a sum of Camp scores. It can be lower than one Camp's score when the additional repositories extend the overall first-to-last commit span more than they add estimated effort. The timeline makes that effect visible, and its final cumulative value equals the headline score.

The timeline is an allocation of today's owned COCOMO effort, not a claim about how large each repository was in the past. Reconstructing historical COCOMO snapshots would require checking out and rescanning every repository at each boundary. The report exposes this distinction in both text and JSON.

## Output and exit status

The text report includes the aggregate score, contribution totals, timeline, author identities, Camp and repository counts, and each scored repository. Dirty repositories and repos without a remote are labeled because they weaken reproducibility.

JSON output contains the same aggregate, timeline method and periods, and per-repository evidence. Local checkout paths and author email addresses are included, so review the file before publishing it.

The process exits:

- `0` when every selected Camp and repository was measured
- `2` for invalid arguments, missing dependencies, unknown Camps, unreadable data, failed Git or `scc` commands, or any incomplete scan

A partial scan may still print measured rows, but it is labeled incomplete and exits `2` so automation cannot mistake it for the full result.

## Develop

From a Camp workspace, `cgo leverage-all` navigates to this project; it does not calculate a report. Then run:

```sh
python3 -m unittest -v
python3 -m compileall -q camp_leverage_all.py
uv build
docker build -f tests/integration/Dockerfile -t camp-leverage-all-integration .
docker run --rm --network none camp-leverage-all-integration
docker run --rm --network none --entrypoint python camp-leverage-all-integration /app/tests/terminal/render_pty.py
```

The project has no runtime Python dependencies. GitHub Actions checks the supported Python versions on macOS and Linux, then runs the end-to-end deduplication fixture in an isolated container. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution and sign-off requirements.

Camp Leverage All is pre-1.0 software. Review [RELEASING.md](RELEASING.md) before changing repository visibility or publishing a release. Security reports should follow [SECURITY.md](SECURITY.md).

## License

Copyright 2026 Obedience Corp. Licensed under the [Apache License 2.0](LICENSE).
