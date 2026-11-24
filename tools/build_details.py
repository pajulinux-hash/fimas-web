"""Z výstupu crawl_adr.py (~/adr_crawl.json) vytvoří data pro nový e-shop:
  public/adr-details.json  – popisy produktů (tabulky, výkresy), parametry, galerie, obsah kategorií,
                             rozkresy podskupin TYP NÁPRAVY / TYP BRZDY, prázdné podskupiny, podsekce (facety), návod
  public/adr-katalog.json  – velké katalogové tabulky (načítají se až na vyžádání)
Použití (Cloud Shell, ~/adrparts-deploy):  python3 tools/build_details.py
"""
import json, os, re, sys, time

HOME = os.path.expanduser('~')
SRC = os.path.join(HOME, 'adr_crawl.json')
OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'public')
d = json.load(open(SRC))
cats = [c for c in d['categories'] if not c.get('error')]
norm = lambda s: re.sub(r'\s+', ' ', (s or '').strip())
leaf = lambda c: norm((c.get('crumbs') or [''])[-1])
is_type = lambda c: any(re.match(r'^TYP (NÁPRAVY|BRZDY)', x or '') for x in c.get('crumbs') or []) and len(c.get('crumbs') or []) >= 3
type_kind = lambda c: 'brake' if any(x.startswith('TYP BRZDY') for x in c['crumbs']) else 'axle'
imgs_of = lambda h: [u.replace(' ', '%20') for u in re.findall(r'<img[^>]+src="([^"]+)"', h or '')]

# --- produkty
products, used = {}, set()
for dn, p in d['products'].items():
    if p.get('error'):
        continue
    e = {}
    if p.get('descId'):
        e['d'] = p['descId']; used.add(p['descId'])
    if p.get('params'):
        e['p'] = [[norm(k).rstrip(':'), norm(v)] for k, v in p['params'] if norm(v)]
    gal = [u.replace(' ', '%20') for u in p.get('gallery') or []]
    if len(gal) > 1:
        e['g'] = gal
    if p.get('image'):
        e['i'] = p['image'].replace(' ', '%20')
    if e:
        products[dn] = e
descs = {k: v for k, v in d['descriptions'].items() if k in used}
for k in list(descs):  # mezery v URL obrázků
    descs[k] = re.sub(r'src="([^"]+)"', lambda m: 'src="' + m.group(1).replace(' ', '%20') + '"', descs[k])

# --- rozkresy podskupin TYP + prázdné podskupiny
type_img, empty_types = {}, []
for c in cats:
    if not is_type(c):
        continue
    ims = imgs_of(c.get('desc'))
    nm = leaf(c)
    if ims:
        type_img[nm] = ims
    if not c.get('items'):
        empty_types.append({'name': nm, 'kind': type_kind(c), 'imgs': ims})

# --- obsah kategorií (2. úroveň): jen tabulky a obrázky s informační hodnotou, ne navigace / propagace
SKIP_CAT = re.compile(r'^(ADR, COLAERT ESSIEUX|třmen pera ADR, COLAERT)$')
cat_html, katalog, guide = {}, {}, ''
for c in cats:
    cr = c.get('crumbs') or []
    h = c.get('desc') or ''
    if not h or is_type(c):
        continue
    h = re.sub(r'src="([^"]+)"', lambda m: 'src="' + m.group(1).replace(' ', '%20') + '"', h)
    if len(cr) == 2 and leaf(c).startswith('JAK URČIT'):
        guide = h
    elif len(cr) >= 2 and leaf(c) == 'KATALOG':
        katalog[norm(cr[1])] = h
    elif len(cr) == 2 and not SKIP_CAT.match(leaf(c)) and ('<table' in h or '<img' in h):
        cat_html[leaf(c)] = h

# --- podsekce (facety) normálních kategorií
PREFIX = re.compile(r'^(pro buben ø|vnitřní šířka|šířka|závit)\s*(.+)$', re.I)
facets = {}
for c in cats:
    cr = [norm(x) for x in c.get('crumbs') or []]
    if is_type(c) or len(cr) < 3 or not c.get('items'):
        continue
    parent = cr[1]
    if len(cr) >= 4:
        group, value = cr[2], cr[-1]
    else:
        m = PREFIX.match(cr[2])
        group, value = (m.group(1), m.group(2)) if m else ('Podskupina', cr[2])
    if value in ('___', 'KATALOG'):
        continue
    facets.setdefault(parent, {}).setdefault(group, {})[value] = sorted({i['dn'] for i in c['items']}, key=int)

details = {'generated': d['generated'], 'source': d['start'], 'products': products, 'desc': descs, 'cat': cat_html,
           'typeImg': type_img, 'emptyTypes': empty_types, 'facets': facets, 'guide': guide,
           'katalog': sorted(katalog.keys())}
os.makedirs(OUT_DIR, exist_ok=True)
json.dump(details, open(os.path.join(OUT_DIR, 'adr-details.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
json.dump({'generated': d['generated'], 'katalog': katalog}, open(os.path.join(OUT_DIR, 'adr-katalog.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('adr-details.json:', os.path.getsize(os.path.join(OUT_DIR, 'adr-details.json')) // 1024, 'kB |',
      'produktů', len(products), 'popisů', len(descs), 'kategorií s obsahem', len(cat_html), list(cat_html),
      '| rozkresů typů', len(type_img), '| prázdných typů', len(empty_types), '| facety', {k: list(v) for k, v in facets.items()},
      '| návod', bool(guide), '| katalog', list(katalog), os.path.getsize(os.path.join(OUT_DIR, 'adr-katalog.json')) // 1024, 'kB')
