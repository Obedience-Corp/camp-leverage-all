# Personal leverage across Camps

## User outcome

One command reports the user's cumulative personal leverage over all registered Camps. If `camp` is unavailable, a Camp cannot be read, a repository cannot be scored, or the selected author has no commits, the output explains the gap. The result is reproducible from its listed repositories and Git author addresses.

## Inputs and scope

- `camp list --format json` supplies registered Camps. The default includes every registered Camp, including demos and inactive Camps. `--camp` narrows the set by exact name or ID; `--campaign` remains a hidden compatibility alias.
- `camp project list --json` supplies each Camp's projects. Every call binds `CAMP_ROOT` to the Camp being scanned so the environment inherited through Camp's plugin dispatcher cannot pin discovery to the invoking Camp. Entries in `.campaign/leverage/config.json` override discovered projects with the same name or path; `include: false` excludes them and an explicit configured path is authoritative. Newly discovered projects remain eligible when the read-only config is stale. Worktree directories are excluded because they duplicate project checkouts.
- An email from `--author-email`, or `git config user.email` by default, seeds identity matching. `--author-name` selects an exact Git author name or Camp author-group key. Any identity group in a selected Camp's `authors.json` containing a known email or explicitly selected group name adds all its emails. Explicit Git names also discover their exact commit emails. Expansion repeats until stable across Camps, but labels of groups reached transitively never become Git-name selectors. Excluded groups do not contribute. The report lists the resulting emails, explicit names, matched groups, and matched Git identities.
- No Camp's leverage state is written. `scc` and Git are invoked directly; the script needs no service or Python dependencies.

## Repository identity and code scope

1. Resolve each eligible project to its Git top-level directory, following Camp linked-project symlinks outside the Camp root. A monorepo subproject resolves to the owning Git repository. A nested submodule with its own Git root remains a separate repo.
2. Normalize an `origin` remote (or Camp's project URL): SSH and HTTPS URLs for the same host and owner/repo map to one case-insensitive key. Resolve SSH `Host` aliases using `ssh -G` (local configuration only), then strip a trailing `.git`, slash, and URL credentials. If no remote exists, use the real Git common directory as a machine-local key. Report this weaker identity in the output.
3. For duplicate checkouts, prefer a standalone project over a monorepo child, then the checkout with the newest HEAD commit timestamp, then lexical path. Score one selected checkout per key. Report all Camp memberships and any discarded checkout paths.
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
personal_estimated_cost_usd = Σ(scc.estimatedCost × author_share)
```

The same deduplicated repository scopes also report current lines blamed to the selected emails, estimated current code LOC (`scc` code lines × author share), and lifetime textual lines added/deleted from matching commits. Git numstat omits binary line counts. These line measures are kept separate because currently owned lines and historical production answer different questions.

Cost uses the exact `estimatedCost` field from the same `scc` scan. Both personal and unscaled repository cost are retained, and only deduplicated personal costs enter the total. `--annual-wage` is a positive integer in USD (default 56286); `--overhead` is finite and positive (default 2.4). The plugin passes both to `scc` explicitly with the organic model and records them in `cost_model`. In `scc` 3.7, annual wage is integer-divided by 12 before multiplication by effort and overhead. Invalid or missing cost results make the repository scan incomplete rather than silently contributing zero. The default text report shows personal COCOMO effort and dollars in the headline, each repository, and the timeline (period and cumulative cost). Narrow terminals stack repository cost details on separate lines. Terminal dollars are rounded; JSON retains floating-point precision. Cost is an estimated development expense, not business value or realized savings.

The first and last author commit dates are merged across unique repositories before calculating the denominator. The script never sums Camp scores, per-project leverage ratios, or per-repo elapsed time. It matches Camp's current personal numerator and calendar-span denominator semantics. This is a COCOMO comparison for personal tracking, not a valuation or a measure of hours worked.

Because the result is a ratio over the combined commit span, adding a Camp does not guarantee a higher aggregate score. A newly included repository can extend the overall calendar span more than it increases estimated effort. The aggregate numerator, denominator, and dates are all reported so this behavior is explicit.

## Timeline

The timeline explains how the combined ratio develops across the full commit span. It does not reconstruct historical repository sizes. For each unique repository, the current `personal_estimated_pm` is allocated among months in proportion to the selected authors' textual lines added in those months. If that repository has no textual additions, its selected-author commits become the allocation basis. This preserves the deduplicated headline numerator while making the timing of production visible.

Periods partition the same calendar span used by the headline score. Each period reports authored commits and lines added/deleted, allocated person-months, allocated person-months divided by that period's calendar months, and the cumulative person-months divided by calendar months since the first matching commit. Empty periods remain visible with zero output. The last period's cumulative leverage equals `full_leverage`. The same weights allocate each repository's personal dollar cost; each period includes `estimated_cost_usd` and `cumulative_estimated_cost_usd`. Period cost sums to `summary.estimated_cost_usd`, and the final cumulative cost equals that headline total, within floating-point precision. Empty periods have zero cost. These are allocations of the current estimate, not historical spending or past wage rates.

With `--timeline auto`, spans up to 18 months use calendar months, spans up to 72 months use calendar quarters, and longer spans use calendar years. `--timeline month`, `quarter`, or `year` selects a fixed interval; `--timeline none` omits it.

JSON identifies the method as `current-owned-effort-allocated-by-authored-lines/v1`, records the fallback allocation basis, and sets `historical_snapshot` to `false`. A future snapshot mode would need to check out and run `scc` against each repository at historical boundaries; the current output does not imply that evidence exists.

## Failure and verification cases

- The same remote attached to two Camps contributes once and reports both memberships.
- SSH/HTTPS spellings of the same remote deduplicate. Different remotes remain separate even if names match.
- Parent monorepo and its nested Git submodule contribute once each; a monorepo child entry cannot add the parent's code a second time.
- One author using two configured emails gets one merged span. No matching commits is an error, not a zero denominator.
- Cost options reject zero, negative, nonfinite, or invalid inputs. Custom wage/overhead affect cost only; the deduplication and ownership rules remain identical.
- Timeline allocation sums to the aggregate estimated person-months, and its final cumulative rate equals the headline full leverage score.
- Missing project directories that still exist in the current Git tree, failed `scc` or blame scans, invalid JSON, and unreadable Camps produce an incomplete report and nonzero exit. A missing configured path absent from the current Git tree is reported as stale metadata and excluded.
- Unit tests cover identity, checkout selection, author expansion, aggregation, and timeline invariants. A live run validates registered Camp discovery and the final report; a two Camp fixture checks visible duplicate membership and the timeline endpoint.
