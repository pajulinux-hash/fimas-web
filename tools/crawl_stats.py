import json, os, re, sys, collections
d = json.load(open(os.path.expanduser('~/adr_crawl.json')))
cats = d['categories']
what = sys.argv[1] if len(sys.argv) > 1 else 'cats'
if what == 'cats':
    big = sorted(cats, key=lambda c: -len(c.get('items', [])))[:6]
    print('NEJVÍC POLOŽEK:', [(c['title'][-40:], len(c['items'])) for c in big])
    print('CHYBY:', [c['url'] for c in cats if c.get('error')])
    L = collections.Counter(len(c.get('crumbs', [])) for c in cats); print('HLOUBKA:', dict(L))
    ds = [c for c in cats if c.get('desc')]
    print('S POPISEM:', len(ds), 'tabulky:', sum(1 for c in ds if '<table' in c['desc']), 'obrázky:', sum(1 for c in ds if '<img' in c['desc']))
    lens = collections.Counter((re.sub(r'<[^>]+>', '', c['desc'])[:60]) for c in ds)
    print('NEJČASTĚJŠÍ ZAČÁTKY POPISU:', lens.most_common(6))
elif what == 'desc':
    c = next(c for c in cats if sys.argv[2] in c['url'] or sys.argv[2] in c.get('title', ''))
    print(c['url'], c['title'], c['crumbs'], len(c['items']), 'items'); print(c['desc'][:int(sys.argv[3]) if len(sys.argv) > 3 else 3000])
