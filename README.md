# adrparts.cz – nasazení e-shopu (větev adrparts-eshop)

Soubory pro nasazení e-shopu ADR Parts na Firebase Hosting (projekt adr-fimas, doména adrparts.cz).

- `public/index.html` – e-shop (React, jeden soubor)
- `public/sw.js` – service worker, maže mezipaměť starého katalogu
- `public/manifest.json` – PWA manifest
- `deploy_hosting.py` – nasazení přes Firebase Hosting REST API (spouští se v Google Cloud Shellu)
- `firestore.rules` – pravidla databáze (účty, objednávky, odstoupení)
- `cloud-function-email/` – Cloud Function adr-email-sender (e-maily objednávek)

Nasazení v Cloud Shellu:
```
git clone -b adrparts-eshop --depth 1 https://github.com/pajulinux-hash/fimas-web.git adrparts-deploy
cd adrparts-deploy && python3 deploy_hosting.py
```
