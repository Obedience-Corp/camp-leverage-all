# Campaign Leverage

Calculate a personal leverage score across registered Camp campaigns without counting a project repository more than once.

```sh
python3 campaign_leverage.py
python3 campaign_leverage.py --author-email lance@work.example --json
python3 campaign_leverage.py --campaign obey-campaign --campaign My_Tools
```

The default author email is `git config user.email`. Repeat `--author-email` to add addresses absent from campaign author configurations. The script expands matching identity groups from each campaign's `.campaign/leverage/authors.json`, then matches Git commits and blame by exact email. It requires `camp`, `git`, and `scc` on `PATH`; it uses only the Python standard library.

The report shows the full score, estimated and actual person-months, unique repository count, campaign count, and each included repo. `--json` provides the same data for automation. A skipped repo or an unavailable campaign is reported explicitly. The command exits nonzero when discovery or scoring is incomplete, so its score cannot be mistaken for a complete result.

See [SPEC.md](SPEC.md) for the calculation and selection rules.
