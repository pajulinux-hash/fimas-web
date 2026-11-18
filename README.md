# fimas.cz – nový web (GitHub Pages)

Statický web bez buildu: `index.html` + pomocné soubory.

## Nasazení
1. Na GitHubu vytvořte repozitář (např. `pajulinux-hash/fimas-web`) a nahrajte obsah této složky.
2. Settings → Pages → Source: *Deploy from a branch*, větev `main`, složka `/ (root)`.
3. Až bude doména přesměrovaná: Settings → Pages → Custom domain: `www.fimas.cz`, po ověření zapněte *Enforce HTTPS* (GitHub sám vytvoří soubor CNAME).

## DNS (požadavek na správce domény)
| Záznam | Název | Hodnota |
|---|---|---|
| CNAME | www | pajulinux-hash.github.io. |
| A | @ (fimas.cz) | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |

Původní A/CNAME záznamy směřující na Webnode je nutné odstranit. Subdoménu `obchod.fimas.cz` (e-shop) **neměnit**.

## Ceník
- Skrytý odkaz: znak **©** v patičce.
- Přímá adresa: `www.fimas.cz/cenik/` (přesměrování, `noindex`, zakázáno v robots.txt).

## Údržba
- Oznámení nahoře: blok `#notice` v `index.html`, skryje se sám den po `data-until`.
- Fotky galerie jsou v `img/g/` (plná velikost, WebP) a `img/g/t/` (náhledy). Seznam alb je v `index.html` v proměnné `GAL`.
- Dokumenty (obchodní podmínky, GDPR) jsou ve složce `docs/`.
- Oznámení nahoře se upravuje v souboru `oznameni.txt`.
