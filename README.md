<h1 align="center">Camp Leverage All</h1>

<p align="center"><strong>Your engineering output across every Camp, counted once.</strong></p>

<p align="center">
  <a href="https://github.com/Obedience-Corp/camp-leverage-all/actions/workflows/ci.yml"><img src="https://github.com/Obedience-Corp/camp-leverage-all/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-F2721C" alt="Python 3.11 or newer">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-F2721C" alt="Apache 2.0 license"></a>
</p>

<p align="center">
  <a href="https://gist.github.com/lancekrogers/aef8af6ab81b974660c262d80326eeeb"><img src="https://gist.githubusercontent.com/lancekrogers/aef8af6ab81b974660c262d80326eeeb/raw/camp-leverage-all-030.gif" width="960" alt="Camp Leverage All terminal report showing COCOMO effort and dollars in the headline, timeline, and repository breakdown"></a>
</p>

<p align="center"><em>Recorded from the real CLI with two sanitized Camps; the shared repository is counted once and the cumulative timeline ends at the headline score and dollar total.</em></p>

Camp Leverage All is an experimental Python plugin for Camp. It discovers registered Camps and projects, joins your configured Git identities, and calculates one personal leverage score with each repository counted once across checkouts and worktrees.

| Deduplicated | Identity-aware | Time-aware |
| --- | --- | --- |
| One remote contributes once across every Camp and checkout. | Personal, work, bot, and agent emails can resolve into one author set. | The report shows period output, period rate, and cumulative leverage through time. |

The exact result depends on your repositories and author identities. Camp Leverage All reads Git history, Camp configuration, and project files to produce its report.

> **Status:** Camp Leverage All is pre-1.0 software. Its calculation contract is documented, but its command and output schemas may evolve before 1.0.

## Quick start

Install [Festival](https://github.com/Obedience-Corp/festival) first; it supplies Camp and the plugin installer. Release archives bundle Python and `scc` 3.7. Git must be available on `PATH`. On macOS:

```sh
brew install --cask Obedience-Corp/tap/festival
festival doctor
```

Install the plugin through the **Festival TUI**:

1. Run `festival` to open the TUI.
2. Open **Browse catalog** and select `obedience-corp/camp-leverage-all`.
3. Press **Enter** to install it and wait for **Install complete**.
4. Quit Festival and run the plugin through Camp:

```sh
camp leverage-all
```

![Festival TUI installs Camp Leverage All from the signed official marketplace, then camp leverage-all reports version 0.3.0](https://gist.githubusercontent.com/lancekrogers/53a3f2955c0af0aaeb119256c86dc05d/raw/camp-leverage-all-festival-install-official.gif)

*Recorded with the released Festival TUI in a fresh home against the signed official marketplace; the catalog entry and its signature are verified by the key built into Festival.*

That first report scans every registered Camp, combines your configured Git identities, and counts each repository once. **COCOMO effort and dollars appear by default in the headline, timeline, and repository breakdown.** It shows estimated period rates and a cumulative average. See [Reading the timeline](#reading-the-timeline) for the column definitions and how those estimates are calculated.

Festival supplies the Camp registry and discovers the plugin executable on `PATH`. Camp launches the plugin as a separate, read-only program.

| Command | Scope | State |
| --- | --- | --- |
| `camp leverage-all` | All registered Camps by default | Read-only plugin with repository deduplication |
| `camp leverage` | Projects in the current Camp | Maintains configuration, cache, snapshots, and history in `.campaign/leverage/` |

The package installs the `camp-leverage-all` executable. Camp's plugin dispatcher exposes it as `camp leverage-all`, keeping it distinct from the native `camp leverage` command.

For npm, pnpm, bun, Linux packages, or release archives, install Festival using its [installation guide](https://github.com/Obedience-Corp/festival#install), then choose the plugin in the Festival catalog. Festival's [navigation guide](https://github.com/Obedience-Corp/festival#navigation) explains optional shell commands such as `cgo`.

### Install from source

If you prefer not to use the Festival catalog, install version `0.3.0` with [`uv`](https://docs.astral.sh/uv/getting-started/installation/). This source installation uses Python 3.11+ and `scc` 3.7+ from your machine:

```sh
brew install scc  # macOS; use your package manager on Linux
uv tool install --force git+https://github.com/Obedience-Corp/camp-leverage-all.git@v0.3.0
camp leverage-all
```

Use the same command to replace an older installation with this release. Release and marketplace steps are tracked in [RELEASING.md](RELEASING.md).

## Who it works for

Camp Leverage All works for any Festival user with one or more Camps registered on the machine. It discovers identities and projects from your own Git and Camp configuration.

By default, it starts with `git config user.email`. If a Camp has `.campaign/leverage/authors.json`, matching identity groups expand that email to the user's other personal, work, bot, or agent addresses. Users without an author file still get a report for their configured Git email. The repeatable `--author-email` and `--author-name` options cover additional identities without changing Camp state.

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

The default report includes a timeline (`--timeline auto`). It chooses monthly buckets for spans up to 18 months, quarters up to 72 months, and years for longer histories. Override the interval or explicitly hide the table when needed:

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

The report includes these measures of your work:

- **Current ownership:** lines currently attributed to your email addresses by `git blame`, plus your proportional share of `scc`'s current code count and COCOMO estimate.
- **Lifetime production:** commits and textual lines added or deleted by those email addresses across all branches.
- **Estimated COCOMO cost (USD):** the sum of each unique repository’s `scc` cost estimate, scaled to your share of current ownership. The headline, timeline, and repository breakdown include this dollar estimate.
- **Full leverage:** your share of COCOMO-estimated project effort divided by the calendar span between your first and last matching commits.
- **Timeline:** the same current, deduplicated personal effort allocated to periods according to authored textual lines added, with commits used when a repository has no textual additions. Each row shows that period's allocated output and rate plus the cumulative rate through that period.

Repository identities come from normalized Git remotes. SSH aliases, SSH URLs, and HTTPS URLs for the same remote collapse to one repository. Camp worktree directories are excluded, and duplicate checkouts report all of their Camp memberships. See [SPEC.md](SPEC.md) for the complete selection and calculation rules.

Use this comparative engineering metric to track estimated development effort alongside your actual code contributions and calendar span.

### Estimated dollar cost

The headline dollar total estimates the development cost of your share of the current code, using the organic COCOMO model. It uses the same selected authors and deduplicated repositories as the leverage score. Shared repos and worktrees cannot add their cost twice.

Defaults match `scc`: **$56,286 annual wage and 2.4× overhead**. Both assumptions appear below the total. Set your own assumptions with:

```sh
camp leverage-all --annual-wage 120000 --overhead 2.4
```

The plugin reads `scc.estimatedCost` directly and multiplies it by your ownership share. `scc` 3.7 computes cost as estimated person-months × truncated monthly wage × overhead; its default monthly wage is $4,690. The dollar figure represents modeled development cost under the displayed wage and overhead assumptions. Changing wage or overhead changes dollars without changing leverage, LOC, or author ownership.

JSON records the assumptions in `cost_model`, the total in `summary.estimated_cost_usd`, and each repository’s personal and whole-repo estimates in `estimated_cost_usd` and `unscaled_estimated_cost_usd`. Values retain full precision in JSON; terminal dollars are rounded for display.

### Why can one Camp score higher than all Camps?

The headline `full leverage` is an all-time average: estimated effort divided by the calendar span between the earliest and latest matching commits. **That span includes quiet periods and gaps between projects.** Adding an older repository can increase the denominator faster than it increases estimated effort.

For example, using illustrative values:

| Scope | Estimated effort | Calendar span | Score |
| --- | ---: | ---: | ---: |
| One recent Camp | 600 person-months | 12 months | 50× |
| All Camps, including older repos | 900 person-months | 36 months | 25× |

The combined scope has more estimated output, but averages it over three times as long. Total output rises while the lifetime average falls. Compare Camp scores over consistent date spans, authors, repository scopes, and calculation rules. Summing individual Camp scores would count shared repositories and overlapping work more than once.

### Reading the timeline

Run `camp leverage-all` to see the timeline in the default report. Use `camp leverage-all --timeline month` for monthly detail regardless of history length.

| Column | Meaning |
| --- | --- |
| `PERIOD` | Calendar month, quarter, or year. |
| `ADDED` | Selected authors' textual lines added during that period, across deduplicated repositories. |
| `OUTPUT` | Current estimated effort allocated to that period, in person-months (`PM`). |
| `COST USD` | Current estimated cost allocated to that period using the same weights as `OUTPUT`. |
| `CUM. USD` | Allocated cost through that period. Its final value equals the headline dollar total. |
| `RATE` | That period's allocated output divided by its calendar duration in months. |
| `CUMULATIVE` | Output allocated through that period divided by the calendar span since the first matching commit. Its final value equals the headline score. |

On narrower terminals, period and cumulative dollars appear on a second line for each period.

Use `RATE` to compare the estimated pace between periods. `CUMULATIVE` includes the earlier history, so a recent period can have a high rate while the cumulative average stays much lower. First and last periods cover only the portion within the matching commit span; durations use a minimum of 0.1 month. Period boundaries are in UTC.

**The timeline allocates today’s code estimate across your commit history.** For each repository, the tool distributes today's author-owned COCOMO effort and cost among periods in proportion to the selected authors' textual lines added. It uses commit counts when that repository has no textual additions. Because the allocation uses current code size and ownership, changes to today’s code can change earlier timeline estimates on a later run.

Measuring historical snapshots would require reconstructing each repository at every period boundary. The current allocation method is identified in JSON with `historical_snapshot: false`.

## Output and exit status

The text report includes the aggregate score, estimated dollar cost and its assumptions, contribution totals, timeline, author identities, Camp and repository counts, and each scored repository. Dirty repositories and repos without a remote are labeled because they weaken reproducibility.

JSON output contains the same aggregate, timeline method and periods, and per-repository evidence. Local checkout paths and author email addresses are included, so review the file before publishing it.

The process exits:

- `0` when every selected Camp and repository was measured
- `2` for invalid arguments, missing dependencies, unknown Camps, unreadable data, failed Git or `scc` commands, or any incomplete scan

A partial scan may still print measured rows, but it is labeled incomplete and exits `2` so automation cannot mistake it for the full result.

## Develop

Source installation is for contributors. From a clone, install an editable copy with [`uv`](https://docs.astral.sh/uv/getting-started/installation/):

```sh
uv tool install --editable .
```

This installs the `camp-leverage-all` executable for development. For a tagged installation, follow the quick start above.

From a Camp workspace, `cgo leverage-all` navigates to this project. Run `camp leverage-all` to calculate a report. To verify development changes:

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
