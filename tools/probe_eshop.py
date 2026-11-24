"""Průzkum HTML struktury obchod.fimas.cz (kategorie + produkt) – výpis tříd, odkazů, tabulek, obrázků."""
import re, sys, urllib.request, collections, os
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'}
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode('utf-8', 'replace')
os.makedirs(os.path.expanduser('~/probe'), exist_ok=True)
for name, u in [('cat', sys.argv[1]), ('prod', sys.argv[2] if len(sys.argv) > 2 else None)]:
    if not u: continue
    h = get(u)
    open(os.path.expanduser(f'~/probe/{name}.html'), 'w').write(h)
    print(f'##### {name} {u} len={len(h)}')
    cls = collections.Counter(c for grp in re.findall(r'class="([^"]+)"', h) for c in grp.split())
    print('CLASSES:', ' '.join(f'{k}:{v}' for k, v in cls.most_common(70)))
    print('CAT LINKS:', len(set(re.findall(r'href="([^"]*-c\d+_\d+_\d+\.htm)"', h))), 'PROD LINKS:', len(set(re.findall(r'href="([^"]*-d\d+\.htm)"', h))))
    print('PAGINATION?:', sorted(set(re.findall(r'href="([^"]*(?:page|strana|_\d+_\d+_\d+)[^"]*)"', h)))[:12])
    print('TABLES:', len(re.findall(r'<table', h)), 'IMGS:', len(re.findall(r'<img', h)))
    for m in re.finditer(r'<table', h):
        print('  TABLE ctx:', re.sub(r'\s+', ' ', h[max(0, m.start()-200):m.start()+150])[:350])
        break
    ids = collections.Counter(re.findall(r'id="([^"]+)"', h))
    print('IDS:', ' '.join(list(ids)[:60]))
