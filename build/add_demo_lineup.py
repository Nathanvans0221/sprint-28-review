#!/usr/bin/env python3
"""Inject the Demo Lineup section: what each dev is presenting at sprint review."""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')

# Presenters' own words (team chat, June 9-10 2026). keywords auto-attach related PRs.
LINEUP = [
    {"dev": "Ethan Boss", "plan": "GrowPoint Integrations flow, starting from an empty tenant.",
     "kw": r"growpoint"},
    {"dev": "Timothy Short", "plan": "wsapi admin changes for Restock, plus the updates to the Restock Dashboard.",
     "kw": r"restock"},
    {"dev": "Kennedy Kirk", "plan": "Merge.dev (QuickBooks) accounting integration — doc going to the review chat in the morning.",
     "kw": r"merge\.?dev|pricingimport|invoiceimport|quickbooks|chart of accounts"},
    {"dev": "Nathan van Wingerden", "plan": "Trial user flow, end to end.",
     "kw": r"trial|user.?invite|set-password"},
    {"dev": "Gabriela Gonzales", "plan": "Kit Builder page (final version) + improvements to code reviews.",
     "kw": r"kit"},
    {"dev": "Scott Slattery", "plan": "Customer Portal.",
     "kw": r"portal|cpr-"},
    {"dev": "Jared", "plan": "Verify updates: mobile picker flow (site → orders → mode selector → scan carts), then the supervisor dashboard — sessions → diff view → submit → order moves to Shipped.",
     "kw": r"verify"},
]
NOT_YET = ["Chris Christensen", "Kevin Short", "Isaac Short", "Hank Williams", "Stephen van Wingerden"]
MAX_RELATED = 4

html_txt = open(HTML, encoding='utf-8').read()
m = re.search(r'(<script id="bootstrap-data" type="application/json">)(.*?)(</script>)', html_txt, re.DOTALL)
data = json.loads(m.group(2).replace('\\u003c', '<'))

all_prs = []
for a in data['authors']:
    for prs in a['products'].values():
        all_prs.extend(prs)

lineup_out = []
for entry in LINEUP:
    rx = re.compile(entry['kw'], re.I)
    matches = [p for p in all_prs
               if p.get('status') == 'merged' and not p.get('is_release') and rx.search(p['title'])]
    matches.sort(key=lambda p: -p.get('review_score', 0))
    seen, related = set(), []
    for p in matches:
        if p['title'] in seen:
            continue
        seen.add(p['title'])
        related.append({k: p[k] for k in ('id', 'title', 'repo', 'url', 'product', 'author')})
        if len(related) >= MAX_RELATED:
            break
    lineup_out.append({"dev": entry['dev'], "plan": entry['plan'], "related": related})

data['demo_lineup'] = lineup_out
data['demo_lineup_pending'] = NOT_YET

safe = json.dumps(data, indent=1).replace('<', '\\u003c')
html_txt = html_txt[:m.start(2)] + safe + html_txt[m.end(2):]

html_txt = html_txt.replace("        navlink('#reviews','By Developer'),",
                            "        navlink('#demos','Demo Lineup'),\n        navlink('#reviews','By Developer'),", 1)

DEMOS_JS = """function demosSection(){
  const lineup = DATA.demo_lineup || [];
  const pending = DATA.demo_lineup_pending || [];
  return el('section', {id:'demos', class:'max-w-7xl mx-auto px-6 py-10'},
    el('div', {class:'sf-eyebrow mb-2'}, 'The Lineup'),
    el('h2', {class:'sf-h2 text-3xl mb-2'}, 'Demo lineup — what each dev is showing'),
    el('p', {class:'mb-6 max-w-3xl', style:'color:#3F4948; font-weight:300;'},
      'Demo plans as shared by each dev.'),
    el('div', {class:'grid md:grid-cols-2 gap-5'},
      ...lineup.map(d => el('div', {class:'sf-card overflow-hidden'},
        el('div', {class:'px-5 py-3', style:'background:#3F4948;'},
          el('div', {class:'sf-h3', style:'color:white;'}, d.dev)
        ),
        el('div', {class:'p-4'},
          el('p', {class:'text-sm', style:'color:#3F4948; font-weight:400;'}, d.plan)
        )
      ))
    ),
    pending.length ? el('p', {class:'mt-5 text-sm italic', style:'color:#B3B3B3;'},
      'Plans not shared yet: ' + pending.join(' · ')) : null
  );
}
function footer(){"""
html_txt = html_txt.replace('function footer(){', DEMOS_JS, 1)
html_txt = html_txt.replace('  reviewsSection(),', '  demosSection(),\n  reviewsSection(),', 1)

open(HTML, 'w', encoding='utf-8').write(html_txt)
json.dump(data, open(os.path.join(ROOT, 'data.json'), 'w'), indent=1)
for d in lineup_out:
    print(d['dev'], '->', len(d['related']), 'related PRs')
print('injected,', len(html_txt), 'bytes')
