from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models.entities import (
    GroceryItem,
    MealPlan,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SupermarketConnection,
    UserMemory,
    UserProfile,
)


def build_system_context(session: Session, user_id: int) -> str:
    """Build a comprehensive, compact Markdown system context for the food & grocery assistant."""
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
    for m in memories[:20]:
        memory_lines.append(f"- [{m.category.capitalize()}] {m.fact}")
    memories_str = "\n".join(memory_lines) if memory_lines else "Aucun souvenir spécifique enregistré pour l'instant."

    # 3. Next meal plans
    upcoming_meals = session.exec(
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.planned_at.asc())
        .limit(3)
    ).all()
    meal_lines = [f"- {m.planned_for or m.planned_at.date()} ({m.slot.value if hasattr(m.slot, 'value') else m.slot}): Recette #{m.recipe_id}" for m in upcoming_meals]
    meal_str = "\n".join(meal_lines) if meal_lines else "Aucun repas planifié prochainement."

    # 4. Low pantry stock
    pantry_low = session.exec(
        select(PantryItem)
        .where(PantryItem.user_id == user_id, PantryItem.quantity <= 1)
        .limit(5)
    ).all()
    pantry_lines = [f"- {p.name} (reste: {p.quantity} {p.unit or ''})" for p in pantry_low]
    pantry_str = "\n".join(pantry_lines) if pantry_lines else "Stocks sous contrôle."

    # 5. Pending grocery list items
    grocery_items = session.exec(
        select(GroceryItem)
        .where(GroceryItem.user_id == user_id, GroceryItem.checked == False)  # noqa: E712
        .limit(8)
    ).all()
    grocery_lines = [f"- {g.name} ({g.quantity or 1} {g.unit or ''})" for g in grocery_items]
    grocery_str = "\n".join(grocery_lines) if grocery_lines else "Liste de courses vide."

    # 6. Recent user recipes
    recent_recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.updated_at.desc())
        .limit(4)
    ).all()
    recipe_lines = [f"- {r.name} ({r.servings} portions, prep: {r.prep_minutes}m, cuisson: {r.cook_minutes}m)" for r in recent_recipes]
    recipes_str = "\n".join(recipe_lines) if recipe_lines else "Aucune recette enregistrée pour l'instant."

    # 7. Connected supermarket stores
    active_conns = session.exec(
        select(SupermarketConnection)
        .where(SupermarketConnection.user_id == user_id, SupermarketConnection.is_active == True)  # noqa: E712
    ).all()
    conn_lines = [f"- {c.store.value.capitalize() if hasattr(c.store, 'value') else str(c.store)} ({c.label})" for c in active_conns]
    connections_str = "\n".join(conn_lines) if conn_lines else "Aucun compte drive supermarché connecté pour l'instant."

    # 8. Known ingredients from recipes and pantry
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

    return f"""Tu es AdamHUB Food & Grocery Copilot, l'assistant culinaire, courses et gestion du frigo de l'utilisateur.

## Profil & Préférences durables de l'utilisateur :
- Objectifs physiques / sport : {fitness_str}
- Régime / contraintes alimentaires : {diet_str}
- Style de vie & Personnalité : {lifestyle_str}
- Ton de communication préféré : {tone_str}

## Mémoire continue (Faits retenus au fil du temps) :
{memories_str}

## Situation en temps réel :
- Date & Heure actuelle : {formatted_now}
- Prochains repas planifiés :
{meal_str}
- Articles actuels de la liste de courses :
{grocery_str}
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
2. Tiens compte IMMÉDIATEMENT des contraintes de l'utilisateur (allergies, régimes, préférences) sans qu'il ait besoin de te les rappeler.
3. Si l'utilisateur te demande d'effectuer une action (ajouter des courses, planifier un repas, enregistrer une recette), exécute l'action directement via les outils disponibles.
4. Enchaînement multi-actions : Quand l'utilisateur te demande d'organiser des repas ou une semaine, enchaîne les actions de manière autonome :
   - Pour chaque plat nouveau, crée la recette avec `recipe__add` (avec ingrédients et étapes).
   - Planifie le repas avec `meal_plan__add`.
   - Ajoute tous les ingrédients manquants dans la liste de courses avec `grocery__add_item`.
   - Enfin, présente à l'utilisateur le récapitulatif clair de ce qui a été fait.
5. Distinction sémantique Recette :
   - Toute préparation culinaire, idée de plat ou recette avec ingrédients et étapes DOIT être enregistrée avec `recipe__add` ou modifiée avec `recipe__update`.
   - Pour la suppression d'une recette (`recipe__delete`), demander une confirmation explicite à l'utilisateur avant d'exécuter l'outil.
6. Supermarché & Drive :
   - Utiliser `supermarket__search` pour rechercher de vrais produits en magasin.
   - Ne jamais inventer d'identifiants de produits ou de prix. Utiliser le `cache_id` retourné par la recherche pour ajouter des articles au panier (`supermarket__add_cart_item`).
   - Si un magasin n'est pas connecté ou nécessite une reconnexion, expliquer à l'utilisateur qu'il peut connecter son compte directement depuis l'application mobile.
7. DÉNOMINATION CANONIQUE ET MESURABILITÉ PHYSIQUE :
   - Différencie explicitement les états culinaires incompatibles (ex: "Saumon frais", "Saumon fumé", "Thon en boîte", "Pâtes penne", "Riz basmati").
   - Tout ingrédient pesable ou mesurable (poissons, viandes, pâtes, riz, farine, fromage râpé, liquides) DOIT être exprimé en unités métriques standard (`g`, `kg`, `ml`, `cl`, `l`).
   - L'unité `item` est réservée aux pièces entières (oeuf, avocat, oignon, citron).
8. ANTI-GASPILLAGE, INGRÉDIENTS BRUTS & BUDGET :
   - Privilégie les matières premières brutes à cuisiner soi-même (lentilles corail sèches, riz cru, ail, oignon, viande/poisson cru non pané).
   - Consulte le garde-manger avant d'ajouter des condiments ou épices déjà disponibles.
"""
