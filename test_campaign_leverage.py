import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import campaign_leverage as leverage


class LeverageTests(unittest.TestCase):
    def checkout(self, key, path, campaign, *, standalone=True, head_time=1):
        return leverage.Checkout(
            key, Path(path), Path(path), campaign, path, standalone, head_time, False
        )

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
                leverage.normalize_remote("git@github-veronica-agent:Obedience-Corp/camp.git"),
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
        self.assertEqual({c.campaign for c in selected[0][1]}, {"A", "B"})

    def test_email_aliases_expand_across_campaigns_and_skip_excluded(self):
        configs = [
            {"authors": {"lance": {"emails": ["one@example.com", "two@example.com"]}}},
            {"authors": {"founder": {"emails": ["two@example.com", "three@example.com"]},
                         "bot": {"emails": ["three@example.com", "bot@example.com"], "exclude": True}}},
        ]
        self.assertEqual(
            leverage.expand_author_emails({"ONE@example.com"}, configs),
            {"one@example.com", "two@example.com", "three@example.com"},
        )

    def test_author_group_name_expands_agent_emails_across_campaigns(self):
        configs = [
            {"authors": {"obey-agent": {"emails": ["agent@corp.example"]}}},
            {"authors": {"automation": {"emails": ["agent@corp.example", "agent@users.noreply.github.com"]}}},
        ]
        emails, groups = leverage.expand_author_identity(set(), {"Obey-Agent"}, configs)
        self.assertEqual(
            emails,
            {"agent@corp.example", "agent@users.noreply.github.com"},
        )
        self.assertIn("obey-agent", groups)
        self.assertIn("automation", groups)

    def test_transitive_group_label_does_not_become_a_git_name_selector(self):
        configs = [{"authors": {
            "lancekrogers": {"emails": ["me@example.com"]},
            "lancekrogers-2": {"emails": ["fixture@test"]},
        }}]
        emails, groups = leverage.expand_author_identity({"me@example.com"}, set(), configs)
        pairs = {("lancekrogers", "fixture@test")}
        self.assertEqual(emails, {"me@example.com"})
        self.assertEqual(groups, {"lancekrogers"})
        self.assertEqual(
            leverage.discover_named_author_emails(emails, set(), pairs),
            {"me@example.com"},
        )

    def test_selected_git_name_discovers_all_of_its_emails(self):
        pairs = {
            ("obey-agent", "one@example.com"),
            ("Obey-Agent", "two@example.com"),
            ("someone else", "other@example.com"),
        }
        self.assertEqual(
            leverage.discover_named_author_emails(set(), {"obey-agent"}, pairs),
            {"one@example.com", "two@example.com"},
        )

    def test_explicit_email_adds_to_git_default(self):
        self.assertEqual(
            leverage.seed_author_emails(["local@example.com"], "default@example.com"),
            {"local@example.com", "default@example.com"},
        )

    def test_history_stats_count_only_selected_author_text_lines(self):
        output = """@@CAMPAIGN_LEVERAGE@@me@example.com\t2026-01-01T00:00:00+00:00

10\t2\tone.py
-\t-\timage.png
@@CAMPAIGN_LEVERAGE@@other@example.com\t2026-01-02T00:00:00+00:00

50\t4\tother.py
@@CAMPAIGN_LEVERAGE@@me@example.com\t2026-02-01T00:00:00+00:00

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

    def test_aggregate_unions_calendar_span_instead_of_summing_repo_effort(self):
        rows = [
            {"estimated_person_months": 12, "first_commit": "2026-01-01T00:00:00+00:00", "last_commit": "2026-02-01T00:00:00+00:00"},
            {"estimated_person_months": 18, "first_commit": "2026-01-15T00:00:00+00:00", "last_commit": "2026-03-01T00:00:00+00:00"},
        ]
        result = leverage.aggregate(rows)
        self.assertAlmostEqual(result["estimated_person_months"], 30)
        self.assertAlmostEqual(result["actual_person_months"], 59 / 30.44)
        self.assertAlmostEqual(result["full_leverage"], 30 / (59 / 30.44))

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
            entries = leverage.project_entries(Path("/campaign"))
        self.assertEqual([entry["Name"] for entry in entries], ["app"])

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
                "estimatedScheduleMonths": 5,
                "languageSummary": [{"Code": 80}],
            }),
            patch.object(leverage, "blame_counts", return_value={"me@example.com": 25, "other@example.com": 75}),
            patch.object(leverage, "command", return_value=""),
        ):
            row = leverage.score_checkout(checkout, {"me@example.com"})
        self.assertAlmostEqual(row["estimated_person_months"], 5)
        self.assertAlmostEqual(row["author_share"], .25)
        self.assertEqual(row["estimated_owned_code_lines"], 20)
        self.assertEqual(row["lines_added"], 30)


if __name__ == "__main__":
    unittest.main()
