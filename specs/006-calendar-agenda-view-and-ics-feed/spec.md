# Feature Specification: Vue calendrier étendue sur l'écran d'accueil & fiabilisation du lien d'abonnement ICS

**Feature Branch**: `006-calendar-agenda-view-and-ics-feed`

**Created**: 2026-09-12

**Status**: Ready for Planning

**Input**: User description: "Vue calendrier étendue sur l'écran d'accueil & fiabilisation du lien d'abonnement ICS. Contexte & Problème : Sur l'écran d'accueil de l'application mobile, l'utilisateur ne voit que les événements d'aujourd'hui sans possibilité de naviguer facilement dans son calendrier ou d'avoir une visibilité sur les jours suivants (semaine, mois). Par ailleurs, le lien d'export et d'abonnement au calendrier ICS vers des clients tiers (Google Calendar, Apple Calendar) doit être fiabilisé et testé. Objectif : 1. Permettre sur l'écran d'accueil de consulter le calendrier au-delà d'aujourd'hui : vue multi-jours / semaine avec navigation intuitive. 2. Spécifier la génération, l'accès et la sécurisation du lien de flux iCalendar (ICS). 3. Définir la gestion des fuseaux horaires, de la fréquence de rafraîchissement et des types d'événements inclus. 4. Définir les user stories (P1, P2, P3), critères d'acceptation et cas limites."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Navigation temporelle & vue multi-jours sur l'écran d'accueil (Priority: P1)

En tant qu'utilisateur de l'application mobile AdamHUB, je souhaite visualiser mes événements au-delà de la seule journée courante et naviguer facilement entre les jours directement depuis l'écran d'accueil (ou via un sélecteur fluide), afin d'anticiper mes journées à venir (repas, séances de sport, tâches planifiées, rendez-vous) sans friction.

**Why this priority**: L'écran d'accueil est le point d'entrée quotidien de l'application mobile. Restreindre la visibilité aux seules 24 heures en cours empêche l'utilisateur d'organiser sa semaine, de vérifier ses repas prévus le lendemain ou de savoir quand sont programmées ses prochaines séances de sport. Offrir cette navigation temporelle constitue la valeur centrale immédiate pour l'expérience mobile.

**Independent Test**: Peut être testé de manière autonome sur l'application mobile en sélectionnant différentes dates dans le ruban de la semaine (ou les jours adjacents) et en vérifiant que les événements affichés s'actualisent instantanément pour la date choisie, avec retour en un tap sur "Aujourd'hui".

**Acceptance Scenarios**:

1. **Given** l'utilisateur se trouve sur l'écran d'accueil, **When** il consulte la section calendrier, **Then** un sélecteur de date (ruban hebdomadaire ou glissière de jours) affiche le jour actuel sélectionné par défaut avec indication visuelle claire du jour courant.
2. **Given** l'utilisateur visualise le jour courant, **When** il sélectionne un jour futur (ex: demain ou après-demain) ou clique sur le bouton "jour suivant", **Then** la liste des événements se met à jour pour afficher les éléments du jour sélectionné (repas, séances de sport, tâches horodatées, événements).
3. **Given** l'utilisateur a navigué vers un jour antérieur ou postérieur, **When** il clique sur le bouton de raccourci "Aujourd'hui", **Then** la vue revient immédiatement sur la date du jour courant.
4. **Given** un jour sélectionné ne comporte aucun événement, **When** la liste se charge, **Then** un état vide convivial et bienveillant est affiché, invitant l'utilisateur à planifier un repas, une séance ou une tâche via l'assistant.
5. **Given** l'utilisateur consulte les événements d'un jour, **When** un événement est affiché, **Then** son type (repas, sport, tâche, événement), son créneau horaire (ou indicateur "Journée") et son statut (ex: tâche terminée, séance effectuée) sont clairement identifiables visuellement.

---

### User Story 2 - Génération, accès et sécurisation du lien d'abonnement ICS (Priority: P1)

En tant qu'utilisateur abonné, je souhaite générer un lien d'abonnement au calendrier iCalendar (ICS / webcal) personnel et sécurisé, le copier en un tap ou m'y abonner directement sur mon appareil mobile, afin que mon calendrier externe (Apple Calendar, Google Calendar, Outlook) se synchronise automatiquement avec mes activités AdamHUB sans devoir ressaisir mes identifiants.

**Why this priority**: La synchronisation externe est essentielle pour que l'utilisateur reçoive ses rappels et voie ses engagements personnels dans son outil de calendrier principal (iPhone, Mac, Google Agenda pro/perso) sans dépendre exclusivement de l'ouverture de l'application mobile.

**Independent Test**: Peut être testé de bout en bout en générant un flux de calendrier depuis l'application ou l'API, en copiant le lien `webcal://` ou `https://`, et en ouvrant ce lien dans Apple Calendar ou Google Calendar pour vérifier l'apparition immédiate des événements sans erreur d'authentification.

**Acceptance Scenarios**:

1. **Given** un utilisateur authentifié dans ses réglages de compte ou sur sa vue calendrier, **When** il accède à la section "Abonnement Calendrier externe", **Then** le système lui présente son lien d'abonnement personnel avec un bouton "Copier le lien" et un bouton "S'abonner" (protocole `webcal://`).
2. **Given** un utilisateur n'ayant pas encore créé de flux de calendrier, **When** il clique sur "Générer mon flux de synchronisation", **Then** un jeton unique, aléatoire et cryptographiquement sûr (non devinable) est généré et associé exclusivement à son compte.
3. **Given** un utilisateur voulant renouveler ou révoquer son accès suite à une fuite de son lien, **When** il clique sur "Régénérer le lien", **Then** l'ancien jeton est immédiatement désactivé (répond 404), un nouveau jeton est produit, et le nouveau lien est affiché.
4. **Given** une requête HTTP entrante sur l'URL publique du flux avec un jeton invalide ou révoqué, **When** le serveur traite la requête, **Then** il répond avec une erreur 404 (Not Found) sans divulguer aucune donnée.
5. **Given** un utilisateur qui s'abonne sur iOS via le protocole `webcal://`, **When** il clique sur le bouton "S'abonner", **Then** l'application Calendar native d'iOS s'ouvre avec la boîte de dialogue de confirmation d'abonnement préremplie.

---

### User Story 3 - Fiabilisation du format RFC 5545, gestion des fuseaux horaires et rafraîchissement (Priority: P2)

En tant qu'utilisateur synchronisant son calendrier avec des clients tiers hétérogènes (Apple Calendar, Google Calendar, Microsoft Outlook), je souhaite que le fichier ICS soit strictement conforme aux standards RFC 5545, respecte les fuseaux horaires, formate adéquatement les événements d'une journée entière et optimise le trafic réseau, afin que les événements s'affichent à la bonne heure sans décalage et sans épuiser la batterie ou la bande passante.

**Why this priority**: Les clients de calendrier tiers sont stricts sur le formatage iCalendar : des lignes trop longues (>75 octets) non repliées ou des événements "toute la journée" mal typés provoquent des rejets silencieux de flux par Google Calendar ou des décalages d'horaires sur Apple Calendar (ex: événement d'une journée affiché à 2h du matin).

**Independent Test**: Peut être testé en soumettant le flux généré à un validateur officiel RFC 5545 (iCalendar Validator) et en simulant des requêtes conditionnelles HTTP (`If-None-Match`) pour vérifier le retour 304 (Not Modified).

**Acceptance Scenarios**:

1. **Given** des événements avec des titres ou des descriptions longs contenant des caractères spéciaux ou des retours à la ligne, **When** le flux ICS est généré, **Then** les lignes respectent le pliage standard (maximum 75 octets par ligne avec espace de continuation) et l'échappement adéquat (`\,`, `\;`, `\n`).
2. **Given** un événement de type "Journée entière" (ex: repas planifié ou tâche sans heure précise), **When** il est exporté dans le flux ICS, **Then** il est encodé avec `VALUE=DATE:YYYYMMDD` pour `DTSTART` et le lendemain pour `DTEND` (fin non inclusive), sans heure UTC, s'affichant en bannière de journée sur tous les clients.
3. **Given** un événement horodaté (ex: séance de sport à 18h30 heure locale), **When** il est exporté, **Then** ses dates sont exprimées en format UTC universel (`Z`), garantissant que le client tiers le transpose fidèlement dans le fuseau horaire de l'appareil.
4. **Given** un client de calendrier effectuant des vérifications périodiques (poll), **When** aucune donnée du calendrier n'a changé depuis la dernière interrogation et que le client envoie l'en-tête `If-None-Match`, **Then** le serveur répond immédiatement par un code HTTP 304 (Not Modified) sans retransmettre le corps du calendrier.
5. **Given** le calendrier exporté, **When** il est interprété par un client compatible (Apple, Outlook), **Then** les métadonnées de rafraîchissement (`REFRESH-INTERVAL;VALUE=DURATION:PT1H` et `X-PUBLISHED-TTL:PT1H`) sont présentes pour encourager une synchronisation toutes les heures.

---

### User Story 4 - Personnalisation des sources et filtres de synchronisation (Priority: P3)

En tant qu'utilisateur ayant des besoins d'organisation ciblés, je souhaite choisir quels types d'événements inclure dans mon flux ICS (repas, entraînements sportifs, tâches, événements personnels) et décider d'inclure ou d'exclure les tâches terminées, afin de ne pas surcharger mon calendrier professionnel ou personnel avec des éléments non pertinents.

**Why this priority**: Permet aux utilisateurs avancés de créer des flux spécialisés (ex: un flux dédié uniquement aux repas pour la famille, ou un flux professionnel n'intégrant que les tâches importantes et rendez-vous).

**Independent Test**: Peut être testé en cochant/décochant des sources (ex: exclure "Repas") dans la configuration du flux et en vérifiant que les événements exclus disparaissent immédiatement du flux ICS exporté.

**Acceptance Scenarios**:

1. **Given** un utilisateur configurant son flux de calendrier, **When** il désélectionne une catégorie (ex: "repas"), **Then** les repas ne sont plus inclus dans le flux ICS généré sous ce jeton.
2. **Given** un flux configuré avec "Inclure les éléments terminés" à faux, **When** l'utilisateur coche une tâche comme terminée dans AdamHUB, **Then** cette tâche n'est plus présente lors de la prochaine génération du flux.

---

### Edge Cases

- **Client tiers sans support de la compression ou avec User-Agent spécifique** : Le flux ICS doit être servi avec `media_type="text/calendar; charset=utf-8"` et sans dépendre d'en-têtes HTTP propriétaires.
- **Utilisateur voyageant entre fuseaux horaires** : Les événements horodatés conservent leur instant absolu UTC ; le client mobile et le calendrier tiers les affichent dans l'heure locale active du terminal.
- **Suppression ou modification d'un événement existant** : L'UID d'un événement reste strictement stable (`adamhub-calendar-item-{id}@adamhub.local`) pour permettre aux clients tiers de mettre à jour ou supprimer l'événement synchronisé sans créer de doublons.
- **Absence totale d'événements sur la période** : Le flux ICS retourne un conteneur VCALENDAR valide et vide (avec en-têtes obligatoires `BEGIN:VCALENDAR`, `VERSION:2.0`, `PRODID:...`, `END:VCALENDAR`) sans générer d'erreur 500 ou de réponse vide.
- **Réseau intermittent ou mode hors-ligne sur mobile** : La vue multi-jours de l'écran d'accueil conserve en cache local les jours récemment chargés et permet la consultation hors-ligne avec mention discrète de dernière synchronisation.
- **Fréquence de requêtes très élevée (DoS / polling agressif)** : Le serveur répond par 304 Not Modified rapidement via calcul d'empreinte ETag (SHA-1), protégeant les ressources du serveur.
- **Période glissante d'export** : L'export ICS couvre une fenêtre temporelle délimitée (ex: 30 jours dans le passé, 365 jours dans le futur) afin de ne pas générer des fichiers de taille excessive pouvant faire planter les clients mobiles.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: L'application mobile (écran d'accueil) DOIT intégrer un composant interactif de navigation de dates permettant de faire défiler les jours de la semaine courante et de sélectionner n'importe quelle date.
- **FR-002**: L'application mobile DOIT actualiser dynamiquement la liste des éléments d'agenda affichés en fonction de la date sélectionnée (sans rechargement complet de l'écran).
- **FR-003**: L'application mobile DOIT proposer un bouton de retour direct vers "Aujourd'hui" lorsque la date sélectionnée diffère de la date actuelle.
- **FR-004**: L'application mobile DOIT afficher un indicateur visuel différencié pour chaque type d'élément du calendrier (repas, séance de fitness, tâche planifiée, événement manuel, habitude).
- **FR-005**: L'application mobile DOIT permettre le rechargement manuel par glissement vers le bas ("pull-to-refresh") sur la vue agenda de la date active.
- **FR-006**: Le système DOIT permettre à tout utilisateur authentifié de générer, consulter et révoquer un ou plusieurs flux de calendrier iCalendar (ICS).
- **FR-007**: Le système DOIT générer un jeton d'accès au flux cryptographiquement aléatoire et imprévisible (au moins 24 octets d'entropie).
- **FR-008**: Le système DOIT exposer une URL publique sécurisée de téléchargement du flux ICS sous la forme `/calendar/feed/{token}.ics`, ainsi qu'une URL de souscription `webcal://`.
- **FR-009**: Le système DOIT restreindre strictement les éléments exposés par un flux aux seules données appartenant au propriétaire du flux (isolation multi-tenant stricte, Principe I de la Constitution).
- **FR-010**: En cas de jeton invalide, désactivé ou inconnu, le système DOIT répondre par un code d'état HTTP 404 (Not Found).
- **FR-011**: Le flux généré DOIT être strictement conforme à la spécification RFC 5545 : encodage UTF-8, fin de ligne CRLF (`\r\n`), repliement des lignes à 75 octets maximum avec espace de continuation, et échappement des caractères réservés.
- **FR-012**: Les événements de journée entière (sans heure spécifique) DOIVENT être exportés avec le type `VALUE=DATE` pour `DTSTART` et `DTEND`, où `DTEND` correspond au lendemain de l'événement (fin non inclusive conforme RFC 5545).
- **FR-013**: Les événements horodatés DOIVENT être exportés avec `DTSTART` et `DTEND` au format UTC universel (`YYYYMMDDTHHMMSSZ`).
- **FR-014**: Le système DOIT inclure dans le flux ICS un UID déterministe et pérenne pour chaque événement, ainsi que les propriétés `DTSTAMP`, `SUMMARY`, `DESCRIPTION`, `CATEGORIES` et `LAST-MODIFIED`.
- **FR-015**: Le système DOIT supporter les requêtes conditionnelles HTTP via l'en-tête `If-None-Match` comparé à l'empreinte ETag du flux, et retourner HTTP 304 sans corps lorsque le contenu est inchangé.
- **FR-016**: Le système DOIT inclure les propriétés de suggestion de fréquence de rafraîchissement (`X-PUBLISHED-TTL:PT1H` et `REFRESH-INTERVAL;VALUE=DURATION:PT1H`) ainsi que l'en-tête HTTP `X-Robots-Tag: noindex`.
- **FR-017**: L'application mobile (vue compte/réglages ou calendrier) DOIT offrir une interface pour copier le lien du flux dans le presse-papiers et ouvrir directement le lien `webcal://` pour déclencher l'abonnement natif.

---

### Key Entities *(include if feature involves data)*

- **CalendarFeed**: Représente une souscription de calendrier externe configurée par un utilisateur.
  - Attributs : identifiant unique (`id`), propriétaire (`user_id`), libellé (`name`), jeton sécurisé (`token`), sources d'événements sélectionnées (`sources`), indicateur d'inclusion des éléments terminés (`include_completed`), indicateur d'activité (`active`), date de dernier accès (`last_accessed_at`), dates de création et mise à jour.
- **CalendarItem**: Représente une entrée d'agenda unifiée (qu'elle soit issue d'un événement propre, d'un repas planifié, d'un entraînement sportif ou d'une tâche).
  - Attributs : identifiant unique (`id`), propriétaire (`user_id`), titre (`title`), description (`description`), date/heure de début en UTC (`start_at`), date/heure de fin en UTC (`end_at`), indicateur journée entière (`all_day`), catégorie métier (`category`), source du module (`source`), statut de complétion (`completed`), date de mise à jour.
- **AgendaDateViewState**: Modèle d'état côté client pour la navigation temporelle.
  - Attributs : date sélectionnée (`selectedDate`), semaine active (`activeWeekStart`), statut de chargement (`isLoading`), statut de rafraîchissement (`isRefreshing`), dictionnaire des éléments par date.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: L'utilisateur accède aux événements de n'importe quel jour de la semaine en cours depuis l'écran d'accueil en moins de 2 interactions tactiles.
- **SC-002**: Le changement de date sur l'écran d'accueil affiche les données du jour sélectionné en moins de 250 millisecondes lorsque les données sont en mémoire cache, et en moins de 1 seconde sur réseau mobile 4G/5G.
- **SC-003**: 100% des fichiers ICS générés sont validés avec succès (0 erreur critique de syntaxe) par les outils d'analyse de conformité RFC 5545 standard.
- **SC-004**: 100% des événements de journée entière s'affichent sous forme de bannières journalières complètes sur Apple Calendar et Google Calendar, sans heure résiduelle (00:00) ni décalage de jour.
- **SC-005**: Plus de 90% des requêtes récurrentes d'interrogation de calendrier provenant des serveurs de synchronisation tiers (Googlebot Calendar, Apple CalendarAgent) sont traitées en HTTP 304 (Not Modified) grâce au cache ETag.
- **SC-006**: La révocation d'un flux de calendrier prend effet immédiatement (délai de 0 seconde côté serveur) : toute requête ultérieure avec l'ancien jeton est rejetée avec un code 404.
- **SC-007**: L'action "S'abonner" sur iPhone ouvre directement l'application Calendrier native avec le flux préconfiguré sans nécessiter de saisie manuelle d'URL par l'utilisateur.

---

## Assumptions

- Les utilisateurs cibles disposent d'un appareil mobile sous iOS ou Android avec accès à une application de calendrier native (Apple Calendrier, Google Agenda ou Outlook) pour l'abonnement externe.
- La fréquence effective de rafraîchissement dépend des moteurs de calendrier tiers (par exemple, Google Agenda actualise les flux distants toutes les 8 à 24 heures de manière asynchrone, tandis qu'Apple Calendar permet un réglage allant de 15 minutes à 1 heure). Les en-têtes et métadonnées configurées indiquent la recommandation optimale (1 heure).
- Tous les horaires et créneaux restent enregistrés et calculés en UTC dans la base de données conformément au Principe IV de la Constitution d'AdamHUB, le fuseau horaire étant appliqué côté client lors de l'affichage ou par le client externe lors de l'importation de l'ICS.
- La portée de l'export est fixée par défaut à 30 jours passés et 365 jours futurs, ce qui couvre l'intégralité des besoins de planification quotidienne sans saturer la mémoire des terminaux.
