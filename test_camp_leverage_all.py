import argparse
import io
import subprocess
import tomllib
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import camp_leverage_all as leverage


class LeverageTests(unittest.TestCase):
    def checkout(self, key, path, camp, *, standalone=True, head_time=1):
        return leverage.Checkout(
            key, Path(path), Path(path), camp, path, standalone, head_time, False
        )

    def report(self):
        return {
            "complete": True,
            "camp_count": 2,
            "unique_repository_count": 1,
            "discovered_repository_count": 1,
            "author_emails": ["developer@example.com"],
            "author_names": ["automation-agent"],
            "author_groups": ["automation-agent", "developer"],
            "matched_git_identities": [],
            "cost_model": {
                "annual_wage_usd": 56_286, "overhead_multiplier": 2.4,
            },
            "summary": {
                "full_leverage": 12.5,
                "estimated_person_months": 50.0, "estimated_cost_usd": 562_800.0,
                "actual_person_months": 4.0,
                "first_commit": "2026-01-01T00:00:00+00:00",
                "last_commit": "2026-05-01T00:00:00+00:00",
                "commit_count": 42,
                "lines_added": 12_345,
                "lines_deleted": 2_345,
                "current_owned_lines": 8_765,
                "estimated_current_code_lines": 7_654,
                "current_code_lines": 10_000,
            },
            "timeline": {
                "interval": "quarter",
                "periods": [{
                    "label": "2026 Q1",
                    "lines_added": 4_321,
                    "estimated_person_months": 20.0, "estimated_cost_usd": 225_120.0,
                    "cumulative_estimated_cost_usd": 225_120.0,
                    "full_leverage": 6.7,
                    "cumulative_leverage": 6.7,
                }],
            },
            "repositories": [{
                "repository": "remote:github.com/example/shared-platform",
                "estimated_person_months": 50.0, "estimated_cost_usd": 562_800.0,
                "camps": ["Client Work", "Studio"],
                "dirty": False,
                "weak_identity": False,
            }],
            "errors": [],
            "warnings": [],
        }

    def test_remote_identity_deduplicates_ssh_and_https(self):
        self.assertEqual(
            leverage.normalize_remote("git@github.com:Obedience-Corp/camp.git"),
            leverage.normalize_remote("https://github.com/obedience-corp/CAMP/"),
        )
        self.assertNotEqual(
            leverage.normalize_remote("git@github.com:someone/camp.git"),
            leverage.normalize_remote("git@github.com:Obedience-Corp/camp.git"),
        )

    def test_ssh_alias_resolves_to_same_repo_as_https(self):
        with patch.object(leverage, "canonical_ssh_host", return_value="github.com"):
            self.assertEqual(
                leverage.normalize_remote("git@github-work:Obedience-Corp/camp.git"),
                leverage.normalize_remote("https://github.com/Obedience-Corp/camp.git"),
            )

    def test_checkout_selection_prefers_direct_and_keeps_membership(self):
        group = [
            self.checkout("remote:github.com/o/repo", "/nested", "A", standalone=False, head_time=9),
            self.checkout("remote:github.com/o/repo", "/direct", "B", head_time=3),
        ]
        selected = leverage.select_checkouts(group)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0][0].scan_path, Path("/direct"))
        self.assertEqual({c.camp for c in selected[0][1]}, {"A", "B"})

    def test_email_aliases_expand_across_camps_and_skip_excluded(self):
        configs = [
            {"authors": {"developer": {"emails": ["one@example.com", "two@example.com"]}}},
            {"authors": {"founder": {"emails": ["two@example.com", "three@example.com"]},
                         "bot": {"emails": ["three@example.com", "bot@example.com"], "exclude": True}}},
        ]
        self.assertEqual(
            leverage.expand_author_emails({"ONE@example.com"}, configs),
            {"one@example.com", "two@example.com", "three@example.com"},
        )

    def test_author_group_name_expands_agent_emails_across_camps(self):
        configs = [
            {"authors": {"automation-agent": {"emails": ["agent@corp.example"]}}},
            {"authors": {"automation": {"emails": ["agent@corp.example", "agent@users.noreply.github.com"]}}},
        ]
        emails, groups = leverage.expand_author_identity(set(), {"Automation-Agent"}, configs)
        self.assertEqual(
            emails,
            {"agent@corp.example", "agent@users.noreply.github.com"},
        )
        self.assertIn("automation-agent", groups)
        self.assertIn("automation", groups)

    def test_transitive_group_label_does_not_become_a_git_name_selector(self):
        configs = [{"authors": {
            "primary-developer": {"emails": ["me@example.com"]},
            "primary-developer-fixture": {"emails": ["fixture@test"]},
        }}]
        emails, groups = leverage.expand_author_identity({"me@example.com"}, set(), configs)
        pairs = {("primary-developer", "fixture@test")}
        self.assertEqual(emails, {"me@example.com"})
        self.assertEqual(groups, {"primary-developer"})
        self.assertEqual(
            leverage.discover_named_author_emails(emails, set(), pairs),
            {"me@example.com"},
        )

    def test_selected_git_name_discovers_all_of_its_emails(self):
        pairs = {
            ("automation-agent", "one@example.com"),
            ("Automation-Agent", "two@example.com"),
            ("someone else", "other@example.com"),
        }
        self.assertEqual(
            leverage.discover_named_author_emails(set(), {"automation-agent"}, pairs),
            {"one@example.com", "two@example.com"},
        )

    def test_author_discovery_falls_back_when_git_lacks_pcre(self):
        with patch.object(
            leverage,
            "command",
            side_effect=[
                leverage.ScanError("Git was built without support for Perl-compatible regexes"),
                "Example Developer\tdeveloper@example.com",
            ],
        ) as run:
            pairs = leverage.git_author_pairs(
                {Path("/repo")}, {"developer@example.com"}, set(),
            )
        self.assertEqual(pairs, {("Example Developer", "developer@example.com")})
        self.assertEqual(run.call_count, 2)

    def test_explicit_email_adds_to_git_default(self):
        self.assertEqual(
            leverage.seed_author_emails(["local@example.com"], "default@example.com"),
            {"local@example.com", "default@example.com"},
        )

    def test_history_stats_count_only_selected_author_text_lines(self):
        output = """@@CAMP_LEVERAGE@@me@example.com\t2026-01-01T00:00:00+00:00

10\t2\tone.py
-\t-\timage.png
@@CAMP_LEVERAGE@@other@example.com\t2026-01-02T00:00:00+00:00

50\t4\tother.py
@@CAMP_LEVERAGE@@me@example.com\t2026-02-01T00:00:00+00:00

7\t1\ttwo.py
99\t8\tvendor/generated.go
"""
        with patch.object(leverage, "command", return_value=output):
            stats = leverage.author_history_stats(Path("/repo"), Path("/repo"), {"me@example.com"})
        self.assertEqual(stats["commit_count"], 2)
        self.assertEqual(stats["lines_added"], 17)
        self.assertEqual(stats["lines_deleted"], 3)
        self.assertEqual(stats["first_commit"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(stats["last_commit"], "2026-02-01T00:00:00+00:00")
        self.assertEqual(stats["activity"], [
            {"month": "2026-01", "commit_count": 1, "lines_added": 10, "lines_deleted": 2},
            {"month": "2026-02", "commit_count": 1, "lines_added": 7, "lines_deleted": 1},
        ])

    def test_aggregate_unions_calendar_span_instead_of_summing_repo_effort(self):
        rows = [
            {"estimated_person_months": 12, "estimated_cost_usd": 135072.0, "first_commit": "2026-01-01T00:00:00+00:00", "last_commit": "2026-02-01T00:00:00+00:00"},
            {"estimated_person_months": 18, "estimated_cost_usd": 202608.0, "first_commit": "2026-01-15T00:00:00+00:00", "last_commit": "2026-03-01T00:00:00+00:00"},
        ]
        result = leverage.aggregate(rows)
        self.assertAlmostEqual(result["estimated_person_months"], 30)
        self.assertEqual(result["estimated_cost_usd"], 337_680.0)
        self.assertAlmostEqual(result["actual_person_months"], 59 / 30.44)
        self.assertAlmostEqual(result["full_leverage"], 30 / (59 / 30.44))

    def test_aggregate_ratio_can_be_lower_than_a_single_camp_ratio(self):
        recent = {
            "estimated_person_months": 100, "estimated_cost_usd": 1125600.0,
            "first_commit": "2026-02-01T00:00:00+00:00",
            "last_commit": "2026-03-01T00:00:00+00:00",
        }
        older = {
            "estimated_person_months": 10, "estimated_cost_usd": 112560.0,
            "first_commit": "2025-03-01T00:00:00+00:00",
            "last_commit": "2025-04-01T00:00:00+00:00",
        }
        self.assertLess(
            leverage.aggregate([recent, older])["full_leverage"],
            leverage.aggregate([recent])["full_leverage"],
        )

    def test_timeline_allocates_effort_and_ends_at_full_score(self):
        rows = [{
            "estimated_person_months": 120.0, "estimated_cost_usd": 1350720.0,
            "first_commit": "2025-01-15T00:00:00+00:00",
            "last_commit": "2026-04-15T00:00:00+00:00",
            "commit_count": 3,
            "lines_added": 120,
            "lines_deleted": 12,
            "activity": [
                {"month": "2025-01", "commit_count": 1, "lines_added": 20, "lines_deleted": 2},
                {"month": "2025-07", "commit_count": 1, "lines_added": 40, "lines_deleted": 4},
                {"month": "2026-04", "commit_count": 1, "lines_added": 60, "lines_deleted": 6},
            ],
        }]
        timeline = leverage.build_timeline(rows)
        self.assertAlmostEqual(
            sum(period["estimated_cost_usd"] for period in timeline["periods"]),
            leverage.aggregate(rows)["estimated_cost_usd"],
        )
        self.assertAlmostEqual(
            timeline["periods"][-1]["cumulative_estimated_cost_usd"],
            leverage.aggregate(rows)["estimated_cost_usd"],
        )
        self.assertEqual(timeline["periods"][1]["estimated_cost_usd"], 0.0)
        self.assertEqual(timeline["interval"], "month")
        self.assertFalse(timeline["historical_snapshot"])
        self.assertAlmostEqual(
            sum(period["estimated_person_months"] for period in timeline["periods"]),
            120.0,
        )
        self.assertAlmostEqual(
            timeline["periods"][-1]["cumulative_leverage"],
            leverage.aggregate(rows)["full_leverage"],
        )

    def test_auto_timeline_uses_quarters_for_multi_year_span(self):
        first = leverage.datetime.fromisoformat("2023-06-01T00:00:00+00:00")
        last = leverage.datetime.fromisoformat("2026-09-01T00:00:00+00:00")
        self.assertEqual(leverage.resolved_timeline_interval(first, last, "auto"), "quarter")
        self.assertEqual(leverage.resolved_timeline_interval(first, last, "year"), "year")

    def test_timeline_can_be_disabled(self):
        self.assertIsNone(leverage.build_timeline([{
            "estimated_person_months": 1.0, "estimated_cost_usd": 11256.0,
            "first_commit": "2026-01-01T00:00:00+00:00",
            "last_commit": "2026-02-01T00:00:00+00:00",
        }], "none"))

    def test_no_author_commits_is_an_error(self):
        with self.assertRaisesRegex(leverage.ScanError, "no selected-author commits"):
            leverage.aggregate([])

    def test_explicit_worktree_entry_cannot_duplicate_project_code(self):
        config = {"projects": {
            "app": {"path": "projects/app", "include": True},
            "worktrees": {"path": "projects/worktrees", "include": True},
        }}
        with (
            patch.object(leverage, "json_command", return_value=[]),
            patch.object(leverage, "json_file", return_value=config),
        ):
            entries = leverage.project_entries(Path("/camp"))
        self.assertEqual([entry["Name"] for entry in entries], ["app"])

    def test_project_discovery_rebinds_inherited_plugin_camp_root(self):
        root = Path("/registered/camp")
        with (
            patch.object(leverage, "json_command", return_value=[]) as run,
            patch.object(leverage, "json_file", return_value={}),
        ):
            self.assertEqual(leverage.project_entries(root), [])
        run.assert_called_once_with(
            "camp", "project", "list", "--json", cwd=root,
            environment={"CAMP_ROOT": str(root)},
        )

    def test_newly_discovered_projects_are_not_hidden_by_stale_config(self):
        config = {"projects": {
            "configured": {"path": "projects/configured", "include": True},
            "excluded": {"path": "projects/excluded", "include": False},
        }}
        discovered = [
            {"Name": "configured", "Path": "projects/configured"},
            {"Name": "excluded", "Path": "projects/excluded"},
            {"Name": "new-project", "Path": "projects/new-project"},
        ]
        with (
            patch.object(leverage, "json_command", return_value=discovered),
            patch.object(leverage, "json_file", return_value=config),
        ):
            entries = leverage.project_entries(Path("/camp"))
        self.assertEqual(
            [entry["Name"] for entry in entries],
            ["configured", "new-project"],
        )

    def test_score_scales_cocomo_effort_by_exact_email_ownership(self):
        checkout = self.checkout("remote:github.com/o/repo", "/repo", "A")
        history = {
            "commit_count": 2,
            "lines_added": 30,
            "lines_deleted": 5,
            "first_commit": "2026-01-01T00:00:00+00:00",
            "last_commit": "2026-02-01T00:00:00+00:00",
        }
        with (
            patch.object(leverage, "author_history_stats", return_value=history),
            patch.object(leverage, "json_command", return_value={
                "estimatedPeople": 4,
                "estimatedCost": 225_120.0,
                "estimatedScheduleMonths": 5,
                "languageSummary": [{"Code": 80}],
            }),
            patch.object(leverage, "blame_counts", return_value={"me@example.com": 25, "other@example.com": 75}),
            patch.object(leverage, "command", return_value=""),
        ):
            row = leverage.score_checkout(checkout, {"me@example.com"})
        self.assertAlmostEqual(row["estimated_person_months"], 5)
        self.assertEqual(row["estimated_cost_usd"], 56_280.0)
        self.assertEqual(row["unscaled_estimated_cost_usd"], 225_120.0)
        self.assertAlmostEqual(row["author_share"], .25)
        self.assertEqual(row["estimated_owned_code_lines"], 20)
        self.assertEqual(row["lines_added"], 30)

    def test_positive_int_rejects_zero_workers(self):
        self.assertEqual(leverage.positive_int("3"), 3)
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "at least 1"):
            leverage.positive_int("0")

    def test_camp_flag_keeps_hidden_legacy_alias(self):
        parser = leverage.build_parser()
        args = parser.parse_args(["--camp", "Studio", "--campaign", "Client Work"])
        self.assertEqual(args.camps, ["Studio", "Client Work"])
        self.assertIn("--camp", parser.format_help())
        self.assertNotIn("--campaign", parser.format_help())
        self.assertEqual(args.timeline, "auto")

    def test_dependency_check_reports_every_missing_command(self):
        with patch.object(leverage.shutil, "which", side_effect=lambda name: None if name != "git" else "/usr/bin/git"):
            self.assertEqual(leverage.missing_commands(), ["camp", "scc"])

    def test_command_timeout_is_a_scan_error(self):
        with patch.object(
            leverage.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=("git", "status"), timeout=1),
        ), self.assertRaisesRegex(leverage.ScanError, "git timed out"):
            leverage.command("git", "status")

    def test_cost_options_reject_invalid_values(self):
        parser = leverage.build_parser()
        for flag, values in (
            ("--annual-wage", ("0", "-1", "1.5", "NaN")),
            ("--overhead", ("0", "-1", "NaN", "inf", "-inf")),
        ):
            for value in values:
                with self.subTest(flag=flag, value=value), patch("sys.stderr", io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        parser.parse_args([f"{flag}={value}"])
                    self.assertEqual(exc.exception.code, 2)
        args = parser.parse_args(["--annual-wage", "120000", "--overhead", "1.5"])
        self.assertEqual(args.annual_wage, 120000)
        self.assertEqual(args.overhead, 1.5)

    def test_invalid_scc_cost_does_not_become_a_plausible_total(self):
        for value in (-1, float("nan"), float("inf")):
            with (
                self.subTest(value=value),
                patch.object(leverage, "author_history_stats", return_value={"commit_count": 1}),
                patch.object(leverage, "json_command", return_value={
                    "estimatedPeople": 1, "estimatedScheduleMonths": 1, "estimatedCost": value,
                }),
                self.assertRaisesRegex(leverage.ScanError, "invalid estimated cost"),
            ):
                leverage.score_checkout(self.checkout("key", "/repo", "camp"), {"me@example.com"})

    def test_custom_cost_assumptions_are_passed_to_scc_and_scaled_by_ownership(self):
        with (
            patch.object(leverage, "author_history_stats", return_value={"commit_count": 1}),
            patch.object(leverage, "json_command", return_value={
                "estimatedPeople": 1, "estimatedScheduleMonths": 1, "estimatedCost": 15000,
            }) as scc,
            patch.object(leverage, "blame_counts", return_value=Counter({
                "me@example.com": 1, "other@example.com": 3,
            })),
            patch.object(leverage, "command", return_value=""),
        ):
            row = leverage.score_checkout(
                self.checkout("key", "/repo", "camp"), {"me@example.com"},
                annual_wage=120000, overhead=1.5,
            )
        self.assertEqual(row["estimated_cost_usd"], 3750)
        argv = scc.call_args.args
        self.assertEqual(argv[argv.index("--avg-wage") + 1], "120000")
        self.assertEqual(argv[argv.index("--overhead") + 1], "1.5")

    def test_cost_timeline_falls_back_to_commits_when_no_lines_were_added(self):
        row = {
            "estimated_person_months": 3, "estimated_cost_usd": 30000,
            "first_commit": "2026-01-01T00:00:00+00:00",
            "last_commit": "2026-03-01T00:00:00+00:00",
            "activity": [
                {"month": "2026-01", "commit_count": 1},
                {"month": "2026-03", "commit_count": 2},
            ],
        }
        periods = leverage.build_timeline([row])["periods"]
        self.assertEqual([p["estimated_cost_usd"] for p in periods], [10000, 0, 20000])
        self.assertEqual(periods[-1]["cumulative_estimated_cost_usd"], 30000)

    def test_scc_minimum_version_is_enforced(self):
        with (
            patch.object(leverage, "command", return_value="scc version 3.6.0"),
            self.assertRaisesRegex(leverage.ScanError, "3.7 or newer"),
        ):
            leverage.validate_scc_version()
        with patch.object(leverage, "command", return_value="scc version 4.0.1"):
            leverage.validate_scc_version()

    def test_frozen_commands_restore_external_library_environment(self):
        with (
            patch.object(leverage.sys, "frozen", True, create=True),
            patch.dict(leverage.os.environ, {
                "LD_LIBRARY_PATH": "/bundle", "LD_LIBRARY_PATH_ORIG": "/system",
                "LIBPATH": "/bundle", "CAMP_ROOT": "/invoking-camp",
            }, clear=True),
        ):
            environment = leverage.command_environment({"CAMP_ROOT": "/selected-camp"})
            self.assertEqual(environment["LD_LIBRARY_PATH"], "/system")
            self.assertNotIn("LIBPATH", environment)
            self.assertEqual(environment["CAMP_ROOT"], "/selected-camp")
            self.assertEqual(leverage.os.environ["LD_LIBRARY_PATH"], "/bundle")

    def test_source_commands_preserve_user_library_environment(self):
        with patch.dict(leverage.os.environ, {"LD_LIBRARY_PATH": "/user"}, clear=True):
            self.assertEqual(leverage.command_environment()["LD_LIBRARY_PATH"], "/user")

    def test_package_and_cli_versions_match(self):
        metadata = tomllib.loads(Path(__file__).with_name("pyproject.toml").read_text())
        self.assertEqual(metadata["project"]["version"], leverage.VERSION)
        self.assertEqual(
            metadata["project"]["scripts"],
            {"camp-leverage-all": "camp_leverage_all:main"},
        )

    def test_wide_terminal_report_has_hierarchy_and_repository_table(self):
        output = io.StringIO()
        errors = io.StringIO()
        leverage.render_text_report(
            self.report(), stream=output, error_stream=errors, color="never", width=96,
        )
        rendered = output.getvalue()
        self.assertIn("CAMP LEVERAGE ALL", rendered)
        self.assertIn("12.5×  full leverage", rendered)
        self.assertIn("CONTRIBUTION", rendered)
        self.assertIn("$562,800  estimated COCOMO cost (USD)", rendered)
        self.assertIn("COST USD", rendered)
        self.assertIn("CUM. USD", rendered)
        self.assertIn("$225,120", rendered)
        self.assertIn("TIMELINE · QUARTER", rendered)
        self.assertIn("2026 Q1", rendered)
        self.assertIn("REPOSITORY", rendered)
        repositories = rendered.split("REPOSITORIES", 1)[1].split("IDENTITY", 1)[0]
        self.assertIn("COST USD", repositories)
        self.assertIn("$562,800", repositories)
        self.assertIn("github.com/example/shared-platform", rendered)
        self.assertNotIn("remote:", rendered)
        self.assertNotIn("\033[", rendered)
        self.assertEqual(errors.getvalue(), "")
        self.assertLessEqual(max(map(len, rendered.splitlines())), 96)

    def test_narrow_terminal_report_stacks_repository_details(self):
        output = io.StringIO()
        leverage.render_text_report(
            self.report(), stream=output, error_stream=io.StringIO(), color="never", width=58,
        )
        rendered = output.getvalue()
        self.assertNotIn("EFFORT", rendered)
        self.assertIn("$225,120 period · $225,120 cumulative USD", rendered)
        self.assertIn("github.com/example/shared-platform\n    50.0 PM · $562,800 USD\n    Client Work, Studio", rendered)
        self.assertLessEqual(max(map(len, rendered.splitlines())), 58)

    def test_forced_color_uses_brand_palette(self):
        output = io.StringIO()
        leverage.render_text_report(
            self.report(), stream=output, error_stream=io.StringIO(), color="always", width=96,
        )
        self.assertIn("\033[38;2;242;114;28m", output.getvalue())

    def test_display_groups_collapse_key_and_name_variants(self):
        self.assertEqual(
            leverage.collapsed_labels([
                "demo agent", "demo-agent", "example developer", "example-developer",
            ]),
            ["demo-agent", "example-developer"],
        )


if __name__ == "__main__":
    unittest.main()
