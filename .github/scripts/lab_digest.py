"""Post new commits of each lab branch to one GitHub issue per branch (docs/COLLABORATION.md).

Deterministic: no agent has to remember to notify. The issue body stores the last
reported commit; each run compares it with the branch head and comments the range,
grouped by area, with submodule pin changes flagged. Pushes that only touch
docs/lab/ advance the marker silently. Standard library only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
BRANCHES = [b.strip() for b in os.environ.get("LAB_BRANCHES", "main,fernando/continuacion-montara").split(",") if b.strip()]
MARKER = re.compile(r"<!-- lab-digest-last: ([0-9a-f]{40}) -->")
AREAS = [
    ("engine pin", lambda p: p == "engine"),
    ("mixer pin", lambda p: p == "mixer"),
    ("web", lambda p: p.startswith("web/")),
    ("deploy", lambda p: p.startswith(("deploy/", "deployment/", "Dockerfile", "compose"))),
    ("tests", lambda p: p.startswith("tests/")),
    ("experiments", lambda p: p.startswith("experiments/")),
    ("docs", lambda p: p.startswith("docs/") or p.endswith(".md")),
    ("ci", lambda p: p.startswith(".github/")),
    ("app code", lambda p: True),
]


def call(method: str, path: str, body: dict | None = None):
    request = urllib.request.Request(
        f"{API}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read() or b"null")


def digest_issue(branch: str) -> dict:
    title = f"Lab digest · {branch}"
    for issue in call("GET", f"/repos/{REPO}/issues?state=open&per_page=100&creator=github-actions%5Bbot%5D") or []:
        if issue.get("title") == title and "pull_request" not in issue:
            return issue
    body = (f"Automatic digest of new commits on `{branch}` (see `docs/COLLABORATION.md`). "
            "Subscribe to this issue to be notified.\n")
    return call("POST", f"/repos/{REPO}/issues", {"title": title, "body": body})


def group(files: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in files:
        area = next(name for name, match in AREAS if match(item["filename"]))
        counts[area] = counts.get(area, 0) + 1
    return counts


def report(branch: str) -> None:
    head = call("GET", f"/repos/{REPO}/commits/{urllib.parse.quote(branch, safe='')}")["sha"]
    issue = digest_issue(branch)
    body = issue.get("body") or ""
    found = MARKER.search(body)
    last = found.group(1) if found else None

    def save(sha: str) -> None:
        new_body = MARKER.sub("", body).rstrip() + f"\n\n<!-- lab-digest-last: {sha} -->\n"
        call("PATCH", f"/repos/{REPO}/issues/{issue['number']}", {"body": new_body})

    if last == head:
        return
    if last is None:
        call("POST", f"/repos/{REPO}/issues/{issue['number']}/comments",
             {"body": f"Digest starts at `{head[:7]}`. Later commits will be listed here."})
        return save(head)
    try:
        diff = call("GET", f"/repos/{REPO}/compare/{last}...{head}")
    except urllib.error.HTTPError as error:
        call("POST", f"/repos/{REPO}/issues/{issue['number']}/comments",
             {"body": f"⚠ Could not compare `{last[:7]}`…`{head[:7]}` (HTTP {error.code}). "
                      "History may have been rewritten; digest restarts here."})
        return save(head)
    files = diff.get("files") or []
    if files and all(f["filename"].startswith("docs/lab/") for f in files):
        return save(head)
    counts = group(files)
    commits = [c for c in diff.get("commits") or [] if len(c.get("parents") or []) < 2]
    lines = [f"**`{last[:7]}` → `{head[:7]}`** · {len(commits)} commit(s) · "
             f"[compare](https://github.com/{REPO}/compare/{last[:12]}...{head[:12]})"]
    pins = [f["filename"] for f in files if f["filename"] in ("engine", "mixer")]
    if pins:
        lines.append(f"⚠ **Submodule pin changed:** {', '.join(pins)} — check compatibility before merging.")
    lines.append("Areas: " + " · ".join(f"{name} {count}" for name, count in counts.items()))
    lines.append("")
    for commit in commits[-30:]:
        lines.append(f"- `{commit['sha'][:7]}` {commit['commit']['message'].splitlines()[0][:110]}")
    if len(commits) > 30:
        lines.append(f"- … and {len(commits) - 30} earlier commits")
    if len(files) >= 300:
        lines.append("_File list truncated by GitHub at 300 files._")
    call("POST", f"/repos/{REPO}/issues/{issue['number']}/comments", {"body": "\n".join(lines)})
    save(head)


def main() -> int:
    failed = 0
    for branch in BRANCHES:
        try:
            report(branch)
        except Exception as error:  # one branch failing must not hide the other
            failed += 1
            print(f"{branch}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
