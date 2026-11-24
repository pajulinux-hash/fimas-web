"""Hloubkový průchod sekce ADR, COLAERT ESSIEUX na obchod.fimas.cz (všechny podkategorie, stránkování,
detaily produktů: fotky, galerie, popis s tabulkami a obrázky).

Výstup: ~/adr_crawl.json  (kategorie, produkty, popisy – deduplikované)
Použití v Cloud Shellu:  python3 tools/crawl_adr.py [--max-products N]
"""
import concurrent.futures as cf
import hashlib, html, json, os, re, sys, time, urllib.request
from html.parser import HTMLParser

BASE = 'https://obchod.fimas.cz'
START = BASE + '/ADR-COLAERT-ESSIEUX-c23_0_1.htm'
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36 ADRParts-audit'}
OUT = os.path.expanduser('~/adr_crawl.json')
MAXP = int(sys.argv[sys.argv.index('--max-products') + 1]) if '--max-products' in sys.argv else 10 ** 9


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            if i == tries - 1:
                print('CHYBA', url, e, file=sys.stderr)
                return ''
            time.sleep(2 + i * 3)


def absu(u):
    u = html.unescape(u or '').strip()
    if not u or u.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '#')):
        return u
    if u.startswith('//'):
        return 'https:' + u
    if u.startswith('/'):
        return BASE + u
    if not re.match(r'^https?://', u):
        return BASE + '/' + u
    return u.replace('http://obchod.fimas.cz', BASE)


# ---------- sanitizace HTML popisů ----------
ALLOWED = {'div', 'p', 'br', 'span', 'b', 'strong', 'i', 'em', 'u', 'small', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
           'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption', 'colgroup', 'col', 'ul', 'ol', 'li',
           'img', 'a', 'sup', 'sub', 'hr', 'blockquote', 'figure', 'figcaption', 'center', 'font'}
DROP_WITH_CONTENT = {'script', 'style', 'iframe', 'form', 'noscript', 'object', 'embed', 'svg', 'button', 'select', 'textarea'}
VOID = {'br', 'img', 'hr', 'col'}
ATTRS = {'img': {'src', 'alt', 'width', 'height', 'title'}, 'a': {'href', 'title'}, 'td': {'colspan', 'rowspan', 'align', 'valign', 'width'},
         'th': {'colspan', 'rowspan', 'align', 'valign', 'width'}, 'table': {'border', 'cellpadding', 'cellspacing', 'width'},
         'col': {'span', 'width'}, 'colgroup': {'span'}, 'font': {'color', 'size'}, 'p': {'align'}, 'div': {'align'}}


class San(HTMLParser):
    def __init__(self, keep_style):
        super().__init__(convert_charrefs=False)
        self.keep_style, self.out, self.skip, self.stack = keep_style, [], 0, []

    def handle_starttag(self, tag, attrs):
        if self.skip or tag in DROP_WITH_CONTENT:
            if tag in DROP_WITH_CONTENT and tag not in VOID:
                self.skip += 1
            return
        if tag not in ALLOWED:
            return
        keep = []
        for k, v in attrs:
            v = v or ''
            if k.startswith('on'):
                continue
            if k == 'style':
                if self.keep_style:
                    v = re.sub(r'(?i)expression\s*\(|url\s*\(\s*["\']?\s*javascript:', '', v)
                    keep.append((k, v))
                continue
            if k in ATTRS.get(tag, ()):
                if k in ('src', 'href'):
                    v = absu(v)
                    if v.lower().startswith('javascript:'):
                        continue
                keep.append((k, v))
        if tag == 'a':
            keep.append(('target', '_blank')); keep.append(('rel', 'noopener'))
        if tag == 'img':
            keep.append(('loading', 'lazy'))
        self.out.append('<' + tag + ''.join(f' {k}="{html.escape(v, quote=True)}"' for k, v in keep) + '>')
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop(); self.out.append(f'</{tag}>')

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT:
            if self.skip:
                self.skip -= 1
            return
        if self.skip or tag not in ALLOWED or tag in VOID:
            return
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop(); self.out.append(f'</{t}>')
                if t == tag:
                    break

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)

    def handle_entityref(self, n):
        if not self.skip:
            self.out.append(f'&{n};')

    def handle_charref(self, n):
        if not self.skip:
            self.out.append(f'&#{n};')

    def result(self):
        while self.stack:
            self.out.append(f'</{self.stack.pop()}>')
        s = ''.join(self.out)
        s = re.sub(r'(<br>\s*){3,}', '<br><br>', s)
        s = re.sub(r'[ \t\r\n]+', ' ', s)
        s = re.sub(r'<(p|div|span|small|strong|b)>\s*(&nbsp;)?\s*</\1>', '', s)
        return s.strip()


def sanitize(fragment, keep_style):
    p = San(keep_style)
    p.feed(fragment); p.close()
    return p.result()


def text_len(h):
    return len(re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip())


# ---------- kategorie ----------
CAT_RE = re.compile(r'href="((?:https?://obchod\.fimas\.cz)?/[^"?#]*-c23_(\d+)_(\d+)\.htm)"')
PROD_RE = re.compile(r'href="((?:https?://obchod\.fimas\.cz)?/[^"?#]*-d(\d+)\.htm)"')
LIST_MARKERS = ['id="centerpage_params_filter_area"', 'class="item-container', 'id="centerpage_filtering_form"',
                'class="subcategory', 'class="categories-box', 'class="product-list', 'class="ws_list', '<!-- END in the center']


def parse_category(url, h):
    m = re.search(r'<h1[^>]*class="title_page[^"]*"[^>]*>(.*?)</h1>', h, re.S)
    title = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip() if m else ''
    crumbs = []
    w = re.search(r'id="wherei">(.*?)</div>', h, re.S)
    if w:
        crumbs = [html.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in re.findall(r'<(?:a|span class="active")[^>]*>(.*?)</(?:a|span)>', w.group(1), re.S)]
        crumbs = [c for c in crumbs if c and c != 'Úvod']
    desc = ''
    if m:
        start = m.end()
        ends = [h.find(k, start) for k in LIST_MARKERS]
        ends = [e for e in ends if e > 0]
        end = min(ends) if ends else start
        raw = h[start:end]
        desc = sanitize(raw, keep_style=True)
        if text_len(desc) < 3 and '<img' not in desc and '<table' not in desc:
            desc = ''
    # položky výpisu (jen bloky item-container, ne levé menu)
    items = []
    for blk in h.split('class="item-container')[1:]:
        blk = blk[:6000]
        pm = PROD_RE.search(blk)
        if not pm:
            continue
        im = re.search(r'<img[^>]+src="([^"]+)"', blk)
        st = 'y' if re.search(r'class="[^"]*stock[-_]y', blk) else ('n' if re.search(r'class="[^"]*stock[-_]n', blk) else '?')
        tm = re.search(r'class="item-title[^"]*"[^>]*>(.*?)</', blk, re.S)
        items.append({'dn': pm.group(2), 'url': absu(pm.group(1)), 'img': absu(im.group(1)) if im else '',
                      'stock': st, 'title': html.unescape(re.sub(r'<[^>]+>', '', tm.group(1))).strip() if tm else ''})
    # stránkování: odkazy na stejnou kategorii s číslem stránky v query
    path = re.sub(r'^https?://[^/]+', '', url)
    pages = set()
    for href in re.findall(r'href="([^"]+)"', h):
        hh = html.unescape(href)
        if path in hh and '?' in hh and re.search(r'(?:^|[?&])(?:page|strana|pg|p|stranka|offset|from)=\d+', hh.split('?', 1)[1]):
            pages.add(absu(hh))
    subcats = sorted({absu(u) for u, a, b in CAT_RE.findall(h)})
    return {'title': title, 'crumbs': crumbs, 'desc': desc, 'items': items, 'pages': sorted(pages), 'links': subcats}


def crawl_categories():
    seen, queue, cats = set(), [START], {}
    while queue:
        batch = [u for u in queue if u not in seen]
        queue = []
        for u in batch:
            seen.add(u)
        with cf.ThreadPoolExecutor(6) as ex:
            for u, h in zip(batch, ex.map(get, batch)):
                if not h:
                    cats[u] = {'url': u, 'error': True}
                    continue
                c = parse_category(u, h)
                c['url'] = u
                # stránkování
                done_pages = {u}
                todo = [p for p in c['pages'] if p not in done_pages]
                while todo:
                    pu = todo.pop(0)
                    if pu in done_pages:
                        continue
                    done_pages.add(pu)
                    ph = get(pu)
                    if not ph:
                        continue
                    pc = parse_category(pu, ph)
                    known = {i['dn'] for i in c['items']}
                    c['items'] += [i for i in pc['items'] if i['dn'] not in known]
                    todo += [p for p in pc['pages'] if p not in done_pages]
                c['pagesVisited'] = sorted(done_pages)
                cats[u] = c
                for l in c['links']:
                    if l not in seen:
                        queue.append(l)
        queue = list(dict.fromkeys(queue))
        print('kategorie:', len(cats), 've frontě:', len(queue), file=sys.stderr)
    return cats


# ---------- produkty ----------
def parse_product(dn, url, h):
    m = re.search(r'<h1[^>]*>(.*?)</h1>', h, re.S)
    name = html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip() if m else ''
    stock = 'skladem' if 'class="stock_yes"' in h else ('není skladem' if 'class="stock_no"' in h else '?')
    main = ''
    mm = re.search(r'id="detail_src_magnifying_small"[^>]*src="([^"]+)"', h) or re.search(r'<img[^>]+src="([^"]+)"[^>]*id="detail_src_magnifying_small"', h)
    if mm:
        main = absu(mm.group(1))
    big = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*<span[^>]*id="magnify_src"', h)
    imgs = []
    for u in re.findall(r'(?:src|href)="([^"]*/fotky\d+/fotos/[^"]+)"', h):
        fu = absu(u)
        fn = fu.rsplit('/', 1)[-1]
        if re.search(rf'(?:^|_){dn}(?:_|\.|image)', fn) or fu == main:
            if fu not in imgs:
                imgs.append(fu)
    # popis
    desc = ''
    dm = re.search(r'id="description"[^>]*>', h)
    if dm:
        start = dm.end()
        ends = [h.find(k, start) for k in ('<!--END description', '<!-- END description', 'id="comment"', 'id="footer"')]
        ends = [e for e in ends if e > 0]
        raw = h[start:min(ends)] if ends else h[start:start + 200000]
        desc = sanitize(raw, keep_style=False)
        desc = re.sub(r'^\s*<div>\s*<h3>Kompletní specifikace</h3>', '<div>', desc)
        if text_len(desc) < 3 and '<img' not in desc and '<table' not in desc:
            desc = ''
    price = ''
    pm = re.search(r'itemprop="price"[^>]*content="([^"]+)"', h) or re.search(r'class="price-value[^"]*"[^>]*>([^<]+)<', h)
    if pm:
        price = pm.group(1).strip()
    params = []
    for k, v in re.findall(r'<tr[^>]*>\s*<t[hd][^>]*class="[^"]*param[^"]*name[^"]*"[^>]*>(.*?)</t[hd]>\s*<t[hd][^>]*>(.*?)</t[hd]>', h, re.S):
        params.append([html.unescape(re.sub(r'<[^>]+>', '', k)).strip(), html.unescape(re.sub(r'<[^>]+>', '', v)).strip()])
    return {'dn': dn, 'url': url, 'name': name, 'stock': stock, 'price': price, 'image': main,
            'imageBig': absu(big.group(1)) if big else '', 'gallery': imgs, 'desc': desc, 'params': params}


def main():
    t0 = time.time()
    cats = crawl_categories()
    prods = {}
    for c in cats.values():
        for i in c.get('items', []):
            prods.setdefault(i['dn'], i['url'])
    todo = list(prods.items())[:MAXP]
    print('produktů k načtení:', len(todo), file=sys.stderr)
    out_p, descs = {}, {}
    def work(t):
        dn, u = t
        h = get(u)
        return parse_product(dn, u, h) if h else {'dn': dn, 'url': u, 'error': True}
    with cf.ThreadPoolExecutor(6) as ex:
        for n, r in enumerate(ex.map(work, todo), 1):
            if r.get('desc'):
                hid = hashlib.sha1(r['desc'].encode()).hexdigest()[:12]
                descs[hid] = r['desc']; r['descId'] = hid
                r['descTables'] = r['desc'].count('<table'); r['descImgs'] = r['desc'].count('<img')
                del r['desc']
            out_p[r['dn']] = r
            if n % 50 == 0:
                print('produkty', n, '/', len(todo), file=sys.stderr)
    for c in cats.values():
        c.pop('links', None); c.pop('pages', None)
    json.dump({'generated': time.strftime('%Y-%m-%d %H:%M'), 'start': START, 'categories': list(cats.values()),
               'products': out_p, 'descriptions': descs}, open(OUT, 'w'), ensure_ascii=False)
    print('HOTOVO', len(cats), 'kategorií,', len(out_p), 'produktů,', len(descs), 'unikátních popisů,',
          round(time.time() - t0), 's ->', OUT, file=sys.stderr)


if __name__ == '__main__':
    main()
