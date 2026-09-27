# Feature Specification: Épuration de l'Interface Mobile & Suppression des Blocs de Suggestions

**Feature Branch**: `007-clean-ui-remove-suggestion-blocks`

**Created**: 2026-09-12

**Status**: Ready for Review

**Input**: User description: "Épuration de l'interface mobile : suppression des gros blocs de suggestions polluants. L'interface mobile actuelle (notamment l'écran d'accueil) est encombrée de volumineux blocs de suggestions et de recommandations automatiques qui monopolisent l'espace visuel et nuisent à l'expérience utilisateur ('ils me font chier, donc j'aimerais que tu les dégages'). L'utilisateur souhaite une interface épurée, dense et efficace, centrée immédiatement sur les informations vitales (calendrier, tâches du jour, statut rapide) sans pollution visuelle."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Vue Quotidienne Immédiate et Épurée sur l'Accueil (Priority: P1)

En tant qu'utilisateur ouvrant l'application mobile le matin ou en déplacement, je veux voir immédiatement mon agenda du jour et mes tâches prioritaires dès l'ouverture sans devoir scroller ni contourner un gros bandeau promotionnel ou de suggestion, afin d'accéder instantanément à mes données réelles sans perte de temps ni distraction visuelle.

**Why this priority**: L'écran d'accueil est le point de contact principal de l'utilisateur. Le gros bloc "Assistant Personnel - Que faisons-nous aujourd'hui ?" monopolisait 30% à 40% de la hauteur visible utile sans apporter d'information concrète sur la journée en cours, reléguant les événements et tâches sous la ligne de flottaison. L'assistant disposant déjà d'un point d'accès permanent central dans la barre de navigation, supprimer ce bloc redonne la priorité absolue aux données réelles.

**Independent Test**: Peut être testé en ouvrant l'application mobile et en vérifiant que le premier événement de l'agenda et la première tâche du jour sont visibles immédiatement sur l'écran d'accueil sans effectuer aucun défilement, et qu'aucun bandeau publicitaire, d'assistant ou de suggestion n'apparaît au-dessus d'eux.

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté ayant au moins 1 événement planifié et 1 tâche ouverte, **When** il ouvre ou consulte l'écran d'accueil, **Then** son agenda du jour et ses tâches s'affichent directement sous l'en-tête (date et salutation), sans aucun bloc de suggestion ou bannière d'accroche intermédiaire.
2. **Given** un écran d'accueil épuré, **When** l'utilisateur regarde le haut de l'écran, **Then** il dispose d'une barre de statut compacte (ou indicateurs résumés discrets) résumant le nombre d'événements, le nombre de tâches en attente et les éventuelles alertes critiques en une seule ligne élégante.
3. **Given** un utilisateur souhaitant échanger avec l'assistant personnel, **When** il cherche à le lancer depuis l'accueil, **Then** il utilise le bouton central dédié de la barre de navigation inférieure sans avoir besoin d'un encart redondant dans la page.

---

### User Story 2 - Débarras des Bannières de Recommandation sur les Onglets Métiers (Priority: P1)

En tant qu'utilisateur consultant ses entraînements sportifs ou gérant ses finances personnelles, je veux accéder directement à mes séances programmées, mes statistiques d'entraînement, mon solde mensuel et mes abonnements récurrents sans subir de blocs promotionnels d'optimisation ou de génération automatique ("Coach Sport IA", "Analyse Budget IA"), afin de conserver un flux de lecture direct et sans bruit.

**Why this priority**: Les onglets "Sport" et "Finance" comportaient chacun des cartes colorées de suggestion d'assistant qui s'intercalaient avant ou entre les données critiques de l'utilisateur. Ces blocs créent un encombrement visuel agressif et ralentissent l'accès aux fonctionnalités de suivi quotidien.

**Independent Test**: Peut être testé en accédant successivement à l'onglet "Sport" puis à l'onglet "Finance", et en vérifiant qu'aucune carte d'incitation IA n'apparaît et que les listes de séances, de métriques et d'abonnements occupent l'espace de premier plan.

**Acceptance Scenarios**:

1. **Given** un utilisateur ouvrant l'onglet "Sport", **When** la page est chargée, **Then** les séances à venir et métriques d'entraînement s'affichent immédiatement sous l'en-tête sans la bannière "Coach Sport IA : Générer une séance sur-mesure".
2. **Given** un utilisateur ouvrant l'onglet "Finances", **When** la page est chargée, **Then** la carte de solde net et de répartition revenus/dépenses est immédiatement suivie de la liste des abonnements récurrents et des transactions, sans le bloc intermédiaire "Analyse Budget IA : Optimiser mes dépenses du mois".
3. **Given** un utilisateur dans l'un de ces onglets souhaitant une assistance, **When** il désire une action d'optimisation ou de génération, **Then** il sollicite l'assistant par le bouton central permanent qui dispose de tout le contexte nécessaire.

---

### User Story 3 - Indicateurs Discrets et Pastilles d'Alerte Contextuelles (Priority: P2)

En tant qu'utilisateur gérant ses stocks et son garde-manger, je veux que les informations utiles mais ponctuelles (ex: stock critique épuisé, denrée bientôt périmée) soient présentées sous forme de badges compacts ou de pastilles discrètes plutôt que sous forme de gros bandeaux d'avertissement anxiogènes ou encombrants, afin d'être alerté avec sobriété sans polluer mon écran.

**Why this priority**: Certaines alertes (rupture d'ingrédient de base, stock nul) ont une réelle utilité opérationnelle, mais les matérialiser par des bannières massives produit le même effet de saturation que les blocs publicitaires. L'information doit être signalée de façon compacte et contextuelle (badge, pastille, chiffre coloré discret).

**Independent Test**: Peut être testé en simulant un garde-manger avec 2 articles en rupture ou sous le seuil minimal, en constatant l'apparition d'une pastille compacte dans la barre de résumé de l'accueil et dans l'onglet Cuisine sans aucun bandeau plein format, et en tapant dessus pour naviguer directement à l'inventaire concerné.

**Acceptance Scenarios**:

1. **Given** un inventaire contenant des articles en quantité inférieure ou égale au seuil d'alerte, **When** l'utilisateur consulte l'écran d'accueil, **Then** un indicateur discret ("⚠️ 2 stocks faibles") apparaît au sein de la ligne de statut compacte sans aucun bloc d'alerte déplié.
2. **Given** l'indicateur discret de stock faible affiché sur l'accueil, **When** l'utilisateur clique sur cette pastille, **Then** l'application navigue directement vers la section Garde-manger de l'onglet Cuisine.
3. **Given** aucun article en rupture de stock, **When** l'utilisateur consulte l'accueil ou la cuisine, **Then** aucun indicateur ou message superflus ne s'affiche.
4. **Given** la vue Garde-manger, **When** un article est en rupture, **Then** il arbore un badge inline discret ("Stock faible") à côté de sa quantité, sans encart de conseil générique.

---

### User Story 4 - États Vides Épurés et Suggestions Minimales (Priority: P3)

En tant qu'utilisateur consultant une liste vide (ex: aucun événement ce jour, toutes les tâches accomplies, ou nouvelle conversation d'assistant), je veux des états d'affichage neutres, sobres et compacts sans discours marketing culpabilisant ni cartes de suggestions empilées, afin de maintenir un calme visuel complet.

**Why this priority**: Même lorsque les bannières principales sont retirées, les messages "vides" actuels (ex: "Demande à l'assistant IA...", gros blocs de questions d'exemple dans le chat) réintroduisent de la pollution. Un état vide doit confirmer calmement la complétion ou l'absence d'éléments en une à deux lignes maximum.

**Independent Test**: Peut être testé en ayant 0 événement au calendrier et 0 tâche en cours, en ouvrant l'accueil et en vérifiant que les conteneurs d'état vide occupent une hauteur minimale, sans texte promotionnel pour l'IA ni illustrations surdimensionnées.

**Acceptance Scenarios**:

1. **Given** un calendrier sans événement aujourd'hui, **When** la section Agenda est affichée, **Then** elle présente une mention compacte et sobre (ex: "Aucun événement prévu • Journée libre") sans incitation publicitaire vers l'assistant.
2. **Given** une liste de tâches vide ou totalement complétée, **When** la section Tâches est affichée, **Then** elle confirme la complétion par un message minimal (ex: "Toutes les tâches sont terminées") tout en conservant le champ d'ajout rapide immédiatement utilisable.
3. **Given** l'ouverture de l'écran d'assistant pour une nouvelle session, **When** l'historique ne contient que le message d'accueil, **Then** les 3 gros rectangles de suggestions verticaux sont remplacés soit par de micro-chips horizontales discrètes, soit par un espace vide centré sur le champ de saisie direct.

---

### Edge Cases

- **Densité sur petits écrans (iPhone SE / petits modèles Android)** : En l'absence des gros blocs de suggestions, la totalité de l'en-tête, de la barre de résumé, des événements et des premières tâches doit s'afficher sans troncature sur un écran à hauteur réduite (ex: 667px).
- **Nombre élevé d'événements ou de tâches** : La suppression des bannières libère de l'espace vertical ; si l'utilisateur possède plus de 5 tâches ou événements, le conteneur reste fluide, borné et scrollable sans saccade.
- **Absence totale de données (nouvel utilisateur)** : L'application affiche des indicateurs discrets de bienvenue et d'invitation sobre à ajouter une première tâche, sans jamais générer de bannières intrusives ou d'alertes bloquantes.
- **Perte de réseau ou erreur de chargement** : L'état d'erreur doit être concis (pastille ou bandeau d'erreur discret avec bouton recharger) plutôt qu'un encart envahissant toute la vue.
- **Transition entre états (suppression de la dernière tâche / ajout de premier stock)** : Les indicateurs et pastilles de résumé se mettent à jour instantanément sans saut visuel de layout (layout shift).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: L'écran d'accueil (`HomeScreen`) NE DOIT PAS afficher la bannière "Assistant Personnel" ("Que faisons-nous aujourd'hui ?") ni aucun bloc de suggestion automatique pleine largeur.
- **FR-002**: L'écran d'accueil DOIT afficher immédiatement les informations vitales (date/salutation, agenda du jour, liste des tâches à faire, et barre de statut compacte) dans la moitié supérieure de l'écran (above-the-fold).
- **FR-003**: L'écran d'accueil DOIT intégrer une barre de statut résumée ("Glance Bar") ultra-compacte (hauteur maximale de 40px) présentant sous forme de puces/pastilles discrètes le nombre d'événements du jour, le nombre de tâches en attente et l'indicateur de stock critique éventuel.
- **FR-004**: L'onglet Sport (`FitnessScreen`) NE DOIT PAS afficher la bannière d'incitation "Coach Sport IA" ("Générer une séance sur-mesure").
- **FR-005**: L'onglet Sport DOIT présenter directement en premier conteneur le résumé des séances à venir et les métriques d'entraînement réelles de l'utilisateur.
- **FR-006**: L'onglet Finance (`FinanceScreen`) NE DOIT PAS afficher le bloc de suggestion "Analyse Budget IA" ("Optimiser mes dépenses du mois").
- **FR-007**: L'onglet Finance DOIT enchaîner directement après la carte de solde net sur la liste des abonnements récurrents et les dernières transactions.
- **FR-008**: Les alertes de stock critique (denrées en rupture ou sous le seuil minimal) NE DOIVENT PAS être affichées sous forme de bannières d'avertissement de grande taille ; elles DOIVENT être synthétisées par une pastille discrète et cliquable au niveau de la barre de statut de l'accueil et par un badge inline compact sur l'article dans la liste du garde-manger.
- **FR-009**: Les états vides des conteneurs de l'accueil (aucun événement prévu, aucune tâche) DOIVENT être compacts (hauteur maximale de 80px), neutres et dépourvus de texte promotionnel ou d'invitation publicitaire vers l'assistant IA.
- **FR-010**: Les états vides des sections Recettes et Garde-manger de l'onglet Cuisine DOIVENT être épurés de toute recommandation textuelle redondante.
- **FR-011**: L'écran de conversation avec l'assistant (`AssistantScreen`) NE DOIT PAS encombrer la nouvelle session avec de volumineuses cartes de suggestions verticales empilées ; les éventuelles suggestions d'exemples de requêtes DOIVENT être limitées à de micro-puces horizontales discrètes n'empiétant pas sur l'espace d'affichage de la conversation.
- **FR-012**: L'accès à l'assistant personnel DOIT demeurer exclusivement piloté par le bouton central flottant de la barre de navigation inférieure (`TabsLayout`), garantissant une disponibilité permanente sans pollution des écrans de contenu.

### Key Entities *(include if feature involves data)*

- **HomeGlanceSummary**: Modèle de données transitoire pour la barre d'aperçu rapide de l'accueil, agrégeant :
  - `calendar_count` (entier) : nombre d'événements prévus aujourd'hui.
  - `pending_tasks_count` (entier) : nombre de tâches non complétées.
  - `low_stock_count` (entier) : nombre d'articles en stock critique ou épuisés.
- **StatusAlertIndicator**: Indicateur visuel compact (pastille / badge) avec statut (neutre, information, avertissement), libellé court et action de redirection ciblée.
- **ScreenEmptyState**: Définition standardisée d'un état vide sobre (icône discrète, message synthétique en une ligne, action principale éventuelle).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Réduction de 100% des bannières de suggestions et de promotion IA sur l'écran d'accueil, l'onglet Sport et l'onglet Finance (0 bloc intrusif restant).
- **SC-002**: Accès instantané à l'agenda et aux tâches dès l'ouverture de l'accueil : le premier rendez-vous et la première tâche sont visibles à 100% au-dessus de la ligne de flottaison (sans scroll) sur tous les téléphones de référence (écrans >= 375x667pt).
- **SC-003**: Gain d'espace vertical utile d'au moins 160 pixels sur l'écran d'accueil et d'au moins 100 pixels sur chaque onglet métier (Sport et Finance).
- **SC-004**: Temps nécessaire pour prendre connaissance de son planning et de ses tâches du jour réduit de plus de 50% grâce à la densité d'information accrue et à la suppression des éléments perturbateurs.
- **SC-005**: Zéro régression fonctionnelle : la navigation vers l'assistant, l'ajout de tâches rapides, le pointage des courses et le suivi des abonnements restent immédiatement opérationnels.

## Assumptions

- L'utilisateur dispose déjà d'un accès direct et évident à l'assistant personnel via le bouton central vert de la barre d'onglets (tab bar), rendant tout rappel ou encart promotionnel dans les pages strictement superflu.
- Les suggestions textuelles génériques ("Demande à l'IA de...", "Génère un plan...") ne sont pas perçues comme de la valeur ajoutée par l'utilisateur, mais comme du bruit visuel indésirable.
- Les données vitales définies comme prioritaires par l'utilisateur sont : le calendrier du jour, les tâches du jour à accomplir, le solde financier / abonnements et l'état des stocks / courses.
- Les alertes de stock critique restent nécessaires pour éviter les ruptures imprévues, mais leur rendu visuel doit être proportionné et non invasif (badge compact / pastille).
- La modification concerne le client mobile SaaS (`app-saas`) sans altérer les contrats d'API backend existants.
