#!/usr/bin/env python3
"""Pull all S28 PRs (merged closed in window + active) across every SilverFern Azure repo."""
import os, json, urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ORG = "https://dev.azure.com/teamsilverfern/SilverFern"
WIN_MIN = "2026-05-20T00:00:00Z"
WIN_MAX = "2026-06-10T00:00:00Z"
TOK = os.popen("az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv 2>/dev/null").read().strip()
HDR = {"Authorization": "Bearer " + TOK}

repos = [r.strip() for r in open("/tmp/sf_repos.txt") if r.strip()]

def fetch(repo, status, extra=None):
    """Paginate through PR list for a repo+status."""
    out = []
    skip = 0
    while True:
        q = {"searchCriteria.status": status, "$top": "1000", "$skip": str(skip), "api-version": "7.1"}
        if extra: q.update(extra)
        url = f"{ORG}/_apis/git/repositories/{urllib.parse.quote(repo)}/pullrequests?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, headers=HDR)
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (404, 203): return out  # repo gone / no access
            raise
        batch = d.get("value", [])
        out.extend(batch)
        if len(batch) < 1000: break
        skip += 1000
    return out

def norm(pr, repo, status):
    cb = pr.get("createdBy", {}) or {}
    src = (pr.get("sourceRefName") or "").replace("refs/heads/", "")
    tgt = (pr.get("targetRefName") or "").replace("refs/heads/", "")
    revs = [r.get("displayName") for r in (pr.get("reviewers") or []) if r.get("displayName")]
    pid = pr.get("pullRequestId")
    return {
        "id": pid, "title": pr.get("title", ""), "repo": repo,
        "author": cb.get("displayName", "Unknown"),
        "author_email": (cb.get("uniqueName") or "").lower(),
        "created": pr.get("creationDate"), "closed": pr.get("closedDate"),
        "merge_status": pr.get("mergeStatus"), "source": src, "target": tgt,
        "status": "merged" if status == "completed" else "active",
        "url": f"{ORG}/_git/{urllib.parse.quote(repo)}/pullrequest/{pid}",
        "reviewers": revs,
    }

def work(repo):
    comp = [norm(pr, repo, "completed") for pr in fetch(repo, "completed",
            {"searchCriteria.queryTimeRangeType": "closed", "searchCriteria.minTime": WIN_MIN, "searchCriteria.maxTime": WIN_MAX})]
    act = [norm(pr, repo, "active") for pr in fetch(repo, "active")]
    return repo, comp, act

completed, active, errors = [], [], []
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = {ex.submit(work, r): r for r in repos}
    for f in as_completed(futs):
        r = futs[f]
        try:
            _, comp, act = f.result()
            completed.extend(comp); active.extend(act)
        except Exception as e:
            errors.append(f"{r}: {type(e).__name__}: {e}")

json.dump({"completed": completed, "active": active, "errors": errors},
          open("/tmp/s28_raw.json", "w"), indent=1)

from collections import Counter
print(f"REPOS QUERIED: {len(repos)}  ERRORS: {len(errors)}")
for e in errors[:20]: print("  ERR", e)
print(f"COMPLETED (merged in window): {len(completed)}")
print(f"ACTIVE (open now): {len(active)}")
rc = Counter(p['repo'] for p in completed)
print("TOP REPOS by merged PRs:")
for r, n in rc.most_common(25): print(f"  {r:32s} {n}")
ac = Counter(p['author'] for p in completed)
print(f"UNIQUE AUTHORS: {len(ac)}")
for a, n in ac.most_common(20): print(f"  {a:28s} {n}")
# active staleness
from datetime import datetime
def cd(p):
    try: return p['created'][:10]
    except: return '?'
print("ACTIVE created-date spread:", Counter(p['created'][:7] if p.get('created') else '?' for p in active).most_common())
