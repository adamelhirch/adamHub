import { useEffect, useState } from 'react';
import { CalendarClock, ChefHat, CheckCircle2, Clock, ExternalLink, Link2, Loader2, Plus, Search, Store, Trash2, Unlink, X } from 'lucide-react';
import api from '../lib/api';
import ComposerSheet from '../components/ComposerSheet';

type RecipeIngredient = {
  id: number;
  recipe_id: number;
  name: string;
  quantity: number;
  unit: string;
  note: string | null;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
};

type Recipe = {
  id: number;
  name: string;
  description: string | null;
  instructions: string;
  steps: string[];
  utensils: string[];
  prep_minutes: number;
  cook_minutes: number;
  servings: number;
  tags: string[];
  source_url: string | null;
  source_platform: string | null;
  source_title: string | null;
  source_description: string | null;
  source_transcript: string | null;
  ingredients: RecipeIngredient[];
  created_at: string;
  updated_at: string;
};

type SupermarketSearchResult = {
  cache_id: number;
  store: string;
  external_id: string | null;
  name: string;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  image_url: string | null;
  product_url: string | null;
};

type SupermarketMapping = {
  id: number;
  target_type: 'recipe_ingredient';
  target_id: number;
  store: string;
  external_id: string;
  store_label: string;
  name_snapshot: string;
  category_snapshot: string | null;
  packaging_snapshot: string | null;
  price_snapshot: string | null;
  product_url: string | null;
  image_url: string | null;
  active: boolean;
};

type MissingIngredient = {
  name: string;
  needed_quantity: number;
  available_quantity: number;
  missing_quantity: number;
  unit: string;
};

type MealPlan = {
  id: number;
  planned_at: string;
  planned_for: string | null;
  slot: 'breakfast' | 'lunch' | 'dinner' | null;
  recipe_id: number;
  recipe_name: string;
  servings_override: number | null;
  note: string | null;
  auto_add_missing_ingredients: boolean;
  synced_grocery_at: string | null;
  cooked: boolean;
  cooked_at: string | null;
  cooked_note: string | null;
  missing_ingredients: MissingIngredient[];
  created_at: string;
  updated_at: string;
};

function hasResolvedCategories(results: SupermarketSearchResult[]): boolean {
  return results.some((result) => Boolean(result.category?.trim()));
}

type RecipeFormState = {
  name: string;
  description: string;
  prep_minutes: string;
  cook_minutes: string;
  servings: string;
  tags: string;
  source_url: string;
  source_platform: string;
  source_title: string;
  source_description: string;
};

type MealPlanFormState = {
  recipe_id: string;
  planned_at: string;
  servings_override: string;
  note: string;
  auto_add_missing_ingredients: boolean;
};

const EMPTY_RECIPE_FORM: RecipeFormState = {
  name: '',
  description: '',
  prep_minutes: '',
  cook_minutes: '',
  servings: '1',
  tags: '',
  source_url: '',
  source_platform: '',
  source_title: '',
  source_description: '',
};

const EMPTY_MEAL_PLAN_FORM: MealPlanFormState = {
  recipe_id: '',
  planned_at: '',
  servings_override: '',
  note: '',
  auto_add_missing_ingredients: true,
};

function parseLines(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

type RecipeTextDraft = {
  id: string;
  value: string;
};

function createTextDraft(value = ''): RecipeTextDraft {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    value,
  };
}

function valuesToTextDrafts(values: string[]): RecipeTextDraft[] {
  return values.length > 0 ? values.map((value) => createTextDraft(value)) : [createTextDraft()];
}

function toDateTimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function fromDateTimeLocalValue(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function formatMealPlanDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

function recipeToForm(recipe: Recipe): RecipeFormState {
  return {
    name: recipe.name,
    description: recipe.description || '',
    prep_minutes: String(recipe.prep_minutes ?? ''),
    cook_minutes: String(recipe.cook_minutes ?? ''),
    servings: String(recipe.servings ?? 1),
    tags: recipe.tags.join(', '),
    source_url: recipe.source_url || '',
    source_platform: recipe.source_platform || '',
    source_title: recipe.source_title || '',
    source_description: recipe.source_description || '',
  };
}

function recipeToIngredientDrafts(recipe: Recipe): RecipeIngredientDraft[] {
  if (!recipe.ingredients.length) return [createIngredientDraft()];
  return recipe.ingredients.map((ingredient) => createIngredientDraft({
    id: `${recipe.id}-${ingredient.id}`,
    name: ingredient.name,
    quantity: String(ingredient.quantity ?? 1),
    unit: ingredient.unit || 'item',
    note: ingredient.note || '',
    store: ingredient.store,
    store_label: ingredient.store_label,
    external_id: ingredient.external_id,
    category: ingredient.category,
    packaging: ingredient.packaging,
    price_text: ingredient.price_text,
    product_url: ingredient.product_url,
    image_url: ingredient.image_url,
  }));
}

type RecipeIngredientDraft = {
  id: string;
  name: string;
  quantity: string;
  unit: string;
  note: string;
  store: string | null;
  store_label: string | null;
  external_id: string | null;
  category: string | null;
  packaging: string | null;
  price_text: string | null;
  product_url: string | null;
  image_url: string | null;
};

function createIngredientDraft(overrides: Partial<RecipeIngredientDraft> = {}): RecipeIngredientDraft {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name: '',
    quantity: '1',
    unit: 'item',
    note: '',
    store: null,
    store_label: null,
    external_id: null,
    category: null,
    packaging: null,
    price_text: null,
    product_url: null,
    image_url: null,
    ...overrides,
  };
}

function buildIngredientPayload(draft: RecipeIngredientDraft) {
  const name = draft.name.trim();
  const quantity = Number(draft.quantity);
  return {
    name,
    quantity: Number.isFinite(quantity) && quantity > 0 ? quantity : 1,
    unit: draft.unit.trim() || 'item',
    note: draft.note.trim() || null,
    store: draft.store,
    store_label: draft.store_label,
    external_id: draft.external_id,
    category: draft.category,
    packaging: draft.packaging,
    price_text: draft.price_text,
    product_url: draft.product_url,
    image_url: draft.image_url,
  };
}

export default function RecipesPage() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [mealPlans, setMealPlans] = useState<MealPlan[]>([]);
  const [mealPlansLoading, setMealPlansLoading] = useState(true);
  const [recipeForm, setRecipeForm] = useState<RecipeFormState>(EMPTY_RECIPE_FORM);
  const [stepDrafts, setStepDrafts] = useState<RecipeTextDraft[]>([createTextDraft()]);
  const [utensilDrafts, setUtensilDrafts] = useState<RecipeTextDraft[]>([createTextDraft()]);
  const [ingredientDrafts, setIngredientDrafts] = useState<RecipeIngredientDraft[]>([createIngredientDraft()]);
  const [editingRecipeId, setEditingRecipeId] = useState<number | null>(null);
  const [mealPlanForm, setMealPlanForm] = useState<MealPlanFormState>(EMPTY_MEAL_PLAN_FORM);
  const [editingMealPlanId, setEditingMealPlanId] = useState<number | null>(null);
  const [showRecipeComposer, setShowRecipeComposer] = useState(false);
  const [showMealPlanComposer, setShowMealPlanComposer] = useState(false);
  const [recipeSaving, setRecipeSaving] = useState(false);
  const [mealPlanSaving, setMealPlanSaving] = useState(false);
  const [recipeDeletingId, setRecipeDeletingId] = useState<number | null>(null);
  const [mealPlanActionId, setMealPlanActionId] = useState<number | null>(null);
  const [recipeCookingId, setRecipeCookingId] = useState<number | null>(null);
  const [recipeFeedback, setRecipeFeedback] = useState<string | null>(null);
  const [recipeError, setRecipeError] = useState<string | null>(null);
  const [activeIngredient, setActiveIngredient] = useState<RecipeIngredient | null>(null);
  const [activeDraftIndex, setActiveDraftIndex] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SupermarketSearchResult[]>([]);
  const [mapping, setMapping] = useState<SupermarketMapping | null>(null);
  const [searchQueryHasCache, setSearchQueryHasCache] = useState(false);
  const [searchPromotionsOnly, setSearchPromotionsOnly] = useState(false);

  const loadRecipes = async () => {
    setLoading(true);
    try {
      const res = await api.get('/recipes');
      setRecipes(res.data);
    } finally {
      setLoading(false);
    }
  };

  const loadMealPlans = async () => {
    setMealPlansLoading(true);
    try {
      const res = await api.get('/meal-plans', { params: { limit: 100 } });
      setMealPlans(res.data);
    } finally {
      setMealPlansLoading(false);
    }
  };

  useEffect(() => {
    void loadRecipes();
    void loadMealPlans();
  }, []);

  const resetIngredientSelection = () => {
    setActiveIngredient(null);
    setActiveDraftIndex(null);
    setSearchQuery('');
    setSearchResults([]);
    setMapping(null);
  };

  const resetRecipeEditor = () => {
    setEditingRecipeId(null);
    setRecipeForm(EMPTY_RECIPE_FORM);
    setStepDrafts([createTextDraft()]);
    setUtensilDrafts([createTextDraft()]);
    setIngredientDrafts([createIngredientDraft()]);
    resetIngredientSelection();
    setShowRecipeComposer(false);
  };

  const resetMealPlanEditor = () => {
    setEditingMealPlanId(null);
    setMealPlanForm(EMPTY_MEAL_PLAN_FORM);
    setShowMealPlanComposer(false);
  };

  const openRecipeComposer = () => {
    setRecipeError(null);
    setRecipeFeedback(null);
    setEditingRecipeId(null);
    setRecipeForm(EMPTY_RECIPE_FORM);
    setStepDrafts([createTextDraft()]);
    setUtensilDrafts([createTextDraft()]);
    setIngredientDrafts([createIngredientDraft()]);
    resetIngredientSelection();
    setShowRecipeComposer(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startEditRecipe = (recipe: Recipe) => {
    setRecipeError(null);
    setRecipeFeedback(null);
    setEditingRecipeId(recipe.id);
    setShowRecipeComposer(true);
    setRecipeForm(recipeToForm(recipe));
    setStepDrafts(valuesToTextDrafts(recipe.steps));
    setUtensilDrafts(valuesToTextDrafts(recipe.utensils));
    setIngredientDrafts(recipeToIngredientDrafts(recipe));
    resetIngredientSelection();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startCreateMealPlan = (recipe?: Recipe) => {
    setRecipeError(null);
    setRecipeFeedback(null);
    setEditingMealPlanId(null);
    setShowMealPlanComposer(true);
    setMealPlanForm({
      ...EMPTY_MEAL_PLAN_FORM,
      recipe_id: recipe ? String(recipe.id) : '',
      planned_at: toDateTimeLocalValue(new Date(Date.now() + 60 * 60 * 1000).toISOString()),
      servings_override: recipe ? String(recipe.servings || 1) : '',
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const startEditMealPlan = (plan: MealPlan) => {
    setRecipeError(null);
    setRecipeFeedback(null);
    setEditingMealPlanId(plan.id);
    setShowMealPlanComposer(true);
    setMealPlanForm({
      recipe_id: String(plan.recipe_id),
      planned_at: toDateTimeLocalValue(plan.planned_at),
      servings_override: plan.servings_override ? String(plan.servings_override) : '',
      note: plan.note || '',
      auto_add_missing_ingredients: plan.auto_add_missing_ingredients,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  useEffect(() => {
    const value = searchQuery.trim();
    if (!value) {
      setSearchQueryHasCache(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void api.get('/supermarket/search', {
        params: {
          store: 'intermarche',
          query: value,
          limit: 1,
        },
      })
        .then((res) => setSearchQueryHasCache(Array.isArray(res.data) && res.data.length > 0))
        .catch(() => setSearchQueryHasCache(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const openIngredientPanel = async (ingredient: RecipeIngredient) => {
    setActiveDraftIndex(null);
    setActiveIngredient(ingredient);
    setSearchQuery(ingredient.name);
    setSearchResults([]);
    const res = await api.get(`/supermarket/mappings/recipe-ingredients/${ingredient.id}`);
    setMapping(res.data);
  };

  const openDraftIngredientPanel = (index: number) => {
    setActiveIngredient(null);
    setActiveDraftIndex(index);
    setSearchQuery(ingredientDrafts[index]?.name || '');
    setSearchResults([]);
    setMapping(null);
  };

  const updateDraftIngredient = (index: number, patch: Partial<RecipeIngredientDraft>) => {
    setIngredientDrafts((current) => current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, ...patch } : draft)));
  };

  const addDraftIngredient = () => {
    setIngredientDrafts((current) => [...current, createIngredientDraft()]);
    setRecipeFeedback(null);
  };

  const removeDraftIngredient = (index: number) => {
    setIngredientDrafts((current) => {
      const next = current.filter((_, draftIndex) => draftIndex !== index);
      return next.length > 0 ? next : [createIngredientDraft()];
    });
    if (activeDraftIndex === index) {
      resetIngredientSelection();
    } else if (activeDraftIndex !== null && activeDraftIndex > index) {
      setActiveDraftIndex(activeDraftIndex - 1);
    }
  };

  const updateStepDraft = (index: number, value: string) => {
    setStepDrafts((current) => current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, value } : draft)));
  };

  const addStepDraft = () => {
    setStepDrafts((current) => [...current, createTextDraft()]);
    setRecipeFeedback(null);
  };

  const removeStepDraft = (index: number) => {
    setStepDrafts((current) => {
      const next = current.filter((_, draftIndex) => draftIndex !== index);
      return next.length > 0 ? next : [createTextDraft()];
    });
  };

  const updateUtensilDraft = (index: number, value: string) => {
    setUtensilDrafts((current) => current.map((draft, draftIndex) => (draftIndex === index ? { ...draft, value } : draft)));
  };

  const addUtensilDraft = () => {
    setUtensilDrafts((current) => [...current, createTextDraft()]);
    setRecipeFeedback(null);
  };

  const removeUtensilDraft = (index: number) => {
    setUtensilDrafts((current) => {
      const next = current.filter((_, draftIndex) => draftIndex !== index);
      return next.length > 0 ? next : [createTextDraft()];
    });
  };

  const runSearch = async (forceRefresh = false) => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      if (!forceRefresh && !searchPromotionsOnly) {
        const cached = await api.get('/supermarket/search', {
          params: {
            store: 'intermarche',
            query: searchQuery.trim(),
            limit: 30,
          },
        });
        if (Array.isArray(cached.data) && cached.data.length >= 30 && hasResolvedCategories(cached.data)) {
          setSearchResults(cached.data);
          return;
        }
      }

      const res = await api.post('/supermarket/search', {
        store: 'intermarche',
        queries: [searchQuery.trim()],
        max_results: 30,
        promotions_only: searchPromotionsOnly,
      }, { timeout: 120_000 });
      setSearchResults(res.data);
    } finally {
      setSearchLoading(false);
    }
  };

  const linkIngredient = async (result: SupermarketSearchResult) => {
    if (activeIngredient) {
      const res = await api.put(`/supermarket/mappings/recipe-ingredients/${activeIngredient.id}`, {
        cache_id: result.cache_id,
        store: result.store,
        external_id: result.external_id,
        store_label: result.store === 'intermarche' ? 'Intermarché' : result.store,
        name_snapshot: result.name,
        category_snapshot: result.category,
        packaging_snapshot: result.packaging,
        price_snapshot: result.price_text,
        product_url: result.product_url,
        image_url: result.image_url,
      });
      setMapping(res.data);
      return;
    }

    if (activeDraftIndex === null) return;
    updateDraftIngredient(activeDraftIndex, {
      name: result.name,
      store: result.store,
      store_label: result.store === 'intermarche' ? 'Intermarché' : result.store,
      external_id: result.external_id,
      category: result.category,
      packaging: result.packaging,
      price_text: result.price_text,
      product_url: result.product_url,
      image_url: result.image_url,
    });
    setRecipeFeedback('Produit magasin lié à l’ingrédient du brouillon.');
  };

  const unlinkIngredient = async () => {
    if (!mapping) return;
    await api.delete(`/supermarket/mappings/${mapping.id}`);
    setMapping(null);
  };

  const confirmRecipeCooked = async (recipe: Recipe) => {
    setRecipeCookingId(recipe.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      const res = await api.post(`/recipes/${recipe.id}/confirm-cooked`, {});
      const payload = res.data as {
        recipe_name: string;
        missing_ingredients: Array<{ name: string; missing_quantity: number }>;
        pantry_consumption: Array<{ name: string; consumed_quantity: number }>;
      };
      const consumedCount = payload.pantry_consumption.reduce((sum, item) => sum + (item.consumed_quantity > 0 ? 1 : 0), 0);
      const missingCount = payload.missing_ingredients.filter((item) => item.missing_quantity > 0).length;
      setRecipeFeedback(
        `${payload.recipe_name} cuisinée. ${consumedCount} ingrédient(s) consommé(s)${missingCount ? `, ${missingCount} manquant(s)` : ''}.`,
      );
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible de consommer la recette.');
    } finally {
      setRecipeCookingId(null);
    }
  };

  const saveRecipe = async () => {
    setRecipeError(null);
    setRecipeFeedback(null);

    const name = recipeForm.name.trim();
    if (!name) {
      setRecipeError('Le nom de la recette est obligatoire.');
      return;
    }

    const instructions = stepDrafts
      .map((draft) => draft.value.trim())
      .filter(Boolean)
      .join('\n');

    const payload = {
      name,
      description: recipeForm.description.trim() || null,
      instructions: instructions || recipeForm.name.trim(),
      steps: stepDrafts.map((draft) => draft.value.trim()).filter(Boolean),
      utensils: utensilDrafts.map((draft) => draft.value.trim()).filter(Boolean),
      prep_minutes: recipeForm.prep_minutes ? Number(recipeForm.prep_minutes) : 0,
      cook_minutes: recipeForm.cook_minutes ? Number(recipeForm.cook_minutes) : 0,
      servings: recipeForm.servings ? Number(recipeForm.servings) : 1,
      tags: parseLines(recipeForm.tags.replaceAll(',', '\n')),
      source_url: recipeForm.source_url.trim() || null,
      source_platform: recipeForm.source_platform.trim() || null,
      source_title: recipeForm.source_title.trim() || null,
      source_description: recipeForm.source_description.trim() || null,
      ingredients: ingredientDrafts
        .map(buildIngredientPayload)
        .filter((ingredient) => ingredient.name),
    };

    setRecipeSaving(true);
    try {
      if (editingRecipeId !== null) {
        await api.patch(`/recipes/${editingRecipeId}`, payload);
        setRecipeFeedback('Recette modifiée.');
      } else {
        await api.post('/recipes', payload);
        setRecipeFeedback('Recette créée.');
      }
      resetRecipeEditor();
      await loadRecipes();
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible d’enregistrer la recette.');
    } finally {
      setRecipeSaving(false);
    }
  };

  const deleteRecipe = async (recipe: Recipe) => {
    const ok = window.confirm(`Supprimer la recette "${recipe.name}" ?`);
    if (!ok) return;

    setRecipeDeletingId(recipe.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      await api.delete(`/recipes/${recipe.id}`);
      if (editingRecipeId === recipe.id) {
        resetRecipeEditor();
      }
      await loadRecipes();
      setRecipeFeedback('Recette supprimée.');
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible de supprimer la recette.');
    } finally {
      setRecipeDeletingId(null);
    }
  };

  const saveMealPlan = async () => {
    setRecipeError(null);
    setRecipeFeedback(null);

    const recipeId = Number(mealPlanForm.recipe_id);
    if (!Number.isFinite(recipeId) || recipeId <= 0) {
      setRecipeError('Choisis une recette pour la planification.');
      return;
    }

    const plannedAt = fromDateTimeLocalValue(mealPlanForm.planned_at);
    if (!plannedAt) {
      setRecipeError('La date de planification est obligatoire.');
      return;
    }

    const payload = {
      recipe_id: recipeId,
      planned_at: plannedAt,
      servings_override: mealPlanForm.servings_override ? Number(mealPlanForm.servings_override) : null,
      note: mealPlanForm.note.trim() || null,
      auto_add_missing_ingredients: mealPlanForm.auto_add_missing_ingredients,
    };

    setMealPlanSaving(true);
    try {
      if (editingMealPlanId !== null) {
        await api.patch(`/meal-plans/${editingMealPlanId}`, payload);
        setRecipeFeedback('Planification modifiée.');
      } else {
        await api.post('/meal-plans', payload);
        setRecipeFeedback('Planification créée.');
      }
      resetMealPlanEditor();
      await Promise.all([loadMealPlans(), loadRecipes()]);
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible d’enregistrer la planification.');
    } finally {
      setMealPlanSaving(false);
    }
  };

  const syncMealPlanGroceries = async (mealPlan: MealPlan) => {
    setMealPlanActionId(mealPlan.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      const res = await api.post(`/meal-plans/${mealPlan.id}/sync-groceries`);
      const created = res.data?.created_grocery_items ?? 0;
      setRecipeFeedback(`${mealPlan.recipe_name}: ${created} article(s) ajouté(s) aux courses.`);
      await loadMealPlans();
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible de synchroniser les courses.');
    } finally {
      setMealPlanActionId(null);
    }
  };

  const confirmMealPlanCooked = async (mealPlan: MealPlan) => {
    setMealPlanActionId(mealPlan.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      const res = await api.post(`/meal-plans/${mealPlan.id}/confirm-cooked`, {});
      const payload = res.data as { pantry_consumption: Array<{ consumed_quantity: number }> };
      const consumedCount = payload.pantry_consumption.reduce((sum, row) => sum + (row.consumed_quantity > 0 ? 1 : 0), 0);
      setRecipeFeedback(`${mealPlan.recipe_name}: cuisiné. ${consumedCount} ingrédient(s) consommé(s).`);
      await loadMealPlans();
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible de confirmer la cuisson.');
    } finally {
      setMealPlanActionId(null);
    }
  };

  const unconfirmMealPlanCooked = async (mealPlan: MealPlan) => {
    setMealPlanActionId(mealPlan.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      const res = await api.post(`/meal-plans/${mealPlan.id}/unconfirm-cooked`);
      const payload = res.data as { pantry_restore: Array<{ restored_quantity: number }> };
      const restoredCount = payload.pantry_restore.reduce((sum, row) => sum + (row.restored_quantity > 0 ? 1 : 0), 0);
      setRecipeFeedback(`${mealPlan.recipe_name}: confirmation annulée. ${restoredCount} ingrédient(s) restauré(s).`);
      await loadMealPlans();
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible d’annuler la cuisson.');
    } finally {
      setMealPlanActionId(null);
    }
  };

  const deleteMealPlan = async (mealPlan: MealPlan) => {
    const ok = window.confirm(`Supprimer la planification "${mealPlan.recipe_name}" ?`);
    if (!ok) return;

    setMealPlanActionId(mealPlan.id);
    setRecipeError(null);
    setRecipeFeedback(null);
    try {
      await api.delete(`/meal-plans/${mealPlan.id}`);
      if (editingMealPlanId === mealPlan.id) {
        resetMealPlanEditor();
      }
      setRecipeFeedback('Planification supprimée.');
      await loadMealPlans();
    } catch (error) {
      setRecipeError(error instanceof Error ? error.message : 'Impossible de supprimer la planification.');
    } finally {
      setMealPlanActionId(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-transparent overflow-y-auto pb-[calc(env(safe-area-inset-bottom)+5.75rem)]">
      <div className="sticky top-0 z-10 border-b border-white/60 bg-white/75 px-4 py-4 shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-xl md:px-8 md:py-5">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">Cuisine</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">Recipes</h1>
            <p className="mt-1 text-sm text-apple-gray-500">Créer des recettes à la main, puis lier les ingrédients à un produit magasin ou les laisser personnalisés.</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={openRecipeComposer}
              className="inline-flex items-center gap-2 rounded-2xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
            >
              <Plus className="w-4 h-4" />
              Nouvelle recette
            </button>
            <button
              type="button"
              onClick={() => {
                setRecipeError(null);
                setRecipeFeedback(null);
                setEditingMealPlanId(null);
                setMealPlanForm(EMPTY_MEAL_PLAN_FORM);
                setShowMealPlanComposer(true);
              }}
              className="inline-flex items-center gap-2 rounded-2xl border border-apple-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-apple-gray-50"
            >
              <CalendarClock className="w-4 h-4" />
              Planifier
            </button>
          </div>
        </div>
      </div>

      <div className="px-4 py-4 space-y-4 md:px-8 md:py-6">
        <ComposerSheet
          open={showRecipeComposer}
          onClose={resetRecipeEditor}
          eyebrow={editingRecipeId !== null ? 'Modifier la recette' : 'Nouvelle recette'}
          title={editingRecipeId !== null ? 'Édition manuelle' : 'Saisie manuelle'}
          subtitle={editingRecipeId !== null
            ? 'Modifie la recette, ses ingrédients, ses étapes et ses ustensiles.'
            : 'Crée la recette à la main. Les ingrédients peuvent ensuite être reliés à des produits magasin ou rester personnalisés.'}
          panelClassName="md:max-w-5xl"
        >
          <div className="rounded-[28px] border border-white/60 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl space-y-4 md:p-5">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <div className="flex items-center gap-2 text-red-600 text-xs font-bold uppercase tracking-wider">
                <ChefHat className="w-4 h-4" />
                {editingRecipeId !== null ? 'Modifier la recette' : 'Nouvelle recette'}
              </div>
              <h2 className="text-lg font-semibold text-black mt-2">
                {editingRecipeId !== null ? 'Édition manuelle' : 'Saisie manuelle'}
              </h2>
              <p className="text-sm text-apple-gray-500 mt-1">
                {editingRecipeId !== null
                  ? 'Modifie la recette, ses ingrédients, ses étapes et ses ustensiles.'
                  : 'Crée la recette à la main. Les ingrédients peuvent ensuite être reliés à des produits magasin ou rester personnalisés.'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {editingRecipeId !== null && (
                <button
                  type="button"
                  onClick={resetRecipeEditor}
              className="inline-flex items-center gap-2 rounded-2xl border border-apple-gray-200 px-4 py-2.5 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                >
                  <X className="w-4 h-4" />
                  Annuler
                </button>
              )}
              <button
                onClick={() => void saveRecipe()}
                disabled={recipeSaving}
              className="inline-flex items-center gap-2 rounded-2xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
              >
                {recipeSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : editingRecipeId !== null ? <CheckCircle2 className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                {editingRecipeId !== null ? 'Enregistrer' : 'Créer la recette'}
              </button>
            </div>
          </div>

          {editingRecipeId !== null && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center justify-between gap-3 flex-wrap">
              <span>Mode édition actif. Tes modifications seront appliquées à la recette existante.</span>
              <button
                type="button"
                onClick={resetRecipeEditor}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-white px-3 py-1.5 font-semibold text-amber-700 hover:bg-amber-100"
              >
                <X className="w-4 h-4" />
                Quitter l’édition
              </button>
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            <input
              value={recipeForm.name}
              onChange={(e) => setRecipeForm((current) => ({ ...current, name: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Nom de la recette"
            />
            <input
              value={recipeForm.prep_minutes}
              onChange={(e) => setRecipeForm((current) => ({ ...current, prep_minutes: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Préparation (min)"
              inputMode="numeric"
            />
            <input
              value={recipeForm.cook_minutes}
              onChange={(e) => setRecipeForm((current) => ({ ...current, cook_minutes: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Cuisson (min)"
              inputMode="numeric"
            />
            <input
              value={recipeForm.servings}
              onChange={(e) => setRecipeForm((current) => ({ ...current, servings: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Portions"
              inputMode="numeric"
            />
            <input
              value={recipeForm.tags}
              onChange={(e) => setRecipeForm((current) => ({ ...current, tags: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Tags séparés par des virgules"
            />
          </div>

          <textarea
            value={recipeForm.description}
            onChange={(e) => setRecipeForm((current) => ({ ...current, description: e.target.value }))}
            className="w-full min-h-24 px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm resize-y"
            placeholder="Description"
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Étapes</p>
                  <p className="text-sm text-apple-gray-500 mt-1">Ajoute les étapes une par une.</p>
                </div>
                <button
                  type="button"
                  onClick={addStepDraft}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-sm font-semibold text-black hover:bg-apple-gray-50"
                >
                  <Plus className="w-4 h-4" />
                  Ajouter une étape
                </button>
              </div>

              <div className="space-y-2">
                {stepDrafts.map((draft, index) => (
                  <div key={draft.id} className="rounded-2xl border border-apple-gray-200 bg-apple-gray-50/60 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-apple-blue/10 text-xs font-bold text-apple-blue">
                          {index + 1}
                        </span>
                        <p className="text-sm font-semibold text-black truncate">
                          {draft.value.trim() || `Étape ${index + 1}`}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeStepDraft(index)}
                        className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 bg-white px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                      >
                        <X className="w-4 h-4" />
                        Supprimer
                      </button>
                    </div>
                    <input
                      value={draft.value}
                      onChange={(e) => updateStepDraft(index, e.target.value)}
                      className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white"
                      placeholder={`Étape ${index + 1}`}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Ustensiles</p>
                  <p className="text-sm text-apple-gray-500 mt-1">Ajoute les ustensiles un par un.</p>
                </div>
                <button
                  type="button"
                  onClick={addUtensilDraft}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-sm font-semibold text-black hover:bg-apple-gray-50"
                >
                  <Plus className="w-4 h-4" />
                  Ajouter un ustensile
                </button>
              </div>

              <div className="space-y-2">
                {utensilDrafts.map((draft, index) => (
                  <div key={draft.id} className="rounded-2xl border border-apple-gray-200 bg-apple-gray-50/60 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-apple-gray-100 text-xs font-bold text-apple-gray-600">
                          {index + 1}
                        </span>
                        <p className="text-sm font-semibold text-black truncate">
                          {draft.value.trim() || `Ustensile ${index + 1}`}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeUtensilDraft(index)}
                        className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 bg-white px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                      >
                        <X className="w-4 h-4" />
                        Supprimer
                      </button>
                    </div>
                    <input
                      value={draft.value}
                      onChange={(e) => updateUtensilDraft(index, e.target.value)}
                      className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white"
                      placeholder={`Ustensile ${index + 1}`}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <input
              value={recipeForm.source_url}
              onChange={(e) => setRecipeForm((current) => ({ ...current, source_url: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="URL source"
            />
            <input
              value={recipeForm.source_platform}
              onChange={(e) => setRecipeForm((current) => ({ ...current, source_platform: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Plateforme source"
            />
            <input
              value={recipeForm.source_title}
              onChange={(e) => setRecipeForm((current) => ({ ...current, source_title: e.target.value }))}
              className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm"
              placeholder="Titre source"
            />
          </div>

          <textarea
            value={recipeForm.source_description}
            onChange={(e) => setRecipeForm((current) => ({ ...current, source_description: e.target.value }))}
            className="w-full min-h-40 px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm resize-y"
            placeholder="Description / contexte optionnel"
          />

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Ingrédients</p>
                <p className="text-sm text-apple-gray-500 mt-1">Ajoute des lignes custom ou relie-les à un produit magasin.</p>
              </div>
              <button
                type="button"
                onClick={addDraftIngredient}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-sm font-semibold text-black hover:bg-apple-gray-50"
              >
                <Plus className="w-4 h-4" />
                Ajouter un ingrédient
              </button>
            </div>

            <div className="space-y-3">
              {ingredientDrafts.map((draft, index) => {
                const isStoreBacked = Boolean(draft.external_id);
                return (
                  <div key={draft.id} className="rounded-2xl border border-apple-gray-200 bg-apple-gray-50/60 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-black">
                            {draft.name.trim() || `Ingrédient ${index + 1}`}
                          </p>
                          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${isStoreBacked ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-apple-gray-100 text-apple-gray-600 border border-apple-gray-200'}`}>
                            {isStoreBacked ? (draft.store_label || 'Magasin') : 'Personnalisé'}
                          </span>
                        </div>
                        {isStoreBacked && (
                          <p className="text-xs text-apple-gray-500 mt-1">
                            {[draft.category, draft.packaging, draft.price_text].filter(Boolean).join(' · ') || 'Produit lié'}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => openDraftIngredientPanel(index)}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50"
                        >
                          <Store className="w-4 h-4" />
                          {isStoreBacked ? 'Modifier le produit' : 'Lier un produit'}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeDraftIngredient(index)}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-apple-gray-600 text-sm font-semibold hover:bg-apple-gray-50"
                        >
                          <X className="w-4 h-4" />
                          Supprimer
                        </button>
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-[1.6fr_0.6fr_0.6fr]">
                      <input
                        value={draft.name}
                        onChange={(e) => updateDraftIngredient(index, { name: e.target.value })}
                        className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white"
                        placeholder="Nom de l’ingrédient"
                      />
                      <input
                        value={draft.quantity}
                        onChange={(e) => updateDraftIngredient(index, { quantity: e.target.value })}
                        className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white"
                        placeholder="Quantité"
                        inputMode="decimal"
                      />
                      <input
                        value={draft.unit}
                        onChange={(e) => updateDraftIngredient(index, { unit: e.target.value })}
                        className="w-full px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white"
                        placeholder="Unité"
                      />
                    </div>

                    <textarea
                      value={draft.note}
                      onChange={(e) => updateDraftIngredient(index, { note: e.target.value })}
                      className="w-full min-h-20 px-3 py-2.5 rounded-xl border border-apple-gray-200 text-sm resize-y bg-white"
                      placeholder="Note optionnelle"
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {(recipeFeedback || recipeError) && (
            <div className={`rounded-xl px-4 py-3 text-sm ${recipeError ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'}`}>
              {recipeError || recipeFeedback}
            </div>
          )}
          </div>
        </ComposerSheet>

        <div className="max-w-4xl mx-auto grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-4">
            {loading ? (
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm py-16 flex items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-apple-blue" />
              </div>
            ) : recipes.length === 0 ? (
              <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm py-16 text-center">
                <ChefHat className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                <p className="text-apple-gray-500 text-sm">Aucune recette pour l’instant</p>
              </div>
            ) : (
              recipes.map((recipe) => (
                <div key={recipe.id} className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden">
                  <div className="px-5 py-4 border-b border-apple-gray-100">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div>
                        <h2 className="text-lg font-semibold text-black">{recipe.name}</h2>
                        <p className="text-sm text-apple-gray-500 mt-1">
                          {recipe.ingredients.length} ingrédient(s) · {recipe.servings} portion(s)
                        </p>
                        {(recipe.source_platform || recipe.source_title) && (
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <p className="text-xs text-apple-gray-400">
                              {recipe.source_platform ? recipe.source_platform.toUpperCase() : 'SOURCE'}{recipe.source_title ? ` · ${recipe.source_title}` : ''}
                            </p>
                            {recipe.source_url && (
                              <a
                                href={recipe.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 rounded-full border border-apple-gray-200 px-2.5 py-1 text-xs font-semibold text-apple-gray-700 hover:bg-apple-gray-50"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                                Voir la source
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2 justify-end">
                        <button
                          type="button"
                          onClick={() => startCreateMealPlan(recipe)}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-sm font-semibold text-black hover:bg-apple-gray-50"
                        >
                          <CalendarClock className="w-4 h-4" />
                          Planifier
                        </button>
                        <button
                          type="button"
                          onClick={() => startEditRecipe(recipe)}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-apple-gray-200 text-sm font-semibold text-black hover:bg-apple-gray-50"
                        >
                          <Link2 className="w-4 h-4" />
                          Modifier
                        </button>
                        <button
                          type="button"
                          onClick={() => void deleteRecipe(recipe)}
                          disabled={recipeDeletingId === recipe.id}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-red-200 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                        >
                          {recipeDeletingId === recipe.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <X className="w-4 h-4" />
                          )}
                          Supprimer
                        </button>
                        <button
                          onClick={() => void confirmRecipeCooked(recipe)}
                          disabled={recipeCookingId === recipe.id}
                          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50"
                        >
                          {recipeCookingId === recipe.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4" />
                          )}
                          J’ai fait
                        </button>
                      </div>
                    </div>
                  </div>
                  <div className="px-5 py-4 grid gap-4 lg:grid-cols-2">
                    <div className="space-y-2">
                      <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Ingrédients</p>
                      <div className="divide-y divide-apple-gray-50 rounded-2xl border border-apple-gray-100 overflow-hidden">
                        {recipe.ingredients.map((ingredient) => (
                          <div key={ingredient.id} className="px-4 py-3 flex items-center gap-3">
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-semibold text-black">{ingredient.name}</p>
                              <p className="text-xs text-apple-gray-500">
                                {ingredient.quantity} {ingredient.unit}
                              </p>
                              {(ingredient.store_label || ingredient.category || ingredient.packaging || ingredient.price_text) && (
                                <p className="text-xs text-apple-gray-400 mt-1">
                                  {[ingredient.store_label, ingredient.category, ingredient.packaging, ingredient.price_text].filter(Boolean).join(' · ')}
                                </p>
                              )}
                            </div>
                            <button
                              onClick={() => void openIngredientPanel(ingredient)}
                              className="px-3 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-medium hover:bg-red-50"
                            >
                              <span className="inline-flex items-center gap-2">
                                <Store className="w-4 h-4" />
                                Lier
                              </span>
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500 mb-2">Étapes</p>
                        {recipe.steps.length > 0 ? (
                          <ol className="space-y-2 rounded-2xl border border-apple-gray-100 p-4">
                            {recipe.steps.map((step, index) => (
                              <li key={`${recipe.id}-step-${index}`} className="flex gap-3 text-sm text-black">
                                <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-apple-blue/10 text-[11px] font-bold text-apple-blue">
                                  {index + 1}
                                </span>
                                <span>{step}</span>
                              </li>
                            ))}
                          </ol>
                        ) : (
                          <p className="rounded-2xl border border-dashed border-apple-gray-200 p-4 text-sm text-apple-gray-400">
                            Aucune étape enregistrée
                          </p>
                        )}
                      </div>

                      <div>
                        <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500 mb-2">Ustensiles</p>
                        {recipe.utensils.length > 0 ? (
                          <div className="flex flex-wrap gap-2 rounded-2xl border border-apple-gray-100 p-4">
                            {recipe.utensils.map((utensil) => (
                              <span key={`${recipe.id}-utensil-${utensil}`} className="rounded-full bg-apple-gray-100 px-3 py-1.5 text-xs font-semibold text-apple-gray-600">
                                {utensil}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="rounded-2xl border border-dashed border-apple-gray-200 p-4 text-sm text-apple-gray-400">
                            Aucun ustensile renseigné
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="space-y-4 lg:sticky lg:top-6 lg:self-start">
            <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-apple-gray-100 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-red-600">
                  {activeDraftIndex !== null ? 'Produit du brouillon' : 'Mapping ingrédient'}
                </p>
                <h3 className="text-sm font-semibold text-black mt-1">
                  {activeIngredient
                    ? activeIngredient.name
                    : activeDraftIndex !== null
                      ? ingredientDrafts[activeDraftIndex]?.name || `Ingrédient ${activeDraftIndex + 1}`
                      : 'Sélectionne un ingrédient'}
                </h3>
              </div>
              {(activeIngredient || activeDraftIndex !== null) && (
                <button onClick={resetIngredientSelection} className="p-2 rounded-lg hover:bg-apple-gray-100 text-apple-gray-500">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="p-5 space-y-4">
              {!activeIngredient && activeDraftIndex === null ? (
                <p className="text-sm text-apple-gray-500">Choisis un ingrédient sauvegardé ou un ingrédient du brouillon pour rechercher un produit magasin.</p>
              ) : (
                <>
                  {activeIngredient && mapping ? (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">{mapping.store_label}</p>
                          <p className="text-sm font-semibold text-black">{mapping.name_snapshot}</p>
                          <p className="text-xs text-apple-gray-500">
                            {[mapping.category_snapshot, mapping.packaging_snapshot, mapping.price_snapshot].filter(Boolean).join(' · ') || 'Produit lié'}
                          </p>
                        </div>
                        <button onClick={() => void unlinkIngredient()} className="p-2 rounded-lg hover:bg-white/70 text-red-600">
                          <Unlink className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ) : activeIngredient ? (
                    <p className="text-sm text-apple-gray-500">Aucun mapping actif pour cet ingrédient.</p>
                  ) : null}

                  {activeDraftIndex !== null && (
                    <div className="rounded-xl border border-apple-gray-200 bg-apple-gray-50 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Brouillon</p>
                      <p className="text-sm font-semibold text-black mt-1">
                        {ingredientDrafts[activeDraftIndex]?.name || `Ingrédient ${activeDraftIndex + 1}`}
                      </p>
                      <p className="text-xs text-apple-gray-500 mt-1">
                        {ingredientDrafts[activeDraftIndex]?.external_id
                          ? 'Produit magasin déjà lié. Tu peux le remplacer.'
                          : 'Choisis un produit pour transformer cette ligne en ingrédient magasin.'}
                      </p>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            void runSearch();
                          }
                        }}
                        className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
                        placeholder="Rechercher chez Intermarché"
                      />
                    </div>
                    <button
                      onClick={() => void runSearch()}
                      disabled={searchLoading || !searchQuery.trim()}
                      className="px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50"
                    >
                      {searchLoading ? 'Recherche…' : 'Rechercher'}
                    </button>
                    {searchQueryHasCache && (
                      <button
                        onClick={() => void runSearch(true)}
                        disabled={searchLoading || !searchQuery.trim()}
                        className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50"
                      >
                        Actualiser
                      </button>
                    )}
                  </div>

                  <label className="flex items-center gap-2 text-sm text-apple-gray-600">
                    <input
                      type="checkbox"
                      checked={searchPromotionsOnly}
                      onChange={(e) => setSearchPromotionsOnly(e.target.checked)}
                      className="h-4 w-4 rounded border-apple-gray-300 text-red-600 focus:ring-red-400"
                    />
                    Promotions uniquement
                  </label>

                  <div className="space-y-2">
                    {searchResults.map((result) => (
                      <div key={result.cache_id} className="rounded-xl border border-apple-gray-200 p-3 flex items-center gap-3">
                        {result.image_url ? (
                          <img src={result.image_url} alt={result.name} className="w-14 h-14 rounded-lg object-contain bg-white p-1 border border-apple-gray-100" />
                        ) : (
                          <div className="w-14 h-14 rounded-lg bg-apple-gray-100 flex items-center justify-center">
                            <ChefHat className="w-5 h-5 text-apple-gray-300" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-black truncate">{result.name}</p>
                          <p className="text-xs text-apple-gray-500">
                            {[result.category, result.packaging, result.price_text].filter(Boolean).join(' · ') || 'Aucun détail'}
                          </p>
                        </div>
                        <button
                          onClick={() => void linkIngredient(result)}
                          className="px-3 py-2 rounded-xl bg-apple-blue text-white text-sm font-semibold hover:bg-blue-600 inline-flex items-center gap-2"
                        >
                          <Link2 className="w-4 h-4" />
                          Lier
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
            </div>

            <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-apple-gray-100 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-red-600">
                    {editingMealPlanId !== null ? 'Modifier la planification' : 'Planification'}
                  </p>
                  <h3 className="text-sm font-semibold text-black mt-1">
                    {editingMealPlanId !== null ? 'Plan existant' : 'Créer une planification'}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowMealPlanComposer((current) => !current)}
                    className="rounded-xl border border-apple-gray-200 bg-white px-3 py-2 text-xs font-semibold text-black transition-colors hover:bg-apple-gray-50"
                  >
                    {showMealPlanComposer ? 'Fermer' : 'Ouvrir'}
                  </button>
                  {editingMealPlanId !== null && (
                    <button onClick={resetMealPlanEditor} className="p-2 rounded-lg hover:bg-apple-gray-100 text-apple-gray-500">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {!showMealPlanComposer && (
                <div className="p-5">
                  <div className="rounded-2xl border border-dashed border-apple-gray-200 bg-apple-gray-50/50 p-4">
                    <p className="text-sm font-semibold text-black">Aucune planification ouverte.</p>
                    <p className="mt-1 text-sm text-apple-gray-500">
                      Ouvre une planification pour choisir une recette, fixer un créneau et préparer les courses si besoin.
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowMealPlanComposer(true)}
                      className="mt-4 inline-flex items-center gap-2 rounded-xl bg-apple-blue px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                    >
                      <CalendarClock className="w-4 h-4" />
                      Ouvrir la planification
                    </button>
                  </div>
                </div>
              )}

              <div className={`p-5 space-y-4 ${showMealPlanComposer ? '' : 'hidden'}`}>
                <div className="space-y-3">
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Recette</span>
                    <select
                      value={mealPlanForm.recipe_id}
                      onChange={(e) => setMealPlanForm((current) => ({ ...current, recipe_id: e.target.value }))}
                      className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                    >
                      <option value="">Choisir une recette</option>
                      {recipes.map((recipe) => (
                        <option key={recipe.id} value={recipe.id}>
                          {recipe.name}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Date et heure</span>
                      <input
                        type="datetime-local"
                        value={mealPlanForm.planned_at}
                        onChange={(e) => setMealPlanForm((current) => ({ ...current, planned_at: e.target.value }))}
                        className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Portions</span>
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={mealPlanForm.servings_override}
                        onChange={(e) => setMealPlanForm((current) => ({ ...current, servings_override: e.target.value }))}
                        className="w-full rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm"
                        placeholder="Optionnel"
                      />
                    </label>
                  </div>

                  <label className="block">
                    <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-apple-gray-500">Note</span>
                    <textarea
                      value={mealPlanForm.note}
                      onChange={(e) => setMealPlanForm((current) => ({ ...current, note: e.target.value }))}
                      className="w-full min-h-24 rounded-xl border border-apple-gray-200 bg-white px-3 py-2.5 text-sm resize-y"
                      placeholder="Ajouter un contexte ou une contrainte"
                    />
                  </label>

                  <label className="flex items-start gap-3 rounded-xl border border-apple-gray-200 bg-apple-gray-50 px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={mealPlanForm.auto_add_missing_ingredients}
                      onChange={(e) => setMealPlanForm((current) => ({ ...current, auto_add_missing_ingredients: e.target.checked }))}
                      className="mt-1 h-4 w-4 rounded border-apple-gray-300 text-red-600 focus:ring-red-500"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-black">Ajouter automatiquement les manquants aux courses</span>
                      <span className="block text-xs text-apple-gray-500 mt-0.5">Le panier reste la source de vérité; l’ajout se fait seulement si ce bouton est activé.</span>
                    </span>
                  </label>

                  <div className="flex flex-col sm:flex-row gap-2">
                    {editingMealPlanId !== null && (
                      <button
                        type="button"
                        onClick={resetMealPlanEditor}
                        className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50"
                      >
                        <X className="w-4 h-4" />
                        Annuler
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => void saveMealPlan()}
                      disabled={mealPlanSaving}
                      className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-apple-blue text-white text-sm font-semibold hover:bg-blue-600 disabled:opacity-50"
                    >
                      {mealPlanSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarClock className="w-4 h-4" />}
                      {editingMealPlanId !== null ? 'Enregistrer la planification' : 'Planifier'}
                    </button>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-apple-gray-500">Planifications</p>
                      <p className="text-sm text-apple-gray-500 mt-1">Actions rapides et suivi des planifications existantes.</p>
                    </div>
                    {mealPlansLoading && <Loader2 className="w-4 h-4 animate-spin text-apple-gray-400" />}
                  </div>

                  <div className="space-y-2">
                    {!mealPlansLoading && mealPlans.length === 0 ? (
                      <p className="rounded-xl border border-dashed border-apple-gray-200 p-4 text-sm text-apple-gray-400">
                        Aucune planification enregistrée
                      </p>
                    ) : (
                      mealPlans.map((plan) => {
                        const missingCount = plan.missing_ingredients.filter((ingredient) => ingredient.missing_quantity > 0).length;
                        return (
                          <div key={plan.id} className="rounded-xl border border-apple-gray-200 p-4 space-y-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-black truncate">{plan.recipe_name}</p>
                                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-apple-gray-500">
                                  <span className="inline-flex items-center gap-1">
                                    <Clock className="w-3.5 h-3.5" />
                                    {formatMealPlanDateTime(plan.planned_at)}
                                  </span>
                                  {plan.cooked ? (
                                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-700">Cuisinée</span>
                                  ) : (
                                    <span className="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700">À faire</span>
                                  )}
                                  {plan.auto_add_missing_ingredients && (
                                    <span className="rounded-full bg-apple-gray-100 px-2 py-0.5 font-semibold text-apple-gray-600">Sync courses</span>
                                  )}
                                  {missingCount > 0 && (
                                    <span className="rounded-full bg-red-50 px-2 py-0.5 font-semibold text-red-700">
                                      {missingCount} manquant(s)
                                    </span>
                                  )}
                                </div>
                                {plan.note && <p className="mt-2 text-xs text-apple-gray-500 line-clamp-2">{plan.note}</p>}
                              </div>
                            </div>

                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                onClick={() => startEditMealPlan(plan)}
                                className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-black hover:bg-apple-gray-50"
                              >
                                <Link2 className="w-4 h-4" />
                                Modifier
                              </button>
                              <button
                                type="button"
                                onClick={() => void syncMealPlanGroceries(plan)}
                                disabled={mealPlanActionId === plan.id}
                                className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
                              >
                                {mealPlanActionId === plan.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Store className="w-4 h-4" />}
                                Courses
                              </button>
                              {plan.cooked ? (
                                <button
                                  type="button"
                                  onClick={() => void unconfirmMealPlanCooked(plan)}
                                  disabled={mealPlanActionId === plan.id}
                                  className="inline-flex items-center gap-2 rounded-xl border border-amber-200 px-3 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                                >
                                  {mealPlanActionId === plan.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
                                  Annuler
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => void confirmMealPlanCooked(plan)}
                                  disabled={mealPlanActionId === plan.id}
                                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                                >
                                  {mealPlanActionId === plan.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                                  J’ai fait
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => void deleteMealPlan(plan)}
                                disabled={mealPlanActionId === plan.id}
                                className="inline-flex items-center gap-2 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm font-semibold text-apple-gray-600 hover:bg-apple-gray-50 disabled:opacity-50"
                              >
                                {mealPlanActionId === plan.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                                Supprimer
                              </button>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
