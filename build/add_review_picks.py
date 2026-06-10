#!/usr/bin/env python3
"""Assign per-dev review picks and inject a Review Picks section into index.html."""
import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'index.html')
PICKS_PER_DEV = 5
BOT_AUTHORS = {'willie-silverfern'}

html_txt = open(HTML, encoding='utf-8').read()
m = re.search(r'(<script id="bootstrap-data" type="application/json">)(.*?)(</script>)', html_txt, re.DOTALL)
data = json.loads(m.group(2).replace('\\u003c', '<'))

# flatten all merged PRs
all_prs = []
for a in data['authors']:
    for prs in a['products'].values():
        all_prs.extend(prs)

reviewers = [a for a in data['authors'] if a['name'] not in BOT_AUTHORS and not a.get('former')]
# candidate pool: merged, substantive, not releases
pool = {p['id']: p for p in all_prs
        if p.get('status') == 'merged' and not p.get('is_release') and p.get('review_score', 0) >= 2}

def area_bonus(reviewer, pr):
    return 1 if pr['product'] in reviewer['products'] else 0

assigned = set()
picks = {r['name']: [] for r in reviewers}
# round-robin: each pass, every reviewer takes their best remaining candidate
for _round in range(PICKS_PER_DEV):
    for r in reviewers:
        best, best_score = None, -99
        for pid, pr in pool.items():
            if pid in assigned or pr['author'] == r['name']:
                continue
            s = pr.get('review_score', 0) + area_bonus(r, pr)
            if s > best_score:
                best, best_score = pr, s
        if best:
            assigned.add(best['id'])
            picks[r['name']].append({k: best[k] for k in ('id', 'title', 'repo', 'url', 'product', 'author', 'review_score')})

data['review_picks'] = picks
print({k: len(v) for k, v in picks.items()})

# re-inject data
safe = json.dumps(data, indent=1).replace('<', '\\u003c')
html_txt = html_txt[:m.start(2)] + safe + html_txt[m.end(2):]

# nav link
html_txt = html_txt.replace("        navlink('#reviews','By Developer'),",
                            "        navlink('#picks','Review Picks'),\n        navlink('#reviews','By Developer'),", 1)

# section renderer + mount
PICKS_JS = """function picksSection(){
  const picks = DATA.review_picks || {};
  const names = Object.keys(picks);
  return el('section', {id:'picks', class:'max-w-7xl mx-auto px-6 py-10'},
    el('div', {class:'sf-eyebrow mb-2'}, 'The Assignments'),
    el('h2', {class:'sf-h2 text-3xl mb-2'}, 'Review picks — who reviews what'),
    el('p', {class:'mb-6 max-w-3xl', style:'color:#3F4948; font-weight:300;'},
      'Each dev gets ' + (picks[names[0]]||[]).length + ' high-impact PRs from teammates to review for the meeting — scored by substance and weighted toward your own product areas. Agent-authored PRs are in the pool: human oversight is the point.'),
    el('div', {class:'grid md:grid-cols-2 gap-5'},
      ...names.map(n => el('div', {class:'sf-card overflow-hidden'},
        el('div', {class:'px-5 py-3 flex items-center justify-between', style:'background:#3F4948;'},
          el('div', {class:'sf-h3', style:'color:white;'}, n),
          el('span', {class:'text-xs', style:'color:#A1DBA6;'}, picks[n].length + ' to review')
        ),
        el('div', {class:'p-3 space-y-1'},
          ...picks[n].map(pr => el('div', {class:'sf-pick-row flex items-center gap-3 px-3 py-2 rounded'},
            el('span', {class:'chip text-xs shrink-0', style:'background:' + (PRODUCT_COLORS[pr.product]||'#6B7280')}, pr.product),
            el('a', {href:pr.url, target:'_blank', class:'text-sm hover:underline flex-1', style:'color:#3F4948;'}, pr.title),
            el('span', {class:'text-xs shrink-0', style:'color:#B3B3B3;'}, pr.author.split(' ')[0]),
            el('span', {class:'text-xs font-mono shrink-0', style:'color:#69936C;'}, '#' + pr.id)
          ))
        )
      ))
    )
  );
}
function footer(){"""
html_txt = html_txt.replace('function footer(){', PICKS_JS, 1)
html_txt = html_txt.replace('  reviewsSection(),', '  picksSection(),\n  reviewsSection(),', 1)
html_txt = html_txt.replace(
    "'Every dev\\'s PRs from S28 grouped by product area. Pick what you want to review — no assignments.'",
    "'Every dev\\'s PRs from S28 grouped by product area. Your assigned review picks are in the Review Picks section above.'")

open(HTML, 'w', encoding='utf-8').write(html_txt)
# keep data.json in sync
json.dump(data, open(os.path.join(ROOT, 'data.json'), 'w'), indent=1)
print('injected picks section,', len(html_txt), 'bytes')
