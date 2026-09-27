# Feature Specification: Recipe App Interactions (Cooking Confirmation, Groceries Restock, and Smart Calendar Scheduling)

**Feature Branch**: `008-recipe-app-interactions`  
**Created**: 2026-09-12  
**Status**: Draft  
**Input**: User description: "On peut partir sur une nouvelle spec concernant les interactions qu'on peut faire avec les recettes sur l'appli. J'aimerais pouvoir dire que j'ai fait une recette et ça devrait soustraire les produits liés à cette recette de mon garde-manger. Je devrais pouvoir aussi ajouter les ingrédients liés à cette recette à mes courses dans le cas où je le souhaite. Planifier cette recette aussi serait pas mal, vu qu'il y a une durée estimée de cuisine, on va pouvoir la planifier, l'ajouter à mon calendrier, en respectant le fait qu'on ne peut pas mettre de choses qui chevauchent dans le calendrier. Si j'ai un truc à faire de 17h à 18h, je ne peux pas mettre ma recette à 17h."

---

## Clarifications

### Session 2026-09-12

- Q: Quel comportement exact doit déclencher le swipe vers la gauche sur une carte de recette dans la liste ? → A: Geste progressif : un swipe court déclenche « Cuisiné maintenant » (déstockage immédiat), un swipe long complet ouvre directement le calendrier de planification.
- Q: Comment l'application doit-elle réagir lorsque l'utilisateur déclenche « Cuisiné maintenant » (swipe court gauche) mais que certains ingrédients sont absents ou en quantité insuffisante dans le garde-manger ? → A: Animation de shake visuelle et haptique + déstockage de ce qui est disponible (plafonné à 0) + proposition immédiate en 1 tap : « Ingrédients manquants détectés. Les ajouter aux courses ? ».
- Q: Quel comportement exact doit se produire lors du swipe vers la droite pour ajouter les ingrédients de la recette à la liste de courses ? → A: Ouverture d'une feuille avec la liste des ingrédients cochables (ingrédients manquants pré-cochés par défaut), permettant de choisir précisément les articles à ajouter aux courses.
- Q: Sur quel écran de l'application mobile ces interactions de swipe s'appliquent-elles ? → A: Sur l'écran Cuisine de l'application Expo (`app-saas/src/app/(tabs)/kitchen.tsx`, section Recettes), directement sur les cartes de recettes, ainsi que via boutons d'action sur la fiche détaillée `/recipe/[id]`.
- Q: Quelles modifications directes de la recette l'utilisateur peut-il effectuer depuis l'application mobile ? → A: Modification directe des portions (avec calcul proportionnel dynamique des quantités d'ingrédients lors de la cuisine et des courses) et modification des instructions de la recette ; la taxonomie avancée des produits drive est reportée à une spec dédiée ultérieure.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Confirmation de cuisine et décrémentation du garde-manger (Priority: P1) 🎯 MVP

En tant qu'utilisateur de l'application AdamHUB, je souhaite indiquer directement depuis la fiche d'une recette que je viens de la cuisiner, afin que les ingrédients nécessaires soient automatiquement déduits des stocks correspondants de mon garde-manger sans risque d'inventaire négatif.

**Why this priority**: C'est le cœur de l'interaction entre le carnet de recettes et l'inventaire ménager. Déduire les ingrédients à la cuisson évite les saisies manuelles fastidieuses et maintient un garde-manger à jour en temps réel (conformément au Principe III de la Constitution).

**Independent Test**:
1. Créer une recette comprenant 250g de pâtes et 3 œufs.
2. Vérifier que le garde-manger contient 500g de pâtes et 6 œufs.
3. Cliquer sur « Cuisiner » / « J'ai cuisiné cette recette » dans l'application.
4. Constater que le garde-manger est automatiquement mis à jour à 250g de pâtes et 3 œufs, avec confirmation visuelle des produits consommés.
5. Cliquer sur « Annuler la cuisson » : vérifier que les stocks initiaux (500g et 6 œufs) sont fidèlement restaurés.

**Acceptance Scenarios**:
1. **Given** une recette avec des ingrédients et un garde-manger contenant des stocks suffisants, **When** l'utilisateur confirme avoir cuisiné la recette, **Then** les quantités respectives sont soustraites du garde-manger et un message de succès récapitule les articles consommés.
2. **Given** une recette nécessitant 300g d'un ingrédient et un stock de seulement 100g dans le garde-manger, **When** l'utilisateur confirme la cuisson, **Then** le stock est décrémenté jusqu'à 0g (interdiction stricte de quantités négatives) et l'ingrédient est signalé comme partiellement manquant dans le récapitulatif.
3. **Given** une cuisson confirmée par erreur, **When** l'utilisateur clique sur « Annuler la cuisine », **Then** les quantités exactement consommées lors de cette session sont réinjectées dans le garde-manger.

---

### User Story 2 - Planification de la recette dans le calendrier avec prévention des chevauchements (Priority: P1)

En tant qu'utilisateur, je souhaite planifier la préparation d'une recette sur un créneau précis de mon calendrier, en calculant sa durée à partir des temps estimés de préparation et de cuisson (`prep_minutes + cook_minutes`), et en garantissant qu'aucun événement ne se chevauche sur mon planning (si j'ai une activité de 17h à 18h, je ne peux pas y planifier ma recette à 17h).

**Why this priority**: Le calendrier AdamHUB applique une règle constitutionnelle stricte de non-chevauchement (Principe IV). Planifier un repas doit tenir compte du temps réel passé en cuisine et respecter les disponibilités réelles de l'utilisateur pour éviter les surréservations d'horaires.

**Independent Test**:
1. Disposer d'un événement au calendrier de 17h00 à 18h00.
2. Ouvrir une recette ayant 15 min de préparation et 30 min de cuisson (durée totale = 45 min).
3. Tenter de planifier cette recette à 17h00 : constater que la planification est bloquée avec une alerte indiquant le conflit avec l'événement existant (« Occupé de 17h00 à 18h00 ») et proposant au moins deux créneaux alternatifs (ex: 18h00–18h45 ou 16h15–17h00).
4. Sélectionner le créneau alternatif à 18h00 : constater la validation immédiate et l'apparition du bloc de cuisine de 18h00 à 18h45 dans le calendrier.

**Acceptance Scenarios**:
1. **Given** une recette avec `prep_minutes = 15` et `cook_minutes = 30`, **When** l'utilisateur ouvre le modal de planification, **Then** la durée par défaut proposée pour le bloc calendrier est de 45 minutes.
2. **Given** un créneau horaire déjà occupé par un événement (tâche, rendez-vous, séance de sport, autre repas), **When** l'utilisateur tente de planifier la recette sur une plage chevauchant cet événement, **Then** le système refuse la création (HTTP 409), signale le conflit précis (titre et horaires de l'événement collisionnant) et présente des créneaux alternatifs non chevauchants.
3. **Given** un créneau libre sélectionné, **When** l'utilisateur valide la planification, **Then** un repas planifié (`MealPlan`) et son bloc calendrier synchronisé (`CalendarItem`) de catégorie `MEAL` sont créés de `start_at` à `start_at + durée`.

---

### User Story 3 - Ajout des ingrédients de la recette à la liste de courses (Priority: P2)

En tant qu'utilisateur, je souhaite ajouter facilement les ingrédients d'une recette à ma liste de courses, avec le choix entre ajouter l'intégralité des ingrédients ou uniquement les ingrédients manquants (déficit par rapport à mon garde-manger actuel).

**Why this priority**: Permet à l'utilisateur de préparer ses approvisionnements sans ressaisir chaque article manuellement et sans acheter en double ce qui est déjà disponible dans ses placards.

**Independent Test**:
1. Créer une recette nécessitant 500g de riz arborio et 200g de parmesan.
2. Avoir 500g de riz arborio dans le garde-manger et 0g de parmesan.
3. Cliquer sur « Ajouter aux courses » :
   - Mode « Ingrédients manquants uniquement » : constater que seul le parmesan (200g) est inséré dans `GroceryItem`.
   - Mode « Tous les ingrédients » : constater que les deux ingrédients sont ajoutés à la liste de courses.

**Acceptance Scenarios**:
1. **Given** une recette consultée sur l'application, **When** l'utilisateur clique sur « Ajouter aux courses », **Then** une boîte de dialogue lui permet de choisir entre « Ingrédients manquants uniquement (recommandé) » et « Tous les ingrédients ».
2. **Given** le choix des ingrédients manquants, **When** le garde-manger contient déjà certains ingrédients en quantité suffisante, **Then** seuls les ingrédients absents ou en quantité insuffisante sont ajoutés à la liste de courses avec la quantité nette manquante.
3. **Given** des articles ajoutés aux courses, **When** l'opération réussit, **Then** une notification toast ou modale informe l'utilisateur du nombre d'articles ajoutés avec un accès direct à la liste de courses.

---

### User Story 4 - Ajustement interactif des portions et des instructions sur mobile (Priority: P2)

En tant qu'utilisateur, je souhaite pouvoir ajuster le nombre de portions d'une recette depuis sa fiche dans l'application mobile pour voir immédiatement les quantités d'ingrédients s'adapter proportionnellement (ex. passer de 2 à 4 portions double automatiquement les quantités requises), et pouvoir modifier les instructions de préparation directement.

**Why this priority**: Permet d'adapter instantanément une recette selon les convives présents sans calcul mental, et d'ajuster les étapes au fur et à mesure de ses habitudes culinaires.

**Independent Test**:
1. Ouvrir une recette calibrée pour 2 portions nécessitant 200g de saumon et 150g de riz.
2. Utiliser le sélecteur incrémental de portions pour passer à 4 portions : vérifier que la liste affiche instantanément 400g de saumon et 300g de riz.
3. Cliquer sur « Cuisiner » : vérifier que les quantités déduites du garde-manger correspondent bien aux 4 portions (400g de saumon et 300g de riz).
4. Modifier les instructions de la recette et enregistrer : vérifier que les modifications sont persistées.

**Acceptance Scenarios**:
1. **Given** une recette avec `servings = 2` et 100g d'un ingrédient, **When** l'utilisateur ajuste les portions à 6, **Then** la quantité affichée pour cet ingrédient s'actualise à 300g (`100 * (6 / 2)`).
2. **Given** des portions ajustées sur la fiche, **When** l'utilisateur confirme la cuisson ou l'ajout aux courses, **Then** les quantités déduites ou transmises aux courses respectent strictement le ratio des portions ajustées.
3. **Given** l'écran de détail de la recette, **When** l'utilisateur édite les instructions textuelles et enregistre, **Then** la recette est mise à jour via l'API et conservée en base.

---

## Edge Cases

- **Recette sans ingrédients renseignés** : Le bouton « Cuisiner » et « Ajouter aux courses » affiche une notification expliquant qu'aucun ingrédient n'est associé à cette recette, sans générer d'erreur serveur.
- **Recette sans temps de préparation ni cuisson (`prep_minutes = 0` et `cook_minutes = 0`)** : La durée par défaut du bloc culinaire dans le calendrier est fixée à 45 minutes, tout en restant modifiable par l'utilisateur dans le sélecteur.
- **Journée saturée lors de la planification** : Si la journée sélectionnée ne dispose d'aucun intervalle libre suffisant pour la durée de la recette, le système propose le premier créneau libre le lendemain matin à partir de 08h00.
- **Incompatibilité ou absence d'unités de mesure** : Si l'ingrédient de la recette a une unité différente du garde-manger (ex: « pièce » vs « g »), la soustraction s'effectue si les unités correspondent, ou signale l'ingrédient comme à vérifier manuellement sans bloquer la confirmation.
- **Suppression d'une recette planifiée** : Si une recette planifiée dans le calendrier est supprimée, les repas planifiés et les blocs calendrier associés sont nettoyés proprement sans laisser d'orphelins.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: L'application (`app-saas` et interface web) DOIT afficher les actions principales « Cuisiner », « Ajouter aux courses » et « Planifier la recette » sur la fiche de détail et sur la liste des recettes.
- **FR-001b**: Sur la liste des recettes, chaque carte DOIT supporter un swipe progressif vers la gauche : un swipe court déclenche immédiatement la confirmation « Cuisiné maintenant » (déstockage direct du garde-manger) ; un swipe long complet ouvre directement le modal de planification calendrier.
- **FR-002**: L'action de confirmation de cuisine DOIT soustraire les quantités des ingrédients de la recette des articles correspondants du garde-manger (`PantryItem`) de l'utilisateur connecté. Si l'utilisateur cuisine une recette sans posséder tous les ingrédients, le système soustrait uniquement les ingrédients réellement disponibles en stock sans bloquer la confirmation.
- **FR-003**: Le système DOIT plafonner les décrémentations du garde-manger à zéro (interdiction stricte de quantités négatives).
- **FR-003b**: En cas d'ingrédients manquants ou en quantité insuffisante lors de « Cuisiné maintenant », l'application DOIT déclencher une animation de secousse (shake visuel + retour haptique), décrémenter le stock disponible, et afficher une action rapide : « Ingrédients manquants détectés. Les ajouter aux courses ? » permettant d'insérer le déficit dans `GroceryItem` en un seul tap.
- **FR-004**: L'utilisateur DOIT pouvoir annuler une confirmation de cuisine récente (« Annuler la cuisson »), ce qui DOIT restituer fidèlement les quantités précédemment soustraites au garde-manger.
- **FR-005**: L'application DOIT permettre de transférer les ingrédients d'une recette vers la liste de courses (`GroceryItem`).
- **FR-005b**: Sur la liste des recettes, chaque carte DOIT supporter un swipe vers la droite ouvrant une feuille modale interactive listant les ingrédients de la recette avec cases à cocher (les ingrédients absents ou en déficit dans le garde-manger étant pré-cochés par défaut).
- **FR-006**: L'utilisateur DOIT pouvoir cocher/décocher manuellement chaque ingrédient dans la feuille d'ajout avant de valider, garantissant qu'aucun ingrédient non souhaité n'est envoyé aux courses.
- **FR-007**: L'application DOIT afficher une action « Planifier la recette » ouvrant un modal de sélection de date et d'heure.
- **FR-008**: La durée de la séance de cuisine DOIT être initialisée automatiquement par la somme `prep_minutes + cook_minutes` de la recette (avec un repli par défaut à 45 minutes si la somme est égale à zéro).
- **FR-009**: Le système DOIT calculer l'horaire de fin de la séance culinaire : `end_at = start_at + durée_minutes`.
- **FR-010**: Le système DOIT vérifier le non-chevauchement du créneau `[start_at, end_at]` avec tous les éléments du calendrier unifié de l'utilisateur (tâches planifiées, rendez-vous, séances de sport, autres repas planifiés).
- **FR-011**: Si un chevauchement est détecté, le système DOIT bloquer la création directe, signaler une erreur de conflit contenant le détail de l'événement en conflit (titre et plage horaire), et fournir au moins deux créneaux alternatifs viables (immédiatement après, avant, ou le lendemain).
- **FR-012**: L'interface mobile et web DOIT afficher clairement le conflit et permettre à l'utilisateur de cliquer sur un créneau suggéré pour l'adopter immédiatement.
- **FR-013**: Le modal de planification DOIT proposer une option (activée par défaut) « Ajouter automatiquement les ingrédients manquants aux courses ».
- **FR-014**: La création du repas planifié DOIT générer ou mettre à jour un `CalendarItem` de catégorie `MEAL` synchronisé avec l'agenda unifié de l'utilisateur.
- **FR-015**: Toutes les interactions DOIVENT être strictement isolées par tenant (`user_id` de l'utilisateur authentifié, Principe I de la Constitution).
- **FR-016**: Toutes les dates et heures transmises et stockées DOIVENT être en UTC (`YYYY-MM-DDTHH:MM:SSZ`, Principe IV de la Constitution).
- **FR-017**: L'écran de détail de la recette (`/recipe/[id]`) DOIT permettre d'ajuster le nombre de portions (`servings`) via un sélecteur interactif incrémental (+/-).
- **FR-018**: La modification des portions DOIT recalculer proportionnellement et dynamiquement les quantités de tous les ingrédients affichés (`quantité_ajustée = quantité_base * (portions_cibles / portions_base)`).
- **FR-019**: Ce calcul proportionnel DOIT s'appliquer aux déductions du garde-manger lors de la confirmation de cuisine et aux quantités envoyées à la liste de courses.
- **FR-020**: L'écran de détail DOIT permettre de modifier directement les instructions textuelles de la recette et de les persister via l'API.
- **FR-021** *(Hors périmètre explicite)* : La taxonomie hiérarchique profonde multi-magasins (catégorisation arborescente des produits drive et mapping universel d'ingrédients) est explicitement exclue de cette spec et reportée à un chantier ultérieur.

---

### Key Entities

- **Recipe**: Représente la fiche culinaire avec nom, description, `prep_minutes`, `cook_minutes`, portions, tags, instructions et étapes.
- **RecipeIngredient**: Représente un ingrédient lié à une recette (nom, quantité, unité, note optionnelle).
- **PantryItem**: Représente un produit en stock dans le garde-manger de l'utilisateur (nom, quantité, unité, catégorie, date de péremption optionnelle).
- **GroceryItem**: Représente un article de la liste de courses de l'utilisateur (nom, quantité, unité, statut coché/non coché).
- **MealPlan**: Représente la planification d'une recette à un moment précis (`planned_at`, `planned_for`, `slot`, `note`, `auto_add_missing_ingredients`).
- **CalendarItem**: Représente l'événement projeté sur la timeline unifiée (`start_at`, `end_at`, source `MEAL_PLAN`, catégorie `MEAL`, titre, description).
- **MealPlanCookConfirmation**: Enregistrement de confirmation d'une session de cuisine avec l'horodatage et la traçabilité des consommations.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: L'utilisateur peut confirmer la cuisine d'une recette depuis sa fiche en moins de 2 clics sur l'application mobile ou web.
- **SC-002**: 100% des ingrédients d'une recette cuisinée sont déduits du garde-manger sans jamais créer de quantité négative (`quantity >= 0`).
- **SC-003**: L'annulation d'une confirmation de cuisine restaure 100% des stocks déduits lors de cette confirmation.
- **SC-004**: 100% des tentatives de planification de recette sur un créneau occupé sont interceptées, évitant tout chevauchement d'agenda.
- **SC-005**: Lors d'un conflit de calendrier, au moins 2 créneaux libres viables sont proposés à l'utilisateur dans l'interface.
- **SC-006**: L'ajout aux courses en mode « Ingrédients manquants » ne génère aucun doublon d'achat pour les ingrédients déjà en stock suffisant dans le garde-manger.
- **SC-007**: L'ajustement du nombre de portions répercute le calcul proportionnel des ingrédients en moins de 100ms sur l'interface mobile sans rechargement réseau complet.
- **SC-008**: La modification des instructions est sauvegardée via l'API avec confirmation visuelle immédiate.

---

## Assumptions

- Les utilisateurs disposent de recettes existantes créées manuellement, importées par vidéo ou enregistrées via l'assistant.
- La durée estimée d'une recette repose sur les champs existants `prep_minutes` et `cook_minutes` du modèle `Recipe`.
- Les unités courantes (g, kg, ml, cl, l, pièce, cuillère) sont comparées avec normalisation de casse et de chaîne ; si les unités divergent (ex. pièce vs gramme), le système ne bloque pas l'action mais alerte l'utilisateur.
- L'infrastructure calendrier utilise le validateur de collision `detect_calendar_conflicts_and_alternatives` et `validate_calendar_slot_free` déjà présent dans `app/services/calendar_hub.py`.
