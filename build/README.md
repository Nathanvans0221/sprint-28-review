# Sprint review page generator

Reproducible pipeline that builds this page from Azure DevOps PRs. Modeled on `sprint-27-review`.

## Run order (edit the sprint window/label first)
1. `az repos list --org https://dev.azure.com/teamsilverfern -p SilverFern --query "[].name" -o tsv | sort > /tmp/sf_repos.txt`
2. `python3 build/pull_s28.py`        → pulls merged (closed-in-window) + active PRs across all repos → `/tmp/s28_raw.json`
3. `python3 build/transform_s28.py`   → classifies product/type/work_stream, builds `/tmp/s28_data.json` (review-page schema)
4. `python3 build/assemble_s28.py`    → clones the prior sprint's `index.html` template, swaps the inlined `bootstrap-data` + title + 6 arc cards → `index.html` + `data.json`

## To bump for the next sprint
- `pull_s28.py`: `WIN_MIN` / `WIN_MAX` (the sprint window, UTC).
- `transform_s28.py`: `SPRINT_LABEL`, `SPRINT_WINDOW`, `NEXT_SPRINT`. Re-tune `KW` / `REPO_PRODUCT` if new repos appear.
- `assemble_s28.py`: `SRC` (prior-sprint template), `DST_DIR`, the six `arcCard(...)` narratives (hand-curated from the arc-material dump that `transform` prints), and the S→S+1 string fixups.

Auth: `az` logged in as a SilverFern user; the pull mints a token via
`az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798` (Azure DevOps).
