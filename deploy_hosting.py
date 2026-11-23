#!/usr/bin/env python3
"""Nasazení e-shopu na Firebase Hosting (site adr-fimas = adrparts.cz) přes REST API.

Spouští se v Google Cloud Shellu (autorizace = gcloud účet vlastníka projektu).
1) Načte aktuálně publikovanou verzi: konfiguraci (rewrites/headers/...) a seznam souborů.
2) Stáhne všechny její soubory do ./backup (záloha starého katalogu).
3) Sestaví novou verzi = staré soubory + soubory z ./public (index.html, sw.js, manifest.json).
4) Do konfigurace doplní Cache-Control: no-cache pro HTML, sw.js a manifest.json.
5) Nahraje, finalizuje a vydá (release). Návrat zpět: Firebase Console → Hosting → historie → Rollback.

Použití:  python3 deploy_hosting.py            (nasadí)
          python3 deploy_hosting.py --dry-run  (jen ukáže, co by nasadil)
"""
import gzip, hashlib, json, os, subprocess, sys, urllib.request, urllib.error

SITE = 'adr-fimas'
API = 'https://firebasehosting.googleapis.com/v1beta1'
DRY = '--dry-run' in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
NO_CACHE = ['/', '/index.html', '/sw.js', '/manifest.json']


def token():
    return subprocess.check_output(['gcloud', 'auth', 'print-access-token'], text=True).strip()


TOKEN = token()


def call(method, url, body=None, raw=None, ctype='application/json'):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + TOKEN, 'Content-Type': ctype, 'x-goog-user-project': SITE})
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode() or '{}'
            return json.loads(txt)
    except urllib.error.HTTPError as e:
        sys.exit(f'CHYBA {e.code} {method} {url}\n{e.read().decode()[:2000]}')


def main():
    rel = call('GET', f'{API}/sites/{SITE}/releases?pageSize=1')['releases'][0]
    cur = rel['version']
    print('Aktuální verze:', cur['name'], '| vydána:', rel.get('releaseTime'))
    config = cur.get('config', {}) or {}
    print('Aktuální konfigurace:', json.dumps(config, ensure_ascii=False))

    files, page = [], ''
    while True:
        r = call('GET', f"{API}/{cur['name']}/files?pageSize=1000" + (f'&pageToken={page}' if page else ''))
        files += [f['path'] for f in r.get('files', [])]
        page = r.get('nextPageToken')
        if not page:
            break
    print('Souborů v aktuální verzi:', len(files), files)

    # záloha + základ nové verze
    content = {}
    os.makedirs(os.path.join(HERE, 'backup'), exist_ok=True)
    for p in files:
        with urllib.request.urlopen(f'https://{SITE}.web.app{p}?nocache=1') as r:
            b = r.read()
        content[p] = b
        out = os.path.join(HERE, 'backup', p.lstrip('/'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(b)
    # nové soubory
    pub = os.path.join(HERE, 'public')
    for root, _, names in os.walk(pub):
        for n in names:
            full = os.path.join(root, n)
            p = '/' + os.path.relpath(full, pub).replace(os.sep, '/')
            content[p] = open(full, 'rb').read()
            print('NOVÝ / NAHRAZENÝ:', p, len(content[p]), 'B')

    headers = [h for h in config.get('headers', []) if h.get('glob') not in NO_CACHE]
    for g in NO_CACHE:
        headers.append({'glob': g, 'headers': {'Cache-Control': 'no-cache'}})
    config['headers'] = headers

    if DRY:
        print('DRY RUN – nic se nenasadilo. Nová konfigurace:', json.dumps(config, ensure_ascii=False))
        return

    ver = call('POST', f'{API}/sites/{SITE}/versions', {'config': config, 'labels': {'deployed-by': 'claude-adrparts-eshop'}})
    vname = ver['name']
    print('Nová verze:', vname)
    gz, hashes = {}, {}
    for p, b in content.items():
        g = gzip.compress(b, mtime=0)
        h = hashlib.sha256(g).hexdigest()
        gz[h] = g
        hashes[p] = h
    pop = call('POST', f'{API}/{vname}:populateFiles', {'files': hashes})
    need = pop.get('uploadRequiredHashes', [])
    print('Nahrávám souborů:', len(need))
    for h in need:
        call('POST', f"{pop['uploadUrl']}/{h}", raw=gz[h], ctype='application/octet-stream')
    call('PATCH', f'{API}/{vname}?update_mask=status', {'status': 'FINALIZED'})
    r = call('POST', f'{API}/sites/{SITE}/releases?versionName={vname}', {'message': 'E-shop ADR Parts nahrazuje katalog'})
    print('HOTOVO – vydáno:', r.get('name'), r.get('releaseTime'))


if __name__ == '__main__':
    main()
