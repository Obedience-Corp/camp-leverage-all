# Campaign Leverage

Calculate a personal leverage score across registered Camp campaigns without counting a project repository more than once.

```sh
python3 campaign_leverage.py
python3 campaign_leverage.py --author-email lance@work.example --json
python3 campaign_leverage.py --author-name obey-agent --author-name obey-veronica
python3 campaign_leverage.py --campaign obey-campaign --campaign My_Tools
```

The default author email is `git config user.email`. Every `--author-email` adds an address to that default and to addresses found in campaign author configurations. Repeat `--author-name` to select an exact Git author name or a Camp author-group key such as `obey-agent`. The script expands matching identity groups from each campaign's `.campaign/leverage/authors.json`, discovers emails used by explicitly selected Git names, then matches Git commits and blame by exact email. Transitive group labels do not become Git-name selectors, which prevents a similarly named test or third-party group from widening the identity. It requires `camp`, `git`, and `scc` on `PATH`; it uses only the Python standard library.

The report shows the full score, estimated and actual person-months, current blamed lines, estimated current code LOC, lifetime lines added and deleted, matching commits, unique repository count, campaign count, and each included repo. Current blamed lines are exact Git attribution across tracked text files. Estimated current code LOC applies that ownership share to `scc`'s code-line count. Lifetime additions and deletions come from Git numstat and exclude binary files. `--json` provides the same data for automation. A skipped repo or an unavailable campaign is reported explicitly. The command exits nonzero when discovery or scoring is incomplete, so its score cannot be mistaken for a complete result.

See [SPEC.md](SPEC.md) for the calculation and selection rules.
