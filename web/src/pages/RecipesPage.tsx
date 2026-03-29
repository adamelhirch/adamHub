import { useEffect, useState } from 'react';
import { ChefHat, Link2, Loader2, Search, Store, Unlink, X } from 'lucide-react';
import api from '../lib/api';

type RecipeIngredient = {
  id: number;
  recipe_id: number;
  name: string;
  quantity: number;
  unit: string;
  note: string | null;
};

type Recipe = {
  id: number;
  name: string;
  description: string | null;
  instructions: string;
  prep_minutes: number;
  cook_minutes: number;
  servings: number;
  tags: string[];
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

function hasResolvedCategories(results: SupermarketSearchResult[]): boolean {
  return results.some((result) => Boolean(result.category?.trim()));
}

export default function RecipesPage() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeIngredient, setActiveIngredient] = useState<RecipeIngredient | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SupermarketSearchResult[]>([]);
  const [mapping, setMapping] = useState<SupermarketMapping | null>(null);
  const [searchQueryHasCache, setSearchQueryHasCache] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await api.get('/recipes');
        setRecipes(res.data);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

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
    setActiveIngredient(ingredient);
    setSearchQuery(ingredient.name);
    setSearchResults([]);
    const res = await api.get(`/supermarket/mappings/recipe-ingredients/${ingredient.id}`);
    setMapping(res.data);
  };

  const runSearch = async (forceRefresh = false) => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      if (!forceRefresh) {
        const cached = await api.get('/supermarket/search', {
          params: {
            store: 'intermarche',
            query: searchQuery.trim(),
            limit: 20,
          },
        });
        if (Array.isArray(cached.data) && cached.data.length > 0 && hasResolvedCategories(cached.data)) {
          setSearchResults(cached.data);
          return;
        }
      }

      const res = await api.post('/supermarket/search', {
        store: 'intermarche',
        queries: [searchQuery.trim()],
        max_results: 10,
      }, { timeout: 120_000 });
      setSearchResults(res.data);
    } finally {
      setSearchLoading(false);
    }
  };

  const linkIngredient = async (result: SupermarketSearchResult) => {
    if (!activeIngredient) return;
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
  };

  const unlinkIngredient = async () => {
    if (!mapping) return;
    await api.delete(`/supermarket/mappings/${mapping.id}`);
    setMapping(null);
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-apple-gray-50 overflow-y-auto">
      <div className="px-8 py-5 border-b border-apple-gray-200 bg-white shadow-sm flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-black">Recipes</h1>
          <p className="text-apple-gray-500 mt-0.5 text-sm">Lier les ingrédients de recette à Intermarché</p>
        </div>
      </div>

      <div className="p-6">
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
                    <h2 className="text-lg font-semibold text-black">{recipe.name}</h2>
                    <p className="text-sm text-apple-gray-500 mt-1">
                      {recipe.ingredients.length} ingrédient(s) · {recipe.servings} portion(s)
                    </p>
                  </div>
                  <div className="divide-y divide-apple-gray-50">
                    {recipe.ingredients.map((ingredient) => (
                      <div key={ingredient.id} className="px-5 py-4 flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-black">{ingredient.name}</p>
                          <p className="text-xs text-apple-gray-500">
                            {ingredient.quantity} {ingredient.unit}
                          </p>
                        </div>
                        <button
                          onClick={() => void openIngredientPanel(ingredient)}
                          className="px-3 py-2 rounded-xl border border-red-200 text-red-600 text-sm font-medium hover:bg-red-50"
                        >
                          <span className="inline-flex items-center gap-2">
                            <Store className="w-4 h-4" />
                            Lier Intermarché
                          </span>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm h-fit sticky top-6">
            <div className="px-5 py-4 border-b border-apple-gray-100 flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-red-600">Mapping ingrédient</p>
                <h3 className="text-sm font-semibold text-black mt-1">
                  {activeIngredient ? activeIngredient.name : 'Sélectionne un ingrédient'}
                </h3>
              </div>
              {activeIngredient && (
                <button onClick={() => setActiveIngredient(null)} className="p-2 rounded-lg hover:bg-apple-gray-100 text-apple-gray-500">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="p-5 space-y-4">
              {!activeIngredient ? (
                <p className="text-sm text-apple-gray-500">Choisis un ingrédient à droite pour rechercher un produit Intermarché.</p>
              ) : (
                <>
                  {mapping ? (
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
                  ) : (
                    <p className="text-sm text-apple-gray-500">Aucun mapping actif pour cet ingrédient.</p>
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
        </div>
      </div>
    </div>
  );
}
