# Reverse-engineering des scrapers supermarchés (recherche + panier)

Découvert par analyse des HAR capturés en session connectée (août 2026). Ce
document fige les endpoints réels pour que les scrapers ne repartent pas de
placeholders inventés.

## Constat transversal

Les enseignes servent la **recherche en HTML serveur-rendu** (Leclerc, Auchan,
Intermarché) **sauf Carrefour**, qui expose un **endpoint JSON** (`/s?q=…&page=N`)
pour le catalogue. Le panier, lui, passe par des endpoints dédiés (JSON /
form-urlencoded).

---

## Leclerc Drive

Base : `www.leclercdrive.fr`. Après connexion + sélection d'un point de
livraison, le site bascule sur un sous-domaine **propre au magasin**, de la
forme `fdN-courses.leclercdrive.fr` (ex. `fd7-courses.leclercdrive.fr`), et les
URL portent l'identifiant du point de livraison (`123111` dans l'exemple) et le
slug du magasin (`Montaudran`).

### Sélection de magasin

- `GET api-recherchemagasins.leclercdrive.fr/API_RechercheMagasins/api/v1/MapPoint/nearby?latitude=..&longitude=..&postalCode=..` → liste des drives proches.
- `GET api-recherchemagasins.leclercdrive.fr/API_RechercheMagasins/api/v1/pointretrait/infomagasin/drive/pointlivraison/{id}` → détail du point de livraison.

### Recherche produit

```
GET https://{sous-domaine}/magasin-{plid}-{plid}-{slug}/recherche.aspx?TexteRecherche={query}
```

Réponse : HTML. Les produits sont des cartes serveur-rendues. Le HTML n'a pas
été capturé avec le corps dans le HAR → les sélecteurs CSS exacts restent à
confirmer sur une session live (voir plus bas).

### Panier

Endpoint unique `panier.aspx`, méthode POST, `Content-Type:
application/x-www-form-urlencoded; charset=UTF-8`, un seul champ `d` contenant
le JSON **url-encodé**.

Actions (champ `eTypeAction`) :
- `1` = ajouter (avec `iQuantite`)
- `2` = mettre à jour la quantité (ou retirer)

Payload décodé (ajout) :

```json
{
  "eTypeAction": 1,
  "iIdProduit": "123697",
  "iQuantite": 1,
  "sNoPointLivraison": "123111",
  "objContexteProvenanceArticle": {
    "eOrigine": 4,
    "eTypePage": 3,
    "sTexteRecherche": "lait",
    "eVue": 0,
    "sInformationsComplementaires": "uni-2"
  }
}
```

Payload décodé (retrait, quantité 0) :

```json
{"eTypeAction": 2, "iIdProduit": "129009", "iQuantite": 0, "sNoPointLivraison": "123111"}
```

Vider le panier : `POST .../panier.aspx?op=3` avec `d={}`.

L'`op` du query string (`op=1`, `op=3`) sélectionne l'opération au niveau de la
route. L'`iIdProduit` est un identifiant numérique du produit (pas l'EAN).

### Fiche produit (détail)

- `POST https://fd7-courses.leclercdrive.fr/magasin-{plid}-{plid}/fiche-produit-zones.ashz` → zones de la fiche.
- `POST https://dp.leclercdrive.fr/ficheproduit/FicheProduitJson.ashx` → JSON du produit (detail structuré).

### Anti-bot

`hCaptcha` (sitekey `c6fbe695-...`) est chargé sur certaines actions. Une
session cookie valide + UA Chrome est le prérequis minimal ; certaines actions
peuvent déclencher le hCaptcha.

---

## Auchan

Base : `www.auchan.fr` ; API JSON sous `api.auchan.fr`.

### Sélection de magasin / contexte

- `GET https://www.auchan.fr/offering-contexts?address.zipcode=..&address.city=..&location.latitude=..&location.longitude=..` → contextes de vente (GROCERY / drive / livraison).
- `GET https://www.auchan.fr/journey` → JSON du parcours courant (magasin sélectionné).
- `POST https://www.auchan.fr/journey/update` → change le contexte/magasin.

Le prix réel dépend du contexte sélectionné (magasin) ; sans contexte, la
recherche affiche « Afficher le prix » au lieu du prix.

### Recherche produit

```
GET https://www.auchan.fr/recherche?text={query}&sort={sort_key}
```

Réponse : HTML serveur-rendu. Structure d'une carte produit :

```html
<article itemscope itemtype="http://schema.org/Product"
         class="product-thumbnail ... outOfStock"
         data-id="{productId-uuid}">
  <a class="product-thumbnail__details-wrapper ..."
     href="/lait-de-savoie-lait-demi-ecreme-uht/pr-C1799228"
     data-id="{productId-uuid}">
    ...
    <p class="product-thumbnail__description" itemprop="name description">
      <strong itemprop="brand">LACTEL</strong>
      Lait demi-écrémé avec vitamine D
    </p>
    <div class="product-thumbnail__attributes">
      <span class="product-attribute" aria-label="Contenance : 8x1l">8x1l</span>
      ...
    </div>
    <meta itemprop="image" content="https://cdn.auchan.fr/media/...">
  </a>
  <footer>
    <button class="product-thumbnail__see-prices-button ... productItemAvailabilityTrigger">
      Afficher le prix
    </button>
  </footer>
</article>
```

**Le prix est présent dans le HTML de recherche quand un magasin est
sélectionné.** Il est dans un bloc `itemprop="offers"` de la carte :

```html
<div class="product-thumbnail__price product-price__container"
     itemprop="offers" itemscope itemtype="http://schema.org/Offer">
  <div class="product-price bolder text-dark-color">7,62€</div>
  <meta itemprop="price" content="7.62">
  <meta itemprop="priceCurrency" content="EUR">
</div>
```

Sans magasin sélectionné, ce bloc est remplacé par le bouton « Afficher le
prix » (lazy-load via `availability`). Le scraper lit `meta[itemprop=price]` +
`meta[itemprop=priceCurrency]`, et expose les identifiants panier depuis les
data-attributs de la carte (`data-current-offer-id`, `data-seller-id` du
`.quantity-selector`).

Champs d'identification produit (nécessaires au panier) :
- `productId` (UUID)
- `offerId` (UUID)
- `sellerId` (UUID du contexte/magasin)

### Panier

Deux chemins coexistent :

1. Ajout « léger » (page) :
   ```
   POST https://www.auchan.fr/cart/update
   Content-Type: application/json
   {
     "cartId": "14382b45-...",
     "items": [{
       "productId": "e7ab4048-...",
       "offerId": "c21f64ea-...",
       "sellerType": "GROCERY",
       "sellerId": "4c663296-...",
       "desiredQuantity": 1,
       "desiredType": "DEFAULT"
     }],
     "consentId": "98c5a148-...",
     "reservationId": null,
     "mbaAvailabilityNeeded": true
   }
   ```

2. API checkout (quantité incrément / décrément / suppression) :
   ```
   POST https://api.auchan.fr/checkout/v1/carts/{cartId}/items?consentId={consentId}
   [{ "id": "{line-id}", "productId": "...", "offerId": "...", "desiredQuantity": 0 }]
   ```
   (`desiredQuantity: 0` = retirer ; sans `id` = ajout d'une ligne.)

Autres endpoints :
- `GET https://api.auchan.fr/checkout/v1/carts/mine?consentId=...` → panier courant.
- `DELETE https://api.auchan.fr/checkout/v1/carts/{cartId}?consentId=...` → vider le panier.
- `GET https://api.auchan.fr/checkout/v1/carts/{cartId}/discount-markup?consentId=...` → remises.

Le `consentId` et le `cartId` sont obtenus à la première interaction panier
(`GET /cart/config`, `GET /cart?consentId=...`, `POST /cart/update`).

---

## Carrefour

Base : `www.carrefour.fr`. Depuis août 2026, le site sert la **recherche en
JSON** — le parsing du SSR `__INITIAL_STATE__` (format Devalue) a été retiré.

### Recherche produit (endpoint retenu)

```
GET https://www.carrefour.fr/s?q={query}&page=N
Accept: application/json, text/plain, */*
X-Requested-With: XMLHttpRequest
```

Réponse : `application/json` sous la forme

```json
{
  "data": [ { "type": "product", "id": "product-{ean}",
              "attributes": { "ean": "…", "title": "…", "brand": "…",
                              "slug": "…", "offers": { … }, "images": { … } },
              "links": { "self": "/p/{slug}-{ean}" } } ],
  "links": { "self": "/s?q=…", "next": "/s?q=…&page=N" },
  "meta": { "total": …, "totalPage": …, "currentPage": … }
}
```

- La **page 1** est rendue en HTML par le navigateur, mais le même endpoint
  renvoie du JSON quand il est appelé avec les headers XHR (confirmé par les
  requêtes `sort` dans le HAR). Le scraper passe donc `Accept: application/json`
  + `X-Requested-With: XMLHttpRequest`.
- **Tri** (param `sort`) : `offers.prices.effective_price`,
  `-offers.prices.effective_price`,
  `offers.prices.standard_price_per_unit.price_per_unit_value`,
  `-offers.prices.standard_price_per_unit.price_per_unit_value`,
  `-product.customer_review.average`. Mapping dans
  `CARREFOUR_SORT_KEYS` (`price_asc`, `price_desc`, `price_per_unit_asc`,
  `price_per_unit_desc`, `best_rated`).
- **Promotions** : le filtre `promotions_only` est appliqué côté client (une
  offre est « en promo » quand son bloc `promotion` est non-null ou sa liste
  `promotions` non vide).
- **Pagination** : suivre `links.next` jusqu'à `max_results` (30/page).
- Le prix par unité (`price.perUnitLabel`, ex. `1.58 € / L`) est concaténé au
  `price_text`.

### Endpoints écartés

- `POST /api/marketing/search` (et `search_panel` / `search_cross_sell`) :
  feed de merchandising (produits sponsorisés + groupes FS/BF), sans tri ni
  pagination — conservé uniquement comme parseur secondaire
  (`parse_carrefour_search`).
- **Panier** : `GET/PATCH/DELETE /api/cart`, `PATCH /api/cart/items` — hors
  périmètre.

### Matrice connexion (validation live, lecture seule)

| Cas | Résultat attendu | Constat |
|---|---|---|
| Recherche sans cookies | `CarrefourAuthError` (pas de cookies) | Le scraper lève avant tout appel réseau quand `data/cookies_carrefour.json` manque (testé offline) |
| Recherche avec cookies depuis une IP data-center | 403 Cloudflare | Confirmé live depuis l'environnement dev : 403 HTML même avec les cookies frais — Cloudflare bloque les IP data-center ; un proxy résidentiel (`ADAMHUB_CARREFOUR_PROXY_URL`) est requis hors navigateur |
| Recherche avec cookies depuis un navigateur réel (HAR) | 200 JSON | Confirmé dans `carrefour.har` / `carrefourr-recherche.har` : pages 2-19 + variantes `sort` servent du JSON |
| Prix sans login | Prix visibles sans login | Les offres (`offers.*.*.attributes.price`) sont présentes dans le JSON sans compte ; un Drive store doit être sélectionné pour que le prix corresponde au magasin |

Le prix est **store-specific** : le scraper lit le prix de l'offre canonique
`subType == "carrefour"` dans `attributes.offers`, qui dépend du magasin porté
par la session cookies.

---

## Conséquences pour les scrapers

1. **Recherche = parsing HTML**, pas un appel JSON. Il faut `httpx` + `BeautifulSoup`
   (déjà utilisé par Intermarché/Carrefour), avec les cookies de session.
2. **Leclerc** : le sous-domaine (`fdN-courses`) et le `magasin-{plid}-{plid}-{slug}`
   dépendent du point de livraison sélectionné → il faut persister le
   `SupermarketStoreSelection` (déjà prévu) pour reconstruire l'URL.
3. **Auchan** : le prix est dans le HTML quand un magasin est sélectionné
   (`meta[itemprop=price]`). Le contexte magasin est porté par les cookies de
   session ; sans lui, le HTML affiche « Afficher le prix » et le prix est
   absent (renvoyé `None` par le scraper).

## Reste à valider en live (bloqué sans session)

- Le sous-domaine Leclerc (`fdN-courses`) et le `magasin-{plid}-{plid}-{slug}`
  doivent être fournis via `ADAMHUB_LECLERC_BASE_URL` (ou un
  `SupermarketStoreSelection`) après sélection d'un Drive.
- L'endpoint d'ajout au panier Auchan n'est pas encore câblé (les identifiants
  `productId`/`offerId`/`sellerId` sont désormais exposés par le scraper).
