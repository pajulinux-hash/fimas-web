// Porovnání sekce ADR na obchod.fimas.cz (výstup crawl_adr.py) s novým e-shopem adrparts.cz.
// Používá PŘESNĚ logiku živého index.html (mergeProducts, resolveCategory, EMBEDDED_PRODUCTS, CATEGORIES).
// Použití v Cloud Shellu:  node tools/compare_adr.js [https://adrparts.cz]  → ~/adr_report.txt + ~/adr_report.json
const fs = require('fs'), os = require('os'), path = require('path');
const SITE = process.argv[2] || 'https://adrparts.cz';
const HOME = os.homedir();

function slice(src, from, to) {
  const a = src.indexOf(from); if (a < 0) throw new Error('nenalezeno: ' + from);
  const b = src.indexOf(to, a + from.length); if (b < 0) throw new Error('nenalezeno: ' + to);
  return src.slice(a, b);
}
const base = (u) => String(u || '').split('?')[0].split('/').pop().toLowerCase();
const num = (v) => { const s = String(v || '').replace(/&nbsp;|\s|CZK|Kč/g, '').replace(',', '.'); const n = parseFloat(s); return isFinite(n) ? n : 0; };

(async () => {
  const crawl = JSON.parse(fs.readFileSync(path.join(HOME, 'adr_crawl.json'), 'utf8'));
  const html = await (await fetch(SITE + '/?audit=' + Date.now())).text();
  const dataJson = await (await fetch('https://storage.googleapis.com/adr-fimas-katalog/data.json?t=' + Date.now())).json();
  const code = [
    slice(html, 'const DATA_CAT_MAP', 'const ORDER_EMAIL'),
    slice(html, 'const CATEGORIES = [', 'const NAV_ITEMS'),
    slice(html, 'const EMBEDDED_PRODUCTS = [', '\n];') + '\n];',
    'return { DATA_CAT_MAP, resolveCategory, mergeProducts, extractDnum, CATEGORIES, EMBEDDED_PRODUCTS };',
  ].join('\n');
  const L = new Function(code)();
  const origLog = console.log, origWarn = console.warn; console.log = () => {}; console.warn = () => {};
  const merged = L.mergeProducts(L.EMBEDDED_PRODUCTS, dataJson);
  console.log = origLog; console.warn = origWarn;
  const catName = (slug) => (L.CATEGORIES.find(c => c.id === slug) || {}).name || slug;

  const byDn = new Map();
  merged.forEach(p => { const dn = p.dn || L.extractDnum(p.url); if (dn && !byDn.has(dn)) byDn.set(dn, p); });
  const djByDn = new Map();
  dataJson.forEach(p => { const dn = L.extractDnum(p.url); if (!dn) return; if (!djByDn.has(dn)) djByDn.set(dn, []); djByDn.get(dn).push(p); });

  const cats = crawl.categories.filter(c => !c.error);
  const leafName = (c) => (c.crumbs && c.crumbs.length ? c.crumbs[c.crumbs.length - 1] : (c.title || '').split(' / ').pop());
  const isType = (c) => (c.crumbs || []).some(x => /^TYP (NÁPRAVY|BRZDY)/i.test(x)) && (c.crumbs || []).length >= 3;
  const crawlProd = crawl.products;
  const catsOf = new Map(); // dn -> [category]
  cats.forEach(c => (c.items || []).forEach(i => { if (!catsOf.has(i.dn)) catsOf.set(i.dn, []); catsOf.get(i.dn).push(c); }));

  const R = { site: SITE, generated: new Date().toISOString(), crawlGenerated: crawl.generated };
  const out = [];
  const say = (...a) => out.push(a.join(' '));

  // A) strom
  const lv = {}; cats.forEach(c => { const k = (c.crumbs || []).length; lv[k] = (lv[k] || 0) + 1; });
  say('=== A) STROM SEKCE ADR na obchod.fimas.cz ===');
  say('kategorií:', cats.length, 'podle hloubky:', JSON.stringify(lv), '| produktů (unikátních):', catsOf.size, '| e-shop (nový) položek:', merged.length);
  const emptyCats = cats.filter(c => !(c.items || []).length && !cats.some(x => (x.crumbs || []).length > (c.crumbs || []).length && (x.crumbs || []).slice(0, (c.crumbs || []).length).join('|') === (c.crumbs || []).join('|')));
  say('prázdné koncové kategorie (bez produktů):', emptyCats.length, emptyCats.slice(0, 15).map(c => leafName(c)).join(' | '));

  // B) chybějící produkty
  const missing = [...catsOf.keys()].filter(dn => !byDn.has(dn));
  R.missing = missing.map(dn => ({ dn, name: (crawlProd[dn] || {}).name, url: (crawlProd[dn] || {}).url, cats: catsOf.get(dn).map(leafName), inDataJson: djByDn.has(dn) }));
  say('\n=== B) PRODUKTY ZE SEKCE ADR, KTERÉ V NOVÉM E-SHOPU CHYBÍ:', missing.length, '===');
  R.missing.forEach(m => say(' -', 'd' + m.dn, m.name, '| kat.:', m.cats.join('; '), '| v data.json:', m.inDataJson ? 'ANO (odfiltrováno)' : 'NE'));

  // C) navíc v novém e-shopu
  const extra = merged.filter(p => { const dn = p.dn || L.extractDnum(p.url); return !dn || !catsOf.has(dn); });
  R.extra = extra.map(p => ({ id: p.id, dn: p.dn || L.extractDnum(p.url), name: p.name, slug: p.categorySlug, stock: p.stock, unverified: !!p.unverified }));
  say('\n=== C) V NOVÉM E-SHOPU NAVÍC (nejsou v sekci ADR na obchod.fimas.cz):', extra.length, '===');
  R.extra.forEach(p => say(' -', p.id, p.dn ? 'd' + p.dn : '(bez d-čísla)', p.name, '|', catName(p.slug), p.unverified ? '| NEOVĚŘENO (není v data.json)' : ''));

  // D) zařazení do kategorií
  say('\n=== D) ZAŘAZENÍ DO KATEGORIÍ (nový e-shop vs. obchod.fimas.cz) ===');
  const wrong = [];
  catsOf.forEach((cl, dn) => {
    const p = byDn.get(dn); if (!p) return;
    const normal = cl.filter(c => !isType(c) && (c.crumbs || []).length >= 2 && !/^TYP |JAK URČIT|KATALOG/i.test(leafName(c)));
    if (!normal.length) return;
    const exp = [...new Set(normal.map(c => L.resolveCategory(leafName(c), p.name)))];
    if (!exp.includes(p.categorySlug)) wrong.push({ dn, name: p.name, now: catName(p.categorySlug), expected: exp.map(catName), from: normal.map(leafName) });
  });
  R.wrongCategory = wrong;
  say('produktů v jiné kategorii, než odpovídá obchod.fimas.cz:', wrong.length);
  wrong.forEach(w => say(' -', 'd' + w.dn, w.name, '| je v:', w.now, '| má být:', w.expected.join(' / '), '| (e-shop:', w.from.join('; ') + ')'));
  // kategorie e-shopu bez mapování (spadnou do „Příslušenství brzdy“)
  const unmapped = cats.filter(c => !isType(c) && (c.crumbs || []).length >= 2 && (c.items || []).length && !L.DATA_CAT_MAP[leafName(c)] && L.resolveCategory(leafName(c), '') === 'brake-accessories');
  say('kategorie obchod.fimas.cz bez vlastního mapování (→ Příslušenství brzdy):', unmapped.map(c => leafName(c) + ' (' + c.items.length + ')').join(' | ') || '-');
  // počty podle kategorií
  say('\npočty položek: obchod.fimas.cz → nový e-shop (stejný slug):');
  const cntRows = [];
  cats.filter(c => !isType(c) && (c.crumbs || []).length === 2).forEach(c => {
    const nm = leafName(c);
    const own = new Set((c.items || []).map(i => i.dn));
    cats.forEach(x => { if ((x.crumbs || []).length > 2 && x.crumbs[1] === nm) (x.items || []).forEach(i => own.add(i.dn)); });
    const slug = L.resolveCategory(nm, '');
    const inNew = [...own].filter(dn => byDn.has(dn)).length;
    cntRows.push([nm, own.size, inNew, catName(slug)]);
  });
  cntRows.forEach(r => say(' -', r[0] + ':', r[1], '→', r[2], '(' + r[3] + ')', r[1] !== r[2] ? '  << ROZDÍL' : ''));

  // E) TYP podsekce
  say('\n=== E) TYP NÁPRAVY / TYP BRZDY ===');
  const typeCats = cats.filter(isType);
  const djCats = new Set(dataJson.map(p => p.category));
  const typeMissing = typeCats.filter(c => !djCats.has(leafName(c)));
  say('podsekcí na obchod.fimas.cz:', typeCats.length, '| chybí v data.json (nový e-shop je nezná):', typeMissing.length, typeMissing.map(c => leafName(c) + ' (' + (c.items || []).length + ')').join(' | '));
  let typeItemMiss = [];
  typeCats.forEach(c => { const nm = leafName(c); (c.items || []).forEach(i => { const e = djByDn.get(i.dn) || []; if (!e.some(x => x.category === nm)) typeItemMiss.push(nm + ': d' + i.dn + ' ' + (i.title || '')); }); });
  say('položek v podsekcích, které data.json k dané podsekci nemá:', typeItemMiss.length); typeItemMiss.slice(0, 60).forEach(x => say(' -', x));
  R.typeMissing = typeMissing.map(leafName); R.typeItemMiss = typeItemMiss;

  // F) fotky
  say('\n=== F) FOTKY ===');
  const noImg = [], diffImg = [], gal = [];
  catsOf.forEach((cl, dn) => {
    const p = byDn.get(dn), c = crawlProd[dn]; if (!p || !c || c.error) return;
    if (c.image && !p.image) noImg.push('d' + dn + ' ' + p.name);
    else if (c.image && p.image && base(c.image) !== base(p.image)) diffImg.push('d' + dn + ' ' + p.name + ' | nový: ' + base(p.image) + ' | obchod: ' + base(c.image));
    if ((c.gallery || []).length > 1) gal.push('d' + dn + ' ' + p.name + ' (' + c.gallery.length + ' fotek)');
  });
  say('bez fotky v novém e-shopu (na obchod.fimas.cz fotka je):', noImg.length); noImg.forEach(x => say(' -', x));
  say('jiná fotka než na obchod.fimas.cz:', diffImg.length); diffImg.forEach(x => say(' -', x));
  say('produkty s více fotkami (nový e-shop ukazuje jen 1):', gal.length); gal.slice(0, 40).forEach(x => say(' -', x));
  const noImgShop = Object.values(crawlProd).filter(p => !p.error && !p.image).map(p => 'd' + p.dn + ' ' + p.name);
  say('bez fotky i na obchod.fimas.cz:', noImgShop.length, noImgShop.slice(0, 20).join(' | '));
  R.noImg = noImg; R.diffImg = diffImg; R.gallery = gal;

  // G) popisy, tabulky, parametry
  say('\n=== G) POPISY, TABULKY, PARAMETRY ===');
  const P = Object.values(crawlProd).filter(p => !p.error);
  const withDesc = P.filter(p => p.descId), withTab = P.filter(p => p.descTables), withImgD = P.filter(p => p.descImgs), withPar = P.filter(p => (p.params || []).length);
  const newHasDesc = merged.filter(p => p.desc || p.descHtml).length;
  say('produkty s popisem:', withDesc.length, '| s tabulkou v popisu:', withTab.length, '| s obrázkem/výkresem v popisu:', withImgD.length, '| s tabulkou parametrů:', withPar.length, '| unikátních popisů:', Object.keys(crawl.descriptions).length);
  say('nový e-shop zobrazuje popis u:', newHasDesc, 'produktů');
  const catDesc = cats.filter(c => c.desc);
  say('kategorie s vlastním obsahem (text/tabulky/obrázky):', catDesc.length, '| s tabulkou:', catDesc.filter(c => c.desc.includes('<table')).length, '| s obrázky:', catDesc.filter(c => c.desc.includes('<img')).length);
  catDesc.forEach(c => say(' -', leafName(c), '|', c.desc.length, 'B', c.desc.includes('<table') ? '| TABULKA' : '', c.desc.includes('<img') ? '| OBRÁZKY ' + (c.desc.match(/<img/g) || []).length : ''));

  // H) název / cena / sklad
  say('\n=== H) NÁZEV, CENA, SKLAD (nový e-shop vs. obchod.fimas.cz) ===');
  const dName = [], dPrice = [], dStock = [];
  catsOf.forEach((cl, dn) => {
    const p = byDn.get(dn), c = crawlProd[dn]; if (!p || !c || c.error) return;
    if (c.name && p.name && c.name.trim() !== p.name.trim()) dName.push('d' + dn + ' nový: ' + p.name + ' | obchod: ' + c.name);
    const li = (cl[0].items || []).find(i => i.dn === dn) || {};
    const cp = num(li.price) || num(c.price);
    const np = Math.round(p.price * 1.21 * 100) / 100;
    if (cp && Math.abs(cp - np) > Math.max(1, cp * 0.005) && Math.abs(cp - p.price) > 1) dPrice.push('d' + dn + ' ' + p.name + ' | nový s DPH: ' + np + ' | obchod: ' + cp);
    const cs = c.stock === 'skladem';
    if (c.stock !== '?' && cs !== !!p.stock) dStock.push('d' + dn + ' ' + p.name + ' | nový: ' + (p.stock ? 'skladem' : 'není') + ' | obchod: ' + c.stock);
  });
  say('jiný název:', dName.length); dName.slice(0, 50).forEach(x => say(' -', x));
  say('jiná cena:', dPrice.length); dPrice.slice(0, 50).forEach(x => say(' -', x));
  say('jiný stav skladu:', dStock.length); dStock.slice(0, 50).forEach(x => say(' -', x));
  R.diffName = dName; R.diffPrice = dPrice; R.diffStock = dStock;

  fs.writeFileSync(path.join(HOME, 'adr_report.txt'), out.join('\n'));
  fs.writeFileSync(path.join(HOME, 'adr_report.json'), JSON.stringify(R, null, 1));
  console.log('REPORT', out.length, 'řádků → ~/adr_report.txt');
})().catch(e => { console.error('CHYBA', e); process.exit(1); });
