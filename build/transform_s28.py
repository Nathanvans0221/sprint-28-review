#!/usr/bin/env python3
"""Transform raw S28 PRs into the sprint-review data.json schema."""
import json, re
from datetime import datetime
from collections import Counter, defaultdict, OrderedDict

raw = json.load(open('/tmp/s28_raw.json'))
merged = raw['completed']
active = [p for p in raw['active'] if (p.get('created') or '') >= '2026-05-01']  # drop ancient stale

SPRINT_LABEL = "S28"
SPRINT_WINDOW = "May 20 – Jun 9, 2026"
NEXT_SPRINT = "Sprint 29"

# ---------- product classification ----------
REPO_PRODUCT = {
    'fulfill-pwa':'FULFILL','restock':'RESTOCK','forecast':'FORECAST/DBR','produce':'PRODUCE',
    'availability-pwa':'AVAILABILITY','mobile-app':'MOBILE','mobile-graphql':'MOBILE',
    'inventory-api':'INVENTORY','inventory-pwa':'INVENTORY','inventory-ws':'INVENTORY','inventory-models':'INVENTORY',
    'inventory-bonnie-sync':'INVENTORY','inventory-bonnie-k8':'INVENTORY','inventory-bonnie-models':'INVENTORY',
    'inventory-walmart-api-auth':'INVENTORY','count-api':'INVENTORY','count-app':'INVENTORY','count-app-view':'INVENTORY',
    'count-mqtt-broker':'INVENTORY','count-mqtt-client':'INVENTORY','countc-firmware':'INVENTORY',
    'countc-firmware-edgebox':'INVENTORY','countc-firmware-edgebox-az':'INVENTORY','webapp-lab-webapp-count':'INVENTORY',
    'pdf-generator':'REPORTS','wsapi-pdf-generator':'REPORTS',
}
DEVTOOLS_REPOS = {'claude-code','clickup-mcp','silverfern-dev-workflow','worksuite-graphql-mcp','ado-playwright-tests',
    'sf-refactor-api','sf-refactor-mcp','sf-csharp-functional','RiderSettings','codys-stuff','azure-auth-test','test-auth-api'}
PLATFORM_REPOS = {'k8s-worksuite','worksuite-synchronization','wsapi-admin-api','wsapi-admin-pwa','wsapi-local-instance',
    'wsapi-intelligence','wsapi-ai-orchestrator','wsapi-mcp','auth-api','auth-local-docker','desktop-auth',
    'environment-server','docker-red','migration-manager','apps-server','cloud-functions','worksuite-console',
    'worksuite-library','worksuite-tools','nagios','GP-Replication-SqlServer','importer','importer-server',
    'analyze','analyze-server','arc','worksuite-seeder'}
OTHER_REPOS = {'marketing-engine-api','marketing-engine-pwa','customer-portal','customer-portal-app','roadmap-voting-pwa',
    'sf-website','sf-website-legacy','help-center','bonnie-customer-intake-form','EventStoreConsole','console','console2'}
SHARED_REPOS = {'wsapi','worksuite-pwa','wsapi-services','wsapi-worker-services'}

# ordered keyword groups for shared repos (first match wins)
KW = [
 ('FORECAST/DBR', ['rcaq','rcdq','restockcalc','restock calc','restockavailability','restock availability','demandrecalc',
    'demand recalc','weeks-of-supply','weeks of supply',' wos','decayed score','ship factor','ship-factor','slope factor',
    'seasonality','baseratesofsale','base rate of sale','baserateofsale','rate of sale','ros.recompute','ros recompute',
    'demand dashboard','restock dashboard','restock-dashboard','daily transaction','inputssnapshot','dimensionsource',
    'restock session','session-create','missing-input','weeksofsupply',' dbr','dbr ','convergence','converged','creationstatus']),
 ('PRODUCE', ['mtr','mpr','ml-0','ml-1',' material','material ','hardgood','hgi','organic lot','vendor lot','grower','harvest',
    'space category','space-category','space dimension','space-dimension','space planning','space event','space-event',
    'productionjob','production job','lot creation','lot count','grade','growpoint','scanner-enabled','scd-','sc-wsapi','spacecategory']),
 ('RESTOCK', ['bros','restock dialog','restock dialogs','restock submit','restock exclusions','created with exclusions',
    'purchase order','reorder','buyer','write orders','writeorders','build units']),
 ('FULFILL', ['fulfill','allocation','allocate','sales order','customer item','customeritem','customerlocations',
    'itemswithbaserate','combinedorders','combined orders','credit order','correctorder','correct order','order creation',
    'order line','order-line','upgrades panel','upgrades ·','days-to-pay','days to pay','effectiveterms','tax authorit',
    'taxauthorit','shelf price','po number','transfer order','transferring an order','shipment','ship-from','order subtotal',
    'order csv','contact defaulting','contact title','orders','order ',' order']),
 ('REPORTS', ['report-schedule','reportschedule','scheduled report','export pdf','report schedule',' report ']),
 ('INVENTORY', ['inventory','perpetual',' bin ','warehouse','stock level','walmart','countsingestor','counts ','ingestor','lotcount','lot count']),
 ('AVAILABILITY', ['availability app','available to promise',' atp ']),
 ('PLATFORM', ['fusionauth','user-invite','userinvite','trialexpiry','trial expiry','set-password','rate-limit','rate limit',
    'role ','permission','telemetry','otel','opentelemetry','kubernetes','k8s','mosquitto','migration','background service',
    'bg-service','kurrent','eventstore','serilog','feature flag','feature-flag','webhook','tenant','merge.dev','mergedev',
    'merge dev','invoiceimport','invoice import','pricingimport','relman','release manifest','post-deploy','appsettings',
    'key vault','keyvault','ioptions','functionalize','decompose ','tryasync','null-forgiving','null-try','foreach','positional']),
]

def classify_product(pr):
    repo = pr['repo']
    if repo in REPO_PRODUCT: return REPO_PRODUCT[repo]
    if repo.startswith('sf-ai-') or ('-mcp' in repo) or repo.startswith('sf-ai') or repo in DEVTOOLS_REPOS: return 'DEV-TOOLS'
    if repo in PLATFORM_REPOS: return 'PLATFORM'
    if repo in OTHER_REPOS: return 'OTHER'
    if repo in SHARED_REPOS:
        text = (pr['title'] + ' ' + pr['source'] + ' ' + pr['target']).lower()
        for prod, toks in KW:
            if any(t in text for t in toks): return prod
        return 'PLATFORM'  # default for shared repos (backend / cross-cutting)
    return 'OTHER'

# ---------- type ----------
CONV = re.compile(r'^(feat|fix|chore|refactor|test|docs|perf|build|ci|style)(\(|:|!)', re.I)
FIX_VERB = re.compile(r'^(fix|resolve|correct|guard|prevent|patch|repair|align|self-heal|handle|stop|avoid|unblock|restore|harden)\b', re.I)
FP = re.compile(r'→|\bforeach\b|functionalize|decompose|tryasync|null-forgiving|null-try|positional|tohashset|\bselectmany\b|blanket try|\.zip\b', re.I)
TRIVIA = re.compile(r'^(bump|revert|pin|merge\b|rename|move|clean|chore|update|remove|delete|drop)\b', re.I)
def derive_type(pr):
    t = pr['title'].strip()
    if FP.search(t): return 'misc'           # autonomous functional refactors
    m = CONV.match(t)
    if m:
        k = m.group(1).lower()
        if k in ('feat','perf'): return 'feat'
        if k == 'fix': return 'fix'
        return 'misc'
    if TRIVIA.match(t) and not SUBSTANCE.search(t): return 'misc'
    if FIX_VERB.match(t): return 'fix'
    return 'feat'                            # default: substantive work = feature

# ---------- work_stream ----------
TICKET = re.compile(r'^([A-Z]{2,}[A-Z0-9]*)-\d')
CONV_SCOPE = re.compile(r'^[a-z]+\(([^)]+)\)', re.I)
DOMAIN = [('FP-REFACTOR',['functionalize','decompose','tryasync','null-forgiving','positional','foreach+','foreach to','→']),
    ('DBR-CALC',['rcaq','rcdq','restockcalc','demandrecalc','weeks-of-supply','decayed score','ship factor','slope factor','restock dashboard','restockavailability','baseratesofsale']),
    ('USER-INVITE',['user-invite','userinvite']),('TRIAL-EXPIRY',['trialexpiry','trial expiry']),
    ('GROWPOINT',['growpoint']),('MERGE-DEV',['merge.dev','mergedev','merge dev','pricingimport','invoiceimport']),
    ('SPACE',['space category','space-category','space dimension','space planning','space event','spacecategory','scd-','sc-wsapi']),
    ('ORDERS',['orders','order ','combinedorders','correctorder']),('CREDIT-ORDER',['credit order']),
    ('TAX',['tax authorit','taxauthorit']),('SSRM',['ssrm']),('UPGRADES',['upgrades']),
    ('TERMS',['effectiveterms','days-to-pay','terms']),('CUSTOMER-ITEM',['customeritem','customer item']),
    ('BROS',['bros']),('AUTH',['fusionauth','auth ','role ','permission']),('TELEMETRY',['otel','telemetry','opentelemetry']),
    ('MATERIAL',['material','mtr','mpr',' ml-']),('SCANNER',['scanner']),('TESTS',['test(','regression','integration test'])]
STREAM_ALIAS = {'MERGEDEV':'MERGE-DEV','RESTOCK-CALC-ACHIE':'RESTOCK-CALC','RESTOCK-ACHIEVABLE':'RESTOCK-CALC',
    'RESTOCK-DASHBOARD':'RESTOCK-DASH','RESTOCK-CALC-ACHIEV':'RESTOCK-CALC'}
def derive_stream(pr):
    t = pr['title']; low = t.lower()
    m = CONV_SCOPE.match(t)
    if m:
        s = m.group(1).upper().replace('_','-')[:18]
    else:
        m = TICKET.match(t)
        if m:
            s = m.group(1)[:18]
        else:
            s = 'MISC'
            for name, toks in DOMAIN:
                if any(tok in low for tok in toks):
                    s = name; break
    return STREAM_ALIAS.get(s, s)

TRIVIAL = re.compile(r'\b(bump|merge|revert|typo|whitespace|lint|format|rename|cleanup|comment)\b', re.I)
def is_release(pr):
    s = (pr['source'] or '').lower(); t = pr['title'].lower()
    return s.startswith('release/') or t.startswith('merge ') and 'release' in t or t.startswith('release ')

SUBSTANCE = re.compile(r'\b(graphql|mutation|query|api|wizard|redesign|panel|dashboard|worker|service|integration|migration|grid)\b', re.I)
def review_score(pr, prod):
    s = 0
    if pr['type']=='feat': s+=2
    elif pr['type']=='fix': s+=1
    if pr.get('is_release'): s-=5
    if TRIVIAL.search(pr['title']): s-=2
    if SUBSTANCE.search(pr['title']): s+=1
    if prod in ('FULFILL','RESTOCK','PRODUCE','FORECAST/DBR','REPORTS'): s+=1
    return max(-5, min(5, s))

# ---------- enrich ----------
def enrich(pr):
    pr['product'] = classify_product(pr)
    pr['type'] = derive_type(pr)
    pr['work_stream'] = derive_stream(pr)
    if pr['work_stream'] == 'FP-REFACTOR' and pr['repo'] in SHARED_REPOS:
        pr['product'] = 'PLATFORM'   # consolidate autonomous refactors in the platform backbone
    pr['is_release'] = is_release(pr)
    pr['review_score'] = review_score(pr, pr['product'])
    pr['merged_short'] = (pr['closed'] or '')[:10]
    pr['created_short'] = (pr['created'] or '')[:10]
    if '\\' in (pr.get('author_email') or ''):  # service principal GUID\GUID
        pr['author_email'] = 'autonomous-agent@silverfern.com'
    return pr

for p in merged: enrich(p); p['status']='merged'
for p in active: enrich(p); p['status']='active'
all_prs = merged + active

# ---------- metrics ----------
type_c = Counter(p['type'] for p in all_prs)
metrics = OrderedDict(
    total_prs=len(all_prs), merged=len(merged), active=len(active),
    feat=type_c['feat'], fix=type_c['fix'], misc=type_c['misc'],
    repos_touched=len(set(p['repo'] for p in all_prs)),
    authors_count=len(set(p['author'] for p in merged)),
    sprint_window=SPRINT_WINDOW, sprint_label=SPRINT_LABEL,
)

# ---------- products ----------
prod_prs = defaultdict(list)
for p in all_prs: prod_prs[p['product']].append(p)
products = OrderedDict()
for prod, prs in sorted(prod_prs.items(), key=lambda kv: -len(kv[1])):
    contrib = Counter(p['author'] for p in prs).most_common(5)
    streams = [(s,c) for s,c in Counter(p['work_stream'] for p in prs).most_common(12) if s!='MISC'][:6]
    feats = [p for p in prs if p['type']=='feat' and not p['is_release']]
    pool = (feats or prs)
    seen=set(); samples=[]
    for p in sorted(pool, key=lambda x:-x['review_score']):
        if p['title'] not in seen: samples.append(p['title']); seen.add(p['title'])
        if len(samples)>=5: break
    products[prod] = OrderedDict(count=len(prs), merged=sum(1 for p in prs if p['status']=='merged'),
        active=sum(1 for p in prs if p['status']=='active'),
        contributors=[[n,c] for n,c in contrib], streams=[[s,c] for s,c in streams], sample_titles=samples)

# ---------- authors ----------
by_author = defaultdict(list)
for p in all_prs: by_author[p['author']].append(p)
authors=[]
for name, prs in by_author.items():
    pmap=defaultdict(list)
    for p in sorted(prs, key=lambda x: x.get('merged_short') or x.get('created_short') or '', reverse=True):
        pmap[p['product']].append(p)
    email = next((p['author_email'] for p in prs if p['author_email']), '')
    authors.append(OrderedDict(name=name, email=email, pr_count=len(prs),
        products=OrderedDict(sorted(pmap.items(), key=lambda kv:-len(kv[1]))), former=False))
authors.sort(key=lambda a:-a['pr_count'])

out = OrderedDict(metrics=metrics, products=products, authors=authors,
    active_prs=sorted(active, key=lambda x:x.get('created_short',''), reverse=True),
    generated_at=datetime.now().isoformat())
json.dump(out, open('/tmp/s28_data.json','w'), indent=1)

# ---------- report ----------
print("METRICS:", json.dumps(metrics))
print("\nPRODUCT DISTRIBUTION:")
for prod,p in products.items(): print(f"  {prod:14s} {p['count']:4d}  (merged {p['merged']}, red {p['active']})  streams: {[s for s,_ in p['streams']]}")
print("\nTYPE:", dict(type_c))
print("AUTHORS:", [(a['name'],a['pr_count']) for a in authors])
print("\n========== ARC MATERIAL: top feature PRs by score per product ==========")
for prod in ['FULFILL','FORECAST/DBR','PRODUCE','PLATFORM','DEV-TOOLS','RESTOCK','INVENTORY']:
    prs=[x for x in all_prs if x['product']==prod and x['type']=='feat' and not x['is_release']]
    prs.sort(key=lambda x:(-x['review_score'], x['repo']))
    print(f"\n##### {prod} ({len(prs)} feats) #####")
    for p in prs[:14]: print(f"   [{p['author'][:13]:13s}|{p['repo'][:15]:15s}] {p['title'][:74]}")
