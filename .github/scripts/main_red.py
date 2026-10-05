"""Report completed main CI runs. Dry runs never contact GitHub."""

import json
import os
import subprocess

TITLE = "main is red"


def decide(results, existing_issue):
    """Return open/comment/close/nothing without I/O or mutating inputs."""
    if "failure" in results.values():
        return "comment" if existing_issue is not None else "open"
    if results and all(result == "success" for result in results.values()):
        return "close" if existing_issue is not None else "nothing"
    # Cancelled/skipped/incomplete runs are not proof of recovery.
    return "nothing"


def api(endpoint, *, method="GET", payload=None, paginate=False):
    args = ["gh", "api", endpoint, "--method", method]
    if paginate:
        args += ["--paginate", "--slurp"]
    if payload is not None:
        args += ["--input", "-"]
    completed = subprocess.run(
        args, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True, check=True,
    )
    return json.loads(completed.stdout)


def find_issue(pages):
    """Use the oldest exact-title open issue; never match a pull request."""
    matches = [issue["number"] for page in pages for issue in page
               if issue.get("title") == TITLE and issue.get("state") == "open"
               and "pull_request" not in issue]
    return min(matches) if matches else None


def report(results, existing_issue, sha, run_url, merged_prs):
    action = decide(results, existing_issue)
    failed = sorted(name for name, result in results.items() if result == "failure")
    if action == "close":
        body = f"green again at {sha}\n\nRun: {run_url}"
    else:
        prs = ", ".join(f"#{pr['number']} ({pr['html_url']})" for pr in merged_prs)
        body = (f"Failing jobs: {', '.join(failed)}\n\nCommit: {sha}"
                f"\n\nMerged PR: {prs or 'none associated with this commit'}"
                f"\n\nRun: {run_url}\n\nFix this through a normal small PR; keep the CI gates intact.")
    return {"action": action, "issue": existing_issue, "title": TITLE, "body": body}


def main():
    # Defence in depth: the workflow must also restrict this job to main pushes.
    if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        print(json.dumps({"action": "nothing", "reason": "not a main push"}))
        return
    needs = json.loads(os.environ["JOB_RESULTS"])
    results = {name: job["result"] for name, job in needs.items()}
    sha = os.environ["GITHUB_SHA"]
    repo = os.environ["GITHUB_REPOSITORY"]
    run_url = f"{os.environ['GITHUB_SERVER_URL']}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    dry_run = os.environ.get("MAIN_RED_DRY_RUN") == "1"
    if dry_run:
        # Fixtures let owners reproduce both paths without a token or API reads.
        existing = os.environ.get("MAIN_RED_EXISTING_ISSUE")
        existing = int(existing) if existing else None
        merged_prs = json.loads(os.environ.get("MAIN_RED_MERGED_PRS", "[]"))
    else:
        prefix = f"repos/{repo}"
        head = api(f"{prefix}/git/ref/heads/main")["object"]["sha"]
        if head != sha:
            print(json.dumps({"action": "nothing", "reason": "superseded main commit"}))
            return
        existing = find_issue(api(f"{prefix}/issues?state=open&per_page=100", paginate=True))
        merged_prs = []
        if decide(results, existing) in ("open", "comment"):
            pages = api(f"{prefix}/commits/{sha}/pulls?per_page=100", paginate=True)
            merged_prs = [pr for page in pages for pr in page
                          if pr.get("merged_at") and pr["base"]["ref"] == "main"]
    plan = report(results, existing, sha, run_url, merged_prs)
    print(json.dumps(plan, sort_keys=True))
    if dry_run or plan["action"] == "nothing":
        return
    if plan["action"] == "open":
        api(f"{prefix}/issues", method="POST", payload={"title": TITLE, "body": plan["body"]})
    else:
        api(f"{prefix}/issues/{existing}/comments", method="POST", payload={"body": plan["body"]})
        if plan["action"] == "close":
            api(f"{prefix}/issues/{existing}", method="PATCH", payload={"state": "closed"})


if __name__ == "__main__":
    main()
