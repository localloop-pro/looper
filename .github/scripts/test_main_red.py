import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

import main_red


class MainRedTests(unittest.TestCase):
    def test_first_failure_opens(self):
        self.assertEqual(main_red.decide({"backend": "failure", "web": "success"}, None), "open")

    def test_second_failure_comments(self):
        self.assertEqual(main_red.decide({"backend": "failure"}, 42), "comment")

    def test_green_closes(self):
        self.assertEqual(main_red.decide({"backend": "success", "web": "success"}, 42), "close")

    def test_green_without_issue_does_nothing(self):
        self.assertEqual(main_red.decide({"backend": "success"}, None), "nothing")

    def test_incomplete_runs_never_close(self):
        for results in ({}, {"web": "skipped"}, {"web": "cancelled"},
                        {"backend": "success", "web": "cancelled"}):
            self.assertEqual(main_red.decide(results, 42), "nothing")

    def test_failure_with_skipped_gate_still_reports(self):
        self.assertEqual(main_red.decide({"backend": "failure", "web": "skipped"}, None), "open")

    def test_issue_lookup_paginates_filters_prs_and_uses_exact_title(self):
        self.assertEqual(main_red.find_issue([
            [{"number": 1, "title": "main is red", "state": "open", "pull_request": {}},
             {"number": 2, "title": "main is red", "state": "closed"},
             {"number": 3, "title": "main is red today", "state": "open"}],
            [{"number": 44, "title": "main is red", "state": "open"},
             {"number": 42, "title": "main is red", "state": "open"}],
        ]), 42)

    def env(self):
        return {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main",
                "GITHUB_SHA": "abc123", "GITHUB_REPOSITORY": "localloop-pro/looper",
                "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "123",
                "JOB_RESULTS": '{"backend":{"result":"failure"}}'}

    def invoke(self, env, responses=()):
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch.object(main_red, "api", side_effect=responses) as api:
            with contextlib.redirect_stdout(output):
                main_red.main()
        return json.loads(output.getvalue()), api

    def test_pr_is_noop_even_with_write_token(self):
        plan, api = self.invoke({**self.env(), "GITHUB_EVENT_NAME": "pull_request"})
        self.assertEqual(plan["action"], "nothing")
        api.assert_not_called()

    def test_other_branch_is_noop(self):
        _, api = self.invoke({**self.env(), "GITHUB_REF": "refs/heads/feature"})
        api.assert_not_called()

    def test_dry_run_failure_and_green_make_no_api_calls(self):
        for result, existing, expected in [("failure", "", "open"), ("failure", "42", "comment"),
                                           ("success", "42", "close"), ("success", "", "nothing")]:
            plan, api = self.invoke({**self.env(), "MAIN_RED_DRY_RUN": "1",
                                    "MAIN_RED_EXISTING_ISSUE": existing,
                                    "JOB_RESULTS": json.dumps({"backend": {"result": result}})})
            self.assertEqual(plan["action"], expected)
            api.assert_not_called()

    def test_live_open_contains_failure_sha_pr_and_run(self):
        plan, api = self.invoke(self.env(), [{"object": {"sha": "abc123"}}, [[]],
            [[{"number": 87, "html_url": "https://github.com/localloop-pro/looper/pull/87",
               "merged_at": "today", "base": {"ref": "main"}}]], {}])
        self.assertEqual(plan["action"], "open")
        for value in ("backend", "abc123", "#87", "/actions/runs/123"):
            self.assertIn(value, plan["body"])
        self.assertEqual(api.call_args.kwargs["payload"], {"title": "main is red", "body": plan["body"]})

    def test_live_repeat_comments_without_creating(self):
        _, api = self.invoke(self.env(), [{"object": {"sha": "abc123"}},
            [[{"number": 42, "title": "main is red", "state": "open"}]], [[]], {}])
        self.assertEqual(api.call_args.args[0], "repos/localloop-pro/looper/issues/42/comments")
        self.assertEqual(api.call_count, 4)

    def test_live_close_comments_before_closing(self):
        plan, api = self.invoke({**self.env(), "JOB_RESULTS": '{"backend":{"result":"success"}}'},
            [{"object": {"sha": "abc123"}}, [[{"number": 42, "title": "main is red", "state": "open"}]], {}, {}])
        self.assertTrue(plan["body"].startswith("green again at abc123"))
        self.assertTrue(api.call_args_list[-2].args[0].endswith("/comments"))
        self.assertEqual(api.call_args.kwargs, {"method": "PATCH", "payload": {"state": "closed"}})

    def test_stale_run_does_not_touch_issues(self):
        plan, api = self.invoke(self.env(), [{"object": {"sha": "newer"}}])
        self.assertEqual(plan["action"], "nothing")
        self.assertEqual(api.call_count, 1)

    def test_api_uses_json_stdin_without_shell(self):
        with patch.object(main_red.subprocess, "run") as run:
            run.return_value.stdout = '{}'
            main_red.api("repos/owner/repo/issues", method="POST", payload={"body": "$(false)\n`false`"})
        self.assertEqual(json.loads(run.call_args.kwargs["input"]), {"body": "$(false)\n`false`"})
        self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
