# Reverse-engineering Leclerc Drive & Auchan (recherche + panier)

Découvert par analyse des HAR capturés en session connectée (août 2026). Ce
document fige les endpoints réels pour que les scrapers ne repartent pas de
placeholders inventés.

## Constat transversal

Les deux enseignes servent la **recherche en HTML serveur-rendu**, pas en API
JSON. Le panier, lui, passe par des endpoints dédiés (JSON / form-urlencoded).

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

**Le prix n'est pas dans le HTML de recherche.** Il est lazy-loadé via le
bouton « Afficher le prix », qui déclenche un appel de disponibilité :

```
GET https://api.auchan.fr/xsell/v0/cross-sell/availability/{productId}?activeContexts=GROCERY--{sellerId}__PICK_UP
```

`productId` est un UUID (`e7ab4048-9672-4ac9-9bd5-db28cd6500a6`), pas un entier.
`sellerId` vient du contexte sélectionné (`4c663296-54a8-45f6-b385-0be86b4dfe98`
= le magasin GROCERY). `offerId` est un autre UUID distinct.

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

## Conséquences pour les scrapers

1. **Recherche = parsing HTML**, pas un appel JSON. Il faut `httpx` + `BeautifulSoup`
   (déjà utilisé par Intermarché/Carrefour), avec les cookies de session.
2. **Leclerc** : le sous-domaine (`fdN-courses`) et le `magasin-{plid}-{plid}-{slug}`
   dépendent du point de livraison sélectionné → il faut persister le
   `SupermarketStoreSelection` (déjà prévu) pour reconstruire l'URL.
3. **Auchan** : le prix est lazy et nécessite le contexte magasin sélectionné
   (`journey` / `offering-contexts`) puis un appel d'availability par produit.
   Sans prix dans le HTML, la recherche devra soit renoncer au prix, soit faire
   N+1 appels d'availability (coûteux).

## Reste à valider en live (bloqué sans session)

- Sélecteurs CSS exacts des cartes produit Leclerc (`recherche.aspx`) et du
  prix dans le HTML Auchan (si jamais présent après sélection de magasin).
- Endpoint exact d'availability Auchan qui renvoie le prix (corps de réponse
  non capturé dans le HAR).
