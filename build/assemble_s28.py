#!/usr/bin/env python3
"""Assemble sprint-28-review/index.html from the S27 template + S28 data."""
import json, re, os

SRC = '/home/natha/projects/sprint-27-review/index.html'
DST_DIR = '/home/natha/projects/sprint-28-review'
os.makedirs(DST_DIR, exist_ok=True)

html_txt = open(SRC, encoding='utf-8').read()
data_txt = open('/tmp/s28_data.json', encoding='utf-8').read()
json.loads(data_txt)  # validate

orig_len = len(html_txt)

# 1. swap inlined bootstrap-data (escape '<' so a PR title can never break the <script>)
safe = data_txt.replace('<', '\\u003c')
pat = re.compile(r'(<script id="bootstrap-data" type="application/json">)(.*?)(</script>)', re.DOTALL)
assert pat.search(html_txt), 'bootstrap-data block not found'
html_txt = pat.sub(lambda m: m.group(1) + safe + m.group(3), html_txt, count=1)

# 2. <title>
html_txt = html_txt.replace('<title>Sprint 27 Review — Silver Fern</title>',
                            '<title>Sprint 28 Review — Silver Fern</title>')

# 3. replace the whole overviewSection() — 6 hand-curated arc cards + milestone intro
NEW_OVERVIEW = """function overviewSection(){
  return el('section', {id:'overview', class:'max-w-7xl mx-auto px-6 py-10'},
    el('div', {class:'sf-eyebrow mb-2'}, 'The Arc'),
    el('h2', {class:'sf-h2 text-3xl mb-3'}, 'Execute Order 66 — in production'),
    el('p', {class:'mb-7 max-w-4xl', style:'color:#3F4948; font-weight:300;'},
      `${DATA.metrics.merged.toLocaleString()} PRs merged in three weeks — Silver Fern's largest sprint on record, and the clearest proof yet of Execute Order 66: a large share shipped by the Product team's auto-dev pipeline and autonomous agents, not in spite of them. ${DATA.metrics.active} still in flight. The big arcs from S28:`),
    el('div', {class:'grid md:grid-cols-2 lg:grid-cols-3 gap-4'},
      arcCard('FULFILL', 'Fulfill Orders go server-side', 'The Orders grid moved to AG Grid Server-Side Row Model — server-side per-column + set filters, row grouping and value aggregations. Credit Orders shipped end-to-end (creditExistingOrder mutation + modal). Items gained COGS, in-grid edit, URL deep-links, and server-resolved Days-to-Pay.'),
      arcCard('FORECAST/DBR', 'The Restock Demand Dashboard lands', 'The DBR engine went front-to-back: a full dashboard with URL-persisted filters, selection and sort, CSV export, decayed-score and allocation-reason columns, and a Restock Index breakdown — riding a hardened calc engine (RCAQ/RCDQ workers, dimensionless slope-factor seasonality, weeks-of-supply overrides, self-healing availability).'),
      arcCard('PRODUCE', 'Material, GrowPoint and Space Planning', 'The Material app migrated onto the shared explorer (ML-04 to ML-07) with scanner-enabled location search. GrowPoint matured — orders validation, item-staging grid, historical-order import pipeline. Space Planning v3 added Capacity Row drilldown and Space Category dimension variations, plus the new order-line Upgrades panel.'),
      arcCard('PLATFORM', 'Accounting, tenant lifecycle and telemetry', 'Merge.dev accounting deepened — a QuickBooks Chart-of-Accounts mirror, a Data Flows panel with per-flow toggles and sync stats, and surfaced QB export failures. Tenant lifecycle got real: inline UserInvite with one-time set-password tokens, TrialExpiry automation, rate-limited public invites. Plus a Command Center home redesign and OTel across the fleet.'),
      arcCard('DEV-TOOLS', 'The pipeline that built the sprint', 'Much of S28 shipped itself. The karpathy-fleet auto-dev runner gained a dotnet flock wrapper; AI Helm added a DeployStage state machine and deploy-writer auth; the new sf-refactor-api (VettedCode + atlas-compliance) went to prod; and the E2E harness was hardened against order-flow flake.'),
      arcCard('PLATFORM', '171 autonomous refactor PRs', 'An autonomous agent — willie-silverfern — merged 171 functional-programming refactors across the backend: foreach to Select / Zip / Traverse, decomposed blanket TryAsync, removed null-forgiving operators, positional Match params. Execute Order 66, running unattended.'),
    )
  );
}"""
ov = re.compile(r'function overviewSection\(\)\{[\s\S]*?\n\}')
assert ov.search(html_txt), 'overviewSection not found'
html_txt = ov.sub(lambda m: NEW_OVERVIEW, html_txt, count=1)

# 4. format big header metrics with thousands separators (1,126 not 1126)
html_txt = html_txt.replace(
    "'font-weight:700; color:white; line-height:1;'}, String(n)),",
    "'font-weight:700; color:white; line-height:1;'}, (typeof n === 'number' ? n.toLocaleString() : String(n))),")

# 5. S27 -> S28 string fixups
html_txt = html_txt.replace('These carry into Sprint 28 planning.', 'These carry into Sprint 29 planning.')
html_txt = html_txt.replace('Every PR from S27 in one filterable grid.', 'Every PR from S28 in one filterable grid.')
html_txt = html_txt.replace(
    "Every dev\\'s PRs from S27 grouped by product area. Pick what you want to review — no assignments. Former Silver Fern devs appear at the end.",
    "Every dev\\'s PRs from S28 grouped by product area. Pick what you want to review — no assignments.")

# write
open(os.path.join(DST_DIR, 'index.html'), 'w', encoding='utf-8').write(html_txt)
open(os.path.join(DST_DIR, 'data.json'), 'w', encoding='utf-8').write(data_txt)

# validation
print('index.html:', len(html_txt), 'bytes (was', orig_len, ')')
print('arcCard count:', html_txt.count('arcCard('))
print('title S28:', '<title>Sprint 28 Review' in html_txt)
print('still says S27:', 'S27' in html_txt, '| Sprint 27:', 'Sprint 27' in html_txt)
print('lg:grid-cols-3:', 'lg:grid-cols-3' in html_txt)
print('data sprint_label:', json.loads(data_txt)['metrics']['sprint_label'])
