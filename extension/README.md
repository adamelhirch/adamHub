# AdamHUB Connect (extension Chrome)

Extension **Manifest V3** qui synchronise tes sessions **Carrefour**,
**Intermarché**, **Leclerc** et **Auchan** avec ton instance AdamHUB. Fini
l'export manuel des cookies : l'extension lit les cookies des enseignes
(HttpOnly compris) et les pousse vers le hub, en arrière-plan et à la demande.

## Installation (sideload)

1. Ouvre Chrome → **chrome://extensions**
2. Active **Mode développeur** en haut à droite
3. Clique **Charger l'extension non empaquetée**
4. Sélectionne le dossier `extension/` de ce repo

L'icône AdamHUB apparaît dans la barre. Épingle-la (clic sur la pièce de puzzle
puis le pin) pour accéder à la popup.

## Version

**v0.3.0** — Manifest V3. Les URLs et la fréquence de synchro sont
**configurables** via la page d'options, et la synchro **automatique** tourne
dans le service worker en arrière-plan.

## Comment ça marche

1. **Authentification** : connecte-toi sur l'app AdamHUB dans un onglet (par
   défaut `http://localhost:5173`). L'extension lit le **JWT** `adamhub_token`
   dans le `localStorage` de cet onglet (`chrome.scripting.executeScript`) puis
   le **met en cache** dans `chrome.storage.local` (clé `token`).
2. **Popup** : à l'ouverture, elle affiche ton prénom
   (`GET /api/v1/auth/me`) et l'état de chaque enseigne ; sinon un bouton
   **« Ouvrir AdamHUB »** t'invite à te connecter.
3. **Synchro** : pour chaque enseigne active, l'extension lit les cookies
   (`chrome.cookies`, HttpOnly inclus), vérifie la présence du marqueur de
   session, puis pousse vers `POST /api/v1/supermarket/connections/import`.
4. **En arrière-plan** : le service worker re-synchronise automatiquement (voir
   « Synchronisation automatique »).
5. Si le token est expiré ou invalide (HTTP 401 à l'import), le cache est purgé
   et il faut se reconnecter sur AdamHUB.

## Page de réglages

Clic droit sur l'icône AdamHUB → **Options** (ou `chrome://extensions` →
Détails → **Options de l'extension**). Tu peux régler :

- **URL API (hub)** — backend AdamHUB (défaut `http://127.0.0.1:8000`)
- **URL frontend** — app AdamHUB (défaut `http://localhost:5173`)
- **Fréquence de synchro** — en heures (défaut `6`)
- **Cooldown** — délai minimal entre deux synchros d'une même enseigne, en
  minutes (défaut `30`)
- **Enseignes actives** — coche/décoche pour mettre une enseigne en pause

Les réglages sont stockés dans `chrome.storage.sync` et relus à la fois par la
popup et par le service worker. Le bouton **Réinitialiser** revient aux valeurs
par défaut.

## Synchronisation automatique

Le service worker (`background.js`) déclenche la synchro dans ces cas :

- **à l'installation / mise à jour** : planifie l'alarme périodique et tente une
  synchro immédiate (ou invite à se reconnecter si aucun token n'est en cache)
- **au démarrage du navigateur** : restaure l'alarme périodique
- **à l'alarme périodique** : re-synchronise les enseignes actives (toutes les
  `syncIntervalHours`)
- **au chargement d'un onglet d'enseigne** : synchronise cette enseigne (en
  respectant le cooldown)

Un échec de synchro ou une session hub expirée produit une **notification** ;
cliquer dessus ouvre AdamHUB le cas échéant.

## Marqueurs de session par enseigne

Pour être synchronisée, une enseigne doit avoir une session active : l'extension
vérifie la présence du cookie marqueur avant d'importer.

| Enseigne    | Cookie marqueur | Site                           |
| ----------- | --------------- | ------------------------------ |
| Carrefour   | `FRO_CONNECTED` | https://www.carrefour.fr/      |
| Intermarché | `itm_session`   | https://www.intermarche.com/   |
| Leclerc     | `.XPRSDRVAUTH`  | https://www.leclercdrive.fr/   |
| Auchan      | `lark-session`  | https://www.auchan.fr/         |

Si le marqueur manque, la synchro de l'enseigne est ignorée avec le message
« Pas de session … active ».

## Connecter un magasin (à la demande)

1. Connecte-toi normalement sur **carrefour.fr** / **intermarche.com** /
   **leclercdrive.fr** / **auchan.fr** dans Chrome (avec l'adresse de livraison
   choisie côté Drive).
2. Ouvre la popup AdamHUB → bouton **Synchroniser maintenant** (ou laisse la
   synchro auto le faire).
3. La popup affiche `✓ … synchronisé le … à …` par enseigne. L'horodatage est
   mémorisé dans `chrome.storage.local` (clé `lastSync`).

Tu peux relancer la synchro quand tu veux pour remplacer une session expirée.

## Auchan — fonctionne sans compte

Contrairement aux autres enseignes, **Auchan n'exige pas de compte** : une
session de navigation anonyme suffit (le prix est rendu dans le HTML dès qu'un
magasin est sélectionné). Les cookies de session sont quand même utiles au
scraper (via l'import ci-dessus), mais tu peux aussi utiliser Auchan sans passer
par l'extension : dans l'app, choisis ton magasin (code postal → liste des
magasins) puis lance la recherche — aucun login requis.

## Plusieurs comptes

Pas de configuration par utilisateur : chaque personne installe l'extension de
son côté et se connecte à son **propre compte AdamHUB** dans un onglet.
L'extension synchronise les magasins sous l'identité du token en cours ; une
connexion est créée par magasin avec une étiquette vide (`label: ""`).

## Permissions demandées

- `alarms` — alarme périodique de synchro
- `cookies` — lire les cookies des domaines magasins (HttpOnly inclus)
- `notifications` — notifier les échecs de synchro / expirations de session
- `scripting` — lire le token depuis l'onglet AdamHUB ouvert
- `storage` — mémoriser le token, `lastSync` et les réglages
- `tabs` — ouvrir AdamHUB et détecter les onglets d'enseignes

`host_permissions` limitées à `127.0.0.1` / `localhost` sur les ports `5173` et
`5174` (frontend) et `8000` (hub), plus `*.carrefour.fr`,
`*.intermarche.com`, `*.leclercdrive.fr`, `*.auchan.fr`. L'extension ne touche
**aucun** autre site, et n'envoie de données qu'au hub configuré (défaut
`http://127.0.0.1:8000`).

## Dépannage

- **« Pas de session Carrefour active » (ou autre)** — le cookie marqueur est
  absent : reconnecte-toi sur l'enseigne, puis relance la synchro.
- **« Aucun cookie … trouvé »** — ouvre le site de l'enseigne dans un onglet et
  connecte-toi avant de synchroniser.
- **« Session expirée » / HTTP 401** — le token hub est expiré : reconnecte-toi
  sur AdamHUB (l'extension t'y invite ou ouvre l'onglet).
- **Rien ne se synchronise** — vérifie la page d'options : l'enseigne est-elle
  cochée ? L'URL API pointe-t-elle bien vers ton hub ?
- **Synchro trop fréquente / trop rare** — ajuste la fréquence (heures) et le
  cooldown (minutes) dans les options ; l'alarme est (re)planifiée à
  l'installation et au démarrage du navigateur.
- **Le frontend tourne sur un autre port** — renseigne l'URL exacte dans les
  options : l'extension reconnaît `localhost` ↔ `127.0.0.1`, mais pas un port
  différent (`5173` vs `5174`).

## Tests

Le socle logique (`lib/`) est testé avec vitest, sans navigateur :

```bash
cd extension
npm test
```
