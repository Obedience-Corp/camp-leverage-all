# Cross-campaign personal leverage score

## User outcome

One command reports the user's cumulative personal leverage over all registered Camp campaigns. If `camp` is unavailable, a campaign cannot be read, a repository cannot be scored, or the selected author has no commits, the output explains the gap. The result is reproducible from its listed repositories and Git author addresses.

## Inputs and scope

- `camp list --format json` supplies registered campaigns. The default includes every registered campaign, including demos and inactive campaigns. `--campaign` narrows the set by exact name or ID.
- `camp project list --json` supplies each campaign's projects. Where `.campaign/leverage/config.json` has a nonempty `projects` map, only its entries with `include: true` are eligible; the config's explicit path is authoritative. Other projects use Camp discovery. Worktree directories are excluded in either case because they duplicate project checkouts.
- An email from `--author-email`, or `git config user.email` by default, seeds identity matching. `--author-name` selects an exact Git author name or Camp author-group key. Any identity group in a selected campaign's `authors.json` containing a known email or explicitly selected group name adds all its emails. Explicit Git names also discover their exact commit emails. Expansion repeats until stable across campaigns, but labels of groups reached transitively never become Git-name selectors. Excluded groups do not contribute. The report lists the resulting emails, explicit names, matched groups, and matched Git identities.
- No campaign's leverage state is written. `scc` and Git are invoked directly; the script needs no service or Python dependencies.

## Repository identity and code scope

1. Resolve each eligible project to its Git top-level directory, following Camp linked-project symlinks outside the campaign root. A monorepo subproject resolves to the owning Git repository. A nested submodule with its own Git root remains a separate repo.
2. Normalize an `origin` remote (or Camp's project URL): SSH and HTTPS URLs for the same host and owner/repo map to one case-insensitive key. Resolve SSH `Host` aliases using `ssh -G` (local configuration only), then strip a trailing `.git`, slash, and URL credentials. If no remote exists, use the real Git common directory as a machine-local key. Report this weaker identity in the output.
3. For duplicate checkouts, prefer a standalone project over a monorepo child, then the checkout with the newest HEAD commit timestamp, then lexical path. Score one selected checkout per key. Report all campaign memberships and any discarded checkout paths.
4. `scc --format json2 --cocomo-project-type organic` scans the selected Git root. Apply Camp's standard generated/vendor/worktree directory exclusions. `scc`'s default `.gitmodules` exclusion keeps nested submodule code out of the parent. Blame uses Git-tracked files with the same directory exclusions.
5. Dirty checkouts are shown as such because `scc` scans current files while Git blame and commit dates use repository history. A remote-less clone cannot be equated to another clone without evidence, so any potential duplicate remains separately listed.

## Calculation

For every unique repo in which the author has at least one commit:

```
repo_estimated_pm = scc.estimatedPeople × scc.estimatedScheduleMonths
author_share = lines currently blamed on selected emails / all blamed lines
personal_estimated_pm = Σ(repo_estimated_pm × author_share)
actual_pm = max(0.1, (latest selected-author commit - earliest selected-author commit) / 30.44 days)
full_leverage = personal_estimated_pm / actual_pm
```

The same deduplicated repository scopes also report current lines blamed to the selected emails, estimated current code LOC (`scc` code lines × author share), and lifetime textual lines added/deleted from matching commits. Git numstat omits binary line counts. These line measures are kept separate because currently owned lines and historical production answer different questions.

The first and last author commit dates are merged across unique repositories before calculating the denominator. The script never sums campaign scores, per-project leverage ratios, or per-repo elapsed time. It matches Camp's current personal numerator and calendar-span denominator semantics. This is a COCOMO comparison for personal tracking, not a valuation or a measure of hours worked.

## Failure and verification cases

- The same remote attached to two campaigns contributes once and reports both memberships.
- SSH/HTTPS spellings of the same remote deduplicate. Different remotes remain separate even if names match.
- Parent monorepo and its nested Git submodule contribute once each; a monorepo child entry cannot add the parent's code a second time.
- One author using two configured emails gets one merged span. No matching commits is an error, not a zero denominator.
- Missing project directories that still exist in the current Git tree, failed `scc` or blame scans, invalid JSON, and unreadable campaigns produce an incomplete report and nonzero exit. A missing configured path absent from the current Git tree is reported as stale metadata and excluded.
- Unit tests cover identity, checkout selection, author expansion, and aggregation. A live run validates registered campaign discovery and the final report; a two-campaign run checks visible duplicate membership.
