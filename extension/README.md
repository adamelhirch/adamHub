# AdamHUB Connect (extension Chrome)

Petite extension qui synchronise tes sessions **Carrefour**, **Intermarché** et
**Uber Eats** avec ton instance AdamHUB. Elle évite la corvée d'export manuel
des cookies — un clic dans la popup, et le hub a une session valide.

## Installation (sideload)

1. Ouvre Chrome → **chrome://extensions**
2. Active **Mode développeur** en haut à droite
3. Clique **Charger l'extension non empaquetée**
4. Sélectionne le dossier `extension/` de ce repo

L'icône AdamHUB apparaît dans la barre. Épingle-la (clic sur la pièce de puzzle
puis le pin).

## Première configuration

L'extension v0.2 n'a **plus aucune saisie**. Auth via le hub.

1. Ouvre `http://127.0.0.1:5173` (l'app AdamHUB) dans Arc/Chrome
2. Crée un compte ou connecte-toi
3. Click sur l'icône AdamHUB Connect → la popup affiche automatiquement « ✓ ton prénom »
4. Sinon : click sur **« Ouvrir AdamHUB »** dans la popup → connecte-toi → reviens dans la popup

## Connecter un magasin

1. Connecte-toi normalement sur **carrefour.fr** / **intermarche.com** /
   **ubereats.com** dans Chrome (avec l'adresse de livraison choisie côté
   Carrefour/UE).
2. Clique l'icône AdamHUB → bouton **Connecter** à côté du magasin.
3. L'extension lit les cookies (y compris les `HttpOnly`) via l'API
   `chrome.cookies` et les pousse vers `POST /supermarket/connections/import`.
4. La popup affiche `✓ Carrefour synchronisé` avec la date — c'est tout.

Tu peux refaire **Connecter** quand tu veux pour remplacer une session expirée
(la déduplication backend se fait par `(store, label)`).

## Multi-comptes

Pour ajouter le compte de quelqu'un d'autre :

1. La 2e personne installe l'extension de son côté (sideload, mêmes étapes)
2. Configure l'URL + sa propre clé API + son étiquette (`Sophie`)
3. Connecte ses magasins normalement

Côté hub, on retrouve une connexion par étiquette ; on peut basculer entre
elles via `PUT /supermarket/connections/{id}/activate` (ou un dropdown frontend
à venir).

## Permissions demandées

- `cookies` — pour lire les cookies des 3 domaines (HttpOnly inclus)
- `storage` — pour mémoriser l'URL du hub + la clé API localement
- `host_permissions` limitées à `*.carrefour.fr`, `*.intermarche.com`,
  `*.ubereats.com`. L'extension ne touche **aucun** autre site.

L'extension n'envoie de données qu'au hub configuré (HTTPS recommandé pour la
prod).
