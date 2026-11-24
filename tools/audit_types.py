"""Kontrola pokrytí rozkresů: podskupiny TYP NÁPRAVY / TYP BRZDY z data.json × TYPE_IMAGES v index.html × dostupnost /typy/*.webp na webu."""
import json, re, sys, urllib.request
SITE = sys.argv[1] if len(sys.argv) > 1 else 'https://adr-fimas.web.app'
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 audit'}), timeout=30) as r:
        return r.status, r.read()
_, raw = get('https://storage.googleapis.com/adr-fimas-katalog/data.json')
data = json.loads(raw)
_, html = get(SITE + '/?nocache=audit')
html = html.decode('utf-8')
m = re.search(r'const TYPE_IMAGES = (\{.*?\});', html)
if not m:
    print('CHYBA: TYPE_IMAGES v index.html na', SITE, 'není (stará verze?)'); sys.exit(1)
TI = json.loads(m.group(1))
def parse(cat):
    if not cat or '~' not in cat: return None
    parts = [x.strip() for x in cat.split('~')]
    if re.match(r'^\d{3}x\d{2,3}$', parts[0]):
        codes = re.findall(r'\b[A-Z][A-Z0-9]\b', parts[2] if len(parts) > 2 else '')
        return ('brake', codes) if codes else None
    if len(parts) == 2 and parts[1] == '':
        codes = re.findall(r'\b[A-Z0-9]{2}\b', parts[0])
        return ('axle', codes) if codes else None
    return None
cats = {}
for p in data:
    c = p.get('category') or ''
    t = parse(c)
    if t: cats.setdefault(c, [t, 0]); cats[c][1] += 1
used = {'axle': set(), 'brake': set()}
print('=== TYP NÁPRAVY ===')
for c, ((k, codes), n) in sorted(cats.items()):
    if k != 'axle': continue
    for code in codes:
        imgs = TI['axle'].get(code, [])
        if imgs: used['axle'].add(code)
        print(('OK  ' if imgs else 'BEZ ') + f'{code:4} ({c!r}, {n} pol.)' + (f' -> {imgs}' if imgs else ''))
print('=== TYP BRZDY ===')
for c, ((k, codes), n) in sorted(cats.items()):
    if k != 'brake': continue
    hit = next((x for x in codes if TI['brake'].get(x)), None)
    if hit: used['brake'].add(hit)
    print(('OK  ' if hit else 'BEZ ') + f'{c} [{",".join(codes)}] ({n} pol.)' + (f' -> {TI["brake"][hit]}' if hit else ''))
print('=== OBRÁZKY BEZ PODSKUPINY ===')
for k in TI:
    for code in TI[k]:
        if code not in used[k]: print(k, code, TI[k][code])
print('=== DOSTUPNOST OBRÁZKŮ NA', SITE, '===')
bad = 0; total = 0
for k in TI:
    for code, lst in TI[k].items():
        for u in lst:
            total += 1
            try:
                st, b = get(SITE + '/' + u)
                if st != 200 or len(b) < 1000: bad += 1; print('CHYBA', st, u, len(b))
            except Exception as e:
                bad += 1; print('CHYBA', u, e)
print('obrázků', total, 'chyb', bad)
