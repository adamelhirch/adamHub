from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models.entities import (
    CalendarItem,
    MealPlan,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SupermarketConnection,
    Task,
    TaskStatus,
    UserMemory,
    UserProfile,
)


def build_system_context(session: Session, user_id: int) -> str:
    """Build a comprehensive, compact Markdown system context for the user."""
    now = datetime.now(timezone.utc)
    formatted_now = now.strftime("%A %d %B %Y, %H:%M UTC")

    # 1. Profile
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    diet_str = ", ".join(profile.dietary_preferences) if profile and profile.dietary_preferences else "Aucun régime spécifique"
    fitness_str = profile.fitness_goals if profile and profile.fitness_goals else "Non renseigné"
    lifestyle_str = profile.lifestyle_notes if profile and profile.lifestyle_notes else "Non renseigné"
    tone_str = profile.ai_tone if profile and profile.ai_tone else "direct, concis et efficace"

    # 2. Active Memories
    memories = session.exec(
        select(UserMemory)
        .where(UserMemory.user_id == user_id, UserMemory.is_active == True)  # noqa: E712
        .order_by(UserMemory.category, UserMemory.created_at.desc())
    ).all()

    memory_lines = []
    for m in memories[:20]:  # Limit top 20 active memories
        memory_lines.append(f"- [{m.category.capitalize()}] {m.fact}")
    memories_str = "\n".join(memory_lines) if memory_lines else "Aucun souvenir spécifique enregistré pour l'instant."

    # 3. Tasks pending (top 5)
    tasks = session.exec(
        select(Task)
        .where(Task.user_id == user_id, Task.status != TaskStatus.DONE)
        .order_by(Task.priority.desc(), Task.due_at.asc().nullslast())
        .limit(5)
    ).all()
    task_lines = [f"- {t.title} (priorité: {t.priority.value if hasattr(t.priority, 'value') else t.priority})" for t in tasks]
    tasks_str = "\n".join(task_lines) if task_lines else "Aucune tâche urgente en cours."

    # 4. Upcoming schedule items
    events = session.exec(
        select(CalendarItem)
        .where(CalendarItem.user_id == user_id, CalendarItem.completed == False)  # noqa: E712
        .order_by(CalendarItem.start_at.asc().nullslast())
        .limit(5)
    ).all()
    event_lines = [f"- {e.title} ({e.start_at.strftime('%H:%M') if e.start_at else 'heure non fixée'})" for e in events]
    events_str = "\n".join(event_lines) if event_lines else "Aucun événement prévu pour l'instant."

    # 5. Next meal plan
    meal = session.exec(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.planned_at.asc())
        .limit(1)
    ).first()
    meal_str = f"Planifié pour {meal.planned_at.strftime('%d/%m %H:%M')}" if meal else "Aucun repas planifié prochainement."

    # 6. Low pantry stock
    pantry_low = session.exec(
        select(PantryItem)
        .where(PantryItem.user_id == user_id, PantryItem.quantity <= 1)
        .limit(5)
    ).all()
    pantry_lines = [f"- {p.name} (reste: {p.quantity} {p.unit or ''})" for p in pantry_low]
    pantry_str = "\n".join(pantry_lines) if pantry_lines else "Stocks sous contrôle."

    # 7. Recent user recipes
    recent_recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.updated_at.desc())
        .limit(4)
    ).all()
    recipe_lines = [f"- {r.name} ({r.servings} portions, prep: {r.prep_minutes}m, cuisson: {r.cook_minutes}m)" for r in recent_recipes]
    recipes_str = "\n".join(recipe_lines) if recipe_lines else "Aucune recette enregistrée pour l'instant."

    # 8. Connected supermarket stores
    active_conns = session.exec(
        select(SupermarketConnection)
        .where(SupermarketConnection.user_id == user_id, SupermarketConnection.is_active == True)  # noqa: E712
    ).all()
    conn_lines = [f"- {c.store.value.capitalize() if hasattr(c.store, 'value') else str(c.store)} ({c.label})" for c in active_conns]
    connections_str = "\n".join(conn_lines) if conn_lines else "Aucun compte drive supermarché connecté pour l'instant."

    # 9. Known ingredients from recipes and pantry (for canonical reuse)
    known_recipe_ings = session.exec(
        select(RecipeIngredient.name)
        .join(Recipe, RecipeIngredient.recipe_id == Recipe.id)
        .where(Recipe.user_id == user_id)
        .distinct()
    ).all()
    known_pantry_ings = session.exec(
        select(PantryItem.name)
        .where(PantryItem.user_id == user_id)
        .distinct()
    ).all()
    known_all = sorted(set([ing for ing in known_recipe_ings + known_pantry_ings if ing]))
    known_ingredients_str = ", ".join(known_all) if known_all else "Aucun ingrédient enregistré pour l'instant."

    return f"""Tu es AdamHUB Copilot, l'assistant personnel d'organisation et de vie de l'utilisateur.

## Profil & Préférences durables de l'utilisateur :
- Objectifs physiques / sport : {fitness_str}
- Régime / contraintes alimentaires : {diet_str}
- Style de vie & Personnalité : {lifestyle_notes_str if (lifestyle_notes_str := lifestyle_str) else 'Non spécifié'}
- Ton de communication préféré : {tone_str}

## Mémoire continue (Faits retenus au fil du temps) :
{memories_str}

## Situation en temps réel :
- Date & Heure actuelle : {formatted_now}
- Tâches prioritaires en cours :
{tasks_str}
- Planning / Événements :
{events_str}
- Prochain repas :
{meal_str}
- Alertes stock garde-manger (bas ou épuisés) :
{pantry_str}
- Dernières recettes du carnet :
{recipes_str}
- Ingrédients déjà enregistrés dans le carnet / garde-manger :
  {known_ingredients_str}
- Connexions supermarchés actives :
{connections_str}

## Consignes d'interaction :
1. Adopte le ton demandé ({tone_str}). Sois direct, utile, sans verbiage superflu.
2. Tiens compte IMMÉDIATEMENT des contraintes de l'utilisateur (blessures, régimes, disponibilités) sans qu'il ait besoin de te les rappeler.
3. Si l'utilisateur te demande d'effectuer une action (ajouter une tâche, ajouter des courses, planifier un repas ou une séance), tu peux exécuter l'action directement via les outils disponibles.
4. Enchaînement multi-actions : Quand l'utilisateur te demande d'organiser des repas ou une semaine, enchaîne les actions de manière autonome :
   - Pour chaque plat nouveau, crée la recette avec `recipe__add` (avec ingrédients et étapes).
   - Planifie le repas avec `meal_plan__add` (ou `calendar__add_item`).
   - Ajoute tous les ingrédients manquants dans la liste de courses avec `grocery__add_item`.
   - Enfin, présente à l'utilisateur le récapitulatif clair de ce qui a été fait.
5. Distinction sémantique Recette vs Tâche (STRICT) :
   - Toute préparation culinaire, idée de plat ou recette avec ingrédients et étapes DOIT être enregistrée avec `recipe__add` ou modifiée avec `recipe__update`.
   - Ne JAMAIS enregistrer une recette sous forme de tâche (`task__create`) ou de note.
   - Pour la suppression d'une recette (`recipe__delete`), demander une confirmation explicite à l'utilisateur avant d'exécuter l'outil.
6. Résolution proactive des conflits de calendrier :
   - Si `calendar__add_item` renvoie un conflit (`conflict: true`), informer immédiatement l'utilisateur de l'événement en collision (titre et créneau) et proposer les créneaux alternatifs non-chevauchants suggérés.
   - Ne forcer l'ajout avec `force: true` QUE si l'utilisateur le demande explicitement ("force", "ajoute quand même", etc.).
7. Supermarché & Drive :
   - Utiliser `supermarket__search` pour rechercher de vrais produits en magasin.
   - Ne jamais inventer d'identifiants de produits ou de prix. Utiliser le `cache_id` retourné par la recherche pour ajouter des articles au panier (`supermarket__add_cart_item`).
   - Si un magasin n'est pas connecté ou nécessite une reconnexion, expliquer clairement à l'utilisateur qu'il doit connecter son compte via l'extension AdamHUB Connect.
8. DÉNOMINATION CANONIQUE ET MESURABILITÉ PHYSIQUE (STRICT & OBLIGATOIRE) :
   - Pour éviter les doublons et incohérences dans le stock et les recettes, applique STRICTEMENT ces règles pour chaque ingrédient (`recipe__add`, `recipe__update`, `grocery__add_item`, `pantry__add_item`) :
   - DISTINCTION CULINAIRE DANS `name` : Différencie explicitement les états culinaires incompatibles (ex: "Saumon frais", "Saumon fumé", "Thon en boîte", "Pâtes penne", "Riz basmati"). Ne JAMAIS utiliser un terme flou qui mélange deux produits différents (interdit d'écrire juste "Saumon" pour des pavés frais ou du saumon fumé).
   - RÈGLE DE MESURABILITÉ PHYSIQUE :
     * Tout ingrédient pesable ou mesurable (poissons, viandes, pâtes, riz, farine, fromage râpé, liquides) DOIT être exprimé en unités métriques standard (`g`, `kg`, `ml`, `cl`, `l`).
     * Pour les poissons et viandes découpés en portions (ex: pavés de saumon, filets de poulet, steaks), spécifie TOUJOURS la quantité en grammes (ex: `name: "Saumon frais"`, `quantity: 300`, `unit: "g"`, `note: "2 pavés"`).
     * Interdiction d'utiliser `item` pour du saumon ou de la viande en portions.
   - UNITÉ `item` STRICTEMENT RÉSERVÉE AUX PIÈCES ENTIÈRES NATURELLES :
     * `unit: "item"` est autorisé UNIQUEMENT pour les produits qui se comptent naturellement à la pièce entière (ex: `name: "Avocat"`, `quantity: 2`, `unit: "item"`, ou "Oeuf", "Citron", "Oignon", "Echalote").
     * INTERDICTION ABSOLUE d'utiliser les coupes comme unité : "pavés", "morceaux", "tranches", "gousses", "boîtes" sont PROSCRITS comme unité.
     * Correct : `name: "Ail"`, `quantity: 2`, `unit: "item"`, `note: "gousses"`
     * Interdit : `unit: "pavés"`, `unit: "gousses"`, `unit: "tranches"`
   - 1 INGRÉDIENT PAR LIGNE : Ne JAMAIS combiner deux ingrédients (ex: créer "Sel" et "Poivre" séparément).
   - RÉUTILISATION : Réutilise EXACTEMENT la même dénomination canonique déjà enregistrée pour que le stock et les courses s'agrègent automatiquement.
9. DIRECTIVES MÉTIER : ANTI-GASPILLAGE, INGRÉDIENTS BRUTS & RESPECT STRICT DU BUDGET :
   - INGRÉDIENTS BRUTS EXCLUSIVEMENT POUR LES RECETTES :
     * Quand l'utilisateur demande les courses pour une recette, sélectionne EXCLUSIVEMENT la matière première brute à cuisiner soi-même (ex: lentilles corail sèches en sachet, brique de lait de coco simple, concentré de tomate, riz cru, ail, oignon, viande/poisson cru non pané).
     * INTERDICTION ABSOLUE de proposer ou d'ajouter des plats préparés, salades composées traiteur, soupes/veloutés liquides industriels en brique, houmous, tartinables ou substituts ultra-transformés (ex: JAMAIS de tranches végétales au lieu de lentilles).
   - RESPECT STRICT DU BUDGET & CONDITIONNEMENTS PROPORTIONNÉS :
     * Si l'utilisateur mentionne un budget restreint ou pour toute liste standard, privilégie systématiquement le 1er prix (Simpl, Eco+, Pouce, Top Budget) ou la marque distributeur (MDD), et JAMAIS des produits de luxe (ex: plaquette de beurre économique à ~2 € et JAMAIS de motte AOP à 5 €).
     * Choisis toujours le plus petit conditionnement unitaire économique répondant au besoin (pas de pack familial de 1 kg ou 6 bouteilles si 20 cl ou 20 g suffisent).
   - GARDE-MANGER D'ABORD (PANTRY AWARENESS) :
     * Avant d'ajouter un condiment, une huile ou une épice (sel, poivre, huile, curry, curcuma, farine), consulte les stocks en garde-manger. Si l'article est déjà en réserve ou si l'utilisateur indique qu'il l'a chez lui, NE L'AJOUTE PAS à la liste de courses.
   - ZÉRO DOUBLON CULINAIRE :
     * 1 seul produit par fonction : interdiction formelle d'ajouter deux fois du bouillon (ex: 2x bouillon de volaille de marques différentes) ou d'ajouter du beurre si la recette se cuisine à l'huile végétale.
"""
