"""Pro každou podskupinu TYP NÁPRAVY: které podskupiny TYP BRZDY s ní sdílejí produkty (podle URL) a jaké produkty v ní jsou."""
import json, re, urllib.request, collections
raw = urllib.request.urlopen('https://storage.googleapis.com/adr-fimas-katalog/data.json', timeout=30).read()
data = json.loads(raw)
def dn(u):
    m = re.search(r'/d(\d+)', u or ''); return m.group(1) if m else (u or '')
axle, brake = collections.defaultdict(set), collections.defaultdict(set)
names = {}
for p in data:
    c = p.get('category') or ''
    if '~' not in c: continue
    parts = [x.strip() for x in c.split('~')]
    k = dn(p.get('url')); names[k] = p['name'][:60]
    if re.match(r'^\d{3}x\d{2,3}$', parts[0]): brake[c].add(k)
    elif len(parts) == 2 and parts[1] == '': axle[c].add(k)
for a, ks in sorted(axle.items()):
    ov = [(b, len(ks & bs)) for b, bs in brake.items() if ks & bs]
    ov.sort(key=lambda x: -x[1])
    print(a, '| sdílí:', '; '.join(f'{b} ({n})' for b, n in ov) or '-', '| produkty:', ' / '.join(sorted(names[k] for k in ks))[:400])
