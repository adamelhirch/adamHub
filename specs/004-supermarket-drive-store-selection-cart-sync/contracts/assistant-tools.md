# Contract: Assistant & MCP Tools

**Module**: `app/skill/actions.py`, `app/mcp/server.py`
**Skill Documentation**: `adamhub-assistant/SKILL.md` (Catégorie `Supermarket / Drive`)

---

## 1. Action `supermarket.search_stores`
Permet à l'assistant de trouver les points de retrait drive (quai, spot, TAPE, piéton) à proximité d'un lieu.

### Parameters
```json
{
  "store": {
    "type": "string",
    "enum": ["leclerc", "auchan", "carrefour", "intermarche"],
    "description": "Enseigne ciblée (optionnel, recherche globale si omis)"
  },
  "query": {
    "type": "string",
    "description": "Code postal ou ville (ex. '31700' ou 'Blagnac')"
  }
}
```

### Response
```json
{
  "success": true,
  "stores": [
    {
      "store": "leclerc",
      "store_id": "0123",
      "name": "E.Leclerc Drive Blagnac",
      "address": "Zone Commerciale du Grand Noble, 31700 Blagnac",
      "pickup_type": "quai",
      "distance_km": 2.4
    },
    {
      "store": "leclerc",
      "store_id": "0123_TAPE_1",
      "name": "Borne TAPE Leclerc Cornebarrieu",
      "address": "Route de Colomiers, 31700 Cornebarrieu",
      "pickup_type": "tape",
      "distance_km": 4.8
    }
  ]
}
```

---

## 2. Action `supermarket.set_favorite_store`
Enregistre ou modifie le magasin drive favori de l'utilisateur.

### Parameters
```json
{
  "store": {
    "type": "string",
    "enum": ["leclerc", "auchan", "carrefour", "intermarche"],
    "description": "Enseigne ciblée"
  },
  "store_id": {
    "type": "string",
    "description": "Identifiant technique du magasin sélectionné"
  },
  "pickup_type": {
    "type": "string",
    "enum": ["quai", "spot", "tape", "pieton"],
    "description": "Typologie de retrait"
  },
  "optimization_strategy": {
    "type": "string",
    "enum": ["mdd", "budget", "bio"],
    "default": "mdd",
    "description": "Stratégie d'optimisation souhaitée"
  }
}
```

---

## 3. Action `supermarket.prepare_cart`
Lance la préparation locale (staging) du panier drive à partir des articles non cochés de la liste de courses.

### Parameters
```json
{
  "store": {
    "type": "string",
    "enum": ["leclerc", "auchan", "carrefour", "intermarche"],
    "description": "Enseigne (si omise, utilise le premier magasin configuré)"
  },
  "optimization_strategy": {
    "type": "string",
    "enum": ["mdd", "budget", "bio"],
    "description": "Surcharge optionnelle de la stratégie (ex. 'bio' pour cette commande)"
  }
}
```

### Assistant Response Behavior
L'assistant restitue un bilan synthétique :
- Nombre d'articles appariés avec succès.
- Éventuelles substitutions proposées avec différentiel de prix.
- Montant total estimé.
- Lien interactif vers l'écran de revue.
- Invitation à valider directement : *"Voulez-vous que je transfère ce panier chez [Enseigne] ?"*

---

## 4. Action `supermarket.confirm_cart_sync`
Valide le job de staging préparé et pousse les articles vers le panier distant du commerçant.

### Parameters
```json
{
  "job_id": {
    "type": "integer",
    "description": "Identifiant du job de staging préparé"
  }
}
```

---

## 5. Action `supermarket.confirm_pickup`
Confirme le retrait physique au supermarché, coche les articles et réapprovisionne le garde-manger.

### Parameters
```json
{
  "job_id": {
    "type": "integer",
    "description": "Identifiant du job terminé"
  }
}
```
