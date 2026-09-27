# Feature Specification: Sélection du Magasin Drive et Synchronisation du Panier depuis la Liste de Courses

**Feature Branch**: `004-supermarket-drive-store-selection-cart-sync`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Sélection du magasin Drive (enseigne, TAPE, spot) et génération de panier Drive depuis la liste de courses. Permettre à l'utilisateur de configurer et changer son drive favori (recherche par code postal/ville, choix du point de retrait/spot/TAPE pour Leclerc, Auchan, Carrefour, Intermarché). Spécifier la transformation de la liste de courses en panier drive (matching d'articles, gestion des équivalents/manquants, validation du panier). Déclenchement via interface mobile/web ou via assistant IA."

## Clarifications

### Session 2026-09-13
- Q: À quel moment exact les articles de la liste de courses doivent-ils être transmis vers le panier en ligne du commerçant ? (FR-013, FR-016) → A: Staging local dans AdamHUB d'abord (calcul des correspondances et propositions de substitution prévisualisées dans un job de brouillon local), puis synchronisation par lot vers le panier distant du commerçant uniquement après validation explicite par l'utilisateur lors de l'écran de revue.
- Q: Comment le moteur de correspondance doit-il sélectionner le produit réel en rayon à partir d'un ingrédient générique et de vos contraintes de budget ou de qualité ? (FR-007, FR-009) → A: Profil d'optimisation intelligent (Marque Distributeur / meilleur rapport qualité-prix par défaut + historique des achats validés prioritaire, avec modes commutables "Budget strict / premier prix" ou "Bio / Qualité").
- Q: Quel statut doivent prendre les articles de la liste de courses une fois le panier synchronisé chez le commerçant, et à quel moment le garde-manger doit-il être réapprovisionné ? (FR-021) → A: Dès la synchronisation réussie vers le commerçant, les articles passent en statut "En panier drive" (non cochés). Une action explicite "Confirmer le retrait des courses" (bouton dans l'interface ou commande à l'assistant) permet de cocher en bloc ces articles et de déclencher le réapprovisionnement automatique du garde-manger (GroceryPantrySync).
- Q: Comment l'expérience de génération et de revue du panier drive s'articule-t-elle dans l'application avec l'assistance IA ? (FR-015, FR-016, FR-018) → A: Depuis l'écran Courses, un bouton dédié situé en haut à droite à côté de "Ajouter un article" (ex. "Préparer mon Drive") ouvre un sous-menu modal (similaire au sélecteur de planification de repas) pré-sélectionnant l'enseigne et le magasin favori de l'utilisateur. La génération s'exécute en tâche de fond via le LLM sans rediriger vers l'écran de chat, et affiche la liste des correspondances dans ce même panneau pour revue.
- Q: Comment l'utilisateur doit-il demander à l'IA d'ajuster ou remplacer des produits dans le panneau de revue avant la synchronisation finale ? (FR-016) → A: Gestes de swipe sur les articles de la liste (identique à l'ergonomie des recettes) : swipe dans un sens pour supprimer l'article, swipe dans l'autre sens pour ouvrir le modal de modification (proposant des alternatives directes et un champ texte pour consigne au LLM). L'article est marqué "À modifier", puis un bouton "Mettre à jour le panier" envoie l'ensemble des ajustements groupés au LLM en tâche de fond pour actualiser le panier avant validation finale.


## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recherche et Configuration du Magasin Drive Favori (Priority: P1)

En tant qu'utilisateur faisant régulièrement ses courses en ligne, je veux rechercher et définir mon magasin Drive préféré pour chaque enseigne prise en charge (Leclerc, Auchan, Carrefour, Intermarché), en précisant le point de retrait exact (quai drive classique, spot de livraison, borne automatique TAPE ou drive piéton), afin que tous les prix, les disponibilités réelles de stock et la constitution de mon panier soient fidèlement alignés avec le point de collecte de mon choix.

**Why this priority**: Il s'agit du prérequis indispensable à toute interaction d'achat. Les catalogues, les tarifs et les stocks des grandes surfaces dépendent strictement de l'entrepôt ou du point de retrait sélectionné. Sans choix explicite du drive local, aucune synchronisation de panier fiable ne peut avoir lieu.

**Independent Test**: Peut être testé de manière autonome en recherchant une commune ou un code postal (ex. "31700" ou "Blagnac"), en sélectionnant un point de retrait spécifique parmi les résultats (ex. Leclerc Drive Blagnac ou Auchan Drive Toulouse), en vérifiant la sauvegarde de ce choix sur le profil de l'utilisateur, et en constatant que ce point de retrait reste actif et visible lors des visites ultérieures.

**Acceptance Scenarios**:

1. **Given** un utilisateur connecté sans magasin drive configuré pour une enseigne, **When** l'utilisateur saisit un code postal ou une ville dans la recherche de drive, **Then** le système affiche la liste ordonnée des magasins et points de retrait disponibles à proximité, avec leur adresse, leur distance estimée et les modes de retrait proposés (quai drive, spot drive, TAPE, drive piéton).
2. **Given** une liste de points de retrait affichée pour une enseigne proposant des points relais déportés ou bornes TAPE (comme Leclerc ou Auchan), **When** l'utilisateur sélectionne un spot ou une borne spécifique rattachée au centre de préparation, **Then** le système enregistre cette sélection précise comme drive actif de l'utilisateur pour cette enseigne.
3. **Given** un utilisateur ayant déjà un drive favori configuré, **When** l'utilisateur choisit de modifier son point de retrait, **Then** le nouveau point de retrait remplace l'ancien pour les opérations futures sans altérer l'historique des listes déjà enregistrées.
4. **Given** deux utilisateurs distincts de l'application, **When** le premier utilisateur configure un drive Leclerc à Toulouse et le second un drive Leclerc à Nantes, **Then** chacun dispose strictement de son propre point de retrait sans interférence ni partage de configuration.

---

### User Story 2 - Génération du Panier Drive depuis la Liste de Courses (Priority: P2)

En tant qu'utilisateur ayant complété sa liste de courses hebdomadaire dans AdamHUB, je veux lancer la transformation automatique de ma liste en panier virtuel chez mon commerçant habituel en un seul clic ou une seule demande, afin d'alimenter mon panier drive réel sans avoir à ressaisir manuellement chaque article sur le site du supermarché.

**Why this priority**: C'est le cœur de la valeur ajoutée pour l'utilisateur. La conversion automatique élimine 20 à 30 minutes de recherche fastidieuse d'articles sur les sites de drive à chaque session de courses hebdomadaire.

**Independent Test**: Peut être testé en constituant une liste de 10 articles variés dans l'application, en cliquant sur "Générer mon panier Drive" pour l'enseigne configurée, et en vérifiant que le système génère un aperçu brouillon local avec les correspondances et quantités exactes, prêt pour la revue utilisateur avant l'envoi définitif vers le commerçant.

**Acceptance Scenarios**:

1. **Given** une liste de courses contenant des articles non cochés et un drive actif configuré chez une enseigne connectée, **When** l'utilisateur déclenche la génération du panier drive, **Then** le système recherche chaque article dans le catalogue réel du point de retrait sélectionné, identifie la meilleure correspondance produit ou substitut, calcule le coût global et prépare un panier brouillon local (staging) en attente de revue.
2. **Given** un article de la liste déjà associé à une référence produit précise du commerçant (produit favori ou déjà acheté), **When** la génération est exécutée, **Then** le système utilise en priorité cette référence exacte pour garantir l'identité du produit sans recherche approximative.
3. **Given** un panier chez le commerçant contenant déjà certains articles avant l'opération, **When** la synchronisation finale est exécutée après validation, **Then** le système incrémente la quantité des articles déjà présents sans les écraser et ajoute les nouveaux articles sans supprimer les lignes préexistantes.
4. **Given** la fin du processus de génération du panier local, **When** l'opération de calcul est achevée, **Then** le système présente un récapitulatif détaillé affichant le nombre d'articles appariés, les propositions de substitution, le montant total estimé et l'accès à l'écran de revue avant envoi distant.

---

### User Story 3 - Gestion des Équivalents, Manquants et Validation (Priority: P3)

En tant qu'utilisateur générant son panier drive, je veux que le système me signale clairement les articles indisponibles dans mon magasin, me suggère des produits de substitution pertinents (même catégorie, contenance similaire, gamme de prix comparable) et me permette d'ajuster ou valider les choix avant confirmation, afin de ne subir aucune mauvaise surprise lors de la réception de ma commande.

**Why this priority**: Dans la pratique réelle de la grande distribution, les ruptures de stock locales et les écarts d'appellation sont fréquents. Un traitement intelligent des substitutions transforme un échec partiel en une expérience fluide et maîtrisée par le consommateur.

**Independent Test**: Peut être testé avec une liste de courses contenant un article en rupture avérée au drive local ; vérifier que le système détecte l'indisponibilité, propose un produit équivalent avec justification claire (même marque/volume ou marque distributeur alternative), permet à l'utilisateur de l'accepter ou de le retirer, et isole les articles totalement introuvables sans bloquer le reste du panier.

**Acceptance Scenarios**:

1. **Given** un article de la liste de courses en rupture de stock dans le point de retrait sélectionné, **When** la conversion de panier est calculée, **Then** le système identifie un article alternatif de même nature et conditionnement équivalent, et le signale explicitement comme "substitution suggérée" avec la différence de prix.
2. **Given** un article de la liste trop imprécis ou introuvable dans le catalogue du drive (ex. "épices rares"), **When** la conversion est effectuée, **Then** l'article est classé en "non trouvé / restant à acheter", conservé intact sur la liste de courses AdamHUB, et n'est pas envoyé de façon erronée au commerçant.
3. **Given** l'écran de revue du panier pré-généré, **When** l'utilisateur interagit avec une ligne de produit via les gestes de glissement (swipe identiques à l'ergonomie des recettes), **Then** un swipe dans un sens supprime l'article du panier, tandis qu'un swipe dans l'autre sens ouvre le modal de modification (proposant des alternatives directes ou la saisie d'une consigne textuelle pour l'IA, marquant l'article "À modifier" jusqu'au clic sur "Mettre à jour le panier").
4. **Given** la validation finale de la revue par l'utilisateur, **When** l'utilisateur clique sur "Valider et synchroniser", **Then** les articles confirmés sont définitivement inscrits dans le panier du drive distant, les éléments correspondants de la liste de courses AdamHUB prennent le statut "En panier drive" (non cochés) sans altérer le garde-manger à ce stade, et une action "Confirmer le retrait des courses" devient disponible pour les cocher en bloc et déclencher le réapprovisionnement automatique du garde-manger une fois la commande récupérée.

---

### User Story 4 - Déclenchement et Pilotage par l'Assistant IA (Priority: P4)

En tant qu'utilisateur interagissant vocalement ou textuellement avec mon assistant personnel AdamHUB, je veux pouvoir lui demander en langage naturel de configurer mon drive ("Mets mon drive Leclerc sur celui de Blagnac") ou de préparer mes courses ("Prépare mon panier drive pour cette semaine"), afin d'obtenir un panier prêt sans naviguer manuellement dans les menus de l'application.

**Why this priority**: L'automatisation par agent conversationnel incarne la vision centrale d'AdamHUB comme copilote du quotidien. Elle permet d'enchaîner naturellement planification des repas, inventaire du garde-manger et courses en une simple commande vocale ou textuelle.

**Independent Test**: Peut être testé en formulant à l'assistant la phrase "Prépare mon panier drive chez Leclerc pour mes courses de la semaine", en vérifiant que l'assistant identifie le drive actif, convertit la liste non cochée, traite les correspondances, et répond avec un bilan synthétique (ex. "14 articles ajoutés, 2 équivalents proposés, total estimé à 48,50 €") accompagné du lien d'accès au panier.

**Acceptance Scenarios**:

1. **Given** un utilisateur demandant à l'assistant de configurer son drive (ex. "Règle mon drive Auchan sur le point relais de Balma"), **When** l'assistant traite la demande, **Then** il recherche le point de retrait correspondant, confirme à l'utilisateur le nom exact et l'adresse du magasin retenu, et enregistre la préférence sur son profil.
2. **Given** une liste de courses contenant des ingrédients de repas planifiés, **When** l'utilisateur ordonne à l'assistant "Crée mon panier drive pour cette semaine", **Then** l'assistant lance la transformation sur le drive configuré, préserve le panier en statut brouillon et fournit une synthèse concise des articles ajoutés, des éventuels articles manquants et du coût total estimé.
3. **Given** un utilisateur demandant la création d'un panier alors qu'aucun drive n'est encore configuré pour l'enseigne demandée, **When** l'assistant analyse la commande, **Then** il informe avec bienveillance l'utilisateur qu'aucun magasin n'est configuré et lui demande sa ville ou son code postal pour procéder au choix du point de retrait.
4. **Given** une demande formulée à l'assistant concernant une enseigne dont la session est déconnectée ou expirée, **When** l'assistant tente l'action, **Then** il prévient l'utilisateur que la session commerçant nécessite d'être réactivée via l'extension du navigateur sans corrompre le panier local.

---

### Edge Cases

- **Changement de magasin avec panier non vide** : Lorsque l'utilisateur change de point de retrait actif pour une même enseigne alors qu'un panier contenait déjà des articles, le système avertit l'utilisateur que les stocks et tarifs peuvent différer entre les deux dépôts et propose une réévaluation automatique des articles dans le nouveau magasin.
- **Rupture générale d'un rayon complet** : Si un rayon entier est indisponible au moment de la commande (ex. coupure d'approvisionnement en produits frais), le système regroupe les manquants dans le rapport d'incident sans faire échouer l'ajout des articles des autres rayons.
- **Incompatibilité des unités de mesure** : Si la liste de courses demande "500g de tomates" alors que le drive vend exclusivement des barquettes de 750g ou des filets de 1kg, le système sélectionne le format commercial le plus proche immédiatement supérieur ou égal en affichant l'équivalence retenue.
- **Ambiguïté sur des termes génériques** : Pour un intitulé très général comme "pain" ou "yaourts", si l'utilisateur n'a pas d'historique d'achat préalable, le système privilégie le produit standard de la marque distributeur le plus populaire ou sollicite une précision si plusieurs familles distinctes s'opposent.
- **Point de retrait fermé temporairement ou travaux** : Si l'API ou le service du commerçant indique qu'un spot ou une borne TAPE est momentanément hors service pour travaux ou maintenance, le système indique l'indisponibilité temporaire et suggère le quai drive principal rattaché.
- **Expiration de session au cours d'un ajout par lot** : Si la session du commerçant expire pendant la synchronisation d'une liste de 25 articles, le système interrompt proprement l'envoi, sauvegarde l'état partiel sans perte, et indique à l'utilisateur exactement quels articles ont été ajoutés et lesquels restent en attente après ré-authentification.
- **Conflits de modifications simultanées** : Si l'utilisateur modifie sa liste de courses sur son mobile pendant qu'une génération de panier est en cours depuis l'assistant, chaque action est traitée de manière séquentielle pour garantir l'intégrité des quantités.
- **Isolation stricte des données entre utilisateurs (Multi-tenant)** : Chaque préférence de magasin, historique de matching et panier virtuel est strictement étanche par utilisateur ; aucune fuite d'adresse ou de contenu de panier n'est possible entre comptes différents.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT permettre à l'utilisateur de rechercher des magasins et points de retrait drive pour chacune des quatre enseignes supportées (Leclerc, Auchan, Carrefour, Intermarché) à partir d'un code postal ou d'un nom de commune française.
- **FR-002**: Pour les enseignes disposant de points de collecte multiples ou déportés (Leclerc et Auchan notamment), le système DOIT restituer la typologie précise du point de retrait : quai Drive standard, borne automatique TAPE (Terminal Automatique de Prise d'Effets/Commandes), Spot Drive urbain, ou Drive piéton.
- **FR-003**: Le système DOIT permettre à chaque utilisateur de définir, consulter et modifier son magasin/point de retrait favori pour chaque enseigne, de manière strictement isolée par compte utilisateur.
- **FR-004**: Le système DOIT conserver de manière sécurisée les identifiants techniques et contextuels du point de retrait sélectionné (code magasin, identifiant de point de livraison, canal de retrait, adresse physique, coordonnées géographiques).
- **FR-005**: Le système DOIT utiliser systématiquement le magasin drive actif de l'utilisateur pour effectuer toute recherche d'article, consultation de prix et ajout au panier auprès de l'enseigne concernée.
- **FR-006**: Le système DOIT permettre de déclencher la génération d'un panier drive à partir des articles non cochés de la liste de courses AdamHUB de l'utilisateur.
- **FR-007**: Le système DOIT résoudre les ingrédients génériques de la liste de courses en produits réels du catalogue du drive en appliquant la stratégie d'optimisation configurée pour l'utilisateur (par défaut : Marque Distributeur / meilleur rapport qualité-prix, commutable en "Budget strict / premier prix" ou "Bio / Qualité"), en donnant la priorité absolue aux références de produits précédemment achetées ou validées par l'utilisateur.
- **FR-008**: Le système NE DOIT JAMAIS insérer dans un panier drive des références de produits fictives ou non vérifiées auprès du catalogue réel du commerçant.
- **FR-009**: Lorsque la référence exacte d'un produit habituel est en rupture de stock au point de retrait choisi, le système DOIT rechercher des produits équivalents respectant la même stratégie d'optimisation (même catégorie, contenance comparable, positionnement tarifaire cohérent) et proposer le meilleur substitut avec justification claire et différentiel de prix.
- **FR-010**: Tout produit de substitution proposé par le système DOIT être explicitement identifié comme tel auprès de l'utilisateur, avec affichage du produit initial demandé, de l'alternative retenue et du différentiel de prix.
- **FR-011**: Les articles de la liste de courses pour lesquels aucune correspondance satisfaisante n'est trouvée DOIVENT être catégorisés comme "articles non trouvés", maintenus sur la liste de courses de l'utilisateur et clairement listés dans le rapport de génération.
- **FR-012**: Le système DOIT convertir les quantités exprimées en unités courantes sur la liste de courses (pièces, grammes, litres) en unités d'emballage ou de conditionnement commercial vendues par le drive.
- **FR-013**: Le système DOIT générer les correspondances d'articles sous forme de job brouillon local (staging), puis synchroniser les articles validés vers le panier distant du commerçant lors de la confirmation finale, en préservant le statut du panier distant en mode brouillon avant paiement.
- **FR-014**: Si un produit de la liste est déjà présent dans le panier distant du commerçant, le système DOIT incrémenter la quantité existante de la valeur demandée sans écraser la ligne ni générer de doublon.
- **FR-015**: L'interface utilisateur (web et mobile) DOIT proposer un bouton dédié en haut à droite de l'écran Liste de courses à côté de "Ajouter un article" (ex. "Préparer mon Drive"), ouvrant un sous-menu modal (similaire au sélecteur de planification de repas) permettant de sélectionner l'enseigne et le point de retrait, pré-rempli par défaut avec le magasin favori configuré sur le profil de l'utilisateur.
- **FR-016**: L'interface de revue du panier DOIT intégrer des gestes de glissement (swipe) sur chaque produit (identiques à l'ergonomie des recettes) : un glissement dans une direction supprime l'article du panier, un glissement dans l'autre direction ouvre un modal de modification affichant des alternatives immédiates et un champ de consigne libre pour le LLM. Les articles ajustés sont étiquetés "À modifier", et un bouton "Mettre à jour le panier" transmet toutes les consignes au LLM en tâche de fond pour recalculer l'aperçu avant la validation et synchronisation finale.
- **FR-017**: L'assistant conversationnel (IA) DOIT être capable d'exécuter la recherche et la sélection du magasin drive favori de l'utilisateur à partir d'une consigne en langage naturel (ex. "Configure mon drive Leclerc à Blagnac").
- **FR-018**: L'assistant conversationnel (IA) DOIT être capable de préparer le panier drive en arrière-plan depuis l'interface courses ou via consigne naturelle dans le chat, en restituant un récapitulatif synthétique sans forcer l'utilisateur à quitter son contexte de travail.
- **FR-019**: Si l'utilisateur sollicite la génération d'un panier auprès d'une enseigne pour laquelle aucun point de retrait n'est sélectionné, le système (interface et assistant) DOIT bloquer l'opération et guider l'utilisateur vers le choix préalable de son magasin.
- **FR-020**: Si la session du commerçant est invalide ou absente, le système DOIT notifier l'utilisateur avec un message clair expliquant comment rafraîchir sa connexion via l'extension navigateur officielle.
- **FR-021**: Dès qu'un article de la liste de courses a été transféré avec succès dans le panier drive et validé par l'utilisateur, le système DOIT lui attribuer le statut "En panier drive" (non coché) pour ne pas fausser prématurément les stocks du garde-manger, et DOIT fournir une action explicite "Confirmer le retrait des courses" pour cocher ces articles en bloc et générer les liaisons de réapprovisionnement (`GroceryPantrySync`).
- **FR-022**: Toutes les dates, heures de réservation et horodatages de synchronisation DOIVENT être enregistrés et transmis au format UTC standardisé.
- **FR-023**: Toutes les opérations de consultation de magasin, de génération de panier et de revue DOIVENT respecter un cloisonnement multi-tenant absolu garantissant l'invisibilité des données d'un compte envers les autres utilisateurs.

---

### Key Entities

- **Point de Retrait Drive (Store Drive Location)** : Représente un lieu physique de collecte de courses rattaché à une enseigne (Leclerc, Auchan, Carrefour, Intermarché). Caractérisé par un identifiant distributeur unique, un nom commercial, une adresse complète, une localisation géographique, un type de retrait (quai standard, borne automatique TAPE, spot drive déporté, drive piéton) et les paramètres techniques de routage du commerçant.
- **Préférence Drive Utilisateur (User Store Preference)** : Association durable entre un compte utilisateur et son point de retrait favori pour une enseigne donnée. Conserve également la stratégie d'optimisation par défaut de l'utilisateur ("MDD / Équilibré", "Budget strict / premier prix", ou "Bio / Qualité").
- **Transformation Liste en Panier (Grocery-to-Cart Job)** : Entité représentant une opération de conversion d'une liste de courses en panier commerçant. Conserve la trace de l'horodatage, de l'enseigne cible, du nombre d'articles traités, du coût estimé global et de l'état d'avancement (en cours, revue requise, synchronisé, en échec).
- **Ligne de Correspondance Produit (Matched Cart Item)** : Résultat de l'appariement entre une ligne générique de la liste de courses et un produit authentique du catalogue du drive. Comporte l'identifiant produit de l'enseigne, la désignation exacte, la marque, le prix unitaire, le conditionnement, la quantité calculée, la source du choix (historique validé, optimisation MDD/budget/bio) et le degré de correspondance (exact, favori, ou substitut).
- **Proposition de Substitution (Substitute Proposal)** : Suggestion d'article alternatif formulée en cas d'indisponibilité du produit cible. Contient la référence de substitution, la justification de l'équivalence (catégorie, contenance, marque alternative), la différence de prix et l'état d'approbation par l'utilisateur (en attente, acceptée, refusée).
- **Article Non Trouvé (Unmatched Grocery Item)** : Ligne de la liste de courses n'ayant pu trouver de produit correspondant fiable dans le catalogue du drive sélectionné. Reste maintenue sur la liste de courses originale pour achat ultérieur ou en magasin physique.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% des utilisateurs disposent de la capacité de configurer et modifier un point de retrait spécifique (incluant bornes TAPE et spots de retrait) pour chacune des 4 enseignes supportées en moins de 30 secondes.
- **SC-002**: Le temps nécessaire à la transformation complète d'une liste de courses moyenne (20 articles) en panier drive brouillon chez le commerçant est inférieur à 15 secondes sous conditions réseau nominales.
- **SC-003**: Le taux de correspondance correcte des articles courants de la liste de courses vers le catalogue authentique du drive atteint au moins 90% dès la première génération.
- **SC-004**: 100% des articles en rupture de stock ou indisponibles font l'objet soit d'une proposition de substitution explicite avec écart de prix affiché, soit d'un classement transparent en article non trouvé, avec 0% d'insertion d'article erroné silencieux.
- **SC-005**: 100% des paniers générés par l'assistant IA ou l'interface demeurent en statut "brouillon" jusqu'à validation explicite de l'utilisateur, assurant un contrôle humain complet avant toute transaction financière.
- **SC-006**: L'assistant conversationnel répond avec succès aux requêtes naturelles de configuration de drive et de génération de panier dans 95% des scénarios sans blocage ni régression.
- **SC-007**: 0% de fuite de données ou d'interférence entre utilisateurs : 100% des préférences de magasins et des paniers sont strictement isolés par tenant.
- **SC-008**: En cas de déconnexion ou d'expiration de session chez le commerçant, 100% des utilisateurs reçoivent un message explicite avec la marche à suivre immédiate, sans blocage définitif de l'interface ni altération de la liste de courses.

---

## Assumptions

- L'utilisateur possède un compte client valide auprès de l'enseigne de supermarché visée et a importé au moins une fois ses identifiants ou cookies de session via l'extension de navigateur AdamHUB Connect.
- Les services en ligne des supermarchés (Leclerc, Auchan, Carrefour, Intermarché) sont opérationnels et maintiennent la disponibilité de leurs catalogues locaux et fonctionnalités de panier en ligne.
- Les correspondances de produits reposent sur les données réelles issues des catalogues des enseignes enregistrées dans le cache de recherche et ne recourent à aucune donnée fictive ou inventée.
- La validation finale de la commande, le choix du créneau horaire précis de retrait au drive et le paiement sécurisé par carte bancaire restent effectués par l'utilisateur directement sur le site ou l'application officielle du commerçant pour des motifs de sécurité bancaire et de conformité légale.
- Le modèle de données sous-jacent prend en charge l'isolation stricte par utilisateur pour l'ensemble des entités relatives aux magasins favoris, aux correspondances et aux paniers.
