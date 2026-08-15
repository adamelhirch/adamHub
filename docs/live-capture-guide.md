# Guide de capture live — Leclerc Drive & Auchan

Objectif : fournir un fichier `.har` (HAR avec le corps des réponses) contenant le
trafic réseau d'une recherche produit sur chaque enseigne, afin de câbler les
vrais endpoints dans `app/services/scrapers/leclerc.py` et `auchan.py`.

Le `.har` suffit : il contient toutes les requêtes XHR/Fetch + les réponses JSON.
On n'a besoin de rien d'autre.

---

## Préparation DevTools (une seule fois, identique pour les deux)

1. Ouvrir le navigateur (Chrome ou Firefox, connecté à ton compte perso).
2. Ouvrir DevTools : `F12` (ou Cmd+Option+I sur Mac).
3. Onglet **Network**.
4. **Cocher « Preserve log »** (Chrome) pour garder le trafic quand la page
   rechange.
5. **Filtrer** sur `Fetch/XHR` (barre de filtre en haut du panneau Network).
6. On va ensuite exporter : bouton **↓ (Export HAR…)** en haut du panneau Network,
   ou clic droit → « Save all as HAR with content ». **Important : « with content »**
   pour que les réponses JSON soient dedans.

Fais les deux enseignes séparément (deux `.har`) : plus simple à trier.

---

## Leclerc Drive

URL : https://www.leclercdrive.fr/

Étapes :

1. Ouvrir la page d'accueil, puis **se connecter** (bouton « Se connecter » en
   haut à droite). Si pas de compte, en créer un.
2. **Sélectionner un magasin Drive** : entrer ton code postal et choisir le drive
   (les prix sont propres au magasin).
3. Aller dans le champ **recherche** et taper un produit simple, ex. `lait`.
4. Valider la recherche. La page de résultats est **servie en HTML serveur-rendu** :
   les produits sont dans un blob JSON embarqué (appel `initOptions('...pnlElementProduit', {..})`).
   C'est le corps HTML de `recherche.aspx` qu'on veut — pas des appels JSON séparés.
5. Optionnel mais utile : changer le tri (ex. « Prix croissant » → `tri=2`) et
   valider, pour capturer la page avec le paramètre `tri`.
6. Dans Network, repérer la requête `GET .../magasin-{plid}-{plid}-{slug}/recherche.aspx?TexteRecherche=...`
   (statut 200, type `text/html`) et vérifier que son corps contient bien `pnlElementProduit`.
7. Exporter le HAR **avec le contenu des réponses** (`Save all as HAR with content`) :
   sans les corps, le parsing HTML ne peut pas être vérifié.

Ce qu'on cherche dedans : le corps HTML de `recherche.aspx` (avec le blob
`pnlElementProduit`), les query params (`TexteRecherche`, `tri`), et un
échantillon des champs nom/prix/image.

---

## Auchan

URL : https://www.auchan.fr/

Étapes :

1. Ouvrir le site (la connexion n'est **pas requise** : une session cookie
   valide suffit, voir `auchan-paslogin.har`).
2. **Choisir un magasin** (bouton de sélection de magasin / localisation) pour
   avoir les prix du drive.
3. Dans la barre de recherche, taper `lait` et lancer la recherche.
4. La page de résultats est **serveur-rendue** (pas de XHR pour les produits) :
   le prix est dans le HTML quand le magasin est sélectionné.
5. Repérer dans Network : `GET /journey`, `GET /offering-contexts?address.*`,
   `POST /journey/update` (sélection magasin), `GET /recherche?text=..` (prix).
6. Exporter le HAR avec contenu. Le corps de `/recherche` est souvent absent du
   HAR (capture sans contenu) : capturer aussi la fiche produit
   (`/pouce-lait-demi-ecreme/pr-C1177649` par ex.) comme référence de structure.

Note : le domaine `api.drive.leclerc` qu'on avait mis dans le code au départ
était un placeholder faux — le scraper lit désormais le HTML serveur-rendu de
`recherche.aspx` (blob `pnlElementProduit`). Pour Auchan, le chemin de
recherche est `/recherche?text=..` (HTML SSR), pas une API JSON.

---

## Livraison

- Sauvegarder deux fichiers, ex. `data/live-capture/leclerc.har` et
  `data/live-capture/auchan.har`.
- Les fournir à l'agent (ou les poser dans `data/live-capture/`), qui s'en sert
  pour corriger les deux scrapers.
