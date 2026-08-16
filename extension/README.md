# AdamHUB Connect (extension Chrome)

Petite extension qui synchronise tes sessions **Carrefour**, **Intermarché**,
**Leclerc** et **Auchan** avec ton instance AdamHUB. Elle évite la corvée
d'export manuel des cookies — un clic dans la popup, et le hub a une session
valide.

## Installation (sideload)

1. Ouvre Chrome → **chrome://extensions**
2. Active **Mode développeur** en haut à droite
3. Clique **Charger l'extension non empaquetée**
4. Sélectionne le dossier `extension/` de ce repo

L'icône AdamHUB apparaît dans la barre. Épingle-la (clic sur la pièce de puzzle
puis le pin).

## Comment ça marche

L'extension est en v0.2 : les URLs sont **codées en dur** dans `popup.js` —
hub sur `http://127.0.0.1:8000` (`HUB_URL`), frontend sur
`http://127.0.0.1:5173` / `http://localhost:5173` (et `5174`, `FRONTEND_URLS`). Il n'y a
**pas de page d'options** : rien n'est configurable depuis l'extension pour
l'instant.

L'authentification se fait via le hub :

1. Connecte-toi sur l'app AdamHUB dans un onglet (`http://127.0.0.1:5174` — ou `5173`).
2. L'extension lit le **JWT** `adamhub_token` dans le `localStorage` de cet
   onglet (`chrome.scripting.executeScript`) puis le **met en cache** dans
   `chrome.storage.local` (clé `token`).
3. À l'ouverture de la popup, elle affiche ton prénom
   (`GET /api/v1/auth/me` avec le token) ; sinon un bouton **« Ouvrir
   AdamHUB »** invite à se connecter.
4. Si le token est expiré ou invalide (HTTP 401 à l'import), le cache est
   purgé et il faut se reconnecter sur AdamHUB.

## Connecter un magasin

1. Connecte-toi normalement sur **carrefour.fr** / **intermarche.com** /
   **leclercdrive.fr** / **auchan.fr** dans Chrome (avec l'adresse de
   livraison choisie côté Drive).
2. Clique l'icône AdamHUB → bouton **Connecter** à côté du magasin.
3. L'extension lit les cookies (y compris les `HttpOnly`) via l'API
   `chrome.cookies` et les pousse vers
   `POST /api/v1/supermarket/connections/import` avec le token du hub.
4. La popup affiche `✓ Carrefour synchronisé` avec la date — c'est tout.
   L'horodatage est mémorisé dans `chrome.storage.local` (clé `lastSync`).

Tu peux refaire **Connecter** quand tu veux pour remplacer une session
expirée.

## Auchan — fonctionne sans compte

Contrairement aux autres enseignes, **Auchan n'exige pas de compte** : une
session de navigation anonyme suffit (le prix est rendu dans le HTML dès qu'un
magasin est sélectionné). Les cookies de session sont quand même utiles au
scraper (via l'import ci-dessus), mais tu peux aussi utiliser Auchan sans
passer par l'extension : dans l'app, choisis ton magasin (code postal →
liste des magasins) puis lance la recherche — aucun login requis.

## Plusieurs comptes

Pas de configuration par utilisateur : chaque personne installe l'extension de
son côté et se connecte à son **propre compte AdamHUB** dans un onglet.
L'extension synchronise les magasins sous l'identité du token en cours ; une
connexion est créée par magasin avec une étiquette vide (`label: ""`).

## Permissions demandées

- `cookies` — pour lire les cookies des domaines magasins (HttpOnly inclus)
- `storage` — pour **mémoriser le token JWT et l'horodatage `lastSync`**
  localement
- `scripting` + `tabs` — pour lire le token depuis l'onglet AdamHUB ouvert
- `host_permissions` limitées à `127.0.0.1:5173` / `localhost:5173`,
  `127.0.0.1:5174` / `localhost:5174` et `127.0.0.1:8000` / `localhost:8000`
  (hub local), plus `*.carrefour.fr`,
  `*.intermarche.com`, `*.leclercdrive.fr`, `*.auchan.fr`. L'extension ne
  touche **aucun** autre site.

L'extension n'envoie de données qu'au hub local codé en dur
(`http://127.0.0.1:8000`).
